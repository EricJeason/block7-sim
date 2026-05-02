"""B.3 缓存命中率验证 — 真实 API 调用。

运行方式:
    cd backend
    pytest tests/test_cache_hit_rate.py -v -s --no-header

要求:
    .env 中 DEEPSEEK_API_KEY 已填真实 key

预期成本:元1–3
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import pytest_asyncio

from src.config import settings
from src.llm.deepseek import DeepSeekClient, ThinkMode
from src.llm.prompt_builder import AgentPersona, AgentRuntimeState, PromptBuilder

pytestmark = pytest.mark.skipif(
    settings.deepseek_api_key in ("", "your_api_key_here"),
    reason="需要真实 DEEPSEEK_API_KEY 才能运行命中率验证",
)


@pytest_asyncio.fixture
async def client():
    c = DeepSeekClient(
        api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url
    )
    yield c
    await c.aclose()


# 固定 persona — 30 次调用复用同一个,Layer 0+1 应被缓存命中
TEST_PERSONA = AgentPersona(
    agent_id="test_agent_01",
    name="李明",
    age=32,
    occupation="小镇杂货店老板",
    personality="沉稳、热情、对小镇老主顾如数家珍",
    background=(
        "李明在镇东头开了 8 年杂货店。妻子在镇医院做护士。"
        "喜欢和客人闲聊,但晚上 8 点准时打烊回家。"
    ),
)


def make_state(turn: int) -> AgentRuntimeState:
    """生成第 turn 轮的动态状态(每轮都不同,模拟真实游戏循环)。"""
    return AgentRuntimeState(
        current_location="杂货店",
        current_mood="平静",
        recent_memories=[
            f"刚刚有个客人买了第 {turn} 包香烟",
            "妻子打来电话提醒晚上吃饭",
        ],
        game_time=f"Day 1, {10 + turn // 6}:{(turn * 10) % 60:02d}",
    )


# 命中率统计配置:总轮数 + 跳过冷启动的预热轮数
TOTAL_TURNS = 35
WARMUP_TURNS = 5  # 前 5 轮算预热,只统计第 6 轮起的 30 轮命中率


@pytest.mark.asyncio
async def test_cache_hit_rate(client):
    """跑 TOTAL_TURNS 次调用,验证去除前 WARMUP_TURNS 轮预热后的命中率 ≥ 90%。"""
    total_input = 0
    total_cache_hit = 0
    total_cost = 0.0
    latencies: list[float] = []
    per_turn_log: list[dict] = []

    for turn in range(TOTAL_TURNS):
        state = make_state(turn)
        messages = PromptBuilder.assemble_messages(
            persona=TEST_PERSONA,
            state=state,
            task_prompt="请用一句话描述你现在最想做的事(20 字以内)。",
        )
        resp = await client.chat(
            messages=messages,
            model=settings.deepseek_model_pro,
            mode=ThinkMode.NON_THINK,
            max_tokens=80,
        )
        per_turn_log.append(
            {
                "turn": turn,
                "input": resp.usage.input_tokens,
                "cache_hit": resp.usage.cache_hit_tokens,
                "cost": resp.usage.cost_yuan,
                "latency_ms": resp.usage.latency_ms,
            }
        )
        # 只统计预热之后的轮次
        if turn >= WARMUP_TURNS:
            total_input += resp.usage.input_tokens
            total_cache_hit += resp.usage.cache_hit_tokens
            total_cost += resp.usage.cost_yuan
            latencies.append(resp.usage.latency_ms)

        print(
            f"[turn {turn:2d}{'(warmup)' if turn < WARMUP_TURNS else ''}] "
            f"input={resp.usage.input_tokens} "
            f"cache_hit={resp.usage.cache_hit_tokens} "
            f"cost=元{resp.usage.cost_yuan:.4f} "
            f"lat={resp.usage.latency_ms:.0f}ms"
        )

    hit_rate = total_cache_hit / total_input if total_input else 0.0
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    p95_latency = (
        sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0.0
    )

    print("\n===== 命中率验证总结 =====")
    print(f"总轮数:{TOTAL_TURNS} (跳过前 {WARMUP_TURNS} 轮预热)")
    print(f"统计轮数:{len(latencies)}")
    print(f"总输入 tokens:{total_input}")
    print(f"总缓存命中 tokens:{total_cache_hit}")
    print(f"命中率:{hit_rate:.1%}")
    print(f"总成本(预热后):元{total_cost:.4f}")
    print(f"平均延迟:{avg_latency:.0f} ms")
    print(f"P95 延迟:{p95_latency:.0f} ms")

    # 也把数据写到 JSON 文件,便于跨平台/跨终端编码读取
    summary_path = Path(__file__).parent.parent / "logs" / "cache_hit_rate_last_run.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(
            {
                "total_turns": TOTAL_TURNS,
                "warmup_turns": WARMUP_TURNS,
                "stat_turns": len(latencies),
                "total_input_tokens": total_input,
                "total_cache_hit_tokens": total_cache_hit,
                "hit_rate": hit_rate,
                "total_cost_yuan_post_warmup": total_cost,
                "avg_latency_ms": avg_latency,
                "p95_latency_ms": p95_latency,
                "per_turn": per_turn_log,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"详细日志已写入:{summary_path}")

    # 硬验收
    assert hit_rate >= 0.90, f"命中率 {hit_rate:.1%} 未达 90%"
    assert avg_latency < 5000, f"平均延迟 {avg_latency:.0f}ms 超过 5s"
