"""Block E 单测:loaders + LLMPlanner(全程 mock LLM,不烧真实 API)。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from src.agent.planning import (
    DailyPlan,
    DailyPlanSlot,
    LLMPlanner,
    LocationLoader,
    PersonaLoader,
    PersonaProfile,
    build_rich_layer_1,
)
from src.agent.runtime import ActionSource, AgentRuntime, QueuedAction, ThinkingReason


# ============================================================================
#                        Fake LLM client + helpers
# ============================================================================


@dataclass
class _FakeUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_hit_tokens: int = 0
    cache_miss_tokens: int = 0
    cost_yuan: float = 0.0
    latency_ms: float = 0.0


@dataclass
class _FakeResponse:
    content: str
    usage: _FakeUsage = None  # type: ignore[assignment]
    raw: dict = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.usage is None:
            self.usage = _FakeUsage()
        if self.raw is None:
            self.raw = {}


class FakeLLM:
    """按调用顺序返回预制 content;记录每次调用的关键参数。"""

    def __init__(self, contents: list[str] | None = None) -> None:
        self.contents = list(contents or [])
        self.calls: list[dict[str, Any]] = []
        self.raise_on_call: BaseException | None = None

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        mode: Any,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> _FakeResponse:
        self.calls.append(
            {
                "model": model,
                "mode": mode,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        if self.raise_on_call is not None:
            raise self.raise_on_call
        if not self.contents:
            return _FakeResponse(content='{"slots": [], "actions": []}')
        return _FakeResponse(content=self.contents.pop(0))


def _build_planner(
    fake_llm: FakeLLM,
    *,
    seconds_per_game_day: float = 86400.0,
) -> LLMPlanner:
    return LLMPlanner(
        llm=fake_llm,  # type: ignore[arg-type]
        memory_store=None,
        persona_loader=PersonaLoader(),
        location_loader=LocationLoader(),
        seconds_per_game_day=seconds_per_game_day,
    )


def _agent(agent_id: str = "agent_01", location: str = "lao_song_plaza") -> AgentRuntime:
    return AgentRuntime(agent_id=agent_id, current_location=location)


# ============================================================================
#                                Loaders
# ============================================================================


def test_persona_loader_loads_real_yaml() -> None:
    loader = PersonaLoader()
    p = loader.load("agent_01")
    assert p.agent_id == "agent_01"
    assert p.display_name == "林秋"
    assert p.occupation == "村医"
    assert p.age == 32
    assert "温和" in p.traits
    assert p.initial_location == "lao_song_plaza"
    # 关系字典已转 sorted tuple of pairs
    rel_keys = [k for k, _ in p.initial_relationships]
    assert "agent_02" in rel_keys


def test_persona_loader_caches_results() -> None:
    loader = PersonaLoader()
    a = loader.load("agent_01")
    b = loader.load("agent_01")
    assert a is b


def test_persona_loader_lists_all_12() -> None:
    loader = PersonaLoader()
    ids = loader.list_agent_ids()
    assert ids == [f"agent_{i:02d}" for i in range(1, 13)]


def test_persona_loader_missing_raises(tmp_path) -> None:
    loader = PersonaLoader(personas_dir=tmp_path)
    with pytest.raises(FileNotFoundError):
        loader.load("agent_99")


def test_location_loader_all_four() -> None:
    loader = LocationLoader()
    locs = loader.all()
    assert set(locs) == {
        "lao_song_plaza",
        "north_frost_workshop",
        "warm_valley_farm",
        "silent_tower_ruins",
    }
    assert locs["lao_song_plaza"].type == "social"
    assert locs["silent_tower_ruins"].type == "liminal"


def test_location_loader_get_unknown_raises() -> None:
    loader = LocationLoader()
    with pytest.raises(KeyError):
        loader.get("nonexistent_location")


# ============================================================================
#                          Layer 1 byte-stability
# ============================================================================


def test_build_rich_layer_1_byte_stable() -> None:
    """同 persona 多次构造产出完全相同字节 → DeepSeek 缓存稳定的前提。"""
    loader = PersonaLoader()
    p = loader.load("agent_01")
    a = build_rich_layer_1(p)
    b = build_rich_layer_1(p)
    assert a == b
    assert "林秋" in a
    assert "村医" in a


def test_build_rich_layer_1_differs_per_agent() -> None:
    loader = PersonaLoader()
    a = build_rich_layer_1(loader.load("agent_01"))
    b = build_rich_layer_1(loader.load("agent_02"))
    assert a != b


# ============================================================================
#                       LLMPlanner — routine path
# ============================================================================


_OK_DAILY = """{
  "slots": [
    {"start_time": "06:00", "end_time": "08:00", "activity": "起床整理工坊", "location": "lao_song_plaza", "notes": ""},
    {"start_time": "08:00", "end_time": "12:00", "activity": "接诊", "location": "lao_song_plaza", "notes": ""},
    {"start_time": "12:00", "end_time": "14:00", "activity": "午饭", "location": "lao_song_plaza", "notes": ""},
    {"start_time": "14:00", "end_time": "18:00", "activity": "调配解药", "location": "lao_song_plaza", "notes": ""},
    {"start_time": "18:00", "end_time": "22:00", "activity": "整理记录", "location": "lao_song_plaza", "notes": ""}
  ]
}"""

_OK_FINE = """{
  "actions": [
    {"action_type": "move_to", "args": {"location": "lao_song_plaza"}, "duration_seconds": 30},
    {"action_type": "work", "args": {"task": "接诊"}, "duration_seconds": 180},
    {"action_type": "observe", "args": {"target": "病人"}, "duration_seconds": 20},
    {"action_type": "rest", "args": {"reason": "稍歇"}, "duration_seconds": 60}
  ]
}"""

_OK_EMERGENCY = """{
  "actions": [
    {"action_type": "move_to", "args": {"location": "lao_song_plaza"}, "duration_seconds": 20},
    {"action_type": "observe", "args": {"target": "事故现场"}, "duration_seconds": 15}
  ]
}"""


@pytest.mark.asyncio
async def test_planner_routine_calls_daily_then_fine() -> None:
    fake = FakeLLM(contents=[_OK_DAILY, _OK_FINE])
    planner = _build_planner(fake)
    actions = await planner.plan_next_actions(
        _agent(),
        ThinkingReason.LOW_WATERMARK,
        {"game_time": 8 * 3600.0},  # day 0, 08:00
    )
    # 两次调用:第 1 次 daily(Pro), 第 2 次 fine(Flash)
    assert len(fake.calls) == 2
    assert fake.calls[0]["model"] == "deepseek-v4-pro"
    assert fake.calls[1]["model"] == "deepseek-v4-flash"
    # 返回 4 个可入队的 QueuedAction
    assert len(actions) == 4
    assert all(isinstance(a, QueuedAction) for a in actions)
    assert all(a.duration_seconds > 0 for a in actions)
    assert all(a.source is ActionSource.PLANNER for a in actions)


@pytest.mark.asyncio
async def test_planner_reuses_daily_within_same_game_day() -> None:
    fake = FakeLLM(contents=[_OK_DAILY, _OK_FINE, _OK_FINE])
    planner = _build_planner(fake)
    # 第 1 次:08:00
    await planner.plan_next_actions(_agent(), ThinkingReason.LOW_WATERMARK, {"game_time": 8 * 3600.0})
    # 第 2 次:14:00 同一天,daily 应复用,只调 fine
    await planner.plan_next_actions(_agent(), ThinkingReason.LOW_WATERMARK, {"game_time": 14 * 3600.0})
    # 期望:1 daily + 2 fine = 3 总调用
    assert len(fake.calls) == 3
    assert fake.calls[0]["model"] == "deepseek-v4-pro"
    assert fake.calls[1]["model"] == "deepseek-v4-flash"
    assert fake.calls[2]["model"] == "deepseek-v4-flash"


@pytest.mark.asyncio
async def test_planner_regenerates_daily_on_new_game_day() -> None:
    fake = FakeLLM(contents=[_OK_DAILY, _OK_FINE, _OK_DAILY, _OK_FINE])
    planner = _build_planner(fake)
    # day 0:08:00
    await planner.plan_next_actions(_agent(), ThinkingReason.LOW_WATERMARK, {"game_time": 8 * 3600.0})
    # day 1:08:00 = 86400 + 8*3600
    await planner.plan_next_actions(
        _agent(), ThinkingReason.LOW_WATERMARK, {"game_time": 86400.0 + 8 * 3600.0}
    )
    # 4 次:daily, fine, daily, fine
    assert len(fake.calls) == 4
    assert fake.calls[2]["model"] == "deepseek-v4-pro"  # 第二个 daily


@pytest.mark.asyncio
async def test_planner_emergency_skips_daily() -> None:
    fake = FakeLLM(contents=[_OK_EMERGENCY])
    planner = _build_planner(fake)
    actions = await planner.plan_next_actions(
        _agent(),
        ThinkingReason.EMERGENCY,
        {"game_time": 14 * 3600.0, "urgent_event": {"summary": "广场上传来惨叫"}},
    )
    assert len(fake.calls) == 1
    assert fake.calls[0]["model"] == "deepseek-v4-flash"
    # 紧急 prompt 必须出现事件描述
    assert "广场上传来惨叫" in fake.calls[0]["messages"][1]["content"]
    assert len(actions) == 2


# ============================================================================
#                     LLMPlanner — fallback / robustness
# ============================================================================


@pytest.mark.asyncio
async def test_planner_fallback_when_llm_raises_on_daily() -> None:
    fake = FakeLLM(contents=[_OK_FINE])  # daily 调用会 raise
    planner = _build_planner(fake)
    # 第一次调用前,把 raise_on_call 设为异常,只让 daily 失败
    raised: list[bool] = [False]

    original = fake.chat

    async def chat_side_effect(**kwargs):
        if not raised[0]:
            raised[0] = True
            raise RuntimeError("simulated daily LLM failure")
        return await original(**kwargs)

    fake.chat = chat_side_effect  # type: ignore[method-assign]

    actions = await planner.plan_next_actions(
        _agent(),
        ThinkingReason.LOW_WATERMARK,
        {"game_time": 8 * 3600.0},
    )
    # daily 失败 → fallback daily plan(单 slot 全天) → fine 仍尝试调用并成功
    assert len(actions) == 4  # _OK_FINE 解出来 4 个


@pytest.mark.asyncio
async def test_planner_fallback_when_fine_returns_garbage() -> None:
    fake = FakeLLM(contents=[_OK_DAILY, "抱歉我不会"])  # fine 解析失败
    planner = _build_planner(fake)
    actions = await planner.plan_next_actions(
        _agent(),
        ThinkingReason.LOW_WATERMARK,
        {"game_time": 8 * 3600.0},
    )
    # fine 解析失败 → 单个 idle 兜底
    assert len(actions) == 1
    assert actions[0].action_type == "idle"
    assert actions[0].duration_seconds > 0


@pytest.mark.asyncio
async def test_planner_drops_invalid_action_entries() -> None:
    """LLM 返回部分坏数据(空 action_type / 0 时长) → 丢弃坏项,保留好项。"""
    bad_then_good = """{
      "actions": [
        {"action_type": "", "duration_seconds": 30},
        {"action_type": "work", "args": {"task": "x"}, "duration_seconds": 60},
        {"action_type": "rest", "duration_seconds": -5}
      ]
    }"""
    fake = FakeLLM(contents=[_OK_DAILY, bad_then_good])
    planner = _build_planner(fake)
    actions = await planner.plan_next_actions(
        _agent(),
        ThinkingReason.LOW_WATERMARK,
        {"game_time": 8 * 3600.0},
    )
    # 1 个 work 保留;空 action_type 丢弃;负 duration 被规整为 1.0 仍保留
    types = [a.action_type for a in actions]
    assert "work" in types
    assert "rest" in types
    assert "" not in types
    assert all(a.duration_seconds > 0 for a in actions)


@pytest.mark.asyncio
async def test_planner_emergency_fallback_on_garbage() -> None:
    fake = FakeLLM(contents=["完全胡说八道"])
    planner = _build_planner(fake)
    actions = await planner.plan_next_actions(
        _agent(),
        ThinkingReason.EMERGENCY,
        {"game_time": 0.0, "urgent_event": {"summary": "test"}},
    )
    assert len(actions) == 1
    assert actions[0].action_type == "observe"


# ============================================================================
#                       Slot finding (time → slot mapping)
# ============================================================================


def test_find_current_slot_within_range() -> None:
    fake = FakeLLM()
    planner = _build_planner(fake)
    daily = DailyPlan(
        agent_id="x",
        game_day=0,
        slots=[
            DailyPlanSlot(start_time="06:00", end_time="08:00", activity="A", location=""),
            DailyPlanSlot(start_time="08:00", end_time="12:00", activity="B", location=""),
            DailyPlanSlot(start_time="12:00", end_time="22:00", activity="C", location=""),
        ],
    )
    # 09:30 → B
    slot = planner._find_current_slot(daily, 9.5 * 3600.0)
    assert slot.activity == "B"


def test_find_current_slot_after_last_returns_latest_started() -> None:
    fake = FakeLLM()
    planner = _build_planner(fake)
    daily = DailyPlan(
        agent_id="x",
        game_day=0,
        slots=[
            DailyPlanSlot(start_time="06:00", end_time="08:00", activity="A", location=""),
            DailyPlanSlot(start_time="08:00", end_time="22:00", activity="B", location=""),
        ],
    )
    # 23:00:超过所有 end_time;选 start_time<=23:00 中最晚的(B)
    slot = planner._find_current_slot(daily, 23 * 3600.0)
    assert slot.activity == "B"


# ============================================================================
#                Prompt structure (cache-friendly Layer 0+1)
# ============================================================================


# ============================================================================
#                  End-to-end:LLMPlanner ↔ ActionScheduler
# ============================================================================


@pytest.mark.asyncio
async def test_planner_plugs_into_scheduler_and_fills_queue() -> None:
    """LLMPlanner 满足 PlanProvider Protocol → 直接挂到 scheduler 上跑。
    Scheduler tick 时队列空 → 触发思考 → 收割 LLMPlanner 返回的 actions。
    """
    from src.agent.scheduler import ActionScheduler

    fake = FakeLLM(contents=[_OK_DAILY, _OK_FINE])
    planner = _build_planner(fake)
    scheduler = ActionScheduler(planner=planner)
    agent = _agent()
    scheduler.register_agent(agent)

    # Tick 1:队列空 → 触发思考。scheduler 同时塞一个 2s fallback idle 占位(默认 fallback_idle_seconds=2.0)。
    tick1 = await scheduler.tick_agent(agent.agent_id, game_time=8 * 3600.0, dt=0.0)
    assert tick1.thinking_started
    assert tick1.fallback_action is not None  # 占位 idle
    assert agent.current_action is tick1.fallback_action

    # 等思考完成(asyncio task 在我们的 sync fake 上几乎立刻 done)
    if agent.pending_thinking is not None:
        await agent.pending_thinking

    # Tick 2:dt=2.0 推完 fallback → 收割思考结果 → popleft 真实动作启动
    tick2 = await scheduler.tick_agent(agent.agent_id, game_time=8 * 3600.0 + 2.0, dt=2.0)
    assert tick2.thinking_completed
    assert len(tick2.appended_actions) == 4
    assert tick2.completed_action is not None  # fallback 完成
    assert tick2.started_action is not None
    assert tick2.started_action.action_type == "move_to"
    # 队列已 popleft 一个 → 还剩 3 个
    assert len(agent.action_queue) == 3

    await scheduler.shutdown()


@pytest.mark.asyncio
async def test_planner_prompt_has_layer_0_and_1_in_system() -> None:
    """system message 必须以 LAYER_0_SYSTEM 开头,后接 Layer 1。
    Layer 2/3 必须在 user message。这是缓存命中的结构前提。
    """
    fake = FakeLLM(contents=[_OK_DAILY, _OK_FINE])
    planner = _build_planner(fake)
    await planner.plan_next_actions(_agent(), ThinkingReason.LOW_WATERMARK, {"game_time": 8 * 3600.0})

    from src.llm.prompt_builder import PromptBuilder

    daily_msgs = fake.calls[0]["messages"]
    assert daily_msgs[0]["role"] == "system"
    assert daily_msgs[0]["content"].startswith(PromptBuilder.LAYER_0_SYSTEM)
    assert "【你的人格设定】" in daily_msgs[0]["content"]
    assert daily_msgs[1]["role"] == "user"
    assert "【当前情境】" in daily_msgs[1]["content"]
    assert "【当前任务】" in daily_msgs[1]["content"]
