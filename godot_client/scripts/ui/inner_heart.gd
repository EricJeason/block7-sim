extends Control

# preload 保证不依赖 .godot/global_script_class_cache.cfg
const ChromeTheme := preload("res://scripts/ui/chrome_theme.gd")
const KeyCapScene := preload("res://scenes/ui/KeyCap.tscn")

## F4.2 F 读自己的心 — 全屏笔记本双页 modal。
## 设计稿对照 docs/design/a/project/modals.jsx InnerHeart 第 167-263 行:
## - 78% 黑遮罩 + 760×540 笔记本(左页 380 + 装订 8 + 右页 380)
## - 左页:玩家自己的想法(Ma Shan Zheng 22px 100% 墨色)
## - 装订线 8px 深咖渐变阴影
## - 右页:"另一种声音" / 反思 / 随笔(20px 62%墨色 italic)
## - 反思来源:backend GET /agent/{player_id}/memories?type=reflection&limit=10

signal closed

var _reflections: Array = []
var _player_name: String = ""


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	anchor_right = 1.0
	anchor_bottom = 1.0
	_build_ui()


func setup(player_name: String, reflections: Array) -> void:
	_player_name = player_name
	_reflections = reflections
	if is_inside_tree():
		_rebuild_pages()


func _build_ui() -> void:
	# 1. 全屏 78% 黑遮罩
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

	# 2. 笔记本容器(居中,760×540)
	var notebook := HBoxContainer.new()
	notebook.add_theme_constant_override("separation", 0)
	notebook.anchor_left = 0.5
	notebook.anchor_top = 0.5
	notebook.anchor_right = 0.5
	notebook.anchor_bottom = 0.5
	notebook.offset_left = -384
	notebook.offset_top = -270
	notebook.offset_right = 384
	notebook.offset_bottom = 270
	notebook.name = "Notebook"
	add_child(notebook)

	# 3. 左页
	var left := PanelContainer.new()
	left.add_theme_stylebox_override("panel", ChromeTheme.make_parchment())
	left.custom_minimum_size = Vector2(380, 540)
	left.name = "LeftPage"
	notebook.add_child(left)

	# 4. 装订线
	var binding := ColorRect.new()
	binding.color = Color(0.118, 0.078, 0.039, 0.7)
	binding.custom_minimum_size = Vector2(8, 540)
	notebook.add_child(binding)

	# 5. 右页
	var right := PanelContainer.new()
	right.add_theme_stylebox_override("panel", ChromeTheme.make_parchment())
	right.custom_minimum_size = Vector2(380, 540)
	right.name = "RightPage"
	notebook.add_child(right)

	_rebuild_pages()


func _rebuild_pages() -> void:
	var left: PanelContainer = get_node_or_null("Notebook/LeftPage") as PanelContainer
	var right: PanelContainer = get_node_or_null("Notebook/RightPage") as PanelContainer
	if left == null or right == null:
		return
	for c in left.get_children():
		c.queue_free()
	for c in right.get_children():
		c.queue_free()

	_build_left_page(left)
	_build_right_page(right)


func _build_left_page(parent: PanelContainer) -> void:
	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 12)
	parent.add_child(vbox)

	# 顶部标识
	var tag := _make_label("左页 · 你自己的想法", ChromeTheme.font_serif(400), 13, ChromeTheme.COLOR_OAK_INK)
	vbox.add_child(tag)

	# 玩家名字(大字 26px)
	var name_label := _make_label(_player_name, ChromeTheme.font_serif(600), 26, ChromeTheme.COLOR_DEEP_INK)
	vbox.add_child(name_label)

	# ink rule
	_add_ink_rule(vbox)

	# 反思 entries(前 2 条 100% 墨色,Ma Shan Zheng 22px)
	var first_reflections: Array = _reflections.slice(0, 2)
	if first_reflections.is_empty():
		var empty := _make_label(
			"……还没积累足够的反思。\n继续走走看看,跨过一天,夜里也许会留下些什么。",
			ChromeTheme.font_handwriting(), 18,
			Color(0.239, 0.184, 0.122, 0.5)
		)
		empty.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		vbox.add_child(empty)
	else:
		for r in first_reflections:
			var text: String = str(r.get("content", ""))
			var label := _make_label(text, ChromeTheme.font_handwriting(), 22, ChromeTheme.COLOR_DEEP_INK)
			label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			vbox.add_child(label)

	# 底部页码
	var spacer := Control.new()
	spacer.size_flags_vertical = Control.SIZE_EXPAND_FILL
	vbox.add_child(spacer)

	var page_num := _make_label(
		"·  今日  ·  1 / 2  ·",
		ChromeTheme.font_mono(400), 10, ChromeTheme.COLOR_OAK_INK
	)
	page_num.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	vbox.add_child(page_num)


func _build_right_page(parent: PanelContainer) -> void:
	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 12)
	parent.add_child(vbox)

	# 顶部标识(右对齐)
	var tag := _make_label("右页 · 另一种声音 · 反思 · 随笔",
		ChromeTheme.font_serif(400), 13, ChromeTheme.COLOR_OAK_INK)
	tag.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	vbox.add_child(tag)

	_add_ink_rule(vbox)

	# 反思 entries(从第 3 条开始,Caveat italic 20px 62% 墨色)
	var later_reflections: Array = _reflections.slice(2, 6)
	if later_reflections.is_empty() and _reflections.size() < 3:
		var hint := _make_label(
			"·"  ,
			ChromeTheme.font_handwriting(), 22,
			Color(0.239, 0.184, 0.122, 0.3)
		)
		hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		vbox.add_child(hint)
	else:
		for r in later_reflections:
			var text: String = str(r.get("content", ""))
			var color := ChromeTheme.COLOR_DEEP_INK
			color.a = 0.62
			var label := _make_label(text, ChromeTheme.font_handwriting(), 20, color)
			label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			vbox.add_child(label)

	# expand
	var spacer := Control.new()
	spacer.size_flags_vertical = Control.SIZE_EXPAND_FILL
	vbox.add_child(spacer)

	# 字体变化预留备注
	var dashed_rule := PanelContainer.new()
	var dashed_sb := StyleBoxFlat.new()
	dashed_sb.bg_color = Color(0.420, 0.345, 0.251, 0.3)
	dashed_rule.add_theme_stylebox_override("panel", dashed_sb)
	dashed_rule.custom_minimum_size = Vector2(0, 1)
	vbox.add_child(dashed_rule)

	var note := _make_label(
		"字体变化预留 · 剧本可注入「导演低语 / 母亲遗笔 / 沉睡的记忆」",
		ChromeTheme.font_serif(400), 11,
		Color(ChromeTheme.COLOR_OAK_INK.r, ChromeTheme.COLOR_OAK_INK.g, ChromeTheme.COLOR_OAK_INK.b, 0.55)
	)
	note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	vbox.add_child(note)

	# 底右 "F 合上"
	var close_row := HBoxContainer.new()
	close_row.alignment = BoxContainer.ALIGNMENT_END
	close_row.add_theme_constant_override("separation", 6)
	vbox.add_child(close_row)

	var cap = KeyCapScene.instantiate()
	cap.text = "F"
	cap.dim = true
	close_row.add_child(cap)

	var close_hint := _make_label("合上", ChromeTheme.font_mono(400), 10, ChromeTheme.COLOR_OAK_INK)
	close_hint.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	close_row.add_child(close_hint)


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
	if event.keycode == KEY_F or event.keycode == KEY_ESCAPE:
		get_viewport().set_input_as_handled()
		_on_close()


func _on_close() -> void:
	closed.emit()
	queue_free()
