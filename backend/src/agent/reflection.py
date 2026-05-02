"""每日反思 — 在每个 sim 日结束时把当日记忆压缩为高层观察。

参见设计文档 §2.5:反思产出的 high-level memory 写回 SQLite,作为下一日规划的输入。
"""
from __future__ import annotations

from typing import Any


async def reflect_daily(agent_id: str, day_index: int) -> list[dict[str, Any]]:
    """读取当日 memory,产出若干高层反思条目。

    Block G 实现。
    """
    raise NotImplementedError("Block G 实现")
