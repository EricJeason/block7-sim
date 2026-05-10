"""SimEngine 单测:不烧真实 API,用 IdlePlanProvider 做规划兜底。"""
from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio

from src.agent.perception import PerceptionBroker
from src.agent.planning import LocationLoader, PersonaLoader
from src.agent.scheduler import ActionScheduler
from src.memory.schema import init_db
from src.memory.store import MemoryStore
from src.sim import SimEngine


@pytest_asyncio.fixture
async def store(tmp_path):
    db_path = str(tmp_path / "sim.db")
    await init_db(db_path)
    return MemoryStore(db_path)


@pytest.fixture
def persona_loader() -> PersonaLoader:
    return PersonaLoader()


@pytest.fixture
def location_loader() -> LocationLoader:
    return LocationLoader()


def _engine(
    store: MemoryStore,
    persona_loader: PersonaLoader,
    location_loader: LocationLoader,
    *,
    agent_ids: list[str] | None = None,
    time_scale: float = 60.0,
    tick_interval: float = 0.05,
) -> SimEngine:
    """构造 SimEngine,默认 scheduler 用 IdlePlanProvider(无 LLM)。"""
    broker = PerceptionBroker(
        memory_store=store,
        persona_loader=persona_loader,
        location_loader=location_loader,
    )
    scheduler = ActionScheduler(memory_store=store, perception_broker=broker)
    return SimEngine(
        scheduler=scheduler,
        memory_store=store,
        persona_loader=persona_loader,
        location_loader=location_loader,
        time_scale=time_scale,
        tick_interval_seconds=tick_interval,
        agent_ids=agent_ids or ["agent_01", "agent_02", "agent_03"],
    )


# ============================================================================
#                       Registration & lifecycle
# ============================================================================


@pytest.mark.asyncio
async def test_start_registers_all_agents(
    store, persona_loader, location_loader
) -> None:
    engine = _engine(store, persona_loader, location_loader)
    await engine.start(run_loop=False)
    for aid in ("agent_01", "agent_02", "agent_03"):
        agent = engine.scheduler.get_agent(aid)
        assert agent.persona_name  # 中文名已填
        assert agent.current_location  # initial_location 已填


@pytest.mark.asyncio
async def test_start_skips_missing_persona(
    store, persona_loader, location_loader
) -> None:
    engine = _engine(
        store,
        persona_loader,
        location_loader,
        agent_ids=["agent_01", "agent_99"],
    )
    await engine.start(run_loop=False)
    engine.scheduler.get_agent("agent_01")  # ok
    with pytest.raises(KeyError):
        engine.scheduler.get_agent("agent_99")


@pytest.mark.asyncio
async def test_start_idempotent(store, persona_loader, location_loader) -> None:
    engine = _engine(store, persona_loader, location_loader)
    await engine.start(run_loop=False)
    await engine.start(run_loop=False)  # 第二次不应出错
    # 仍只有 3 个
    assert len(list(engine.scheduler._agents)) == 3


# ============================================================================
#                              tick_once
# ============================================================================


@pytest.mark.asyncio
async def test_tick_once_advances_game_time(
    store, persona_loader, location_loader
) -> None:
    engine = _engine(
        store, persona_loader, location_loader, time_scale=60.0, tick_interval=1.0
    )
    await engine.start(run_loop=False)
    assert engine.game_time == 0.0
    await engine.tick_once(dt_real=1.0)
    assert engine.game_time == 60.0  # 60 game seconds per real second
    await engine.tick_once(dt_real=2.0)
    assert engine.game_time == 60.0 + 120.0


@pytest.mark.asyncio
async def test_tick_once_returns_one_result_per_agent(
    store, persona_loader, location_loader
) -> None:
    engine = _engine(store, persona_loader, location_loader)
    await engine.start(run_loop=False)
    results = await engine.tick_once()
    ids = {r.agent_id for r in results}
    assert ids == {"agent_01", "agent_02", "agent_03"}


# ============================================================================
#                         world_snapshot 形状
# ============================================================================


@pytest.mark.asyncio
async def test_world_snapshot_shape(
    store, persona_loader, location_loader
) -> None:
    engine = _engine(store, persona_loader, location_loader)
    await engine.start(run_loop=False)
    snap = engine.world_snapshot()
    assert snap["time_scale"] == 60.0
    assert snap["game_time"] == 0.0
    assert len(snap["locations"]) == 4  # 4 个场所
    assert len(snap["agents"]) == 3
    # 每个 agent 都有 display_name (从 persona)
    for a in snap["agents"]:
        assert a["display_name"]
        assert a["current_location"]


# ============================================================================
#                          subscribe / publish
# ============================================================================


@pytest.mark.asyncio
async def test_subscribe_unsubscribe(store, persona_loader, location_loader) -> None:
    engine = _engine(store, persona_loader, location_loader)
    q = engine.subscribe()
    assert q in engine._subscribers
    engine.unsubscribe(q)
    assert q not in engine._subscribers


@pytest.mark.asyncio
async def test_tick_publishes_thinking_event(
    store, persona_loader, location_loader
) -> None:
    """IdlePlanProvider 会在第一个 tick 立刻被触发(队列 < 30s 阈值)
    → 事件流应包含 thinking_started。"""
    engine = _engine(store, persona_loader, location_loader)
    await engine.start(run_loop=False)
    q = engine.subscribe()
    await engine.tick_once(dt_real=0.5)

    # 收一些事件,但不等到天荒地老
    types = []
    for _ in range(20):
        try:
            ev = await asyncio.wait_for(q.get(), timeout=0.1)
            types.append(ev.type)
        except asyncio.TimeoutError:
            break
    assert "thinking_started" in types


# ============================================================================
#                        run_loop start/stop
# ============================================================================


@pytest.mark.asyncio
async def test_run_loop_starts_and_stops_cleanly(
    store, persona_loader, location_loader
) -> None:
    engine = _engine(
        store,
        persona_loader,
        location_loader,
        time_scale=10.0,
        tick_interval=0.05,  # 50ms 一次 tick
    )
    await engine.start(run_loop=True)
    # 让它 tick 几下
    await asyncio.sleep(0.2)
    assert engine.game_time > 0  # 至少前进过
    await engine.stop()
    # 停掉后再观察 100ms,游戏时间不应再前进
    final = engine.game_time
    await asyncio.sleep(0.1)
    assert engine.game_time == final
