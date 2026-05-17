"""Memory 子系统:CRUD + 关键词检索 + 时间衰减打分 + LLM 重要性打分。

参见设计文档 v0.2 §4。严禁引入 embedding / FTS5 / jieba。
所有 IO 异步 (aiosqlite)。
"""
from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass, field
from typing import Literal

import aiosqlite

logger = logging.getLogger(__name__)

MemoryType = Literal["observation", "reflection", "plan"]

_CHINESE_CHUNK_RE = re.compile(r"[一-龥]{2,}")
_JSON_ARRAY_RE = re.compile(r"\[[\s\d,]+\]")


@dataclass
class Memory:
    """单条 memory。memory_id 在入库前为 None,入库后由 MemoryStore.insert 回填。"""

    memory_id: int | None
    agent_id: str
    memory_type: MemoryType
    content: str
    importance: int                              # 1..10
    game_time: float
    real_time: float
    location: str | None
    related_agents: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    compressed: bool = False


@dataclass
class RetrievalResult:
    """检索结果:memory + 综合相关性得分。"""

    memory: Memory
    relevance_score: float


def _auto_extract_keywords(content: str) -> list[str]:
    """从 content 自动抽取 ≥2 字的中文片段作为关键词。

    Block C 用最简实现,不引入 jieba。Block E 如有需求再升级。
    """
    return _CHINESE_CHUNK_RE.findall(content)


def _row_to_memory(row: aiosqlite.Row) -> Memory:
    related = row["related_agents"]
    related_list = json.loads(related) if related else []
    keywords_str = row["keywords"] or ""
    keyword_list = keywords_str.split() if keywords_str else []
    return Memory(
        memory_id=int(row["memory_id"]),
        agent_id=str(row["agent_id"]),
        memory_type=row["memory_type"],  # type: ignore[arg-type]
        content=str(row["content"]),
        importance=int(row["importance"]),
        game_time=float(row["game_time"]),
        real_time=float(row["real_time"]),
        location=row["location"],
        related_agents=related_list,
        keywords=keyword_list,
        compressed=bool(row["compressed"]),
    )


