# Block-7 UI 重做 · 对拼图(Gap Analysis)

> **目的**:把 Claude Design 产出的 `Block7 UI.html` 设计稿,与当前 Godot 端实装,做**逐元素对照**。让 Eric 在动手前一眼看清:**设计稿要什么 / 现在有什么 / 差什么 / 改起来多大**。
> **作者**:Claude Code(接手 session,2026-05-17)
> **设计稿位置**:`docs/design/a/` (从 `Block7 UI.html` 入口起,10 个 jsx + 6 字体 + 2 份 brief)
> **本文档不是 brief,不是任务派单。是给 Eric 拍板用的对拼图。**

---

## 0. TL;DR(30 秒读)

- **设计稿不是面板美化,是架构级 UI 重做**:推翻当前 7 个 panel + 4×3 网格 + 数字键流程,转为 WASD 扮演 + 锚点站位 + 极简 HUD + 11 个按需 modal。
- **总工时**:UI 重做 v0.2-v0.3 范围(走动可玩 + 4 modal) ≈ **5 天**;v0.4 LLM modal + RPG 容器 ≈ **5-8 天**(本次不算)。
- **现阶段决策**:Eric 已拍 — 像素场景资产先不管,沿用现有 4 张 ChatGPT 大背景图。
- **下一步**:你 review 本文档,标记你愿意接受 / 想改的部分,然后我从 F0 字体+chrome 开始干。

---

## 1. 视觉规范速查(从 [Block7 UI.html](a/project/Block7%20UI.html) + [ui-elements.jsx](a/project/ui-elements.jsx) 提取,**已锁,不要 re-decide**)

### 1.1 配色

| 用途 | Hex | Godot 里怎么用 |
|---|---|---|
| UI 主底(羊皮纸暖底) | `#E8DCC4` ~ `#ECDDC1`~`#E3D3B3` 渐变 | `StyleBoxFlat.bg_color` + `Gradient` |
| UI 边框(旧橡木墨) | `#6B5840` | `StyleBoxFlat.border_color`,1px |
| 深咖墨(主要正文) | `#3D2F1F` | `Label.font_color` |
| 强调(封蜡红) | `#8B4513` | 关键按钮 / 选中行文字 |
| 冷紫(治愈者) | `#7A5A96` ~ `#C9B1D4`(梦境粒子) | 名牌 drop-shadow / dreamparticle Color |
| Modal 遮罩 | `rgba(26, 20, 16, 0.78)` | `ColorRect`,全屏 |
| 木板浅色 | `#D4B896` / `#D9BF94`-`#B6915F` 渐变 | WoodClock 主色 |
| 木板深边 | `#8B6F47` / `#6B5840` | WoodClock border |
| 钉头 | `#3A2418` | 4px 圆点 |

### 1.2 字体三组

| 用途 | 拉丁 | 中文 | Godot 加载位置 |
|---|---|---|---|
| UI 主文字、NPC 名、标题 | Cormorant Garamond | Noto Serif SC | `godot_client/assets/fonts/serif/` |
| 心声、反思、日记(S4) | Caveat | Ma Shan Zheng | `godot_client/assets/fonts/handwriting/` |
| 系统信息、时间、cost | IBM Plex Mono | Noto Sans SC | `godot_client/assets/fonts/mono/` |

**许可**:全部 SIL OFL 免费可用 ✅,从 Google Fonts 下载 .ttf 即可。

### 1.3 Chrome 4 件套(CSS class → Godot StyleBox)

