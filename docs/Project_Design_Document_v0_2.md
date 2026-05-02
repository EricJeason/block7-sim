# 项目设计文档 v0.2 · 紧急开发版

> **代号**：Block-7（待 Jesason 最终敲定世界观）
> **基于**：v0.1 的修订与升级
> **核心变更**：取消向量检索 / 引入快动作慢思考架构 / 上下文缓存最大化 / 两天紧急开发节奏
> **更新时间**：2026-05-01
> **状态**：等待审阅 → 立即进入 Day 0 准备

---

## 0. v0.2 相对于 v0.1 的关键变更

| # | 变更 | 影响范围 |
|---|------|----------|
| 1 | 取消 embedding/向量检索，改用 in-context recall + 关键词粗筛 | Memory 模块、Retrieval 模块、依赖列表 |
| 2 | 引入 Action Queue + 异步思考管道（"快动作慢思考"） | 整个 Agent 大脑层、时间系统 |
| 3 | LLM 切换至 DeepSeek V4-Pro（1M 上下文 + 默认思维链） | LLM 接口层、prompt 设计 |
| 4 | 引入 4 层 Prompt 缓存结构以最大化命中率 | 所有 Prompt 模板 |
| 5 | 时间表压缩为两天紧急开发（Phase 1A + 1B） | 路线图、任务清单 |
| 6 | 美术资产改为直接使用图片贴图（不强制像素化） | 美术工作流 |
| 7 | 世界观推迟到最后阶段敲定，用占位 ID + YAML 配置解耦 | 数据层、persona 文件 |

---

## 1. 核心架构创新：快动作慢思考

### 1.1 设计动机

LLM 调用延迟约 1-5 秒（V4-Pro 实测延迟方差较大）。如果让 agent 在游戏里"原地等 LLM 思考"，体验会非常糟糕——玩家看到 NPC 时不时凝固几秒。

但人类大脑也不是即时反应的。我们走在路上时，大脑已经在想下一步；说话时下一句还没成型。**思考永远比执行超前一步**。我们的架构模仿这个：游戏循环只负责按已规划好的动作清单执行，**永远不等 LLM**；LLM 在后台异步思考，结果到达后追加到清单尾部。

### 1.2 核心数据结构：Action Queue

每个 agent 维护一个动作队列：

```python
@dataclass
class QueuedAction:
    action_type: str              # move_to / interact / talk_to / idle / sleep / ...
    args: dict
    duration_seconds: float       # 这个动作在游戏中执行需要的时间
    started_at: Optional[float]   # 开始执行时的游戏时间戳
    interruptible: bool = True    # 是否可被打断

@dataclass
class AgentRuntime:
    agent_id: str
    action_queue: deque[QueuedAction]
    current_action: Optional[QueuedAction]
    pending_thinking: Optional[asyncio.Task]  # 当前正在跑的 LLM 思考任务
    last_thinking_started_at: float
```

### 1.3 调度循环（伪代码）

```python
async def agent_tick(agent: AgentRuntime, dt: float):
    # 1. 推进当前动作
    if agent.current_action:
        agent.current_action.elapsed += dt
        if agent.current_action.elapsed >= agent.current_action.duration:
            await complete_action(agent, agent.current_action)
            agent.current_action = None

    # 2. 弹出下一个动作
    if agent.current_action is None and agent.action_queue:
        agent.current_action = agent.action_queue.popleft()
        await start_action(agent, agent.current_action)

    # 3. 检查是否需要触发思考
    remaining_time = sum(a.duration for a in agent.action_queue)
    if agent.current_action:
        remaining_time += agent.current_action.duration - agent.current_action.elapsed

    THINKING_TRIGGER_THRESHOLD = 30.0  # 游戏秒
    if (remaining_time < THINKING_TRIGGER_THRESHOLD
        and agent.pending_thinking is None):
        agent.pending_thinking = asyncio.create_task(
            think_and_extend_queue(agent)
        )

    # 4. 检查思考是否完成（非阻塞）
    if agent.pending_thinking and agent.pending_thinking.done():
        new_actions = agent.pending_thinking.result()
        agent.action_queue.extend(new_actions)
        agent.pending_thinking = None

    # 5. 队列空 + 思考还没回 → fallback
    if (agent.current_action is None
        and not agent.action_queue
        and agent.pending_thinking is not None):
        agent.current_action = QueuedAction(
            action_type="idle",
            args={},
            duration_seconds=2.0,
        )
```

