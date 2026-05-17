extends Control

# preload 保证不依赖 .godot/global_script_class_cache.cfg
const ChromeTheme := preload("res://scripts/ui/chrome_theme.gd")

## F3 Q 场所概览半屏卡片(轻量信息层,无全屏遮罩)。
##
## 设计稿对照 docs/design/a/project/modals.jsx LocationCard 第 7-87 行:
## - 右上 376×自适应 卡片,top=70 right=28
## - 羊皮纸 + 1px 旧橡木墨边 + 圆角 4px + drop-shadow
## - 内容(从上到下):
##   * 场所名(中文 serif 26 + 英文 mono 10)+ 右上"Q · 关闭"按钮
##   * mood 文字(serif 13 italic)
##   * "此地 · N 人" + 2列 NPC grid(色块 + 名字 + 角色)
##   * "出口" + 出口列表(serif 14 + 封蜡红 › 前缀)
##   * 底部 今日天气 + DAY N HH:MM
##
## 控制:Q 切换显隐;Esc 关闭;鼠标点关闭按钮关闭。

signal closed

var _location_id: String = ""


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP  # 拦截鼠标
	# 定位:右上,但用绝对位置确保不被 stretch 影响布局
	anchor_left = 0.0
	anchor_top = 0.0
	anchor_right = 0.0
	anchor_bottom = 0.0
	offset_left = 880.0
	offset_top = 70.0
	offset_right = 1256.0
	offset_bottom = 670.0
	_build_card()


func setup(location_id: String) -> void:
	_location_id = location_id
	# 在 _ready 之后才能填充 — 如果 _ready 已经跑,立即重填
	if is_inside_tree():
		_rebuild_content()


func _build_card() -> void:
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", ChromeTheme.make_parchment())
	panel.anchor_right = 1.0
	panel.anchor_bottom = 1.0
	panel.name = "Panel"
	add_child(panel)

	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 8)
	vbox.name = "VBox"
	panel.add_child(vbox)

	# 首次填充(_location_id 可能空,稍后 setup 调用会重填)
	_rebuild_content()


