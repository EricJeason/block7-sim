# Day 1 Block D — AgentRuntime + Action Queue 异步调度器

> **派发对象**:Codex / Claude Code 新 session(建议直接在 main 分支工作)
> **预计时长**:60–120 分钟
> **预计真实 API 成本**:¥0
> **依赖**:Block A/B/C 已实落
> **本 Block 性质**:核心架构硬关卡。只实现调度与运行时,不实现真实 LLM 规划业务。

---

## 任务上下文

**项目**:Block-7 生成式智能体社会模拟器
**当前阶段**:Day 1, Block D
**架构总纲**:`docs/Project_Design_Document_v0_2.md`,重点章节:
- §1:快动作慢思考
- §1.2:Action Queue 数据结构
- §1.3:调度循环
- §1.4:紧急打断机制
- §2.2:4 层 Prompt 缓存结构
- §3:无向量检索的 memory 召回

**已完成前置模块**:
- Block A:FastAPI / Godot / 配置 / 测试骨架
- Block B:`DeepSeekClient`、`ThinkMode`、`PromptBuilder`
- Block C:`MemoryStore`、SQLite schema、关键词检索、importance scorer

**Block D 的定位**:

Block D 是“AI 慢思考”和“游戏快执行”之间的隔离层。它必须保证:

1. 游戏循环只消费已有动作,永不等待 LLM。
2. LLM 规划只能在后台任务中运行,完成后把新动作追加到队列尾部。
3. 队列低水位时自动触发后台思考。
4. 队列空但后台思考未完成时,agent 执行短 idle fallback,画面不能冻结。
5. 高重要性事件可触发 emergency replan:保留当前原子动作,清空后续队列,取消常规思考,启动紧急思考。

**重要边界**:

Block D 不负责让 LLM 真正“聪明”。真实粗粒度 / 细粒度规划属于 Block E。Block D 只定义可插拔的 planner 协议,并用 fake planner 写完整测试。

---

## 先解决的风险:D.0 世界观占位符解耦

当前 `backend/src/llm/prompt_builder.py` 的 Layer 0 硬编码了“青岚镇”。这会把后续世界观锁死,也会污染僵尸病毒 / 政府 / 警察模拟方向。

Block D 开始前必须做一个小型前置修正:

1. 把 Layer 0 中所有具体世界名“青岚镇”替换为稳定占位符:

   ```text
   [WORLD_PENDING]
   ```

2. Layer 0 不要写死江南小镇、茶节、土地庙等具体设定。改为“通用社会模拟占位上下文”,只保留:
   - agent 必须遵守角色身份
   - 输出必须稳定为简体中文
   - 决策必须按 JSON 格式返回
   - 当前世界观尚未最终敲定,具体地点 / 阵营 / 社会规则以后由 persona 与 location 配置注入
   - 当前版本以“封闭社区中的多角色社会模拟”为通用占位描述

3. 占位 Layer 0 仍要足够长且完全稳定,不要为了占位而缩得太短。它依然承担 DeepSeek prompt cache 的稳定前缀职责。

4. 更新 smoke test:

   ```python
   assert "青岚镇" not in PromptBuilder.LAYER_0_SYSTEM
   assert "[WORLD_PENDING]" in PromptBuilder.LAYER_0_SYSTEM
   ```

5. 不要在 Block D 敲定最终世界观。最终世界观后续只需要替换这个占位上下文即可。

验收:
- 本地 smoke test 通过。
- `PromptBuilder` 的 Layer 0+1 稳定性测试仍通过。
- 不新增任何真实 API 调用。

---

## 任务目标(全部达成才算 Block D 通过)

