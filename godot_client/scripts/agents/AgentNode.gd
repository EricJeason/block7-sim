extends Node2D

# preload 保证不依赖 .godot/global_script_class_cache.cfg(被 .gitignore)
const ChromeTheme := preload("res://scripts/ui/chrome_theme.gd")
const KeyCapScene := preload("res://scenes/ui/KeyCap.tscn")

## 单个 agent 在场景里的可视节点。LocationView 在 agent 进入本场所时 instantiate。
##
## 视觉构成 (F2):
##   PlaceholderRect — 缺 sprite 时的色块兜底
##   Sprite          — 有 walk_*.png 时显示
##   NameLabel       — 头顶显示中文名(F2 保留常驻,F4 改 hover 触发)
##   ActionLabel     — 脚下 action 摘要(F2 隐藏,用 HoverWhisper 替代)
##   ThinkingIndicator — 💭(F2 永久隐藏,违反扮演体验)
##   SpeechBubble    — 对话气泡(Block I 保留)
##   HoverWhisper    — F2 新增:距离 <140px 玩家时头顶显示 "name·action"(动态创建)
##   EPrompt         — F2 新增:距离 <110px 且为最近 NPC 时上方 [E] 互动(动态创建)

@export var agent_id: String = ""

@onready var placeholder_rect: ColorRect = $PlaceholderRect
@onready var sprite: Sprite2D = $Sprite
@onready var name_label: Label = $NameLabel
@onready var action_label: Label = $ActionLabel
@onready var thinking_indicator: Label = $ThinkingIndicator
@onready var speech_bubble: PanelContainer = $SpeechBubble
@onready var speech_label: Label = $SpeechBubble/SpeechLabel
@onready var click_area: Area2D = $ClickArea

var _has_sprite: bool = false
var _speech_hide_timer: SceneTreeTimer = null

# F2 动态创建的 hover whisper + E prompt
var _hover_whisper: PanelContainer = null
var _hover_whisper_label: Label = null
var _e_prompt: HBoxContainer = null
var _current_action_text: String = ""


func _ready() -> void:
	if agent_id == "":
		push_warning("[AgentNode] agent_id is empty")
		return

	_apply_persona_visuals()
	_apply_initial_action_label()
	# F2: 隐藏 ActionLabel 常驻显示(改用 HoverWhisper)+ 永久隐藏 💭 思考指示器
	# (设计稿红线:"上帝视角语言,跟扮演体验冲突")
	action_label.visible = false
	thinking_indicator.visible = false
	# 点击 sprite/色块 → 触发 GameWorld.agent_clicked,main.gd 据此弹 memory 面板
	click_area.input_event.connect(_on_click_area_input)

	_build_hover_whisper()
	_build_e_prompt()


func _on_click_area_input(_viewport: Node, event: InputEvent, _shape_idx: int) -> void:
	if event is InputEventMouseButton:
		var mb := event as InputEventMouseButton
		if mb.pressed and mb.button_index == MOUSE_BUTTON_LEFT:
			GameWorld.agent_clicked.emit(agent_id)


func _apply_persona_visuals() -> void:
	# 中文名(从 GameWorld 缓存取)
	var a: Dictionary = GameWorld.get_agent(agent_id)
	var display_name: String = a.get("display_name", agent_id)
	name_label.text = display_name

	# 尝试加载 sprite
	var sprite_path: String = "res://assets/characters/%s/idle.png" % agent_id
	if not ResourceLoader.exists(sprite_path):
		sprite_path = "res://assets/characters/%s/walk_s.png" % agent_id

	if ResourceLoader.exists(sprite_path):
		var tex: Texture2D = load(sprite_path) as Texture2D
		if tex != null:
			sprite.texture = tex
			# 缩放到约 120 像素高(与占位 PlaceholderRect 一致)
			var target_h: float = 120.0
			var orig_h: float = tex.get_height()
			if orig_h > 0.0:
				var s: float = target_h / orig_h
				sprite.scale = Vector2(s, s)
			sprite.visible = true
			placeholder_rect.visible = false
			_has_sprite = true
			return

	# 没素材 → 用色块占位,颜色按 agent_id hash 区分
	placeholder_rect.color = _color_for_agent(agent_id)
	placeholder_rect.visible = true
	sprite.visible = false