| Class | 视觉 | Godot 落地 |
|---|---|---|
| `.parchment` | 羊皮纸 + 中央高光径向渐变 + 角落暗化径向 + 9/13/17px 圆点纸纹 + inset 墨边 + 投影 | `StyleBoxFlat` bg `#ECDDC1`→`#E3D3B3` linear + `border_width=1 border_color=#6B5840AA` + `corner_radius=5` + 1 张 `paper_grain.png` 9×9 平铺(可 `mix_blend_mode multiply` 或直接 `modulate`) |
| `.wood` | 重复线性渐变(1px 暗线 + 5px 间隔 + 17px 间隔)+ inset 顶亮 + 底深 + 1px 墨边 | `StyleBoxTexture` 9-slice 的 `wood_plank.png`,或 `StyleBoxFlat` + `shader` |
| `.ink-rule` | 横向墨线分隔,两端淡出 | `TextureRect` 用 1×1 渐变 PNG,或 `HSeparator` 改 style |
| `.wax` | 封蜡红径向渐变 | `StyleBoxFlat` 圆形 + `bg_color #8B4513` + `corner_radius_all_corners=999` |

### 1.4 关键动画

| 动画 | 用途 | 时长 | Godot 落地 |
|---|---|---|---|
| `selpulse` | 选中 NPC 脉冲光晕 | 1.4s 循环 | `Tween` modulate alpha + scale |
| `dreamdrift` | 治愈者夜间梦境粒子 | 3.4s 循环 | `CPUParticles2D`,2px 紫,上飘 26px,fade in/out |
| `modalfade` | Modal 淡入 | 360ms | `Tween` modulate + position offset 8px |
| `inkbleed` | 反思条目浮现 | 480ms | `Tween` modulate + blur shader |

---

## 2. 逐元素对照(设计稿 × 现有 Godot × 改动)

### 2.1 HUD chrome(8 个元素)

| # | 设计稿元素 | 设计稿源 | 当前 Godot 对应 | 改动 | 复杂度 | 工时 |
|---|---|---|---|---|---|---|
| H1 | **WoodClock**(顶部中央 240×52 木板时钟 + 4 时段图标 + 可选裂纹) | [ui-elements.jsx:81](a/project/ui-elements.jsx) | TimePanel(左上 290×90 黑底,显示 `Day 3, 15:52`) | **新建** WoodClock.gd / .tscn,旧 TimePanel **删除** | M | 4h |
| H2 | **LocationLabel**(左下,30px 中文 + 11px 英文 + N HERE,半透明叠在场景上) | [ui-elements.jsx:207](a/project/ui-elements.jsx) | NavLabel(顶部居中长字"[当前]老松广场 切换:[1]..[4]") | **新建** LocationLabel.gd,旧 NavLabel **删除**(场所切换走 exit + 1-4 debug) | S | 2h |
| H3 | **KeyHints**(右下,KeyCap 列阵 8 键:E/C/I/J/P/Q/F/Esc) | [ui-elements.jsx:224](a/project/ui-elements.jsx) | 无独立面板,提示散在 NavLabel | **新建** KeyHints.gd + KeyCap 子控件 | S | 2h |
| H4 | **PAUSED chip**(Tab 触发,顶部 60px 半透明黄底 mono 11px) | [main-screen.jsx:240](a/project/main-screen.jsx) | PausePanel(左下 280×80 大按钮 ▶/⏸) | **改造** — 删大按钮,只留 chip + 加 Tab 键监听 | S | 1h |
| H5 | **删除** Inspector(右上 270×360 当前 9 人列表) | — | [main.gd](../../godot_client/scripts/main.gd) 当前显示 9 人 | **删除**(转 Q 场所概览 modal) | S | 0.5h |
| H6 | **删除** MemoryPanel(右下 270×330,点 agent 弹) | — | 点 Inspector / sprite 时浮现 | **删除**(转 F 读自己心 + P 图鉴) | S | 0.5h |
| H7 | **删除** ReflectionPanel(左上 290×45 紫色"🌒 反思: N 条") | — | TimePanel 下方 | **删除**(转 F modal 内) | S | 0.5h |
| H8 | **LoadingOverlay** 改 parchment 风 + 暮谷镇剪影 | brief §2.4 | 现是纯黑半透明 + "⏳ 暮谷镇 · 加载中" | **改样式** — 换羊皮纸底 + 可选歪松剪影(后续) | S | 1h |

**HUD 小计**:**1.5 天**(F0 字体准备好后,这些是组装活)

### 2.2 场景 / Agent 层(7 个元素)

