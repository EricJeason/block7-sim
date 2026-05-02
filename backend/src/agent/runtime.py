"""AgentRuntime — 单个 agent 的运行时数据载体(身份、状态、当前位置等)。"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AgentRuntime:
    """单个 agent 的运行时状态快照。

    Block A: 只放数据类骨架,真实字段在 Block D/E 由调度器与感知系统填充。
    """

    agent_id: str
    persona_name: str = ""
    current_location: str = ""
    current_action: str = ""
    # 短期状态(Block D 实现)
    state: dict[str, object] = field(default_factory=dict)
    # 当前 plan(Block E 实现):粗粒度日程 + 细粒度任务栈
    plan: dict[str, object] = field(default_factory=dict)


def load_runtime(agent_id: str) -> AgentRuntime:
    """从 persona YAML 与 SQLite memory 中恢复 AgentRuntime。

    Block D 实现。
    """
    raise NotImplementedError("Block D 实现")
