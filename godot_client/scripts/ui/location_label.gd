class_name LocationLabel
extends VBoxContainer

# preload 保证不依赖 .godot/global_script_class_cache.cfg(被 .gitignore)
const ChromeTheme := preload("res://scripts/ui/chrome_theme.gd")

## 左下场所标 — 30px 中文 + 11px 英文大写 + N HERE。
## 设计稿 ui-elements.jsx LocationLabel()。
##
## 视觉:无背景(浮于场景上),文字带 textShadow(rgba(245,235,200,0.55) + 暖色发光)
## 锚点:左 32px,底 28px(由父节点 anchor 定位)

@export var location_name: String = "老松广场":
	set(value):
		location_name = value
		_refresh()

@export var location_name_en: String = "Old Pine Plaza":
	set(value):
		location_name_en = value
		_refresh()

@export var count: int = 0:
	set(value):
		count = value
		_refresh()

@onready var _cn_label: Label = $CnLabel
@onready var _en_label: Label = $EnLabel


func _ready() -> void:
	add_theme_constant_override("separation", 4)

	# 中文场所名:30px Cormorant Garamond + Noto Serif SC SemiBold,深咖墨 0.92 alpha
	_cn_label.add_theme_font_override("font", ChromeTheme.font_serif(600))
	_cn_label.add_theme_font_size_override("font_size", 30)
	var ink := ChromeTheme.COLOR_DEEP_INK
	ink.a = 0.92
	_cn_label.add_theme_color_override("font_color", ink)
	# 暖色文字阴影模拟 textShadow(StyleBoxFlat 加 1px 偏移 + 暖光)
	# Godot Label 没原生 textShadow,用 outline 模拟暖色光晕
	_cn_label.add_theme_color_override("font_outline_color", Color(0.96, 0.92, 0.78, 0.6))
	_cn_label.add_theme_constant_override("outline_size", 4)

	# 英文小标 + count:11px IBM Plex Mono + 字距宽 letter-spacing,大写
	_en_label.add_theme_font_override("font", ChromeTheme.font_mono(400))
	_en_label.add_theme_font_size_override("font_size", 11)
	var oak := ChromeTheme.COLOR_OAK_INK
	oak.a = 0.6
	_en_label.add_theme_color_override("font_color", oak)
	_en_label.add_theme_color_override("font_outline_color", Color(0.96, 0.92, 0.78, 0.5))
	_en_label.add_theme_constant_override("outline_size", 3)

	_refresh()


func _refresh() -> void:
	if _cn_label == null:
		return
	_cn_label.text = location_name
	# 11px mono uppercase + 字距宽 — Godot Label 没 letter-spacing,
	# 文本里手动加空格(每字符后 1 space)模拟,过度则字距太宽,这里只保留正常显示
	_en_label.text = "%s · %d HERE" % [location_name_en.to_upper(), count]
