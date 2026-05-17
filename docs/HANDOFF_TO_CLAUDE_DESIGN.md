# Block-7 暮谷镇 · 项目交接包

> **给谁看**:Eric 在 Claude.ai 网页端开新对话,讨论游戏设计 + 找 Claude Design 重做 UI 时,把这份文档**复制粘贴**到对话开头。
> **目标**:让一个零上下文的 AI 在 5 分钟内理解这个项目的全部关键信息,然后能产出有用的设计建议 / UI 稿。
> **更新时间**:2026-05-17

---

## 一句话项目定位

Stanford《Generative Agents》论文的中文复刻 + 创造性扩展。**12 个由 LLM 驱动的 NPC,在一个有限世界(暮谷镇)里自主活动、对话、互相感知、跨日反思,产生涌现叙事**。后端 Python + DeepSeek V4-Pro/Flash,前端 Godot 4。

**Eric 自我定位**:高三学生,非专职程序员,主理人 + 世界观作者。代码由 Claude Code(Claude Opus 4.7)和 Codex(GPT 5.5)协作完成。

**Day 1 MVP 已全部完成**——Sim 引擎闭环 + Godot 端实时显示 + 4 张场景背景 + 对话气泡 + 每日反思 + 成本控制。**真实 API 实测产出过千绫师徒、阿杏失眠 等论文级涌现剧情**。

---

## 暮谷镇世界观(简版)

**类型**:架空异世界 / 类近代奇幻 / 悬疑生活流 / 循环 horror

**核心设定**:暮谷镇坐落于一片异世界边境,寒带与热带交界处的小盆地。地脉异常涌现"魔物",一百多年前**拓境者协会**开放拓荒。村民来自四面八方——研究者、移民、退役军人、二代定居者。村子自给自足,有铁匠、医者、炼金术师、农民、捕魔队员、商人、酒馆主。

**核心张力**:"小魔潮"是常态,每次感染 1-3 个村民,村里能处理。但古老记载暗示每隔几十年会有一次"**大魔潮**"——能感染全村,触发"循环重置"。预言的日子正在临近。

**主题**:身份的连续性、记忆的可信度、"被治愈"是否真的意味着回到原来的自己。**被治愈过的村民被称为"治愈者",社会上不歧视他们,但他们之间有一种沉默的共识——某种"我们都做过那个梦"的微妙连结**,从不在公共场合提起。

**4 个场所**:
- `lao_song_plaza` 老松广场 — 中央枢纽,歪脖子老松树 + 酒馆 + 议事厅
- `north_frost_workshop` 北霜工坊 — 寒带,提炼霜髓矿,捕魔队驻地
- `warm_valley_farm` 暖谷农场 — 热带山谷,草药、温棚、文姐的故乡小树(开着不该开的花)
- `silent_tower_ruins` 寂塔遗迹 — 倒了一半的石塔,塔身刻字被烧掉,只有野兽小径通向

**12 个角色**(每个都有 22 字段富 schema persona):

| ID | 名字 | 职业 | 关键秘密(known_secrets / inner_conflict) |
|---|---|---|---|
| 01 | 林秋 | 村医 | 8 年前自己曾被感染过但已遗忘;最近反复梦见配药材 |
| 02 | 阿杏 | 林秋徒弟 | 已被感染 3 次,梦最近开始清晰化 |
| 03 | 早纪 | 协会驻村员 | 发现寂塔建造年份与协会档案差 17 年,在调查协会掩盖什么 |
| 04 | 艾琳 | 客居研究员 | **30 年前父亲在这里"殉职",她来调查真相,带着父亲笔记藏在地板下** |
| 05 | 沈砚 | 村长 | **30 年前亲历事件,知道艾琳父亲死因不是"殉职"** |
| 06 | 千绫 | 捕魔队长 | 暗恋林秋,不知林秋是治愈者 |
| 07 | 苏拂 | 酒馆老板 | 已数到 7 个做相似梦的客人;丈夫五年前"主动选择不被治愈" |
| 08 | 马九 | 跑商 | 发现西边小村已经空了(大魔潮可能已在邻区开始) |
| 09 | 田柱 | 铁匠 | 把刻名字的刀想送给沈砚 |
| 10 | 文姐 | 农场主 | 林秋的闺蜜,做着"奇怪的梦",故乡小树开了不该开的花 |
| 11 | 小璎 | 捕魔队员 | 千绫的徒弟,第一次面对大型实战 |
| 12 | 白嬤 | 村中老人 | 收落叶的陶罐快满了(几次循环都没出现过的时机) |

