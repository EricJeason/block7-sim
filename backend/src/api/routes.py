"""FastAPI HTTP 路由。

约定:所有需要 sim 状态的端点都从 request.app.state.sim_engine 取 SimEngine。
SimEngine 由 main.py 的 lifespan 创建并挂载。

端点:
- GET /world            初始化:locations + 所有 agent 当前分布 + 时钟参数
- GET /agents           所有 agent 的运行时快照
- GET /agent/{id}/state 单个 agent 完整快照
- GET /agent/{id}/memories?limit=20&type=observation
                        最近 N 条 memory(可按 type 过滤)
"""
from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, HTTPException, Query, Request

from src.memory.store import Memory
from src.sim import SimEngine

router = APIRouter()


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
