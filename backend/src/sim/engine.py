"""SimEngine:把 scheduler / planner / broker / memory_store 拼起来跑。

职责:
- 启动时从 PersonaLoader 注册全部 12 agent (current_location 来自 persona.initial_location)
- 后台 asyncio.Task 定期 tick:推进 game_time + 调 scheduler.tick_all
- 把 TickResult 翻译成 SimEvent 推给所有订阅者(WebSocket fanout)
- 优雅停机:停止 tick 循环 + 调 scheduler.shutdown() drain pending tasks

设计要点:
- tick_once() 是手动接口,供测试 + 不开自动循环时使用
- 自动循环用 wait_for(stop_event, timeout=interval) 实现可中断 sleep
- 订阅者用 asyncio.Queue (有界,满时丢事件并 log)
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from src.agent.planning import LocationLoader, PersonaLoader
from src.agent.runtime import AgentRuntime
from src.agent.scheduler import ActionScheduler, TickResult
from src.memory.store import MemoryStore

logger = logging.getLogger(__name__)


@dataclass
class SimEvent:
    """Sim 内部事件,序列化后发给 WebSocket 订阅者。"""

    type: str  # tick / action_started / action_completed / thinking_started / thinking_completed / agent_moved / tick_error
    agent_id: str | None
    game_time: float
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "agent_id": self.agent_id,
            "game_time": self.game_time,
            "payload": self.payload,
        }


class SimEngine:
    """模拟引擎主入口。FastAPI lifespan 启动一个,挂到 app.state。"""

    def __init__(
        self,
        scheduler: ActionScheduler,
        memory_store: MemoryStore,
        persona_loader: PersonaLoader,
        location_loader: LocationLoader,
        time_scale: float = 60.0,
        tick_interval_seconds: float = 1.0,
        agent_ids: list[str] | None = None,
        subscriber_queue_size: int = 200,
    ) -> None:
        """
        Args:
            time_scale: 1 现实秒 = N 游戏秒。默认 60(1 现实分钟 = 1 游戏小时)。
            tick_interval_seconds: 后台 tick 循环的真实秒间隔。默认 1.0。
            agent_ids: 要注册的 agent 列表;None → 自动加载 personas/ 下全部。
            subscriber_queue_size: 单个订阅者队列上限,满时丢事件防止慢消费者拖慢 sim。
        """
        self.scheduler = scheduler
        self.memory_store = memory_store
        self.persona_loader = persona_loader
        self.location_loader = location_loader
        self.time_scale = time_scale
        self.tick_interval_seconds = tick_interval_seconds
        self.agent_ids = agent_ids or persona_loader.list_agent_ids()
        self.subscriber_queue_size = subscriber_queue_size

        self.game_time: float = 0.0
        self._tick_task: asyncio.Task[None] | None = None
        self._stop_event: asyncio.Event | None = None
        self._subscribers: set[asyncio.Queue[SimEvent]] = set()
        self._registered = False

    # ---------------------------------------------------------------- start

    async def start(self, *, run_loop: bool = True) -> None:
        """注册 agent + (可选)启动后台 tick 循环。

        run_loop=False 时(测试用),只注册,不启动循环;调用方手动 tick_once。
        """
        if not self._registered:
            self._register_agents()
            self._registered = True
        if run_loop and self._tick_task is None:
            self._stop_event = asyncio.Event()
            self._tick_task = asyncio.create_task(self._run_tick_loop())
            logger.info(
                "[sim] started: %d agents, time_scale=%g, tick_interval=%gs",
                len(self.agent_ids),
                self.time_scale,
                self.tick_interval_seconds,
            )

    def _register_agents(self) -> None:
        registered = 0
        for agent_id in self.agent_ids:
            try:
                persona = self.persona_loader.load(agent_id)
            except FileNotFoundError:
                logger.warning(
                    "[sim] skipping unknown agent_id=%s (persona file missing)", agent_id
                )
                continue
            agent = AgentRuntime(
                agent_id=agent_id,
                persona_name=persona.display_name,
                current_location=persona.initial_location,
            )
            self.scheduler.register_agent(agent)
            registered += 1
        logger.info("[sim] registered %d agents", registered)

    # ------------------------------------------------------------------ stop

    async def stop(self) -> None:
        """优雅停机:取消 tick 循环 + drain scheduler pending tasks。"""
        if self._stop_event is not None:
            self._stop_event.set()
        if self._tick_task is not None:
            try:
                await asyncio.wait_for(self._tick_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("[sim] tick loop did not stop in 5s, cancelling")
                self._tick_task.cancel()
                try:
                    await self._tick_task
                except (asyncio.CancelledError, Exception):  # noqa: BLE001
                    pass
            self._tick_task = None
        await self.scheduler.shutdown()
        logger.info("[sim] stopped at game_time=%g", self.game_time)

    # ---------------------------------------------------------------- ticks

    async def tick_once(self, dt_real: float | None = None) -> list[TickResult]:
        """手动一次 tick(测试 + run_loop=False 场景)。

        dt_real 默认用 tick_interval_seconds。返回所有 agent 的 TickResult。
        """
        if dt_real is None:
            dt_real = self.tick_interval_seconds
        game_dt = dt_real * self.time_scale
        self.game_time += game_dt
        results = await self.scheduler.tick_all(
            game_time=self.game_time, dt=game_dt
        )
        for r in results:
            self._publish_tick_result(r)
        return results

    async def _run_tick_loop(self) -> None:
        assert self._stop_event is not None
        last_real = time.monotonic()
        while not self._stop_event.is_set():
            try:
                # 等 stop 信号或 tick 间隔,谁先到谁触发
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.tick_interval_seconds,
                )
                # stop 触发了 → 退出循环
                break
            except asyncio.TimeoutError:
                pass  # 正常 tick 时机
            now = time.monotonic()
            dt_real = now - last_real
            last_real = now
            try:
                await self.tick_once(dt_real=dt_real)
            except Exception as exc:  # noqa: BLE001
                logger.exception("[sim] tick error: %s", exc)

    # ------------------------------------------------------- subscribe / pub

    def subscribe(self) -> asyncio.Queue[SimEvent]:
        """WebSocket handler 调此获得一个事件队列。记得在断开时 unsubscribe。"""
        q: asyncio.Queue[SimEvent] = asyncio.Queue(maxsize=self.subscriber_queue_size)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[SimEvent]) -> None:
        self._subscribers.discard(q)

    def _publish(self, event: SimEvent) -> None:
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    "[sim] subscriber queue full, dropping type=%s agent=%s",
                    event.type,
                    event.agent_id,
                )

    def _publish_tick_result(self, result: TickResult) -> None:
        gt = self.game_time
        if result.error:
            self._publish(
                SimEvent(
                    type="tick_error",
                    agent_id=result.agent_id,
                    game_time=gt,
                    payload={"error": result.error},
                )
            )
            return
        # 按 scheduler 内部实际产生顺序发:thinking 完成 → action 完成 → action 启动 → thinking 启动
        if result.thinking_completed:
            self._publish(
                SimEvent(
                    type="thinking_completed",
                    agent_id=result.agent_id,
                    game_time=gt,
                    payload={"appended_count": len(result.appended_actions)},
                )
            )
        if result.completed_action is not None:
            self._publish(
                SimEvent(
                    type="action_completed",
                    agent_id=result.agent_id,
                    game_time=gt,
                    payload={
                        "action_type": result.completed_action.action_type,
                        "args": dict(result.completed_action.args),
                    },
                )
            )
        if result.started_action is not None:
            agent = self.scheduler.get_agent(result.agent_id)
            self._publish(
                SimEvent(
                    type="action_started",
                    agent_id=result.agent_id,
                    game_time=gt,
                    payload={
                        "action_type": result.started_action.action_type,
                        "args": dict(result.started_action.args),
                        "duration_seconds": result.started_action.duration_seconds,
                        "current_location": agent.current_location,
                    },
                )
            )
        if result.thinking_started:
            self._publish(
                SimEvent(
                    type="thinking_started",
                    agent_id=result.agent_id,
                    game_time=gt,
                )
            )

    # ------------------------------------------------------- snapshot helpers

    def world_snapshot(self) -> dict[str, Any]:
        """初始化时给客户端的世界快照:locations + agents 当前分布 + 元数据。"""
        locations = []
        for loc in self.location_loader.all().values():
            locations.append(
                {
                    "id": loc.location_id,
                    "name": loc.name,
                    "type": loc.type,
                    "description": loc.description,
                    "open_hours": loc.open_hours,
                    "adjacent_to": list(loc.adjacent_to),
                }
            )
        agents = []
        for agent_id in self.agent_ids:
            try:
                agent = self.scheduler.get_agent(agent_id)
            except KeyError:
                continue
            try:
                persona = self.persona_loader.load(agent_id)
                display_name = persona.display_name
            except FileNotFoundError:
                display_name = ""
            agents.append(
                {
                    "agent_id": agent_id,
                    "display_name": display_name,
                    "current_location": agent.current_location,
                    "current_mood": agent.current_mood,
                    "current_action": (
                        agent.current_action.to_dict()
                        if agent.current_action is not None
                        else None
                    ),
                }
            )
        return {
            "game_time": self.game_time,
            "time_scale": self.time_scale,
            "tick_interval_seconds": self.tick_interval_seconds,
            "locations": locations,
            "agents": agents,
        }
