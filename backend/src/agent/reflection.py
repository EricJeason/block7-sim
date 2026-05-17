"""Block G.1:每日反思 — 跨游戏日时把当日记忆压缩为高层 reflection。

参见 v0.2 §2.5 / §3.4 / 工作展望.md G.1。

流程:
1. 每跨一个游戏日(SimEngine 检测 game_time // 86400 变化)→ 触发 ReflectionRunner
2. 拉当日所有 memory(observation + plan, importance ≥ 4)
3. 调 Pro + think_high 生成 5-10 条 reflection
4. 写入 memory_type='reflection',importance 由 LLM 自评

Prompt 复用 4 层结构(Layer 0 暮谷镇 + Layer 1 PersonaProfile +
Layer 2 当日 memory dump + Layer 3 反思任务)— 与 LLMPlanner 共享同一
Layer 0/1 缓存命名空间,保持命中率。

并发限制:Pro think_high 单次 60-90 秒,12 agent 同时跑会占满 DeepSeek 连接
+ 让 fine plan 排队。用 asyncio.Semaphore 限制 max_concurrent=3,
让 fine plan 仍能正常被服务。
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

from src.agent.planning import PersonaLoader, build_rich_layer_1
from src.llm.deepseek import DeepSeekClient, ThinkMode
from src.llm.prompt_builder import PromptBuilder
from src.memory.store import Memory, MemoryStore

logger = logging.getLogger(__name__)

# 默认拉当日 importance ≥ 4 的 memory 作为反思输入
DEFAULT_MIN_IMPORTANCE = 4
# 默认希望 LLM 产出多少条 reflection
DEFAULT_REFLECTION_COUNT = 7
# 反思任务并发上限(防止 12 个 Pro think_high 同时跑饿死 fine plan)
DEFAULT_MAX_CONCURRENT = 3
SECONDS_PER_GAME_DAY = 86400.0

_JSON_OBJECT_RE = re.compile(r"\{[\s\S]*\}")


REFLECTION_TASK = """昨天(游戏内第 {game_day} 天)你经历的事:

{memory_dump}

【任务】
回顾这一整天的经历,从一个普通村民、一个 {occupation} 的视角,写下 5-10 条
高层"反思"(reflection)。这些反思是你**今天才意识到、或被今天的事激活的**洞察,
不是简单复述事件,而是带有以下任一性质:

- 把多件事串联起来的判断("我注意到 A 和 B 都……,这说明……")
- 对人际关系微妙变化的察觉("阿杏对我的语气比上周冷了一点")
- 对自己内心状态的诚实承认("我嘴上说放心,其实昨晚没睡好")
- 对未来的预感或决定("明天必须找早纪谈一次")
- 与你 known_secrets / unknown_to_self / inner_conflict 相关的隐秘思绪

要求:
1. 用第一人称,语言风格符合你的说话方式
2. 每条 30-80 字,不要太空泛、不要堆形容词
3. 每条标一个 importance(1-10):
   - 1-3 = 鸡毛蒜皮的小观察
   - 4-6 = 影响后续行动的中度洞察
   - 7-8 = 重要情感 / 关系发现
   - 9-10 = 决定性领悟(罕见)

