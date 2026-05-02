"""同场所事件传播 — 当一个 agent 触发可观测事件时,通知同一 location 的其他 agent。

参见设计文档 §2.4:不使用全局广播,只对共享同一 location 的 agent 推送事件,降低 prompt 体积。
"""
from __future__ import annotations

from typing import Any


async def broadcast_event(location: str, event: dict[str, Any]) -> None:
    """把事件写入所有同场所 agent 的短期感知缓冲。

    Block F 实现。
    """
    raise NotImplementedError("Block F 实现")


async def collect_observations(agent_id: str) -> list[dict[str, Any]]:
    """读取 agent 当前感知缓冲,合并为给规划/反思使用的上下文。

    Block F 实现。
    """
    raise NotImplementedError("Block F 实现")
