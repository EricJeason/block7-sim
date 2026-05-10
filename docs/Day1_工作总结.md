# Day 1 工作总结

> 期间:2026-05-02(Day 1 上半,Block A/B/C)+ 2026-05-10(Day 1 下半,世界观敲定 + D 合并 + E + F)
> 协作:Eric(主理) × Claude Opus 4.7 × Codex (ChatGPT 5.5,负责 Block D)
> 状态:Day 1 backend MVP 实质完成 (A→F),进入收尾(G/H 待做)

---

## 一句话总结

按 v0.2 设计文档原本"两天紧急开发"的节奏,**Day 1 单日交付了 6 个 Block (A→F) + 暮谷镇世界观敲定 + 真实 API 验证**——超额完成了原计划 Day 1 + Day 2 上午的全部 backend 工作。Sim 引擎内部已闭环:Planner 产出 Action → Scheduler 推进 → Action 完成 → Perception 写 observation → 下一轮 Planner 自然感知到。

---

## 时间线

### 第一阶段:2026-05-02(基础设施)

| 时间 | Commit | Block | 内容 |
|---|---|---|---|
| 17:32 | fb2ade9 | A | 项目骨架:Python 后端 + Godot 客户端占位,21 个模块文件,FastAPI `/health`,4 个 smoke 测试 |
| 17:59 | b3c6834 | B | DeepSeek 异步客户端 + 4 层 Prompt 缓存,真实命中率 **91.2%**(青岚镇占位 LAYER_0) |
| 18:14 | 1031e32 | C | Memory 子系统:SQLite schema + CRUD + 关键词检索 + 时间衰减打分 + LLM 批量重要性打分 |

### 第二阶段:2026-05-10(世界观 + D 合并 + 上层逻辑)

| 时间 | Commit | Block | 内容 |
|---|---|---|---|
| 22:10 | 4cc2fd9 | — | **暮谷镇世界观接入**:替换 LAYER_0(青岚镇 → 暮谷镇),12 个 persona YAML + 4 个 location + 催化剂 + 未决项,真实命中率 **92.9%** |
| 22:18 | c805e0d | D | **合并 Codex Block D**:AgentRuntime + Action Queue 调度器(491 行)+ 21 个调度测试。冲突点 prompt_builder.py 保留暮谷镇,丢弃 [WORLD_PENDING] 占位 |
| 22:43 | c41ac02 | E | **粗 + 细两层规划器**:LLMPlanner 实现 PlanProvider Protocol,PersonaLoader / LocationLoader / build_rich_layer_1,20 测试,全 mock |
| 22:56 | 7525ccd | E | **真实 API 验证 + 三处修复**:暴露 max_tokens / timeout / location id 三个 bug 一并修掉,跑通林秋真实 daily + fine |
| 23:08 | 666e870 | F | **Perception 同场所事件传播**:PerceptionBroker + scheduler 接入 + 17 测试,完成 sim 内部闭环 |

---

## 关键架构决策(及为什么)

### 1. 取消向量检索,只用关键词 + LLM in-context recall
**为什么**:DeepSeek 没有原生 embedding API;V4-Pro 1M 上下文 + 默认思维链能力够强,让 LLM 自己在 prompt 里挑相关 memory 比 cosine similarity 准。  
**代价**:大量旧 memory 时需要 SQL 粗筛(`LIKE` + 时间衰减 + importance 加权)。  
**禁区**:严禁引入 sentence-transformers / faiss / chromadb / langchain。

### 2. 4 层 Prompt 缓存结构,前 3 层字节稳定
- Layer 0:暮谷镇世界观(~1280 tokens,所有 agent 共享,**永不变**)
- Layer 1:agent persona(~600 tokens,同 agent 跨调用稳定)
- Layer 2:近期记忆 + 当前情境(每次变)
- Layer 3:本次任务 prompt(每次变)  

DeepSeek 缓存按 token 前缀匹配,前 3 层字节稳定 → 命中率 92.9%(实测 30 轮)。**改动 LAYER_0_SYSTEM 必须重跑命中率回归测试**。

