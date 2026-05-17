# CLAUDE.md — Block-7 项目工作守则

**项目代号**:Block-7 生成式智能体社会模拟器(暮谷镇)
**当前阶段**:Day 1 MVP **全部完成**(A→I,含暮谷镇世界观);BC 成本控制开关已上;**Eric 在外讨论 UI 重做**(Claude.ai + Claude Design),Claude Code 后台持续打磨
**协作主理**:Eric(高三学生,非专职程序员)

---

## ⚡ 你接手时请按这个顺序读

1. **本文档**(< 1 分钟):红线 + 索引
2. **[`HANDOFF_FOR_NEXT_SESSION.md`](HANDOFF_FOR_NEXT_SESSION.md)**(5 分钟):**session 续接说明 + 打磨任务清单 + 文件地图**——2026-05-17 新写,优先读
3. **[`工作展望.md`](工作展望.md)**(5 分钟):接手指南 + 剩余 Block 详规 + 待 Eric 拍板事项
4. **[`Day1_工作总结.md`](Day1_工作总结.md)**(可选,5 分钟):历史轨迹 + 实测数据 + 踩坑记录
5. **[`Project_Design_Document_v0_2.md`](Project_Design_Document_v0_2.md)**(查阅型):架构总纲

> 不要直接看 `Day1_Block_*_Task.md`——那些是历史任务派单,可能与当前代码不一致。

**给 Eric 的对外交接包**(他在 Claude.ai 网页端讨论设计时复制粘贴用):
- [`HANDOFF_TO_CLAUDE_DESIGN.md`](HANDOFF_TO_CLAUDE_DESIGN.md):完整项目交接包
- [`UI_REDESIGN_BRIEF.md`](UI_REDESIGN_BRIEF.md):专门给 Claude Design 看的 UI 重做简报

---

## 🚫 八条红线(动手前确认)

1. **不引入 embedding / 向量检索**。Memory 召回只能 SQLite LIKE + 时间衰减。严禁 sentence-transformers / faiss / chromadb / langchain。
2. **不破坏 4 层 prompt 缓存的字节稳定性**。改 LAYER_0_SYSTEM 或 build_rich_layer_1 → 必须重跑 `pytest tests/test_cache_hit_rate.py` 确认仍 ≥ 90%。
3. **scheduler.tick 永不阻塞**。LLM 调用全部走 asyncio.create_task,通过 _memory_write_tasks 集合追踪。
4. **PlanProvider / PerceptionListener Protocol 是稳定契约**——改签名会震动调度器与所有 mock。
5. **暮谷镇 LAYER_0 + 12 personas 是叙事核心**——改这些 = 缓存失效 + 角色行为跑偏。
6. **不能 amend / force-push 已有 commit;不能 --no-verify 跳 hook**——遇修上一 commit 的需求,创建新 commit。
7. **Pro think_high 调用必须 max_tokens ≥ 3000 + client timeout ≥ 90s**(推理 token 也吃 max_tokens 配额)。
8. **不主动写文档**(README / *.md)除非 Eric 明确要求。

---

## 当前 Block 进度(详见 [工作展望.md](工作展望.md))

| Block | 内容 | 状态 |
|---|---|---|
| A | 项目骨架 | ✅ |
| B | DeepSeek 客户端 + 4 层缓存 | ✅ 命中率 92.9% |
| C | Memory 子系统 | ✅ |
| **+** | 暮谷镇世界观锁定 | ✅ |
| D | AgentRuntime + Action Queue 调度器 | ✅ Codex 实现 |
| E | 粗 + 细两层规划器 | ✅ |
| F | Perception 同场所传播 | ✅ |
| H | FastAPI + WebSocket + Godot 端联调 | ✅ 51ee432 + 387306f |
| BC | 成本控制(暂停按钮 + scheduler 频率优化) | ✅ 082f6a8 |
| I | 对话状态机(DialogueSession + SpeechBubble) | ✅ afd0349 + 5913bb7 + d42cb3e |
| G | 每日反思 + memory 压缩(跨日触发) | ✅ f25e9fd |

测试基线:**122 mock 测试全绿** + 3 真实 API 集成测试(¥0.05/次,需 .env)。

**Day 1 MVP 全部完成**:sim 引擎 + Godot 端实时显示 + 对话 + 反思 + 压缩。
12 agent 真实活动 + 对话 + 跨日反思,论文级别的 emergent narrative。

**2026-05-17 持续打磨 14 commit** 完成。详见
[HANDOFF_FOR_NEXT_SESSION.md](HANDOFF_FOR_NEXT_SESSION.md)。
真实 API 验证缓存命中率 **92.9%**(无破坏 Layer 0/1 字节稳定)。

---

## 协作风格

- **Eric 不是程序员**:决策时给 2-3 个对照选项让他选,不要直接拍板。
- **大白话 + 类比**:解释 asyncio / cache / WebSocket 用日常类比。
- **变更前先核对状态**:Eric 可能与 Codex 或其它 Claude 并行;改主目录前先 `git status`。
- **真实 API 验证比单测有效**:涉及 prompt 设计的 Block 必须做一次真实调用(¥0.02–0.05)。
- **每个 Block 独立 commit**:不要揉一起;commit 信息中文,体例参照已有 commit。
- **占位函数留 `raise NotImplementedError("Block X 实现")`** 标注归属。

---

## 开发命令(Windows / PowerShell)

```powershell
.\dev.ps1 install   # pip install -e ".[dev]"
.\dev.ps1 backend   # uvicorn 启动后端
.\dev.ps1 test      # pytest
.\dev.ps1 lint      # ruff + mypy
```

mac/linux 用 `make install / backend / test / lint`。
