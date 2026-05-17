extends Control

# preload 保证不依赖 .godot/global_script_class_cache.cfg
const ChromeTheme := preload("res://scripts/ui/chrome_theme.gd")
const KeyCapScene := preload("res://scenes/ui/KeyCap.tscn")

## F4.4 全屏 DialogueSession (S11) — 玩家与 NPC 持续对话 modal。
##
## 设计稿对照 docs/design/a/project/modals.jsx DialogueSession 第 316+:
## - 78% 黑遮罩 + 居中卡片(960×600)
## - 顶部:NPC portrait(256×256 占位)+ 名字 + 关闭按钮
## - 中部:对话历史 ScrollContainer
## - 底部:LineEdit + 发送按钮 + 提示
##
## 流程:
## 1. main.gd 已经通过 BackendClient.player_greet 创建 session,玩家初始 line + NPC 回复已推回
## 2. modal setup(session_id, npc_id, initial_history) 进入持续对话状态
## 3. GameWorld.dialogue_line signal → 追加新 line 到历史显示
## 4. 玩家输入 + Enter / 发送 → BackendClient.continue_dialogue
## 5. Esc / 关闭按钮 → BackendClient.end_dialogue → 关 modal

signal closed

var _session_id: String = ""
var _npc_id: String = ""
var _npc_name: String = ""
var _player_name: String = ""
var _is_npc_thinking: bool = false
# F4.4 时序:setup 在 backend player_greet 返回 session_id 后才调,但 WS 推 dialogue_line
# 可能更早到达。setup 前的 WS 消息存进 buffer,setup 后 flush。
var _pending_lines: Array = []
var _seen_turn_indices: Dictionary = {}

@onready var _history_vbox: VBoxContainer = $Card/Content/HistoryScroll/HistoryVBox
@onready var _history_scroll: ScrollContainer = $Card/Content/HistoryScroll
@onready var _input_edit: LineEdit = $Card/Content/InputRow/InputEdit
@onready var _send_btn: Button = $Card/Content/InputRow/SendBtn
@onready var _name_label: Label = $Card/Content/Header/NameCol/Name
@onready var _role_label: Label = $Card/Content/Header/NameCol/Role
@onready var _portrait_rect: ColorRect = $Card/Content/Header/Portrait
@onready var _thinking_label: Label = $Card/Content/HistoryScroll/HistoryVBox/ThinkingLabel


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	anchor_right = 1.0
	anchor_bottom = 1.0
	_apply_styles()
	# 连接 backend WS 事件
	GameWorld.dialogue_line.connect(_on_dialogue_line)
	GameWorld.dialogue_ended.connect(_on_dialogue_ended)
	# 输入框
	_input_edit.text_submitted.connect(_on_input_submitted)
	_send_btn.pressed.connect(_on_send_pressed)
	# 自动 focus 到输入框
	_input_edit.call_deferred("grab_focus")


func setup(session_id: String, npc_id: String) -> void:
	"""main.gd 在 BackendClient.player_greet 回调里调:
	  session_id - backend session id(get_player_greet response)
	  npc_id     - 对话对方 agent_id
	"""
	_session_id = session_id
	_npc_id = npc_id
	var npc_agent: Dictionary = GameWorld.get_agent(npc_id)
	_npc_name = npc_agent.get("display_name", npc_id)
	var player_agent: Dictionary = GameWorld.get_agent(GameWorld.player_agent_id)
	_player_name = player_agent.get("display_name", "我")

	if is_inside_tree():
		_refresh_header()
		_flush_pending_lines()


func _flush_pending_lines() -> void:
	"""把 setup 前缓存的 WS dialogue_line 倒回来 append。"""
	for entry in _pending_lines:
		if entry.get("sid", "") == _session_id:
			_consume_dialogue_line(entry.get("speaker_id", ""), entry.get("text", ""), entry.get("turn_idx", -1))
	_pending_lines.clear()


