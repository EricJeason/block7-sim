"""Action Queue 调度器 — 永不阻塞游戏循环的异步任务编排。

参见设计文档 §3.x:Action Queue 的关键约束是任何 LLM 调用都不能阻塞 Godot 端的 60Hz tick。
"""
from __future__ import annotations

from typing import Any


async def enqueue(agent_id: str, action: dict[str, Any]) -> None:
    """把 agent 的下一个待执行 action 放进队列。

    Block D 实现。
    """
    raise NotImplementedError("Block D 实现")


async def tick() -> None:
    """每个 sim tick 拉取一批 ready 状态的 action,触发对应 LLM 调用或本地动作。

    Block D 实现。
    """
    raise NotImplementedError("Block D 实现")