**关键点**：调度循环本身完全同步、无阻塞。LLM 调用在 asyncio 里跑，做完了再"汇入"队列。

### 1.4 紧急打断机制

对 importance ≥ 8 的事件，触发紧急 replan：

```python
async def trigger_emergency_replan(agent: AgentRuntime, event: Memory):
    # 当前正在执行的原子动作不可打断
    # 但队列后段可以全部清空，重新规划
    agent.action_queue.clear()

    # 取消正在跑的常规思考
    if agent.pending_thinking:
        agent.pending_thinking.cancel()

    # 启动紧急思考（带高优先级标识）
    agent.pending_thinking = asyncio.create_task(
        think_with_urgency(agent, urgent_event=event)
    )
```

注意：**当前正在执行的原子动作不可打断**——做饭做了一半物理上不能立刻停下；但做完后续的"吃、走"可以全部重来。

### 1.5 对话特殊模式

对话不走 Action Queue。当两个 agent 进入对话：

- 双方 Action Queue 暂停
- 进入对话状态机（`DialogueSession`）
- 每说一句话有 2-4 秒"打字+显示"时间，期间 LLM 生成下一句
- 任意一方决定结束（达到 max_turn 或 leave_dialogue），双方退出对话状态、重启 Action Queue

### 1.6 思考指示器（UI 副产物）

由于思考是显式异步的，我们可以**在 UI 上让玩家看到 agent 正在思考**——agent 头顶有时浮现一个灯泡 emoji（💭）。这把"AI 不确定性"变成了可见的设计语言。玩家会主动等 agent 想好，而不是抱怨它"为什么不动"。

---

## 2. 上下文缓存最大化策略

### 2.1 价格背景

> 截至 2026-05-05 限时优惠期内：
> - V4-Pro：缓存命中输入 0.025 元/M tokens，未命中 3 元/M，输出 6 元/M
> - V4-Flash：缓存命中输入 0.02 元/M tokens，未命中 1 元/M，输出 2 元/M
> - 1M tokens 上下文标配，384K tokens 最大输出

**关键洞察**：V4-Pro 缓存命中价是未命中价的 **1/120**。设计目标是让 95%+ 的输入 tokens 命中缓存。

### 2.2 4 层 Prompt 缓存结构

DeepSeek 的缓存机制是**前缀匹配**——只要前 N 个 tokens 与历史调用一致，前 N 个就命中缓存。所以**绝对禁止把变化的内容放前面**。所有 prompt 严格按下面顺序拼接：

```
┌─────────────────────────────────────────────────┐
│ Layer 0：世界观 + 全员人设速览（~5K tokens）      │  永远不变，所有 agent 共享
│   - 项目背景设定                                  │
│   - 全局规则                                      │
│   - 所有 agent 的一句话速览（"林夏：义体黑客..."）  │
├─────────────────────────────────────────────────┤
│ Layer 1：当前 agent 完整人设（~2K tokens）         │  几乎不变，跨 tick 保持
│   - 完整 backstory                                │
│   - 性格、目标、说话风格                            │
│   - 与其他 agent 的关系认知                        │
├─────────────────────────────────────────────────┤
│ Layer 2：最近 30 分钟世界事件（~8K tokens）        │  半小时滚动更新
│   - 经过粗筛的 50 条最相关 memory                   │
│   - 反思类记忆优先                                  │
├─────────────────────────────────────────────────┤
│ Layer 3：当前情境 + 决策提示（~2K tokens）         │  每次调用都不一样
│   - 当前游戏时间                                   │
│   - 当前位置                                       │
│   - 正在做什么 / 队列里接下来是什么                  │
│   - 即将决策的具体问题                              │
└─────────────────────────────────────────────────┘
```