func _apply_styles() -> void:
	# 全屏遮罩
	$Scrim.color = ChromeTheme.COLOR_MODAL_SCRIM
	# 卡片
	$Card.add_theme_stylebox_override("panel", ChromeTheme.make_parchment())
	# NPC portrait 占位
	_portrait_rect.color = Color(0.42, 0.345, 0.251, 0.4)
	# 标题
	_name_label.add_theme_font_override("font", ChromeTheme.font_serif(600))
	_name_label.add_theme_font_size_override("font_size", 24)
	_name_label.add_theme_color_override("font_color", ChromeTheme.COLOR_DEEP_INK)
	_role_label.add_theme_font_override("font", ChromeTheme.font_mono(400))
	_role_label.add_theme_font_size_override("font_size", 11)
	_role_label.add_theme_color_override("font_color", ChromeTheme.COLOR_OAK_INK)
	# 输入框
	_input_edit.add_theme_font_override("font", ChromeTheme.font_serif(500))
	_input_edit.add_theme_font_size_override("font_size", 16)
	_input_edit.add_theme_color_override("font_color", ChromeTheme.COLOR_DEEP_INK)
	_input_edit.placeholder_text = "在这里写你的话…  (Enter 发送)"
	# 发送按钮
	_send_btn.add_theme_font_override("font", ChromeTheme.font_serif(600))
	_send_btn.add_theme_font_size_override("font_size", 14)
	_send_btn.text = "发送 →"
	# Thinking 提示(初始隐藏)
	_thinking_label.add_theme_font_override("font", ChromeTheme.font_serif(400))
	_thinking_label.add_theme_font_size_override("font_size", 14)
	_thinking_label.add_theme_color_override("font_color", Color(ChromeTheme.COLOR_OAK_INK.r, ChromeTheme.COLOR_OAK_INK.g, ChromeTheme.COLOR_OAK_INK.b, 0.6))
	_thinking_label.visible = false


func _refresh_header() -> void:
	_name_label.text = _npc_name
	# 加载 portrait(如果有)
	var portrait_path: String = "res://assets/portraits/%s/normal.png" % _npc_id
	if not ResourceLoader.exists(portrait_path):
		portrait_path = "res://assets/characters/%s/idle.png" % _npc_id
	if ResourceLoader.exists(portrait_path):
		var tex: Texture2D = load(portrait_path) as Texture2D
		if tex != null:
			# 用 TextureRect 替代 ColorRect 显示
			var existing_sprite: TextureRect = _portrait_rect.get_node_or_null("PortraitSprite") as TextureRect
			if existing_sprite == null:
				existing_sprite = TextureRect.new()
				existing_sprite.name = "PortraitSprite"
				existing_sprite.anchor_right = 1.0
				existing_sprite.anchor_bottom = 1.0
				existing_sprite.expand_mode = TextureRect.EXPAND_FIT_WIDTH_PROPORTIONAL
				existing_sprite.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
				_portrait_rect.add_child(existing_sprite)
			existing_sprite.texture = tex
	# 角色简介(从 persona / mood)
	var npc_agent: Dictionary = GameWorld.get_agent(_npc_id)
	var role: String = npc_agent.get("current_mood", "")
	if role == "":
		role = "在 %s" % GameWorld.get_location(GameWorld.current_view_location).get("name", "暮谷镇")
	_role_label.text = role


func _append_line(speaker_id: String, text: String) -> void:
	"""追加一行对话到历史。玩家右对齐 + 封蜡红;NPC 左对齐 + 深咖墨。"""
	var is_player: bool = (speaker_id == GameWorld.player_agent_id)
	var speaker_name: String = _player_name if is_player else _npc_name

	# 整行
	var row := HBoxContainer.new()
	row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.alignment = BoxContainer.ALIGNMENT_END if is_player else BoxContainer.ALIGNMENT_BEGIN

	# 气泡(PanelContainer + Label)
	var bubble := PanelContainer.new()
	var bubble_sb := StyleBoxFlat.new()
	if is_player:
		bubble_sb.bg_color = Color(ChromeTheme.COLOR_WAX_RED.r, ChromeTheme.COLOR_WAX_RED.g, ChromeTheme.COLOR_WAX_RED.b, 0.08)
		bubble_sb.border_color = Color(ChromeTheme.COLOR_WAX_RED.r, ChromeTheme.COLOR_WAX_RED.g, ChromeTheme.COLOR_WAX_RED.b, 0.4)
	else:
		bubble_sb.bg_color = Color(ChromeTheme.COLOR_OAK_INK.r, ChromeTheme.COLOR_OAK_INK.g, ChromeTheme.COLOR_OAK_INK.b, 0.06)
		bubble_sb.border_color = Color(ChromeTheme.COLOR_OAK_INK.r, ChromeTheme.COLOR_OAK_INK.g, ChromeTheme.COLOR_OAK_INK.b, 0.4)
	bubble_sb.border_width_left = 1
	bubble_sb.border_width_right = 1
	bubble_sb.border_width_top = 1
	bubble_sb.border_width_bottom = 1
	bubble_sb.corner_radius_top_left = 6
	bubble_sb.corner_radius_top_right = 6
	bubble_sb.corner_radius_bottom_left = 6
	bubble_sb.corner_radius_bottom_right = 6
	bubble_sb.content_margin_left = 12
	bubble_sb.content_margin_right = 12
	bubble_sb.content_margin_top = 8
	bubble_sb.content_margin_bottom = 8
	bubble.add_theme_stylebox_override("panel", bubble_sb)
	bubble.custom_minimum_size = Vector2(0, 0)
	bubble.size_flags_horizontal = Control.SIZE_SHRINK_END if is_player else Control.SIZE_SHRINK_BEGIN

	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 2)
	bubble.add_child(v)

	# 名字小标
	var name_label := Label.new()
	name_label.text = speaker_name
	name_label.add_theme_font_override("font", ChromeTheme.font_mono(600))
	name_label.add_theme_font_size_override("font_size", 9)
	var name_color: Color = ChromeTheme.COLOR_WAX_RED if is_player else ChromeTheme.COLOR_OAK_INK
	name_label.add_theme_color_override("font_color", name_color)
	v.add_child(name_label)

	# 文字
	var text_label := Label.new()
	text_label.text = text
	text_label.add_theme_font_override("font", ChromeTheme.font_serif(500))
	text_label.add_theme_font_size_override("font_size", 16)
	text_label.add_theme_color_override("font_color", ChromeTheme.COLOR_DEEP_INK)
	text_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	text_label.custom_minimum_size = Vector2(min(500, get_viewport_rect().size.x * 0.5), 0)
	v.add_child(text_label)

	row.add_child(bubble)

	# 把"thinking"label 永远保持在最底,新行插在它之前
	var thinking_index: int = _thinking_label.get_index()
	_history_vbox.add_child(row)
	_history_vbox.move_child(row, thinking_index)

	# 自动滚到底
	call_deferred("_scroll_to_bottom")


