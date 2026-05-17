extends Control

# preload 保证不依赖 .godot/global_script_class_cache.cfg
const ChromeTheme := preload("res://scripts/ui/chrome_theme.gd")
const KeyCapScene := preload("res://scenes/ui/KeyCap.tscn")

## F3 Esc 系统菜单 sidebar — 右侧 316×viewport 滑入。
##
## 设计稿对照 docs/design/a/project/modals.jsx SystemMenu 第 90-164 行:
## - 右侧 sidebar 316px 宽,全高
## - 模糊半透明遮罩(scrim 0.45 alpha)
## - "暂停 · 安息片刻"标题 + "DAY N · HH:MM · PAUSED" 副标题
## - 8 选项列表:继续游戏(primary封蜡红边框) / 保存 / 读档 / 设置 /
##   剧本档案(灰显 + "敬请期待"tag) / 日志档案(T) / 地图(M) / 回主菜单
## - 底部固定:BLOCK-7 · MU GU ZHEN · v0.3

signal closed

# 选项定义(label / hint / primary / disabled / tag / id)
const ITEMS: Array = [
	{"id": "resume",   "label": "继续游戏", "hint": "Esc", "primary": true},
	{"id": "save",     "label": "保存进度", "hint": ""},
	{"id": "load",     "label": "读取存档", "hint": ""},
	{"id": "settings", "label": "设置",     "hint": ""},
	{"id": "scenario", "label": "剧本档案", "hint": "", "tag": "敬请期待", "disabled": true},
	{"id": "log",      "label": "日志档案", "hint": "T", "disabled": true},  # v0.5
	{"id": "map",      "label": "地图",     "hint": "M", "disabled": true},  # v0.3+
	{"id": "main_menu","label": "回到主菜单", "hint": "", "disabled": true},  # 无主菜单
]


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	# 全屏覆盖(scrim + sidebar)
	anchor_right = 1.0
	anchor_bottom = 1.0
	_build_ui()


func _build_ui() -> void:
	# 1. 半透明遮罩(scrim)
	var scrim := ColorRect.new()
	scrim.color = Color(0.102, 0.078, 0.063, 0.45)
	scrim.anchor_right = 1.0
	scrim.anchor_bottom = 1.0
	scrim.mouse_filter = Control.MOUSE_FILTER_STOP
	scrim.gui_input.connect(func(e: InputEvent) -> void:
		if e is InputEventMouseButton and (e as InputEventMouseButton).pressed:
			_on_close()
	)
	add_child(scrim)

	# 2. 右侧 sidebar(羊皮纸,316 宽全高)
	var sidebar := PanelContainer.new()
	sidebar.add_theme_stylebox_override("panel", ChromeTheme.make_parchment())
	sidebar.anchor_left = 1.0
	sidebar.anchor_top = 0.0
	sidebar.anchor_right = 1.0
	sidebar.anchor_bottom = 1.0
	sidebar.offset_left = -316.0
	sidebar.offset_right = 0.0
	sidebar.offset_top = 0.0
	sidebar.offset_bottom = 0.0
	sidebar.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(sidebar)

	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 6)
	sidebar.add_child(vbox)

	# 标题
	var title := _make_label("暂停 · 安息片刻", ChromeTheme.font_serif(600), 22, ChromeTheme.COLOR_DEEP_INK)
	vbox.add_child(title)

	# 副标题 "DAY N · HH:MM · PAUSED"
	var gt: float = GameWorld.game_time
	var day: int = int(gt / 86400.0) + 1
	var sec_today: float = fmod(gt, 86400.0)
	var hour: int = int(sec_today / 3600.0)
	var minute: int = int(fmod(sec_today, 3600.0) / 60.0)
	var pause_state: String = "PAUSED" if GameWorld.paused else "RUNNING"
	var subtitle := _make_label(
		"DAY %d · %02d:%02d · %s" % [day, hour, minute, pause_state],
		ChromeTheme.font_mono(400), 10, ChromeTheme.COLOR_OAK_INK
	)
	vbox.add_child(subtitle)

	# ink rule
	var rule := PanelContainer.new()
	rule.add_theme_stylebox_override("panel", ChromeTheme.make_ink_rule())
	rule.custom_minimum_size = Vector2(0, 1)
	rule.add_theme_constant_override("margin_top", 10)
	vbox.add_child(rule)

	# 间距
	var spacer := Control.new()
	spacer.custom_minimum_size = Vector2(0, 8)
	vbox.add_child(spacer)

	# 选项列表
	for it in ITEMS:
		vbox.add_child(_make_option_row(it))

	# 间距 expand
	var fill := Control.new()
	fill.size_flags_vertical = Control.SIZE_EXPAND_FILL
	vbox.add_child(fill)

	# 底部 ink-rule + 版本号
	var bottom_rule := PanelContainer.new()
	bottom_rule.add_theme_stylebox_override("panel", ChromeTheme.make_ink_rule())
	bottom_rule.custom_minimum_size = Vector2(0, 1)
	vbox.add_child(bottom_rule)

	var version := _make_label(
		"BLOCK-7 · MU GU ZHEN · v0.3",
		ChromeTheme.font_mono(400), 10, ChromeTheme.COLOR_OAK_INK
	)
	version.add_theme_color_override("font_color",
		Color(ChromeTheme.COLOR_OAK_INK.r, ChromeTheme.COLOR_OAK_INK.g, ChromeTheme.COLOR_OAK_INK.b, 0.7))
	vbox.add_child(version)