### 2.3 单次调用成本估算

| 部分 | tokens | 单价（元/M） | 成本（元） |
|------|--------|-------------|-----------|
| Layer 0-2 命中 | 15,000 | 0.025 | 0.000375 |
| Layer 3 未命中 | 2,000 | 3 | 0.006 |
| 输出 | 500 | 6 | 0.003 |
| **小计** | | | **约 0.0094 元** |

10 agent × 100 次/agent/游戏日 = **约 9 元/游戏日**

如果游戏内 1 日对应现实 1 小时，**1 小时游戏 ≈ ¥9**。完全可控。开发期总预算 ¥100 仍然充足。

### 2.4 缓存预热策略

游戏启动时主动发一次 Layer 0+1 的 ping 调用，让缓存"热"起来。否则前几次调用都未命中，体验会有冷启动延迟。

```python
async def warmup_cache_for_agent(agent_id: str):
    """在 agent 真正开始决策前，预热它的 Layer 0+1 缓存"""
    prompt = build_layer0() + build_layer1(agent_id) + "\n\n# 预热\n请回答：你是谁？"
    await llm.chat(messages=[{"role": "user", "content": prompt}], max_tokens=20)
```

---

## 3. 无向量检索方案：In-Context Recall + 关键词粗筛

### 3.1 不用 embedding 的可行性

V4-Pro 的 1M 上下文 + 默认思维链能力，意味着把数百条 memory 直接塞进 prompt，让模型自己做"in-context retrieval"是可行的。LLM 的语义理解能力 >> cosine similarity。

但完全不筛也不行——agent 跑几天后，memory 数量会膨胀到几千条，全塞进去太浪费。所以用两层过滤。

### 3.2 第一层：关键词粗筛（纯 SQL，0 成本）

从当前情境提取**索引关键词**：当前位置 ID、最近接触的 agent ID、当前正在做的事情类型、最近 1 小时新增的 importance ≥ 6 的事件主题。

用这些关键词在 SQLite 里 LIKE 查询：

```sql
SELECT * FROM memories
WHERE agent_id = ?
  AND (
    content LIKE '%' || :keyword1 || '%'
    OR content LIKE '%' || :keyword2 || '%'
    OR JSON_EXTRACT(metadata, '$.location') = :current_location
    OR JSON_EXTRACT(metadata, '$.subject') IN (:nearby_agents)
  )
ORDER BY importance DESC, timestamp_real DESC
LIMIT 80;
```

宁可多召回，不要漏。

### 3.3 第二层：放进 Layer 2，让 LLM 自己挑

把粗筛的 80 条 memory 拼成 Layer 2，让 V4-Pro 在 in-context 中自己判断哪些是当前决策真正需要的。它的判断比 cosine similarity 准得多。

### 3.4 Memory 压缩策略（防止无限膨胀）

每个游戏日结束时批量执行：

| 时间段 | 压缩规则 |
|-------|---------|
| 最近 24 游戏小时 | 全保留，原文 |
| 1-7 天前 | importance ≥ 5 保留，importance < 5 合并为"日常摘要" |
| 7 天以前 | 仅保留 reflection 和 importance ≥ 7 的事件 |

合并日常摘要时调用一次 LLM：

```
Prompt：以下是 {agent_name} 在 {date_range} 的日常事件。请用 100 字以内的第一人称
摘要这段时间的整体情况，保留有意义的细节，丢弃重复的小事。

事件列表：
{events}
```

合并后原 memory 标记为 `archived=true`，不再被检索。

---

## 4. 角色与场所设计（占位结构）

### 4.1 设计原则

