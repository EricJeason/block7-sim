extends Control

# preload 保证不依赖 .godot/global_script_class_cache.cfg
const ChromeTheme := preload("res://scripts/ui/chrome_theme.gd")
const KeyCapScene := preload("res://scenes/ui/KeyCap.tscn")

## v0.3 RPG 容器 通用 placeholder modal (C/I/J/P 共用)。
##
## 设计稿对照 docs/design/a/project/rpg-modals.jsx:
## - 全屏 78% 黑遮罩 + 居中羊皮纸大卡(960×580)
## - 顶部:大标题 + 副标题 + ink rule
## - 中央:占位插画 + 简要说明 + 已规划的 RPG 容器 schema
## - 底部:"v0.4 解锁" tag + 关闭键提示
##
## F4 阶段先实装框架(键位 + modal 容器);具体内容 LLM 接入 / 数据驱动留 v0.4 后期。

signal closed

var _hotkey: String = "C"
var _title: String = "角色面板"
var _subtitle: String = "C · 你自己"
var _description: String = ""
var _schema_text: String = ""


func setup(hotkey: String, title: String, subtitle: String, description: String, schema_text: String) -> void:
	_hotkey = hotkey
	_title = title
	_subtitle = subtitle
	_description = description
	_schema_text = schema_text
	if is_inside_tree():
		_rebuild()


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	anchor_right = 1.0
	anchor_bottom = 1.0
	_build_ui()
	_rebuild()


func _build_ui() -> void:
	# 全屏遮罩
	var scrim := ColorRect.new()
	scrim.color = ChromeTheme.COLOR_MODAL_SCRIM
	scrim.anchor_right = 1.0
	scrim.anchor_bottom = 1.0
	scrim.mouse_filter = Control.MOUSE_FILTER_STOP
	scrim.gui_input.connect(func(e: InputEvent) -> void:
		if e is InputEventMouseButton and (e as InputEventMouseButton).pressed:
			_on_close()
	)
	add_child(scrim)

	# 居中羊皮纸大卡(960×580)
	var card := PanelContainer.new()
	card.add_theme_stylebox_override("panel", ChromeTheme.make_parchment())
	card.anchor_left = 0.5
	card.anchor_top = 0.5
	card.anchor_right = 0.5
	card.anchor_bottom = 0.5
	card.offset_left = -480
	card.offset_top = -290
	card.offset_right = 480
	card.offset_bottom = 290
	card.name = "Card"
	add_child(card)