严格返回 JSON:
{{
  "reflections": [
    {{"content": "...", "importance": 6}},
    {{"content": "...", "importance": 4}},
    ...
  ]
}}
不要解释,不要 markdown,不要前后缀。"""


@dataclass
class ReflectionResult:
    agent_id: str
    game_day: int
    reflections: list[Memory]  # 已插库的 reflection memories
    source_count: int          # 输入 memory 条数
    cost_yuan: float


class ReflectionRunner:
    """每日反思执行器。

    用法(SimEngine 跨日时):
        runner = ReflectionRunner(llm, persona_loader, memory_store, ...)
        result = await runner.run_for_agent(agent_id, game_day=2, game_time=172800.0)
    """

    def __init__(
        self,
        llm: DeepSeekClient,
        persona_loader: PersonaLoader,
        memory_store: MemoryStore,
        model_pro: str = "deepseek-v4-pro",
        min_importance: int = DEFAULT_MIN_IMPORTANCE,
        seconds_per_game_day: float = SECONDS_PER_GAME_DAY,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
    ) -> None:
        self.llm = llm
        self.persona_loader = persona_loader
        self.memory_store = memory_store
        self.model_pro = model_pro
        self.min_importance = min_importance
        self.seconds_per_game_day = seconds_per_game_day
        # 限制 Pro think_high 反思调用并发,避免饿死 fine plan
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def run_for_agent(
        self,
        agent_id: str,
        game_day: int,
        game_time: float,
    ) -> ReflectionResult:
        """对 agent_id 跑一次反思(受 semaphore 限制)。

        game_day:反思的目标日(0-indexed,内部计算时段)
        game_time:当前 sim 时间,用于写入 reflection 的 game_time 字段
        """
        async with self._semaphore:
            return await self._run_for_agent_inner(agent_id, game_day, game_time)

    async def _run_for_agent_inner(
        self,
        agent_id: str,
        game_day: int,
        game_time: float,
    ) -> ReflectionResult:
        try:
            persona = self.persona_loader.load(agent_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[reflection] persona load failed agent=%s: %s", agent_id, exc)
            return ReflectionResult(agent_id, game_day, [], 0, 0.0)

        time_min = float(game_day) * self.seconds_per_game_day
        time_max = float(game_day + 1) * self.seconds_per_game_day

        # 拉当日 observation + plan + 已有 reflection(去重时排除)
        try:
            source = await self.memory_store.get_in_time_range(
                agent_id=agent_id,
                game_time_min=time_min,
                game_time_max=time_max,
                memory_types=["observation", "plan"],
                min_importance=self.min_importance,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[reflection] memory fetch failed agent=%s: %s", agent_id, exc)
            return ReflectionResult(agent_id, game_day, [], 0, 0.0)

        if not source:
            logger.info(
                "[reflection] agent=%s day=%d: no source memory (imp ≥ %d), skip",
                agent_id, game_day, self.min_importance,
            )
            return ReflectionResult(agent_id, game_day, [], 0, 0.0)

        # 构 prompt 4 层
        layer_0 = PromptBuilder.LAYER_0_SYSTEM
        layer_1 = build_rich_layer_1(persona)
        memory_dump = self._format_memory_dump(source)
        task = REFLECTION_TASK.format(
            game_day=game_day + 1,
            memory_dump=memory_dump,
            occupation=persona.occupation,
        )
        messages = [
            {"role": "system", "content": layer_0 + "\n" + layer_1},
            {"role": "user", "content": task},
        ]

        try:
            # max_tokens 3000:同 daily plan,留足 think_high 推理 + JSON 输出空间
            response = await self.llm.chat(
                messages=messages,
                model=self.model_pro,
                mode=ThinkMode.THINK_HIGH,
                temperature=0.6,
                max_tokens=3000,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[reflection] LLM failed agent=%s day=%d: %s: %r",
                agent_id, game_day, type(exc).__name__, exc,
            )
            return ReflectionResult(agent_id, game_day, [], len(source), 0.0)

        parsed = self._parse_reflections(response.content)
        if not parsed:
            logger.warning(
                "[reflection] parse empty agent=%s day=%d raw=%r",
                agent_id, game_day, response.content[:200],
            )
            return ReflectionResult(
                agent_id, game_day, [], len(source), response.usage.cost_yuan
            )

        # 写库
        written: list[Memory] = []
        for content, importance in parsed:
            mem = Memory(
                memory_id=None,
                agent_id=agent_id,
                memory_type="reflection",
                content=content,
                importance=importance,
                game_time=game_time,
                real_time=time.time(),
                location=None,
                related_agents=[],
                keywords=["反思", f"day{game_day + 1}"],
            )
            try:
                await self.memory_store.insert(mem)
                written.append(mem)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[reflection] insert failed: %s", exc)

        logger.info(
            "[reflection] agent=%s day=%d: %d source → %d reflection, cost=%.4f元",
            agent_id, game_day, len(source), len(written), response.usage.cost_yuan,
        )
        return ReflectionResult(
            agent_id, game_day, written, len(source), response.usage.cost_yuan
        )

    # ------------------------------------------------------- helpers

    def _format_memory_dump(self, memories: list[Memory]) -> str:
        """把当日 memory 格式化成可读列表。"""
        lines: list[str] = []
        for mem in memories:
            tag = mem.memory_type[0].upper()  # O/P
            t_str = self._format_game_time(mem.game_time)
            content = mem.content.strip().replace("\n", " ")
            lines.append(f"  - [{t_str} {tag} imp={mem.importance}] {content}")
        return "\n".join(lines) if lines else "  (今日无显著事件)"

    def _format_game_time(self, game_time: float) -> str:
        seconds_today = game_time % self.seconds_per_game_day
        hour = int(seconds_today // 3600)
        minute = int((seconds_today % 3600) // 60)
        return f"{hour:02d}:{minute:02d}"

    def _parse_reflections(self, raw_content: str) -> list[tuple[str, int]]:
        """解析 LLM 输出的 JSON {"reflections": [{"content":..., "importance":...}, ...]}

        复用 planning._robust_json_loads:容错 markdown 包裹 + trailing comma。
        """
        # 延迟导入避免循环依赖
        from src.agent.planning import _robust_json_loads
        data = _robust_json_loads(raw_content)
        if not isinstance(data, dict):
            return []
        raw_list = data.get("reflections")
        if not isinstance(raw_list, list):
            return []
        out: list[tuple[str, int]] = []
        for item in raw_list:
            if not isinstance(item, dict):
                continue
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            try:
                importance = int(item.get("importance", 5))
            except (TypeError, ValueError):
                importance = 5
            importance = max(1, min(10, importance))
            out.append((content, importance))
        return out


# ============================================================================
#                  Module-level legacy wrapper (Block A 占位)
# ============================================================================


async def reflect_daily(agent_id: str, day_index: int) -> list[dict[str, Any]]:
    """Block A 留下的占位签名。Block G 后:请用 ReflectionRunner.run_for_agent。"""
    raise NotImplementedError(
        "Block G:请用 ReflectionRunner.run_for_agent(agent_id, game_day, game_time)"
    )
