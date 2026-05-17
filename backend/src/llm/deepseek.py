"""DeepSeek API 异步客户端,支持 think-high / non-think 双模式与 4 层缓存。

参见设计文档 §2.1 / §2.3:
- Pro 用于 planning / reflection(质量敏感,可走 think_high)
- Flash 用于对话生成 / importance 打分(延迟敏感,走 non_think)

实现要点:
- httpx.AsyncClient 单例,避免每次重建连接池
- 失败重试:指数退避,最多 3 次,base 1s,max 8s,总超时 30s
- 重试触发:httpx.TimeoutException / httpx.ConnectError / HTTP 5xx
- 不重试:HTTP 4xx(请求错误,重试无意义)
- 价格常数实测于 2026-05-02,如有变化更新此处注释
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class ThinkMode(str, Enum):
    NON_THINK = "non_think"      # 对话生成、importance 打分等延迟敏感
    THINK_HIGH = "think_high"    # planning、reflection 等质量敏感
    # 不实现 THINK_MAX,见 v0.2 文档 §2.3


# 价格表(¥ / M tokens),实测于 2026-05-02
# 如官方调价,更新这些常数并修改"实测于"日期
_PRICE_TABLE: dict[str, dict[str, float]] = {
    "deepseek-v4-pro": {
        "input_miss": 2.0,
        "input_hit": 0.2,
        "output": 8.0,
    },
    "deepseek-v4-flash": {
        "input_miss": 0.5,
        "input_hit": 0.05,
        "output": 2.0,
    },
}


def _calc_cost_yuan(
    model: str, cache_hit_tokens: int, cache_miss_tokens: int, output_tokens: int
) -> float:
    """按模型与 cache 命中情况折算单次调用成本(元)。未识别模型返回 0。"""
    prices = _PRICE_TABLE.get(model)
    if prices is None:
        return 0.0
    per_million = 1_000_000.0
    return (
        cache_hit_tokens * prices["input_hit"] / per_million
        + cache_miss_tokens * prices["input_miss"] / per_million
        + output_tokens * prices["output"] / per_million
    )


@dataclass
class LLMUsage:
    """单次调用的 token 与成本统计。"""

    input_tokens: int
    output_tokens: int
    cache_hit_tokens: int
    cache_miss_tokens: int
    cost_yuan: float
    latency_ms: float


@dataclass
class LLMResponse:
    content: str
    usage: LLMUsage
    raw: dict[str, Any] = field(default_factory=dict)


class DeepSeekClient:
    """DeepSeek 异步 chat completion 客户端,内置缓存计费与重试。"""

    def __init__(self, api_key: str, base_url: str, timeout: float = 120.0) -> None:
        # 默认 120s:Block E 的 Pro think_high 规划任务实测可达 30-60s(推理 + JSON 输出)。
        # Block B 的 non_think 调用通常 1-3s,长 timeout 不影响其性能,只是失败时多等一会。
        # 实测于 2026-05-10。
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        # P3 打磨:累计成本统计,GET /sim/health 暴露给前端
        self.total_cost_yuan: float = 0.0
        self.total_calls: int = 0
        self.total_errors: int = 0  # 重试耗尽后抛的次数
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.total_cache_hit_tokens: int = 0
        # 红线 #2 运行时守卫:50 次调用后若命中率 < 85% 报警(只报一次)
        self._cache_warning_emitted: bool = False
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    def update_api_key(self, new_key: str) -> None:
        """运行时更新 API key(供 Godot 弹窗 POST /sim/api_key/set 调)。

        - 更新 self.api_key
        - 更新 httpx AsyncClient 的 Authorization header
        - 不重建连接池,后续 chat() 立即用新 key
        """
        self.api_key = new_key
        self._client.headers["Authorization"] = f"Bearer {new_key}"

    def is_api_key_configured(self) -> bool:
        """检查 key 是否有效(非空 + 非占位 + 长度合理)。"""
        if not self.api_key:
            return False
        if self.api_key in ("your_api_key_here", "PLACEHOLDER", "dummy"):
            return False
        if len(self.api_key) < 10:
            return False
        return True

    def masked_api_key(self) -> str:
        """脱敏的 key,只显示首尾各 4 位(用于 GET /sim/api_key/status 回显)。

        例:sk-abcd...wxyz
        """
        if not self.is_api_key_configured():
            return ""
        if len(self.api_key) <= 12:
            return "sk-***"
        return f"{self.api_key[:6]}...{self.api_key[-4:]}"

    def _build_request_body(
        self,
        messages: list[dict[str, str]],
        model: str,
        mode: ThinkMode,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        # 思考模式控制 — 按 v0.2 任务文档 B.1.2 §4 spec:
        #   NON_THINK  → "thinking": {"type": "disabled"}
        #   THINK_HIGH → "thinking": {"type": "enabled", "effort": "high"}
        # 若 DeepSeek 实际 API 字段名不同(如 reasoning_effort / enable_thinking),
        # 在此处按实测调整,并更新"实测于" 日期。
        if mode is ThinkMode.NON_THINK:
            body["thinking"] = {"type": "disabled"}
        elif mode is ThinkMode.THINK_HIGH:
            body["thinking"] = {"type": "enabled", "effort": "high"}
        return body

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str = "deepseek-v4-pro",
        mode: ThinkMode = ThinkMode.NON_THINK,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> LLMResponse:
        """发起一次 chat completion 调用。失败按指数退避重试,总超时 30s。"""
        try:
            return await self._chat_with_retry(messages, model, mode, temperature, max_tokens)
        except Exception:
            self.total_errors += 1
            raise

    async def _chat_with_retry(
        self,
        messages: list[dict[str, str]],
        model: str,
        mode: ThinkMode,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        url = f"{self.base_url}/v1/chat/completions"
        body = self._build_request_body(messages, model, mode, temperature, max_tokens)

        max_attempts = 3
        base_delay = 1.0
        max_delay = 8.0
        deadline = time.monotonic() + self.timeout
        last_exc: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            t0 = time.monotonic()
            try:
                # per-attempt timeout 不超过剩余总超时
                resp = await self._client.post(
                    url, json=body, timeout=min(self.timeout, remaining)
                )
                latency_ms = (time.monotonic() - t0) * 1000.0

                if 500 <= resp.status_code < 600:
                    last_exc = httpx.HTTPStatusError(
                        f"server error {resp.status_code}", request=resp.request, response=resp
                    )
                    # 5xx 走重试
                    if attempt < max_attempts:
                        delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
                        await asyncio.sleep(delay)
                        continue
                    raise last_exc

                # 4xx 直接抛(不重试)
                resp.raise_for_status()

                data = resp.json()
                return self._parse_response(data, model, latency_ms)

            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_exc = exc
                if attempt < max_attempts:
                    delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
                    # 不超过剩余 deadline
                    delay = min(delay, max(0.0, deadline - time.monotonic()))
                    if delay > 0:
                        await asyncio.sleep(delay)
                    continue
                raise

        # 跑出循环还没成功 → 抛最后一次异常
        assert last_exc is not None
        raise last_exc

    def _parse_response(
        self, data: dict[str, Any], model: str, latency_ms: float
    ) -> LLMResponse:
        content = data["choices"][0]["message"]["content"]
        usage_raw = data.get("usage", {})
        input_tokens = int(usage_raw.get("prompt_tokens", 0))
        output_tokens = int(usage_raw.get("completion_tokens", 0))
        cache_hit_tokens = int(usage_raw.get("prompt_cache_hit_tokens", 0))
        cache_miss_tokens = int(usage_raw.get("prompt_cache_miss_tokens", 0))
        # 兜底:若服务端只返回 prompt_tokens 而无 hit/miss,把全部算成 miss
        if cache_hit_tokens == 0 and cache_miss_tokens == 0 and input_tokens > 0:
            cache_miss_tokens = input_tokens

        cost_yuan = _calc_cost_yuan(
            model, cache_hit_tokens, cache_miss_tokens, output_tokens
        )
        usage = LLMUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_hit_tokens=cache_hit_tokens,
            cache_miss_tokens=cache_miss_tokens,
            cost_yuan=cost_yuan,
            latency_ms=latency_ms,
        )
        logger.info(
            "[deepseek] model=%s input=%d output=%d cache_hit=%d cost=%.4f元 latency=%.0fms",
            model,
            input_tokens,
            output_tokens,
            cache_hit_tokens,
            cost_yuan,
            latency_ms,
        )
        # 累计统计(P3 /sim/health)
        self.total_cost_yuan += cost_yuan
        self.total_calls += 1
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cache_hit_tokens += cache_hit_tokens
        # 红线 #2 运行时守卫:50+ 次调用后命中率仍 < 85% → 警告一次
        # Layer 0/1 字节稳定性应保证 90%+,< 85% 表明缓存被破坏(应该重跑
        # test_cache_hit_rate.py 定位最近哪个 prompt 改动出问题)
        if (
            not self._cache_warning_emitted
            and self.total_calls >= 50
            and self.total_input_tokens > 0
        ):
            rate = self.total_cache_hit_tokens / self.total_input_tokens
            if rate < 0.85:
                logger.warning(
                    "[deepseek] ⚠️  cache hit rate %.1f%% < 85%% (target ≥ 90%%) — "
                    "Layer 0/1 字节稳定性可能被破坏。检查最近 LAYER_0_SYSTEM / "
                    "build_rich_layer_1 / dialogue layer 改动,跑 "
                    "tests/test_cache_hit_rate.py 定位",
                    rate * 100,
                )
                self._cache_warning_emitted = True
        return LLMResponse(content=content, usage=usage, raw=data)