func _scroll_to_bottom() -> void:
	if _history_scroll == null:
		return
	var vbar = _history_scroll.get_v_scroll_bar()
	if vbar:
		await get_tree().process_frame
		_history_scroll.scroll_vertical = int(vbar.max_value)


func _set_npc_thinking(thinking: bool) -> void:
	_is_npc_thinking = thinking
	_thinking_label.visible = thinking
	if thinking:
		_thinking_label.text = "%s 正在斟酌……" % _npc_name
		# 禁用输入直到 NPC 回复完
		_input_edit.editable = false
		_send_btn.disabled = true
	else:
		_input_edit.editable = true
		_send_btn.disabled = false
		_input_edit.call_deferred("grab_focus")


func _on_dialogue_line(session_id: String, speaker_id: String, text: String, turn_idx: int) -> void:
	if _session_id == "":
		# 还没 setup,buffer 起来等 setup 后 flush
		_pending_lines.append({
			"sid": session_id, "speaker_id": speaker_id, "text": text, "turn_idx": turn_idx
		})
		return
	if session_id != _session_id:
		return
	_consume_dialogue_line(speaker_id, text, turn_idx)


func _consume_dialogue_line(speaker_id: String, text: String, turn_idx: int) -> void:
	"""处理一条 dialogue_line(已通过 session_id 校验)。
	用 turn_idx 去重 — 防 setup flush + WS 异步多次推到。"""
	if turn_idx >= 0 and _seen_turn_indices.has(turn_idx):
		return
	if turn_idx >= 0:
		_seen_turn_indices[turn_idx] = true
	_append_line(speaker_id, text)
	if speaker_id == GameWorld.player_agent_id:
		_set_npc_thinking(true)
	else:
		_set_npc_thinking(false)


func _on_dialogue_ended(session_id: String, _initiator_id: String, _target_id: String, _total_turns: int, _reason: String) -> void:
	if session_id != _session_id:
		return
	# Backend 主动关闭(可能 LLM 输出 [END] token)
	_on_close()


func _on_input_submitted(text: String) -> void:
	_send_player_line(text)


func _on_send_pressed() -> void:
	_send_player_line(_input_edit.text)


func _send_player_line(text: String) -> void:
	var clean: String = text.strip_edges()
	if clean == "":
		return
	if _is_npc_thinking:
		return
	_input_edit.text = ""
	# 立即显示玩家 line(乐观)— backend WS 也会推回 dialogue_line 但 session_id 不变,会重复
	# 简化:不本地预显,等 WS 推。然后 NPC 思考态由 _on_dialogue_line 设
	BackendClient.continue_dialogue(_session_id, clean, func(ok: bool) -> void:
		if not ok:
			push_warning("[dialogue] continue failed")
	)


func _input(event: InputEvent) -> void:
	if not (event is InputEventKey) or not event.pressed or event.echo:
		return
	if event.keycode == KEY_ESCAPE:
		get_viewport().set_input_as_handled()
		_on_close()


func _on_close() -> void:
	# 通知 backend 关闭 session(可选)
	if _session_id != "":
		BackendClient.end_dialogue(_session_id)
	# 解绑 signal
	if GameWorld.dialogue_line.is_connected(_on_dialogue_line):
		GameWorld.dialogue_line.disconnect(_on_dialogue_line)
	if GameWorld.dialogue_ended.is_connected(_on_dialogue_ended):
		GameWorld.dialogue_ended.disconnect(_on_dialogue_ended)
	closed.emit()
	queue_free()
