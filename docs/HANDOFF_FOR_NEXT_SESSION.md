# 给下一个 Claude Code Session 的接手说明

> **写于**:2026-05-17,Day 1 MVP 完成、Eric 让我"持续打磨"后开新 session 准备处理 UI 重做的节点。
> **当前 worktree**:`C:\Users\Administrator\Documents\block7-sim\.claude\worktrees\musing-dijkstra-847010`
> **branch**:`claude/musing-dijkstra-847010`

---

## 30 秒快速恢复

1. `cd worktree backend && python -m pytest -q` 应得 **115 passed**
2. `git log --oneline -15` 看最近 15 个 commit
3. 读 `docs/CLAUDE.md`(< 1 分钟,红线)
4. 读 `docs/工作展望.md`(< 5 分钟,当前进度 + Block 详规)
5. 这份 `HANDOFF_FOR_NEXT_SESSION.md`(< 5 分钟,session 续接)

---

## Eric 当前的工作流(2026-05-17 拍板)

**兵分两路**:
- **Eric 这一路**:开 Claude.ai 网页对话讨论游戏设计 → 找 Claude Design 重做 UI → 导入设计稿
- **Claude Code 这一路**(我):后台"持续打磨系统",持续修小 bug + 完善文档 + 提升质量

**交接物**:
- `docs/HANDOFF_TO_CLAUDE_DESIGN.md` — Eric 复制粘贴到 Claude.ai 用的项目交接包
- `docs/UI_REDESIGN_BRIEF.md` — 专门给 Claude Design 看的 UI 重做简报(更精简)
- 本文档 — 给"下一个 Claude Code session"用,确保连续性

---

## Day 1 MVP 完成情况(2026-05-17 23 个 commit 的全图)

```
387306f  Block H Godot 端实装
c9c8bd1  docs 同步
082f6a8  BC 成本控制
afd0349  Block I 对话状态机 初版
5913bb7  Block I bug fix(observers / 中文名反查)
d42cb3e  Block I 精修(气泡时长 / LoadingOverlay)
f25e9fd  Block G 反思 + 压缩
24207d7  docs 同步 Day 1 MVP 完成
f2756e5  精修轮次 2(fallback / 时钟插值 / Block G 可见化)
a5b808f  LoadingOverlay 兜底(超时 / 反思触发即完成)
492145b  反思并发限制 + memory 面板反思高亮
f73d767  启动脚本端口冲突 + LoadingOverlay 隐藏 game_time
```

**测试基线**:115 mock 测试全绿 + 3 真实 API 集成测试(¥0.05/次,需 .env)

---

## 红线(动手前必读)

详见 `docs/CLAUDE.md`。最重要的几条:

1. **不引入 embedding / 向量检索**
2. **不破坏 Layer 0 / 1 字节稳定**(改 LAYER_0_SYSTEM 或 build_rich_layer_1 必须重跑 `tests/test_cache_hit_rate.py`)
3. **scheduler.tick 永不阻塞** — LLM 调用走 `asyncio.create_task`
4. **PlanProvider / PerceptionListener / DialogueGuard Protocol 是稳定契约**
5. **暮谷镇 LAYER_0 + 12 personas 是叙事核心** — 改 = 缓存失效 + 角色行为跑偏
6. **不能 amend / force-push** — 修上一 commit 就创建新 commit
7. **Pro think_high 调用必须 `max_tokens ≥ 3000` + client timeout ≥ 90s**
8. **不主动写文档** 除非 Eric 明确要求(本文档是 Eric 在 2026-05-17 明确要求才写)

---

## 已知遗留(Day 2 UX 修一波时一起处理)