**世界观推迟到 Day 2 末或开发完成后才最终敲定**。但代码层面必须先跑起来。所以使用占位 ID + YAML 配置的方式，让世界观可热替换。

### 4.2 占位结构

`backend/data/personas/agent_01.yaml` 到 `agent_10.yaml`：

```yaml
# agent_01.yaml
id: agent_01
display_name: "[待定]"
age: [待定]
identity: "[待定]"
traits: ["[待定]", "[待定]", "[待定]"]
long_term_goal: "[待定]"
mid_term_goal: "[待定]"
short_term_needs: "[待定]"
backstory: |
  [待定]
speaking_style: "[待定]"
initial_location: location_a
initial_relationships:
  agent_02: "认识但不熟"
  agent_03: "[待定]"
unknown_facts: |
  [待定]
seed_event: |
  [待定，作为初始记忆注入]
```

`backend/data/locations.yaml`：

```yaml
locations:
  - id: location_a
    name: "[待定]"
    description: "[待定]"
    type: "private"  # private / social / public / commercial
  - id: location_b
    name: "[待定]"
    type: "social"
  # ...
```

### 4.3 当前候选世界观（Jesason 备选清单）

> 以下方向中任选一个填入 YAML 即可。架构不变。

**候选 A：僵尸病毒爆发（Jesason 当前倾向）**
- 设定：城市某区域出现传染源，政府试图封锁，居民求生
- 角色：感染者、政府官员、警察、抵抗者、科学家、平民
- 张力源：信任 / 猜疑 / 牺牲 / 救赎
- 风险：DeepSeek 内容审核可能对暴力/绝望描写有限制；Day 2 调试时如遇拒绝，软化为"行为失控症"

**候选 B：赛博朋克小型社区**（v0.1 原方案）
- 设定：202X 年城市边缘的混合居住区
- 角色：黑客、酒吧老板、医生、流浪诗人等
- 张力源：阶级 / 监视 / 反抗 / 友情

**候选 C：基于 Jesason 现有小说世界观**
- 《永夜之吻》吸血鬼世界
- 《异世界革命物语》异世界

**候选 D：完全原创**
- 等 Jesason 临场决定

### 4.4 什么时候敲定

**最晚 Day 2 上午**。原因：persona YAML 必须填好实际内容，否则 prompt 里大量 `[待定]` 会让 LLM 输出胡言乱语。

但**架构、代码、UI、美术（占位）都可以在世界观未定的状态下并行推进**。

---

## 5. 美术资产规格（直接使用图片，无需像素化）

### 5.1 文件格式与尺寸

- **统一格式**：PNG（带 alpha 通道）
- **角色 idle / walk 帧**：建议 128×192（人形比例 2:3，内容居中）
- **场所背景**：建议 1280×720 或 1920×1080
- **UI 元素**：根据用途，但避免大于 512×512
- **像素风可有可无**——只要风格统一即可。AI 直出的"像素感"图片可以直接用

### 5.2 强制命名规范（Claude Code 依赖此规范批量加载）

```
godot_client/assets/
├── characters/
│   ├── agent_01/
│   │   ├── idle.png
│   │   ├── walk_n.png
│   │   ├── walk_s.png
│   │   ├── walk_e.png
│   │   ├── walk_w.png
│   │   └── portrait.png        # 可选，对话框头像，方形 256×256
│   ├── agent_02/
│   └── ... (10-12 个)
├── locations/
│   ├── location_a/
│   │   ├── background.png
│   │   └── walkable_mask.png   # 可选，黑白图标记可走区
│   └── ...
├── ui/
│   ├── dialogue_bubble.png
│   ├── time_panel_bg.png
│   ├── agent_inspector_bg.png
│   └── icons/
│       ├── thinking.png
│       ├── speaking.png
│       └── ... (状态图标)
└── effects/
    ├── thinking_indicator.png
    └── speech_dots.png
```

### 5.3 最小必要资产清单（Day 1 之前必须备好）

