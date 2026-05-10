"""Block F 单测:PerceptionBroker + scheduler 集成。

不调用真实 LLM。memory store 用 tmp SQLite。
"""
from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio

from src.agent.perception import PerceptionBroker
from src.agent.planning import LocationLoader, PersonaLoader
from src.agent.runtime import ActionSource, AgentRuntime, QueuedAction
from src.agent.scheduler import ActionScheduler
from src.memory.schema import init_db
from src.memory.store import MemoryStore


# ============================================================================
#                                Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def store(tmp_path):
    db_path = str(tmp_path / "perception.db")
    await init_db(db_path)
    return MemoryStore(db_path)


@pytest.fixture
def persona_loader() -> PersonaLoader:
    return PersonaLoader()


@pytest.fixture
def location_loader() -> LocationLoader:
    return LocationLoader()


def _agent(agent_id: str, location: str = "lao_song_plaza") -> AgentRuntime:
    return AgentRuntime(agent_id=agent_id, current_location=location)


def _action(action_type: str = "work", **args) -> QueuedAction:
    return QueuedAction(
        action_type=action_type,
        args=dict(args),
        duration_seconds=60.0,
        source=ActionSource.PLANNER,
    )


# ============================================================================
#                          Skipping & filtering
# ============================================================================


@pytest.mark.asyncio
async def test_broker_skips_idle_action(store: MemoryStore) -> None:
    broker = PerceptionBroker(memory_store=store)
    actor = _agent("agent_01")
    others = [_agent("agent_02"), _agent("agent_03")]
    written = await broker.on_action_completed(
        actor, _action("idle"), [actor, *others], game_time=100.0
    )
    assert written == []
    # 验证 store 里也确实没写
    for ob in others:
        assert await store.count(ob.agent_id) == 0


@pytest.mark.asyncio
async def test_broker_skips_actor_self(store: MemoryStore) -> None:
    """actor 自己不该作为观察者写一条 'X 在做 Y' 给自己。"""
    broker = PerceptionBroker(memory_store=store)
    actor = _agent("agent_01")
    written = await broker.on_action_completed(
        actor, _action("work", task="x"), [actor], game_time=100.0
    )
    assert written == []
    assert await store.count("agent_01") == 0


@pytest.mark.asyncio
async def test_broker_skips_when_no_co_located(store: MemoryStore) -> None:
    """场上有别人,但都不在同一 location。"""
    broker = PerceptionBroker(memory_store=store)
    actor = _agent("agent_01", location="lao_song_plaza")
    others = [
        _agent("agent_02", location="warm_valley_farm"),
        _agent("agent_03", location="north_frost_workshop"),
    ]
    written = await broker.on_action_completed(
        actor, _action("work", task="x"), [actor, *others], game_time=100.0
    )
    assert written == []
    for ob in others:
        assert await store.count(ob.agent_id) == 0


@pytest.mark.asyncio
async def test_broker_no_memory_store_returns_empty() -> None:
    """没接 store(早期 dev / 单测场景):应安静返回 [],不抛错。"""
    broker = PerceptionBroker(memory_store=None)
    actor = _agent("agent_01")
    others = [_agent("agent_02")]
    result = await broker.on_action_completed(
        actor, _action("work", task="x"), [actor, *others], game_time=100.0
    )
    assert result == []


@pytest.mark.asyncio
async def test_broker_skips_when_actor_has_no_location(store: MemoryStore) -> None:
    broker = PerceptionBroker(memory_store=store)
    actor = _agent("agent_01", location="")
    others = [_agent("agent_02", location="")]
    written = await broker.on_action_completed(
        actor, _action("work", task="x"), [actor, *others], game_time=100.0
    )
    assert written == []


# ============================================================================
#                          Writing observations
# ============================================================================


@pytest.mark.asyncio
async def test_broker_writes_one_memory_per_observer(store: MemoryStore) -> None:
    broker = PerceptionBroker(memory_store=store)
    actor = _agent("agent_01")
    observers = [_agent("agent_02"), _agent("agent_03"), _agent("agent_04")]
    written = await broker.on_action_completed(
        actor, _action("work", task="配药"), [actor, *observers], game_time=100.0
    )
    assert len(written) == 3
    for ob in observers:
        recent = await store.get_recent(ob.agent_id, limit=10)
        assert len(recent) == 1
        assert recent[0].memory_type == "observation"
        assert "配药" in recent[0].content
        assert recent[0].related_agents == ["agent_01"]
        assert recent[0].location == "lao_song_plaza"


