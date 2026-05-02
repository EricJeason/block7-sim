# Day 1 Block C — Memory 子系统(SQLite + 关键词检索 + 重要性打分)

> **派发对象**:Claude Desktop App 的 Code session(关闭 worktree,main 分支直接工作)
> **预计时长**:30–45 分钟
> **预计真实 API 成本**:¥0.3–0.8(用于重要性打分集成测试)
> **依赖**:Block A 与 Block B 已实落

---

## 任务上下文

**项目**:Block-7 生成式智能体社会模拟器
**当前阶段**:Day 1, Block C
**架构总纲**:`docs/Project_Design_Document_v0_2.md`,**重点章节 §4(Memory 子系统)**
**Block B 关键产出可复用**:`DeepSeekClient`(Block C 用 V4-Flash non-think 做批量打分)、`ThinkMode`、`LLMResponse`

**核心设计原则**(v0.2 §4):
- **不使用 embedding / 向量检索**——只用 SQLite `LIKE` 关键词粗筛 + 时间衰减 + LLM in-context 精筛
- **Memory 类型分三种**:`observation`(观察)、`reflection`(反思,Block E 写入)、`plan`(计划,Block D 写入)
- **重要性打分**:每条 memory 入库时记一个 1–10 的 importance,影响检索权重
- **批量打分**:用 V4-Flash non-think,一次 5 条减少 API 调用次数

---

## 任务目标(全部达成才算通过)

| # | 目标 | 验收 |
|---|---|---|
| 1 | SQLite schema 定义清晰,支持异步操作 | 建表脚本可重复执行,DROP IF EXISTS 安全 |
| 2 | Memory CRUD 接口完整 | 单测 ≥ 90% 路径覆盖 |
| 3 | 关键词检索 + 时间衰减打分 | 可按 query 返回 top-k,顺序合理 |
| 4 | 重要性批量打分(LLM) | 单次调用打 5 条,返回 5 个 1–10 整数 |
| 5 | Memory 压缩接口骨架 | 函数可调用,Block E 阶段填充逻辑 |
| 6 | 集成测试:存 → 查 → 打分 端到端跑通 | 真实 API,1 次 LLM 调用 |

---

## 详细规格

### C.1 SQLite Schema — `backend/src/memory/schema.py`

#### C.1.1 表结构

```python
"""SQLite schema 定义。所有表用 IF NOT EXISTS,允许幂等执行。"""
from __future__ import annotations

# 表 1:agents — 角色基本信息(Block C 不写入,只建表;Block D 起会用)
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

# 表 2:memories — 核心 memory 表
CREATE_MEMORIES = """
CREATE TABLE IF NOT EXISTS memories (
    memory_id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    memory_type TEXT NOT NULL CHECK(memory_type IN ('observation', 'reflection', 'plan')),
    content TEXT NOT NULL,
    importance INTEGER NOT NULL DEFAULT 5 CHECK(importance BETWEEN 1 AND 10),
    game_time REAL NOT NULL,        -- 游戏内时间戳(秒)
    real_time REAL NOT NULL,        -- 真实时间戳(用于排序/调试)
    location TEXT,                  -- 发生地点(可空)
    related_agents TEXT,            -- JSON 数组字符串,例如 '["agent_02","agent_03"]'
    keywords TEXT NOT NULL,         -- 空格分隔的关键词,用于 LIKE 检索
    compressed INTEGER DEFAULT 0,   -- 0=原始, 1=已被压缩归档
    FOREIGN KEY (agent_id) REFERENCES agents(agent_id)
);
"""

# 索引:加速按 agent + 时间检索
CREATE_INDEX_AGENT_TIME = """
CREATE INDEX IF NOT EXISTS idx_memories_agent_time
ON memories(agent_id, game_time DESC);
"""

# 索引:加速重要性筛选
CREATE_INDEX_IMPORTANCE = """
CREATE INDEX IF NOT EXISTS idx_memories_importance
ON memories(agent_id, importance DESC);
"""

# 表 3:events — 同场所事件传播(Block D 用,这里仅建表)
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

ALL_DDL = [
    CREATE_AGENTS,
    CREATE_MEMORIES,
    CREATE_INDEX_AGENT_TIME,
    CREATE_INDEX_IMPORTANCE,
    CREATE_EVENTS,
    CREATE_INDEX_EVENT_LOC_TIME,
]


async def init_db(db_path: str) -> None:
    """初始化数据库,执行所有 DDL。幂等,可重复调用。"""
    import aiosqlite
    async with aiosqlite.connect(db_path) as db:
        for ddl in ALL_DDL:
            await db.execute(ddl)
        await db.commit()
```

