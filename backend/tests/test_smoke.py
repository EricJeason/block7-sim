"""Block A/B 烟测:验证所有模块可 import,/health 路由返回 200,prompt 缓存层稳定。"""
from __future__ import annotations

from fastapi.testclient import TestClient

from src.main import app


def test_health() -> None:
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_imports() -> None:
    """所有占位模块都能 import,即使未实现"""
    from src.agent import perception, planning, reflection, runtime, scheduler  # noqa: F401
    from src.agent.runtime import AgentRuntime, QueuedAction  # noqa: F401
    from src.agent.scheduler import ActionScheduler, SchedulerConfig  # noqa: F401
    from src.api import routes, websocket  # noqa: F401
    from src.llm import deepseek, prompt_builder  # noqa: F401
    from src.memory import compression, schema, store  # noqa: F401


def test_prompt_builder_locked_to_muguzhen() -> None:
    """LAYER_0 已锁定为暮谷镇(Eric 已敲定世界观)。占位符与旧世界名都不应再出现。"""
    from src.llm.prompt_builder import PromptBuilder

    assert "暮谷镇" in PromptBuilder.LAYER_0_SYSTEM
    assert "[WORLD_PENDING]" not in PromptBuilder.LAYER_0_SYSTEM
    assert "青岚镇" not in PromptBuilder.LAYER_0_SYSTEM


def test_prompt_builder_layer_stability() -> None:
    """Layer 0+1 在两次构建中字节相等,Layer 2+3 在状态变化时不同。"""
    from src.llm.prompt_builder import AgentPersona, AgentRuntimeState, PromptBuilder

    persona = AgentPersona(
        agent_id="x",
        name="测试",
        age=30,
        occupation="测试员",
        personality="测试性格",
        background="测试背景",
    )
    state1 = AgentRuntimeState(
        current_location="A",
        current_mood="平静",
        recent_memories=["m1"],
        game_time="Day 1, 10:00",
    )
    state2 = AgentRuntimeState(
        current_location="B",
        current_mood="开心",
        recent_memories=["m2"],
        game_time="Day 1, 11:00",
    )
    msgs1 = PromptBuilder.assemble_messages(persona, state1, "任务1")
    msgs2 = PromptBuilder.assemble_messages(persona, state2, "任务2")
    assert msgs1[0]["content"] == msgs2[0]["content"]
    assert msgs1[1]["content"] != msgs2[1]["content"]


def test_deepseek_client_init() -> None:
    """DeepSeekClient 能被实例化(不发起真实调用)。"""
    from src.llm.deepseek import DeepSeekClient

    c = DeepSeekClient(api_key="dummy", base_url="https://example.com")
    assert c is not None