### 3. 快动作慢思考(Codex Block D + Block E 联合实现)
- Action Queue 调度器永不阻塞游戏循环
- LLM 规划在背景 asyncio.Task 里跑,完成后追加到队列尾部
- 队列水位 < 30 游戏秒时触发新一轮思考
- 紧急事件(importance ≥ 8)触发 emergency replan,清队列尾段但不打断当前原子动作

### 4. PlanProvider / PerceptionListener Protocol 解耦
Scheduler 不依赖具体 LLM 或 Memory 实现,只依赖两个 Protocol。这意味着:
- 测试可以注入 mock,完全不烧 API
- 切换 LLM 厂商或 prompt 策略不影响 scheduler

### 5. 暮谷镇世界观直接 baked into Layer 0(放弃占位策略)
**为什么变**:Codex 当时按 v0.2 文档原意,把世界观留为 [WORLD_PENDING] 占位,等 Block H 注入。Eric 在 5-10 决定不再留占位。  
**取舍**:Baked 写法损失了"换世界观无需改代码"的灵活性,但缓存命中率从 91.2% 提升到 92.9%(更多 token 进缓存),且避免了将来再次解耦的工程成本。  
**前提**:暮谷镇是定下来的世界,不会再换。

### 6. 富 schema PersonaProfile vs 6 字段 AgentPersona 并存
- AgentPersona(6 字段,frozen):供 ImportanceScorer 等不需要全套人设的轻量场景
- PersonaProfile(22 字段,frozen):供 LLMPlanner 构造富 Layer 1
- 两者形成独立的 DeepSeek 缓存命名空间,互不污染

---

## 实测发现(踩过的坑 + 数据)

### Cache hit rate 实测
| Layer 0 内容 | 字数 | 命中率 | 备注 |
|---|---|---|---|
| 青岚镇(Block B) | ~1900 字 / ~900 tokens | **91.2%** | 刚过 90% 硬关卡 |
| 暮谷镇(Day 1 收尾后) | ~2400 字 / ~1280 tokens | **92.9%** | 长 Layer 0 反而帮助命中(更多 cached input) |

### Block E 真实 API 暴露的 3 个 bug
1. **DeepSeekClient 默认 timeout=30s 太短**:Pro think_high 推理 30-60s,大 prompt 必抛 ReadTimeout。改为 120s。
2. **_plan_daily max_tokens=800 太小**:think_high 模式的"推理 tokens"也吃 max_tokens 配额,800 下推理吃完所有预算,JSON 输出在第一个 slot 的 notes 中段被截断。改为 3000。
3. **Flash 不知道 location id 列表**:fine plan 输出 `move_to(location="医工坊")` 而不是 `lao_song_plaza`。修:把 location_options 注入 fine prompt + 加规则"location 必须用 id"。

### Prompt 输出质量(林秋真实 daily plan 实测)
think_high 自发引用了 persona 多个层面 + catalyst 元素:
- "顺便看阿杏夜里有没有留字条"(known_secrets:怀疑阿杏是高频感染者)
- "歪脖子松树好像又高了点"(catalyst:老松树似乎在缓慢长高)
- "多要一小块边角料带回研究"(long_term_goal:根治稳定解药)
- "实在睡不着索性再翻一遍笔记"(personality:失眠是常态)

这是论文级别的角色一致性。结论:**4 层 prompt + 富 PersonaProfile + 暮谷镇 LAYER_0 真的喂得动 think_high**。

### API 成本(实测)
| 调用 | 模型 | 模式 | 单次成本 | 单次延迟 |
|---|---|---|---|---|
| Daily plan | V4-Pro | think_high | ~¥0.024 | ~80s |
| Fine plan | V4-Flash | non_think | ~¥0.002 | ~5s |
| Importance scoring(5 条/批) | V4-Flash | non_think | ~¥0.0001 | ~1.5s |
| Cache hit rate 测试(30 轮) | V4-Pro | non_think | ~¥0.014 / 30 轮 | ~1.7s/次 |

按 12 agent × ~10 fine + 1 daily / 游戏日,backend 端约 ¥0.3/游戏日。

---

## 当前能力清单

