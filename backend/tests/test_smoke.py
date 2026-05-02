"""Block A 烟测:验证所有模块可 import,/health 路由返回 200。"""
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
    from src.api import routes, websocket  # noqa: F401
    from src.llm import deepseek, prompt_builder  # noqa: F401
    from src.memory import compression, schema, store  # noqa: F401