**完整 persona YAML**:`backend/data/personas/agent_01.yaml` ~ `agent_12.yaml`

---

## 技术架构(给设计师参考)

### 后端(Python + FastAPI + DeepSeek)

```
Planner 产 action → ActionScheduler 推进 → Action 完成 → Perception 写 observation
                                                              ↓
   talk_to 触发 DialogueSession → 多轮 LLM 生成对白 → 双方 memory
                                                              ↓
SimEngine 跨日检测 → 后台并行触发反思 + 压缩 → 5-10 条 reflection memory
                                                              ↓
                            SimEvent → WebSocket → Godot 客户端
```

**关键设计**:
- **快动作慢思考**:游戏循环永不阻塞 LLM,LLM 在后台 asyncio.Task 跑,完成后追加到队列
- **4 层 Prompt 缓存**:Layer 0(暮谷镇,~1280 tokens,所有 agent 共享)+ Layer 1(persona,~600 tokens,同 agent 跨调用稳定)+ Layer 2 + 3 每次变。命中率 92.9%
- **不引入向量检索**:Memory 召回只用 SQLite LIKE + 时间衰减 + LLM in-context recall
- **暂停按钮**:默认 paused 启动,Eric 点 ▶ 才烧 token(成本控制)

### Godot 客户端(已实装)

- **4 个独立 LocationScene**(.tscn)——每个场所一张 1254×1254 背景图 + agent 在 4×3 网格固定位置
- **AgentNode**:walk_n/s/e/w sprite(只有 agent_04 艾琳有真实素材,其它 11 个是色块) + 头顶名牌 + 💭 思考灯泡 + 白色对话气泡(动态时长 max(4, 字数×0.18) 秒)
- **HUD**:左上时钟 + 连接状态 + 反思计数器(紫色"🌒 反思: N 条 / Day X"),右上 Inspector(当前场所 agent 列表 + current_action),右下 MemoryPanel(点 agent 看最近 20 条记忆,反思紫色高亮),左下 暂停按钮 + 数字键 1/2/3/4 切场所,顶部导航提示
- **加载界面**:全屏黑色 + "⏳ 暮谷镇 · 加载中" + 进度

---

## 当前 UI 状态 + 痛点(重点!Claude Design 看这里)

### 视觉问题(已知,等设计稿)

1. **"整张地图就是一张贴图"** — 当前只是单一背景 + 12 个静态 sprite 固定 4×3 网格,**完全没有星露谷物语那种"游戏感"**。Eric 反复反馈这是最大痛点
2. **角色名牌 / Inspector / action 标签互相重叠**(尤其老松广场 9 人挤一个网格时)
3. **气泡(对话白底)和 thinking 灯泡(💭)视觉上区分不够**
4. **HUD 各 panel 半透明色块叠加场景上,缺乏统一视觉语言**——TimePanel / ReflectionPanel / Inspector / MemoryPanel / PausePanel / LoadingOverlay 都是 `Color(0.06, 0.08, 0.12, 0.72)` 半透明黑底,没有装饰边框或纹理
5. **艾琳的真实金发蓝裙像素 sprite vs 其它 11 个色块,违和感强**
6. **角色站位不会真的"走" — agent 在场所之间是瞬移**(scheduler.tick 中 location 切换,Godot 端 LocationView 立刻把 AgentNode 从旧场所卸载、在新场所创建)

### 真正的"星露谷化"需要(给设计师评估)

| 技术 | 当前 | 期望 |
|---|---|---|
| TileMap 分层 | 无,单张大背景 | 16×16/32×32 瓦片地砖,分层(地面/装饰/碰撞/前景) |
| Collision Shape | 无 | 墙、桌、炉子有物理形状,角色不能穿过 |
| AStarGrid2D 寻路 | 无,瞬移 | 角色真的按路径走,绕开障碍 |
| AnimatedSprite2D | 静态 walk_n/s/e/w 切换 | 8 帧 walk 循环 |
| Camera2D follow | 静态俯视 | 镜头跟角色 / 玩家自由滚动 |
| 可交互 Area2D | 无 | E 键互动,坐下、开门、拾起 |

**Eric 的态度**:愿意接受星露谷感的工程投入(单独 1.5-2 天 Block J),但希望先有清晰的 UI 设计稿。

### 给 Claude Design 的设计目标

请基于以下约束产出 UI 设计稿:

