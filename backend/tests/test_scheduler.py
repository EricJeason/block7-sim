from __future__ import annotations

import asyncio
import time

import pytest

from src.agent.runtime import ActionSource, AgentRuntime, QueuedAction, ThinkingReason
from src.agent.scheduler import ActionScheduler, SchedulerConfig
from src.memory.schema import init_db
from src.memory.store import MemoryStore


class InstantPlanner:
    def __init__(self, action_type: str = "idle") -> None:
        self.action_type = action_type
        self.calls = 0
        self.reasons: list[ThinkingReason] = []

    async def plan_next_actions(
        self,
        agent: AgentRuntime,
        reason: ThinkingReason,
        context: dict[str, object],
    ) -> list[QueuedAction]:
        self.calls += 1
        self.reasons.append(reason)
        return [
            QueuedAction(
                action_type=self.action_type,
                args={"location": "x"} if self.action_type == "move_to" else {},
                duration_seconds=5.0,
            )
        ]


class BulkPlanner:
    def __init__(self, count: int) -> None:
        self.count = count

    async def plan_next_actions(
        self,
        agent: AgentRuntime,
        reason: ThinkingReason,
        context: dict[str, object],
    ) -> list[QueuedAction]:
        return [
            QueuedAction(action_type=f"planned_{index}", duration_seconds=1.0)
            for index in range(self.count)
        ]


class ReasonPlanner:
    async def plan_next_actions(
        self,
        agent: AgentRuntime,
        reason: ThinkingReason,
        context: dict[str, object],
    ) -> list[QueuedAction]:
        return [QueuedAction(action_type=reason.value, duration_seconds=1.0)]


class SlowPlanner:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.calls = 0
        self.reasons: list[ThinkingReason] = []

    async def plan_next_actions(
        self,
        agent: AgentRuntime,
        reason: ThinkingReason,
        context: dict[str, object],
    ) -> list[QueuedAction]:
        self.calls += 1
        self.reasons.append(reason)
        self.started.set()
        await self.release.wait()
        return [
            QueuedAction(
                action_type="move_to",
                args={"location": "x"},
                duration_seconds=5.0,
            )
        ]


class ErrorPlanner:
    async def plan_next_actions(
        self,
        agent: AgentRuntime,
        reason: ThinkingReason,
        context: dict[str, object],
    ) -> list[QueuedAction]:
        raise RuntimeError("planner failed")


class SlowMemoryStore:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.calls = 0

    async def insert(self, memory: object) -> int:
        self.calls += 1
        self.started.set()
        await self.release.wait()
        return 1


def test_queued_action_validation() -> None:
    with pytest.raises(ValueError):
        QueuedAction(action_type="")
    with pytest.raises(ValueError):
        QueuedAction(action_type="idle", duration_seconds=0)
    with pytest.raises(ValueError):
        QueuedAction(action_type="idle", elapsed_seconds=-1)


def test_action_progress_and_completion() -> None:
    action = QueuedAction(action_type="work", duration_seconds=10.0)
    action.advance(4.0)
    assert not action.is_complete
    assert action.remaining_seconds == 6.0

    action.advance(6.0)
    assert action.is_complete
    assert action.remaining_seconds == 0.0

    action.advance(100.0)
    assert action.elapsed_seconds == 10.0
    assert action.remaining_seconds == 0.0


def test_snapshot_does_not_expose_mutable_runtime_state() -> None:
    action = QueuedAction(
        action_type="work",
        args={"nested": {"value": 1}},
        duration_seconds=3.0,
    )
    agent = AgentRuntime(
        agent_id="a1",
        state={"needs": {"food": 3}},
        plan={"steps": ["start"]},
    )
    agent.action_queue.append(action)

    snapshot = agent.snapshot()
    snapshot["queue"][0]["args"]["nested"]["value"] = 99
    snapshot["state"]["needs"]["food"] = 0
    snapshot["plan"]["steps"].append("mutated")

    assert action.args["nested"]["value"] == 1
    assert agent.state["needs"]["food"] == 3
    assert agent.plan["steps"] == ["start"]


async def test_scheduler_starts_next_action() -> None:
    scheduler = ActionScheduler(config=SchedulerConfig(thinking_trigger_threshold=0.0))
    agent = AgentRuntime(agent_id="a1")
    action = QueuedAction(action_type="move_to", duration_seconds=3.0)
    agent.action_queue.append(action)
    scheduler.register_agent(agent)

    result = await scheduler.tick_agent("a1", game_time=42.0, dt=0.0)

    assert result.started_action is action
    assert agent.current_action is action
    assert action.started_at == 42.0


