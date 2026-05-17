"""Block G.2:Memory 压缩。

按 v0.2 §3.4 规则,在每个游戏日末尾(跨日触发,SimEngine 调度):
- 24 游戏小时内:全保留(不动)
- 1-7 天前:importance < 5 用 LLM Flash 合并为一条"日常摘要" reflection,
  原 memory 标记 compressed(后续检索默认排除)
- 7 天以前:仅保留 reflection + importance ≥ 7,其余直接标记 compressed(不合并)

合并产生的"日常摘要"以 memory_type='reflection' 入库,importance 固定 4
(低于真正反思,高于日常事件)。
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass

from src.llm.deepseek import ThinkMode
from src.memory.store import Memory, MemoryStore

logger = logging.getLogger(__name__)

# 时间窗口(游戏秒)
SECONDS_PER_GAME_DAY = 86400.0
DAYS_KEEP_RAW = 1.0     # 1 天内不压缩
DAYS_MERGE_LOW = 7.0    # 1-7 天前的低 importance 合并
# 1-7 天的"低重要性"阈值
LOW_IMPORTANCE_MAX = 4   # importance ≤ 4 视为低
# 7 天前的"保留下限"
DEEP_KEEP_MIN_IMPORTANCE = 7

# 合并后日常摘要的固定 importance
SUMMARY_IMPORTANCE = 4

SUMMARY_PROMPT = """以下是 {agent_name} 在最近一段时间(游戏内第 {day_start}-{day_end} 天)
经历的若干琐碎事件(每条都不算重要):

{events}

