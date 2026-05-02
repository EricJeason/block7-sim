"""粗粒度(每日大日程)与细粒度(分钟级动作)规划。

参见设计文档 §2.3:粗粒度规划用 Pro 模型每日 1 次,细粒度用 Flash 模型按需触发。
"""
from __future__ import annotations

from typing import Any


async def plan_daily(agent_id: str, day_index: int) -> dict[str, Any]:
    """生成 agent 当日粗粒度日程(几个时间段、每段做什么)。

    Block E 实现(依赖 Block B 的 DeepSeek 客户端 + Block C 的 memory store)。
    """
    raise NotImplementedError("Block E 实现")


async def plan_fine(agent_id: str, daily_slot: dict[str, Any]) -> list[dict[str, Any]]:
    """把粗粒度时段拆成具体的分钟级 action 列表。

    Block E 实现。
    """
    raise NotImplementedError("Block E 实现")