| # | 目标 | 验收标准 |
|---|---|---|
| 1 | `AgentRuntime` 从占位数据类升级为真实运行时 | 包含动作队列、当前动作、后台思考任务、状态快照 |
| 2 | `QueuedAction` 数据结构完整 | 支持校验、推进 elapsed、剩余时间计算、序列化 |
| 3 | `ActionScheduler` 可注册 / tick 多个 agent | 单 agent 与多 agent 单测均通过 |
| 4 | tick 永不阻塞慢 planner | fake planner sleep 200ms 时,tick 在 50ms 内返回 |
| 5 | 低水位自动触发后台思考 | 不重复创建 pending task,完成后追加动作 |
| 6 | 队列空 + 思考未完成时 fallback idle | agent 不冻结,current_action 合法 |
| 7 | emergency replan 正确 | 当前原子动作保留,未来队列清空,常规思考取消,紧急思考启动 |
| 8 | plan memory 薄写入 | planner 结果可选写入 `memory_type="plan"` 的 memory |
| 9 | 测试覆盖核心竞态 | 至少 10 个 Block D 单元测试,不调用真实 API |
| 10 | lint / mypy / pytest 通过 | `ruff check src tests`, `mypy src`, `pytest -v tests/test_scheduler.py tests/test_smoke.py tests/test_memory.py` |

---

## 核心设计原则

### 原则 1:tick 只能做“快操作”

`tick()` 允许做:
- 推进当前动作 elapsed
- 完成动作
- 弹出队列下一个动作
- 检查后台 task 是否 done
- 创建后台 task
- 追加已经完成的 planner 结果
- 创建短 idle fallback

`tick()` 禁止做:
- 直接 await LLM
- 直接 await planner 生成结果
- 等待 pending task
- 做任何网络 IO
- 做长时间数据库查询

如果 tick 里写了类似下面的代码,就是 Block D 失败:

```python
new_actions = await planner.plan(...)
```

正确做法:

```python
agent.pending_thinking = asyncio.create_task(
    planner.plan(agent.snapshot(), reason, context)
)
```

然后在后续 tick 中:

```python
if agent.pending_thinking.done():
    new_actions = agent.pending_thinking.result()
    agent.action_queue.extend(new_actions)
```

### 原则 2:Block D 只依赖 planner 协议,不依赖真实规划实现

Block E 才会把 DeepSeek + PromptBuilder + MemoryStore 组合成真正的 planner。Block D 只定义一个协议:

```python
class PlanProvider(Protocol):
    async def plan_next_actions(
        self,
        agent: AgentRuntime,
        reason: ThinkingReason,
        context: dict[str, Any],
    ) -> list[QueuedAction]:
        ...
```

Block D 测试使用 fake planner:
- 立刻返回动作
- 延迟返回动作
- 抛异常
- 永不返回直到被 cancel

### 原则 3:当前原子动作默认不可被 emergency 中断

紧急事件来临时:
- 不停止 `current_action`
- 清空 `action_queue`
- 取消常规 pending thinking
- 启动 emergency thinking

原因:角色正在执行的视觉动作如果随意打断,Godot 表现层会难做,也会让模拟显得不真实。真正的紧急反应发生在当前动作完成之后。

### 原则 4:fallback 是体验保护,不是规划结果

idle fallback 只用于“队列空但 planner 还没返回”的空窗期。它不能永久填满队列,不能掩盖 planner 一直失败的问题。

建议:
- fallback idle duration:2.0 游戏秒
- 若 planner 连续失败超过 3 次,记录 warning,但仍保持 idle fallback

---

## 详细规格

### D.1 Runtime 数据结构 — `backend/src/agent/runtime.py`

把当前占位 `AgentRuntime` 扩展为真实运行时。

#### D.1.1 类型定义

```python
from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Deque, Literal
from uuid import uuid4


class ThinkingReason(str, Enum):
    LOW_WATERMARK = "low_watermark"
    EMPTY_QUEUE = "empty_queue"
    EMERGENCY = "emergency"
    MANUAL = "manual"


class ActionSource(str, Enum):
    PLANNER = "planner"
    FALLBACK = "fallback"
    MANUAL = "manual"
    EMERGENCY = "emergency"


@dataclass
class QueuedAction:
    action_type: str
    args: dict[str, Any] = field(default_factory=dict)
    duration_seconds: float = 1.0
    action_id: str = field(default_factory=lambda: uuid4().hex)
    started_at: float | None = None
    elapsed_seconds: float = 0.0
    interruptible: bool = True
    source: ActionSource = ActionSource.PLANNER

    def __post_init__(self) -> None:
        ...

    @property
    def remaining_seconds(self) -> float:
        ...

    @property
    def is_complete(self) -> bool:
        ...

    def start(self, game_time: float) -> None:
        ...

    def advance(self, dt: float) -> None:
        ...

    def to_dict(self) -> dict[str, Any]:
        ...
```

