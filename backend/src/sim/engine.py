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
from src.memory.compression import MemoryCompressor
from src.agent.reflection import ReflectionRunner
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
        reflection_runner: ReflectionRunner | None = None,
        compressor: MemoryCompressor | None = None,
        enable_daily_reflection: bool = True,
        seconds_per_game_day: float = 86400.0,
        dialogue_manager: Any | None = None,
    ) -> None:
        """
        Args:
            time_scale: 1 现实秒 = N 游戏秒。默认 60(1 现实分钟 = 1 游戏小时)。
            tick_interval_seconds: 后台 tick 循环的真实秒间隔。默认 1.0。
            agent_ids: 要注册的 agent 列表;None → 自动加载 personas/ 下全部。
            subscriber_queue_size: 单个订阅者队列上限,满时丢事件防止慢消费者拖慢 sim。
            reflection_runner: Block G ReflectionRunner;None → 不做跨日反思。
            compressor: Block G MemoryCompressor;None → 不做跨日压缩。
            enable_daily_reflection: True 且有 runner/compressor → 跨日自动触发。
        """
        self.scheduler = scheduler
        self.memory_store = memory_store
        self.persona_loader = persona_loader
        self.location_loader = location_loader
        self.time_scale = time_scale
        self.tick_interval_seconds = tick_interval_seconds
        self.agent_ids = agent_ids or persona_loader.list_agent_ids()
        self.subscriber_queue_size = subscriber_queue_size
        self.reflection_runner = reflection_runner
        self.compressor = compressor
        self.enable_daily_reflection = enable_daily_reflection
        self.seconds_per_game_day = seconds_per_game_day
        # 弱引用 DialogueManager 只是为了 /sim/health 统计;若用 weakref 会麻烦,
        # 直接 keep ref(life cycle 与 SimEngine 一致,都活到 lifespan 结束)
        self.dialogue_manager = dialogue_manager

        self.game_time: float = 0.0
        self._tick_task: asyncio.Task[None] | None = None
        self._stop_event: asyncio.Event | None = None
        self._subscribers: set[asyncio.Queue[SimEvent]] = set()
        self._registered = False
        self._paused: bool = False
        self._last_game_day: int = 0
        self._reflection_tasks: set[asyncio.Task[None]] = set()
        # P3 打磨:运行时统计,GET /sim/health 暴露
        self._start_real_time: float = 0.0
        self._total_ticks: int = 0
        self._reflection_started_count: int = 0
        self._reflection_completed_count: int = 0
        self._reflection_total_count: int = 0
        self._reflection_merged_count: int = 0
        self._reflection_archived_count: int = 0
        self._reflection_total_cost: float = 0.0

    # ---------------------------------------------------------------- start

    async def start(self, *, run_loop: bool = True, paused: bool = False) -> None:
        """注册 agent + (可选)启动后台 tick 循环。

        run_loop=False 时(测试用),只注册,不启动循环;调用方手动 tick_once。
        paused=True 时,tick 循环启动但暂停状态——不烧任何 token,
        客户端调用 /sim/resume 才开始真实运行(Eric 用此默认控制成本)。
        """
        self._paused = paused
        if not self._registered:
            self._register_agents()
            self._registered = True
        if self._start_real_time == 0.0:
            self._start_real_time = time.monotonic()
        if run_loop and self._tick_task is None:
            self._stop_event = asyncio.Event()
            self._tick_task = asyncio.create_task(self._run_tick_loop())
            logger.info(
                "[sim] started: %d agents, time_scale=%g, tick_interval=%gs, paused=%s",
                len(self.agent_ids),
                self.time_scale,
                self.tick_interval_seconds,
                self._paused,
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
        """优雅停机:取消 tick 循环 + drain scheduler/reflection pending tasks。"""
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
        # 取消未完成的 reflection task(Pro think_high 单次 60s,shutdown 必须能强行结束)
        for task in list(self._reflection_tasks):
            if not task.done():
                task.cancel()
        if self._reflection_tasks:
            await asyncio.wait(self._reflection_tasks, timeout=2.0)
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
        self._total_ticks += 1
        # Block G:跨游戏日 → 触发后台反思 + 压缩
        new_game_day = int(self.game_time // self.seconds_per_game_day)
        if new_game_day > self._last_game_day:
            completed_day = self._last_game_day
            self._last_game_day = new_game_day
            self._schedule_daily_reflection(completed_day)
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
            if self._paused:
                # 暂停期间 last_real 仍更新,resume 后不会突然推一大段 game_time
                continue
            try:
                await self.tick_once(dt_real=dt_real)
            except Exception as exc:  # noqa: BLE001
                logger.exception("[sim] tick error: %s", exc)

    # -------------------------------------------- Block G: daily reflection

    def _schedule_daily_reflection(self, completed_day: int) -> None:
        """跨日时启动后台任务跑反思 + 压缩。永不阻塞 tick。"""
        if not self.enable_daily_reflection:
            return
        if self.reflection_runner is None and self.compressor is None:
            return
        self._reflection_started_count += 1
        self._publish(
            SimEvent(
                type="daily_reflection_started",
                agent_id=None,
                game_time=self.game_time,
                payload={
                    "game_day": completed_day,
                    "agent_count": len(self.agent_ids),
                },
            )
        )
        task = asyncio.create_task(self._run_daily_reflection(completed_day))
        self._reflection_tasks.add(task)
        task.add_done_callback(self._reflection_tasks.discard)

    async def _run_daily_reflection(self, completed_day: int) -> None:
        """并行跑所有 agent 的 reflection,然后并行跑 compression。"""
        reflection_total = 0
        cost_total = 0.0
        if self.reflection_runner is not None:
            tasks = [
                self.reflection_runner.run_for_agent(
                    agent_id=aid, game_day=completed_day, game_time=self.game_time,
                )
                for aid in self.agent_ids
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, BaseException):
                    logger.warning("[sim] reflection task error: %s", r)
                    continue
                reflection_total += len(r.reflections)
                cost_total += r.cost_yuan

        archived_total = 0
        merged_total = 0
        if self.compressor is not None:
            tasks = [
                self.compressor.compress_old_memories(
                    agent_id=aid, current_game_time=self.game_time
                )
                for aid in self.agent_ids
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, BaseException):
                    logger.warning("[sim] compression task error: %s", r)
                    continue
                archived_total += r.archived_count
                merged_total += r.merged_count
                cost_total += r.cost_yuan

        logger.info(
            "[sim] daily reflection day=%d: %d reflections, merged=%d archived=%d, cost=%.3f元",
            completed_day, reflection_total, merged_total, archived_total, cost_total,
        )
        # 累计统计(P3 /sim/health)
        self._reflection_completed_count += 1
        self._reflection_total_count += reflection_total
        self._reflection_merged_count += merged_total
        self._reflection_archived_count += archived_total
        self._reflection_total_cost += cost_total
        self._publish(
            SimEvent(
                type="daily_reflection_completed",
                agent_id=None,
                game_time=self.game_time,
                payload={
                    "game_day": completed_day,
                    "reflection_count": reflection_total,
                    "merged_count": merged_total,
                    "archived_count": archived_total,
                    "cost_yuan": round(cost_total, 4),
                },
            )
        )

    # ---------------------------------------------------------- pause / resume

    def is_paused(self) -> bool:
        return self._paused

    def pause(self) -> None:
        """暂停 tick(不影响已经在 await 的 LLM 任务,但不会触发新一波)。

        客户端可调 POST /sim/pause 触发。重复调用幂等。
        """
        if self._paused:
            return
        self._paused = True
        logger.info("[sim] paused at game_time=%g", self.game_time)
        self._publish(
            SimEvent(
                type="paused_changed",
                agent_id=None,
                game_time=self.game_time,
                payload={"paused": True},
            )
        )

    def resume(self) -> None:
        if not self._paused:
            return
        self._paused = False
        logger.info("[sim] resumed at game_time=%g", self.game_time)
        self._publish(
            SimEvent(
                type="paused_changed",
                agent_id=None,
                game_time=self.game_time,
                payload={"paused": False},
            )
        )

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
                        "source": result.completed_action.source.value,
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
                        # Block I 精修 #2:source 让 Godot 区分 fallback / planner /
                        # emergency / manual,LoadingOverlay 只在真 planner action
                        # 到达后才算 warmup 完成,不被 fallback idle 误触发
                        "source": result.started_action.source.value,
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
        if result.thinking_failed:
            # thinking 被 cancel / 抛异常 — 复用 thinking_completed 通知前端
            # 隐藏 💭(原代码只发 completed,失败时 💭 残留)
            self._publish(
                SimEvent(
                    type="thinking_failed",
                    agent_id=result.agent_id,
                    game_time=gt,
                )
            )

    # ------------------------------------------------------ external emitter

    def emit_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        agent_id: str | None = None,
    ) -> None:
        """通用 SimEvent 发布接口,供外部模块(如 DialogueManager)推送事件给订阅者。

        type 已存在的:tick / action_started / action_completed / thinking_started /
        thinking_completed / agent_moved / tick_error / paused_changed / hello。
        Block I 新增:dialogue_started / dialogue_line / dialogue_ended。
        """
        self._publish(
            SimEvent(
                type=event_type,
                agent_id=agent_id,
                game_time=self.game_time,
                payload=payload,
            )
        )

    # ------------------------------------------------------- snapshot helpers

    def health_snapshot(self, llm_client: Any | None = None) -> dict[str, Any]:
        """运行时健康统计。给 GET /sim/health 用。

        Args:
            llm_client: 可选,传 DeepSeekClient 实例可加 LLM 总成本/调用统计
        """
        uptime = time.monotonic() - self._start_real_time if self._start_real_time > 0 else 0.0
        snap: dict[str, Any] = {
            "uptime_seconds": round(uptime, 1),
            "game_time": self.game_time,
            "game_day": int(self.game_time // self.seconds_per_game_day),
            "paused": self._paused,
            "agent_count": len(self.agent_ids),
            "subscriber_count": len(self._subscribers),
            "tick_count": self._total_ticks,
            "time_scale": self.time_scale,
            "tick_interval_seconds": self.tick_interval_seconds,
            "reflection": {
                "started": self._reflection_started_count,
                "completed": self._reflection_completed_count,
                "in_flight": len(self._reflection_tasks),
                "total_reflections": self._reflection_total_count,
                "total_merged": self._reflection_merged_count,
                "total_archived": self._reflection_archived_count,
                "total_cost_yuan": round(self._reflection_total_cost, 4),
            },
        }
        if llm_client is not None and hasattr(llm_client, "total_cost_yuan"):
            snap["llm"] = {
                "total_calls": getattr(llm_client, "total_calls", 0),
                "total_cost_yuan": round(getattr(llm_client, "total_cost_yuan", 0.0), 4),
                "total_input_tokens": getattr(llm_client, "total_input_tokens", 0),
                "total_output_tokens": getattr(llm_client, "total_output_tokens", 0),
                "total_cache_hit_tokens": getattr(llm_client, "total_cache_hit_tokens", 0),
            }
            # 缓存命中率(仅 input)
            total_in = snap["llm"]["total_input_tokens"]
            if total_in > 0:
                snap["llm"]["cache_hit_rate"] = round(
                    snap["llm"]["total_cache_hit_tokens"] / total_in, 3
                )
            else:
                snap["llm"]["cache_hit_rate"] = 0.0
        if self.dialogue_manager is not None:
            snap["dialogue"] = {
                "total_sessions_started": getattr(
                    self.dialogue_manager, "total_sessions_started", 0
                ),
                "total_sessions_ended": getattr(
                    self.dialogue_manager, "total_sessions_ended", 0
                ),
                "total_lines": getattr(self.dialogue_manager, "total_lines", 0),
                "total_cost_yuan": round(
                    getattr(self.dialogue_manager, "total_cost_yuan", 0.0), 4
                ),
                "active_sessions": len(
                    getattr(self.dialogue_manager, "_sessions", {})
                ),
            }
        return snap

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
            "paused": self._paused,
            "locations": locations,
            "agents": agents,
        }
