"""DialogueManager / DialogueSession 单测。

不烧真实 API,所有 LLM 调用 mock。覆盖:
- try_start_session 成功/失败路径
- is_agent_busy_with_dialogue 状态跟踪
- _run_session 串行多轮,正确交替 speaker
- [END] 标记提前结束
- memory 写入双方
- event emitter 收 dialogue_started / dialogue_line / dialogue_ended
- shutdown drain
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import pytest
import pytest_asyncio

from src.agent.dialogue import (
    DEFAULT_MAX_TURNS,
    DialogueLine,
    DialogueManager,
    DialogueSession,
)
from src.agent.planning import PersonaProfile
from src.agent.runtime import AgentRuntime
from src.llm.deepseek import LLMResponse, LLMUsage
from src.memory.schema import init_db
from src.memory.store import MemoryStore


# ============================================================================
#                                Mocks
# ============================================================================


@dataclass
class MockLLM:
    """记录 chat() 调用,按预设响应列表返回。"""

    responses: list[str] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)
    _idx: int = 0

    async def chat(self, **kwargs) -> LLMResponse:
        self.calls.append(kwargs)
        if self._idx < len(self.responses):
            content = self.responses[self._idx]
            self._idx += 1
        else:
            content = "(默认台词)"
        return LLMResponse(
            content=content,
            usage=LLMUsage(0, 0, 0, 0, 0.0, 0.0),
            raw={},
        )


class MockPersonaLoader:
    """按 agent_id 返回简化的 PersonaProfile。"""

    def __init__(self, names: dict[str, str]) -> None:
        self._names = names

    def load(self, agent_id: str) -> PersonaProfile:
        return PersonaProfile(
            agent_id=agent_id,
            display_name=self._names.get(agent_id, agent_id),
            gender="?",
            age=30,
            occupation="测试员",
            identity="测试角色",
            appearance="?",
            traits=("测试",),
            personality="测试人格",
            backstory="测试背景",
            speaking_style="测试语气",
            long_term_goal="?",
            mid_term_goal="?",
            short_term_needs="?",
            initial_location="lao_song_plaza",
            typical_locations=(),
            daily_routine="?",
            initial_relationships=(),
            known_secrets="?",
            unknown_to_self="?",
            inner_conflict="?",
            seed_memories=(),
        )


# ============================================================================
#                                Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def store(tmp_path):
    db_path = str(tmp_path / "dialog.db")
    await init_db(db_path)
    return MemoryStore(db_path)


@pytest.fixture
def persona_loader() -> MockPersonaLoader:
    return MockPersonaLoader({"agent_01": "林秋", "agent_02": "阿杏", "agent_03": "早纪"})


@pytest.fixture
def captured_events() -> list[tuple[str, dict]]:
    return []


def _make_agent(agent_id: str, location: str = "lao_song_plaza") -> AgentRuntime:
    return AgentRuntime(agent_id=agent_id, current_location=location)


def _make_manager(
    llm: MockLLM,
    persona_loader: MockPersonaLoader,
    store: MemoryStore,
    captured_events: list[tuple[str, dict]],
    max_turns: int = DEFAULT_MAX_TURNS,
) -> DialogueManager:
    mgr = DialogueManager(
        llm=llm,
        persona_loader=persona_loader,
        memory_store=store,
        model_flash="mock-flash",
        max_turns=max_turns,
    )
    mgr.set_event_emitter(lambda et, p: captured_events.append((et, p)))
    return mgr


async def _drain(mgr: DialogueManager) -> None:
    """等所有内部 session task 跑完。"""
    for _ in range(50):  # 最多 5 秒
        if not mgr._tasks:
            return
        await asyncio.sleep(0.1)


# ============================================================================
#                          start_session / guard
# ============================================================================


@pytest.mark.asyncio
async def test_try_start_session_marks_both_busy(
    persona_loader, store, captured_events
):
    llm = MockLLM(responses=["你好。", "嗯。"])  # 2 句够 max_turns=2
    mgr = _make_manager(llm, persona_loader, store, captured_events, max_turns=2)

    a = _make_agent("agent_01")
    b = _make_agent("agent_02")
    session = mgr.try_start_session(a, b, game_time=100.0)
    assert session is not None
    assert mgr.is_agent_busy_with_dialogue("agent_01") is True
    assert mgr.is_agent_busy_with_dialogue("agent_02") is True
    assert mgr.is_agent_busy_with_dialogue("agent_03") is False

    await _drain(mgr)
    # 跑完后双方解禁
    assert mgr.is_agent_busy_with_dialogue("agent_01") is False
    assert mgr.is_agent_busy_with_dialogue("agent_02") is False


@pytest.mark.asyncio
async def test_try_start_returns_none_when_different_location(
    persona_loader, store, captured_events
):
    llm = MockLLM()
    mgr = _make_manager(llm, persona_loader, store, captured_events)
    a = _make_agent("agent_01", location="lao_song_plaza")
    b = _make_agent("agent_02", location="north_frost_workshop")
    session = mgr.try_start_session(a, b, game_time=100.0)
    assert session is None
    assert mgr.is_agent_busy_with_dialogue("agent_01") is False


@pytest.mark.asyncio
async def test_try_start_returns_none_when_self(
    persona_loader, store, captured_events
):
    llm = MockLLM()
    mgr = _make_manager(llm, persona_loader, store, captured_events)
    a = _make_agent("agent_01")
    assert mgr.try_start_session(a, a, game_time=0.0) is None


@pytest.mark.asyncio
async def test_concurrent_start_for_same_agent_blocked(
    persona_loader, store, captured_events
):
    """agent_01 已在和 agent_02 对话中,agent_03 再来 try → 拒绝。"""
    # 给足够多的预设响应,避免第一场对话过早结束
    llm = MockLLM(responses=["...", "...", "...", "...", "...", "..."])
    mgr = _make_manager(llm, persona_loader, store, captured_events)

    a, b, c = _make_agent("agent_01"), _make_agent("agent_02"), _make_agent("agent_03")
    s1 = mgr.try_start_session(a, b, game_time=0.0)
    assert s1 is not None

    # agent_01 已 busy
    s2 = mgr.try_start_session(a, c, game_time=0.0)
    assert s2 is None
    # agent_02 也 busy
    s3 = mgr.try_start_session(c, b, game_time=0.0)
    assert s3 is None

    await _drain(mgr)


# ============================================================================
#                          turn 推进 + speaker 交替
# ============================================================================


@pytest.mark.asyncio
async def test_speaker_alternates_correctly(
    persona_loader, store, captured_events
):
    """initiator 先开口,然后交替。"""
    llm = MockLLM(responses=["你好阿杏。", "林秋姐。", "今天怎么样?", "还好。"])
    mgr = _make_manager(llm, persona_loader, store, captured_events, max_turns=4)
    a = _make_agent("agent_01")
    b = _make_agent("agent_02")

    mgr.try_start_session(a, b, game_time=100.0)
    await _drain(mgr)

    lines = [e for et, e in captured_events if et == "dialogue_line"]
    assert len(lines) == 4
    assert lines[0]["speaker_id"] == "agent_01"
    assert lines[1]["speaker_id"] == "agent_02"
    assert lines[2]["speaker_id"] == "agent_01"
    assert lines[3]["speaker_id"] == "agent_02"
    assert lines[0]["text"] == "你好阿杏。"


@pytest.mark.asyncio
async def test_end_token_terminates_early(
    persona_loader, store, captured_events
):
    """LLM 输出 [END] 提前结束。"""
    llm = MockLLM(
        responses=[
            "你好。",
            "我们改天再说吧。[END]",
            "这句不该出现",  # max_turns=4 但应在第 2 轮提前结束
        ]
    )
    mgr = _make_manager(llm, persona_loader, store, captured_events, max_turns=4)
    mgr.try_start_session(_make_agent("agent_01"), _make_agent("agent_02"), 0.0)
    await _drain(mgr)

    lines = [e for et, e in captured_events if et == "dialogue_line"]
    assert len(lines) == 2
    # [END] 标记已被剥离
    assert "[END]" not in lines[1]["text"]
    assert "我们改天再说吧" in lines[1]["text"]

    ended = [e for et, e in captured_events if et == "dialogue_ended"]
    assert len(ended) == 1
    assert ended[0]["reason"] == "llm_end_token"
    assert ended[0]["total_turns"] == 2


@pytest.mark.asyncio
async def test_max_turns_reached(persona_loader, store, captured_events):
    llm = MockLLM(responses=["1", "2", "3"])
    mgr = _make_manager(llm, persona_loader, store, captured_events, max_turns=3)
    mgr.try_start_session(_make_agent("agent_01"), _make_agent("agent_02"), 0.0)
    await _drain(mgr)
    ended = [e for et, e in captured_events if et == "dialogue_ended"]
    assert ended[0]["reason"] == "max_turns"
    assert ended[0]["total_turns"] == 3


# ============================================================================
#                              memory 写入
# ============================================================================


@pytest.mark.asyncio
async def test_dialogue_writes_memory_to_both(
    persona_loader, store, captured_events
):
    llm = MockLLM(responses=["你好。", "嗯。"])
    mgr = _make_manager(llm, persona_loader, store, captured_events, max_turns=2)
    mgr.try_start_session(_make_agent("agent_01"), _make_agent("agent_02"), 100.0)
    await _drain(mgr)

    mem_a = await store.get_recent("agent_01", limit=10)
    mem_b = await store.get_recent("agent_02", limit=10)
    assert len(mem_a) == 1
    assert len(mem_b) == 1
    # 双方记忆都包含对方名 + 对话内容
    assert "阿杏" in mem_a[0].content
    assert "你好。" in mem_a[0].content
    assert "林秋" in mem_b[0].content
    assert mem_a[0].memory_type == "observation"
    assert "agent_02" in mem_a[0].related_agents


# ============================================================================
#                            event sequence
# ============================================================================


@pytest.mark.asyncio
async def test_event_sequence(persona_loader, store, captured_events):
    llm = MockLLM(responses=["你好。", "嗯。"])
    mgr = _make_manager(llm, persona_loader, store, captured_events, max_turns=2)
    mgr.try_start_session(_make_agent("agent_01"), _make_agent("agent_02"), 0.0)
    await _drain(mgr)

    types = [et for et, _ in captured_events]
    assert types[0] == "dialogue_started"
    assert types[-1] == "dialogue_ended"
    # 中间应有 2 个 dialogue_line
    assert types.count("dialogue_line") == 2


# ============================================================================
#                                shutdown
# ============================================================================


@pytest.mark.asyncio
async def test_shutdown_cancels_pending(persona_loader, store, captured_events):
    # LLM 故意慢:每次响应 sleep 长一点,这样 session 在 shutdown 时还在跑
    class SlowLLM(MockLLM):
        async def chat(self, **kwargs) -> LLMResponse:
            await asyncio.sleep(1.0)
            return await super().chat(**kwargs)

    llm = SlowLLM(responses=["..."] * 10)
    mgr = _make_manager(llm, persona_loader, store, captured_events, max_turns=10)
    mgr.try_start_session(_make_agent("agent_01"), _make_agent("agent_02"), 0.0)
    # 不等完,立刻 shutdown
    await asyncio.sleep(0.05)
    await mgr.shutdown()
    # 全部 session 应被清理
    assert mgr.is_agent_busy_with_dialogue("agent_01") is False
    assert mgr.is_agent_busy_with_dialogue("agent_02") is False


# ============================================================================
#                       F4.1 try_start_player_session
# ============================================================================


@pytest.mark.asyncio
async def test_player_session_prefills_player_line(persona_loader, store, captured_events):
    """玩家发起对话:玩家 line 立即写入 session.lines + 立即 emit dialogue_line。"""
    llm = MockLLM(responses=["嗯,你早。"])
    mgr = _make_manager(llm, persona_loader, store, captured_events, max_turns=2)

    player = _make_agent("agent_01")
    target = _make_agent("agent_02")
    session = mgr.try_start_player_session(player, target, "你好,阿杏。", 100.0)
    assert session is not None
    assert session.initiator_id == "agent_01"
    assert session.target_id == "agent_02"
    # 玩家 line 立即在 lines 里
    assert len(session.lines) == 1
    assert session.lines[0].speaker_id == "agent_01"
    assert session.lines[0].text == "你好,阿杏。"
    # 事件:dialogue_started + dialogue_line(玩家那一句)
    started_count = sum(1 for et, _ in captured_events if et == "dialogue_started")
    line_count = sum(1 for et, _ in captured_events if et == "dialogue_line")
    assert started_count == 1
    assert line_count == 1
    # session 跑完 → NPC LLM 回复 + dialogue_ended
    await _drain(mgr)
    assert len(session.lines) == 2
    assert session.lines[1].speaker_id == "agent_02"
    assert session.lines[1].text == "嗯,你早。"


@pytest.mark.asyncio
async def test_player_session_rejects_empty_line(persona_loader, store, captured_events):
    """空 / 空白 player_line 应返回 None。"""
    llm = MockLLM()
    mgr = _make_manager(llm, persona_loader, store, captured_events)
    player = _make_agent("agent_01")
    target = _make_agent("agent_02")
    assert mgr.try_start_player_session(player, target, "", 0.0) is None
    assert mgr.try_start_player_session(player, target, "   \n  ", 0.0) is None


@pytest.mark.asyncio
async def test_player_session_rejects_different_location(persona_loader, store, captured_events):
    """玩家和 NPC 在不同场所应返回 None。"""
    llm = MockLLM()
    mgr = _make_manager(llm, persona_loader, store, captured_events)
    player = _make_agent("agent_01", location="lao_song_plaza")
    target = _make_agent("agent_02", location="warm_valley_farm")
    assert mgr.try_start_player_session(player, target, "你好。", 0.0) is None


@pytest.mark.asyncio
async def test_player_session_rejects_when_busy(persona_loader, store, captured_events):
    """玩家或 NPC 已在另一场对话中应返回 None。"""
    llm = MockLLM(responses=["A 回应", "B 回应", "..."])
    mgr = _make_manager(llm, persona_loader, store, captured_events, max_turns=4)
    # 先让 agent_02 进入另一场对话
    a = _make_agent("agent_02")
    c = _make_agent("agent_03")
    mgr.try_start_session(a, c, 0.0)
    # 玩家(01)想找 agent_02 → 应失败
    player = _make_agent("agent_01")
    assert mgr.try_start_player_session(player, a, "你好。", 0.0) is None
    await mgr.shutdown()