async def test_scheduler_completes_current_action() -> None:
    scheduler = ActionScheduler(config=SchedulerConfig(thinking_trigger_threshold=0.0))
    action = QueuedAction(action_type="work", duration_seconds=2.0)
    action.start(1.0)
    agent = AgentRuntime(agent_id="a1", current_action=action)
    scheduler.register_agent(agent)

    result = await scheduler.tick_agent("a1", game_time=3.0, dt=2.0)

    assert result.completed_action is action
    assert agent.current_action is None


async def test_tick_all_ticks_multiple_agents() -> None:
    scheduler = ActionScheduler(config=SchedulerConfig(thinking_trigger_threshold=0.0))
    first = AgentRuntime(agent_id="a1")
    second = AgentRuntime(agent_id="a2")
    first.action_queue.append(QueuedAction(action_type="idle", duration_seconds=1.0))
    second.action_queue.append(QueuedAction(action_type="work", duration_seconds=1.0))
    scheduler.register_agent(first)
    scheduler.register_agent(second)

    results = await scheduler.tick_all(game_time=10.0, dt=0.0)

    assert {result.agent_id for result in results} == {"a1", "a2"}
    assert first.current_action is not None
    assert second.current_action is not None


async def test_tick_all_isolates_single_agent_failure(monkeypatch) -> None:
    scheduler = ActionScheduler(config=SchedulerConfig(thinking_trigger_threshold=0.0))
    bad = AgentRuntime(agent_id="bad")
    good = AgentRuntime(agent_id="good")
    good.action_queue.append(QueuedAction(action_type="work", duration_seconds=1.0))
    scheduler.register_agent(bad)
    scheduler.register_agent(good)
    original_tick_agent = scheduler.tick_agent

    async def flaky_tick_agent(
        agent_id: str,
        *,
        game_time: float,
        dt: float,
        context: dict[str, object] | None = None,
    ):
        if agent_id == "bad":
            raise RuntimeError("bad agent")
        return await original_tick_agent(agent_id, game_time=game_time, dt=dt, context=context)

    monkeypatch.setattr(scheduler, "tick_agent", flaky_tick_agent)

    results = await scheduler.tick_all(game_time=10.0, dt=0.0)
    by_agent = {result.agent_id: result for result in results}

    assert by_agent["bad"].error == "RuntimeError: bad agent"
    assert by_agent["good"].error is None
    assert by_agent["good"].started_action is good.current_action


async def test_low_watermark_starts_single_thinking_task() -> None:
    planner = SlowPlanner()
    scheduler = ActionScheduler(planner=planner)
    agent = AgentRuntime(agent_id="a1")
    agent.action_queue.append(QueuedAction(action_type="idle", duration_seconds=5.0))
    scheduler.register_agent(agent)

    first = await scheduler.tick_agent("a1", game_time=1.0, dt=0.0)
    await asyncio.sleep(0)
    old_task = agent.pending_thinking
    second = await scheduler.tick_agent("a1", game_time=1.1, dt=0.0)

    assert first.thinking_started
    assert not second.thinking_started
    assert planner.calls == 1
    assert agent.pending_thinking is old_task
    await scheduler.shutdown()


async def test_fallback_repeats_without_duplicate_pending_task() -> None:
    planner = SlowPlanner()
    scheduler = ActionScheduler(
        planner=planner,
        config=SchedulerConfig(fallback_idle_seconds=1.0),
    )
    agent = AgentRuntime(agent_id="a1")
    scheduler.register_agent(agent)

    first = await scheduler.tick_agent("a1", game_time=1.0, dt=0.0)
    await asyncio.sleep(0)
    first_task = agent.pending_thinking
    second = await scheduler.tick_agent("a1", game_time=2.0, dt=1.0)

    assert first.fallback_action is not None
    assert second.completed_action is first.fallback_action
    assert second.fallback_action is not None
    assert planner.calls == 1
    assert agent.pending_thinking is first_task
    await scheduler.shutdown()


