"""Block E:粗 + 细两层规划。

参见设计文档 v0.2 §1 / §2.3:
- 粗粒度日程(_plan_daily):每天清晨用 Pro + think_high 生成 5-7 个时段
- 细粒度展开(_plan_fine):被 scheduler 触发(LOW_WATERMARK / EMPTY_QUEUE)时
  用 Flash + non_think 把当前 slot 展开为 3-7 个 QueuedAction
- 紧急分支(_plan_emergency):跳过 daily plan,直接基于 urgent_event 生成动作

LLMPlanner 实现 scheduler.PlanProvider Protocol,可直接注入 ActionScheduler。
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from src.agent.runtime import ActionSource, AgentRuntime, QueuedAction, ThinkingReason
from src.llm.deepseek import DeepSeekClient, ThinkMode
from src.llm.prompt_builder import PromptBuilder
from src.memory.store import Memory, MemoryStore

logger = logging.getLogger(__name__)


# ============================================================================
#                       Persona / Location / DailyPlan
# ============================================================================


@dataclass(frozen=True)
class PersonaProfile:
    """完整 persona,加载自 backend/data/personas/agent_*.yaml。

    富 schema 版本(20+ 字段),用于 Block E/F/G 的 prompt 构造。
    Block A 的 AgentPersona(6 字段)仍存在,供 ImportanceScorer 等轻量场景使用。

    frozen=True 防止缓存被意外改写;list 字段统一转 tuple 强化不可变。
    """

    agent_id: str
    display_name: str
    gender: str
    age: int
    occupation: str
    identity: str
    appearance: str
    traits: tuple[str, ...]
    personality: str
    backstory: str
    speaking_style: str
    long_term_goal: str
    mid_term_goal: str
    short_term_needs: str
    initial_location: str
    typical_locations: tuple[str, ...]
    daily_routine: str
    initial_relationships: tuple[tuple[str, str], ...]
    known_secrets: str
    unknown_to_self: str
    inner_conflict: str
    seed_memories: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class LocationInfo:
    """场所信息,加载自 backend/data/locations.yaml。"""

    location_id: str
    name: str
    type: str  # private / social / public / commercial / liminal
    description: str
    typical_occupants: tuple[str, ...]
    open_hours: str
    adjacent_to: tuple[str, ...]


@dataclass
class DailyPlanSlot:
    """单个时段(粗粒度)。"""

    start_time: str  # "06:00"
    end_time: str  # "08:00"
    activity: str  # 自然语言:"在医工坊接诊"
    location: str  # 场所 id
    notes: str = ""


@dataclass
class DailyPlan:
    """单个 agent 的当日粗粒度日程。"""

    agent_id: str
    game_day: int
    slots: list[DailyPlanSlot] = field(default_factory=list)


# ============================================================================
#                                  Loaders
# ============================================================================

# 默认数据路径:backend/data/{personas/, locations.yaml}
# planning.py 在 backend/src/agent/,parents[2] 是 backend/
_DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DEFAULT_PERSONAS_DIR = _DEFAULT_DATA_DIR / "personas"
DEFAULT_LOCATIONS_FILE = _DEFAULT_DATA_DIR / "locations.yaml"


class PersonaLoader:
    """从 YAML 加载 PersonaProfile。带内存缓存,避免重复磁盘 IO。"""

    def __init__(self, personas_dir: Path | str | None = None) -> None:
        self.personas_dir = Path(personas_dir) if personas_dir else DEFAULT_PERSONAS_DIR
        self._cache: dict[str, PersonaProfile] = {}

    def load(self, agent_id: str) -> PersonaProfile:
        if agent_id in self._cache:
            return self._cache[agent_id]
        path = self.personas_dir / f"{agent_id}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"persona YAML not found: {path}")
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        profile = _parse_persona(raw)
        self._cache[agent_id] = profile
        return profile

    def list_agent_ids(self) -> list[str]:
        return sorted(p.stem for p in self.personas_dir.glob("agent_*.yaml"))


def _parse_persona(raw: dict[str, Any]) -> PersonaProfile:
    """raw YAML dict → PersonaProfile,容忍缺字段。"""
    relationships_raw = raw.get("initial_relationships") or {}
    # sorted(...) 保证 tuple 顺序稳定,prompt 字节稳定
    relationships = tuple(sorted((str(k), str(v)) for k, v in relationships_raw.items()))
    seed_raw = raw.get("seed_memories") or []
    seed = tuple(dict(item) for item in seed_raw if isinstance(item, dict))
    return PersonaProfile(
        agent_id=str(raw["id"]),
        display_name=str(raw.get("display_name", "")),
        gender=str(raw.get("gender", "")),
        age=int(raw.get("age", 0)),
        occupation=str(raw.get("occupation", "")),
        identity=str(raw.get("identity", "")),
        appearance=str(raw.get("appearance", "")),
        traits=tuple(str(t) for t in (raw.get("traits") or [])),
        personality=str(raw.get("personality", "")).strip(),
        backstory=str(raw.get("backstory", "")).strip(),
        speaking_style=str(raw.get("speaking_style", "")),
        long_term_goal=str(raw.get("long_term_goal", "")),
        mid_term_goal=str(raw.get("mid_term_goal", "")),
        short_term_needs=str(raw.get("short_term_needs", "")),
        initial_location=str(raw.get("initial_location", "")),
        typical_locations=tuple(str(loc) for loc in (raw.get("typical_locations") or [])),
        daily_routine=str(raw.get("daily_routine", "")).strip(),
        initial_relationships=relationships,
        known_secrets=str(raw.get("known_secrets", "")).strip(),
        unknown_to_self=str(raw.get("unknown_to_self", "")).strip(),
        inner_conflict=str(raw.get("inner_conflict", "")),
        seed_memories=seed,
    )


class LocationLoader:
    """从 locations.yaml 一次性加载所有场所到内存。"""

    def __init__(self, locations_file: Path | str | None = None) -> None:
        self.locations_file = (
            Path(locations_file) if locations_file else DEFAULT_LOCATIONS_FILE
        )
        self._cache: dict[str, LocationInfo] | None = None
        # F2: yaml 里 LocationInfo dataclass 之外的字段(name_en / anchors)。
        # 这些字段**不进入 LLM prompt**(保护 Layer 0/1/2 cache 字节稳定),
        # 仅给前端使用(锚点站位 / 英文场所名)。通过 extra() 方法暴露。
        self._extra_cache: dict[str, dict[str, Any]] | None = None

    def all(self) -> dict[str, LocationInfo]:
        if self._cache is None:
            self._cache = self._load()
        return self._cache

    def get(self, location_id: str) -> LocationInfo:
        try:
            return self.all()[location_id]
        except KeyError as exc:
            raise KeyError(f"unknown location: {location_id}") from exc

    def extra(self, location_id: str) -> dict[str, Any]:
        """获取 LocationInfo 之外的 yaml 字段(name_en / anchors)。

        与 LocationInfo dataclass 分离,保证不影响 Planner / LLM prompt。
        缺失字段返回空 dict(空字符串 / 空 list)。
        """
        if self._extra_cache is None:
            self._load_extra()
        assert self._extra_cache is not None
        return self._extra_cache.get(location_id, {"name_en": "", "anchors": []})

    def _load_extra(self) -> None:
        if not self.locations_file.exists():
            self._extra_cache = {}
            return
        raw = yaml.safe_load(self.locations_file.read_text(encoding="utf-8"))
        extra: dict[str, dict[str, Any]] = {}
        for entry in (raw or {}).get("locations", []):
            if not isinstance(entry, dict):
                continue
            loc_id = str(entry["id"])
            extra[loc_id] = {
                "name_en": str(entry.get("name_en", "")),
                "anchors": [dict(a) for a in (entry.get("anchors") or [])],
            }
        self._extra_cache = extra

    def _load(self) -> dict[str, LocationInfo]:
        if not self.locations_file.exists():
            raise FileNotFoundError(f"locations.yaml not found: {self.locations_file}")
        raw = yaml.safe_load(self.locations_file.read_text(encoding="utf-8"))
        out: dict[str, LocationInfo] = {}
        for entry in (raw or {}).get("locations", []):
            if not isinstance(entry, dict):
                continue
            loc = LocationInfo(
                location_id=str(entry["id"]),
                name=str(entry.get("name", "")),
                type=str(entry.get("type", "")),
                description=str(entry.get("description", "")).strip(),
                typical_occupants=tuple(
                    str(x) for x in (entry.get("typical_occupants") or [])
                ),
                open_hours=str(entry.get("open_hours", "")),
                adjacent_to=tuple(str(x) for x in (entry.get("adjacent_to") or [])),
            )
            out[loc.location_id] = loc
        return out


# ============================================================================
#                       Prompt Layer 1 (rich persona)
# ============================================================================


def build_rich_layer_1(persona: PersonaProfile) -> str:
    """从 PersonaProfile 构造 Layer 1 — 字节稳定。

    与 PromptBuilder.build_layer_1_persona(用 6 字段 AgentPersona)互不干扰,
    各自形成独立的 DeepSeek 缓存命名空间。
    """
    rels = "\n".join(f"  - {aid}:{desc}" for aid, desc in persona.initial_relationships)
    if not rels:
        rels = "  - (无)"
    traits_text = "、".join(persona.traits) if persona.traits else "(未填)"
    return (
        "【你的人格设定】\n"
        f"姓名:{persona.display_name}\n"
        f"性别:{persona.gender}\n"
        f"年龄:{persona.age}\n"
        f"职业:{persona.occupation}\n"
        f"身份:{persona.identity}\n"
        f"外貌:{persona.appearance}\n"
        f"性格特质:{traits_text}\n"
        f"性格:{persona.personality}\n"
        f"背景:{persona.backstory}\n"
        f"说话风格:{persona.speaking_style}\n"
        f"长期目标:{persona.long_term_goal}\n"
        f"中期目标:{persona.mid_term_goal}\n"
        f"当下需求:{persona.short_term_needs}\n"
        f"内心冲突:{persona.inner_conflict}\n"
        "日常作息:\n"
        f"{persona.daily_routine}\n"
        "关键关系:\n"
        f"{rels}\n"
        "你自己知道但通常不会主动告诉别人的事:\n"
        f"{persona.known_secrets}\n"
    )


# ============================================================================
#                         Prompt templates (Layer 3)
# ============================================================================


_ACTION_VOCAB = """
可选 action_type(也允许其它自定义类型):
- move_to(args.location):走到某场所,duration 视距离,默认 30-60 秒
- idle(args.reason):短暂停顿/等待,duration 5-30 秒
- work(args.task):进行某项工作(配药、打铁、写报告等),duration 60-300 秒
- rest(args.reason):休息/进餐/睡眠,duration 60-600 秒
- observe(args.target):观察人或物,duration 10-30 秒
- interact(args.target, args.action):与物品/工具互动,duration 30-120 秒
- talk_to(args.agent_id, args.opening):主动与他人对话,duration 60-90 秒。
  ⚠ args.agent_id **必须**用 agent_xx 格式(如 agent_01、agent_06),
  不要用中文名(如"林秋""千绫")。可参考你 persona 中
  initial_relationships 里的 key 即正确的 agent_id。