@pytest.mark.asyncio
async def test_broker_uses_persona_display_name(
    store: MemoryStore, persona_loader: PersonaLoader
) -> None:
    """有 persona_loader 时,observation 应用中文名 (林秋) 而不是 agent_id。"""
    broker = PerceptionBroker(memory_store=store, persona_loader=persona_loader)
    actor = _agent("agent_01")  # 林秋
    observer = _agent("agent_02")  # 阿杏
    await broker.on_action_completed(
        actor, _action("work", task="配药"), [actor, observer], game_time=100.0
    )
    recent = await store.get_recent("agent_02", limit=1)
    assert "林秋" in recent[0].content
    assert "agent_01" not in recent[0].content


@pytest.mark.asyncio
async def test_broker_uses_location_display_name(
    store: MemoryStore, location_loader: LocationLoader
) -> None:
    broker = PerceptionBroker(memory_store=store, location_loader=location_loader)
    actor = _agent("agent_01", location="lao_song_plaza")
    observer = _agent("agent_02", location="lao_song_plaza")
    await broker.on_action_completed(
        actor, _action("work", task="x"), [actor, observer], game_time=100.0
    )
    recent = await store.get_recent("agent_02", limit=1)
    assert "老松广场" in recent[0].content


@pytest.mark.asyncio
async def test_broker_importance_bumped_for_relationship(
    store: MemoryStore, persona_loader: PersonaLoader
) -> None:
    """阿杏(agent_02)的 initial_relationships 包含 agent_01(林秋) → 看见林秋时
    importance = default(3) + 1 = 4。
    """
    broker = PerceptionBroker(
        memory_store=store, persona_loader=persona_loader, default_importance=3
    )
    actor = _agent("agent_01")  # 林秋
    apricot = _agent("agent_02")  # 阿杏(关系内)
    stranger = _agent("agent_99")  # 未知 agent(无关系)

    await broker.on_action_completed(
        actor, _action("work", task="x"), [actor, apricot, stranger], game_time=100.0
    )
    apricot_mem = (await store.get_recent("agent_02", limit=1))[0]
    assert apricot_mem.importance == 4  # +1 bump

    # 99 没有 persona 文件,fallback 走默认 3
    stranger_mem = (await store.get_recent("agent_99", limit=1))[0]
    assert stranger_mem.importance == 3


@pytest.mark.asyncio
async def test_broker_keywords_include_actor_and_location(
    store: MemoryStore, persona_loader: PersonaLoader, location_loader: LocationLoader
) -> None:
    broker = PerceptionBroker(
        memory_store=store,
        persona_loader=persona_loader,
        location_loader=location_loader,
    )
    actor = _agent("agent_01")
    observer = _agent("agent_02")
    await broker.on_action_completed(
        actor, _action("work", task="x"), [actor, observer], game_time=100.0
    )
    recent = await store.get_recent("agent_02", limit=1)
    kws = " ".join(recent[0].keywords)
    assert "林秋" in kws
    assert "agent_01" in kws
    assert "老松广场" in kws or "lao_song_plaza" in kws
    assert "work" in kws


# ============================================================================
#                            move_to side effect
# ============================================================================


@pytest.mark.asyncio
async def test_move_to_updates_actor_location(store: MemoryStore) -> None:
    broker = PerceptionBroker(memory_store=store)
    actor = _agent("agent_01", location="lao_song_plaza")
    await broker.on_action_completed(
        actor,
        _action("move_to", location="north_frost_workshop"),
        [actor],
        game_time=100.0,
    )
    assert actor.current_location == "north_frost_workshop"


@pytest.mark.asyncio
async def test_move_to_invalid_location_does_not_apply(
    store: MemoryStore, location_loader: LocationLoader
) -> None:
    broker = PerceptionBroker(memory_store=store, location_loader=location_loader)
    actor = _agent("agent_01", location="lao_song_plaza")
    await broker.on_action_completed(
        actor,
        _action("move_to", location="不存在的场所"),
        [actor],
        game_time=100.0,
    )
    # 验证未生效
    assert actor.current_location == "lao_song_plaza"


