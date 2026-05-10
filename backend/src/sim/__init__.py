"""Block H:Sim 调度引擎 + 事件总线。

把 ActionScheduler / LLMPlanner / PerceptionBroker / MemoryStore 拼起来,
跑后台 tick 循环,向订阅者(WebSocket 客户端)广播事件。
"""
from src.sim.engine import SimEngine, SimEvent

__all__ = ["SimEngine", "SimEvent"]
