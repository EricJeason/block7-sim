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

from src.agent.dialogue import DialogueManager
from src.agent.perception import PerceptionBroker
from src.agent.planning import LLMPlanner, LocationLoader, PersonaLoader
from src.agent.reflection import ReflectionRunner
from src.agent.scheduler import ActionScheduler, SchedulerConfig
from src.api.routes import router as api_router
from src.api.websocket import router as ws_router
from src.config import settings
from src.llm.deepseek import DeepSeekClient
from src.memory.compression import MemoryCompressor
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


def _validate_settings() -> None:
    """启动前校验关键配置,提前给清晰的错误提示(而非第一次 LLM 调用才崩)。

    设计原则:
    - 缺 DEEPSEEK_API_KEY → 警告但允许启动(用户可能在调试 Godot 端,paused 模式不烧 token)
    - persona 目录 / locations 文件缺失 → 严重错误,直接抛(没人格 sim 跑不起来)
    """
    key = settings.deepseek_api_key
    if not key or key in ("your_api_key_here", "PLACEHOLDER"):
        logger.warning(
            "[main] ⚠️  DEEPSEEK_API_KEY 未配置或仍是占位符。"
            "Godot 端可以连后端看初始状态,但任何 LLM 调用会失败。"
            "请在项目根 .env 填真实 key 后重启。"
        )
    from src.agent.planning import DEFAULT_PERSONAS_DIR, DEFAULT_LOCATIONS_FILE
    if not DEFAULT_PERSONAS_DIR.exists():
        raise RuntimeError(
            f"[main] persona 目录不存在: {DEFAULT_PERSONAS_DIR}\n"
            "请检查 backend/data/personas/ 是否完整(应有 agent_01.yaml ~ agent_12.yaml)"
        )
    persona_count = len(list(DEFAULT_PERSONAS_DIR.glob("agent_*.yaml")))
    if persona_count < 12:
        logger.warning(
            "[main] ⚠️  仅找到 %d 个 persona YAML,期望 12 个(agent_01..agent_12)",
            persona_count,
        )
    if not DEFAULT_LOCATIONS_FILE.exists():
        raise RuntimeError(
            f"[main] locations.yaml 不存在: {DEFAULT_LOCATIONS_FILE}"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    # 配置校验 — 早期发现 .env 缺失,不要在第一次 LLM 调用时才崩
    _validate_settings()

    auto_tick = _env_bool("BLOCK7_AUTO_TICK", True)
    start_paused = _env_bool("BLOCK7_START_PAUSED", True)  # 默认暂停启动,零成本
    time_scale = _env_float("BLOCK7_TIME_SCALE", 60.0)
    tick_interval = _env_float("BLOCK7_TICK_INTERVAL", 1.0)
    thinking_threshold = _env_float("BLOCK7_THINKING_THRESHOLD", 120.0)
    max_actions = int(_env_float("BLOCK7_MAX_ACTIONS", 15.0))
    enable_daily_reflection = _env_bool("BLOCK7_DAILY_REFLECTION", True)

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
    # Block I:对话状态机。先构造(此时 emit 还未接,推到事件会被静默丢弃,
    # 但此时也不会有任何对话发生),engine 构造完后再回填 set_event_emitter。
    dialogue_manager = DialogueManager(
        llm=llm_client,
        persona_loader=persona_loader,
        memory_store=memory_store,
        model_flash=settings.deepseek_model_flash,
    )
    broker = PerceptionBroker(
        memory_store=memory_store,
        persona_loader=persona_loader,
        location_loader=location_loader,
        dialogue_manager=dialogue_manager,
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
        dialogue_guard=dialogue_manager,
    )

    # Block G:每日反思 + memory 压缩(跨日触发)
    reflection_runner = ReflectionRunner(
        llm=llm_client,
        persona_loader=persona_loader,
        memory_store=memory_store,
        model_pro=settings.deepseek_model_pro,
    )
    compressor = MemoryCompressor(
        store=memory_store,
        llm=llm_client,
        model=settings.deepseek_model_flash,
        persona_loader=persona_loader,
    )

    # 4. SimEngine 启动
    engine = SimEngine(
        scheduler=scheduler,
        memory_store=memory_store,
        persona_loader=persona_loader,
        location_loader=location_loader,
        time_scale=time_scale,
        tick_interval_seconds=tick_interval,
        reflection_runner=reflection_runner,
        compressor=compressor,
        enable_daily_reflection=enable_daily_reflection,
        dialogue_manager=dialogue_manager,  # /sim/health dialogue 统计
    )
    # 回填 emit_event:DialogueManager 现在可以推 dialogue_* 事件给 WS 订阅者
    dialogue_manager.set_event_emitter(engine.emit_event)
    await engine.start(run_loop=auto_tick, paused=start_paused)

    # 5. 挂 app.state
    app.state.sim_engine = engine
    app.state.llm_client = llm_client
    app.state.dialogue_manager = dialogue_manager

    try:
        yield
    finally:
        logger.info("[main] lifespan shutdown")
        await engine.stop()
        await dialogue_manager.shutdown()
        await llm_client.aclose()


app = FastAPI(title="Block-7 Sim Backend", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


# 业务路由 + WebSocket
app.include_router(api_router)
app.include_router(ws_router)