#### C.1.2 设计要点

1. **`game_time` 用 REAL**(Unix 时间戳风格,秒级浮点)。Block D 的 GameClock 与之配合
2. **`keywords` 字段冗余存储**——存入时已经分好词,避免每次检索时实时分词
3. **不用 FTS5**:虽然 SQLite 自带的全文检索功能更强,但中文分词需要额外配置(jieba 等),引入依赖。Block C 阶段用最简单的 `LIKE %keyword%`,**性能足够 12 个 agent 的规模**
4. **`compressed` 字段**:Block E 的 reflection 会把多条原始 memory 压缩为一条总结,被压缩的 memory `compressed=1`,检索时默认排除

---

### C.2 Memory CRUD — `backend/src/memory/store.py`

#### C.2.1 数据类与接口

```python
"""Memory 子系统:CRUD + 关键词检索 + 时间衰减打分。"""
from __future__ import annotations
import json
import time
import math
from dataclasses import dataclass, field
from typing import Literal
import aiosqlite

MemoryType = Literal["observation", "reflection", "plan"]


@dataclass
class Memory:
    memory_id: int | None     # 入库前为 None
    agent_id: str
    memory_type: MemoryType
    content: str
    importance: int           # 1–10
    game_time: float
    real_time: float
    location: str | None
    related_agents: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    compressed: bool = False


@dataclass
class RetrievalResult:
    memory: Memory
    relevance_score: float    # 综合得分(关键词匹配 + 时间衰减 + 重要性)


class MemoryStore:
    """Memory 持久化与检索。所有 IO 异步。"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def insert(self, memory: Memory) -> int:
        """插入一条 memory,返回新生成的 memory_id。"""
        ...

    async def insert_batch(self, memories: list[Memory]) -> list[int]:
        """批量插入(单 transaction),返回所有新 id。"""
        ...

    async def get_by_id(self, memory_id: int) -> Memory | None:
        ...

    async def get_recent(
        self,
        agent_id: str,
        limit: int = 10,
        memory_types: list[MemoryType] | None = None,
        exclude_compressed: bool = True,
    ) -> list[Memory]:
        """按 game_time DESC 取最近 N 条。"""
        ...

    async def search(
        self,
        agent_id: str,
        keywords: list[str],
        current_game_time: float,
        top_k: int = 5,
        time_decay_lambda: float = 0.005,   # 衰减常数,见下
    ) -> list[RetrievalResult]:
        """关键词检索 + 时间衰减打分。
        
        打分公式:
            keyword_score = 命中关键词数 / len(keywords)         # 0..1
            recency_score = exp(-lambda * (current - mem_time))  # 0..1,越近越大
            importance_score = importance / 10                   # 0..1
            relevance = 0.4 * keyword_score + 0.4 * recency_score + 0.2 * importance_score
        
        返回按 relevance DESC 的前 top_k 条。
        """
        ...

    async def mark_compressed(self, memory_ids: list[int]) -> None:
        """把指定 memory 标记为 compressed,后续检索默认排除。"""
        ...

    async def count(self, agent_id: str) -> int:
        """统计该 agent 的活跃(未压缩)memory 数量。"""
        ...
```

#### C.2.2 实现要点

1. **关键词检索的 SQL**(参考实现):