class MemoryStore:
    """Memory 持久化与检索。所有 IO 异步。"""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    # ------------------------------------------------------------------ insert

    async def insert(self, memory: Memory) -> int:
        """插入一条 memory,返回新生成的 memory_id。

        若 memory.keywords 为空,自动从 content 提取中文片段作为关键词。
        """
        keywords = memory.keywords or _auto_extract_keywords(memory.content)
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO memories (
                    agent_id, memory_type, content, importance,
                    game_time, real_time, location, related_agents,
                    keywords, compressed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory.agent_id,
                    memory.memory_type,
                    memory.content,
                    memory.importance,
                    memory.game_time,
                    memory.real_time,
                    memory.location,
                    json.dumps(memory.related_agents, ensure_ascii=False),
                    " ".join(keywords),
                    1 if memory.compressed else 0,
                ),
            )
            await db.commit()
            new_id = cursor.lastrowid
        assert new_id is not None
        memory.memory_id = int(new_id)
        memory.keywords = keywords
        return int(new_id)

    async def insert_batch(self, memories: list[Memory]) -> list[int]:
        """批量插入,单 transaction。返回所有新 id(顺序与入参一致)。"""
        if not memories:
            return []
        new_ids: list[int] = []
        async with aiosqlite.connect(self.db_path) as db:
            for memory in memories:
                keywords = memory.keywords or _auto_extract_keywords(memory.content)
                cursor = await db.execute(
                    """
                    INSERT INTO memories (
                        agent_id, memory_type, content, importance,
                        game_time, real_time, location, related_agents,
                        keywords, compressed
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        memory.agent_id,
                        memory.memory_type,
                        memory.content,
                        memory.importance,
                        memory.game_time,
                        memory.real_time,
                        memory.location,
                        json.dumps(memory.related_agents, ensure_ascii=False),
                        " ".join(keywords),
                        1 if memory.compressed else 0,
                    ),
                )
                assert cursor.lastrowid is not None
                memory.memory_id = int(cursor.lastrowid)
                memory.keywords = keywords
                new_ids.append(int(cursor.lastrowid))
            await db.commit()
        return new_ids

    # --------------------------------------------------------------------- get

    async def get_by_id(self, memory_id: int) -> Memory | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM memories WHERE memory_id = ?", (memory_id,)
            ) as cursor:
                row = await cursor.fetchone()
        if row is None:
            return None
        return _row_to_memory(row)

    async def get_recent(
        self,
        agent_id: str,
        limit: int = 10,
        memory_types: list[MemoryType] | None = None,
        exclude_compressed: bool = True,
    ) -> list[Memory]:
        """按 game_time DESC 取该 agent 最近 N 条 memory。"""
        where_clauses = ["agent_id = ?"]
        params: list[object] = [agent_id]
        if exclude_compressed:
            where_clauses.append("compressed = 0")
        if memory_types:
            placeholders = ",".join("?" for _ in memory_types)
            where_clauses.append(f"memory_type IN ({placeholders})")
            params.extend(memory_types)
        sql = (
            "SELECT * FROM memories WHERE "
            + " AND ".join(where_clauses)
            + " ORDER BY game_time DESC LIMIT ?"
        )
        params.append(limit)
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, params) as cursor:
                rows = await cursor.fetchall()
        return [_row_to_memory(row) for row in rows]

    # ------------------------------------------------------------------ search

    async def search(
        self,
        agent_id: str,
        keywords: list[str],
        current_game_time: float,
        top_k: int = 5,
        time_decay_lambda: float = 0.005,
        exclude_compressed: bool = True,
    ) -> list[RetrievalResult]:
        """关键词检索 + 时间衰减打分。

        打分:
            keyword  = 命中关键词数 / max(1, len(keywords))      # 0..1
            recency  = exp(-lambda * max(0, current - mem_time))  # 0..1
            importance = importance / 10                           # 0..1
            relevance = 0.4*keyword + 0.4*recency + 0.2*importance

        实现策略:SQL 先按重要性粗筛 top_k * 5 候选,再在 Python 端精确打分。
        TODO(Block D): time_decay_lambda 假设 game_time 单位为秒、time_scale=1day/24min。
            若 GameClock 改了 time_scale,在调用方传新的 lambda 进来。
        """
        where_clauses = ["agent_id = ?"]
        params: list[object] = [agent_id]
        if exclude_compressed:
            where_clauses.append("compressed = 0")

        if keywords:
            keyword_clauses = []
            for kw in keywords:
                keyword_clauses.append("keywords LIKE ?")
                params.append(f"%{kw}%")
            where_clauses.append("(" + " OR ".join(keyword_clauses) + ")")

        sql = (
            "SELECT * FROM memories WHERE "
            + " AND ".join(where_clauses)
            + " ORDER BY importance DESC LIMIT ?"
        )
        # 粗筛区取 top_k * 5,留出空间做 Python 端精排
        params.append(max(top_k * 5, top_k))

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, params) as cursor:
                rows = await cursor.fetchall()

        candidates = [_row_to_memory(row) for row in rows]
        kw_count = max(1, len(keywords))
        scored: list[RetrievalResult] = []
        for mem in candidates:
            hits = sum(1 for kw in keywords if kw in mem.keywords or kw in mem.content)
            keyword_score = hits / kw_count
            delta = max(0.0, current_game_time - mem.game_time)
            recency_score = math.exp(-time_decay_lambda * delta)
            importance_score = mem.importance / 10.0
            relevance = (
                0.4 * keyword_score
                + 0.4 * recency_score
                + 0.2 * importance_score
            )
            scored.append(RetrievalResult(memory=mem, relevance_score=relevance))

        scored.sort(key=lambda r: r.relevance_score, reverse=True)
        return scored[:top_k]

    # -------------------------------------------------------------- compressed

    async def mark_compressed(self, memory_ids: list[int]) -> None:
        """把指定 memory 标记为 compressed,后续检索默认排除。"""
        if not memory_ids:
            return
        placeholders = ",".join("?" for _ in memory_ids)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                f"UPDATE memories SET compressed = 1 WHERE memory_id IN ({placeholders})",
                memory_ids,
            )
            await db.commit()

    async def count(self, agent_id: str) -> int:
        """统计该 agent 的活跃(未压缩)memory 数量。"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM memories WHERE agent_id = ? AND compressed = 0",
                (agent_id,),
            ) as cursor:
                row = await cursor.fetchone()
        return int(row[0]) if row else 0

    # =========================================================== Block G 查询

    async def get_in_time_range(
        self,
        agent_id: str,
        game_time_min: float,
        game_time_max: float,
        memory_types: list[MemoryType] | None = None,
        min_importance: int = 0,
        exclude_compressed: bool = True,
    ) -> list[Memory]:
        """拉指定 game_time 区间(左闭右开)+ 类型 + 重要性下限的 memory。

        Block G 反思器用此拉当日 memory(min=00:00, max=24:00),做高层 reflection。
        """
        where = ["agent_id = ?", "game_time >= ?", "game_time < ?", "importance >= ?"]
        params: list[object] = [agent_id, game_time_min, game_time_max, min_importance]
        if exclude_compressed:
            where.append("compressed = 0")
        if memory_types:
            placeholders = ",".join("?" for _ in memory_types)
            where.append(f"memory_type IN ({placeholders})")
            params.extend(memory_types)
        sql = (
            "SELECT * FROM memories WHERE "
            + " AND ".join(where)
            + " ORDER BY game_time ASC"
        )
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, params) as cursor:
                rows = await cursor.fetchall()
        return [_row_to_memory(row) for row in rows]

    async def get_older_than(
        self,
        agent_id: str,
        game_time_max: float,
        max_importance: int | None = None,
        exclude_types: list[MemoryType] | None = None,
        exclude_compressed: bool = True,
    ) -> list[Memory]:
        """拉指定 game_time 之前(< max)的 memory,用于压缩。

        Block G 压缩:
        - 拉 1-7 天前 importance < 5 → 合并日常摘要
        - 拉 7 天以前非 reflection 且 importance < 7 → 标记 compressed
        """
        where = ["agent_id = ?", "game_time < ?"]
        params: list[object] = [agent_id, game_time_max]
        if exclude_compressed:
            where.append("compressed = 0")
        if max_importance is not None:
            where.append("importance <= ?")
            params.append(max_importance)
        if exclude_types:
            placeholders = ",".join("?" for _ in exclude_types)
            where.append(f"memory_type NOT IN ({placeholders})")
            params.extend(exclude_types)
        sql = (
            "SELECT * FROM memories WHERE "
            + " AND ".join(where)
            + " ORDER BY game_time ASC"
        )
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, params) as cursor:
                rows = await cursor.fetchall()
        return [_row_to_memory(row) for row in rows]


