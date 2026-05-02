"""Memory CRUD + 检索单元测试。不调用真实 LLM。"""
from __future__ import annotations

import time

import pytest
import pytest_asyncio

from src.memory.schema import init_db
from src.memory.store import Memory, MemoryStore


@pytest_asyncio.fixture
async def store(tmp_path):
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)
    return MemoryStore(db_path)


async def test_insert_and_get(store: MemoryStore) -> None:
    m = Memory(
        memory_id=None,
        agent_id="a1",
        memory_type="observation",
        content="今天买了一斤苹果",
        importance=4,
        game_time=100.0,
        real_time=time.time(),
        location="水果店",
        keywords=["买", "苹果"],
    )
    mid = await store.insert(m)
    assert mid > 0

    fetched = await store.get_by_id(mid)
    assert fetched is not None
    assert fetched.content == "今天买了一斤苹果"
    assert fetched.importance == 4
    assert fetched.location == "水果店"
    assert "苹果" in fetched.keywords


async def test_get_recent_orders_by_time(store: MemoryStore) -> None:
    for i in range(5):
        await store.insert(
            Memory(
                memory_id=None,
                agent_id="a1",
                memory_type="observation",
                content=f"事件 {i}",
                importance=5,
                game_time=float(i * 10),
                real_time=time.time(),
                location="X",
                keywords=[f"事件{i}"],
            )
        )
    recent = await store.get_recent("a1", limit=3)
    assert len(recent) == 3
    # 应按 game_time DESC,即 i=4, 3, 2
    assert recent[0].content == "事件 4"
    assert recent[1].content == "事件 3"
    assert recent[2].content == "事件 2"


async def test_search_keyword_match(store: MemoryStore) -> None:
    await store.insert(
        Memory(
            memory_id=None,
            agent_id="a1",
            memory_type="observation",
            content="买了苹果",
            importance=5,
            game_time=100.0,
            real_time=time.time(),
            location="X",
            keywords=["苹果", "购买"],
        )
    )
    await store.insert(
        Memory(
            memory_id=None,
            agent_id="a1",
            memory_type="observation",
            content="散步",
            importance=2,
            game_time=99.0,
            real_time=time.time(),
            location="Y",
            keywords=["散步"],
        )
    )
    results = await store.search(
        "a1", keywords=["苹果"], current_game_time=100.0, top_k=5
    )
    assert len(results) == 1
    assert "苹果" in results[0].memory.content


async def test_search_time_decay(store: MemoryStore) -> None:
    """同样关键词 + 同样重要性,新 memory 应排在前(时间衰减压制旧 memory)。"""
    await store.insert(
        Memory(
            memory_id=None,
            agent_id="a1",
            memory_type="observation",
            content="老的苹果记忆",
            importance=5,
            game_time=0.0,
            real_time=time.time(),
            location="X",
            keywords=["苹果"],
        )
    )
    await store.insert(
        Memory(
            memory_id=None,
            agent_id="a1",
            memory_type="observation",
            content="新的苹果记忆",
            importance=5,
            game_time=99.0,
            real_time=time.time(),
            location="X",
            keywords=["苹果"],
        )
    )
    results = await store.search(
        "a1", keywords=["苹果"], current_game_time=100.0, top_k=5
    )
    assert results[0].memory.content == "新的苹果记忆"


async def test_compressed_excluded_by_default(store: MemoryStore) -> None:
    mid = await store.insert(
        Memory(
            memory_id=None,
            agent_id="a1",
            memory_type="observation",
            content="将被压缩",
            importance=5,
            game_time=100.0,
            real_time=time.time(),
            location="X",
            keywords=["压缩"],
        )
    )
    await store.mark_compressed([mid])
    recent = await store.get_recent("a1", limit=10)
    assert len(recent) == 0
    assert await store.count("a1") == 0


async def test_keyword_auto_extract(store: MemoryStore) -> None:
    """如果 keywords 为空,应从 content 自动提取中文片段。"""
    m = Memory(
        memory_id=None,
        agent_id="a1",
        memory_type="observation",
        content="李明在杂货店买了苹果",
        importance=5,
        game_time=100.0,
        real_time=time.time(),
        location="杂货店",
        keywords=[],
    )
    mid = await store.insert(m)
    fetched = await store.get_by_id(mid)
    assert fetched is not None
    # 至少抽出某个连续中文片段(整句作为一个 chunk 也算通过)
    assert len(fetched.keywords) >= 1
    joined = " ".join(fetched.keywords)
    assert any(token in joined for token in ["李明", "杂货店", "苹果"])


async def test_importance_scorer_robust_to_garbage_response() -> None:
    """ImportanceScorer 在 LLM 返回非 JSON 时应兜底为全 5。"""
    from src.memory.store import ImportanceScorer

    class _FakeUsage:
        def __init__(self) -> None:
            self.input_tokens = 0
            self.output_tokens = 0
            self.cache_hit_tokens = 0
            self.cache_miss_tokens = 0
            self.cost_yuan = 0.0
            self.latency_ms = 0.0

    class _FakeResponse:
        def __init__(self, content: str) -> None:
            self.content = content
            self.usage = _FakeUsage()
            self.raw: dict = {}

    class _FakeClient:
        def __init__(self, content: str) -> None:
            self._content = content

        async def chat(self, **_kw):  # noqa: ANN003
            return _FakeResponse(self._content)

    # Case 1: 返回乱码,无 JSON
    scorer = ImportanceScorer(_FakeClient("抱歉我不会"), model="deepseek-v4-flash")
    assert await scorer.score(["a", "b", "c"]) == [5, 5, 5]

    # Case 2: JSON 数组长度不对 → 截断 / 补齐
    scorer = ImportanceScorer(_FakeClient("结果是 [3, 7]"), model="deepseek-v4-flash")
    assert await scorer.score(["a", "b", "c", "d"]) == [3, 7, 5, 5]

    # Case 3: 越界值 → clamp 到 [1, 10]
    scorer = ImportanceScorer(_FakeClient("[0, 11, 5]"), model="deepseek-v4-flash")
    assert await scorer.score(["a", "b", "c"]) == [1, 10, 5]