| # | 设计稿元素 | 设计稿源 | 当前 Godot 对应 | 改动 | 复杂度 | 工时 |
|---|---|---|---|---|---|---|
| W1 | **场景背景**(SVG 320×180 像素化) | [scenes.jsx](a/project/scenes.jsx) | 4 张 1254×1254 ChatGPT 大图 | **沿用现有**(Eric 已拍 ✅) | — | 0 |
| W2 | **锚点站位**(每场 6-7 个锚点,NPC 按 anchor 坐标放) | [data.jsx:26](a/project/data.jsx) LOCATIONS.anchors | AgentNode 在 4×3 grid 用 `_slot_position_for(sorted_index)` 算位 | **重构** — `backend/data/locations.yaml` 加 anchors[],GameWorld 提供 `get_anchor_position(scene_id, anchor_id)`,AgentNode 按 anchor_id 站位 | L | 6h(含后端) |
| W3 | **PlayerNode**(默认艾琳 + WASD + 头顶 YOU + 暖色 drop-shadow + facing 跟随移动) | [main-screen.jsx:179](a/project/main-screen.jsx) | 无玩家概念(只有 12 个 NPC) | **全新** — PlayerNode.gd + WASD 监听 + `(x,y)` 坐标 + 朝向 + 场景边界限制 + Sprite 选 agent_04 | L | 6h |
| W4 | **HoverWhisper**(距离 < 140px 时 NPC 头顶 "名 · action") | [ui-elements.jsx:181](a/project/ui-elements.jsx) | AgentNode 头顶 NameTag 常驻 + 脚下 action 常驻 | **重构** — NameTag 改 hover 触发(GameWorld 算距离),格式改为 "name · action",样式改 parchment | M | 4h |
| W5 | **E-prompt**(距离 < 110px 时 NPC 上方 [E] 互动) | [main-screen.jsx:196](a/project/main-screen.jsx) | 无 | **新建** — 复用 KeyCap 控件,挂 AgentNode 子节点 | S | 2h |
| W6 | **删除** 💭 思考灯泡 | brief 红线 | AgentNode 上方 💭 + Tween 闪烁 | **删除** — `_on_agent_thinking_started/_completed` signal 解绑 + 节点删除 | S | 0.5h |
| W7 | **z-sort by y**(后面的 NPC 被前面的遮挡) | [main-screen.jsx:135](a/project/main-screen.jsx) | 当前 sprite y 越大 z_index 越大?需要确认 | **检查 + 调整** | S | 1h |
| W8 | **治愈者紫晕 + 夜间梦境粒子**(治愈者:林秋 / 阿杏 / 白嬤) | [main-screen.jsx:164](a/project/main-screen.jsx) | 无 | **新建** — AgentNode 加可选 healer drop-shadow + CPUParticles2D | M | 3h |

**Agent 小计**:**3 天**

### 2.3 Modal 层(11 个,标识实装版本)

