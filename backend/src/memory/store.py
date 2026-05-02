"""Memory CRUD + 关键词查询。

参见设计文档第 0 节变更项 #1:**严禁使用 embedding / 向量检索**。
所有 memory 召回走关键词倒排 + 时间衰减打分。
"""
from __future__ import annotations

from typing import Any


async def insert_observation(agent_id: str, content: str, location: str, ts: float) -> int:
    """写入一条原始观察记录,返回新 row id。

    Block C 实现。
    """
    raise NotImplementedError("Block C 实现")


async def query_by_keywords(
    agent_id: str,
    keywords: list[str],
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """按关键词召回 agent 相关记忆,按时间衰减 + 重要性打分。

    Block C 实现。严禁引入向量库。
    """
    raise NotImplementedError("Block C 实现")
