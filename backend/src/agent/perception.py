"""Block F:同场所事件传播 (Perception)。

参见设计文档 v0.2 §2.4:不做全局广播,只对共享同一 location 的 agent 推送事件。

PerceptionBroker 由 ActionScheduler 在 action 完成时调用:
1. 应用 move_to 副作用 — 把 actor.current_location 更新到目标场所(若有效)
2. 在 (新) 场所上,给所有其他在场 agent 写一条 memory_type='observation' 记忆
3. 跳过 actor 本人;跳过低价值动作 (idle 等)

不与 LLM 直接打交道(纯写库),但产出的 observation 会被 Block E 的 _plan_fine
通过 memory_store.get_recent() 读到 → agent 自然"知道"别人在做什么。
"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, Iterable

from src.agent.runtime import AgentRuntime, QueuedAction
from src.memory.store import Memory, MemoryStore

if TYPE_CHECKING:  # 仅类型注解,避免循环 import 与运行期硬依赖
    from src.agent.dialogue import DialogueManager
    from src.agent.planning import LocationLoader, PersonaLoader

logger = logging.getLogger(__name__)


# 完成时不广播为 observation 的低价值 action_type
_SILENT_ACTION_TYPES: frozenset[str] = frozenset({"idle"})


class PerceptionBroker:
    """同场所事件广播器。

    用法:
        broker = PerceptionBroker(memory_store, persona_loader, location_loader)
        scheduler = ActionScheduler(planner=planner, perception_broker=broker, ...)

    Scheduler 会在每个 agent 完成 action 时(tick 中)异步调起 broker。
    """

    def __init__(
        self,
        memory_store: MemoryStore | None,
        persona_loader: "PersonaLoader | None" = None,
        location_loader: "LocationLoader | None" = None,
        default_importance: int = 3,
        dialogue_manager: "DialogueManager | None" = None,
    ) -> None:
        self.memory_store = memory_store
        self.persona_loader = persona_loader
        self.location_loader = location_loader
        self.default_importance = default_importance
        self.dialogue_manager = dialogue_manager

    async def on_action_completed(
        self,
        actor: AgentRuntime,
        action: QueuedAction,
        all_agents: Iterable[AgentRuntime],
        game_time: float,
    ) -> list[Memory]:
        """处理 actor 完成 action 的事件。返回写入的 memory 列表(便于测试 + 日志)。

        步骤:
        1. 若是 move_to 且目标场所有效 → 更新 actor.current_location
        2. 若动作类型在 _SILENT_ACTION_TYPES 中 → 跳过
        3. 找出与 actor 同场所的其他 agent (观察者)
        4. 给每个观察者写一条 observation memory
        """
        self._apply_move_effect(actor, action)

        # Block I:talk_to 提前在这里尝试触发,避免下面的 observers 为空 / 静默
        # action 早 return 跳过对话触发(实测发现这正是 talk_to 无法启动对话的根因:
        # 当 target 不在场所内时 observers 为空,直接 return [],对话永远启不起来)。
        # 即使没有第三方观察者,talk_to 仍应该尝试启动 actor↔target 的双人对话。
        self._maybe_trigger_dialogue(actor, action, all_agents, game_time)

        if action.action_type in _SILENT_ACTION_TYPES:
            return []

        # actor 自己永远不算观察者;空 location 不广播(谁也观察不到)
        actor_location = actor.current_location
        if not actor_location:
            return []

        observers = [
            a
            for a in all_agents
            if a.agent_id != actor.agent_id and a.current_location == actor_location
        ]
        if not observers:
            return []

        if self.memory_store is None:
            return []

        actor_name = self._actor_display_name(actor)
        location_name = self._location_name(actor_location)
        content = self._format_observation_content(actor_name, location_name, action)
        keywords = self._observation_keywords(actor, action, location_name)

        written: list[Memory] = []
        for observer in observers:
            importance = self._importance_for_observer(observer, actor)
            mem = Memory(
                memory_id=None,
                agent_id=observer.agent_id,
                memory_type="observation",
                content=content,
                importance=importance,
                game_time=game_time,
                real_time=time.time(),
                location=actor_location,
                related_agents=[actor.agent_id],
                keywords=keywords,
            )
            try:
                await self.memory_store.insert(mem)
                written.append(mem)
            except Exception as exc:  # noqa: BLE001 — store 故障不应阻塞 sim
                logger.warning(
                    "[perception] write failed observer=%s actor=%s: %s",
                    observer.agent_id,
                    actor.agent_id,
                    exc,
                )

        return written

    # --------------------------------------------------------- dialogue trigger

    def _maybe_trigger_dialogue(
        self,
        actor: AgentRuntime,
        action: QueuedAction,
        all_agents: Iterable[AgentRuntime],
        game_time: float,
    ) -> None:
        """talk_to 完成 + 目标在同场所 → 尝试启动对话。

        DialogueManager.try_start_session 内部会再校验同场所、不冲突等。
        """
        if action.action_type != "talk_to" or self.dialogue_manager is None:
            return
        args = action.args if isinstance(action.args, dict) else {}
        raw_target = args.get("agent_id")
        if not isinstance(raw_target, str) or not raw_target:
            return
        # 把 all_agents 实体化为 list,既能按 agent_id 又能按 display_name 反查
        agent_list = list(all_agents)
        target = self._resolve_agent_by_id_or_name(raw_target, agent_list)
        if target is None:
            logger.warning(
                "[perception] talk_to target not found: %r (actor=%s)",
                raw_target,
                actor.agent_id,
            )
            return
        self.dialogue_manager.try_start_session(actor, target, game_time)

    def _resolve_agent_by_id_or_name(
        self,
        target_str: str,
        all_agents: list[AgentRuntime],
    ) -> AgentRuntime | None:
        """先按 agent_id 精确匹配;失败则按 PersonaProfile.display_name 反查。

        LLM 倾向输出中文名("林秋")而不是 ID("agent_01"),这里做兼容兜底。
        """
        for a in all_agents:
            if a.agent_id == target_str:
                return a
        if self.persona_loader is None:
            return None
        for a in all_agents:
            try:
                persona = self.persona_loader.load(a.agent_id)
            except Exception:  # noqa: BLE001
                continue
            if persona.display_name == target_str:
                return a
        return None

    # ------------------------------------------------------------ side effect

    def _apply_move_effect(self, actor: AgentRuntime, action: QueuedAction) -> None:
        """move_to 完成后把 actor.current_location 改到目标场所。"""
        if action.action_type != "move_to":
            return
        target = action.args.get("location") if isinstance(action.args, dict) else None
        if not isinstance(target, str) or not target:
            return
        if self.location_loader is not None:
            try:
                self.location_loader.get(target)
            except KeyError:
                logger.warning(
                    "[perception] move_to invalid location=%r for agent=%s; not applying",
                    target,
                    actor.agent_id,
                )
                return
        if actor.current_location != target:
            logger.info(
                "[perception] %s moved %s -> %s",
                actor.agent_id,
                actor.current_location or "?",
                target,
            )
            actor.current_location = target

    # ------------------------------------------------------------- formatting

    def _actor_display_name(self, actor: AgentRuntime) -> str:
        if self.persona_loader is not None:
            try:
                name = self.persona_loader.load(actor.agent_id).display_name
                if name:
                    return name
            except Exception:  # noqa: BLE001
                pass
        return actor.persona_name or actor.agent_id

    def _location_name(self, location_id: str) -> str:
        if not location_id:
            return "?"
        if self.location_loader is not None:
            try:
                return self.location_loader.get(location_id).name or location_id
            except KeyError:
                return location_id
        return location_id

    def _format_observation_content(
        self,
        actor_name: str,
        location_name: str,
        action: QueuedAction,
    ) -> str:
        a_type = action.action_type
        args = action.args if isinstance(action.args, dict) else {}
        if a_type == "move_to":
            return f"{actor_name}来到了{location_name}"
        if a_type == "work":
            task = args.get("task", "事情")
            return f"{actor_name}在{location_name}做{task}"
        if a_type == "rest":
            reason = args.get("reason", "")
            tail = f"({reason})" if reason else ""
            return f"{actor_name}在{location_name}休息{tail}"
        if a_type == "observe":
            target = args.get("target", "周围")
            return f"{actor_name}在{location_name}打量{target}"
        if a_type == "interact":
            target = args.get("target", "某物")
            sub = args.get("action", "互动")
            return f"{actor_name}在{location_name}与{target}{sub}"
        if a_type == "talk_to":
            target = args.get("agent_id", "某人")
            return f"{actor_name}主动找{target}说话"
        # 通用兜底:其它自定义 action_type
        if args:
            args_text = ",".join(f"{k}={v}" for k, v in args.items())
            return f"{actor_name}在{location_name}做{a_type}({args_text})"
        return f"{actor_name}在{location_name}做{a_type}"

    def _observation_keywords(
        self,
        actor: AgentRuntime,
        action: QueuedAction,
        location_name: str,
    ) -> list[str]:
        """关键词:actor 中文名 + actor_id + 场所名 + 场所 id + action_type。
        重复项去重,顺序稳定 → 利于 LIKE 检索。"""
        keys: list[str] = []
        if self.persona_loader is not None:
            try:
                name = self.persona_loader.load(actor.agent_id).display_name
                if name:
                    keys.append(name)
            except Exception:  # noqa: BLE001
                pass
        keys.append(actor.agent_id)
        if location_name:
            keys.append(location_name)
        if actor.current_location:
            keys.append(actor.current_location)
        keys.append(action.action_type)
        # dedupe preserving order
        return list(dict.fromkeys(k for k in keys if k))

    def _importance_for_observer(
        self,
        observer: AgentRuntime,
        actor: AgentRuntime,
    ) -> int:
        """默认 default_importance,如果 observer 与 actor 有 initial_relationship 则 +1。"""
        importance = self.default_importance
        if self.persona_loader is None:
            return importance
        try:
            profile = self.persona_loader.load(observer.agent_id)
        except Exception:  # noqa: BLE001
            return importance
        related_ids = {key for key, _ in profile.initial_relationships}
        if actor.agent_id in related_ids:
            return min(10, importance + 1)
        return importance


# ============================================================================
#                  Module-level legacy wrappers (Block A 占位接口)
# ============================================================================


async def broadcast_event(location: str, event: dict[str, Any]) -> None:
    """Block A 占位签名。Block F 改用 PerceptionBroker.on_action_completed。"""
    raise NotImplementedError(
        "Block F 后:请用 PerceptionBroker.on_action_completed(actor, action, agents, game_time)"
    )


async def collect_observations(agent_id: str) -> list[dict[str, Any]]:
    """Block A 占位签名。Block F 后:观察直接落入 SQLite memories 表
    (memory_type='observation'),用 MemoryStore.get_recent(...) 取。"""
    raise NotImplementedError(
        "Block F 后:请用 MemoryStore.get_recent(agent_id) 或 .search(...) 取 observation"
    )