func _rebuild() -> void:
	var card: PanelContainer = get_node_or_null("Card") as PanelContainer
	if card == null:
		return
	for c in card.get_children():
		c.queue_free()

	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 10)
	card.add_child(vbox)

	# 顶部 标题 + 副标题 + 右上关闭键
	var header := HBoxContainer.new()
	header.add_theme_constant_override("separation", 12)
	vbox.add_child(header)

	var title_col := VBoxContainer.new()
	title_col.add_theme_constant_override("separation", 2)
	title_col.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(title_col)

	title_col.add_child(_make_label(_title, ChromeTheme.font_serif(600), 26, ChromeTheme.COLOR_DEEP_INK))
	title_col.add_child(_make_label(_subtitle, ChromeTheme.font_mono(400), 10, ChromeTheme.COLOR_OAK_INK))

	# 右上 关闭键
	var close_row := HBoxContainer.new()
	close_row.add_theme_constant_override("separation", 6)
	close_row.alignment = BoxContainer.ALIGNMENT_END
	header.add_child(close_row)

	var cap = KeyCapScene.instantiate()
	cap.text = _hotkey
	cap.dim = true
	close_row.add_child(cap)

	close_row.add_child(_make_label("关闭", ChromeTheme.font_mono(400), 10, ChromeTheme.COLOR_OAK_INK))

	_add_ink_rule(vbox)

	# 中央:左右两栏(描述 + schema)
	var content_row := HBoxContainer.new()
	content_row.add_theme_constant_override("separation", 28)
	content_row.size_flags_vertical = Control.SIZE_EXPAND_FILL
	vbox.add_child(content_row)

	# 左栏:描述 + 占位插图
	var left_col := VBoxContainer.new()
	left_col.add_theme_constant_override("separation", 14)
	left_col.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	content_row.add_child(left_col)

	# 占位插图(简单 ColorRect 加纹理感)
	var illustration := PanelContainer.new()
	var ill_sb := StyleBoxFlat.new()
	ill_sb.bg_color = Color(0.420, 0.345, 0.251, 0.12)
	ill_sb.border_color = Color(ChromeTheme.COLOR_OAK_INK.r, ChromeTheme.COLOR_OAK_INK.g, ChromeTheme.COLOR_OAK_INK.b, 0.4)
	ill_sb.border_width_left = 1
	ill_sb.border_width_right = 1
	ill_sb.border_width_top = 1
	ill_sb.border_width_bottom = 1
	ill_sb.corner_radius_top_left = 3
	ill_sb.corner_radius_top_right = 3
	ill_sb.corner_radius_bottom_left = 3
	ill_sb.corner_radius_bottom_right = 3
	ill_sb.content_margin_left = 20
	ill_sb.content_margin_right = 20
	ill_sb.content_margin_top = 30
	ill_sb.content_margin_bottom = 30
	illustration.add_theme_stylebox_override("panel", ill_sb)
	illustration.custom_minimum_size = Vector2(0, 180)
	left_col.add_child(illustration)

	var ill_inner := VBoxContainer.new()
	ill_inner.alignment = BoxContainer.ALIGNMENT_CENTER
	ill_inner.add_theme_constant_override("separation", 8)
	illustration.add_child(ill_inner)

	# 大占位符号(用 mono 字体的中点)
	var symbol_label := _make_label("·  ·  ·", ChromeTheme.font_serif(400), 32, Color(0.420, 0.345, 0.251, 0.5))
	symbol_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	ill_inner.add_child(symbol_label)

	var coming_soon := _make_label("敬请期待  ·  COMING SOON",
		ChromeTheme.font_mono(600), 11,
		Color(ChromeTheme.COLOR_WAX_RED.r, ChromeTheme.COLOR_WAX_RED.g, ChromeTheme.COLOR_WAX_RED.b, 0.7))
	coming_soon.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	ill_inner.add_child(coming_soon)

	# 描述
	var desc_label := _make_label(_description,
		ChromeTheme.font_serif(400), 14, ChromeTheme.COLOR_DEEP_INK)
	desc_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	left_col.add_child(desc_label)

	# 右栏:schema 预览(剧本注入接口)
	var right_col := VBoxContainer.new()
	right_col.add_theme_constant_override("separation", 8)
	right_col.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	content_row.add_child(right_col)

	var schema_title := _make_label("SCHEMA · 剧本注入接口",
		ChromeTheme.font_mono(600), 10, ChromeTheme.COLOR_WAX_RED)
	right_col.add_child(schema_title)

	# schema text 在虚线方框里(类似设计稿的 hidden_attributes 框)
	var schema_panel := PanelContainer.new()
	var schema_sb := StyleBoxFlat.new()
	schema_sb.bg_color = Color(ChromeTheme.COLOR_OAK_INK.r, ChromeTheme.COLOR_OAK_INK.g, ChromeTheme.COLOR_OAK_INK.b, 0.05)
	schema_sb.border_color = Color(ChromeTheme.COLOR_OAK_INK.r, ChromeTheme.COLOR_OAK_INK.g, ChromeTheme.COLOR_OAK_INK.b, 0.5)
	schema_sb.border_width_left = 1
	schema_sb.border_width_right = 1
	schema_sb.border_width_top = 1
	schema_sb.border_width_bottom = 1
	schema_sb.content_margin_left = 12
	schema_sb.content_margin_right = 12
	schema_sb.content_margin_top = 10
	schema_sb.content_margin_bottom = 10
	schema_panel.add_theme_stylebox_override("panel", schema_sb)
	right_col.add_child(schema_panel)

	var schema_label := _make_label(_schema_text,
		ChromeTheme.font_mono(400), 11, ChromeTheme.COLOR_OAK_INK)
	schema_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	schema_panel.add_child(schema_label)

	# 底部 schema 说明
	var schema_note := _make_label(
		"框架本身是 design · 未来玩家剧本可往此容器注入字段",
		ChromeTheme.font_serif(400), 11,
		Color(ChromeTheme.COLOR_OAK_INK.r, ChromeTheme.COLOR_OAK_INK.g, ChromeTheme.COLOR_OAK_INK.b, 0.7))
	schema_note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	right_col.add_child(schema_note)


func _make_label(text: String, font: FontVariation, size: int, color: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_override("font", font)
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	return l


func _add_ink_rule(parent: Node) -> void:
	var rule := PanelContainer.new()
	rule.add_theme_stylebox_override("panel", ChromeTheme.make_ink_rule())
	rule.custom_minimum_size = Vector2(0, 1)
	parent.add_child(rule)


func _input(event: InputEvent) -> void:
	if not (event is InputEventKey) or not event.pressed or event.echo:
		return
	# 按对应 hotkey 或 Esc 关闭
	if event.keycode == KEY_ESCAPE:
		get_viewport().set_input_as_handled()
		_on_close()
		return
	# 匹配 hotkey(单字符 C/I/J/P)
	var key_str: String = _hotkey.to_upper()
	if key_str.length() == 1:
		var ch: int = key_str.unicode_at(0)
		if event.keycode == ch:
			get_viewport().set_input_as_handled()
			_on_close()


func _on_close() -> void:
	closed.emit()
	queue_free()