| # | 问题 | 修复建议 |
|---|---|---|
| 1 | R 键既是刷新又被 Eric 期待打开 reflection 面板 | R 改为打开 reflection panel,刷新改 F5;或者 memory 面板加 tab 按钮(全部/反思/观察/计划) |
| 2 | Inspector 9 人时与 agent 名牌重叠 | 4×3 grid 改 6×2 或别的布局;或者 Inspector 改成右侧滚动列表(已是 ScrollContainer 但宽度不够) |
| 3 | 💭 思考灯泡偶尔残留(thinking_completed 后 1-2 帧才隐藏) | _on_agent_thinking_completed 立即 set visible=false,加 force redraw |
| 4 | agent 名牌 4×3 网格撞位(同 hash 落同格) | `_slot_position_for` 用更稳定的分配(或预先洗牌) |
| 5 | "时针秒针各走各"(time_scale=3600 下分钟跳变) | 已部分解决(GameWorld._process 本地插值),但加速模式仍跳。可以考虑加速模式下隐藏 minute 只显示 hour |
| 6 | `daily JSON parse failed` 偶发(daily plan 解析失败,LLM 返回非纯 JSON) | 加更强的 fallback parser(找第一个 `{` 到最后一个 `}` 容错) |
| 7 | day=2/3/7 反思条数=0(端到端测试观察到) | source memory 不足或 LLM 返回空。考虑放宽 min_importance=4 → 3 |

---

## 我在 Eric 出差期间的"持续打磨"任务清单

> 这是我接手"自动化打磨"后给自己排的工作。**请下一任 session 检查这些任务的状态**——它们应该作为独立 commit 出现在 git log。

### 优先级 1(必做)
- [ ] **修 #1 R/O/P 快捷键 / memory 类型 tab**——MemoryPanel 顶部加 4 个 Button(全部 / 🌒 反思 / 👁 观察 / 📋 计划),点击切换 filter
- [ ] **修 #6 daily JSON parse 容错**——_parse_daily_slots 用更宽松正则,LLM 偶尔输出带 markdown 包裹时也能解析
- [ ] **修 #4 _slot_position_for 撞位**——改用 sorted agent_id index 而不是 hash

### 优先级 2(应做)
- [ ] **修 #3 💭 残留**——AgentNode.on_thinking_completed 加 `await get_tree().process_frame` 确保下一帧不再可见
- [ ] **修 #2 Inspector 撞位**——把 ScrollContainer 宽度从 258 扩到 290;或者 inspector 列表项加 padding
- [ ] **加 GET /agent/{id}/reflections 专用端点**——返回仅 type=reflection 的最近 N 条,Godot 端可单独拉

### 优先级 3(可选)
- [ ] **修 #7 反思 0 条问题**——放宽 min_importance=4→3,或者加 LLM 重试一次
- [ ] **加 backend 健康检查路由**——GET /sim/health 返回 reflection 失败率、平均 LLM 延迟、各 model token 消耗
- [ ] **加 daily plan prompt 微调**——Eric 测试时偶尔看到 daily plan 不调用 talk_to(对话频率低),加规则 "至少 1-2 个时段考虑 talk_to(args.agent_id)"

### 优先级 4(实验性)
- [ ] **跑长时间 sim 压测**——在 LL 模式(low LLM,只用 Flash)跑 2-3 游戏日,看 memory 表增长曲线 + 压缩有效性
- [ ] **加 sim 历史回放**——把每次跑的 SimEvent 序列化到 JSON,后续可以重放

---

## 关键文件地图(给新接手 Claude 用)