校验要求:
- `action_type` 非空
- `duration_seconds > 0`
- `elapsed_seconds >= 0`
- `elapsed_seconds` 不允许超过 `duration_seconds` 太多;`advance()` 内部 clamp 到 duration

#### D.1.2 AgentRuntime

```python
@dataclass
class AgentRuntime:
    agent_id: str
    persona_name: str = ""
    current_location: str = ""
    current_mood: str = "neutral"

    action_queue: Deque[QueuedAction] = field(default_factory=deque)
    current_action: QueuedAction | None = None

    pending_thinking: asyncio.Task[list[QueuedAction]] | None = None
    pending_reason: ThinkingReason | None = None
    last_thinking_started_at: float = 0.0
    consecutive_planning_failures: int = 0

    state: dict[str, Any] = field(default_factory=dict)
    plan: dict[str, Any] = field(default_factory=dict)

    def queued_remaining_seconds(self) -> float:
        ...

    def total_remaining_seconds(self) -> float:
        ...

    def has_pending_thinking(self) -> bool:
        ...

    def snapshot(self) -> dict[str, Any]:
        ...
```

`snapshot()` 用于后续 WebSocket / 测试 / 日志,至少包含:
- agent_id
- current_location
- current_mood
- current_action dict 或 None
- queue list
- pending_reason
- total_remaining_seconds
- consecutive_planning_failures

#### D.1.3 保留 load_runtime 占位

`load_runtime(agent_id: str)` 暂时可以继续 `raise NotImplementedError("Block D 实现")`,但若本 Block 有余力,可以实现一个最小版本:
- 从 SQLite `agents` 表恢复基础字段
- 初始 action_queue 为空

不要为了 `load_runtime` 扩大 scope 到 persona YAML 解析。persona 完整加载可以留给后续 Block。

---

### D.2 Scheduler 配置与结果类型 — `backend/src/agent/scheduler.py`

新增配置类:

```python
@dataclass(frozen=True)
class SchedulerConfig:
    thinking_trigger_threshold: float = 30.0
    fallback_idle_seconds: float = 2.0
    max_planner_actions: int = 10
    max_consecutive_planning_failures: int = 3
```

新增 tick 结果:

```python
@dataclass
class TickResult:
    agent_id: str
    started_action: QueuedAction | None = None
    completed_action: QueuedAction | None = None
    appended_actions: list[QueuedAction] = field(default_factory=list)
    fallback_action: QueuedAction | None = None
    thinking_started: bool = False
    thinking_completed: bool = False
    thinking_failed: bool = False
```

`TickResult` 是测试和日志的核心,不要只靠内部状态猜测发生了什么。

---

### D.3 PlanProvider 协议

在 `scheduler.py` 中定义:

```python
class PlanProvider(Protocol):
    async def plan_next_actions(
        self,
        agent: AgentRuntime,
        reason: ThinkingReason,
        context: dict[str, Any],
    ) -> list[QueuedAction]:
        ...
```

提供一个本地 fallback provider,用于开发和无 planner 场景:

```python
class IdlePlanProvider:
    async def plan_next_actions(...) -> list[QueuedAction]:
        return [
            QueuedAction(
                action_type="idle",
                args={"reason": "idle_plan_provider"},
                duration_seconds=5.0,
                source=ActionSource.FALLBACK,
            )
        ]
```

注意:
- 真实 DeepSeek 规划不在 Block D 实现。
- `PlanProvider` 不能 import `src.agent.planning.plan_fine`。
- Block D 测试必须只用 fake provider。

---

