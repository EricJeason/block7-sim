"""把 API key 写入项目根 .env 文件(Godot 端弹窗 → POST /sim/api_key/set → 此模块)。

设计原则:
- 只改 DEEPSEEK_API_KEY 一行,其它行不动
- .env 不存在 → 从 .env.example 复制 + 改 key
- .env.example 也不存在 → 创建最简版只含 DEEPSEEK_API_KEY
- 写入失败不抛(只 log warning),内存中的 key 仍然生效
- 永不读取 .env 返回给客户端(key 是单向写,只能写入不能读出)
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# config.py 在 backend/src/,parent.parent = backend/,parent.parent.parent = 项目根
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"
_ENV_EXAMPLE_PATH = _PROJECT_ROOT / ".env.example"

# 匹配 DEEPSEEK_API_KEY=xxx 行(可有可无的空格 / 引号)
_API_KEY_LINE_RE = re.compile(r"^\s*DEEPSEEK_API_KEY\s*=.*$", re.MULTILINE)


def persist_api_key_to_env(new_key: str) -> bool:
    """把 new_key 写入项目根 .env 文件。

    返回:成功 True / 失败 False(失败原因仅 log,不抛)

    行为:
    - .env 存在:替换 DEEPSEEK_API_KEY= 行(如无则追加)
    - .env 不存在 但 .env.example 存在:复制 .env.example → .env,再替换 key
    - 都不存在:创建最简 .env 只含一行 key
    """
    if not new_key or not new_key.strip():
        logger.warning("[config_writer] 拒绝写入空 key")
        return False
    new_key = new_key.strip()
    new_line = f"DEEPSEEK_API_KEY={new_key}"

    try:
        if _ENV_PATH.exists():
            content = _ENV_PATH.read_text(encoding="utf-8")
            if _API_KEY_LINE_RE.search(content):
                # 替换现有行
                content = _API_KEY_LINE_RE.sub(new_line, content, count=1)
            else:
                # 没该行 → 追加(末尾加换行确保格式)
                if not content.endswith("\n"):
                    content += "\n"
                content += new_line + "\n"
            _ENV_PATH.write_text(content, encoding="utf-8")
            logger.info("[config_writer] 已更新 %s 的 DEEPSEEK_API_KEY", _ENV_PATH.name)
            return True

        if _ENV_EXAMPLE_PATH.exists():
            # 从模板生成
            content = _ENV_EXAMPLE_PATH.read_text(encoding="utf-8")
            content = _API_KEY_LINE_RE.sub(new_line, content, count=1)
            _ENV_PATH.write_text(content, encoding="utf-8")
            logger.info(
                "[config_writer] 从 .env.example 生成 %s 并写入 key", _ENV_PATH.name
            )
            return True

        # 最简兜底:只写一行
        _ENV_PATH.write_text(new_line + "\n", encoding="utf-8")
        logger.info("[config_writer] 创建最简 %s", _ENV_PATH.name)
        return True

    except OSError as exc:
        logger.warning("[config_writer] 写 .env 失败: %s", exc)
        return False
