"""FastAPI HTTP 路由。

约定:所有需要 sim 状态的端点都从 request.app.state.sim_engine 取 SimEngine。
SimEngine 由 main.py 的 lifespan 创建并挂载。

端点:
- GET /world            初始化:locations + 所有 agent 当前分布 + 时钟参数
- GET /agents           所有 agent 的运行时快照
- GET /agent/{id}/state 单个 agent 完整快照
- GET /agent/{id}/memories?limit=20&type=observation
                        最近 N 条 memory(可按 type 过滤)
- GET /sim/api_key/status   key 是否已配置 + 脱敏首尾(不返回明文)
- POST /sim/api_key/set     body={key} 运行时设 key + 写 .env
"""
from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from src.config_writer import persist_api_key_to_env
from src.memory.store import Memory
from src.sim import SimEngine

router = APIRouter()


class SetApiKeyRequest(BaseModel):
    key: str = Field(..., description="DeepSeek API key (sk- 开头)")
    persist: bool = Field(default=True, description="是否写入项目根 .env 文件(默认 True)")


def _get_engine(request: Request) -> SimEngine:
    engine = getattr(request.app.state, "sim_engine", None)
    if engine is None:
        raise HTTPException(
            status_code=503,
            detail="sim_engine not initialized (lifespan not started?)",
        )
    return cast(SimEngine, engine)


@router.get("/world")
async def get_world(request: Request) -> dict[str, Any]:
    """初始化:locations + 所有 agent 当前分布 + 时钟参数。"""
    engine = _get_engine(request)
    return engine.world_snapshot()


@router.get("/sim/state")
async def get_sim_state(request: Request) -> dict[str, Any]:
    """轻量查询:仅返回 sim 当前是否暂停 + game_time。"""
    engine = _get_engine(request)
    return {"paused": engine.is_paused(), "game_time": engine.game_time}


@router.get("/sim/health")
async def get_sim_health(request: Request) -> dict[str, Any]:
    """运行时健康统计:uptime / tick 数 / 反思统计 / LLM 累计成本 + 缓存命中率。

    供 Eric 在 PowerShell `curl http://127.0.0.1:8000/sim/health` 快速查看
    "我跑了多久,反思状态,花了多少钱,缓存命中正常吗"。
    """
    engine = _get_engine(request)
    llm_client = getattr(request.app.state, "llm_client", None)
    return engine.health_snapshot(llm_client=llm_client)


# =========================================================== API key 管理

@router.get("/sim/api_key/status")
async def get_api_key_status(request: Request) -> dict[str, Any]:
    """查询 API key 是否已配置 + 脱敏首尾。永不返回明文。

    给 Godot 启动时调用,无 key 则弹"输入 key"对话框。
    """
    llm_client = getattr(request.app.state, "llm_client", None)
    if llm_client is None or not hasattr(llm_client, "is_api_key_configured"):
        return {"configured": False, "masked": ""}
    configured = llm_client.is_api_key_configured()
    return {
        "configured": configured,
        "masked": llm_client.masked_api_key() if configured else "",
    }


@router.post("/sim/api_key/set")
async def set_api_key(req: SetApiKeyRequest, request: Request) -> dict[str, Any]:
    """运行时设 API key。

    - 校验 sk- 开头
    - 调 DeepSeekClient.update_api_key 立刻生效(不重启 backend)
    - 默认 persist=True 写到项目根 .env(下次启动自动加载)
    - 返回 status,不返回明文 key
    """
    key = req.key.strip()
    if not key.startswith("sk-") or len(key) < 20:
        raise HTTPException(
            status_code=400,
            detail="key 格式错误,应以 sk- 开头且长度 ≥ 20 字符",
        )
    llm_client = getattr(request.app.state, "llm_client", None)
    if llm_client is None or not hasattr(llm_client, "update_api_key"):
        raise HTTPException(
            status_code=503, detail="llm_client 未初始化"
        )
    llm_client.update_api_key(key)
    persisted = False
    if req.persist:
        persisted = persist_api_key_to_env(key)
    return {
        "configured": True,
        "masked": llm_client.masked_api_key(),
        "persisted_to_env": persisted,
    }


@router.post("/sim/pause")
async def pause_sim(request: Request) -> dict[str, Any]:
    """暂停 tick(不烧 token)。幂等。"""
    engine = _get_engine(request)
    engine.pause()
    return {"paused": True}


@router.post("/sim/resume")
async def resume_sim(request: Request) -> dict[str, Any]:
    """恢复 tick。幂等。"""
    engine = _get_engine(request)
    engine.resume()
    return {"paused": False}


@router.get("/agents")
async def list_agents(request: Request) -> list[dict[str, Any]]:
    """所有 agent 的运行时快照(用 AgentRuntime.snapshot)。"""
    engine = _get_engine(request)
    out = []
    for agent_id in engine.agent_ids:
        try:
            agent = engine.scheduler.get_agent(agent_id)
        except KeyError:
            continue
        out.append(agent.snapshot())
    return out


@router.get("/agent/{agent_id}/state")
async def get_agent_state(agent_id: str, request: Request) -> dict[str, Any]:
    engine = _get_engine(request)
    try:
        agent = engine.scheduler.get_agent(agent_id)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"unknown agent_id: {agent_id}"
        ) from None
    return agent.snapshot()


@router.get("/agent/{agent_id}/memories")
async def get_agent_memories(
    agent_id: str,
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    type: str | None = Query(
        default=None, description="observation / reflection / plan"
    ),
) -> list[dict[str, Any]]:
    engine = _get_engine(request)
    try:
        engine.scheduler.get_agent(agent_id)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"unknown agent_id: {agent_id}"
        ) from None
    types = [type] if type in ("observation", "reflection", "plan") else None
    memories = await engine.memory_store.get_recent(
        agent_id, limit=limit, memory_types=types  # type: ignore[arg-type]
    )
    return [_memory_to_dict(m) for m in memories]


def _memory_to_dict(m: Memory) -> dict[str, Any]:
    return {
        "memory_id": m.memory_id,
        "agent_id": m.agent_id,
        "memory_type": m.memory_type,
        "content": m.content,
        "importance": m.importance,
        "game_time": m.game_time,
        "real_time": m.real_time,
        "location": m.location,
        "related_agents": m.related_agents,
        "keywords": m.keywords,
    }