### D.4 ActionScheduler 主类

实现:

```python
class ActionScheduler:
    def __init__(
        self,
        planner: PlanProvider | None = None,
        memory_store: MemoryStore | None = None,
        config: SchedulerConfig | None = None,
    ) -> None:
        ...

    def register_agent(self, agent: AgentRuntime) -> None:
        ...

    def get_agent(self, agent_id: str) -> AgentRuntime:
        ...

    async def enqueue(
        self,
        agent_id: str,
        action: QueuedAction,
        *,
        front: bool = False,
    ) -> None:
        ...

    async def tick_agent(
        self,
        agent_id: str,
        *,
        game_time: float,
        dt: float,
        context: dict[str, Any] | None = None,
    ) -> TickResult:
        ...

    async def tick_all(
        self,
        *,
        game_time: float,
        dt: float,
        context_by_agent: dict[str, dict[str, Any]] | None = None,
    ) -> list[TickResult]:
        ...

    async def trigger_emergency_replan(
        self,
        agent_id: str,
        event: dict[str, Any],
        *,
        game_time: float,
    ) -> None:
        ...

    async def shutdown(self) -> None:
        ...
```

#### D.4.1 tick_agent 必须按这个顺序执行

1. 校验 `dt >= 0`。
2. 如果 `pending_thinking.done()`,取出结果:
   - 正常:追加到队列尾部,最多保留 `max_planner_actions`
   - 异常 / CancelledError:记录 warning,增加 `consecutive_planning_failures`
   - 清空 `pending_thinking` 与 `pending_reason`
   - 可选写入 plan memory
3. 推进 `current_action`:
   - 如果存在,调用 `advance(dt)`
   - 如果完成,生成 `completed_action`,把 `current_action = None`
4. 如果没有当前动作且队列非空:
   - `popleft()`
   - `start(game_time)`
   - 设为 `current_action`
5. 计算 `total_remaining_seconds()`。
6. 如果剩余时长 `< thinking_trigger_threshold` 且没有 pending:
   - `asyncio.create_task(...)` 启动 planner
   - 设置 `pending_reason = LOW_WATERMARK` 或 `EMPTY_QUEUE`
   - 不 await task
7. 如果当前动作为空、队列为空、但 pending 存在:
   - 创建 fallback idle action
   - 立即 start
   - 设为 `current_action`

#### D.4.2 低水位触发规则

触发 planner 的条件:

```python
remaining = agent.total_remaining_seconds()
if remaining < config.thinking_trigger_threshold and agent.pending_thinking is None:
    reason = ThinkingReason.EMPTY_QUEUE if remaining <= 0 else ThinkingReason.LOW_WATERMARK
    start_background_thinking(...)
```

不得重复触发:
- 只要 `pending_thinking is not None`,不再创建第二个 planner task。

#### D.4.3 Planner 结果校验

planner 返回后必须校验:
- 返回值必须是 `list[QueuedAction]`
- 空列表允许,但会导致后续 fallback idle
- action duration 必须 > 0
- 最多追加 `max_planner_actions` 条,多余截断并 warning

不要因为 planner 输出坏数据导致 scheduler 崩溃。坏数据视为 planning failure。

---

### D.5 Emergency Replan

实现:

```python
async def trigger_emergency_replan(
    self,
    agent_id: str,
    event: dict[str, Any],
    *,
    game_time: float,
) -> None:
    ...
```

语义:

1. 找到 agent。
2. 清空 `agent.action_queue`。
3. 若 `agent.pending_thinking` 存在:
   - `cancel()`
   - 不 await 长时间等待
   - 标记为常规思考被紧急打断
4. 保留 `agent.current_action`。
5. 启动新的 background thinking:
   - `reason=ThinkingReason.EMERGENCY`
   - `context={"urgent_event": event}`
6. 若当前没有动作,后续 tick 会用 fallback idle 保持画面动起来。

测试必须覆盖:
- current_action 不变
- future queue 被清空
- old pending 被 cancel
- new pending reason 是 EMERGENCY
- fake emergency planner 返回的动作被追加