| # | Modal | 快捷键 | 设计稿源 | 版本 | 复杂度 | 工时 |
|---|---|---|---|---|---|---|
| M1 | **BubbleMenu**(E 互动) — 羊皮纸气泡 + 下指三角尾 + 3 选项("打招呼"/"读心 ×限 1"/"离开"),箭头键导航 | [ui-elements.jsx:120](a/project/ui-elements.jsx) | **v0.2** | M | 4h |
| M2 | **LocationCard**(Q 场所概览) — 半屏卡片,在场人数 / 出口 / 天气 / 日期 | [modals.jsx](a/project/modals.jsx)(待读) | **v0.3** | M | 4h |
| M3 | **SystemMenu**(Esc) — 侧栏滑入,设置 / 日志档案 / **剧本档案 (敬请期待)** / 退出 | modals.jsx | **v0.3** | M | 3h |
| M4 | **EventLog**(T 大事日志) — 侧栏滑入,时间线倒序 | modals.jsx | **v0.5** | M | 3h |
| M5 | **InnerHeart**(F 读自己心,S4) — 全屏笔记本双页,Caveat 手写 + Ma Shan Zheng,左右页字体差异 | modals.jsx | **v0.4**(需 LLM) | L | 8h |
| M6 | **RelationshipNetwork**(R,S5) — 全屏关系网图,12 节点 + 三态紫圈 + hover tooltip | modals.jsx | **v0.4** | L | 10h |
| M7 | **DialogueSession**(S11,E→打招呼) — 全屏对话 + portrait + 3 LLM 候选 + 自由输入框 + 读秒 | modals.jsx | **v0.4**(需 LLM) | L | 10h |
| M8 | **CharacterPanel**(C 角色面板) — 显性 stats + 半显症状 + 隐性 yaml 占位 + 装备 + 背包概要 | [rpg-modals.jsx](a/project/rpg-modals.jsx) | **v0.3** | L | 6h |
| M9 | **InventoryPanel**(I 背包) — 5×2 格子 + 容量 + 选中详情 + actions | rpg-modals.jsx | **v0.3** | L | 6h |
| M10 | **QuestBook**(J 任务/线索) — 双 tab(线索羊皮纸 / 任务待办) | rpg-modals.jsx | **v0.4** | L | 6h |
| M11 | **CodexPanel**(P 图鉴) — 12 人列表 + ●○○ 解锁度 + 字段渐进解锁 | rpg-modals.jsx | **v0.4** | L | 6h |

**Modal 小计**:**v0.2** ≈ 4h,**v0.3** ≈ 23h,**v0.4 + v0.5** ≈ 43h(下次再做)

### 2.4 后端要改(3 处)

| # | 改动 | 文件 | 复杂度 | 工时 |
|---|---|---|---|---|
| B1 | `locations.yaml` 加 `anchors: [{id, label, x, y}, ...]`(每场 6-7 个) | [backend/data/locations.yaml](../../backend/data/locations.yaml) | S | 1h(填数据) |
| B2 | Planner 把 action 映射到 anchor_id(目前只到 location_id) | [backend/src/agent/planning.py](../../backend/src/agent/planning.py) | M | 3h(改 prompt + parse) |
| B3 | `/sim/player/bind` 路由,玩家绑定到 agent_04,scheduler 跳过该 agent 的 LLM 规划 | [backend/src/api/routes.py](../../backend/src/api/routes.py) + [scheduler.py](../../backend/src/agent/scheduler.py) | M | 4h |
| B4 | `/agent/{id}/state` 返回 anchor_id(可选,前端可以从 action 推) | routes.py | S | 1h |

**后端小计**:**~1 天**(可并行 F2 阶段做)

---

## 3. 5 阶段实装路线(共 ~5 天 到 v0.3 收口)

### F0 · 字体 + chrome 基础(0.5 天)
- 下载 6 字体 .ttf,放 `godot_client/assets/fonts/{serif|handwriting|mono}/`
- 写 `ChromeTheme.gd`:导出 4 个 StyleBox 工厂方法(`make_parchment()` / `make_wood_plank()` / `make_ink_rule()` / `make_wax_seal()`)
- 写 `KeyCap.tscn`(可复用控件,后面 KeyHints / E-prompt 都用)
- **检查点**:Main.tscn 顶部贴一个测试 parchment Panel + 三组字体 demo,能看到正确的视觉

### F1 · 极简 HUD 替换(0.5 天)
- 新建 `WoodClock.tscn` + `LocationLabel.tscn` + `KeyHints.tscn`
- 删除 TimePanel / ReflectionPanel / NavLabel / Inspector / MemoryPanel / PausePanel
- 改造 Main.tscn:顶中央 + 左下 + 右下三件套
- 加 Tab 键 → PAUSED chip
- **检查点**:启动后只剩木板时钟 + 场所名 + 键位提示,4×3 网格还在但 HUD 已全新

### F2 · 玩家化 + 锚点站位(1.5 天)
- B1:`locations.yaml` 加 anchors(4 场 × 6-7 锚点)
- B3:`/sim/player/bind` + scheduler 跳过玩家
- 新建 `PlayerNode.gd` + WASD + facing + 边界限制(scene_id, x, y, facing)
- 改造 AgentNode:锚点站位 + z-sort by y + HoverWhisper(距离触发) + E-prompt(距离触发)
- 删除 💭 思考灯泡
- **检查点**:WASD 走动,走近 NPC 看到 hover whisper,更近看到 E 提示

