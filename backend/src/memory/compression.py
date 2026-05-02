"""Memory 压缩策略 — 控制单 agent 长期记忆体量。

参见设计文档 §2.6:阈值触发后把旧观察合并为反思,原始条目转入冷存储。
"""
from __future__ import annotations


async def compress_old_observations(agent_id: str, before_ts: float) -> int:
    """把 before_ts 之前的原始观察合并为反思,返回压缩条目数。

    Block G 实现。
    """
    raise NotImplementedError("Block G 实现")
