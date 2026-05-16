"""Action Queue 调度器:永不在 tick 中等待 planner 完成。"""
from __future__ import annotations

import asyncio
import copy
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol

from src.agent.runtime import ActionSource, AgentRuntime, QueuedAction, ThinkingReason
from src.memory.store import Memory, MemoryStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SchedulerConfig:
    """Scheduler 调度参数。

    成本控制要点(2026-05-16 实测调整):
    - thinking_trigger_threshold 从 30 → 120 游戏秒:fine plan 触发频率降 4 倍
    - max_planner_actions 从 10 → 15:每次 fine plan 出更多 action 覆盖更长时段
    - 共同降低 LLM 调用频率,把 ¥1.76/游戏日 拉回到目标 ¥0.4/游戏日
    """

    thinking_trigger_threshold: float = 120.0
    fallback_idle_seconds: float = 2.0
    max_planner_actions: int = 15
    max_consecutive_planning_failures: int = 3


@dataclass
class TickResult:
    agent_id: str
    started_action: QueuedAction | None = None
    completed_action: QueuedAction | None = None
    appended_actions: list[QueuedAction] = field(default_factory=list)
    fallback_action: QueuedAction | None = None
    thinking_started: bool = False
    thinking_completed: bool = False
    thinking_failed: bool = False
    error: str | None = None


class PlanProvider(Protocol):
    async def plan_next_actions(
        self,
        agent: AgentRuntime,
        reason: ThinkingReason,
        context: dict[str, Any],
    ) -> list[QueuedAction]:
        ...


class IdlePlanProvider:
    async def plan_next_actions(
        self,
        agent: AgentRuntime,
        reason: ThinkingReason,
        context: dict[str, Any],
    ) -> list[QueuedAction]:
        return [
            QueuedAction(
                action_type="idle",
                args={"reason": "idle_plan_provider"},
                duration_seconds=5.0,
                source=ActionSource.FALLBACK,
            )
        ]


class PerceptionListener(Protocol):
    """Block F:scheduler 在 action 完成时调用此协议。

    实现见 src.agent.perception.PerceptionBroker。Protocol 让 scheduler 不依赖
    具体实现,可注入任何匹配签名的对象(便于测试)。返回值由 scheduler 丢弃,
    抛异常会被 _memory_write_tasks 的 done_callback 静默 log 不影响 tick。
    """

    async def on_action_completed(
        self,
        actor: AgentRuntime,
        action: QueuedAction,
        all_agents: Iterable[AgentRuntime],
        game_time: float,
    ) -> Any:
        ...


