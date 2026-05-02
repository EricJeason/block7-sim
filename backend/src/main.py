"""FastAPI app entry point. Block A 只实现 /health 验活路由。"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Block A: 占位,Block B 之后这里加 LLM 客户端预热、数据库连接等
    _ = settings  # 引用一下,确保配置加载链路通畅
    yield


app = FastAPI(title="Block-7 Sim Backend", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