| 类别 | 数量 | 备注 |
|------|------|------|
| 角色 idle | 5 个 | agent_01 ~ agent_05 |
| 角色 walk 4 方向 | 5 × 4 = 20 张 | |
| 场所背景 | 1 张 | location_a |
| UI 基础 | 3 张 | dialogue_bubble, time_panel_bg, thinking_indicator |
| **小计** | **29 张** | |

### 5.4 完整资产清单（Day 2 末完成）

| 类别 | 数量 | 备注 |
|------|------|------|
| 角色 idle | 10-12 个 | 补齐 |
| 角色 walk 4 方向 | 40-48 张 | |
| 角色 portrait（对话头像） | 10-12 张 | |
| 场所背景 | 3-4 张 | |
| 场所 walkable mask（可选） | 3-4 张 | 简化寻路用 |
| UI 完整 | ~10 张 | |
| 效果图 | 3-5 张 | |
| **合计** | **约 80-100 张** | |

### 5.5 推荐生成工作流

考虑到时间紧迫，**强烈建议先用 AI 直出生成所有占位图，Day 1 用占位图开发，Day 2 你再单独用更精细的方法替换关键资产**：

1. **快速占位**（30 分钟生成全套）：用 ChatGPT/Imagen/Flux 直接生成"像素风格"或"卡通风格"图片，不追求精修
2. **风格统一**（重要）：所有角色用同一个风格 prompt 模板。例：
   ```
   Pixel art character, 32-bit style, full body, facing [direction],
   simple background, 128x192 resolution,
   {character_description}
   ```
3. **背景简化**：场所背景可以先用单色块 + 几个家具贴图叠加，不必一次生成完整画面

### 5.6 Claude Code 如何加载这些图

完全标准 Godot 工作流，**没有任何特殊处理**。Claude Code 会写出类似：

```gdscript
# scripts/agents/AgentNode.gd
@export var agent_id: String

func _ready():
    var idle_path = "res://assets/characters/" + agent_id + "/idle.png"
    var idle_tex = load(idle_path) as Texture2D
    $Sprite2D.texture = idle_tex

    # 加载 4 方向行走帧
    for dir in ["n", "s", "e", "w"]:
        var walk_path = "res://assets/characters/" + agent_id + "/walk_" + dir + ".png"
        var walk_tex = load(walk_path) as Texture2D
        # 注册到 AnimationPlayer 或 SpriteFrames
```

只要你按命名规范放图，Claude Code 就能批量处理。

---

## 6. 两天紧急开发计划

### 6.1 总体策略

- **目标**：Phase 1A + 1B 部分（3-5 agent + 1-2 场所 + 核心 plan-action-memory + 简单对话）
- **延伸目标**（如果顺利）：扩展到 8-12 agent + 3-4 场所
- **充分利用 Claude Max 20×**：可以并行让多个 Claude Code 任务同时跑（前端、后端、persona 配置）
- **占位优先**：所有美术、世界观都先用占位，跑通逻辑再美化

### 6.2 Day 0（今晚或明早）：准备工作

预计 2-4 小时，可以分散：

1. 把 Claude Max 20× 账号弄好（等商家发货）
2. 注册 DeepSeek API key，充值 ¥100
3. 安装：Godot 4.x、Python 3.11+、VS Code（或你的偏好编辑器）、Aseprite（可选）
4. 用 ChatGPT/Imagen 生成 5 个角色 + 1 个场景的占位图（粗糙即可）
5. 把占位图按命名规范放好
6. 把这份 v0.2 文档过一遍，标记你不同意的点

### 6.3 Day 1：核心架构跑通

#### 上午（4 小时）

**Block A：项目骨架（30 分钟，Claude Code 一次性）**

任务包发给 Claude Code：
> 根据文档第 6 节 "Python 后端实现规格"和第 5 节"Godot 端实现规格"建立项目骨架。包括目录结构、空文件、基础配置（pyproject.toml、project.godot、.gitignore、.env.example）。不要写业务逻辑，只搭架子。

