"""FastAPI app 入口 — Block H 完整 sim 联调。

Lifespan 启动顺序:
1. init_db (SQLite schema 幂等创建)
2. 构造 DeepSeekClient + MemoryStore + PersonaLoader + LocationLoader
3. 装配 LLMPlanner + PerceptionBroker + ActionScheduler
4. 创建 SimEngine,start (注册 12 agent + 启动后台 tick 循环)
5. 挂到 app.state 供 routes/websocket 使用

环境变量:
- DEEPSEEK_API_KEY:必填,否则 LLM 路径会失败,但 SimEngine 仍能启动 (planner 不被触发时无副作用)
- BLOCK7_AUTO_TICK=0 / 1:1=自动 tick 循环(默认), 0=只注册 agent 不自动 tick(测试 / 离线观察用)
- BLOCK7_START_PAUSED=1 / 0:1=tick 循环启动但暂停(默认,零成本) , 0=立即运行
  暂停时 backend 不调任何 LLM,客户端调 POST /sim/resume 才开始烧 token
- BLOCK7_TIME_SCALE=60.0:1 现实秒 = N 游戏秒
- BLOCK7_TICK_INTERVAL=1.0:tick 真实秒间隔
- BLOCK7_THINKING_THRESHOLD=120.0:队列剩余少于此值(游戏秒)才触发新一波 fine plan
- BLOCK7_MAX_ACTIONS=15:每次 fine plan 输出上限
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.agent.perception import PerceptionBroker
from src.agent.planning import LLMPlanner, LocationLoader, PersonaLoader
from src.agent.scheduler import ActionScheduler, SchedulerConfig
from src.api.routes import router as api_router
from src.api.websocket import router as ws_router
from src.config import settings
from src.llm.deepseek import DeepSeekClient
from src.memory.schema import init_db
from src.memory.store import MemoryStore
from src.sim import SimEngine

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    auto_tick = _env_bool("BLOCK7_AUTO_TICK", True)
    start_paused = _env_bool("BLOCK7_START_PAUSED", True)  # 默认暂停启动,零成本
    time_scale = _env_float("BLOCK7_TIME_SCALE", 60.0)
    tick_interval = _env_float("BLOCK7_TICK_INTERVAL", 1.0)
    thinking_threshold = _env_float("BLOCK7_THINKING_THRESHOLD", 120.0)
    max_actions = int(_env_float("BLOCK7_MAX_ACTIONS", 15.0))

    logger.info(
        "[main] lifespan startup: auto_tick=%s start_paused=%s time_scale=%g "
        "tick_interval=%g thinking_threshold=%g max_actions=%d",
        auto_tick,
        start_paused,
        time_scale,
        tick_interval,
        thinking_threshold,
        max_actions,
    )

    # 1. 数据库 schema
    await init_db(settings.sqlite_path)

    # 2. 基础组件
    llm_client = DeepSeekClient(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )
    memory_store = MemoryStore(settings.sqlite_path)
    persona_loader = PersonaLoader()
    location_loader = LocationLoader()

    # 3. Agent 上层逻辑
    planner = LLMPlanner(
        llm=llm_client,
        memory_store=memory_store,
        persona_loader=persona_loader,
        location_loader=location_loader,
        model_pro=settings.deepseek_model_pro,
        model_flash=settings.deepseek_model_flash,
    )
    broker = PerceptionBroker(
        memory_store=memory_store,
        persona_loader=persona_loader,
        location_loader=location_loader,
    )
    scheduler_config = SchedulerConfig(
        thinking_trigger_threshold=thinking_threshold,
        max_planner_actions=max_actions,
    )
    scheduler = ActionScheduler(
        planner=planner,
        memory_store=memory_store,
        config=scheduler_config,
        perception_broker=broker,
    )

    # 4. SimEngine 启动
    engine = SimEngine(
        scheduler=scheduler,
        memory_store=memory_store,
        persona_loader=persona_loader,
        location_loader=location_loader,
        time_scale=time_scale,
        tick_interval_seconds=tick_interval,
    )
    await engine.start(run_loop=auto_tick, paused=start_paused)

    # 5. 挂 app.state
    app.state.sim_engine = engine
    app.state.llm_client = llm_client

    try:
        yield
    finally:
        logger.info("[main] lifespan shutdown")
        await engine.stop()
        await llm_client.aclose()


app = FastAPI(title="Block-7 Sim Backend", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


# 业务路由 + WebSocket
app.include_router(api_router)
app.include_router(ws_router)
