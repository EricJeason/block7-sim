extends Control

# preload 保证不依赖 .godot/global_script_class_cache.cfg
const ChromeTheme := preload("res://scripts/ui/chrome_theme.gd")
const KeyCapScene := preload("res://scenes/ui/KeyCap.tscn")

## F4.3 R 关系网 modal — 全屏 12 节点圆形布局 + 治愈者三态紫圈。
## 设计稿对照 docs/design/a/project/modals.jsx RelationshipNetwork 第 490-618 行。
##
## 治愈者三态(suspicion score):
##   - 0 → 无标记
##   - 1-2 → 灰色虚线圈(觉得哪里不对)
##   - 3+ → 紫色实线圈(已确认治愈者)
##
## F4.3 简化版:suspicion score hard-code 几个 NPC,F4 后期接 backend 线索积分系统。

signal closed

# Hard-coded suspicion scores(F4 后期改 backend driven)
# 来自 docs/design/a/project/modals.jsx 第 496-501 行
const SUSPICION: Dictionary = {
	"agent_01": 3,   # 林秋 - confirmed
	"agent_02": 2,   # 阿杏 - suspect
	"agent_12": 1,   # 白嬤 - first inkling
	"agent_07": 1,   # 苏拂 - first inkling
}

# 已知关系(玩家观察到的)— 12 NPC 节点的两两连线
# 数组里每个元素是 [agent_id_a, agent_id_b](无序,只画一次)
const KNOWN_LINKS: Array = [
	["agent_01", "agent_02"],  # 林秋 ↔ 阿杏(师徒)
	["agent_01", "agent_10"],  # 林秋 ↔ 文姐(闺蜜)
	["agent_06", "agent_11"],  # 千绫 ↔ 小璎(师徒)
	["agent_05", "agent_04"],  # 沈砚 ↔ 艾琳(知道艾琳父亲的事)
	["agent_06", "agent_01"],  # 千绫 ↔ 林秋(暗恋)
	["agent_07", "agent_05"],  # 苏拂 ↔ 沈砚(村里熟人)
	["agent_04", "agent_03"],  # 艾琳 ↔ 早纪(协会调查)
]


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	anchor_right = 1.0
	anchor_bottom = 1.0
	_build_ui()


func _build_ui() -> void:
	# 1. 全屏遮罩
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

	# 2. 居中羊皮纸大卡片(80px 边距)
	var card := PanelContainer.new()
	card.add_theme_stylebox_override("panel", ChromeTheme.make_parchment())
	card.anchor_left = 0.0
	card.anchor_top = 0.0
	card.anchor_right = 1.0
	card.anchor_bottom = 1.0
	card.offset_left = 80
	card.offset_top = 60
	card.offset_right = -80
	card.offset_bottom = -60
	add_child(card)

	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 10)
	card.add_child(vbox)

	# 3. 顶部:标题 + 副标题 + 右边日期
	var header := HBoxContainer.new()
	header.add_theme_constant_override("separation", 12)
	vbox.add_child(header)

	var title_col := VBoxContainer.new()
	title_col.add_theme_constant_override("separation", 2)
	title_col.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(title_col)

	title_col.add_child(_make_label("关系网", ChromeTheme.font_serif(600), 26, ChromeTheme.COLOR_DEEP_INK))
	title_col.add_child(_make_label("R · 你所感知的连结", ChromeTheme.font_mono(400), 10, ChromeTheme.COLOR_OAK_INK))

	# 右上 日期
	var gt: float = GameWorld.game_time
	var day: int = int(gt / 86400.0) + 1
	var npc_count: int = GameWorld.agents.size()
	var meta_label := _make_label(
		"DAY %d · %d 人 · 未知关系 %d" % [day, npc_count, max(0, npc_count - 5)],
		ChromeTheme.font_mono(400), 10, ChromeTheme.COLOR_OAK_INK
	)
	meta_label.vertical_alignment = VERTICAL_ALIGNMENT_BOTTOM
	header.add_child(meta_label)

	_add_ink_rule(vbox)

	# 4. 关系网 Canvas(可绘制区域)
	var canvas := _NetworkCanvas.new()
	canvas.suspicion_data = SUSPICION
	canvas.known_links = KNOWN_LINKS
	canvas.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	canvas.size_flags_vertical = Control.SIZE_EXPAND_FILL
	canvas.custom_minimum_size = Vector2(0, 440)
	vbox.add_child(canvas)

	_add_ink_rule(vbox)

	# 5. 底部图例
	var legend := HBoxContainer.new()
	legend.add_theme_constant_override("separation", 16)
	vbox.add_child(legend)

	_add_legend_item(legend, "你", ChromeTheme.COLOR_WAX_RED, false, false, Color.TRANSPARENT)
	_add_legend_item(legend, "关系 · 已知", ChromeTheme.COLOR_OAK_INK, false, false, Color.TRANSPARENT)
	_add_legend_item(legend, "1-2 分 · 觉得哪里不对", ChromeTheme.COLOR_PARCHMENT_LO, true, false, Color(0.627, 0.565, 0.502))
	_add_legend_item(legend, "3+ 分 · 已确认治愈者", ChromeTheme.COLOR_PARCHMENT_LO, false, true, ChromeTheme.COLOR_HEALER_LILAC)

	# 底右 R 合上
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	legend.add_child(spacer)

	var cap = KeyCapScene.instantiate()
	cap.text = "R"
	cap.dim = true
	legend.add_child(cap)

	legend.add_child(_make_label("合上", ChromeTheme.font_mono(400), 10, ChromeTheme.COLOR_OAK_INK))