**Block B：DeepSeek 客户端 + 缓存验证（1 小时）**

任务：
> 实现 `backend/src/llm/deepseek.py`。要求：
> - OpenAI 兼容接口调用 DeepSeek V4-Pro
> - 内置 token 计数与累计成本统计
> - 关键：验证缓存命中率。写一个测试，连续 5 次发同样的 5K-token prompt，检查 `prompt_cache_hit_tokens` 字段，命中率必须 ≥ 90%。

如果这一步缓存命中率达不到 90%，说明我们对 DeepSeek 缓存机制理解有误，**必须先解决再继续**——这是整个成本模型的基础。

**Block C：核心数据结构 + SQLite schema（1 小时）**

任务：
> 实现 SQLite schema（按文档第 6.2 节，但移除 embedding 字段）。实现 ORM 层。实现 Memory CRUD + 关键词查询。

**Block D：Action Queue 调度器（1.5 小时）**

任务：
> 实现 `backend/src/agent/scheduler.py`，按文档第 1.3 节的伪代码。重点：
> - asyncio 调度
> - 队列水位机制
> - 紧急打断
> - fallback 处理

#### 下午（4 小时）

**Block E：Planning（粗 + 细两层）（1.5 小时）**

任务：
> 实现 `backend/src/agent/planning.py`：
> - 粗粒度日程：每天清晨生成（5-7 条主要活动）
> - 细粒度展开：被 Action Queue 触发时调用，把"在酒吧吃早餐"展开成 5-10 个具体动作

**Block F：Memory 写入 + 重要性打分（1 小时）**

任务：
> 实现观察事件写入流程。重要性打分用 batch 模式：每 5 条 memory 凑一批一次性给 LLM 打分。

**Block G：FastAPI 路由 + WebSocket（1.5 小时）**

任务：
> 实现 `backend/src/api/routes.py` 和 `websocket.py`。按文档第 6.3 节的端点列表。

#### 晚上（3-4 小时）

**Block H：Godot 客户端（4 小时，可与后端 Block 并行）**

任务：
> 实现 Godot 客户端：
> 1. GameClock（游戏时间系统）
> 2. BackendClient（HTTP + WebSocket）
> 3. Main 场景：加载 location_a 背景图
> 4. AgentNode：加载 agent_01 的精灵图，按后端推送的 action 移动
> 5. 简单 UI：左上角时间面板

**Day 1 验收**：单个 agent 在屏幕上按 LLM 生成的日程自主活动，行为流畅，玩家能看到时间流逝。

### 6.4 Day 2：扩展与对话

#### 上午（4 小时）

**Block I：扩展到 5 agent（1 小时）**

任务：
> 复制 agent_01 配置 → agent_02..05。调度器扩展为多 agent 并发。验证多个 agent 在同一场所互不干扰。

**Block J：Perception 系统（1 小时）**

任务：
> 实现同场所事件传播：当 agent A 在场所 L 做了动作 D，所有同时在 L 的其他 agent 都生成一条 observation。

**Block K：对话状态机（2 小时）**

任务：
> 实现对话流程：发起 → 接受 → 多轮交互 → 结束 → 写入双方 memory。每句台词由 LLM 生成。Godot 端实现对话气泡 UI。

#### 下午（4 小时）

**Block L：世界观敲定 + persona 填充（1 小时）**

**Jesason 必须在此时拍板世界观**。把 10 份 YAML 填好。

**Block M：美术资产替换（1.5 小时）**

把占位图替换为正式资产。

**Block N：Reflection 简版（1.5 小时）**

任务：
> 实现 reflection 三步流程，但每天结束触发（不是 importance 累积阈值）。简化版即可。

#### 晚上（3-4 小时）

**Block O：调试 + 参数调优（2 小时）**

观察 agent 行为日志，调对话长度、重要性阈值、思考触发阈值等参数。

