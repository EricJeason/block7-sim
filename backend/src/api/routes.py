"""FastAPI 路由集合。Block A 只暴露 /health,真实业务路由在 Block H 接入。"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """与 main.py 的 /health 等价的备用健康路由,供未来挂到子路由前缀使用。"""
    return {"status": "ok", "version": "0.1.0"}