func _color_for_agent(aid: String) -> Color:
	# 按 agent_id 哈希派生稳定颜色;饱和度高便于辨识
	var h: int = abs(aid.hash())
	var hue: float = float(h % 360) / 360.0
	return Color.from_hsv(hue, 0.55, 0.85)


func _apply_initial_action_label() -> void:
	var a: Dictionary = GameWorld.get_agent(agent_id)
	var current_action = a.get("current_action")
	if current_action == null or typeof(current_action) != TYPE_DICTIONARY:
		_current_action_text = ""
		return
	_current_action_text = _format_action_label(current_action)


# ----------------------------------------------------- event handlers
# 这些方法由 LocationView 主动调用(它从 GameWorld signal 接到事件后转发)

func on_action_started(action: Dictionary) -> void:
	_current_action_text = _format_action_label(action)
	if _hover_whisper_label != null and _hover_whisper.visible:
		_hover_whisper_label.text = _whisper_text()
	# 移动动作:按 args.location 切换朝向贴图
	if action.get("action_type", "") == "move_to":
		_face_for_direction("s")  # 占位:默认朝南。后续可按 from/to 算


func on_action_completed(_action: Dictionary) -> void:
	_current_action_text = ""
	if _hover_whisper_label != null and _hover_whisper.visible:
		_hover_whisper_label.text = _whisper_text()


var _thinking_timeout_timer: SceneTreeTimer = null

func on_thinking_started() -> void:
	# F2: 不再显示 💭 思考灯泡(扮演体验)。保留 method 签名给 LocationView 调用。
	pass


func on_thinking_completed(_appended_count: int) -> void:
	# F2: 不再操作 thinking_indicator(已永久隐藏)
	pass


# ------------------------------------------------------- dialogue speech

## 显示一句台词。时长按字数动态调整(每字 ~0.18s,最少 4 秒):
##   30 字 → 5.4 秒,50 字 → 9 秒,80 字 → 14.4 秒
## 由 LocationView 接到 GameWorld.dialogue_line signal 后转发。
func show_speech_line(text: String) -> void:
	speech_label.text = text
	speech_bubble.visible = true
	# 按字数算阅读时间;中文字符按 1 字计算
	var duration: float = max(4.0, float(text.length()) * 0.18)
	var snapshot_text := text
	var t := get_tree().create_timer(duration)
	_speech_hide_timer = t
	t.timeout.connect(func() -> void:
		# 仅在没有被新台词覆盖时才隐藏
		if speech_label.text == snapshot_text:
			speech_bubble.visible = false
	)


## 仅在显式需要立刻清空时调用(如场景切换)。
## dialogue_ended 不再调此方法,让最后一句的 timer 自然结束 — 避免被挤掉。
func hide_speech() -> void:
	speech_bubble.visible = false
	speech_label.text = ""


# -------------------------------------------------------------- helpers

func _format_action_label(action: Dictionary) -> String:
	"""把 action dict 压成一行可读文字。"""
	var a_type: String = action.get("action_type", "?")
	var args: Dictionary = action.get("args", {})
	var summary: String = a_type
	if a_type == "move_to":
		summary = "→ " + str(args.get("location", "?"))
	elif a_type == "work":
		summary = "工作:" + str(args.get("task", "?"))
	elif a_type == "rest":
		summary = "休息"
	elif a_type == "observe":
		summary = "观察:" + str(args.get("target", "?"))
	elif a_type == "interact":
		summary = "互动:" + str(args.get("target", "?"))
	elif a_type == "talk_to":
		summary = "说话→" + str(args.get("agent_id", "?"))
	elif a_type == "idle":
		summary = "..."
	return summary