```python
# WHERE 子句:每个关键词一个 LIKE,OR 连接
where_clauses = ["agent_id = ?"]
params = [agent_id]
if exclude_compressed:
    where_clauses.append("compressed = 0")
keyword_clauses = []
for kw in keywords:
    keyword_clauses.append("keywords LIKE ?")
    params.append(f"%{kw}%")
if keyword_clauses:
    where_clauses.append("(" + " OR ".join(keyword_clauses) + ")")

sql = f"SELECT * FROM memories WHERE {' AND '.join(where_clauses)} ORDER BY importance DESC LIMIT ?"
params.append(top_k * 5)   # 先粗筛 top_k * 5 条,再 Python 端精确打分
```

2. **时间衰减常数 `lambda = 0.005` 推导**:游戏时间 1 小时 = 3600 秒,`exp(-0.005 * 3600) = 1.5e-8`,意味着 1 小时前的 memory 衰减得几乎为 0。**这个 lambda 适合"游戏内 1 天 = 真实 24 分钟"的快进比**,后续 Block D 如果调了 time_scale 要回来调这个。**留 TODO 注释**。

3. **`insert` 时如果 `keywords=[]`,自动从 content 提取**:用最朴素的方式——分词只保留 ≥2 字的中文片段(用正则 `re.findall(r'[\u4e00-\u9fa5]{2,}', content)` 兜底)。**这是为了让上游不传 keywords 也能跑**,Block D 写入 memory 时不必每次手动提取。

4. **所有 SQL 用参数化绑定**,绝不拼字符串,防注入(虽然单机没人攻击你,但是好习惯)。

---

### C.3 重要性批量打分 — `backend/src/memory/store.py` 内的辅助类

#### C.3.1 接口

```python
class ImportanceScorer:
    """批量为 memory 打 1–10 重要性分。用 V4-Flash non-think。"""

    BATCH_SIZE = 5

    SCORE_PROMPT = """请为以下 {n} 条 memory 各打一个 1–10 的重要性分数。

打分标准:
- 1–3:日常琐事(吃饭、走路、寒暄)
- 4–6:有一定影响的事件(工作进展、人际互动)
- 7–8:重要决定或情感事件(重大冲突、感情变化)
- 9–10:转折性事件(死亡、重大启示、关系彻底改变)

memory 列表:
{items}

只返回一个 JSON 数组,长度等于 memory 数量,每个元素是 1–10 的整数。
不要任何解释。例如:[3, 7, 5, 4, 8]
"""

    def __init__(self, llm_client, model: str):
        """llm_client: DeepSeekClient 实例;model: 'deepseek-v4-flash'(从 settings 注入)"""
        ...

    async def score(self, contents: list[str]) -> list[int]:
        """对 contents(长度 ≤ BATCH_SIZE)打分,返回长度相同的整数列表。
        
        鲁棒性要求:
        - 如果 LLM 返回的 JSON 解析失败,日志告警并返回全 5(中位数兜底)
        - 如果返回数组长度不对,截断或补 5 到正确长度
        - 如果某个值不在 1–10,clamp 到 [1, 10]
        - 单次调用不重试(因为是非关键路径,失败用兜底)
        """
        ...

    async def score_many(self, contents: list[str]) -> list[int]:
        """对任意长度的 contents 批量打分,内部按 BATCH_SIZE 切片。"""
        ...
```

#### C.3.2 实现要点

1. **JSON 解析鲁棒**:LLM 偶尔会在 JSON 前后加文字,先用正则 `re.search(r'\[[\s\d,]+\]', content)` 抓出 JSON 部分再 `json.loads`
2. **不并发调用**:`score_many` 内的多个 batch **串行**调用(避免重复触发 cache miss + 简化错误处理)
3. **返回值长度严格等于输入长度**——即使 LLM 出错也用 5 兜底,不让上游 zip 出问题

---

### C.4 Memory 压缩骨架 — `backend/src/memory/compression.py`

**Block C 只搭骨架,不实现真实逻辑**(Block E Reflection 阶段才填充)。