func _make_option_row(item: Dictionary) -> Control:
	var row := PanelContainer.new()
	var sb := StyleBoxFlat.new()
	if item.get("primary", false):
		sb.bg_color = Color(0.545, 0.271, 0.075, 0.10)  # 0.10 alpha 封蜡红底
		sb.border_color = Color(0.545, 0.271, 0.075, 0.45)
		sb.border_width_left = 1
		sb.border_width_right = 1
		sb.border_width_top = 1
		sb.border_width_bottom = 1
		sb.corner_radius_top_left = 3
		sb.corner_radius_top_right = 3
		sb.corner_radius_bottom_left = 3
		sb.corner_radius_bottom_right = 3
	else:
		sb.bg_color = Color(0, 0, 0, 0)  # 透明
	sb.content_margin_left = 12
	sb.content_margin_right = 12
	sb.content_margin_top = 10
	sb.content_margin_bottom = 10
	row.add_theme_stylebox_override("panel", sb)

	if not item.get("disabled", false):
		row.mouse_filter = Control.MOUSE_FILTER_STOP
		row.gui_input.connect(func(e: InputEvent) -> void:
			if e is InputEventMouseButton and (e as InputEventMouseButton).pressed:
				_on_option(item.get("id", ""))
		)
	if item.get("disabled", false):
		row.modulate.a = 0.55

	var hbox := HBoxContainer.new()
	hbox.add_theme_constant_override("separation", 8)
	row.add_child(hbox)

	var color: Color = ChromeTheme.COLOR_WAX_RED if item.get("primary", false) else ChromeTheme.COLOR_DEEP_INK
	var weight: int = 600 if item.get("primary", false) else 500
	var label := _make_label(item.get("label", ""), ChromeTheme.font_serif(weight), 17, color)
	label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	hbox.add_child(label)

	# tag(敬请期待)
	var tag = item.get("tag", "")
	if tag != "":
		var tag_label := _make_label(tag.to_upper(), ChromeTheme.font_mono(400), 9, ChromeTheme.COLOR_WAX_RED)
		var tag_panel := PanelContainer.new()
		var tag_sb := StyleBoxFlat.new()
		tag_sb.bg_color = Color(0.545, 0.271, 0.075, 0.06)
		tag_sb.border_color = Color(0.545, 0.271, 0.075, 0.45)
		tag_sb.border_width_left = 1
		tag_sb.border_width_right = 1
		tag_sb.border_width_top = 1
		tag_sb.border_width_bottom = 1
		tag_sb.corner_radius_top_left = 2
		tag_sb.corner_radius_top_right = 2
		tag_sb.corner_radius_bottom_left = 2
		tag_sb.corner_radius_bottom_right = 2
		tag_sb.content_margin_left = 6
		tag_sb.content_margin_right = 6
		tag_sb.content_margin_top = 1
		tag_sb.content_margin_bottom = 1
		tag_panel.add_theme_stylebox_override("panel", tag_sb)
		tag_panel.add_child(tag_label)
		hbox.add_child(tag_panel)

	# hint KeyCap
	var hint: String = item.get("hint", "")
	if hint != "":
		var cap = KeyCapScene.instantiate()
		cap.text = hint
		cap.dim = true
		hbox.add_child(cap)

	return row


func _make_label(text: String, font: FontVariation, size: int, color: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_override("font", font)
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	return l


func _input(event: InputEvent) -> void:
	if not (event is InputEventKey) or not event.pressed or event.echo:
		return
	if event.keycode == KEY_ESCAPE:
		get_viewport().set_input_as_handled()
		_on_close()


func _on_option(option_id: String) -> void:
	match option_id:
		"resume":
			_on_close()
		_:
			print("[system_menu] %s — v0.4+ 实装" % option_id)


func _on_close() -> void:
	closed.emit()
	queue_free()