**Block P：通宵测试（剩余时间）**

让游戏跑 1-2 个游戏日，记录所有事件。第二天起来分析有没有涌现行为。

### 6.5 Day 3（可选）

**如果 Day 2 末状态良好**：扩展到 8-12 agent + 3-4 场所，达到 v0.1 的完整 MVP。

**如果 Day 2 末有 bug**：第三天专门修 bug、抛光体验、补完 UI。

---

## 7. 风险与应对（更新版）

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| Day 1 缓存命中率不达标 | 中 | 高 | Block B 是 hard gate，不达标必须先解决；可降级到 V4-Flash |
| Action Queue 调度有 bug | 中 | 高 | 写单元测试覆盖核心场景；asyncio 调试器 |
| LLM 输出 JSON 格式错误 | 高 | 中 | 严格 schema 校验 + 重试 + fallback 到默认动作 |
| Agent 行为陷入循环 | 高 | 中 | 无聊检测：连续 N 次相同 action 强制 replan |
| 世界观相关的内容审核拦截 | 中 | 中 | Day 2 上午测试敏感词；准备替代世界观 |
| 美术资产风格不统一 | 高 | 中 | 占位优先，正式资产用同一 prompt 模板生成 |
| 两天工时严重超支 | 高 | 高 | 砍 Phase 1B（对话）保 Phase 1A；接受"3 agent demo"作为兜底 |
| Claude Max 账号未及时到货 | 中 | 高 | 用现有账号开始 Day 0 准备；正式开发等账号到位 |

---

## 8. Claude Code 任务包模板

每次给 Claude Code 派发任务时，按这个格式：

```
=== 任务上下文 ===
项目：Block-7 生成式智能体社会模拟器
当前阶段：Day X, Block Y
前置任务：[列出已完成的 block]
本任务依赖：[列出依赖的其他模块]

=== 任务目标 ===
[一句话目标]

=== 详细规格 ===
参考文档：v0.2 文档第 X 节
具体要求：
1. ...
2. ...
3. ...

=== 验收标准 ===
- [可测试的检查点]
- [可观察的行为]

=== 注意事项 ===
- 不要使用 embedding 或向量检索
- 严格遵守命名规范（见文档第 5.2 节）
- 所有 prompt 必须遵循 4 层缓存结构（见文档第 2.2 节）
```

---

## 9. Jesason 待确认事项（v0.2 版）

请在 Day 0（今晚）前确认：

1. **架构层面**：是否同意"快动作慢思考 + Action Queue"作为核心架构？
2. **检索层面**：是否同意完全不用 embedding，只用关键词粗筛 + LLM in-context recall？
3. **模型层面**：是否使用 V4-Pro 作为主模型？背景 agent 是否使用 V4-Flash 降本？
4. **世界观层面**：是否接受占位 + Day 2 上午敲定？倾向哪个候选（A 僵尸 / B 赛博朋克 / C 你的小说 / D 现场决定）？
5. **资产层面**：是否同意 Day 0 用 AI 直出生成占位图，Day 2 再美化？
6. **节奏层面**：是否同意目标定为 Phase 1A+1B 部分（3-5 agent），冲刺扩展到完整 MVP（8-12 agent）？

回复后我们立刻进入 Day 0 准备阶段。

---

## 附录：关键引用

DeepSeek V4 系列于 2026-04-24 发布，V4-Pro 总参数 1.6T、激活参数 49B、原生 1M tokens 上下文；V4-Pro 在 SWE-bench Verified 等 Agent 评测中达到开源最佳水平。V4-Pro 缓存命中输入限时 0.025 元/M tokens（折后 2.5 折）。详见 https://api-docs.deepseek.com/

---

## 文档变更记录

| 版本 | 日期 | 主要变更 |
|------|------|---------|
| v0.1 | 2026-05-01 | 初稿 |
| v0.2 | 2026-05-01 | 引入快动作慢思考、缓存最大化、无向量检索、两天紧急开发 |