---

### D.6 Plan Memory 薄写入

Block C 中 `memories.memory_type` 已包含 `plan`。Block D 应把“planner 新增的动作列表”写成一条轻量 plan memory,方便后续检索与调试。

要求:
- `ActionScheduler.__init__` 接受可选 `memory_store: MemoryStore | None`
- 如果没有 memory_store,跳过写入
- 如果有 memory_store,当 planner 成功返回非空动作时写一条 memory:

```python
Memory(
    memory_id=None,
    agent_id=agent.agent_id,
    memory_type="plan",
    content="计划: move_to(..., 10s) -> interact(..., 5s)",
    importance=4 if reason != ThinkingReason.EMERGENCY else 7,
    game_time=game_time,
    real_time=time.time(),
    location=agent.current_location or None,
    related_agents=[],
    keywords=[agent.current_location, "plan", reason.value, ...],
)
```

注意:
- 写入失败不能让 tick 崩溃。记录 warning 即可。
- 这只是薄写入,不是 reflection,也不是语义总结。
- 不调用 LLM。

---

### D.7 模块级兼容函数

当前 `backend/src/agent/scheduler.py` 暴露了:

```python
async def enqueue(agent_id: str, action: dict[str, Any]) -> None:
    ...

async def tick() -> None:
    ...
```

为了不破坏未来 import,保留模块级包装:

```python
default_scheduler = ActionScheduler()

async def enqueue(agent_id: str, action: dict[str, Any]) -> None:
    queued = QueuedAction(...)
    await default_scheduler.enqueue(agent_id, queued)

async def tick() -> None:
    # 兼容占位接口。可以对 default_scheduler.tick_all 做最小调用,
    # 或明确 raise NotImplementedError("Block H 接入 game_time 后实现")
```

建议:
- `enqueue()` 做真实包装。
- `tick()` 若没有 game_time/dt 参数,保持 `NotImplementedError("Block H 接入 game_time 后实现")` 也可以。
- 核心测试使用 `ActionScheduler` 类,不要依赖模块级 `tick()`。

---

### D.8 日志与调试

使用标准 logging:

```python
logger = logging.getLogger(__name__)
```

建议日志事件:
- register agent
- start action
- complete action
- start thinking
- thinking completed
- thinking failed
- emergency replan
- fallback idle

日志内容要短,不要打印完整 prompt 或巨大 memory。

---

## 单元测试规格 — `backend/tests/test_scheduler.py`

必须新增测试文件 `backend/tests/test_scheduler.py`。

### D.9.1 Fake planner

测试内定义:

```python
class InstantPlanner:
    async def plan_next_actions(...):
        return [QueuedAction(action_type="idle", duration_seconds=5.0)]


class SlowPlanner:
    def __init__(self):
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def plan_next_actions(...):
        self.started.set()
        await self.release.wait()
        return [QueuedAction(action_type="move_to", args={"location": "x"}, duration_seconds=5.0)]


class ErrorPlanner:
    async def plan_next_actions(...):
        raise RuntimeError("planner failed")
```

### D.9.2 必测场景

1. `test_queued_action_validation`
   - 空 action_type 抛 ValueError
   - duration <= 0 抛 ValueError

2. `test_action_progress_and_completion`
   - duration 10
   - advance 4 后未完成
   - advance 6 后完成
   - remaining 不为负数

3. `test_scheduler_starts_next_action`
   - agent 队列里有一条 action
   - tick 后 current_action 被设置并 started_at == game_time

4. `test_scheduler_completes_current_action`
   - current_action elapsed 到 duration
   - tick 返回 completed_action
   - current_action 清空或切换下一条

5. `test_low_watermark_starts_single_thinking_task`
   - remaining < threshold
   - tick 第一次创建 pending
   - tick 第二次不创建第二个 pending

6. `test_tick_does_not_block_slow_planner`
   - SlowPlanner 内部等待 release
   - `await scheduler.tick_agent(...)` 必须很快返回
   - 可用 `time.monotonic()` 断言 < 0.05s 或 < 0.1s

