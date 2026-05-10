# Day 1 Block D Review — Action Queue 调度内核复审与硬化

> **派发对象**:Codex / Claude Code 新 session
> **预计时长**:30–60 分钟
> **预计真实 API 成本**:¥0
> **依赖**:Block D 已实现但尚未 commit
> **本任务性质**:代码审查 + 小范围硬化。不是 Block E,不要新增真实 LLM 规划。

---

## 任务上下文

**项目**:Block-7 生成式智能体社会模拟器
**当前阶段**:Day 1, Block D 完成后的复审
**权威任务包**:
- `Day1_Block_D_Task.md`
- `docs/CLAUDE.md`
- `docs/Project_Design_Document_v0_2.md` §1 / §2.2 / §3

**Block D 当前产出**:
- `backend/src/agent/runtime.py`
- `backend/src/agent/scheduler.py`
- `backend/tests/test_scheduler.py`
- `backend/src/llm/prompt_builder.py` 的 `[WORLD_PENDING]` 占位符修正
- `backend/tests/test_smoke.py`
- `backend/tests/test_memory.py` 的 lint 小修

**本 Review 的核心问题**:

Block D 是后续所有 agent 行为的地基。测试通过不等于长期运行稳定。请以代码审查姿态检查:

1. `tick_agent()` 是否真的不会被慢 planner / 慢 IO 拖住。
2. pending thinking task 是否可能泄漏、被重复创建、被错误覆盖。
3. emergency replan 是否会留下旧 task、旧结果、旧 reason 或吞掉异常。
4. planner 输出坏数据时 scheduler 是否能保持模拟继续运行。
5. `tick_all()` 是否会因单个 agent 异常拖垮所有 agent。
6. plan memory 写入是否会把数据库 IO 放到 tick 快路径上。
7. `AgentRuntime.snapshot()` 是否足够安全供 Block H / WebSocket 消费。

---

## 工作模式

本任务优先级是 **发现风险 > 小范围修复 > 保持接口稳定**。

你可以做:
- 阅读代码并给出 review findings。
- 修改 Block D 内部实现以修复高置信度问题。
- 增加测试覆盖已确认风险。
- 修复不改变语义的 lint / typing 问题。

你不要做:
- 不要实现 Block E 的真实 LLM planner。
- 不要调用真实 DeepSeek API。
- 不要实现 WebSocket / Godot UI。
- 不要改动世界观设定,只保留 `[WORLD_PENDING]`。
- 不要大规模重构目录结构或重命名公共接口。

若发现问题但修复会显著扩大 scope,请只报告并解释风险,不要硬改。

---

## 自检流程

开始前必须执行:

```powershell
git status --short
```

确认当前工作区至少包含 Block D 相关改动。不要回滚用户已有改动。

然后阅读:

```text
Day1_Block_D_Task.md
backend/src/agent/runtime.py
backend/src/agent/scheduler.py
backend/tests/test_scheduler.py
backend/tests/test_smoke.py
backend/src/llm/prompt_builder.py
```

跑基线:

```powershell
cd backend
pytest -v tests/test_scheduler.py tests/test_smoke.py tests/test_memory.py
ruff check src tests
mypy src
```

如果基线不通过,先定位是否是 Block D 当前改动造成。不要先做新功能。

---

## Review 重点清单

### R.1 tick 快路径非阻塞

检查 `ActionScheduler.tick_agent()` 是否只做快操作。

重点看:
- 是否 await 了 planner。
- 是否 await 了潜在慢 IO。
- `_collect_finished_thinking()` 中是否 await 了 `_write_plan_memory()`。
- SQLite `MemoryStore.insert()` 是否可能让 tick 被磁盘 IO 拖住。

判断标准:
- “不 await planner”是硬要求。
- “tick 中少量 SQLite 写入”当前测试可接受,但从架构上有风险。若要修,优先改成 fire-and-forget 后台写入并在 `shutdown()` 中清理写入 task;若修复复杂,至少把它作为 review finding 报告。

建议测试:
- 增加一个 fake slow memory store,确认 planner 收割 tick 不会被 memory 写入卡住。
- 如果选择不改,报告中说明这是已知风险。

### R.2 pending task 生命周期