"""

DAILY_PLAN_TASK = """请为今天生成一份粗粒度日程。要求:
1. 5-7 个时段,覆盖从早上起床到晚上睡觉。
2. 每个时段说清楚:开始时间(HH:MM)、结束时间、做什么、在哪个场所(用 location_id)。
3. 必须符合你的人格设定与日常作息;但不要照抄 routine,要根据当下情境(短期需求、关系状态)做合理调整。
4. 优先考虑你的中期目标与今日具体需求。

可用场所(只能用这些 id):
{location_options}

今天是游戏内第 {game_day} 天。当前时间:{game_time_str}。

只返回严格 JSON,格式如下:
{{
  "slots": [
    {{"start_time": "06:00", "end_time": "08:00", "activity": "...", "location": "lao_song_plaza", "notes": "..."}},
    ...
  ]
}}
不要任何解释、markdown 包裹或前后缀。
"""

FINE_PLAN_TASK = """根据下面的「当前时段」,展开成 5-10 个具体的小动作。

当前时段:{slot_summary}
当前位置:{current_location}
你刚才在做:{recent_actions}

可用场所(move_to 的 location 字段必须用以下 id 之一,不要用中文名):
{location_options}

{action_vocab}

要求:
1. 输出 5-10 个动作,合起来覆盖该时段(约 30-120 游戏分钟,即 1800-7200 游戏秒)。
2. 每个动作 duration_seconds 必须 > 0,单位是游戏秒。
   - 大多数动作建议 ≥ 120 秒(2 分钟),不要堆一串 10-30 秒的小动作。
   - work 类活动一般 180-600 秒;rest 类 300-900 秒;observe / interact 60-180 秒。
