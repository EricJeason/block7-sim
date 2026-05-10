"""AgentRuntime 与 Action Queue 的运行时数据结构。"""
from __future__ import annotations

import asyncio
import copy
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Deque
from uuid import uuid4


class ThinkingReason(str, Enum):
    LOW_WATERMARK = "low_watermark"
    EMPTY_QUEUE = "empty_queue"
    EMERGENCY = "emergency"
    MANUAL = "manual"


class ActionSource(str, Enum):
    PLANNER = "planner"
    FALLBACK = "fallback"
    MANUAL = "manual"
    EMERGENCY = "emergency"


@dataclass
class QueuedAction:
    action_type: str
    args: dict[str, Any] = field(default_factory=dict)
    duration_seconds: float = 1.0
    action_id: str = field(default_factory=lambda: uuid4().hex)
    started_at: float | None = None
    elapsed_seconds: float = 0.0
    interruptible: bool = True
    source: ActionSource = ActionSource.PLANNER

    def __post_init__(self) -> None:
        if not self.action_type or not self.action_type.strip():
            raise ValueError("action_type must be non-empty")
        if not isinstance(self.args, dict):
            raise ValueError("args must be a dict")
        if self.duration_seconds <= 0:
            raise ValueError("duration_seconds must be > 0")
        if self.elapsed_seconds < 0:
            raise ValueError("elapsed_seconds must be >= 0")
        if self.elapsed_seconds - self.duration_seconds > 1e-6:
            raise ValueError("elapsed_seconds cannot exceed duration_seconds")
        if self.elapsed_seconds > self.duration_seconds:
            self.elapsed_seconds = self.duration_seconds
        self.source = ActionSource(self.source)

    @property
    def remaining_seconds(self) -> float:
        return max(0.0, self.duration_seconds - self.elapsed_seconds)

    @property
    def is_complete(self) -> bool:
        return self.elapsed_seconds >= self.duration_seconds

    def start(self, game_time: float) -> None:
        self.started_at = game_time

    def advance(self, dt: float) -> None:
        if dt < 0:
            raise ValueError("dt must be >= 0")
        self.elapsed_seconds = min(self.duration_seconds, self.elapsed_seconds + dt)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "args": copy.deepcopy(self.args),
            "duration_seconds": self.duration_seconds,
            "started_at": self.started_at,
            "elapsed_seconds": self.elapsed_seconds,
            "remaining_seconds": self.remaining_seconds,
            "is_complete": self.is_complete,
            "interruptible": self.interruptible,
            "source": self.source.value,
        }


@dataclass
class AgentRuntime:
    """单个 agent 的 Action Queue 运行时状态。"""

    agent_id: str
    persona_name: str = ""
    current_location: str = ""
    current_mood: str = "neutral"

    action_queue: Deque[QueuedAction] = field(default_factory=deque)
    current_action: QueuedAction | None = None

    pending_thinking: asyncio.Task[list[QueuedAction]] | None = None
    pending_reason: ThinkingReason | None = None
    last_thinking_started_at: float = 0.0
    consecutive_planning_failures: int = 0

    state: dict[str, Any] = field(default_factory=dict)
    plan: dict[str, Any] = field(default_factory=dict)

    def queued_remaining_seconds(self) -> float:
        return sum(action.remaining_seconds for action in self.action_queue)

    def total_remaining_seconds(self) -> float:
        current_remaining = (
            self.current_action.remaining_seconds if self.current_action is not None else 0.0
        )
        return current_remaining + self.queued_remaining_seconds()

    def has_pending_thinking(self) -> bool:
        return self.pending_thinking is not None and not self.pending_thinking.done()

    def snapshot(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "persona_name": self.persona_name,
            "current_location": self.current_location,
            "current_mood": self.current_mood,
            "current_action": (
                self.current_action.to_dict() if self.current_action is not None else None
            ),
            "queue": [action.to_dict() for action in self.action_queue],
            "pending_reason": (
                self.pending_reason.value if self.pending_reason is not None else None
            ),
            "total_remaining_seconds": self.total_remaining_seconds(),
            "consecutive_planning_failures": self.consecutive_planning_failures,
            "state": copy.deepcopy(self.state),
            "plan": copy.deepcopy(self.plan),
        }


def load_runtime(agent_id: str) -> AgentRuntime:
    """从持久化数据恢复 AgentRuntime。

    Block D 暂不扩大 scope 到 persona YAML / SQLite agents 表恢复。
    """
    raise NotImplementedError("Block D 实现")