7. `test_pending_thinking_appends_actions_when_done`
   - release SlowPlanner
   - 下一次 tick 后 appended_actions 非空
   - pending_thinking 清空

8. `test_empty_queue_while_thinking_uses_idle_fallback`
   - 无 current_action,无 queue,pending 未完成
   - tick 后 current_action 是 fallback idle

9. `test_emergency_replan_keeps_current_action_and_clears_future_queue`
   - current_action 存在
   - queue 有未来动作
   - pending 常规 thinking 存在
   - emergency 后 current_action 不变,queue 清空,pending 变为新 task

10. `test_planner_exception_does_not_crash_tick`
    - ErrorPlanner
    - task done 后 tick 不抛异常
    - consecutive_planning_failures 增加
    - 后续 fallback 仍可执行

11. `test_plan_memory_written_when_store_present`
    - 用 tmp_path init_db
    - planner 返回动作
    - tick 收割结果后 `MemoryStore.get_recent(..., memory_types=["plan"])` 能查到 plan memory

12. `test_shutdown_cancels_pending_tasks`
    - 注册 agent 并启动 SlowPlanner
    - `await scheduler.shutdown()`
    - pending task 被 cancel 或清空

测试注意:
- 不调用真实 DeepSeek API。
- 不依赖真实时间 sleep。需要等待 task 调度时用 `await asyncio.sleep(0)`。
- 不要让慢 planner 测试真的睡 200ms;用 `asyncio.Event` 控制更稳。

---

## Smoke Test 更新

更新 `backend/tests/test_smoke.py`:

1. 原有 import 测试继续通过。
2. 增加 PromptBuilder 世界占位符测试:

```python
def test_prompt_builder_uses_world_placeholder() -> None:
    from src.llm.prompt_builder import PromptBuilder

    assert "青岚镇" not in PromptBuilder.LAYER_0_SYSTEM
    assert "[WORLD_PENDING]" in PromptBuilder.LAYER_0_SYSTEM
```

3. 增加 scheduler 基础 import:

```python
from src.agent.scheduler import ActionScheduler, SchedulerConfig
from src.agent.runtime import AgentRuntime, QueuedAction
```

---

## 执行流程(必须按顺序)

1. `git status --short`
   - 确认工作区状态。
   - 不要回滚用户已有改动。

2. D.0 世界占位符修正
   - 修改 `backend/src/llm/prompt_builder.py`
   - 更新 smoke test
   - 先跑 `pytest -v tests/test_smoke.py`

3. D.1 runtime 数据结构
   - 修改 `backend/src/agent/runtime.py`
   - 写 `QueuedAction` 与 `AgentRuntime`
   - 先补最基础 action 测试

4. D.2-D.5 scheduler 主逻辑
   - 修改 `backend/src/agent/scheduler.py`
   - 先实现不带 memory 的调度闭环
   - 跑 scheduler 测试前 10 项

5. D.6 plan memory 薄写入
   - 接入 `MemoryStore`
   - 写 tmp sqlite 测试

6. D.7 兼容函数
   - 保留模块级 `enqueue`
   - 不强行实现无参数 `tick`

7. 全量本地验证:

   ```powershell
   cd backend
   pytest -v tests/test_scheduler.py tests/test_smoke.py tests/test_memory.py
   ruff check src tests
   mypy src
   ```

---

## 验收标准

### 验收 1:本地测试

必须通过:

```powershell
cd backend
pytest -v tests/test_scheduler.py tests/test_smoke.py tests/test_memory.py
```

预期:
- `tests/test_scheduler.py` 至少 10 个测试
- 不出现真实 API skip 之外的失败
- 不产生 “Task was destroyed but it is pending” warning

### 验收 2:lint 与类型检查

必须通过:

```powershell
cd backend
ruff check src tests
mypy src
```

注意:当前 `tests/test_memory.py` 可能已有一个未使用 import。Block D session 应顺手修掉这个 lint 问题,但不要改测试语义。

### 验收 3:非阻塞调度证明