3. 如果 slot 的 location 与「当前位置」相同,**不要**输出 move_to 浪费时间;直接做正事。
4. 如果需要换场所,第一个动作用 move_to 过去,location 必须是上面列表中的 id。
5. **社交考量**:这是一个生活流模拟,人与人之间的对话才是世界活起来的标志。
   如果你与某个 initial_relationships 中的人有未解决的话题、需要推进的关系、
   或者只是日常关心(担心他的状态、想分享见闻),可以安排 1 个 talk_to 动作。
   尤其在以下情境:
   - 午饭时段(12:00-13:00)在酒馆 / 老松广场
   - 黄昏 / 夜晚(18:00-22:00)在酒馆
   - 早晨(06:00-08:00)在工作场所开始前的寒暄
   - 你有 known_secrets 与对方相关时(适度试探,符合人格)
   不要硬塞 — 自然的 1 次对话比 10 个 idle 动作珍贵。
6. 严格 JSON,格式:
{{
  "actions": [
    {{"action_type": "move_to", "args": {{"location": "lao_song_plaza"}}, "duration_seconds": 60}},
    {{"action_type": "work", "args": {{"task": "..."}}, "duration_seconds": 300}}
  ]
}}
不要任何解释,不要 markdown 包裹。
"""

EMERGENCY_TASK = """突发事件:{event_summary}