func _add_legend_item(parent: Node, label_text: String, swatch_color: Color, dashed_ring: bool, solid_ring: bool, ring_color: Color) -> void:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 6)

	# 色块
	var chip := ColorRect.new()
	chip.color = swatch_color
	chip.custom_minimum_size = Vector2(12, 12)
	row.add_child(chip)

	# (可选)环
	if dashed_ring or solid_ring:
		# 用 ColorRect 圆角模拟 — 用 PanelContainer + StyleBoxFlat 圆角 999
		var ring := PanelContainer.new()
		var sb := StyleBoxFlat.new()
		sb.bg_color = Color.TRANSPARENT
		sb.border_width_left = 1 if dashed_ring else 2
		sb.border_width_right = 1 if dashed_ring else 2
		sb.border_width_top = 1 if dashed_ring else 2
		sb.border_width_bottom = 1 if dashed_ring else 2
		sb.border_color = ring_color
		sb.corner_radius_top_left = 999
		sb.corner_radius_top_right = 999
		sb.corner_radius_bottom_left = 999
		sb.corner_radius_bottom_right = 999
		ring.add_theme_stylebox_override("panel", sb)
		ring.custom_minimum_size = Vector2(14, 14)
		row.add_child(ring)

	row.add_child(_make_label(label_text, ChromeTheme.font_mono(400), 10, ChromeTheme.COLOR_OAK_INK))

	parent.add_child(row)


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
	if event.keycode == KEY_R or event.keycode == KEY_ESCAPE:
		get_viewport().set_input_as_handled()
		_on_close()


func _on_close() -> void:
	closed.emit()
	queue_free()


# ============================================================================
# 内嵌 Control 子类 — 绘制 12 节点关系网
# ============================================================================
class _NetworkCanvas extends Control:
	var suspicion_data: Dictionary = {}
	var known_links: Array = []
	# 用于 hover tooltip(F4.3 简化:暂不实装 hover,F4 后期接)

	const ChromeTheme := preload("res://scripts/ui/chrome_theme.gd")

	func _draw() -> void:
		var rect_size: Vector2 = size
		if rect_size.x < 100 or rect_size.y < 100:
			return

		var cx: float = rect_size.x * 0.5
		var cy: float = rect_size.y * 0.5
		var radius: float = min(rect_size.x, rect_size.y) * 0.4

		# 排序 agent_ids,稳定每次同一布局
		var all_ids: Array = GameWorld.agents.keys()
		all_ids.sort()
		var n: int = all_ids.size()
		if n == 0:
			return

		var positions: Dictionary = {}
		for i in range(n):
			var aid: String = all_ids[i]
			var angle: float = (float(i) / n) * TAU - PI * 0.5
			positions[aid] = Vector2(cx + cos(angle) * radius, cy + sin(angle) * radius)

		# 1. 画连线(known links)
		var link_color := ChromeTheme.COLOR_OAK_INK
		link_color.a = 0.5
		for link in known_links:
			if link.size() != 2:
				continue
			var a: String = link[0]
			var b: String = link[1]
			if not positions.has(a) or not positions.has(b):
				continue
			draw_line(positions[a], positions[b], link_color, 1.2, true)

		# 2. 画节点(circle + name)
		for i in range(n):
			var aid: String = all_ids[i]
			var pos: Vector2 = positions[aid]
			var is_player: bool = (aid == GameWorld.player_agent_id)
			var score: int = suspicion_data.get(aid, 0)

			# 治愈者三态环
			if score >= 3:
				# 紫色实线圈
				draw_arc(pos, 24, 0, TAU, 32, ChromeTheme.COLOR_HEALER_LILAC, 2.0, true)
			elif score >= 1:
				# 灰色虚线圈(GDScript 不直接支持 dashed line,用多段 arc 模拟)
				var dash_color := Color(0.627, 0.565, 0.502, 0.85)
				var seg_count: int = 16
				for s in range(0, seg_count, 2):
					var start_angle: float = TAU * s / seg_count
					var end_angle: float = TAU * (s + 1) / seg_count
					draw_arc(pos, 24, start_angle, end_angle, 4, dash_color, 1.3, true)

			# 节点圆
			var node_color: Color = _color_for_agent(aid)
			var border_color: Color = ChromeTheme.COLOR_WAX_RED if is_player else ChromeTheme.COLOR_OAK_INK
			var border_width: float = 3.0 if is_player else 1.0
			var node_radius: float = 22.0 if is_player else 18.0
			draw_circle(pos, node_radius, node_color)
			draw_arc(pos, node_radius, 0, TAU, 32, border_color, border_width, true)

			# YOU 文字
			if is_player:
				var font_mono: FontVariation = ChromeTheme.font_mono(600)
				var you_text: String = "YOU"
				var text_size: Vector2 = font_mono.get_string_size(you_text, HORIZONTAL_ALIGNMENT_CENTER, -1, 9)
				draw_string(font_mono, pos + Vector2(-text_size.x * 0.5, 3), you_text,
					HORIZONTAL_ALIGNMENT_CENTER, -1, 9, Color.WHITE)

			# 节点下方名字
			var name_text: String = GameWorld.get_agent(aid).get("display_name", aid)
			var font_serif: FontVariation = ChromeTheme.font_serif(500)
			var name_size: Vector2 = font_serif.get_string_size(name_text, HORIZONTAL_ALIGNMENT_CENTER, -1, 14)
			draw_string(font_serif, pos + Vector2(-name_size.x * 0.5, 42), name_text,
				HORIZONTAL_ALIGNMENT_CENTER, -1, 14, ChromeTheme.COLOR_DEEP_INK)

	func _color_for_agent(aid: String) -> Color:
		# 按 agent_id hash 派生稳定色(与 AgentNode 一致)
		var h: int = abs(aid.hash())
		var hue: float = float(h % 360) / 360.0
		return Color.from_hsv(hue, 0.55, 0.85)
