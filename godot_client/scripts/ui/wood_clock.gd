class_name WoodClock
extends PanelContainer

# preload 保证不依赖 .godot/global_script_class_cache.cfg(被 .gitignore)
const ChromeTheme := preload("res://scripts/ui/chrome_theme.gd")
const ClockIconScript := preload("res://scripts/ui/clock_icon.gd")

## 顶部中央木板时钟(240×52),设计稿 ui-elements.jsx WoodClock()。
##
## 视觉:wood 木纹底 + 4 个钉头 + 18×18 时段图标 + "DAY 3 · 15:52" 21px Cormorant
## 挂法:固定 240×52,从屏幕顶端 -4px 嵌入感(由父节点定位)

@export var day: int = 1:
	set(value):
		day = value
		_refresh_label()

@export var hour: int = 0:
	set(value):
		hour = value
		_refresh_label()
		_refresh_icon()

@export var minute: int = 0:
	set(value):
		minute = value
		_refresh_label()

## 大魔潮临近时显示木板裂纹(F4 阶段加 cracked path 渲染)
@export var cracked: bool = false:
	set(value):
		cracked = value
		queue_redraw()

@onready var _icon: Control = $HBox/Icon  # 类型实际为 ClockIcon,但用基类避开 class_name cache 依赖
@onready var _label: Label = $HBox/Label


func _ready() -> void:
	# 木板 stylebox
	add_theme_stylebox_override("panel", ChromeTheme.make_wood_plank())
	custom_minimum_size = Vector2(240, 52)

	# 标签字体
	_label.add_theme_font_override("font", ChromeTheme.font_serif(600))
	_label.add_theme_font_size_override("font_size", 21)
	_label.add_theme_color_override("font_color", ChromeTheme.COLOR_DEEP_INK)
	_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER

	_refresh_label()
	_refresh_icon()


func _refresh_label() -> void:
	if _label == null:
		return
	_label.text = "DAY %d · %02d:%02d" % [day, hour, minute]


func _refresh_icon() -> void:
	if _icon == null:
		return
	_icon.phase = _phase_from_hour(hour)


func _phase_from_hour(h: int) -> String:
	if h >= 6 and h < 11:
		return "morning"
	if h >= 11 and h < 17:
		return "noon"
	if h >= 17 and h < 20:
		return "dusk"
	return "night"


# F4 阶段:在 _draw 里画木板裂纹 path (设计稿 ui-elements.jsx 105-110 行)
# func _draw() -> void:
#     if not cracked: return
#     ... draw SVG path "M 80 0 L 96 14 ..."
