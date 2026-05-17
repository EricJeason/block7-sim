extends Control

# preload 保证不依赖 .godot/global_script_class_cache.cfg
const ChromeTheme := preload("res://scripts/ui/chrome_theme.gd")

## F2 E 互动气泡菜单 — 玩家按 E 时在最近 NPC 头顶弹出。
##
## 视觉(对照 docs/design/a/project/ui-elements.jsx BubbleMenu 第 120-176 行):
## - NPC 名字标题(14px serif SemiBold 居中)
## - 羊皮纸面板 + 1px 旧橡木墨边 + 圆角 5px
## - 3 选项行(15px serif),选中行有封蜡红左三角箭头 + 0.10 alpha bg + 封蜡红文字
## - 选项可带 cost 标记(右侧 mono 10px 封蜡红)
## - 下指三角尾(SVG polygon → Godot 用 _draw 画三角)
##
## 控制:↑↓ 切选项,Enter / 鼠标点击确认,Esc 取消
## 弹出位置:由 main.gd 设置(NPC 头顶上方)
## 销毁:确认或取消后 queue_free,signal option_chosen(action_id) 通知外部

signal option_chosen(action_id: String)
signal cancelled

const OPTIONS: Array = [
	{"id": "greet",     "label": "打招呼"},
	{"id": "read_mind", "label": "读心", "cost": "× 限 1", "disabled": true},  # v0.4 解锁
	{"id": "leave",     "label": "离开"},
]

var npc_name: String = ""
var selected_index: int = 0

var _name_label: Label
var _panel: PanelContainer
var _options_vbox: VBoxContainer
var _option_rows: Array[HBoxContainer] = []


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP  # 拦截鼠标,防穿透到下方场景
	set_process_unhandled_input(true)
	_build_ui()
	_refresh_highlight()


func setup(target_npc_name: String) -> void:
	"""main.gd 实例化后调用,传入 NPC 名字。"""
	npc_name = target_npc_name
	if _name_label != null:
		_name_label.text = npc_name


func _build_ui() -> void:
	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 4)
	add_child(vbox)

	# NPC 名字标题(panel 上方)
	_name_label = Label.new()
	_name_label.text = npc_name
	_name_label.add_theme_font_override("font", ChromeTheme.font_serif(600))
	_name_label.add_theme_font_size_override("font_size", 14)
	_name_label.add_theme_color_override("font_color", ChromeTheme.COLOR_DEEP_INK)
	_name_label.add_theme_color_override("font_outline_color", Color(0.96, 0.92, 0.78, 0.7))
	_name_label.add_theme_constant_override("outline_size", 2)
	_name_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	vbox.add_child(_name_label)

	# 羊皮纸 panel
	_panel = PanelContainer.new()
	_panel.add_theme_stylebox_override("panel", ChromeTheme.make_parchment())
	_panel.custom_minimum_size = Vector2(140, 0)
	vbox.add_child(_panel)

	_options_vbox = VBoxContainer.new()
	_options_vbox.add_theme_constant_override("separation", 2)
	_panel.add_child(_options_vbox)

	# 3 选项行
	for i in range(OPTIONS.size()):
		var opt: Dictionary = OPTIONS[i]
		var row := _make_option_row(opt, i)
		_option_rows.append(row)
		_options_vbox.add_child(row)

	# 下指三角尾(用 Control + _draw,在 vbox 外面)
	var tail := _Tail.new()
	tail.custom_minimum_size = Vector2(20, 14)
	tail.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	vbox.add_child(tail)


