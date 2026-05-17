"""ReflectionRunner + MemoryCompressor + SimEngine 跨日触发 单测。

不烧真实 API,LLM 全 mock。覆盖:
- MemoryStore 新增的 get_in_time_range / get_older_than
- ReflectionRunner.run_for_agent 解析 JSON + 写库 + 空 source 跳过
- MemoryCompressor 1-7 天合并 + 7 天前 archive
- SimEngine 跨日检测 + 调度并行任务
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import pytest
import pytest_asyncio

from src.agent.dialogue import DialogueManager  # noqa: F401 (用于 SimEngine 完整调线)
from src.agent.perception import PerceptionBroker
from src.agent.planning import LocationLoader, PersonaProfile
from src.agent.reflection import ReflectionRunner
from src.agent.scheduler import ActionScheduler
from src.llm.deepseek import LLMResponse, LLMUsage
from src.memory.compression import MemoryCompressor
from src.memory.schema import init_db
from src.memory.store import Memory, MemoryStore
from src.sim import SimEngine


SECONDS_PER_DAY = 86400.0


# ============================================================================
#                                Mocks
# ============================================================================


@dataclass
class MockLLM:
    """记录 chat 调用,按预设响应列表返回。"""

    responses: list[str] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)
    cost_per_call: float = 0.01
    _idx: int = 0

    async def chat(self, **kwargs) -> LLMResponse:
        self.calls.append(kwargs)
        if self._idx < len(self.responses):
            content = self.responses[self._idx]
            self._idx += 1
        else:
            content = '{"reflections": []}'
        return LLMResponse(
            content=content,
            usage=LLMUsage(0, 0, 0, 0, self.cost_per_call, 0.0),
            raw={},
        )


class MockPersonaLoader:
    def __init__(self, names: dict[str, str]) -> None:
        self._names = names

    def load(self, agent_id: str) -> PersonaProfile:
        return PersonaProfile(
            agent_id=agent_id,
            display_name=self._names.get(agent_id, agent_id),
            gender="?",
            age=30,
            occupation="测试员",
            identity="测试",
            appearance="?",
            traits=(),
            personality="",
            backstory="",
            speaking_style="",
            long_term_goal="",
            mid_term_goal="",
            short_term_needs="",
            initial_location="lao_song_plaza",
            typical_locations=(),
            daily_routine="",
            initial_relationships=(),
            known_secrets="",
            unknown_to_self="",
            inner_conflict="",
            seed_memories=(),
        )

    def list_agent_ids(self) -> list[str]:
        return list(self._names.keys())


# ============================================================================
#                                Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def store(tmp_path):
    db_path = str(tmp_path / "reflect.db")
    await init_db(db_path)
    return MemoryStore(db_path)


@pytest.fixture
def persona_loader() -> MockPersonaLoader:
    return MockPersonaLoader({"agent_01": "林秋", "agent_02": "阿杏"})


async def _insert(
    store: MemoryStore,
    agent_id: str,
    memory_type: str,
    content: str,
    importance: int,
    game_time: float,
) -> Memory:
    mem = Memory(
        memory_id=None,
        agent_id=agent_id,
        memory_type=memory_type,
        content=content,
        importance=importance,
        game_time=game_time,
        real_time=time.time(),
        location=None,
        related_agents=[],
        keywords=[],
    )
    await store.insert(mem)
    return mem


# ============================================================================
#                          MemoryStore 新查询接口
# ============================================================================


@pytest.mark.asyncio
async def test_get_in_time_range_filters_by_importance(store):
    # 当日(0-86400s)有 3 条,importance 5/3/7
    await _insert(store, "a", "observation", "x1", 5, 1000)
    await _insert(store, "a", "observation", "x2", 3, 2000)
    await _insert(store, "a", "observation", "x3", 7, 3000)
    # 次日 1 条
    await _insert(store, "a", "observation", "y1", 9, SECONDS_PER_DAY + 1000)

    result = await store.get_in_time_range(
        "a", 0, SECONDS_PER_DAY, min_importance=4
    )
    assert len(result) == 2  # imp 5 和 7,不要 3
    assert {m.content for m in result} == {"x1", "x3"}


@pytest.mark.asyncio
async def test_get_in_time_range_filters_by_type(store):
    await _insert(store, "a", "observation", "obs", 5, 1000)
    await _insert(store, "a", "plan", "plan1", 5, 2000)
    await _insert(store, "a", "reflection", "refl", 5, 3000)

    result = await store.get_in_time_range(
        "a", 0, SECONDS_PER_DAY, memory_types=["observation", "plan"]
    )
    assert len(result) == 2
    assert {m.content for m in result} == {"obs", "plan1"}


@pytest.mark.asyncio
async def test_get_older_than_excludes_reflections(store):
    await _insert(store, "a", "observation", "old1", 3, 1000)
    await _insert(store, "a", "reflection", "old_refl", 5, 2000)
    await _insert(store, "a", "observation", "old_high", 8, 3000)

    cutoff = SECONDS_PER_DAY * 7
    # 拉 importance < 7 + 非 reflection
    result = await store.get_older_than(
        "a", cutoff, max_importance=6, exclude_types=["reflection"]
    )
    assert len(result) == 1
    assert result[0].content == "old1"


# ============================================================================
#                            ReflectionRunner
# ============================================================================


@pytest.mark.asyncio
async def test_reflection_skips_empty_source(store, persona_loader):
    """source memory 为 0 → 不调 LLM,直接返回空 result。"""
    llm = MockLLM()
    runner = ReflectionRunner(llm, persona_loader, store)
    result = await runner.run_for_agent("agent_01", game_day=0, game_time=SECONDS_PER_DAY)
    assert result.reflections == []
    assert result.source_count == 0
    assert len(llm.calls) == 0  # 没调 LLM


@pytest.mark.asyncio
async def test_reflection_generates_and_writes(store, persona_loader):
    # 插 3 条当日 imp ≥ 4 的 memory
    await _insert(store, "agent_01", "observation", "今天去了医工坊", 5, 30000)
    await _insert(store, "agent_01", "observation", "见到了阿杏", 7, 50000)
    await _insert(store, "agent_01", "plan", "下午配药", 4, 70000)

    llm = MockLLM(
        responses=[
            '{"reflections": ['
            '{"content": "阿杏今天眼神比平时空", "importance": 7},'
            '{"content": "新配的解药剂量可能要调", "importance": 5}'
            ']}'
        ],
        cost_per_call=0.024,
    )
    runner = ReflectionRunner(llm, persona_loader, store, min_importance=4)
    result = await runner.run_for_agent(
        "agent_01", game_day=0, game_time=SECONDS_PER_DAY
    )
    assert result.source_count == 3
    assert len(result.reflections) == 2
    assert result.cost_yuan == 0.024
    # 写库验证
    stored = await store.get_recent("agent_01", limit=20, memory_types=["reflection"])
    assert len(stored) == 2
    contents = {m.content for m in stored}
    assert "阿杏今天眼神比平时空" in contents


@pytest.mark.asyncio
async def test_reflection_parses_bad_json_gracefully(store, persona_loader):
    llm = MockLLM(responses=["这不是 JSON,只是闲聊。"])
    await _insert(store, "agent_01", "observation", "x", 5, 30000)
    runner = ReflectionRunner(llm, persona_loader, store)
    result = await runner.run_for_agent("agent_01", game_day=0, game_time=SECONDS_PER_DAY)
    assert result.reflections == []  # parse fail → 空


@pytest.mark.asyncio
async def test_reflection_clamps_importance(store, persona_loader):
    llm = MockLLM(
        responses=[
            '{"reflections": ['
            '{"content": "a", "importance": 999},'
            '{"content": "b", "importance": -3},'
            '{"content": "c", "importance": "not_int"}'
            ']}'
        ]
    )
    await _insert(store, "agent_01", "observation", "x", 5, 30000)
    runner = ReflectionRunner(llm, persona_loader, store)
    result = await runner.run_for_agent("agent_01", game_day=0, game_time=SECONDS_PER_DAY)
    importances = [m.importance for m in result.reflections]
    assert importances == [10, 1, 5]  # clamp 到 1-10,非整数兜底 5


# ============================================================================
#                           MemoryCompressor
# ============================================================================


@pytest.mark.asyncio
async def test_compression_24h_keeps_all(store, persona_loader):
    """24 小时内的全保留,不进任何压缩动作。"""
    # current = day 3 = 3 * 86400 = 259200
    current = 3 * SECONDS_PER_DAY
    await _insert(store, "agent_01", "observation", "very_recent_low", 2, current - 1000)

    llm = MockLLM()
    compressor = MemoryCompressor(store, llm, persona_loader=persona_loader)
    result = await compressor.compress_old_memories("agent_01", current)
    assert result.merged_count == 0
    assert result.archived_count == 0
    # 原 memory 仍未 compressed
    recent = await store.get_recent("agent_01", limit=10)
    assert len(recent) == 1


@pytest.mark.asyncio
async def test_compression_merges_mid_zone(store, persona_loader):
    """1-7 天前 importance ≤ 4 的 memory → 合并为 summary reflection。"""
    current = 5 * SECONDS_PER_DAY  # day 5
    # 2 天前两条 imp=3
    await _insert(store, "agent_01", "observation", "琐事1", 3, 3 * SECONDS_PER_DAY + 100)
    await _insert(store, "agent_01", "observation", "琐事2", 2, 3 * SECONDS_PER_DAY + 200)
    # 高 importance 不应被合并
    await _insert(store, "agent_01", "observation", "重要", 8, 3 * SECONDS_PER_DAY + 300)

    llm = MockLLM(responses=["最近几天我处理了一些琐碎事情,没什么大事发生。"])
    compressor = MemoryCompressor(store, llm, persona_loader=persona_loader)
    result = await compressor.compress_old_memories("agent_01", current)
    assert result.merged_count == 2  # 琐事1+2 被合并
    assert result.summary_inserted is True

    # summary 是 reflection 类型,importance=4
    refls = await store.get_recent("agent_01", limit=10, memory_types=["reflection"])
    assert len(refls) == 1
    assert refls[0].importance == 4
    assert "日常摘要" in refls[0].content

    # 高 importance 仍存活
    all_obs = await store.get_recent("agent_01", limit=10, memory_types=["observation"])
    contents = {m.content for m in all_obs}
    assert "重要" in contents
    # 琐事1+2 已 compressed,默认 get_recent 排除
    assert "琐事1" not in contents


@pytest.mark.asyncio
async def test_compression_archives_deep_zone(store, persona_loader):
    """7 天前非 reflection 且 importance < 7 → 直接 compressed,不合并。"""
    current = 10 * SECONDS_PER_DAY
    # 8 天前
    await _insert(store, "agent_01", "observation", "deep_low", 4, 2 * SECONDS_PER_DAY)
    await _insert(store, "agent_01", "observation", "deep_high", 8, 2 * SECONDS_PER_DAY + 100)
    await _insert(store, "agent_01", "reflection", "deep_refl", 5, 2 * SECONDS_PER_DAY + 200)

    llm = MockLLM()  # 不会调 LLM(没有 mid_zone)
    compressor = MemoryCompressor(store, llm, persona_loader=persona_loader)
    result = await compressor.compress_old_memories("agent_01", current)
    # mid_zone 有 deep_low(importance=4),但 8天前 > 7 天阈值, 不在 1-7 天窗口
    # 实际上 1-7 天前 = current-7day 到 current-1day = day 3-9
    # 8 天前(day 2)不在 1-7 天窗口里,所以 mid_zone 空
    # deep_zone: 7 天前 = day 0-3, day 2 在其中。deep_low (imp=4) 被 archive
    assert result.merged_count == 0  # 没合并
    assert result.archived_count == 1  # deep_low 被 archive

    # deep_high(imp=8) 和 deep_refl 仍存活
    survivors = await store.get_recent("agent_01", limit=20, exclude_compressed=True)
    contents = {m.content for m in survivors}
    assert "deep_high" in contents
    assert "deep_refl" in contents
    assert "deep_low" not in contents


# ============================================================================
#                           SimEngine 跨日触发
# ============================================================================


@pytest.fixture
def location_loader() -> LocationLoader:
    return LocationLoader()


@pytest_asyncio.fixture
async def cross_day_engine(store, persona_loader, location_loader):
    """SimEngine + Mock LLM + 2 agent,time_scale 大让 tick_once 跨日。"""
    broker = PerceptionBroker(memory_store=store, persona_loader=persona_loader)
    scheduler = ActionScheduler(memory_store=store, perception_broker=broker)

    llm = MockLLM(
        responses=['{"reflections": [{"content": "今天累了", "importance": 5}]}'] * 4
    )
    runner = ReflectionRunner(llm, persona_loader, store)
    compressor = MemoryCompressor(store, llm, persona_loader=persona_loader)

    engine = SimEngine(
        scheduler=scheduler,
        memory_store=store,
        persona_loader=persona_loader,
        location_loader=location_loader,
        time_scale=SECONDS_PER_DAY * 2,  # 1 真实秒 = 2 游戏日,1 次 tick_once(dt=1) → 跨 2 天
        tick_interval_seconds=0.05,
        agent_ids=["agent_01", "agent_02"],
        reflection_runner=runner,
        compressor=compressor,
    )
    await engine.start(run_loop=False)
    engine._mock_llm = llm  # type: ignore  方便测试读
    return engine


@pytest.mark.asyncio
async def test_no_reflection_on_first_tick_within_day(
    store, persona_loader, location_loader
):
    """tick 没跨日时不触发反思。"""
    broker = PerceptionBroker(memory_store=store, persona_loader=persona_loader)
    scheduler = ActionScheduler(memory_store=store, perception_broker=broker)
    llm = MockLLM()
    runner = ReflectionRunner(llm, persona_loader, store)
    engine = SimEngine(
        scheduler=scheduler,
        memory_store=store,
        persona_loader=persona_loader,
        location_loader=location_loader,
        time_scale=60.0,  # 1 现实秒 = 60 游戏秒,远不到一天
        tick_interval_seconds=0.05,
        agent_ids=["agent_01"],
        reflection_runner=runner,
    )
    await engine.start(run_loop=False)
    await engine.tick_once(dt_real=1.0)  # game_time = 60
    # 反思任务集合应为空
    assert len(engine._reflection_tasks) == 0
    assert len(llm.calls) == 0


@pytest.mark.asyncio
async def test_reflection_triggers_on_day_crossing(cross_day_engine):
    """tick 跨过一天 → 后台 reflection task 启动。"""
    q = cross_day_engine.subscribe()
    await cross_day_engine.tick_once(dt_real=1.0)  # game_time = 2 day
    # 等后台 reflection 跑完
    await asyncio.sleep(0.5)
    # 应收到 daily_reflection_started + completed
    types = []
    while not q.empty():
        ev = q.get_nowait()
        types.append(ev.type)
    assert "daily_reflection_started" in types
    assert "daily_reflection_completed" in types


@pytest.mark.asyncio
async def test_reflection_disabled_when_flag_off(
    store, persona_loader, location_loader
):
    broker = PerceptionBroker(memory_store=store, persona_loader=persona_loader)
    scheduler = ActionScheduler(memory_store=store, perception_broker=broker)
    llm = MockLLM()
    runner = ReflectionRunner(llm, persona_loader, store)
    engine = SimEngine(
        scheduler=scheduler,
        memory_store=store,
        persona_loader=persona_loader,
        location_loader=location_loader,
        time_scale=SECONDS_PER_DAY * 2,
        tick_interval_seconds=0.05,
        agent_ids=["agent_01"],
        reflection_runner=runner,
        enable_daily_reflection=False,  # ← 关掉
    )
    await engine.start(run_loop=False)
    await engine.tick_once(dt_real=1.0)
    await asyncio.sleep(0.3)
    assert len(llm.calls) == 0  # 关了就不调 LLM
