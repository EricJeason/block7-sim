"""全局配置,从 .env 加载。"""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


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
    sqlite_path=os.getenv("SQLITE_PATH", "./backend/data/sim.db"),
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    log_dir=os.getenv("LOG_DIR", "./logs"),
)
