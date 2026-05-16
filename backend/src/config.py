"""全局配置,从 .env 加载。"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# config.py 在 backend/src/config.py;parent.parent = backend/, parent.parent.parent = 项目根
# 路径解析策略:
#   绝对路径 → 直接使用
#   相对路径 → 基于"项目根目录"解析 (而不是 cwd)
# 这样无论从 worktree/backend、worktree根、主仓库根启动,都得到一致结果。
# .env 里 SQLITE_PATH=./backend/data/sim.db 这种写法在所有场景都正确。
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _BACKEND_DIR.parent
_DEFAULT_SQLITE_PATH = "./backend/data/sim.db"
_DEFAULT_LOG_DIR = "./logs"


def _resolve_path(raw: str) -> str:
    """SQLite path / log dir 通用解析:相对路径基于项目根。"""
    p = Path(raw)
    if p.is_absolute():
        return str(p)
    return str((_PROJECT_ROOT / p).resolve())


@dataclass(frozen=True)
class Settings:
    deepseek_api_key: str
    deepseek_base_url: str
    deepseek_model_pro: str
    deepseek_model_flash: str
    backend_host: str
    backend_port: int
    sqlite_path: str
    log_level: str
    log_dir: str


settings = Settings(
    deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
    deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    deepseek_model_pro=os.getenv("DEEPSEEK_MODEL_PRO", "deepseek-v4-pro"),
    deepseek_model_flash=os.getenv("DEEPSEEK_MODEL_FLASH", "deepseek-v4-flash"),
    backend_host=os.getenv("BACKEND_HOST", "127.0.0.1"),
    backend_port=int(os.getenv("BACKEND_PORT", "8000")),
    sqlite_path=_resolve_path(os.getenv("SQLITE_PATH", _DEFAULT_SQLITE_PATH)),
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    log_dir=_resolve_path(os.getenv("LOG_DIR", _DEFAULT_LOG_DIR)),
)
