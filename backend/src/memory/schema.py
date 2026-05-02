"""SQLite schema 定义。所有表用 IF NOT EXISTS,允许幂等执行。

参见设计文档 v0.2 §4(Memory 子系统):
- agents:角色基本信息(Block C 不写入,只建表)
- memories:核心 memory 表(observation / reflection / plan)
- events:同场所事件传播(Block D 用)

不引入 FTS5 / jieba / 任何中文分词依赖,关键词检索走 LIKE。
"""
from __future__ import annotations

import aiosqlite

SCHEMA_VERSION: int = 1


CREATE_AGENTS = """
CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    age INTEGER NOT NULL,
    occupation TEXT NOT NULL,
    personality TEXT NOT NULL,
    background TEXT NOT NULL,
    current_location TEXT,
    current_mood TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
"""

CREATE_MEMORIES = """
CREATE TABLE IF NOT EXISTS memories (
    memory_id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    memory_type TEXT NOT NULL CHECK(memory_type IN ('observation', 'reflection', 'plan')),
    content TEXT NOT NULL,
    importance INTEGER NOT NULL DEFAULT 5 CHECK(importance BETWEEN 1 AND 10),
    game_time REAL NOT NULL,
    real_time REAL NOT NULL,
    location TEXT,
    related_agents TEXT,
    keywords TEXT NOT NULL,
    compressed INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (agent_id) REFERENCES agents(agent_id)
);
"""

CREATE_INDEX_AGENT_TIME = """
CREATE INDEX IF NOT EXISTS idx_memories_agent_time
ON memories(agent_id, game_time DESC);
"""

CREATE_INDEX_IMPORTANCE = """
CREATE INDEX IF NOT EXISTS idx_memories_importance
ON memories(agent_id, importance DESC);
"""

CREATE_EVENTS = """
CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id TEXT NOT NULL,
    location TEXT NOT NULL,
    description TEXT NOT NULL,
    game_time REAL NOT NULL,
    FOREIGN KEY (actor_id) REFERENCES agents(agent_id)
);
"""

CREATE_INDEX_EVENT_LOC_TIME = """
CREATE INDEX IF NOT EXISTS idx_events_loc_time
ON events(location, game_time DESC);
"""

ALL_DDL: list[str] = [
    CREATE_AGENTS,
    CREATE_MEMORIES,
    CREATE_INDEX_AGENT_TIME,
    CREATE_INDEX_IMPORTANCE,
    CREATE_EVENTS,
    CREATE_INDEX_EVENT_LOC_TIME,
]


async def init_db(db_path: str) -> None:
    """初始化数据库,执行所有 DDL。幂等,可重复调用。"""
    async with aiosqlite.connect(db_path) as db:
        for ddl in ALL_DDL:
            await db.execute(ddl)
        await db.commit()