检查:
- 低水位时是否只创建一个 pending task。
- task done 后是否总能清空 `pending_thinking` 与 `pending_reason`。
- task cancelled 后是否取 result / exception 以避免未取异常 warning。
- `shutdown()` 是否能清理所有 pending planner task。
- emergency replan 中旧 task cancel 后是否可能留下未被收割的异常。

建议测试:
- pending task 抛异常后 tick 不崩。
- emergency cancel 一个会在 cancellation cleanup 中抛异常的 task,不出现未取异常。

### R.3 emergency replan 语义

必须保持:
- 当前 `current_action` 不被替换。
- 未来 `action_queue` 被清空。
- 旧常规 thinking 被取消或废弃。
- 新 pending reason 是 `EMERGENCY`。
- emergency planner 结果到达后追加到当前动作后方,不立刻打断当前动作。

额外检查:
- 如果 emergency 来时旧 pending 已经 done,是否会把旧 planner 结果意外追加。
- 如果连续两次 emergency,是否会正确取消第一次 emergency pending。

建议新增测试:
- `test_emergency_discards_done_regular_pending_result`
- `test_second_emergency_replaces_first_emergency_pending`

### R.4 tick_all 多 agent 隔离

当前 `tick_all()` 如果用 `asyncio.gather()` 默认行为,一个 agent 的 `tick_agent()` 抛异常可能让整个 tick_all 抛出。

请判断这是否符合模拟目标。

推荐方向:
- 对游戏模拟来说,一个 agent 的异常不应拖垮所有 agent。
- 可以新增 `TickResult.error: str | None` 字段,或在 `tick_all()` 内捕获单 agent 异常并 logger warning。
- 如果修改公共结构会扩大 scope,至少作为 review finding 报告。

建议测试:
- 注册两个 agent,其中一个通过特殊状态触发 tick 异常,另一个仍然 tick。

注意:
- 不要为了制造测试而写奇怪业务逻辑。
- 如果代码当前没有自然异常路径,可只报告设计风险。

### R.5 planner 输出校验与来源标记

检查:
- planner 返回非 list 是否失败可控。
- planner 返回非 `QueuedAction` 是否失败可控。
- planner 返回超过 `max_planner_actions` 是否截断。
- planner 返回 `ActionSource.EMERGENCY` 是否保留。
- emergency reason 下返回的普通 planner action 是否需要强制 source 为 `EMERGENCY`。

建议:
- 不必强制所有 emergency action source 都改成 `EMERGENCY`,但要明确设计选择。
- 如果未来 Godot 要显示“紧急动作”,source 或 reason 需要可追踪。

### R.6 fallback idle 行为

检查:
- fallback 是否只在队列空且 pending 存在时创建。
- fallback 是否会导致低水位不断重复触发 planner。
- fallback 完成后如果 planner 仍没返回,是否继续短 idle,画面不冻结。
- planner 连续失败时是否能继续 fallback,并保留 failure count。

建议测试:
- slow planner 长时间不返回,多次 tick 后 agent 连续 idle,且没有创建多个 pending task。
- planner 连续失败 3 次后仍不崩,可 logger warning。

### R.7 snapshot 安全性

检查 `AgentRuntime.snapshot()`:
- 是否直接暴露可变 `state` / `plan` 引用。
- 是否直接暴露 action `args` 引用。
- WebSocket 发送前修改 snapshot 是否会污染 runtime。

推荐方向:
- 对 `state` / `plan` / `args` 做 shallow copy 或 `copy.deepcopy`。
- 如果担心性能,至少 action `to_dict()` 中复制 `args`。

建议测试:
- 修改 snapshot 返回的 queue action args,不影响原 action args。
- 修改 snapshot["state"],不影响 agent.state。

### R.8 action 时间语义

检查:
- `QueuedAction.start()` 被重复调用是否允许。
- 已经 start 的 action 被重新 enqueue / start 是否可能覆盖 `started_at`。
- `advance(dt)` 对很大 dt 的 clamp 是否正确。
- `dt=0` 是否不会造成异常。

建议:
- 当前允许重复 start 不一定是 bug,但要明确是否可接受。
- 如果要收紧,可在 `start()` 中仅当 `started_at is None` 时设置,重复 start logger warning 或 no-op。

