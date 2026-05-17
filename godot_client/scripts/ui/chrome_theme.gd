class_name ChromeTheme
extends RefCounted

## 暮谷镇 UI 视觉规范工厂(羊皮纸 + 旧橡木墨 + 木板 + 封蜡红)。
##
## 来自 Claude Design 产出的 Block7 UI.html 设计稿,
## 已锁定的视觉规范见 docs/design/Block7_UI_GAP.md §1。
##
## 所有 StyleBox 通过这里的静态工厂方法构造,保证视觉一致 + 单点修改。
## 字体通过 FontVariation 包装,基础字体(拉丁)+ 中文 fallback。
##
## 用法示例:
##   var sb := ChromeTheme.make_parchment()
##   $MyPanel.add_theme_stylebox_override("panel", sb)
##   $MyLabel.add_theme_font_override("font", ChromeTheme.font_serif())
##   $MyLabel.add_theme_color_override("font_color", ChromeTheme.COLOR_DEEP_INK)

# ============================== 配色常量 ==============================
# 与 docs/design/a/project/Block7 UI.html .parchment / .wood / .wax CSS class 一一对应

## 羊皮纸暖底 — UI 主色,渐变高光端
const COLOR_PARCHMENT_HI := Color("#ECDDC1")
## 羊皮纸暖底 — 渐变阴影端
const COLOR_PARCHMENT_LO := Color("#E3D3B3")
## 旧橡木墨 — 边框、烧字、深色文字辅助
const COLOR_OAK_INK := Color("#6B5840")
## 深咖墨 — 主要正文
const COLOR_DEEP_INK := Color("#3D2F1F")
## 封蜡红 — 警示、关键按钮、选中行文字
const COLOR_WAX_RED := Color("#8B4513")
## 治愈者冷紫 — 名牌晕、关系网紫圈
const COLOR_HEALER_LILAC := Color("#7A5A96")
## 梦境碎片 — 治愈者夜间粒子色(更淡)
const COLOR_DREAM_PARTICLE := Color("#C9B1D4")
## Modal 全屏遮罩 — rgba(26, 20, 16, 0.78)
const COLOR_MODAL_SCRIM := Color(0.102, 0.078, 0.063, 0.78)
## 木板浅色(顶端) — wood class 渐变高光
const COLOR_WOOD_LIGHT := Color("#D9BF94")
## 木板深色(底端) — wood class 渐变阴影
const COLOR_WOOD_DARK := Color("#B6915F")
## 木板顶部 inset 高光 — 一行像素的强提亮
const COLOR_WOOD_TOP_INSET := Color("#E8D2A6")
## 木板底部 inset 阴影 — 一行像素的强暗化
const COLOR_WOOD_BOTTOM_INSET := Color("#8B6F47")
## 木板钉头深色
const COLOR_NAIL := Color("#3A2418")

# ============================== 字体资源 ==============================
# Variable font 通过 FontVariation 调权重;Regular 单 weight 直接用

const FONT_SERIF_LATIN := preload("res://assets/fonts/serif/CormorantGaramond-Variable.ttf")
const FONT_SERIF_CJK := preload("res://assets/fonts/serif/NotoSerifSC-Variable.ttf")
const FONT_HANDWRITING_LATIN := preload("res://assets/fonts/handwriting/Caveat-Variable.ttf")
const FONT_HANDWRITING_CJK := preload("res://assets/fonts/handwriting/MaShanZheng-Regular.ttf")
const FONT_MONO_LATIN := preload("res://assets/fonts/mono/IBMPlexMono-Regular.ttf")
const FONT_MONO_LATIN_SEMIBOLD := preload("res://assets/fonts/mono/IBMPlexMono-SemiBold.ttf")
const FONT_MONO_CJK := preload("res://assets/fonts/mono/NotoSansSC-Variable.ttf")

# ============================== 字体组装 ==============================
# 每个 font_xxx() 返回新的 FontVariation,可叠 weight。
# 中文 fallback 通过 FontVariation.fallbacks 设置。

## UI 主文字、NPC 名、标题(Cormorant Garamond + Noto Serif SC)
static func font_serif(weight: int = 400) -> FontVariation:
	var fv := FontVariation.new()
	fv.base_font = FONT_SERIF_LATIN
	fv.fallbacks = [FONT_SERIF_CJK]
	fv.variation_opentype = {&"wght": weight}
	return fv

## 心声、反思、日记(Caveat + Ma Shan Zheng)
static func font_handwriting(weight: int = 400) -> FontVariation:
	var fv := FontVariation.new()
	fv.base_font = FONT_HANDWRITING_LATIN
	fv.fallbacks = [FONT_HANDWRITING_CJK]
	fv.variation_opentype = {&"wght": weight}
	return fv

## 系统信息、时间、cost、debug(IBM Plex Mono + Noto Sans SC)
static func font_mono(weight: int = 400) -> FontVariation:
	var fv := FontVariation.new()
	if weight >= 500:
		fv.base_font = FONT_MONO_LATIN_SEMIBOLD
	else:
		fv.base_font = FONT_MONO_LATIN
	fv.fallbacks = [FONT_MONO_CJK]
	return fv

# ============================== StyleBox 工厂 ==============================

