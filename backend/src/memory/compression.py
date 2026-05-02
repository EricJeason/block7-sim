"""Memory 压缩:把游戏内 N 天前的 memory 压缩为一条 reflection。

参见设计文档 v0.2 §2.6 / §4。Block C 仅搭骨架,真实压缩逻辑在 Block E 实现。
"""
from __future__ import annotations

from .store import MemoryStore


class MemoryCompressor:
    """将旧 memory 压缩为单条 reflection。Block E 填充实现。"""

    DAYS_THRESHOLD: int = 7  # 游戏内 7 天前的 memory 进入压缩候选

    def __init__(self, store: MemoryStore, llm_client, model: str) -> None:
        self.store = store
        self.llm = llm_client
        self.model = model

    async def compress_old_memories(
        self, agent_id: str, current_game_time: float
    ) -> int:
        """触发一次压缩,返回被压缩的 memory 数量。

        Block C:返回 0(不实际压缩)。
        TODO(Block E): 拉出 game_time < current - DAYS_THRESHOLD * 86400 的 memory,
        让 LLM (Pro / think_high) 总结成一条 reflection,写回后调用
        store.mark_compressed(...) 把原始条目标记。
        """
        return 0
