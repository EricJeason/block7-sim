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


class BindPlayerRequest(BaseModel):
    agent_id: str | None = Field(
        default=None,
        description="玩家绑定到的 agent_id(如 agent_04);传 null 解绑回到上帝模式",
    )


class PlayerGreetRequest(BaseModel):
    target_id: str = Field(..., description="玩家要打招呼的 NPC agent_id")
    player_line: str = Field(..., description="玩家说的话(F4.1 固定 / v0.4 LLM 候选或自由输入)")
    max_turns: int = Field(default=2, ge=2, le=8, description="对话总轮数,默认 2(玩家 1+NPC 1)")


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


@router.get("/sim/player")
async def get_player(request: Request) -> dict[str, Any]:
    """F2: 查询当前玩家绑定的 agent_id(None = 上帝模式)。"""
    engine = _get_engine(request)
    return {"player_agent_id": engine.scheduler.get_player_agent_id()}


@router.post("/sim/player/bind")
async def bind_player(req: BindPlayerRequest, request: Request) -> dict[str, Any]:
    """F2: 绑定 agent_id 为玩家控制(扮演模式)。

    - 该 agent 的 LLM 思考被跳过(玩家通过 WASD/E 互动手动决策)
    - 传 agent_id=None 解绑,回到上帝模式(所有 agent 由 LLM 控制)
    - 默认 Godot 客户端启动时调此绑定 agent_04(艾琳)
    """
    engine = _get_engine(request)
    try:
        engine.scheduler.set_player_agent(req.agent_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None
    return {"player_agent_id": engine.scheduler.get_player_agent_id()}


@router.post("/dialogue/player_greet")
async def player_greet(req: PlayerGreetRequest, request: Request) -> dict[str, Any]:
    """F4.1 玩家发起对话(打招呼) — DialogueManager 触发 NPC LLM 回复。

    流程:
    1. 校验玩家已绑定(scheduler.get_player_agent_id != None)
    2. 校验 target 存在 + 与玩家同场所
    3. 调 DialogueManager.try_start_player_session(player, target, player_line)
    4. 立即广播 dialogue_started + dialogue_line(玩家那一句)WS 事件
    5. 后台 LLM 生成 NPC 回复,完成后 WS 推 dialogue_line(NPC 那一句)
    6. 同步返回 session_id 给 Godot 用以追踪
    """
    engine = _get_engine(request)
    player_id = engine.scheduler.get_player_agent_id()
    if player_id is None:
        raise HTTPException(status_code=400, detail="尚未绑定玩家(POST /sim/player/bind 先绑定)")
    if engine.dialogue_manager is None:
        raise HTTPException(status_code=503, detail="dialogue_manager 未初始化")
    try:
        player = engine.scheduler.get_agent(player_id)
        target = engine.scheduler.get_agent(req.target_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None

    session = engine.dialogue_manager.try_start_player_session(
        player=player,
        target=target,
        player_line=req.player_line,
        game_time=engine.game_time,
        max_turns=req.max_turns,
    )
    if session is None:
        # 失败原因:同 id / 不同场所 / 双方已在对话 / 空 line
        raise HTTPException(
            status_code=409,
            detail="无法发起对话:同 id / 不同场所 / 一方已在对话中 / line 为空",
        )
    return {
        "session_id": session.session_id,
        "initiator_id": session.initiator_id,
        "target_id": session.target_id,
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