func _face_for_direction(direction: String) -> void:
	"""切换 walk 方向贴图。direction: n/s/e/w。仅在有素材时切换。"""
	if not _has_sprite:
		return
	var path: String = "res://assets/characters/%s/walk_%s.png" % [agent_id, direction]
	if not ResourceLoader.exists(path):
		return
	var tex: Texture2D = load(path) as Texture2D
	if tex != null:
		sprite.texture = tex


# ============================================================================
# F2 HoverWhisper + E-prompt(玩家走近触发,LocationView 调度)
# ============================================================================

func _build_hover_whisper() -> void:
	"""动态构造头顶 hover whisper(半透明羊皮纸 + 旧橡木墨边 + serif 13px)。
	内容:"name · action 摘要"。设计稿 ui-elements.jsx HoverWhisper()。"""
	_hover_whisper = PanelContainer.new()
	_hover_whisper.add_theme_stylebox_override("panel", ChromeTheme.make_parchment_floating(0.78))
	_hover_whisper.visible = false
	_hover_whisper.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hover_whisper.position = Vector2(-90, -160)  # 头顶上方
	_hover_whisper.size = Vector2(180, 0)

	_hover_whisper_label = Label.new()
	_hover_whisper_label.add_theme_font_override("font", ChromeTheme.font_serif(500))
	_hover_whisper_label.add_theme_font_size_override("font_size", 13)
	_hover_whisper_label.add_theme_color_override("font_color", Color(0.157, 0.118, 0.078, 0.92))
	_hover_whisper_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_hover_whisper_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_hover_whisper.add_child(_hover_whisper_label)

	add_child(_hover_whisper)


func _build_e_prompt() -> void:
	"""动态构造 [E] 互动浮气泡 — 头顶更高位置,只对最近 NPC 显示。
	设计稿 main-screen.jsx 第 196-211 行:KeyCap E + "互动" 半透明 chip。"""
	_e_prompt = HBoxContainer.new()
	_e_prompt.add_theme_constant_override("separation", 6)
	_e_prompt.visible = false
	_e_prompt.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_e_prompt.position = Vector2(-50, -200)  # 比 whisper 更高

	var key_cap = KeyCapScene.instantiate()
	key_cap.text = "E"
	_e_prompt.add_child(key_cap)

	var label := Label.new()
	label.text = "互动"
	label.add_theme_font_override("font", ChromeTheme.font_serif(500))
	label.add_theme_font_size_override("font_size", 13)
	label.add_theme_color_override("font_color", ChromeTheme.COLOR_DEEP_INK)
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER

	var label_panel := PanelContainer.new()
	label_panel.add_theme_stylebox_override("panel", ChromeTheme.make_parchment_floating(0.9))
	label_panel.add_child(label)
	_e_prompt.add_child(label_panel)

	add_child(_e_prompt)


func _whisper_text() -> String:
	"""组合 hover whisper 文本:"name · action 摘要"。"""
	var a: Dictionary = GameWorld.get_agent(agent_id)
	var display_name: String = a.get("display_name", agent_id)
	var action_summary: String = _current_action_text
	if action_summary == "":
		# 没在做事 → 用 persona role 当 fallback (设计稿 main-screen.jsx 137 行)
		action_summary = a.get("current_mood", "...")
	return "%s  ·  %s" % [display_name, action_summary]


## LocationView 在 _process 中调用 — 玩家距离 <140px 时 show=true
func set_hover_whisper(should_show: bool) -> void:
	if _hover_whisper == null:
		return
	if should_show:
		_hover_whisper_label.text = _whisper_text()
		_hover_whisper.visible = true
	else:
		_hover_whisper.visible = false


## LocationView 调用 — 距离 <110px **且**为最近 NPC 时 show=true
func set_e_prompt(should_show: bool) -> void:
	if _e_prompt == null:
		return
	_e_prompt.visible = should_show
