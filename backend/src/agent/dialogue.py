"""Block I:对话状态机。

参见 v0.2 §1.5。对话不走 Action Queue,是特殊模式:
1. agent A 完成 talk_to(B) action,且 B 在同场所 → 触发 DialogueSession
2. 双方进入对话状态(scheduler 看到他们 in_dialogue 就跳过 action 推进)
3. DialogueManager 后台串行调 LLM,逐句生成台词,每句立刻发 WS 事件
4. 达到 max_turns 或 LLM 输出 [END] → 结束
5. 整段对话写入双方 memory(observation),双方恢复 Action Queue

Prompt 复用 4 层结构(Layer 0 暮谷镇世界观 + Layer 1 当前 speaker 的 PersonaProfile
+ Layer 2 对方简介 + 历史对话 + Layer 3 任务"接下一句话")。
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable
from uuid import uuid4

from src.agent.planning import PersonaLoader, build_rich_layer_1
from src.agent.runtime import AgentRuntime
from src.llm.deepseek import DeepSeekClient, ThinkMode
from src.llm.prompt_builder import PromptBuilder
from src.memory.store import Memory, MemoryStore

logger = logging.getLogger(__name__)


# 最多轮次(双方加起来):6 轮 ≈ 6 次 LLM Flash 调用 ≈ ¥0.012/场
DEFAULT_MAX_TURNS = 6

# LLM 输出包含此标记 → 视为对方让对话结束
_END_TOKEN = "[END]"

# 提取 JSON-less 纯文本台词(去掉前后引号、空白)
_QUOTE_RE = re.compile(r'^[「『"\'\s]+|[」』"\'\s]+$')


# ============================================================================
#                              Data classes
# ============================================================================


@dataclass
class DialogueLine:
    speaker_id: str
    text: str
    game_time: float
    turn_idx: int  # session 内第几句(0-indexed)


@dataclass
class DialogueSession:
    """两个 agent 间的对话状态。"""

    session_id: str
    initiator_id: str
    target_id: str
    location: str
    started_at_game_time: float
    max_turns: int = DEFAULT_MAX_TURNS
    lines: list[DialogueLine] = field(default_factory=list)
    ended: bool = False
    end_reason: str = ""

    def participants(self) -> tuple[str, str]:
        return self.initiator_id, self.target_id

    def next_speaker(self) -> str:
        """下一个发言者:初始是发起者,然后交替。"""
        if not self.lines:
            return self.initiator_id
        last = self.lines[-1].speaker_id
        return self.target_id if last == self.initiator_id else self.initiator_id

    def has_other(self, agent_id: str) -> str | None:
        if agent_id == self.initiator_id:
            return self.target_id
        if agent_id == self.target_id:
            return self.initiator_id
        return None


# ============================================================================
#                          Dialogue prompt template
# ============================================================================


DIALOGUE_TASK = """你是 {speaker_name},正在和 {other_name} 在 {location_name} 对话。

【对方简介】
{other_brief}

【已说过的话(按顺序)】
{history}

【任务】
作为 {speaker_name},接下来说一句话(1-3 句,不超过 80 字)。
要求:
1. 符合你的人格、说话风格、当前心境与对方的关系
2. 不要打破角色,不要冒出"作为 AI"之类的话
3. 不要输出引号、speaker 标识或 JSON,只输出纯台词
4. 如果你觉得对话该结束了(达成共识 / 尴尬退场 / 被打断),在台词末尾加 {end_token}

