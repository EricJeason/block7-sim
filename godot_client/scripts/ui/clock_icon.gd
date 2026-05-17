class_name ClockIcon
extends Control

## 18×18 像素时段图标 — morning / noon / dusk / night 四套。
## 来自 docs/design/a/project/ui-elements.jsx ClockIcon(),用 SVG rect 1:1 port 成 Godot draw_rect。

@export var phase: String = "noon":
	set(value):
		phase = value
		queue_redraw()


func _init() -> void:
	custom_minimum_size = Vector2(18, 18)
	mouse_filter = Control.MOUSE_FILTER_IGNORE


func _draw() -> void:
	var c := _color_for_phase()
	match phase:
		"morning": _draw_morning(c)
		"noon": _draw_noon(c)
		"dusk": _draw_dusk(c)
		"night": _draw_night(c)


func _color_for_phase() -> Color:
	match phase:
		"morning": return Color("#e8a04a")
		"noon": return Color("#f4c054")
		"dusk": return Color("#d8804a")
		"night": return Color("#e8e0c4")
		_: return Color.WHITE


func _r(x: float, y: float, w: float, h: float, c: Color) -> void:
	draw_rect(Rect2(x, y, w, h), c, true, -1.0)


func _draw_morning(c: Color) -> void:
	# 升起的太阳:小半圆 + 光芒 + 地平线
	_r(7, 6, 4, 4, c)
	_r(6, 7, 6, 2, c)
	_r(8, 2, 2, 2, c)
	_r(2, 8, 2, 2, c)
	_r(14, 8, 2, 2, c)
	var dim := c
	dim.a = 0.7
	_r(3, 3, 2, 2, dim)
	_r(13, 3, 2, 2, dim)
	# 地平线
	var horizon := Color("#6b5840")
	horizon.a = 0.6
	_r(0, 13, 18, 1, horizon)


func _draw_noon(c: Color) -> void:
	# 烈日:正圆 + 八方光芒
	_r(6, 6, 6, 6, c)
	_r(5, 7, 8, 4, c)
	_r(7, 5, 4, 8, c)
	_r(8, 1, 2, 2, c)
	_r(8, 15, 2, 2, c)
	_r(1, 8, 2, 2, c)
	_r(15, 8, 2, 2, c)
	_r(3, 3, 2, 2, c)
	_r(13, 3, 2, 2, c)
	_r(3, 13, 2, 2, c)
	_r(13, 13, 2, 2, c)


func _draw_dusk(c: Color) -> void:
	# 黄昏:太阳压向地平线
	_r(6, 8, 6, 4, c)
	_r(7, 6, 4, 4, c)
	var dim := c
	dim.a = 0.7
	_r(2, 9, 2, 2, dim)
	_r(14, 9, 2, 2, dim)
	var horizon := Color("#6b5840")
	_r(0, 12, 18, 1, horizon)
	var horizon2 := horizon
	horizon2.a = 0.5
	_r(0, 13, 18, 1, horizon2)


func _draw_night(c: Color) -> void:
	# 月亮:外圆 + 内空(背景挖空模拟新月)+ 星点
	_r(5, 4, 7, 10, c)
	_r(6, 3, 5, 1, c)
	_r(6, 14, 5, 1, c)
	# 内挖(用深咖墨模拟"被切走"的月相)
	_r(7, 5, 6, 8, Color("#3d2f1f"))
	# 远星
	var dim := c
	dim.a = 0.7
	_r(14, 3, 1, 1, dim)
	_r(2, 11, 1, 1, dim)
	dim.a = 0.5
	_r(15, 8, 1, 1, dim)