@pytest.mark.asyncio
async def test_move_to_then_observers_at_destination_see_arrival(
    store: MemoryStore, location_loader: LocationLoader
) -> None:
    """林秋从老松广场 move_to 北霜工坊 → 北霜工坊在场的人(千绫)应看到她到达。
    老松广场上的人(苏拂)不该收到。
    """
    broker = PerceptionBroker(memory_store=store, location_loader=location_loader)
    actor = _agent("agent_01", location="lao_song_plaza")  # 林秋出发地
    qianling = _agent("agent_06", location="north_frost_workshop")  # 千绫在目的地
    sufu = _agent("agent_07", location="lao_song_plaza")  # 苏拂在出发地

    written = await broker.on_action_completed(
        actor,
        _action("move_to", location="north_frost_workshop"),
        [actor, qianling, sufu],
        game_time=100.0,
    )
    # 应只对千绫写一条
    assert len(written) == 1
    qianling_mem = (await store.get_recent("agent_06", limit=1))[0]
    assert "来到了" in qianling_mem.content
    sufu_recent = await store.get_recent("agent_07", limit=10)
    assert sufu_recent == []


# ============================================================================
#                  Robustness: store write failure shouldn't crash
# ============================================================================


@pytest.mark.asyncio
async def test_broker_swallows_store_errors() -> None:
    """store.insert 抛错时,broker 不应把异常向上抛 — 写不进去就 log,继续 sim。"""

    class _BrokenStore:
        async def insert(self, mem):
            raise RuntimeError("simulated store down")

    broker = PerceptionBroker(memory_store=_BrokenStore())  # type: ignore[arg-type]
    actor = _agent("agent_01")
    observer = _agent("agent_02")
    # 不应 raise
    written = await broker.on_action_completed(
        actor, _action("work", task="x"), [actor, observer], game_time=100.0
    )
    assert written == []  # 没成功写


# ============================================================================
#                   Scheduler integration (broker fires on tick)
# ============================================================================


@pytest.mark.asyncio
async def test_scheduler_calls_broker_on_action_complete(store: MemoryStore) -> None:
    """ActionScheduler 在 tick 中完成 action 时应触发 broker 写 observation。"""
    broker = PerceptionBroker(memory_store=store)
    scheduler = ActionScheduler(perception_broker=broker)
    actor = _agent("agent_01")
    observer = _agent("agent_02")
    scheduler.register_agent(actor)
    scheduler.register_agent(observer)

    # 给 actor 队列一个 60s 的 work 动作
    await scheduler.enqueue("agent_01", _action("work", task="配药"))

    # tick 1:启动 work
    r1 = await scheduler.tick_agent("agent_01", game_time=0.0, dt=0.0)
    assert r1.started_action is not None and r1.started_action.action_type == "work"

    # tick 2:推进到完成 + 触发 broker
    r2 = await scheduler.tick_agent("agent_01", game_time=60.0, dt=60.0)
    assert r2.completed_action is not None and r2.completed_action.action_type == "work"

    # broker 是 fire-and-forget,等所有 background 写入完成
    await scheduler.shutdown()

    # 观察者应有一条 observation
    recent = await store.get_recent("agent_02", limit=10)
    assert len(recent) == 1
    assert recent[0].memory_type == "observation"
    assert "配药" in recent[0].content


@pytest.mark.asyncio
async def test_scheduler_without_broker_works_unchanged(store: MemoryStore) -> None:
    """没注入 broker 时,scheduler 行为与之前完全一致。"""
    scheduler = ActionScheduler()  # 无 broker
    actor = _agent("agent_01")
    observer = _agent("agent_02")
    scheduler.register_agent(actor)
    scheduler.register_agent(observer)
    await scheduler.enqueue("agent_01", _action("work", task="配药"))

    await scheduler.tick_agent("agent_01", game_time=0.0, dt=0.0)
    await scheduler.tick_agent("agent_01", game_time=60.0, dt=60.0)
    await scheduler.shutdown()

    # 观察者不该有任何 observation 记忆
    recent = await store.get_recent("agent_02", limit=10)
    assert recent == []


@pytest.mark.asyncio
async def test_scheduler_move_to_propagates_location_via_broker(
    store: MemoryStore, location_loader: LocationLoader
) -> None:
    """完整路径:scheduler 完成 move_to → broker 应用副作用 → actor.current_location 更新。"""
    broker = PerceptionBroker(memory_store=store, location_loader=location_loader)
    scheduler = ActionScheduler(perception_broker=broker)
    actor = _agent("agent_01", location="lao_song_plaza")
    scheduler.register_agent(actor)
    move = QueuedAction(
        action_type="move_to",
        args={"location": "north_frost_workshop"},
        duration_seconds=30.0,
        source=ActionSource.PLANNER,
    )
    await scheduler.enqueue("agent_01", move)
    await scheduler.tick_agent("agent_01", game_time=0.0, dt=0.0)  # 启动
    await scheduler.tick_agent("agent_01", game_time=30.0, dt=30.0)  # 完成
    await scheduler.shutdown()
    assert actor.current_location == "north_frost_workshop"
