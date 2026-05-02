"""DeepSeek HTTP 客户端(Pro / Flash 双模型),封装 chat/completions 与成本统计。

参见设计文档 §2.1:Pro 用于反思 + 粗粒度规划,Flash 用于细粒度规划与对话。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class LLMResponse:
    """DeepSeek 调用的统一返回结构。"""

    content: str
    prompt_tokens: int
    completion_tokens: int
    cache_hit_tokens: int
    model: str
    raw: dict[str, Any]


class DeepSeekClient:
    """异步 DeepSeek 客户端骨架。Block B 实现真实 HTTP 调用。"""

    def __init__(self, api_key: str, base_url: str) -> None:
        self.api_key = api_key
        self.base_url = base_url

    async def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """调用 DeepSeek chat/completions 端点,返回 LLMResponse。

        Block B 实现:支持 prompt cache、超时重试、成本统计。
        """
        raise NotImplementedError("Block B 实现")