```python
"""Memory 压缩:把 7 天前的 memory 压缩为 reflection。Block E 实现具体逻辑。"""
from __future__ import annotations
from .store import MemoryStore, Memory


class MemoryCompressor:
    """将旧 memory 压缩为单条 reflection。"""

    DAYS_THRESHOLD = 7   # 游戏内 7 天前的 memory 进入压缩候选

    def __init__(self, store: MemoryStore, llm_client, model: str):
        self.store = store
        self.llm = llm_client
        self.model = model

    async def compress_old_memories(self, agent_id: str, current_game_time: float) -> int:
        """触发一次压缩,返回被压缩的 memory 数量。
        
        Block C 阶段:返回 0 即可(不实际压缩)。
        Block E 阶段:实现真实压缩逻辑。
        """
        # TODO(Block E): 实现真实压缩
        return 0
```

---

### C.5 单元测试 — `backend/tests/test_memory.py`

不烧 API 钱,纯本地测试。

```python
"""Memory CRUD + 检索单元测试。不调用真实 LLM。"""
import os
import time
import pytest
from src.memory.schema import init_db
from src.memory.store import MemoryStore, Memory


@pytest.fixture
async def store(tmp_path):
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)
    return MemoryStore(db_path)


@pytest.mark.asyncio
async def test_insert_and_get(store):
    m = Memory(
        memory_id=None, agent_id="a1", memory_type="observation",
        content="今天买了一斤苹果", importance=4,
        game_time=100.0, real_time=time.time(),
        location="水果店", keywords=["买", "苹果"],
    )
    mid = await store.insert(m)
    assert mid > 0
    fetched = await store.get_by_id(mid)
    assert fetched is not None
    assert fetched.content == "今天买了一斤苹果"


@pytest.mark.asyncio
async def test_get_recent_orders_by_time(store):
    for i in range(5):
        await store.insert(Memory(
            memory_id=None, agent_id="a1", memory_type="observation",
            content=f"事件 {i}", importance=5,
            game_time=float(i * 10), real_time=time.time(),
            location="X", keywords=[f"事件{i}"],
        ))
    recent = await store.get_recent("a1", limit=3)
    assert len(recent) == 3
    # 应按 game_time DESC,即 i=4, 3, 2
    assert recent[0].content == "事件 4"
    assert recent[2].content == "事件 2"


@pytest.mark.asyncio
async def test_search_keyword_match(store):
    await store.insert(Memory(
        memory_id=None, agent_id="a1", memory_type="observation",
        content="买了苹果", importance=5, game_time=100.0, real_time=time.time(),
        location="X", keywords=["苹果", "购买"],
    ))
    await store.insert(Memory(
        memory_id=None, agent_id="a1", memory_type="observation",
        content="散步", importance=2, game_time=99.0, real_time=time.time(),
        location="Y", keywords=["散步"],
    ))
    results = await store.search("a1", keywords=["苹果"], current_game_time=100.0, top_k=5)
    assert len(results) == 1
    assert "苹果" in results[0].memory.content


@pytest.mark.asyncio
async def test_search_time_decay(store):
    """同样关键词,新 memory 应排在前。"""
    await store.insert(Memory(
        memory_id=None, agent_id="a1", memory_type="observation",
        content="老的苹果记忆", importance=5,
        game_time=0.0, real_time=time.time(),  # 很久以前
        location="X", keywords=["苹果"],
    ))
    await store.insert(Memory(
        memory_id=None, agent_id="a1", memory_type="observation",
        content="新的苹果记忆", importance=5,
        game_time=99.0, real_time=time.time(),  # 1 秒前
        location="X", keywords=["苹果"],
    ))
    results = await store.search("a1", keywords=["苹果"], current_game_time=100.0, top_k=5)
    assert results[0].memory.content == "新的苹果记忆"


@pytest.mark.asyncio
async def test_compressed_excluded_by_default(store):
    mid = await store.insert(Memory(
        memory_id=None, agent_id="a1", memory_type="observation",
        content="将被压缩", importance=5,
        game_time=100.0, real_time=time.time(),
        location="X", keywords=["压缩"],
    ))
    await store.mark_compressed([mid])
    recent = await store.get_recent("a1", limit=10)
    assert len(recent) == 0


@pytest.mark.asyncio
async def test_keyword_auto_extract(store):
    """如果 keywords 为空,应从 content 自动提取中文片段。"""
    m = Memory(
        memory_id=None, agent_id="a1", memory_type="observation",
        content="李明在杂货店买了苹果", importance=5,
        game_time=100.0, real_time=time.time(),
        location="杂货店", keywords=[],
    )
    mid = await store.insert(m)
    fetched = await store.get_by_id(mid)
    # 应至少包含"李明"、"杂货店"、"苹果"中的某些片段
    assert any(kw in fetched.keywords for kw in ["李明", "杂货店", "苹果"])
```