async def test_tick_does_not_block_slow_planner() -> None:
    planner = SlowPlanner()
    scheduler = ActionScheduler(planner=planner)
    agent = AgentRuntime(agent_id="a1")
    scheduler.register_agent(agent)

    started_at = time.monotonic()
    result = await scheduler.tick_agent("a1", game_time=1.0, dt=0.0)
    elapsed = time.monotonic() - started_at
    await asyncio.sleep(0)

    assert result.thinking_started
    assert result.fallback_action is not None
    assert planner.started.is_set()
    assert elapsed < 0.05
    await scheduler.shutdown()


async def test_pending_thinking_appends_actions_when_done() -> None:
    planner = SlowPlanner()
    scheduler = ActionScheduler(
        planner=planner,
        config=SchedulerConfig(thinking_trigger_threshold=0.1),
    )
    agent = AgentRuntime(agent_id="a1")
    scheduler.register_agent(agent)

    await scheduler.tick_agent("a1", game_time=1.0, dt=0.0)
    await asyncio.sleep(0)
    planner.release.set()
    await asyncio.sleep(0)
    result = await scheduler.tick_agent("a1", game_time=2.0, dt=0.0)

    assert result.thinking_completed
    assert len(result.appended_actions) == 1
    assert agent.pending_thinking is None
    assert list(agent.action_queue) == result.appended_actions


async def test_planner_result_truncated_to_max_actions() -> None:
    scheduler = ActionScheduler(
        planner=BulkPlanner(count=5),
        config=SchedulerConfig(thinking_trigger_threshold=0.1, max_planner_actions=2),
    )
    agent = AgentRuntime(agent_id="a1")
    scheduler.register_agent(agent)

    await scheduler.tick_agent("a1", game_time=1.0, dt=0.0)
    await asyncio.sleep(0)
    result = await scheduler.tick_agent("a1", game_time=2.0, dt=0.0)

    assert result.thinking_completed
    assert [action.action_type for action in result.appended_actions] == [
        "planned_0",
        "planned_1",
    ]


async def test_empty_queue_while_thinking_uses_idle_fallback() -> None:
    planner = SlowPlanner()
    scheduler = ActionScheduler(planner=planner)
    agent = AgentRuntime(agent_id="a1")
    scheduler.register_agent(agent)

    result = await scheduler.tick_agent("a1", game_time=1.0, dt=0.0)
    await asyncio.sleep(0)

    assert result.fallback_action is not None
    assert agent.current_action is result.fallback_action
    assert agent.current_action.action_type == "idle"
    assert agent.current_action.source is ActionSource.FALLBACK
    await scheduler.shutdown()


async def test_emergency_replan_keeps_current_action_and_clears_future_queue() -> None:
    planner = SlowPlanner()
    scheduler = ActionScheduler(
        planner=planner,
        config=SchedulerConfig(thinking_trigger_threshold=0.1),
    )
    current = QueuedAction(action_type="cook", duration_seconds=10.0)
    current.start(1.0)
    agent = AgentRuntime(agent_id="a1", current_action=current)
    agent.action_queue.append(QueuedAction(action_type="eat", duration_seconds=5.0))
    scheduler.register_agent(agent)
    old_task = asyncio.create_task(
        planner.plan_next_actions(agent, ThinkingReason.LOW_WATERMARK, {})
    )
    agent.pending_thinking = old_task
    agent.pending_reason = ThinkingReason.LOW_WATERMARK
    await asyncio.sleep(0)

    await scheduler.trigger_emergency_replan(
        "a1",
        {"importance": 9, "description": "urgent"},
        game_time=2.0,
    )

    assert agent.current_action is current
    assert not agent.action_queue
    assert old_task.cancelled()
    assert agent.pending_thinking is not old_task
    assert agent.pending_reason is ThinkingReason.EMERGENCY

    planner.release.set()
    await asyncio.sleep(0)
    result = await scheduler.tick_agent("a1", game_time=3.0, dt=0.0)

    assert result.thinking_completed
    assert result.appended_actions[0].action_type == "move_to"


async def test_emergency_discards_done_regular_pending_result() -> None:
    planner = ReasonPlanner()
    scheduler = ActionScheduler(
        planner=planner,
        config=SchedulerConfig(thinking_trigger_threshold=0.1),
    )
    agent = AgentRuntime(agent_id="a1")
    scheduler.register_agent(agent)
    old_task = asyncio.create_task(
        planner.plan_next_actions(agent, ThinkingReason.LOW_WATERMARK, {})
    )
    await asyncio.sleep(0)
    assert old_task.done()
    agent.pending_thinking = old_task
    agent.pending_reason = ThinkingReason.LOW_WATERMARK

    await scheduler.trigger_emergency_replan("a1", {"description": "urgent"}, game_time=2.0)
    await asyncio.sleep(0)
    result = await scheduler.tick_agent("a1", game_time=3.0, dt=0.0)

    assert [action.action_type for action in result.appended_actions] == ["emergency"]
    assert agent.current_action is result.appended_actions[0]