报告中必须包含:
- fake slow planner 被启动
- tick 没有等待 planner 完成
- tick 耗时断言通过

这是 Block D 的硬关卡。

### 验收 4:emergency replan 证明

报告中必须包含:
- 当前动作保留
- 未来队列清空
- 旧 pending 被取消
- 新 pending reason 为 `EMERGENCY`

### 验收 5:世界占位符

报告中必须包含:
- `PromptBuilder.LAYER_0_SYSTEM` 已不含“青岚镇”
- 含 `[WORLD_PENDING]`
- Layer 0+1 稳定性测试仍通过

---

## 严禁事项

1. **严禁在 tick 中 await LLM / planner**。
2. **严禁引入 embedding / faiss / chromadb / langchain / sentence-transformers**。
3. **严禁在 Block D 调用真实 DeepSeek API**。
4. **严禁实现完整 planning prompt**。那是 Block E。
5. **严禁实现 WebSocket / Godot 移动 UI**。那是 Block H。
6. **严禁把最终世界观写死进代码**。当前只用 `[WORLD_PENDING]`。
7. **严禁吞掉所有异常不记录**。planner 失败可 fallback,但必须 logger warning。
8. **严禁让 pending asyncio task 在测试结束后悬挂**。测试和 scheduler 都必须清理任务。
9. **严禁做大规模重构或新增顶层目录**。仅改 `backend/src/agent/*`,必要时小改 `prompt_builder.py` 与测试。

---

## Block D 完成时报告格式

完成后请报告:

```text
Block D 完成报告

1. 实现文件
- backend/src/agent/runtime.py
- backend/src/agent/scheduler.py
- backend/tests/test_scheduler.py
- backend/src/llm/prompt_builder.py (D.0 占位符修正)
- backend/tests/test_smoke.py

2. 核心能力
- Action Queue 推进:
- 后台 thinking:
- fallback idle:
- emergency replan:
- plan memory 写入:

3. 验证结果
- pytest:
- ruff:
- mypy:

4. 重要设计选择
- 为什么 tick 不 await planner:
- 为什么 current_action 不被 emergency 打断:
- Block E 如何接入 PlanProvider:

5. 遗留给 Block E/H 的接口
- PlanProvider:
- AgentRuntime.snapshot():
- TickResult:
```

---

## 给后续 Block 的接口预期

### Block E 如何接入

Block E 只需要实现一个真实 planner:

```python
class LLMPlanProvider:
    async def plan_next_actions(
        self,
        agent: AgentRuntime,
        reason: ThinkingReason,
        context: dict[str, Any],
    ) -> list[QueuedAction]:
        # 1. 读取 memory
        # 2. 构造 PromptBuilder messages
        # 3. 调 DeepSeek
        # 4. 校验 JSON
        # 5. 返回 QueuedAction list
```

然后:

```python
scheduler = ActionScheduler(planner=LLMPlanProvider(...), memory_store=store)
```

无需改 scheduler 核心逻辑。

### Block H 如何接入

Godot / WebSocket 只需要消费:

```python
agent.snapshot()
tick_result
queued_action.to_dict()
```

后端每个 sim tick 调:

```python
results = await scheduler.tick_all(game_time=game_time, dt=dt)
```

再把 action start / complete / snapshot 推给 Godot。

---

## 我对 Block D 的工程判断

Block D 的难点不在代码量,而在“异步边界”:

- 如果 tick 等 planner,游戏会卡。
- 如果 pending task 不清理,测试和运行时会泄漏。
- 如果 emergency 直接打断当前动作,Godot 表现层会变复杂。
- 如果 planner 结果不校验,后续 LLM 一次坏 JSON 会打崩模拟。
- 如果 fallback 设计不清楚,agent 会在空队列时僵住。

所以本任务包把 Block D 拆成“可测试调度内核”,暂时不碰真实 LLM。等这个内核稳了,Block E 才把 DeepSeek 接进来。这个顺序比一次性把调度、规划、prompt、memory 全混在一起可靠得多。
