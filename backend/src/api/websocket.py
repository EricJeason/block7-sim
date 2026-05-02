"""WebSocket 路由 — Godot 客户端订阅 sim 事件流。Block H 实现。"""
from __future__ import annotations

from fastapi import APIRouter, WebSocket

router = APIRouter()


@router.websocket("/ws/sim")
async def sim_socket(ws: WebSocket) -> None:
    """Godot 客户端用此 WS 订阅 sim tick / agent 事件。

    Block H 实现。
    """
    raise NotImplementedError("Block H 实现")
