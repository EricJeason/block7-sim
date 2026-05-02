"""端到端集成测试:存 memory → LLM 打分 → 检索。

烧少量真实 API 钱(预计 ¥0.05–0.2)。严禁 #5:只跑 1 次 LLM 调用。
"""
from __future__ import annotations

import pytest

from src.config import settings
from src.llm.deepseek import DeepSeekClient
from src.memory.schema import init_db
from src.memory.store import ImportanceScorer, MemoryStore

pytestmark = pytest.mark.skipif(
    settings.deepseek_api_key in ("", "your_api_key_here"),
    reason="需要真实 DEEPSEEK_API_KEY",
)


async def test_importance_scoring_e2e(tmp_path) -> None:
    db = str(tmp_path / "int.db")
    await init_db(db)
    _store = MemoryStore(db)  # 验证 schema 可用,不写入(单调用约束)

    client = DeepSeekClient(
        api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url
    )
    try:
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
        print(f"\n实测分数: {scores}")
        assert scores[0] > scores[1], (
            f"重逢/丧妻 应 > 冰棍, 实际 {scores[0]} vs {scores[1]}"
        )
        assert scores[4] > scores[3], (
            f"决定外出 应 > 起床洗漱, 实际 {scores[4]} vs {scores[3]}"
        )
    finally:
        await client.aclose()