只输出台词本身。开始:"""


# ============================================================================
#                             DialogueManager
# ============================================================================


SimEventEmitter = Callable[[str, dict[str, Any]], None]
"""SimEngine 注入的 publish 函数。type / payload。"""


class DialogueManager:
    """活跃 dialogue session 管理 + LLM 生成对白。

    实现 DialogueGuard Protocol(给 scheduler 用):is_agent_busy_with_dialogue(id) -> bool
    """

    def __init__(
        self,
        llm: DeepSeekClient,
        persona_loader: PersonaLoader,
        memory_store: MemoryStore | None,
        model_flash: str = "deepseek-v4-flash",
        max_turns: int = DEFAULT_MAX_TURNS,
        on_event: SimEventEmitter | None = None,
    ) -> None:
        self.llm = llm
        self.persona_loader = persona_loader
        self.memory_store = memory_store
        self.model_flash = model_flash
        self.max_turns = max_turns
        self.on_event = on_event

        # session_id → session
        self._sessions: dict[str, DialogueSession] = {}
        # agent_id → session_id(反查;一个 agent 同时只在一场对话)
        self._agent_session: dict[str, str] = {}
        # 后台任务跟踪(shutdown 时 drain)
        self._tasks: set[asyncio.Task[None]] = set()

    # ----------------------------------------------------- DialogueGuard

    def is_agent_busy_with_dialogue(self, agent_id: str) -> bool:
        """scheduler 调:agent 在对话中应跳过 action 推进。"""
        return agent_id in self._agent_session

    # ----------------------------------------------------- session lifecycle

    def try_start_session(
        self,
        initiator: AgentRuntime,
        target: AgentRuntime,
        game_time: float,
    ) -> DialogueSession | None:
        """尝试启动一场对话。

        返回 None 表示无法开启(双方已在某场对话 / 不在同场所 / 同一 agent)。
        启动后会立刻 emit dialogue_started 事件,并 schedule 后台 run_session。
        """
        if initiator.agent_id == target.agent_id:
            return None
        if not initiator.current_location:
            return None
        if initiator.current_location != target.current_location:
            return None
        if (
            initiator.agent_id in self._agent_session
            or target.agent_id in self._agent_session
        ):
            return None

        session = DialogueSession(
            session_id=uuid4().hex,
            initiator_id=initiator.agent_id,
            target_id=target.agent_id,
            location=initiator.current_location,
            started_at_game_time=game_time,
            max_turns=self.max_turns,
        )
        self._sessions[session.session_id] = session
        self._agent_session[initiator.agent_id] = session.session_id
        self._agent_session[target.agent_id] = session.session_id

        logger.info(
            "[dialogue] session started id=%s %s ↔ %s @ %s",
            session.session_id[:8],
            initiator.agent_id,
            target.agent_id,
            session.location,
        )
        self._emit(
            "dialogue_started",
            {
                "session_id": session.session_id,
                "initiator_id": initiator.agent_id,
                "target_id": target.agent_id,
                "location": session.location,
            },
        )
        task = asyncio.create_task(self._run_session(session))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return session

    async def _run_session(self, session: DialogueSession) -> None:
        """串行生成 max_turns 轮台词,完成后写 memory + emit dialogue_ended。"""
        try:
            for turn_idx in range(session.max_turns):
                if session.ended:
                    break
                line = await self._generate_line(session, turn_idx)
                if line is None:
                    session.end_reason = "llm_failed"
                    break
                # 检测 LLM 主动结束标记
                stripped, wants_end = self._strip_end_token(line.text)
                line.text = stripped
                session.lines.append(line)
                self._emit(
                    "dialogue_line",
                    {
                        "session_id": session.session_id,
                        "speaker_id": line.speaker_id,
                        "text": line.text,
                        "turn_idx": line.turn_idx,
                    },
                )
                if wants_end:
                    session.end_reason = "llm_end_token"
                    break
            if not session.end_reason:
                session.end_reason = "max_turns"
            await self._finalize_session(session)
        except Exception as exc:  # noqa: BLE001
            logger.exception("[dialogue] session %s crashed: %s", session.session_id[:8], exc)
            session.end_reason = f"crashed:{type(exc).__name__}"
            await self._finalize_session(session)

    async def _finalize_session(self, session: DialogueSession) -> None:
        session.ended = True
        # 释放双方
        for aid in (session.initiator_id, session.target_id):
            if self._agent_session.get(aid) == session.session_id:
                del self._agent_session[aid]
        # 写双方 memory
        if self.memory_store is not None and session.lines:
            await self._write_dialogue_memory(session)
        logger.info(
            "[dialogue] session ended id=%s reason=%s turns=%d",
            session.session_id[:8],
            session.end_reason,
            len(session.lines),
        )
        self._emit(
            "dialogue_ended",
            {
                "session_id": session.session_id,
                "initiator_id": session.initiator_id,
                "target_id": session.target_id,
                "total_turns": len(session.lines),
                "reason": session.end_reason,
            },
        )
        # 保留 session 在 _sessions 短时间供查询;实际生产可加超时清理。
        # 这里立即清理以释放内存。
        self._sessions.pop(session.session_id, None)

    # ----------------------------------------------------- llm call

    async def _generate_line(
        self,
        session: DialogueSession,
        turn_idx: int,
    ) -> DialogueLine | None:
        speaker_id = session.next_speaker()
        other_id = session.has_other(speaker_id) or ""
        try:
            speaker_persona = self.persona_loader.load(speaker_id)
            other_persona = self.persona_loader.load(other_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[dialogue] persona load failed: %s", exc)
            return None

        # Layer 0 + Layer 1 = 字节稳定(speaker 的完整人设),命中 DeepSeek 缓存
        layer_0 = PromptBuilder.LAYER_0_SYSTEM
        layer_1 = build_rich_layer_1(speaker_persona)

        # Layer 3 = 任务 + 对方简介 + 历史
        other_brief = (
            f"{other_persona.display_name}({other_persona.age}岁{other_persona.occupation})"
            f",{other_persona.identity}"
        )
        history_text = self._format_history(session)
        task = DIALOGUE_TASK.format(
            speaker_name=speaker_persona.display_name,
            other_name=other_persona.display_name,
            location_name=session.location,
            other_brief=other_brief,
            history=history_text,
            end_token=_END_TOKEN,
        )
        messages = [
            {"role": "system", "content": layer_0 + "\n" + layer_1},
            {"role": "user", "content": task},
        ]
        try:
            response = await self.llm.chat(
                messages=messages,
                model=self.model_flash,
                mode=ThinkMode.NON_THINK,
                temperature=0.85,  # 高温度,对话更生动
                max_tokens=120,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[dialogue] LLM failed speaker=%s turn=%d: %s",
                speaker_id,
                turn_idx,
                exc,
            )
            return None
        text = self._clean_text(response.content)
        if not text:
            return None
        return DialogueLine(
            speaker_id=speaker_id,
            text=text,
            game_time=session.started_at_game_time,  # 简化:都用 session 起始时间
            turn_idx=turn_idx,
        )

    def _format_history(self, session: DialogueSession) -> str:
        if not session.lines:
            return "  (尚未开口,这是开场。)"
        out_lines = []
        for line in session.lines:
            try:
                persona = self.persona_loader.load(line.speaker_id)
                name = persona.display_name
            except Exception:  # noqa: BLE001
                name = line.speaker_id
            out_lines.append(f"  {name}:{line.text}")
        return "\n".join(out_lines)

    def _clean_text(self, raw: str) -> str:
        """去掉前后空白 / 引号,LLM 输出的台词可能包了 "" 或 「」。"""
        text = raw.strip()
        # 多次剥离前后引号
        prev = None
        while prev != text:
            prev = text
            text = _QUOTE_RE.sub("", text).strip()
        return text

    def _strip_end_token(self, text: str) -> tuple[str, bool]:
        if _END_TOKEN in text:
            return text.replace(_END_TOKEN, "").strip(), True
        return text, False

    # ----------------------------------------------------- memory write

    async def _write_dialogue_memory(self, session: DialogueSession) -> None:
        """把整段对话作为一条 observation memory 写入双方。"""
        try:
            init_persona = self.persona_loader.load(session.initiator_id)
            target_persona = self.persona_loader.load(session.target_id)
        except Exception:  # noqa: BLE001
            return
        transcript = "\n".join(
            f"{(init_persona if line.speaker_id == session.initiator_id else target_persona).display_name}:{line.text}"
            for line in session.lines
        )
        # 简化:重要性固定 5(Block G 反思时会重新评分)
        importance = 5
        for owner_id, other_persona in (
            (session.initiator_id, target_persona),
            (session.target_id, init_persona),
        ):
            content = f"和{other_persona.display_name}在{session.location}对话:\n{transcript}"
            mem = Memory(
                memory_id=None,
                agent_id=owner_id,
                memory_type="observation",
                content=content,
                importance=importance,
                game_time=session.started_at_game_time,
                real_time=time.time(),
                location=session.location,
                related_agents=[session.initiator_id, session.target_id],
                keywords=[
                    init_persona.display_name,
                    target_persona.display_name,
                    "对话",
                    session.location,
                ],
            )
            try:
                await self.memory_store.insert(mem)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[dialogue] memory write failed owner=%s: %s", owner_id, exc
                )

    # ----------------------------------------------------- event emit

    def set_event_emitter(self, emitter: SimEventEmitter) -> None:
        """循环依赖 workaround:DialogueManager 在 SimEngine 之前构造,
        SimEngine 构造完后回填 emit_event 引用。"""
        self.on_event = emitter

    def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        if self.on_event is None:
            return
        try:
            self.on_event(event_type, payload)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[dialogue] event emit failed: %s", exc)

    # ----------------------------------------------------- shutdown

    async def shutdown(self) -> None:
        """优雅停机:取消所有活跃 session task。"""
        for task in list(self._tasks):
            if not task.done():
                task.cancel()
        if self._tasks:
            await asyncio.wait(self._tasks, timeout=2.0)
        self._sessions.clear()
        self._agent_session.clear()


# ============================================================================
#                  Module-level legacy wrapper (Block A 占位)
# ============================================================================


async def start_session(actor_id: str, target_id: str) -> dict[str, Any]:
    raise NotImplementedError(
        "Block I:请用 DialogueManager.try_start_session(initiator, target, game_time)"
    )