# ============================================================================
#                           Importance Scorer (LLM)
# ============================================================================


class ImportanceScorer:
    """批量为 memory 打 1–10 重要性分。用 V4-Flash non-think,单次 5 条。"""

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

    def __init__(self, llm_client, model: str) -> None:
        """llm_client: DeepSeekClient 实例; model: settings.deepseek_model_flash。"""
        self.llm = llm_client
        self.model = model

    async def score(self, contents: list[str]) -> list[int]:
        """对 contents (长度 ≤ BATCH_SIZE) 打分,返回长度相同的整数列表。

        鲁棒性:JSON 解析失败 / 长度不对 / 越界 → 兜底为 5,clamp 到 [1,10]。
        单次调用不重试 — 非关键路径,失败用兜底而不是阻塞。
        """
        n = len(contents)
        if n == 0:
            return []
        if n > self.BATCH_SIZE:
            raise ValueError(
                f"score() 仅支持单批 ≤ {self.BATCH_SIZE},收到 {n}。请用 score_many。"
            )

        items_str = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(contents))
        prompt = self.SCORE_PROMPT.format(n=n, items=items_str)

        # 延迟导入避免循环 import (DeepSeekClient 未来可能反向引用 memory 类型)
        from src.llm.deepseek import ThinkMode

        try:
            response = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                mode=ThinkMode.NON_THINK,
                temperature=0.3,
                max_tokens=64,
            )
        except Exception as exc:  # noqa: BLE001 — 非关键路径,失败兜底
            logger.warning("[importance] LLM 调用失败,用兜底 5: %s", exc)
            return [5] * n

        return self._parse_scores(response.content, n)

    async def score_many(self, contents: list[str]) -> list[int]:
        """对任意长度的 contents 批量打分,内部按 BATCH_SIZE 切片串行调用。"""
        results: list[int] = []
        for start in range(0, len(contents), self.BATCH_SIZE):
            batch = contents[start : start + self.BATCH_SIZE]
            results.extend(await self.score(batch))
        return results

    def _parse_scores(self, raw_content: str, expected_n: int) -> list[int]:
        """从 LLM 返回中抓出 JSON 整数数组,长度补齐到 expected_n,值 clamp 到 [1,10]。"""
        match = _JSON_ARRAY_RE.search(raw_content)
        if match is None:
            logger.warning(
                "[importance] LLM 返回无法解析 JSON,用兜底 5: %r", raw_content[:200]
            )
            return [5] * expected_n

        try:
            arr = json.loads(match.group(0))
        except json.JSONDecodeError:
            logger.warning(
                "[importance] JSON.loads 失败,用兜底 5: %r", match.group(0)[:200]
            )
            return [5] * expected_n

        if not isinstance(arr, list):
            return [5] * expected_n

        # 截断 / 补齐
        if len(arr) > expected_n:
            arr = arr[:expected_n]
        elif len(arr) < expected_n:
            arr = list(arr) + [5] * (expected_n - len(arr))

        # clamp 到 [1, 10],非整数兜底为 5
        clamped: list[int] = []
        for v in arr:
            try:
                iv = int(v)
            except (TypeError, ValueError):
                iv = 5
            clamped.append(max(1, min(10, iv)))
        return clamped
