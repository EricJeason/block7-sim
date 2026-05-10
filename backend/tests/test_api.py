"""HTTP 路由 + WebSocket 单测。

不走 main.py 的 lifespan(避免依赖真实 DeepSeek key);
手工组装一个 FastAPI app + 注入 SimEngine 到 app.state。
"""
from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.agent.perception import PerceptionBroker
from src.agent.planning import LocationLoader, PersonaLoader
from src.agent.runtime import ActionSource, QueuedAction
from src.agent.scheduler import ActionScheduler
from src.api.routes import router as api_router
from src.api.websocket import router as ws_router
from src.memory.schema import init_db
from src.memory.store import Memory, MemoryStore
from src.sim import SimEngine


# ============================================================================
#                               Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def engine(tmp_path) -> SimEngine:
    db_path = str(tmp_path / "api.db")
    await init_db(db_path)
    store = MemoryStore(db_path)
    persona_loader = PersonaLoader()
    location_loader = LocationLoader()
    broker = PerceptionBroker(
        memory_store=store,
        persona_loader=persona_loader,
        location_loader=location_loader,
    )
    scheduler = ActionScheduler(memory_store=store, perception_broker=broker)
    eng = SimEngine(
        scheduler=scheduler,
        memory_store=store,
        persona_loader=persona_loader,
        location_loader=location_loader,
        agent_ids=["agent_01", "agent_02"],
    )
    await eng.start(run_loop=False)
    return eng


@pytest.fixture
def app_with_engine(engine: SimEngine) -> FastAPI:
    """构造带 sim_engine 的 FastAPI app,跳过 main.py lifespan。"""
    app = FastAPI()
    app.include_router(api_router)
    app.include_router(ws_router)
    app.state.sim_engine = engine
    return app


@pytest.fixture
def client(app_with_engine: FastAPI) -> TestClient:
    return TestClient(app_with_engine)


# ============================================================================
#                            HTTP /world
# ============================================================================


def test_world_returns_locations_and_agents(client: TestClient) -> None:
    r = client.get("/world")
    assert r.status_code == 200
    data = r.json()
    assert data["time_scale"] == 60.0
    assert len(data["locations"]) == 4
    assert len(data["agents"]) == 2
    loc_ids = {loc["id"] for loc in data["locations"]}
    assert "lao_song_plaza" in loc_ids
    assert "silent_tower_ruins" in loc_ids


def test_world_503_when_no_engine_attached() -> None:
    """没挂 sim_engine 时返回 503,而不是崩溃。"""
    bare_app = FastAPI()
    bare_app.include_router(api_router)
    with TestClient(bare_app) as c:
        r = c.get("/world")
        assert r.status_code == 503


# ============================================================================
#                            HTTP /agents
# ============================================================================


def test_list_agents(client: TestClient) -> None:
    r = client.get("/agents")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    ids = {a["agent_id"] for a in data}
    assert ids == {"agent_01", "agent_02"}


# ============================================================================
#                       HTTP /agent/{id}/state
# ============================================================================


def test_get_agent_state_ok(client: TestClient) -> None:
    r = client.get("/agent/agent_01/state")
    assert r.status_code == 200
    data = r.json()
    assert data["agent_id"] == "agent_01"
    assert data["persona_name"] == "林秋"
    assert data["current_location"] == "lao_song_plaza"


def test_get_agent_state_404(client: TestClient) -> None:
    r = client.get("/agent/agent_99/state")
    assert r.status_code == 404


# ============================================================================
#                       HTTP /agent/{id}/memories
# ============================================================================


@pytest.mark.asyncio
async def test_get_agent_memories(engine: SimEngine, app_with_engine: FastAPI) -> None:
    # 先手动写两条 memory
    for i, importance in enumerate([5, 3]):
        await engine.memory_store.insert(
            Memory(
                memory_id=None,
                agent_id="agent_01",
                memory_type="observation",
                content=f"测试记忆 {i}",
                importance=importance,
                game_time=float(i * 10),
                real_time=0.0,
                location="lao_song_plaza",
                related_agents=[],
                keywords=["测试"],
            )
        )
    with TestClient(app_with_engine) as client:
        r = client.get("/agent/agent_01/memories?limit=10")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 2
        # game_time DESC → 最新的(i=1)在前
        assert data[0]["content"] == "测试记忆 1"


def test_get_memories_404_for_unknown_agent(client: TestClient) -> None:
    r = client.get("/agent/agent_99/memories")
    assert r.status_code == 404


# ============================================================================
#                            WebSocket /ws/sim
# ============================================================================


def test_ws_hello_on_connect(client: TestClient) -> None:
    """连上去应立即收到 hello 事件。"""
    with client.websocket_connect("/ws/sim") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "hello"
        assert msg["payload"]["agent_count"] == 2
        assert msg["payload"]["time_scale"] == 60.0


def test_ws_ping_pong(client: TestClient) -> None:
    with client.websocket_connect("/ws/sim") as ws:
        ws.receive_json()  # 跳过 hello
        ws.send_text("ping")
        msg = ws.receive_json()
        assert msg["type"] == "pong"


@pytest.mark.asyncio
async def test_ws_receives_tick_events(
    engine: SimEngine, app_with_engine: FastAPI
) -> None:
    """订阅 → 手动塞一个 action 进队列 → tick → WS 应收到 action_started 事件。"""
    # 给 agent_01 队列里加一个 work 动作
    await engine.scheduler.enqueue(
        "agent_01",
        QueuedAction(
            action_type="work",
            args={"task": "测试"},
            duration_seconds=60.0,
            source=ActionSource.PLANNER,
        ),
    )

    with TestClient(app_with_engine) as client:
        with client.websocket_connect("/ws/sim") as ws:
            ws.receive_json()  # hello
            # 同步内手动 tick(异步调度借 asyncio.run 不行 — 用 portal 调用)
            from anyio.from_thread import start_blocking_portal

            with start_blocking_portal() as portal:
                portal.call(engine.tick_once, 0.0)

            # 应当收到 action_started for agent_01
            seen_types = []
            for _ in range(5):
                msg = ws.receive_json()
                seen_types.append((msg["type"], msg.get("agent_id")))
                if msg["type"] == "action_started" and msg["agent_id"] == "agent_01":
                    assert msg["payload"]["action_type"] == "work"
                    return
            pytest.fail(f"未收到 action_started for agent_01, 只看到: {seen_types}")
