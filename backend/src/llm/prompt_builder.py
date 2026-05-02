"""4 层 prompt 缓存结构构建器。

参见设计文档 §2.2:为最大化 DeepSeek 的 prompt cache 命中率,所有 prompt 必须按以下分层拼接:
    Layer 0 — 系统指令 / 角色框架(进程级常驻,跨 agent 共用)
    Layer 1 — agent 不变特征(persona、背景),每个 agent 一份,跨调用复用
    Layer 2 — 当日相对稳定上下文(当日规划、反思、关键 memory 摘要)
    Layer 3 — 本次调用专属(当前观察、即时输入)

调用方按需提供各层片段,本模块负责拼接并保证可缓存前缀稳定。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PromptLayers:
    """4 层 prompt 的纯文本载荷。"""

    layer0_system: str
    layer1_persona: str
    layer2_daily: str
    layer3_call: str


def build_messages(layers: PromptLayers) -> list[dict[str, str]]:
    """把 4 层文本拼成 DeepSeek 可吃的 messages 列表。

    Block B 实现:正确划分 system / user / assistant 角色,确保前 3 层在每次调用中
    生成完全一致的 token 序列以触发 prompt cache。
    """
    raise NotImplementedError("Block B 实现")
