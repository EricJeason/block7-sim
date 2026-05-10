"""WebSocket /ws/sim — Godot 客户端订阅 sim 事件流。

握手后:
- 立即发一个 hello 事件,带 game_time + agent 数,便于客户端确认连上
- 进入循环:从 SimEngine.subscribe() 队列拉 SimEvent → JSON → ws.send_json
- 客户端可发 ping(任何 text)→ 回 pong,用于保活/检测
- 断开时自动 unsubscribe + 清理
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.sim import SimEngine

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws/sim")
async def sim_socket(ws: WebSocket) -> None:
    """订阅 sim 事件 + 推送给客户端。"""
    engine: SimEngine | None = getattr(ws.app.state, "sim_engine", None)
    if engine is None:
        await ws.close(code=1011, reason="sim_engine not initialized")
        return

    await ws.accept()
    queue = engine.subscribe()
    logger.info("[ws] client connected, total subscribers=%d", len(engine._subscribers))

    # 发个 hello 让客户端确认握手成功
    try:
        await ws.send_json(
            {
                "type": "hello",
                "agent_id": None,
                "game_time": engine.game_time,
                "payload": {
                    "agent_count": len(engine.agent_ids),
                    "time_scale": engine.time_scale,
                },
            }
        )
    except Exception:  # noqa: BLE001
        engine.unsubscribe(queue)
        return

    # 两条任务并行:
    # 1) 从队列拉事件 → 推给客户端
    # 2) 从客户端读 ping → 回 pong (检测断开 + 保活)
    sender_task = asyncio.create_task(_send_loop(ws, queue))
    receiver_task = asyncio.create_task(_receive_loop(ws))
    try:
        done, pending = await asyncio.wait(
            [sender_task, receiver_task], return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
    finally:
        engine.unsubscribe(queue)
        logger.info("[ws] client disconnected, remaining=%d", len(engine._subscribers))


async def _send_loop(ws: WebSocket, queue: asyncio.Queue) -> None:
    """从订阅队列拉事件推给客户端。"""
    while True:
        event = await queue.get()
        try:
            await ws.send_json(event.to_dict())
        except WebSocketDisconnect:
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("[ws] send failed: %s", exc)
            return


async def _receive_loop(ws: WebSocket) -> None:
    """读客户端消息;ping → pong;其它消息也回 ack。
    收到 disconnect 抛异常自然结束循环。"""
    while True:
        try:
            text = await ws.receive_text()
        except WebSocketDisconnect:
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("[ws] receive failed: %s", exc)
            return
        if text == "ping":
            try:
                await ws.send_json({"type": "pong", "agent_id": None, "game_time": 0, "payload": {}})
            except Exception:  # noqa: BLE001
                return
        # 其它客户端消息暂不处理(为 Block I/K 留接口)