### R.9 plan memory 写入

检查:
- plan memory 内容是否足够可读。
- keywords 是否可能包含空字符串或不可序列化值。
- `MemoryStore.insert()` 异常是否被捕获。
- 写入的 `game_time` 是否是 planner 完成时 tick 的时间,而非 planner 启动时间。

注意:
- Block D 的 plan memory 是“薄写入”,不是 reflection。
- 不要调用 LLM 总结 plan。

### R.10 世界观占位符

检查:
- `PromptBuilder.LAYER_0_SYSTEM` 不含“青岚镇”。
- 包含 `[WORLD_PENDING]`。
- 没有写死最终僵尸 / 政府 / 警察设定。
- Layer 0+1 稳定性测试仍通过。

---

## 允许的小范围修复

如果确认存在问题,可以优先修这些:

1. `QueuedAction.to_dict()` 复制 `args`,避免 snapshot 污染 runtime。
2. `AgentRuntime.snapshot()` 复制 `state` 与 `plan`。
3. 为 fallback 长时间等待场景补测试。
4. 为连续 emergency 补测试。
5. 为 planner 返回过多 actions 补测试。
6. 清理 emergency cancel 后可能的未取异常。
7. 若实现简单,把 plan memory 写入迁移到后台 write task,并在 `shutdown()` 中清理。

不要修这些:

1. 不要接入 DeepSeek。
2. 不要设计最终 action schema。
3. 不要实现对话状态机。
4. 不要新增 API 路由。
5. 不要改 Godot 文件。

---

## 建议补充测试

视时间选择,优先级从高到低:

1. `test_snapshot_does_not_expose_mutable_runtime_state`
2. `test_fallback_repeats_without_duplicate_pending_task`
3. `test_planner_result_truncated_to_max_actions`
4. `test_second_emergency_replaces_first_emergency_pending`
5. `test_emergency_discards_done_regular_pending_result`
6. `test_tick_all_agent_failure_isolated_or_documented`
7. `test_plan_memory_write_failure_does_not_crash_tick`

测试原则:
- 不调用真实 API。
- 不使用真实 sleep 等待。
- 用 `asyncio.Event` 控制慢任务。
- 测试结束必须清理 scheduler pending task。

---

## 输出格式

最终回答必须使用代码审查格式:

1. **Findings**
   - 若有问题,按严重程度排序。
   - 每条包含文件路径、行号、风险说明、触发条件、建议修复。
   - 不要把风格偏好伪装成 bug。

2. **Fixes Applied**
   - 如果做了修复,列出改动文件与修复内容。
   - 如果没有修复,写“无”。

3. **Verification**
   - 写明实际运行的命令与结果:

   ```powershell
   pytest -v tests/test_scheduler.py tests/test_smoke.py tests/test_memory.py
   ruff check src tests
   mypy src
   ```

4. **Residual Risks**
   - 仍建议留给 Block E/H 的风险。
   - 尤其说明 plan memory 写入是否仍在 tick 路径上。

---

## 通过标准

本 Review 通过需要满足:

- 没有 P0/P1 未解释风险。
- 若修改代码,所有 Block D 验证命令通过。
- 若不修改代码,必须清晰说明“未发现需要修改的问题”或列出可接受风险。
- 不引入真实 API 调用。
- 不扩大到 Block E/H。

---

## 我对这次 Review 的判断

Block D 当前报告很漂亮,但它仍然值得复审。原因是 Action Queue 调度器属于“短测试容易过,长时间运行才暴露问题”的模块。

我尤其关心三个点:

1. **tick 快路径里是否混入了慢 IO**。即使 SQLite insert 很快,未来 agent 多起来后也可能变成肉眼卡顿。
2. **取消任务是否彻底**。asyncio 里的 cancel 如果不收割,经常会在长跑时留下 warning 或幽灵状态。
3. **snapshot 是否隔离运行时状态**。Block H 会频繁把 snapshot 发给 Godot,如果 snapshot 里暴露可变引用,后面很容易出现“UI 改了状态”的诡异 bug。

这次 Review 的目标不是把 D 做得花哨,而是确认它够稳,可以放心承接 Block E 的真实 LLM planner。