### F3 · 模态 4 件 + exit 切场所(1 天)
- BubbleMenu(E):3 选项,"读心"v0.2 disabled,"打招呼"stub(玩家头顶冒 stub 气泡,无 LLM)
- LocationCard(Q):半屏卡片
- SystemMenu(Esc):侧栏
- exit zone 检测:走到边界 `trigger_zone` 自动切场所(需先在 locations.yaml 加 exits)
- 1-4 debug 传送保留
- **检查点**:v0.2 完整收口 — 走 + 切场 + 互动菜单

### F4 · 治愈者氛围 + 大魔潮(1.5 天)
- 治愈者紫晕(林秋/阿杏/白嬤)+ dreamparticle 粒子(atmosphere=night)
- LoomingOverlay / DuskOverlay / NightOverlay(三层多 blend)
- WoodClock 加 cracked 路径(atmosphere=looming 时显)
- LoadingOverlay 换 parchment 风
- **检查点**:视觉收尾,启动到走动全套设计稿氛围

**v0.3 RPG 容器**(C/I/J/P)再加 ~3 天,放下一阶段。
**v0.4 LLM modal**(F/R/S11)再加 ~4 天,需后端 LLM 接入。

---

## 4. 待你拍板的决策(7 条)

| # | 决策点 | 推荐 | 替代 |
|---|---|---|---|
| D1 | 字体 .ttf 放 git 还是 .gitattributes lfs? | git(每字体 ~150KB,6 字体不到 1MB) | lfs(过度工程) |
| D2 | chrome StyleBox 用 GDScript 工厂方法 还是 .tres 资源? | **工厂方法**(改一处全部更新) | .tres(visual 编辑友好但难批量改) |
| D3 | 玩家默认绑定哪个 agent? | **艾琳(agent_04)** — 设计稿默认 + 有完整 sprite | 选角屏(v0.4 才上,本次不做) |
| D4 | 锚点数据 source of truth 在哪? | **backend/data/locations.yaml**(已经是后端权威源) | godot_client(双份会漂) |
| D5 | 走到 exit 切场所的视觉过渡? | **淡黑 200ms**(简单可用) | 像 Stardew Valley 的卷帘(过度工程) |
| D6 | 现有 4 张 ChatGPT 大背景图保留 1:1 还是缩到 1280×720? | **缩到 1280×720**(贴合设计稿 canvas + 锚点坐标系) | 保留 1:1 让玩家滚动(过度工程) |
| D7 | F4 阶段的 LoadingOverlay 加歪松剪影,自己画 SVG 还是问你? | **我自己用 SVG path 画**(可商量替换) | 问你找美术 |

---

## 5. 我建议的下一步(等你 review 本文档)

1. **你 review §1-§4**,标记:
   - 哪些决策可以接受(✅)
   - 哪些要改(改成什么)
   - D1-D7 7 条选项,你想怎么选
2. **我开 F0**(字体 + chrome 基础,半天,无破坏性,完全可逆)
3. **F0 跑完给你看一眼 demo**(Main.tscn 加几个测试 Panel),你确认视觉对路再进 F1

---

## 附:关键代码引用