请用第一人称、{agent_name} 的语气,把这些事件**摘要成一段 80 字以内的话**,
保留还算有意义的细节,丢掉重复或纯粹日常的部分。不要分点,只输出一段连贯的文字。
不要解释,不要前后缀。"""


@dataclass
class CompressionResult:
    agent_id: str
    merged_count: int       # 被合并到 summary 的 memory 数
    archived_count: int     # 直接标记 compressed 的 memory 数(7 天前低 importance)
    summary_inserted: bool
    cost_yuan: float


class MemoryCompressor:
    """旧 memory 压缩器。跨日触发,与 ReflectionRunner 配合 SimEngine。"""

    def __init__(
        self,
        store: MemoryStore,
        llm,
        model: str = "deepseek-v4-flash",
        persona_loader=None,
        seconds_per_game_day: float = SECONDS_PER_GAME_DAY,
    ) -> None:
        self.store = store
        self.llm = llm
        self.model = model
        self.persona_loader = persona_loader
        self.seconds_per_game_day = seconds_per_game_day

    async def compress_old_memories(
        self,
        agent_id: str,
        current_game_time: float,
    ) -> CompressionResult:
        """按规则压缩该 agent 的旧 memory。

        返回 merged_count + archived_count + summary_inserted。
        """
        cutoff_1d = current_game_time - DAYS_KEEP_RAW * self.seconds_per_game_day
        cutoff_7d = current_game_time - DAYS_MERGE_LOW * self.seconds_per_game_day

        # 1. 1-7 天前的 importance ≤ 4 → 合并为日常摘要
        mid_zone = await self._fetch_merge_candidates(agent_id, cutoff_1d, cutoff_7d)
        merged_count = 0
        summary_inserted = False
        cost = 0.0
        if mid_zone:
            inserted, cost = await self._merge_to_summary(
                agent_id, mid_zone, current_game_time, cutoff_1d, cutoff_7d
            )
            if inserted:
                summary_inserted = True
                await self.store.mark_compressed([m.memory_id for m in mid_zone if m.memory_id])
                merged_count = len(mid_zone)

        # 2. 7 天以前的非 reflection 且 importance < 7 → 直接 mark_compressed
        deep_zone = await self._fetch_deep_archive(agent_id, cutoff_7d)
        archived_count = 0
        if deep_zone:
            ids = [m.memory_id for m in deep_zone if m.memory_id]
            if ids:
                await self.store.mark_compressed(ids)
                archived_count = len(ids)

        if merged_count or archived_count:
            logger.info(
                "[compress] agent=%s: merged %d (summary=%s) + archived %d, cost=%.4f元",
                agent_id, merged_count, summary_inserted, archived_count, cost,
            )
        return CompressionResult(
            agent_id=agent_id,
            merged_count=merged_count,
            archived_count=archived_count,
            summary_inserted=summary_inserted,
            cost_yuan=cost,
        )

    # ------------------------------------------------------------ fetch

    async def _fetch_merge_candidates(
        self,
        agent_id: str,
        cutoff_1d: float,
        cutoff_7d: float,
    ) -> list[Memory]:
        """1-7 天前 importance ≤ LOW_IMPORTANCE_MAX 的 memory。"""
        try:
            # 用 [cutoff_7d, cutoff_1d) 区间
            mems = await self.store.get_in_time_range(
                agent_id=agent_id,
                game_time_min=cutoff_7d,
                game_time_max=cutoff_1d,
                min_importance=0,  # 不限制下限
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[compress] fetch mid_zone failed agent=%s: %s", agent_id, exc)
            return []
        # 过滤 importance ≤ 4 且非 reflection
        return [
            m
            for m in mems
            if m.importance <= LOW_IMPORTANCE_MAX and m.memory_type != "reflection"
        ]

    async def _fetch_deep_archive(
        self,
        agent_id: str,
        cutoff_7d: float,
    ) -> list[Memory]:
        """7 天以前的非 reflection 且 importance < DEEP_KEEP_MIN_IMPORTANCE。"""
        try:
            mems = await self.store.get_older_than(
                agent_id=agent_id,
                game_time_max=cutoff_7d,
                max_importance=DEEP_KEEP_MIN_IMPORTANCE - 1,
                exclude_types=["reflection"],
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[compress] fetch deep_zone failed agent=%s: %s", agent_id, exc)
            return []
        return mems

    # ------------------------------------------------------------ merge

    async def _merge_to_summary(
        self,
        agent_id: str,
        memories: list[Memory],
        current_game_time: float,
        cutoff_1d: float,
        cutoff_7d: float,
    ) -> tuple[bool, float]:
        """把 memories 合并成一条 reflection memory。返回 (inserted, cost)。"""
        agent_name = self._agent_display_name(agent_id)
        day_start = int(cutoff_7d // self.seconds_per_game_day) + 1
        day_end = int(cutoff_1d // self.seconds_per_game_day) + 1
        events_text = "\n".join(
            f"  - {m.content.strip()}" for m in memories[:50]  # 上限 50 条防 token 爆
        )
        prompt = SUMMARY_PROMPT.format(
            agent_name=agent_name,
            day_start=day_start,
            day_end=day_end,
            events=events_text,
        )
        try:
            response = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                mode=ThinkMode.NON_THINK,
                temperature=0.5,
                max_tokens=200,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[compress] merge LLM failed agent=%s: %s", agent_id, exc)
            return False, 0.0
        summary_text = response.content.strip()
        if not summary_text:
            return False, response.usage.cost_yuan

        mem = Memory(
            memory_id=None,
            agent_id=agent_id,
            memory_type="reflection",
            content=f"(日常摘要){summary_text}",
            importance=SUMMARY_IMPORTANCE,
            game_time=current_game_time,
            real_time=time.time(),
            location=None,
            related_agents=[],
            keywords=["日常摘要", f"day{day_start}-{day_end}"],
        )
        try:
            await self.store.insert(mem)
            return True, response.usage.cost_yuan
        except Exception as exc:  # noqa: BLE001
            logger.warning("[compress] summary insert failed: %s", exc)
            return False, response.usage.cost_yuan

    def _agent_display_name(self, agent_id: str) -> str:
        if self.persona_loader is None:
            return agent_id
        try:
            return self.persona_loader.load(agent_id).display_name
        except Exception:  # noqa: BLE001
            return agent_id
