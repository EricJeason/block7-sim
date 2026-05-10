"""Block E 真实 API 集成测试:跑林秋一次完整的 daily + fine 链路。

跳过条件:无 DEEPSEEK_API_KEY。
预计成本:¥0.02-0.05 / 次。

运行:
    cd backend
    pytest tests/test_planning_integration.py -v -s
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.agent.planning import (
    LLMPlanner,
    LocationLoader,
    PersonaLoader,
)
from src.agent.runtime import AgentRuntime, ThinkingReason
from src.config import settings
from src.llm.deepseek import DeepSeekClient

pytestmark = pytest.mark.skipif(
    settings.deepseek_api_key in ("", "your_api_key_here"),
    reason="需要真实 DEEPSEEK_API_KEY",
)


@pytest.mark.asyncio
async def test_planner_real_api_smoke() -> None:
    """跑林秋(agent_01)的真实 plan_next_actions 一次,打印 daily + fine 结果。

    断言只做最基本的:有返回、字段合法。质量靠人眼看 stdout。
    """
    # 默认 120s timeout 足够覆盖 Pro think_high 规划(实测 30-60s)
    client = DeepSeekClient(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )
    try:
        planner = LLMPlanner(
            llm=client,
            memory_store=None,  # 暂不联 memory,用空集
            persona_loader=PersonaLoader(),
            location_loader=LocationLoader(),
            model_pro=settings.deepseek_model_pro,
            model_flash=settings.deepseek_model_flash,
        )

        agent = AgentRuntime(
            agent_id="agent_01",
            persona_name="林秋",
            current_location="lao_song_plaza",
            current_mood="平静",
        )

        # game_time = Day 1 早上 08:30
        game_time = 8 * 3600.0 + 30 * 60.0

        print("\n" + "=" * 76)
        print("Block E 真实 API 集成测试 — 林秋 (agent_01) 早上 08:30")
        print("=" * 76)

        actions = await planner.plan_next_actions(
            agent,
            ThinkingReason.LOW_WATERMARK,
            {"game_time": game_time},
        )

        # ---------- 打印 daily plan ----------
        daily = planner._daily_plans.get("agent_01")
        assert daily is not None, "daily plan 应被生成并缓存"
        print(f"\n[Daily Plan] day={daily.game_day + 1},共 {len(daily.slots)} 个时段:")
        for i, slot in enumerate(daily.slots, 1):
            notes = f" ({slot.notes})" if slot.notes else ""
            print(
                f"  {i}. {slot.start_time}-{slot.end_time}  "
                f"@ {slot.location:24s}  {slot.activity}{notes}"
            )

        # ---------- 打印 fine actions ----------
        print(f"\n[Fine Actions] 共 {len(actions)} 个动作:")
        for i, act in enumerate(actions, 1):
            args_text = (
                ", ".join(f"{k}={v}" for k, v in act.args.items())
                if act.args
                else "(无参数)"
            )
            print(
                f"  {i}. {act.action_type:12s}  "
                f"{act.duration_seconds:5.1f}s  {args_text}"
            )
        total_seconds = sum(a.duration_seconds for a in actions)
        print(f"  总时长:{total_seconds:.0f}s ({total_seconds / 60:.1f} min)")

        # ---------- 写日志便于回看(避免 Windows codepage 截断中文)----------
        log_path = (
            Path(__file__).parent.parent
            / "logs"
            / "planner_real_api_last_run.json"
        )
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            json.dumps(
                {
                    "agent_id": agent.agent_id,
                    "game_time": game_time,
                    "daily_plan": {
                        "game_day": daily.game_day,
                        "slots": [
                            {
                                "start_time": s.start_time,
                                "end_time": s.end_time,
                                "activity": s.activity,
                                "location": s.location,
                                "notes": s.notes,
                            }
                            for s in daily.slots
                        ],
                    },
                    "fine_actions": [
                        {
                            "action_type": a.action_type,
                            "args": a.args,
                            "duration_seconds": a.duration_seconds,
                        }
                        for a in actions
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\n  详细日志已写入:{log_path}")
        print("=" * 76)

        # ---------- 基本断言 ----------
        assert len(daily.slots) >= 3, f"daily 至少 3 个时段,实际 {len(daily.slots)}"
        assert len(actions) >= 1, "fine 至少 1 个动作"
        assert all(a.duration_seconds > 0 for a in actions)
        assert all(a.action_type for a in actions)
        # 不要求精确匹配 location 集,但 daily 里至少 1 个 slot 用了已知 location
        valid_locs = {
            "lao_song_plaza",
            "north_frost_workshop",
            "warm_valley_farm",
            "silent_tower_ruins",
        }
        used_locs = {s.location for s in daily.slots}
        assert (
            used_locs & valid_locs
        ), f"daily 没有用到任何已知 location:{used_locs}"
    finally:
        await client.aclose()