| 设计稿组件 | 源文件 | 关键行 |
|---|---|---|
| 入口 HTML + 6 字体 + CSS chrome | [Block7 UI.html](a/project/Block7%20UI.html) | 9-135 |
| 12 NPC + 4 场所 + 锚点数据 | [data.jsx](a/project/data.jsx) | 4-81 |
| S3 主屏逻辑(WASD + 距离 + Modal 路由) | [main-screen.jsx](a/project/main-screen.jsx) | 5-329 |
| WoodClock + BubbleMenu + HoverWhisper + LocationLabel + KeyHints + KeyCap | [ui-elements.jsx](a/project/ui-elements.jsx) | 81-294 |
| 14×22 SVG sprite | [pixel.jsx](a/project/pixel.jsx) | 12-198 |
| 4 场景 SVG + 3 atmosphere overlay | [scenes.jsx](a/project/scenes.jsx) | 27-407 |
| v2 完整 brief | [HANDOFF_TO_CLAUDE_DESIGN_v2.md](a/project/uploads/HANDOFF_TO_CLAUDE_DESIGN_v2.md) | 全文 |
| v2.1 增量 brief | [INCREMENT_FOR_CLAUDE_DESIGN_v2_1.md](a/project/uploads/INCREMENT_FOR_CLAUDE_DESIGN_v2_1.md) | 全文 |
| Eric 与 Claude Design 对话历史 | [chat1.md](a/chats/chat1.md) | 全文 |

---

## 附 B:实装记录(2026-05-17 自主推进)

Eric 出远门期间 Claude Code 自主完成 F0→F4 + v0.3 RPG 容器框架。

### 已完成 commits(按时间序)

| Commit | 阶段 | 内容 |
|---|---|---|
| `39bbcfc` | F0 | 视觉地基:字体 7 个 + ChromeTheme 6 StyleBox + KeyCap + 设计稿包 |
| `e487021` | F1 | 极简 HUD:WoodClock(顶部木板时钟)+ LocationLabel(左下场所标)+ KeyHints(右下键位列阵)+ PausedChip |
| `e26e5c2` | bug | 3 个 .ps1 加 UTF-8 BOM 修中文乱码 |
| `93781af` | F1 fix | LoadingOverlay 文字"点左下 ▶ 开始按钮"→"按 Tab 启动预热" |
| `6e26a2b` | F2A 后端 | locations.yaml 加 anchors + name_en + LocationLoader.extra() + /sim/player/bind + scheduler 跳过玩家 LLM(135 tests) |
| `6e68624` | F2B Godot | PlayerNode(WASD + 朝向 + 边界 + YOU 标签)+ LocationView 跳过玩家 + 锚点站位 + bind_player 自动调用 |
| `ea7b41b` | F2C+D | AgentNode HoverWhisper + E-prompt + BubbleMenu(E 3 选项)+ 删 💭 思考灯泡 |
| `c577724` | tooling | 一键启动脚本 `scripts/launch_all.ps1`(关旧进程 + 启 backend + 启 Godot) |
| `4c0722d` | F2 fix | 4 修复:删重复场所标 + 修朝向 + 边界自动切场所 + 全屏 F11 |
| `404e8f7` | F2 polish | 边界提示气泡 + 打招呼 stub 气泡对答 + BubbleMenu 键盘修复(_input + W/S/E/Enter/Space + 100ms grace) |
| `d2dea75` | F2 fix | 边界范围扩大 380→180(玩家视觉到屏幕边缘才触发) |
| `f01c44c` | F2 fix | 边界提示改 HUD 固定位置(玩家走顶部不再被顶出屏) |
| `b1ed7c8` | F3 | Q 场所概览(半屏羊皮纸卡片)+ Esc 系统菜单(右侧 sidebar 8 选项) |
| `01f3e12` | F3 polish | 对话气泡 1.5× 慢速(0.18s/字→0.27s/字)+ HoverWhisper 滞后区(140/240) |
| `030f6d9` | F4.1 后端+前端 | 打招呼接 LLM:DialogueManager.try_start_player_session + /dialogue/player_greet + BackendClient.player_greet(139 tests) |
| `47bb818` | F4.2 | F 读自己的心:全屏笔记本双页 modal(左玩家想法 Ma Shan Zheng 100% / 右"另一种声音" Caveat 62%)+ 拉 reflections |
| `1e2f68f` | F4.3 | R 关系网:12 节点圆形布局 + 治愈者三态紫圈(实线/虚线/无)+ 7 条 known links + 底部图例 |
| `a02a05d` | v0.3 RPG | C/I/J/P 共用 RpgPlaceholder modal + 数据 schema 预览 + 占位插图 + "敬请期待" |
| `5d869a0` | F4.4 轻量 | BubbleMenu 3 句具体打招呼让玩家自选(取代随机种子)→ 后端 LLM 据此生成 |
| `fc057d4` | docs | GAP 文档附 B 实装记录 |
| `8cb2a78` | F4.4 完整 | 全屏 DialogueSession modal:LineEdit 自由输入 + 持续对话 + WS 实时刷新 + 双方气泡 + 思考态;backend continue/end 路由 + auto_finalize 字段(143 tests) |