```
backend/
├── src/
│   ├── agent/
│   │   ├── runtime.py            AgentRuntime + QueuedAction + ThinkingReason
│   │   ├── scheduler.py          ActionScheduler + 3 Protocols + 调度循环 (Codex)
│   │   ├── planning.py           LLMPlanner + PersonaLoader + LocationLoader + 4 层 prompt
│   │   ├── perception.py         PerceptionBroker + dialogue trigger + 中文名反查
│   │   ├── dialogue.py           DialogueSession + DialogueManager (Block I)
│   │   └── reflection.py         ReflectionRunner Pro+think_high (Block G,semaphore=3)
│   ├── memory/
│   │   ├── schema.py             SQLite DDL
│   │   ├── store.py              MemoryStore CRUD + 检索 + ImportanceScorer + Block G 查询
│   │   └── compression.py        MemoryCompressor 1-7天合并 + 7天前 archive (Block G)
│   ├── llm/
│   │   ├── deepseek.py           DeepSeekClient 异步 + 重试 + 计费 (Block B)
│   │   └── prompt_builder.py     LAYER_0_SYSTEM + 6 字段 AgentPersona Layer 1
│   ├── api/
│   │   ├── routes.py             HTTP /world /agents /agent/{id}/state/memories + /sim/pause/resume/state
│   │   └── websocket.py          WS /ws/sim
│   ├── sim/
│   │   └── engine.py             SimEngine + 跨日触发 + emit_event
│   ├── config.py                 Settings 绝对路径解析
│   └── main.py                   lifespan 配线全部
└── tests/                        115 mock + 3 真实 API

godot_client/
├── project.godot                 autoload (GameClock/GameWorld/BackendClient) + 数字键 1/2/3/4 input map
├── scripts/
│   ├── game_clock.gd             autoload,Block A 占位(没真用)
│   ├── game_world.gd             autoload,12 agent 状态镜像 + signal 总线 + warmup tracker
│   ├── backend_client.gd         HTTP + WS + 重连 (WS 状态机 bug 已修)
│   ├── main.gd                   Main 场景控制 + HUD 接 signal
│   ├── location_view.gd          LocationView 基类
│   └── agents/AgentNode.gd       AgentNode 加 SpeechBubble (Block I)
├── scenes/
│   ├── Main.tscn                 顶层场景 + HUD(TimePanel/Inspector/MemoryPanel/PausePanel/ReflectionPanel/LoadingOverlay/NavLabel)
│   ├── AgentNode.tscn            AgentNode 模板
│   ├── LocationView.tscn         LocationView 模板
│   └── locations/                4 个 inherited scene
└── assets/
    ├── characters/agent_04/      艾琳的全套 sprite + 5 张感染态变体
    ├── characters/agent_01-12/   其它 11 个目录基本空,只有 .gitkeep
    ├── locations/                4 张 ChatGPT 生成场景图
    └── portraits/agent_04/       艾琳胸像

scripts/
└── launch_backend.ps1            统一启动脚本(端口冲突自动清理)

docs/
├── CLAUDE.md                     工作守则 + 红线
├── 工作展望.md                   接手指南 + 当前进度 + 剩余 Block 详规
├── Day1_工作总结.md              历史轨迹 + 实测数据 + 踩坑
├── Project_Design_Document_v0_2.md  架构总纲
├── HANDOFF_TO_CLAUDE_DESIGN.md   Eric 给 Claude.ai 的交接包(2026-05-17 新)
├── HANDOFF_FOR_NEXT_SESSION.md   本文(2026-05-17 新)
└── worldview/                    暮谷镇 LAYER_0 / 催化剂 / 未决项
```

---

## Eric 接下来可能扔回来的需求

1. **Claude Design 给了 UI 设计稿** → 你看图实装(主要改 Main.tscn 各 panel 样式 + 可能加新 .tscn)
2. **11 个角色 sprite** → 放到 `godot_client/assets/characters/agent_xx/`(命名规范 walk_n/s/e/w.png + idle.png + portrait.png)
3. **新 Block J/K/L** → 按 `docs/工作展望.md` 的规划走
4. **新 worldview 调整** → 修改 persona YAML 或 LAYER_0_SYSTEM(注意红线 #2 + #5)
5. **测试问题反馈** → 截图 + console 输出,定位 bug 修复

---

## 协作风格(关键)

- **Eric 不是程序员** — 技术决策给 2-3 个对照选项让他选,不要直接拍板
- **类比 + 大白话** — asyncio / WebSocket / 缓存命中率用日常类比解释
- **变更前先核对状态** — Eric 可能与其它 Claude/Codex 并行,改主目录前先 `git status`
- **真实 API 验证比单测有效** — 涉及 prompt 设计的 Block 必须做一次真实调用
- **每个 Block 独立 commit** — commit 信息中文,体例参照已有 commit
- **占位函数留 `raise NotImplementedError("Block X 实现")`** 标注归属
