class_name PausedChip
extends PanelContainer

# preload 保证不依赖 .godot/global_script_class_cache.cfg(被 .gitignore)
const ChromeTheme := preload("res://scripts/ui/chrome_theme.gd")

## 顶部 PAUSED chip — Tab 触发暂停时显示,从 WoodClock 下方居中浮现。
## 设计稿 main-screen.jsx 239-247 行。
##
## 视觉:半透明羊皮纸 + 1px 墨边 + Plex Mono 11px "· PAUSED · TAB",字距 0.2em
## 锚点:顶 60px,水平居中

@onready var _label: Label = $Label


func _ready() -> void:
	add_theme_stylebox_override("panel", ChromeTheme.make_parchment_floating(0.9))

	_label.add_theme_font_override("font", ChromeTheme.font_mono(600))
	_label.add_theme_font_size_override("font_size", 11)
	_label.add_theme_color_override("font_color", ChromeTheme.COLOR_DEEP_INK)
	# 字距由文本内的空格手动撑
	_label.text = "·  P A U S E D  ·  T A B  ·"
	_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER

	visible = false
	mouse_filter = Control.MOUSE_FILTER_IGNORE
