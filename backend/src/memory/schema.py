"""SQLite schema 定义。

Block C 在此处声明所有表(observations / reflections / plans / agents / locations 等)
以及索引、迁移版本号。Block A 仅占位。
"""
from __future__ import annotations


SCHEMA_VERSION: int = 0


def init_schema() -> str:
    """返回完整 DDL 字符串,供 store.py 在启动时执行。

    Block C 实现。
    """
    raise NotImplementedError("Block C 实现")