## 羊皮纸面板 — 暖底 + 1px 旧橡木墨边 + 圆角 5px + 暖投影。
## 对应 CSS .parchment(渐变背景 + inset 墨边 + 投影)。
## Godot StyleBoxFlat 不支持渐变,这里用 mid-tone 主色,
## paper-grain 纸纹层 F4 阶段叠 paper_grain.png 实现。
static func make_parchment() -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = COLOR_PARCHMENT_HI.lerp(COLOR_PARCHMENT_LO, 0.5)
	sb.border_width_left = 1
	sb.border_width_right = 1
	sb.border_width_top = 1
	sb.border_width_bottom = 1
	sb.border_color = Color(COLOR_OAK_INK.r, COLOR_OAK_INK.g, COLOR_OAK_INK.b, 0.5)
	sb.corner_radius_top_left = 5
	sb.corner_radius_top_right = 5
	sb.corner_radius_bottom_left = 5
	sb.corner_radius_bottom_right = 5
	sb.shadow_color = Color(0.157, 0.110, 0.063, 0.35)  # rgba(40,28,16,0.35)
	sb.shadow_size = 6
	sb.shadow_offset = Vector2(0, 6)
	sb.content_margin_left = 12
	sb.content_margin_right = 12
	sb.content_margin_top = 10
	sb.content_margin_bottom = 10
	return sb

## 半透明羊皮纸(用于浮在场景上的 HUD 小卡片 — location label / hover whisper / chip 等)。
## bg alpha 0.78,边框 alpha 0.45。
static func make_parchment_floating(alpha: float = 0.85) -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	var bg := COLOR_PARCHMENT_HI.lerp(COLOR_PARCHMENT_LO, 0.3)
	bg.a = alpha
	sb.bg_color = bg
	sb.border_width_left = 1
	sb.border_width_right = 1
	sb.border_width_top = 1
	sb.border_width_bottom = 1
	sb.border_color = Color(COLOR_OAK_INK.r, COLOR_OAK_INK.g, COLOR_OAK_INK.b, 0.45)
	sb.corner_radius_top_left = 2
	sb.corner_radius_top_right = 2
	sb.corner_radius_bottom_left = 2
	sb.corner_radius_bottom_right = 2
	sb.content_margin_left = 8
	sb.content_margin_right = 8
	sb.content_margin_top = 1
	sb.content_margin_bottom = 1
	return sb

## 木板时钟底 — 暖木色 + 顶亮 + 底深 + 1px 墨边 + 下圆角 6px(嵌入屏幕顶端)。
## 对应 CSS .wood(repeating linear gradient + inset 顶亮 + 底深 + 1px 墨边 + drop-shadow)。
static func make_wood_plank() -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = COLOR_WOOD_LIGHT.lerp(COLOR_WOOD_DARK, 0.5)
	sb.border_width_left = 1
	sb.border_width_right = 1
	sb.border_width_top = 2
	sb.border_width_bottom = 3
	sb.border_color = COLOR_OAK_INK
	sb.corner_radius_top_left = 0
	sb.corner_radius_top_right = 0
	sb.corner_radius_bottom_left = 6
	sb.corner_radius_bottom_right = 6
	sb.shadow_color = Color(0.078, 0.047, 0.016, 0.4)
	sb.shadow_size = 4
	sb.shadow_offset = Vector2(0, 4)
	sb.content_margin_left = 18
	sb.content_margin_right = 18
	sb.content_margin_top = 6
	sb.content_margin_bottom = 6
	return sb

## KeyCap 风格 — 小键位提示底:半透明羊皮纸 + 1px 墨边 + 圆角 3px。
## 用于 KeyCap.tscn / KeyHints 列阵 / E-prompt。
static func make_keycap() -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	var bg := COLOR_PARCHMENT_HI
	bg.a = 0.85
	sb.bg_color = bg
	sb.border_width_left = 1
	sb.border_width_right = 1
	sb.border_width_top = 1
	sb.border_width_bottom = 1
	sb.border_color = Color(COLOR_OAK_INK.r, COLOR_OAK_INK.g, COLOR_OAK_INK.b, 0.55)
	sb.corner_radius_top_left = 3
	sb.corner_radius_top_right = 3
	sb.corner_radius_bottom_left = 3
	sb.corner_radius_bottom_right = 3
	sb.content_margin_left = 5
	sb.content_margin_right = 5
	sb.content_margin_top = 1
	sb.content_margin_bottom = 1
	return sb

## 封蜡红圆点(用于强调点 / 选中标记 / 锚点标注等小装饰)。
static func make_wax_seal() -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = COLOR_WAX_RED
	sb.corner_radius_top_left = 999
	sb.corner_radius_top_right = 999
	sb.corner_radius_bottom_left = 999
	sb.corner_radius_bottom_right = 999
	return sb

## ink-rule 横向分隔线背景(配 HSeparator 用)。
## 注意:CSS .ink-rule 两端淡出由 linear-gradient 实现,
## StyleBoxFlat 不能渐变,这里只做实色版,渐变留 F4 用 texture/shader 实现。
static func make_ink_rule() -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(COLOR_OAK_INK.r, COLOR_OAK_INK.g, COLOR_OAK_INK.b, 0.55)
	return sb