**视觉风格**:
- **像素风(32-bit)** + **悬疑、生活流、循环 horror** 氛围
- 主色调:暮黄 / 灰青 / 偏紫(治愈者梦境主题色) / 火焰橙(北霜工坊)
- 不要太"明亮可爱"——这个世界有一种宁静中暗伏的紧绷
- 参考:Stardew Valley(操作感)+ To the Moon(叙事氛围)+ Disco Elysium(信息密度)

**核心信息层级**(玩家需要快速看到的):
1. **时间 + 日**(暮谷镇时间感与节奏)
2. **正在发生什么**(对话、思考、动作 — 当前场景里 12 个 agent 的实时状态)
3. **agent 的内心活动**(memory / reflection — 点击 agent 看)
4. **玩家控制**(暂停 / 切场所 / 未来的"扮演 agent" / "注入事件")

**信息密度优先级**(高到低):
- 对话气泡 > 角色名 > 当前 action > 思考状态 > 时间 > 反思计数 > 成本

**UI 必备组件**:
- 4 个场所背景图(可保留现有 1254×1254 大图,或重新设计成 TileMap)
- 角色 sprite(12 个,统一像素风,32×48 或 64×96 比例)
- 时间/日 显示
- 对话气泡 / 字幕系统
- agent inspector(可看 memory / reflection / current_action)
- 暂停 / 速度控制
- 加载/预热界面

**UI 创新点(可选,Eric 期待惊喜)**:
- 治愈者的"梦境碎片"作为 UI 元素之一(比如夜晚屏幕边缘漂浮)
- 大魔潮临近的氛围反馈(屏幕逐渐变冷色,植物轻微变化)
- 反思条目可视化(不只是文字列表,可能是"心象笔记本")

**约束**:
- 分辨率 1280×720(可接受 1920×1080 高清版本)
- 必须在 Godot 4 里能实装(不要太复杂的特效)
- 不依赖任何 paid asset(用 free assets 或自己生成像素图)

---

## 资源清单(交付给设计师)

### 视觉资产
- `godot_client/assets/locations/{id}/background.png` × 4 张(1254×1254 ChatGPT 生成像素风场景图,已可用)
- `godot_client/assets/characters/agent_04/`:艾琳的 walk_n/s/e/w + idle + 5 张感染态变体立绘
- `godot_client/assets/characters/agent_01/`(及 02-03、05-12):**目前是空目录**,需要补全 11 个角色的 sprite

### 文字资产
- `backend/data/world.yaml`:暮谷镇全局设定
- `backend/data/locations.yaml`:4 个场所详细描述
- `backend/data/personas/agent_*.yaml`:12 个完整 persona(22 字段)
- `docs/worldview/暮谷镇_layer_0_原文.md`:LAYER_0 完整原文
- `docs/worldview/暮谷镇_催化剂.md`:大魔潮临近的 6 条触发信号
- `docs/worldview/暮谷镇_未决项.md`:17 项 Eric 还在拍板中的细节

---

## 给 Claude.ai 对话的 prompt 示例

> 你是一位资深独立游戏 UI/UX 设计师,擅长像素风 + 叙事性游戏的界面设计(参考 Stardew Valley / To the Moon / Disco Elysium)。我现在要做一个生成式智能体社会模拟器,代号 "Block-7 暮谷镇"。请阅读下面这份项目交接包,然后:
>
> 1. **评估当前 UI 设计的核心问题**(已列在"当前 UI 状态 + 痛点"节)
> 2. **给出整体视觉风格的方向建议**(主色调、UI 装饰元素、字体)
> 3. **重新设计 4 个核心面板**(TimePanel / Inspector / MemoryPanel / LoadingOverlay),给出 ASCII 框图或文字描述
> 4. **建议 1-2 个"惊喜创新点"**(用 worldview 的元素强化沉浸感)
> 5. **列出我需要补充提供的资产清单**(11 个角色 sprite 之外还需要什么)
>
> 完成后,我会把你的输出导入回 Claude Code 实装。
>
> [然后把整个 HANDOFF_TO_CLAUDE_DESIGN.md 粘贴过去]

---

## 你不必读的部分(给 Claude Code 接手用,这里只是索引)

- `docs/CLAUDE.md`——项目工作守则 + 红线
- `docs/工作展望.md`——接手指南 + 当前进度 + 剩余 Block 详规
- `docs/Day1_工作总结.md`——历史轨迹 + 踩坑 + 实测数据
- `docs/Project_Design_Document_v0_2.md`——架构总纲
- `docs/HANDOFF_FOR_NEXT_SESSION.md`——给下一个 Claude Code session 接手的说明