func _make_option_row(opt: Dictionary, idx: int) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	row.mouse_filter = Control.MOUSE_FILTER_STOP
	row.gui_input.connect(func(e: InputEvent) -> void: _on_row_input(e, idx))

	# 左三角箭头(选中时显示,默认不可见占位)
	var arrow := Label.new()
	arrow.text = "▶"
	arrow.add_theme_font_override("font", ChromeTheme.font_serif(600))
	arrow.add_theme_font_size_override("font_size", 10)
	arrow.add_theme_color_override("font_color", ChromeTheme.COLOR_WAX_RED)
	arrow.custom_minimum_size = Vector2(14, 0)
	arrow.modulate.a = 0.0  # 默认隐藏
	arrow.name = "Arrow"
	row.add_child(arrow)

	var label := Label.new()
	label.text = opt.get("label", "")
	label.add_theme_font_override("font", ChromeTheme.font_serif(500))
	label.add_theme_font_size_override("font_size", 15)
	label.add_theme_color_override("font_color", ChromeTheme.COLOR_DEEP_INK)
	label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	label.name = "Label"
	row.add_child(label)

	# 可选 cost 标(右侧 mono 10px 封蜡红)
	var cost = opt.get("cost", "")
	if cost != "":
		var cost_label := Label.new()
		cost_label.text = cost
		cost_label.add_theme_font_override("font", ChromeTheme.font_mono(400))
		cost_label.add_theme_font_size_override("font_size", 10)
		cost_label.add_theme_color_override("font_color", ChromeTheme.COLOR_WAX_RED)
		row.add_child(cost_label)

	# disabled 选项:整行 alpha 0.55
	if opt.get("disabled", false):
		row.modulate.a = 0.55

	return row


func _refresh_highlight() -> void:
	for i in range(_option_rows.size()):
		var row: HBoxContainer = _option_rows[i]
		var arrow: Label = row.get_node("Arrow") as Label
		var label: Label = row.get_node("Label") as Label
		if i == selected_index:
			arrow.modulate.a = 1.0
			label.add_theme_color_override("font_color", ChromeTheme.COLOR_WAX_RED)
		else:
			arrow.modulate.a = 0.0
			label.add_theme_color_override("font_color", ChromeTheme.COLOR_DEEP_INK)


func _on_row_input(event: InputEvent, idx: int) -> void:
	if event is InputEventMouseButton:
		var mb := event as InputEventMouseButton
		if mb.pressed and mb.button_index == MOUSE_BUTTON_LEFT:
			selected_index = idx
			_refresh_highlight()
			_confirm()
	elif event is InputEventMouseMotion:
		if selected_index != idx:
			selected_index = idx
			_refresh_highlight()


func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventKey) or not event.pressed or event.echo:
		return
	var key = event.keycode
	if key == KEY_UP:
		get_viewport().set_input_as_handled()
		_move_selection(-1)
	elif key == KEY_DOWN:
		get_viewport().set_input_as_handled()
		_move_selection(1)
	elif key == KEY_ENTER:
		get_viewport().set_input_as_handled()
		_confirm()
	elif key == KEY_ESCAPE:
		get_viewport().set_input_as_handled()
		_cancel()


func _move_selection(delta: int) -> void:
	var new_idx: int = selected_index + delta
	# 跳过 disabled
	while new_idx >= 0 and new_idx < OPTIONS.size() and OPTIONS[new_idx].get("disabled", false):
		new_idx += delta
	if new_idx < 0 or new_idx >= OPTIONS.size():
		return
	selected_index = new_idx
	_refresh_highlight()


func _confirm() -> void:
	var opt: Dictionary = OPTIONS[selected_index]
	if opt.get("disabled", false):
		return  # 不响应
	var action_id: String = opt.get("id", "")
	option_chosen.emit(action_id)
	queue_free()


func _cancel() -> void:
	cancelled.emit()
	queue_free()


# 下指三角尾内联类
class _Tail extends Control:
	func _draw() -> void:
		var w: float = size.x
		var h: float = size.y
		# 填充(羊皮纸色)
		var fill_pts := PackedVector2Array([
			Vector2(0, 0), Vector2(w, 0), Vector2(w * 0.5, h)
		])
		draw_polygon(fill_pts, PackedColorArray([Color("#E3D3B3")]))
		# 描边(旧橡木墨)
		draw_line(Vector2(0, 0), Vector2(w * 0.5, h), Color("#6B5840"), 1.0)
		draw_line(Vector2(w * 0.5, h), Vector2(w, 0), Color("#6B5840"), 1.0)