---

### C.6 集成测试 — `backend/tests/test_memory_integration.py`

**烧少量真实 API 钱**(预计 ¥0.05–0.2)。

```python
"""端到端测试:存 memory → LLM 打分 → 检索。"""
import time
import pytest
from src.config import settings
from src.memory.schema import init_db
from src.memory.store import MemoryStore, Memory, ImportanceScorer
from src.llm.deepseek import DeepSeekClient

pytestmark = pytest.mark.skipif(
    settings.deepseek_api_key in ("", "your_api_key_here"),
    reason="需要真实 DEEPSEEK_API_KEY",
)


@pytest.mark.asyncio
async def test_importance_scoring_e2e(tmp_path):
    db = str(tmp_path / "int.db")
    await init_db(db)
    store = MemoryStore(db)
    
    client = DeepSeekClient(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)
    scorer = ImportanceScorer(client, model=settings.deepseek_model_flash)

    contents = [
        "今天和老朋友重逢,他告诉我妻子去世了",   # 高
        "买了一根冰棍",                            # 低
        "在镇广场看到陌生人和镇长激烈争吵",        # 中高
        "起床、刷牙、吃早饭",                      # 低
        "决定明天去外地寻找失踪的儿子",            # 高
    ]
    scores = await scorer.score(contents)
    
    assert len(scores) == 5
    assert all(1 <= s <= 10 for s in scores)
    
    # 弱断言:第 1、5 条应高于第 2、4 条
    print(f"实测分数: {scores}")
    assert scores[0] > scores[1], f"重逢/冰棍 应 > 买冰棍, 实际 {scores[0]} vs {scores[1]}"
    assert scores[4] > scores[3], f"决定外出 应 > 起床洗漱, 实际 {scores[4]} vs {scores[3]}"

    await client.aclose()
```

---

## 执行流程

1. ✅ 验证 Block A/B 仍完好:`pytest tests/test_smoke.py -v`
2. 🛠 实现 `schema.py`
3. 🛠 实现 `store.py` 的 `MemoryStore`
4. 🛠 实现 `store.py` 的 `ImportanceScorer`
5. 🛠 实现 `compression.py` 骨架
6. 🧪 跑 `test_memory.py`(不烧钱),全绿才进入下一步
7. 🔥 跑 `test_memory_integration.py`(烧少量钱)
8. ✅ git commit:`Day 1 Block C: Memory subsystem (SQLite + keyword search + LLM scoring)`

---

## 报告格式

1. 文件清单(memory 模块 + 测试)
2. 单元测试结果(应有 6 个新 PASSED + 之前 4 个继续 PASSED)
3. 集成测试 LLM 打分实测分数(那 5 条 memory 的真实分数)
4. 集成测试成本与延迟
5. 新 commit hash
6. 下一步建议

报告末尾:

> Block C 完成。请 Eric 在主对话回复"Block C 完成,请发 Block D 任务包"。

---

## 严禁事项

1. **不引入 jieba / FTS5 / 任何中文分词库**——`re.findall(r'[\u4e00-\u9fa5]{2,}', text)` 已足够 Block C 使用
2. **不引入 ORM**(SQLAlchemy 等)——直接写 SQL,简单可控
3. **不实现真实 memory 压缩**——`compression.py` 留 TODO,Block E 实现
4. **不修改 Block A/B 已交付的功能**
5. **集成测试只跑 1 次 LLM 调用**(5 条打分 = 1 次 batch 调用)。**不要循环测多次**——成本会指数增长
6. **遇决策不确定**,留 `# TODO(Block X)` 继续推进,不要询问 Eric