### Sim 引擎能做的
- 多 agent 注册到 ActionScheduler,各自维护独立 Action Queue 与 pending_thinking 状态
- tick 推进当前动作 + 收割完成的 LLM 思考结果 + 触发新一轮思考(队列水位)
- 紧急 replan(清队列尾段,不打断原子动作)
- LLMPlanner 按粗→细两层产出 actions:粗粒度日程按 game_day 缓存,细粒度按 slot + 近期记忆展开
- 紧急分支跳过粗粒度,直接基于 urgent_event 生成短动作
- Perception:action 完成时,同场所其他 agent 自动获得一条 observation memory
- move_to action 完成时自动更新 actor.current_location(只接受 location_loader 中存在的 id)
- 关系加权 importance:观察者与 actor 有 initial_relationship → memory importance +1
- 4 个场所 / 12 个角色全部从 YAML 加载,内存缓存

### 还做不到(Block G/H 待补)
- 反思:每日游戏日结束时回顾当日 memory 提炼高层 reflection
- 旧 memory 压缩归档(防止跑长游戏 token 爆炸)
- FastAPI 路由暴露 agent 状态 + memory 历史
- WebSocket 推送 sim 事件流给 Godot 客户端
- Godot 端真正显示角色行为(目前只有 hello world 标签)

---

## 测试覆盖

```
69 passed in 1.05s
- test_memory.py     :  7  Block C
- test_perception.py : 17  Block F
- test_planning.py   : 20  Block E
- test_scheduler.py  : 20  Block D (Codex)
- test_smoke.py      :  5  Block A/B + 暮谷镇锁定
```

不计入常规跑(需真实 API key):
- test_cache_hit_rate.py:35 轮真实 API 跑命中率回归(¥0.02 / 次)
- test_memory_integration.py:1 次真实 importance 打分(¥0.0001)
- test_planning_integration.py:1 次真实 daily + fine(¥0.026)

---

## 未决项与遗留 TODO

### 高优先级(影响后续 Block)
- **暮谷镇 layer_0 中的"霜髓节"是 Claude 整理时加的**(见 [docs/worldview/暮谷镇_未决项.md](worldview/暮谷镇_未决项.md))——Eric 待确认保留或删除
- **大魔潮"重置"是字面时间倒流还是仅治愈**——影响 Block G 的反思逻辑(若是时间倒流,反思如何处理跨循环记忆?)
- **time_decay_lambda(memory 衰减速度)与 game_clock 的 time_scale 没正式对齐**——目前 store.py 注释里有 TODO,Block G 之前应该统一

### 中优先级(味道层 / 工程债)
- 缓存命中率 92.9%,余量只剩 2.9pp。改 Layer 0/1 必须重跑测试;最好加一个 CI 钩子。
- DeepSeekClient 的 thinking 字段格式是按猜测实现的(`thinking: {type, effort}`),Block B 注释说"若实际不同按实测调"——目前 Pro think_high 实测可用,但 fine plan 是 Flash non_think,没验证 Flash + think 是否会出错
- planning.py 模块级 plan_daily / plan_fine 仍是 NotImplementedError,需要被 Block H 联调时彻底删除或重定向

### 低优先级
- agent.current_location 默认空字符串,但 perception 要求非空才广播——初始化时应统一从 persona.initial_location 填,目前在测试里手动填
- 多余 worktree 空目录 `.claude/worktrees/eager-herschel-fcfd3e/`(被会话锁着删不掉)——下次 Eric 重启 Claude 后手动 rmdir

---

## 协作回顾

- **与 Codex 的合并冲突**:Codex 上周做完 Block D 后没合并,Eric 派工时也忘了告知。今天 Day 1 收尾时撞上,通过 stash + ff merge + cherry-pick 风格的 prompt_builder.py 冲突保留我方版本完成合并。**经验**:派工前先 git status 主目录,避免类似情况
- **与 claude.ai 的世界观对话**:工作流是"Eric 上传 worldview_kit 三份引导文档 → 与 claude.ai 端对话深挖 → 上传输出规范文档收稿"。这一轮产出 17 份高质量文件(world / locations / 12 personas / catalyst / pending),质量超出预期
- **真实 API 验证的 ROI**:Block E 一次 ¥0.026 的集成测试当场抓出 3 个 bug,远比单测有效。**经验**:涉及 prompt 设计的 Block 必须做一次真实调用验证

---

## 下一步指引

接下来做什么、未决事项怎么办、未来 Claude 怎么接手——见 [docs/工作展望.md](工作展望.md)。
