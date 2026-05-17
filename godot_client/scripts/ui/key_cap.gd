class_name KeyCap
extends PanelContainer

# preload 保证不依赖 .godot/global_script_class_cache.cfg(被 .gitignore)
const ChromeTheme := preload("res://scripts/ui/chrome_theme.gd")

## 单个键位提示控件 — 设计稿里 BubbleMenu / KeyHints / E-prompt 复用的最小积木。
##
## 视觉:半透明羊皮纸底 + 1px 旧橡木墨边 + IBM Plex Mono 10px SemiBold 居中。
## 来自 docs/design/a/project/ui-elements.jsx KeyCap()。

## 显示文字(键名)。如 "E" / "WASD" / "Esc" / "Tab"。
@export var text: String = "E":
	set(value):
		text = value
		if is_inside_tree() and has_node("Label"):
			($Label as Label).text = value

## 灰显(用于不可用 / 占位的键位提示)
@export var dim: bool = false:
	set(value):
		dim = value
		modulate.a = 0.6 if value else 1.0


func _ready() -> void:
	# Stylebox(羊皮纸 0.85α + 墨边 0.55α + 圆角 3px)
	add_theme_stylebox_override("panel", ChromeTheme.make_keycap())

	# 字体 + 颜色
	var label: Label = $Label
	label.text = text
	label.add_theme_font_override("font", ChromeTheme.font_mono(600))
	label.add_theme_font_size_override("font_size", 10)
	label.add_theme_color_override("font_color", ChromeTheme.COLOR_DEEP_INK)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER

	# 最小宽度 18(让 1 字符的键如 "E" 不至于挤成方块)
	custom_minimum_size = Vector2(18, 0)
	mouse_filter = Control.MOUSE_FILTER_IGNORE

	if dim:
		modulate.a = 0.6