func _rebuild_content() -> void:
	var vbox: VBoxContainer = get_node_or_null("Panel/VBox") as VBoxContainer
	if vbox == null:
		return
	for child in vbox.get_children():
		child.queue_free()

	var loc: Dictionary = GameWorld.get_location(_location_id)
	var cn_name: String = loc.get("name", _location_id)
	var en_name: String = loc.get("name_en", _location_id)
	var description: String = loc.get("description", "")
	var adjacent: Array = loc.get("adjacent_to", [])

	# 1. 标题行(中文 + 英文 + 关闭按钮)
	var title_row := HBoxContainer.new()
	title_row.add_theme_constant_override("separation", 8)
	vbox.add_child(title_row)

	var title_col := VBoxContainer.new()
	title_col.add_theme_constant_override("separation", 2)
	title_col.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	title_row.add_child(title_col)

	var cn_label := _make_label(cn_name, ChromeTheme.font_serif(600), 26, ChromeTheme.COLOR_DEEP_INK)
	title_col.add_child(cn_label)

	var en_label := _make_label(en_name.to_upper(), ChromeTheme.font_mono(400), 10, ChromeTheme.COLOR_OAK_INK)
	title_col.add_child(en_label)

	var close_btn := Button.new()
	close_btn.text = "Q · 关闭"
	close_btn.add_theme_font_override("font", ChromeTheme.font_mono(600))
	close_btn.add_theme_font_size_override("font_size", 10)
	close_btn.add_theme_color_override("font_color", ChromeTheme.COLOR_OAK_INK)
	close_btn.flat = true
	close_btn.pressed.connect(_on_close)
	title_row.add_child(close_btn)

	# 2. mood/description(取 description 第一行作为氛围标语)
	var mood: String = description.split("\n")[0].strip_edges() if description.length() > 0 else ""
	if mood.length() > 0:
		# 限制长度,避免占太多空间
		if mood.length() > 60:
			mood = mood.substr(0, 60) + "..."
		var mood_label := _make_label(mood, ChromeTheme.font_serif(400), 13, ChromeTheme.COLOR_OAK_INK)
		mood_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		vbox.add_child(mood_label)

	_add_ink_rule(vbox)

	# 3. "此地 · N 人"
	var here_agents: Array = GameWorld.get_agents_in_location(_location_id)
	# 排除玩家自己
	var npc_agents: Array = []
	for a in here_agents:
		if not GameWorld.is_player_agent(a.get("agent_id", "")):
			npc_agents.append(a)

	var section_label := _make_label("此地 · %d 人" % npc_agents.size(),
		ChromeTheme.font_mono(400), 10, ChromeTheme.COLOR_OAK_INK)
	vbox.add_child(section_label)

	# 4. NPC grid(2 列)
	var grid := GridContainer.new()
	grid.columns = 2
	grid.add_theme_constant_override("h_separation", 6)
	grid.add_theme_constant_override("v_separation", 4)
	vbox.add_child(grid)

	for a in npc_agents:
		var npc_row := _make_npc_row(a)
		grid.add_child(npc_row)

	_add_ink_rule(vbox)

	# 5. 出口
	var exits_title := _make_label("出口", ChromeTheme.font_mono(400), 10, ChromeTheme.COLOR_OAK_INK)
	vbox.add_child(exits_title)

	if adjacent.is_empty():
		var none_label := _make_label("(此地无显式出口)", ChromeTheme.font_serif(400), 13, ChromeTheme.COLOR_OAK_INK)
		vbox.add_child(none_label)
	else:
		for adj_id in adjacent:
			var adj_loc: Dictionary = GameWorld.get_location(adj_id)
			var adj_name: String = adj_loc.get("name", adj_id)
			var dir_hint: String = _direction_hint(_location_id, adj_id)
			var exit_row := HBoxContainer.new()
			exit_row.add_theme_constant_override("separation", 8)
			var prefix := _make_label("›", ChromeTheme.font_serif(600), 16, ChromeTheme.COLOR_WAX_RED)
			exit_row.add_child(prefix)
			var exit_label := _make_label("%s%s" % [dir_hint, adj_name],
				ChromeTheme.font_serif(500), 14, ChromeTheme.COLOR_DEEP_INK)
			exit_row.add_child(exit_label)
			vbox.add_child(exit_row)

	_add_ink_rule(vbox)

	# 6. 底部:天气 + 日期时间
	var footer := HBoxContainer.new()
	footer.add_theme_constant_override("separation", 0)
	vbox.add_child(footer)

	var weather_col := VBoxContainer.new()
	weather_col.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	weather_col.add_child(_make_label("今日天气", ChromeTheme.font_mono(400), 10, ChromeTheme.COLOR_OAK_INK))
	weather_col.add_child(_make_label("晴 · 微风", ChromeTheme.font_serif(500), 14, ChromeTheme.COLOR_DEEP_INK))
	footer.add_child(weather_col)

	var time_col := VBoxContainer.new()
	time_col.alignment = BoxContainer.ALIGNMENT_END
	var gt: float = GameWorld.game_time
	var day: int = int(gt / 86400.0) + 1
	var sec_today: float = fmod(gt, 86400.0)
	var hour: int = int(sec_today / 3600.0)
	var minute: int = int(fmod(sec_today, 3600.0) / 60.0)
	var day_label := _make_label("DAY %d" % day, ChromeTheme.font_mono(400), 10, ChromeTheme.COLOR_OAK_INK)
	day_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	time_col.add_child(day_label)
	var time_label := _make_label("%02d:%02d" % [hour, minute],
		ChromeTheme.font_mono(600), 14, ChromeTheme.COLOR_DEEP_INK)
	time_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	time_col.add_child(time_label)
	footer.add_child(time_col)


func _make_npc_row(agent: Dictionary) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 6)

	# 色块(按 agent_id hash 派生稳定色)
	var color_chip := ColorRect.new()
	var aid: String = agent.get("agent_id", "")
	var h: int = abs(aid.hash())
	color_chip.color = Color.from_hsv(float(h % 360) / 360.0, 0.55, 0.85)
	color_chip.custom_minimum_size = Vector2(8, 8)
	row.add_child(color_chip)

	var name_label := _make_label(agent.get("display_name", aid),
		ChromeTheme.font_serif(500), 13, ChromeTheme.COLOR_DEEP_INK)
	name_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(name_label)

	# 角色简称(从 mood / current_action 取,F2 简化)
	return row


func _direction_hint(from_id: String, to_id: String) -> String:
	"""根据 player_node.gd 的方向映射,在 exit 名前加方向前缀。"""
	if from_id == "lao_song_plaza":
		match to_id:
			"north_frost_workshop": return "北 → "
			"warm_valley_farm":     return "南 → "
			"silent_tower_ruins":   return "东 → "
	# 其他场所:任意方向都回 plaza
	return "→ "


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
	var key = event.keycode
	if key == KEY_Q or key == KEY_ESCAPE:
		get_viewport().set_input_as_handled()
		_on_close()


func _on_close() -> void:
	closed.emit()
	queue_free()