class ActionScheduler:
    def __init__(
        self,
        planner: PlanProvider | None = None,
        memory_store: MemoryStore | None = None,
        config: SchedulerConfig | None = None,
        perception_broker: PerceptionListener | None = None,
    ) -> None:
        self._planner = planner or IdlePlanProvider()
        self._memory_store = memory_store
        self._config = config or SchedulerConfig()
        self._perception_broker = perception_broker
        self._agents: dict[str, AgentRuntime] = {}
        self._discarded_planning_tasks: set[asyncio.Task[list[QueuedAction]]] = set()
        self._memory_write_tasks: set[asyncio.Task[None]] = set()

    def register_agent(self, agent: AgentRuntime) -> None:
        self._agents[agent.agent_id] = agent
        logger.info("[scheduler] registered agent=%s", agent.agent_id)

    def get_agent(self, agent_id: str) -> AgentRuntime:
        try:
            return self._agents[agent_id]
        except KeyError as exc:
            raise KeyError(f"agent not registered: {agent_id}") from exc

    async def enqueue(
        self,
        agent_id: str,
        action: QueuedAction,
        *,
        front: bool = False,
    ) -> None:
        agent = self.get_agent(agent_id)
        if front:
            agent.action_queue.appendleft(action)
        else:
            agent.action_queue.append(action)

    async def tick_agent(
        self,
        agent_id: str,
        *,
        game_time: float,
        dt: float,
        context: dict[str, Any] | None = None,
    ) -> TickResult:
        if dt < 0:
            raise ValueError("dt must be >= 0")

        agent = self.get_agent(agent_id)
        tick_context = dict(context or {})
        result = TickResult(agent_id=agent_id)

        await self._collect_finished_thinking(agent, result, game_time)

        if agent.current_action is not None:
            agent.current_action.advance(dt)
            if agent.current_action.is_complete:
                completed = agent.current_action
                result.completed_action = completed
                logger.info(
                    "[scheduler] complete agent=%s action=%s",
                    agent.agent_id,
                    completed.action_type,
                )
                agent.current_action = None
                # Block F:把完成事件丢给 perception broker(异步,不阻塞 tick)
                if self._perception_broker is not None:
                    self._schedule_perception_broadcast(agent, completed, game_time)

        if agent.current_action is None and agent.action_queue:
            next_action = agent.action_queue.popleft()
            next_action.start(game_time)
            agent.current_action = next_action
            result.started_action = next_action
            logger.info(
                "[scheduler] start agent=%s action=%s",
                agent.agent_id,
                next_action.action_type,
            )

        remaining = agent.total_remaining_seconds()
        if remaining < self._config.thinking_trigger_threshold and agent.pending_thinking is None:
            reason = ThinkingReason.EMPTY_QUEUE if remaining <= 0 else ThinkingReason.LOW_WATERMARK
            self._start_background_thinking(agent, reason, game_time, tick_context)
            result.thinking_started = True

        if (
            agent.current_action is None
            and not agent.action_queue
            and agent.pending_thinking is not None
        ):
            fallback = self._build_fallback_action(agent)
            fallback.start(game_time)
            agent.current_action = fallback
            result.fallback_action = fallback
            result.started_action = result.started_action or fallback
            logger.info("[scheduler] fallback idle agent=%s", agent.agent_id)

        return result

    async def tick_all(
        self,
        *,
        game_time: float,
        dt: float,
        context_by_agent: dict[str, dict[str, Any]] | None = None,
    ) -> list[TickResult]:
        if dt < 0:
            raise ValueError("dt must be >= 0")

        contexts = context_by_agent or {}
        agent_ids = list(self._agents)
        raw_results = await asyncio.gather(
            *[
                self.tick_agent(
                    agent_id,
                    game_time=game_time,
                    dt=dt,
                    context=contexts.get(agent_id),
                )
                for agent_id in agent_ids
            ],
            return_exceptions=True,
        )

        results: list[TickResult] = []
        for agent_id, raw_result in zip(agent_ids, raw_results, strict=True):
            if isinstance(raw_result, BaseException):
                error = self._format_exception(raw_result)
                logger.warning("[scheduler] tick failed agent=%s: %s", agent_id, error)
                results.append(TickResult(agent_id=agent_id, error=error))
            else:
                results.append(raw_result)
        return results

    async def trigger_emergency_replan(
        self,
        agent_id: str,
        event: dict[str, Any],
        *,
        game_time: float,
    ) -> None:
        agent = self.get_agent(agent_id)
        agent.action_queue.clear()

        old_task = agent.pending_thinking
        if old_task is not None:
            if not old_task.done():
                old_task.cancel()
                logger.info("[scheduler] emergency cancelled pending agent=%s", agent_id)
            self._track_discarded_planning_task(old_task)
            await asyncio.sleep(0)

        agent.pending_thinking = None
        agent.pending_reason = None
        self._start_background_thinking(
            agent,
            ThinkingReason.EMERGENCY,
            game_time,
            {"urgent_event": dict(event)},
        )
        logger.info("[scheduler] emergency replan agent=%s", agent_id)

    async def shutdown(self) -> None:
        pending_tasks: list[asyncio.Task[list[QueuedAction]]] = []
        for agent in self._agents.values():
            task = agent.pending_thinking
            if task is not None:
                if not task.done():
                    task.cancel()
                    pending_tasks.append(task)
                elif not task.cancelled():
                    try:
                        task.result()
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "[scheduler] pending task ended before shutdown: %s",
                            exc,
                        )
                agent.pending_thinking = None
                agent.pending_reason = None

        if pending_tasks:
            done, pending = await asyncio.wait(pending_tasks, timeout=1.0)
            for task in done:
                if task.cancelled():
                    continue
                try:
                    task.result()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("[scheduler] pending task ended during shutdown: %s", exc)
            if pending:
                logger.warning("[scheduler] %d pending tasks did not finish shutdown", len(pending))

        await self._drain_discarded_planning_tasks()
        await self._drain_memory_write_tasks()

    async def _collect_finished_thinking(
        self,
        agent: AgentRuntime,
        result: TickResult,
        game_time: float,
    ) -> None:
        task = agent.pending_thinking
        if task is None or not task.done():
            return

        reason = agent.pending_reason or ThinkingReason.MANUAL
        try:
            actions = self._validate_planner_actions(task.result())
        except asyncio.CancelledError:
            result.thinking_failed = True
            agent.consecutive_planning_failures += 1
            logger.warning("[scheduler] thinking cancelled agent=%s", agent.agent_id)
        except Exception as exc:  # noqa: BLE001
            result.thinking_failed = True
            agent.consecutive_planning_failures += 1
            logger.warning("[scheduler] thinking failed agent=%s: %s", agent.agent_id, exc)
        else:
            result.thinking_completed = True
            result.appended_actions = actions
            agent.action_queue.extend(actions)
            agent.consecutive_planning_failures = 0
            logger.info(
                "[scheduler] thinking completed agent=%s actions=%d",
                agent.agent_id,
                len(actions),
            )
            self._schedule_plan_memory_write(agent, actions, reason, game_time)
        finally:
            agent.pending_thinking = None
            agent.pending_reason = None

    def _validate_planner_actions(self, raw_actions: object) -> list[QueuedAction]:
        if not isinstance(raw_actions, list):
            raise ValueError("planner result must be list[QueuedAction]")

        actions: list[QueuedAction] = []
        for raw_action in raw_actions:
            if not isinstance(raw_action, QueuedAction):
                raise ValueError("planner result contains non-QueuedAction")
            if raw_action.duration_seconds <= 0:
                raise ValueError("planner result contains non-positive duration")
            actions.append(raw_action)

        if len(actions) > self._config.max_planner_actions:
            logger.warning(
                "[scheduler] planner returned %d actions; truncating to %d",
                len(actions),
                self._config.max_planner_actions,
            )
            return actions[: self._config.max_planner_actions]
        return actions

    def _start_background_thinking(
        self,
        agent: AgentRuntime,
        reason: ThinkingReason,
        game_time: float,
        context: dict[str, Any],
    ) -> None:
        task_context = dict(context)
        task_context.setdefault("game_time", game_time)
        agent.pending_thinking = asyncio.create_task(
            self._planner.plan_next_actions(agent, reason, task_context)
        )
        agent.pending_reason = reason
        agent.last_thinking_started_at = game_time
        logger.info("[scheduler] thinking started agent=%s reason=%s", agent.agent_id, reason.value)

    def _build_fallback_action(self, agent: AgentRuntime) -> QueuedAction:
        reason = agent.pending_reason.value if agent.pending_reason is not None else "unknown"
        return QueuedAction(
            action_type="idle",
            args={"reason": "waiting_for_plan", "thinking_reason": reason},
            duration_seconds=self._config.fallback_idle_seconds,
            source=ActionSource.FALLBACK,
        )

    async def _write_plan_memory(
        self,
        agent_id: str,
        current_location: str,
        actions: list[QueuedAction],
        reason: ThinkingReason,
        game_time: float,
    ) -> None:
        if self._memory_store is None or not actions:
            return
        content = "计划: " + " -> ".join(self._format_action_for_memory(action) for action in actions)
        keywords = [
            keyword
            for keyword in [
                current_location,
                "plan",
                reason.value,
                *(action.action_type for action in actions),
            ]
            if keyword
        ]
        try:
            await self._memory_store.insert(
                Memory(
                    memory_id=None,
                    agent_id=agent_id,
                    memory_type="plan",
                    content=content,
                    importance=7 if reason is ThinkingReason.EMERGENCY else 4,
                    game_time=game_time,
                    real_time=time.time(),
                    location=current_location or None,
                    related_agents=[],
                    keywords=keywords,
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[scheduler] plan memory write failed agent=%s: %s", agent_id, exc)

    def _format_action_for_memory(self, action: QueuedAction) -> str:
        if action.args:
            args_text = ", ".join(f"{key}={value}" for key, value in action.args.items())
            return f"{action.action_type}({args_text}, {action.duration_seconds:g}s)"
        return f"{action.action_type}({action.duration_seconds:g}s)"

    def _schedule_plan_memory_write(
        self,
        agent: AgentRuntime,
        actions: list[QueuedAction],
        reason: ThinkingReason,
        game_time: float,
    ) -> None:
        if self._memory_store is None or not actions:
            return
        task = asyncio.create_task(
            self._write_plan_memory(
                agent.agent_id,
                agent.current_location,
                copy.deepcopy(actions),
                reason,
                game_time,
            )
        )
        self._memory_write_tasks.add(task)
        task.add_done_callback(self._consume_memory_write_task)

    def _schedule_perception_broadcast(
        self,
        agent: AgentRuntime,
        action: QueuedAction,
        game_time: float,
    ) -> None:
        """Block F:把 broker 调用作为后台任务,不阻塞 tick。

        复用 _memory_write_tasks 集合,使 shutdown() 自然 drain perception 写入。
        broker 内部异常会被 _consume_memory_write_task 静默 log。
        """
        if self._perception_broker is None:
            return
        # 拷贝 action 与 agents 快照,避免 broker 在异步执行期间观察到后续 tick 的状态变更
        action_snapshot = copy.deepcopy(action)
        agent_snapshot = list(self._agents.values())
        task = asyncio.create_task(
            self._perception_broker.on_action_completed(
                agent, action_snapshot, agent_snapshot, game_time,
            )
        )
        self._memory_write_tasks.add(task)
        task.add_done_callback(self._consume_memory_write_task)

    def _consume_memory_write_task(self, task: asyncio.Task[None]) -> None:
        if task not in self._memory_write_tasks:
            return
        self._memory_write_tasks.discard(task)
        try:
            task.result()
        except asyncio.CancelledError:
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("[scheduler] plan memory task failed: %s", exc)

    def _track_discarded_planning_task(
        self,
        task: asyncio.Task[list[QueuedAction]],
    ) -> None:
        self._discarded_planning_tasks.add(task)
        task.add_done_callback(self._consume_discarded_planning_task)

    def _consume_discarded_planning_task(
        self,
        task: asyncio.Task[list[QueuedAction]],
    ) -> None:
        if task not in self._discarded_planning_tasks:
            return
        self._discarded_planning_tasks.discard(task)
        try:
            task.result()
        except asyncio.CancelledError:
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("[scheduler] discarded planning task failed: %s", exc)

    async def _drain_discarded_planning_tasks(self) -> None:
        tasks = list(self._discarded_planning_tasks)
        if not tasks:
            return
        for task in tasks:
            if not task.done():
                task.cancel()
        done, pending = await asyncio.wait(tasks, timeout=1.0)
        for task in done:
            self._consume_discarded_planning_task(task)
        if pending:
            logger.warning("[scheduler] %d discarded planner tasks did not finish", len(pending))

    async def _drain_memory_write_tasks(self) -> None:
        tasks = list(self._memory_write_tasks)
        if not tasks:
            return
        done, pending = await asyncio.wait(tasks, timeout=1.0)
        for task in done:
            self._consume_memory_write_task(task)
        if not pending:
            return
        logger.warning("[scheduler] %d plan memory writes did not finish shutdown", len(pending))
        for task in pending:
            task.cancel()
        done_after_cancel, still_pending = await asyncio.wait(pending, timeout=1.0)
        for task in done_after_cancel:
            self._consume_memory_write_task(task)
        if still_pending:
            logger.warning(
                "[scheduler] %d plan memory writes remained pending after cancel",
                len(still_pending),
            )

    def _format_exception(self, exc: BaseException) -> str:
        return f"{type(exc).__name__}: {exc}"


default_scheduler = ActionScheduler()


async def enqueue(agent_id: str, action: dict[str, Any]) -> None:
    """模块级兼容包装:把 dict action 放进默认 scheduler。"""
    try:
        default_scheduler.get_agent(agent_id)
    except KeyError:
        default_scheduler.register_agent(AgentRuntime(agent_id=agent_id))
    queued = QueuedAction(**action)
    await default_scheduler.enqueue(agent_id, queued)


async def tick() -> None:
    """兼容占位接口;Block H 接入 game_time/dt 后再实现。"""
    raise NotImplementedError("Block H 接入 game_time 后实现")