你必须立刻反应。当前位置:{current_location}。

{action_vocab}

输出 1-5 个紧急动作,处理这个事件。优先短动作(< 60 秒)。
严格 JSON,格式:{{"actions": [...]}}。不要解释。
"""


# JSON 抽取:取第一个 {...} 块
_JSON_OBJECT_RE = re.compile(r"\{[\s\S]*\}")
# Markdown 代码块包裹("```json ... ```")的剥离
_MD_CODE_FENCE_RE = re.compile(r"^```(?:json|JSON)?\s*\n?|\n?```\s*$", re.MULTILINE)
# 容错:JSON 内 trailing comma( `, }` 或 `, ]` )
_TRAILING_COMMA_RE = re.compile(r",(\s*[}\]])")

# Fallback 动作时长(秒)
_FALLBACK_DURATION = 5.0


def _robust_json_loads(raw_content: str) -> dict | list | None:
    """容错 JSON 解析。

    LLM 偶尔会:
    - 用 markdown 代码块 ```json ... ``` 包裹输出
    - 在末尾留 trailing comma `, }` (Python 风格)
    - 加注释 / 解释段(_JSON_OBJECT_RE 已能跳过前后文)

    依次尝试:
    1. 直接 json.loads(raw match)
    2. 剥离 markdown 后再 json.loads
    3. 修掉 trailing comma 再 json.loads

    任一成功返回结果;全部失败返回 None。
    """
    # 先剥离 markdown 包裹再找 {...}
    cleaned = _MD_CODE_FENCE_RE.sub("", raw_content.strip()).strip()
    match = _JSON_OBJECT_RE.search(cleaned)
    if match is None:
        return None
    candidate = match.group(0)

    # 尝试 1:严格 json.loads
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # 尝试 2:修掉 trailing comma
    cleaned2 = _TRAILING_COMMA_RE.sub(r"\1", candidate)
    try:
        return json.loads(cleaned2)
    except json.JSONDecodeError:
        pass

    return None


def _format_location_options(
    locations: dict[str, LocationInfo],
    typical: tuple[str, ...],
) -> str:
    """把 location 列表格式化给 LLM。常去的标 [常去]。"""
    typical_set = set(typical)
    lines = []
    for loc_id, loc in locations.items():
        marker = " [常去]" if loc_id in typical_set else ""
        lines.append(f"- {loc_id}({loc.name},{loc.type}){marker}")
    return "\n".join(lines)


# ============================================================================
#                              LLMPlanner
# ============================================================================


class LLMPlanner:
    """生成式 agent 的两层规划器。

    实现 scheduler.PlanProvider Protocol — 直接注入 ActionScheduler 即可。
    粗粒度日程按 game day 缓存,同一天复用。
    """

    def __init__(
        self,
        llm: DeepSeekClient,
        memory_store: MemoryStore | None,
        persona_loader: PersonaLoader,
        location_loader: LocationLoader,
        model_pro: str = "deepseek-v4-pro",
        model_flash: str = "deepseek-v4-flash",
        recent_memory_count: int = 8,
        seconds_per_game_day: float = 86400.0,
    ) -> None:
        self.llm = llm
        self.memory_store = memory_store
        self.persona_loader = persona_loader
        self.location_loader = location_loader
        self.model_pro = model_pro
        self.model_flash = model_flash
        self.recent_memory_count = recent_memory_count
        self.seconds_per_game_day = seconds_per_game_day
        self._daily_plans: dict[str, DailyPlan] = {}

    # ------------------------------------------------------------ public API

    async def plan_next_actions(
        self,
        agent: AgentRuntime,
        reason: ThinkingReason,
        context: dict[str, Any],
    ) -> list[QueuedAction]:
        """PlanProvider Protocol 入口。"""
        game_time = float(context.get("game_time", 0.0))
        if reason is ThinkingReason.EMERGENCY:
            event = context.get("urgent_event") or {}
            return await self._plan_emergency(agent, event, game_time)
        return await self._plan_routine(agent, game_time)

    # --------------------------------------------------------- routine path

    async def _plan_routine(
        self, agent: AgentRuntime, game_time: float
    ) -> list[QueuedAction]:
        persona = self.persona_loader.load(agent.agent_id)
        daily = await self._ensure_daily_plan(agent, persona, game_time)
        slot = self._find_current_slot(daily, game_time)
        memories = await self._fetch_recent_memories(agent.agent_id)
        return await self._plan_fine(agent, persona, slot, memories, game_time)

    async def _ensure_daily_plan(
        self,
        agent: AgentRuntime,
        persona: PersonaProfile,
        game_time: float,
    ) -> DailyPlan:
        """同一游戏日复用,新一天重新生成。"""
        game_day = self._game_day_index(game_time)
        cached = self._daily_plans.get(agent.agent_id)
        if cached is not None and cached.game_day == game_day:
            return cached
        daily = await self._plan_daily(agent, persona, game_day, game_time)
        self._daily_plans[agent.agent_id] = daily
        return daily

    async def _plan_daily(
        self,
        agent: AgentRuntime,
        persona: PersonaProfile,
        game_day: int,
        game_time: float,
    ) -> DailyPlan:
        locations = self.location_loader.all()
        location_options = _format_location_options(locations, persona.typical_locations)
        time_str = self._format_game_time(game_time)
        task = DAILY_PLAN_TASK.format(
            location_options=location_options,
            game_day=game_day + 1,
            game_time_str=time_str,
        )
        messages = self._assemble_messages(persona, agent, [], task, game_time)
        try:
            # max_tokens 必须给得够 — Pro think_high 模式的"推理 tokens"也计入 max_tokens 配额。
            # 实测于 2026-05-10:max_tokens=800 时,推理花掉绝大部分配额,
            # JSON 输出在首个 slot 的 notes 中段就被截断 → 解析失败 → fallback。
            # 3000 = ~2000 推理 + ~800 JSON 输出,留足余量。
            response = await self.llm.chat(
                messages=messages,
                model=self.model_pro,
                mode=ThinkMode.THINK_HIGH,
                temperature=0.7,
                max_tokens=3000,
            )
        except Exception as exc:  # noqa: BLE001 — LLM 是外部边界,失败兜底
            logger.warning(
                "[planner] daily LLM failed agent=%s: %s: %r",
                agent.agent_id,
                type(exc).__name__,
                exc,
            )
            return self._fallback_daily_plan(agent, persona, game_day)
        slots = self._parse_daily_slots(response.content)
        if not slots:
            logger.warning(
                "[planner] daily plan parse empty agent=%s, using fallback",
                agent.agent_id,
            )
            return self._fallback_daily_plan(agent, persona, game_day)
        return DailyPlan(agent_id=agent.agent_id, game_day=game_day, slots=slots)

    def _fallback_daily_plan(
        self,
        agent: AgentRuntime,
        persona: PersonaProfile,
        game_day: int,
    ) -> DailyPlan:
        """LLM 失败时的最简兜底:全天单 slot,使用 persona 的 short_term_needs。"""
        return DailyPlan(
            agent_id=agent.agent_id,
            game_day=game_day,
            slots=[
                DailyPlanSlot(
                    start_time="06:00",
                    end_time="22:00",
                    activity=f"按日常作息生活({persona.short_term_needs or '日常事务'})",
                    location=persona.initial_location or "",
                )
            ],
        )

    async def _plan_fine(
        self,
        agent: AgentRuntime,
        persona: PersonaProfile,
        slot: DailyPlanSlot,
        memories: list[Memory],
        game_time: float,
    ) -> list[QueuedAction]:
        slot_summary = (
            f"{slot.start_time}-{slot.end_time} 在 {slot.location or '?'}:{slot.activity}"
        )
        if slot.notes:
            slot_summary += f" ({slot.notes})"
        recent_actions = self._summarize_recent_actions(agent)
        locations = self.location_loader.all()
        location_options = _format_location_options(
            locations, persona.typical_locations
        )
        task = FINE_PLAN_TASK.format(
            slot_summary=slot_summary,
            current_location=agent.current_location or "?",
            recent_actions=recent_actions,
            location_options=location_options,
            action_vocab=_ACTION_VOCAB,
        )
        messages = self._assemble_messages(persona, agent, memories, task, game_time)
        try:
            response = await self.llm.chat(
                messages=messages,
                model=self.model_flash,
                mode=ThinkMode.NON_THINK,
                temperature=0.7,
                # 800 留余量:5-10 个 action × 平均 80 tokens/个 ≈ 600-800
                max_tokens=800,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[planner] fine LLM failed agent=%s: %s", agent.agent_id, exc
            )
            return self._fallback_fine_actions(slot)
        actions = self._parse_actions(response.content)
        if not actions:
            return self._fallback_fine_actions(slot)
        return actions

    def _fallback_fine_actions(self, slot: DailyPlanSlot) -> list[QueuedAction]:
        return [
            QueuedAction(
                action_type="idle",
                args={"reason": f"plan_fail_in_slot:{slot.activity[:40]}"},
                duration_seconds=_FALLBACK_DURATION,
                source=ActionSource.PLANNER,
            )
        ]

    # ------------------------------------------------------- emergency path

    async def _plan_emergency(
        self,
        agent: AgentRuntime,
        event: dict[str, Any],
        game_time: float,
    ) -> list[QueuedAction]:
        persona = self.persona_loader.load(agent.agent_id)
        memories = await self._fetch_recent_memories(agent.agent_id)
        task = EMERGENCY_TASK.format(
            event_summary=self._summarize_event(event),
            current_location=agent.current_location or "?",
            action_vocab=_ACTION_VOCAB,
        )
        messages = self._assemble_messages(persona, agent, memories, task, game_time)
        try:
            response = await self.llm.chat(
                messages=messages,
                model=self.model_flash,
                mode=ThinkMode.NON_THINK,
                temperature=0.5,
                max_tokens=400,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[planner] emergency LLM failed agent=%s: %s", agent.agent_id, exc
            )
            return [
                QueuedAction(
                    action_type="idle",
                    args={"reason": "emergency_plan_failed"},
                    duration_seconds=_FALLBACK_DURATION,
                    source=ActionSource.PLANNER,
                )
            ]
        actions = self._parse_actions(response.content)
        if not actions:
            return [
                QueuedAction(
                    action_type="observe",
                    args={"target": "surroundings", "reason": "emergency_unparseable"},
                    duration_seconds=_FALLBACK_DURATION,
                    source=ActionSource.PLANNER,
                )
            ]
        return actions

    # -------------------------------------------------- helpers / formatters

    def _game_day_index(self, game_time: float) -> int:
        return int(game_time // self.seconds_per_game_day)

    def _format_game_time(self, game_time: float) -> str:
        seconds_today = game_time % self.seconds_per_game_day
        hour = int(seconds_today // 3600)
        minute = int((seconds_today % 3600) // 60)
        day = int(game_time // self.seconds_per_game_day) + 1
        return f"Day {day}, {hour:02d}:{minute:02d}"

    def _find_current_slot(
        self, daily: DailyPlan, game_time: float
    ) -> DailyPlanSlot:
        """根据 game_time 找当前 slot;都不匹配则返回最接近的。"""
        if not daily.slots:
            return DailyPlanSlot(
                start_time="00:00", end_time="23:59", activity="休息", location=""
            )
        seconds_today = game_time % self.seconds_per_game_day
        hour = int(seconds_today // 3600)
        minute = int((seconds_today % 3600) // 60)
        current = f"{hour:02d}:{minute:02d}"
        for slot in daily.slots:
            if slot.start_time <= current < slot.end_time:
                return slot
        # fallback:start_time <= current 中最晚的;否则第一个
        candidates = [s for s in daily.slots if s.start_time <= current]
        return candidates[-1] if candidates else daily.slots[0]

    def _summarize_recent_actions(self, agent: AgentRuntime) -> str:
        if agent.current_action is None:
            return "(无)"
        args_str = (
            "," + ",".join(f"{k}={v}" for k, v in agent.current_action.args.items())
            if agent.current_action.args
            else ""
        )
        return f"{agent.current_action.action_type}({agent.current_action.duration_seconds:g}s{args_str})"

    def _summarize_event(self, event: dict[str, Any]) -> str:
        if not event:
            return "(未知事件)"
        if "summary" in event:
            return str(event["summary"])
        return ", ".join(f"{k}={v}" for k, v in event.items())

    async def _fetch_recent_memories(self, agent_id: str) -> list[Memory]:
        if self.memory_store is None:
            return []
        try:
            return await self.memory_store.get_recent(
                agent_id, limit=self.recent_memory_count
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[planner] memory fetch failed agent=%s: %s", agent_id, exc)
            return []

    def _format_memories(self, memories: list[Memory]) -> str:
        if not memories:
            return "  (近期无相关记忆)"
        lines = []
        for mem in memories[:8]:
            tag = mem.memory_type[0].upper()  # O / R / P
            content = mem.content.strip().replace("\n", " ")[:120]
            lines.append(f"  - [{tag} imp={mem.importance}] {content}")
        return "\n".join(lines)

    def _assemble_messages(
        self,
        persona: PersonaProfile,
        agent: AgentRuntime,
        memories: list[Memory],
        task: str,
        game_time: float,
    ) -> list[dict[str, str]]:
        """组装 4 层消息:Layer 0 (system) + Layer 1 (per-agent) → system message;
        Layer 2 (memories+state) + Layer 3 (task) → user message。

        Layer 0 + Layer 1 字节稳定 → DeepSeek 缓存命中 (Layer 0 跨 agent 共享,
        Layer 1 同 agent 跨调用稳定)。
        """
        layer_0 = PromptBuilder.LAYER_0_SYSTEM
        layer_1 = build_rich_layer_1(persona)
        memories_text = self._format_memories(memories)
        layer_2 = (
            "【当前情境】\n"
            f"游戏时间:{self._format_game_time(game_time)}\n"
            f"所在位置:{agent.current_location or '?'}\n"
            f"当前情绪:{agent.current_mood or '平静'}\n"
            "近期记忆:\n"
            f"{memories_text}\n"
        )
        return [
            {"role": "system", "content": layer_0 + "\n" + layer_1},
            {"role": "user", "content": layer_2 + "\n【当前任务】\n" + task},
        ]

    # ----------------------------------------------------- LLM output parsing

    def _parse_daily_slots(self, raw_content: str) -> list[DailyPlanSlot]:
        data = _robust_json_loads(raw_content)
        if data is None:
            logger.warning("[planner] daily JSON parse failed: %r", raw_content[:200])
            return []
        raw_slots = data.get("slots") if isinstance(data, dict) else None
        if not isinstance(raw_slots, list):
            return []
        slots: list[DailyPlanSlot] = []
        for raw in raw_slots:
            if not isinstance(raw, dict):
                continue
            start = str(raw.get("start_time", "")).strip()
            end = str(raw.get("end_time", "")).strip()
            activity = str(raw.get("activity", "")).strip()
            if not (start and end and activity):
                continue
            slots.append(
                DailyPlanSlot(
                    start_time=start,
                    end_time=end,
                    activity=activity,
                    location=str(raw.get("location", "")).strip(),
                    notes=str(raw.get("notes", "")).strip(),
                )
            )
        return slots

    def _parse_actions(self, raw_content: str) -> list[QueuedAction]:
        data = _robust_json_loads(raw_content)
        if data is None:
            logger.warning("[planner] action JSON parse failed: %r", raw_content[:200])
            return []
        raw_actions = data.get("actions") if isinstance(data, dict) else None
        if not isinstance(raw_actions, list):
            return []
        actions: list[QueuedAction] = []
        for raw in raw_actions:
            if not isinstance(raw, dict):
                continue
            action_type = str(raw.get("action_type", "")).strip()
            if not action_type:
                continue
            args_raw = raw.get("args")
            args = dict(args_raw) if isinstance(args_raw, dict) else {}
            try:
                duration = float(raw.get("duration_seconds", 1.0))
            except (TypeError, ValueError):
                duration = 1.0
            if duration <= 0:
                duration = 1.0
            try:
                actions.append(
                    QueuedAction(
                        action_type=action_type,
                        args=args,
                        duration_seconds=duration,
                        source=ActionSource.PLANNER,
                    )
                )
            except ValueError as exc:
                logger.warning("[planner] action validation failed: %s", exc)
                continue
        return actions


# ============================================================================
#                  Module-level legacy wrappers (Block A 占位接口)
# ============================================================================


async def plan_daily(agent_id: str, day_index: int) -> dict[str, Any]:
    """Block A 留下的占位签名。Block E 改用 LLMPlanner._plan_daily。"""
    raise NotImplementedError(
        "Block E 后:请构造 LLMPlanner 并调用 _plan_daily(agent, persona, game_day, game_time)"
    )


async def plan_fine(agent_id: str, daily_slot: dict[str, Any]) -> list[dict[str, Any]]:
    """Block A 留下的占位签名。Block E 改用 LLMPlanner._plan_fine。"""
    raise NotImplementedError(
        "Block E 后:请构造 LLMPlanner 并调用 _plan_fine(agent, persona, slot, memories, game_time)"
    )