async def test_second_emergency_replaces_first_emergency_pending() -> None:
    planner = SlowPlanner()
    scheduler = ActionScheduler(
        planner=planner,
        config=SchedulerConfig(thinking_trigger_threshold=0.1),
    )
    agent = AgentRuntime(agent_id="a1")
    scheduler.register_agent(agent)

    await scheduler.trigger_emergency_replan("a1", {"description": "first"}, game_time=1.0)
    await asyncio.sleep(0)
    first_task = agent.pending_thinking
    await scheduler.trigger_emergency_replan("a1", {"description": "second"}, game_time=2.0)
    await asyncio.sleep(0)

    assert first_task is not None
    assert first_task.cancelled()
    assert agent.pending_thinking is not first_task
    assert agent.pending_reason is ThinkingReason.EMERGENCY
    assert planner.calls == 2

    planner.release.set()
    await asyncio.sleep(0)
    result = await scheduler.tick_agent("a1", game_time=3.0, dt=0.0)

    assert result.thinking_completed
    assert result.appended_actions[0].action_type == "move_to"


async def test_planner_exception_does_not_crash_tick() -> None:
    scheduler = ActionScheduler(
        planner=ErrorPlanner(),
        config=SchedulerConfig(thinking_trigger_threshold=0.1),
    )
    agent = AgentRuntime(agent_id="a1")
    scheduler.register_agent(agent)

    await scheduler.tick_agent("a1", game_time=1.0, dt=0.0)
    await asyncio.sleep(0)
    result = await scheduler.tick_agent("a1", game_time=2.0, dt=0.0)

    assert result.thinking_failed
    assert agent.consecutive_planning_failures == 1
    assert agent.current_action is not None
    assert agent.current_action.source is ActionSource.FALLBACK


async def test_plan_memory_written_when_store_present(tmp_path) -> None:
    db_path = str(tmp_path / "memory.db")
    await init_db(db_path)
    store = MemoryStore(db_path)
    scheduler = ActionScheduler(
        planner=InstantPlanner("move_to"),
        memory_store=store,
        config=SchedulerConfig(thinking_trigger_threshold=0.1),
    )
    agent = AgentRuntime(agent_id="a1", current_location="home")
    scheduler.register_agent(agent)

    await scheduler.tick_agent("a1", game_time=1.0, dt=0.0)
    await asyncio.sleep(0)
    result = await scheduler.tick_agent("a1", game_time=2.0, dt=0.0)
    await scheduler.shutdown()
    memories = await store.get_recent("a1", memory_types=["plan"])

    assert result.thinking_completed
    assert len(memories) == 1
    assert memories[0].memory_type == "plan"
    assert "move_to" in memories[0].content
    assert "plan" in memories[0].keywords


async def test_plan_memory_write_does_not_block_tick() -> None:
    store = SlowMemoryStore()
    scheduler = ActionScheduler(
        planner=InstantPlanner("move_to"),
        memory_store=store,
        config=SchedulerConfig(thinking_trigger_threshold=0.1),
    )
    agent = AgentRuntime(agent_id="a1", current_location="home")
    scheduler.register_agent(agent)

    await scheduler.tick_agent("a1", game_time=1.0, dt=0.0)
    await asyncio.sleep(0)
    started_at = time.monotonic()
    result = await scheduler.tick_agent("a1", game_time=2.0, dt=0.0)
    elapsed = time.monotonic() - started_at
    await asyncio.sleep(0)

    assert result.thinking_completed
    assert elapsed < 0.05
    assert store.started.is_set()
    assert store.calls == 1
    store.release.set()
    await scheduler.shutdown()


async def test_shutdown_cancels_pending_tasks() -> None:
    planner = SlowPlanner()
    scheduler = ActionScheduler(planner=planner)
    agent = AgentRuntime(agent_id="a1")
    scheduler.register_agent(agent)

    await scheduler.tick_agent("a1", game_time=1.0, dt=0.0)
    await asyncio.sleep(0)
    old_task = agent.pending_thinking
    await scheduler.shutdown()

    assert agent.pending_thinking is None
    assert old_task is not None
    assert old_task.cancelled()