### 测试基线

- **后端 pytest**:122 → **143 全过**(+5 player binding + 4 player session + 4 continue/end + 8 其他)
- **Cache 命中率**:Layer 0/1 字节稳定保护,所有 LLM 调用走原 prompt 结构 ✓
- **Godot --headless cold-start**:所有 commit 后都验证通过(无 class_name cache 依赖)
- **真实 API**:F4.1 / F4.4 玩家发起对话使用 DeepSeek Flash,单句 ¥0.001-0.003

### 全部键位(v0.3 全解锁)

| 键 | 功能 | 状态 |
|---|---|---|
| WASD | 移动 | ✓ F2 |
| E | 走近 NPC 弹气泡菜单 → 选 3 句具体话发后端 LLM | ✓ F4.4 |
| C | 角色面板(placeholder) | ✓ v0.3 framework |
| I | 背包(placeholder) | ✓ v0.3 framework |
| J | 线索/任务(placeholder) | ✓ v0.3 framework |
| P | 图鉴(placeholder) | ✓ v0.3 framework |
| Q | 场所概览(半屏卡片) | ✓ F3 |
| F | 读自己的心(笔记本双页) | ✓ F4.2 |
| R | 关系网(12 节点 + 紫圈) | ✓ F4.3 |
| Esc | 系统菜单(右侧 sidebar) | ✓ F3 |
| Tab | 暂停/恢复 | ✓ F1 |
| F11 | 切全屏 ↔ Maximized | ✓ F2 |
| 1-4 | debug 传送场所 | ✓ 保留 |

### 已知遗留(给下一任 session 或 Eric 回来)

1. **F4.4 LLM 候选自动生成**:DialogueSession modal 当前是"自由输入"模式,设计稿 S11 还有"3 LLM 候选 + ✎ 复制编辑 + → 直接发送"功能(后端要新加 generate_player_options 路由让 LLM 替玩家生成 3 句候选)
2. **v0.3 RPG 容器 C/I/J/P 真实内容**:目前只是 placeholder + schema 预览,具体 stat bar / 物品 grid / 线索时间线 / 解锁度 留后续
3. **NPC 头顶常驻 action**:Eric 提过"日后用角色头顶显示工作内容",F4 没动,当前仍是 hover 距离触发
4. **场景像素化**:GAP §2.2 W1 选了保留现有 4 张 ChatGPT 大背景图,SVG 像素化版留以后
5. **anime-pixel sprite**:11 个 NPC 还是色块占位(只有艾琳有真实素材),v0.4+ 要美术补
6. **F4.3 关系网线索积分**:目前 suspicion / known_links 都 hard-code,v0.4+ 要 backend 驱动(玩家近距离观察 / 听说 / 直接对话累计)
7. **NPC portrait 资产**:DialogueSession 头部用 idle.png 兜底,11 个 NPC 还没真 portrait,设计稿要 256×256 anime-pixel bust shot

### 下次接手:从哪开始

**推荐先做**(高价值低风险):
- v0.3 C 角色面板真实数据(读玩家 persona + reflection 统计) — 4-6h
- F4.4 完整版 S11 全屏对话 modal — 8-12h(需要后端 LLM 候选生成)

**中等价值**:
- v0.3 P 图鉴接 codex 解锁系统(后端需 + agent 之间互动累计)
- F4.3 关系网 backend 驱动线索积分

**风险高的**(等大决策):
- 场景 SVG/TileMap 化(Block J,1.5-2 天)
- 11 个 NPC anime-pixel sprite(需美术或 AI 生成)
