extends Node2D

## 单个 agent 在场景里的可视节点。LocationView 在 agent 进入本场所时 instantiate。
##
## 视觉构成:
##   PlaceholderRect — 缺 sprite 时的色块兜底
##   Sprite          — 有 walk_*.png 时显示
##   NameLabel       — 头顶显示中文名
##   ActionLabel     — 脚下显示当前 action_type 与 args 摘要
##   ThinkingIndicator — 头顶上方,思考时显示 💭

@export var agent_id: String = ""

@onready var placeholder_rect: ColorRect = $PlaceholderRect
@onready var sprite: Sprite2D = $Sprite
@onready var name_label: Label = $NameLabel
@onready var action_label: Label = $ActionLabel
@onready var thinking_indicator: Label = $ThinkingIndicator
@onready var speech_bubble: PanelContainer = $SpeechBubble
@onready var speech_label: Label = $SpeechBubble/SpeechLabel

var _has_sprite: bool = false
var _speech_hide_timer: SceneTreeTimer = null


func _ready() -> void:
	if agent_id == "":
		push_warning("[AgentNode] agent_id is empty")
		return

	_apply_persona_visuals()
	_apply_initial_action_label()


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
		action_label.text = ""
		return
	action_label.text = _format_action_label(current_action)


# ----------------------------------------------------- event handlers
# 这些方法由 LocationView 主动调用(它从 GameWorld signal 接到事件后转发)

func on_action_started(action: Dictionary) -> void:
	action_label.text = _format_action_label(action)
	# 移动动作:按 args.location 切换朝向贴图
	if action.get("action_type", "") == "move_to":
		_face_for_direction("s")  # 占位:默认朝南。后续可按 from/to 算


func on_action_completed(_action: Dictionary) -> void:
	action_label.text = ""


func on_thinking_started() -> void:
	thinking_indicator.visible = true


func on_thinking_completed(_appended_count: int) -> void:
	thinking_indicator.visible = false


# ------------------------------------------------------- dialogue speech

## 显示一句台词,3 秒后自动隐藏(如果没有新台词覆盖)。
## 由 LocationView 接到 GameWorld.dialogue_line signal 后转发。
func show_speech_line(text: String, duration_seconds: float = 3.0) -> void:
	speech_label.text = text
	speech_bubble.visible = true
	# 取消旧 timer,重置 3 秒
	# SceneTreeTimer 没有 cancel,但旧 timer 触发时检查 text 是否已变即可
	var snapshot_text := text
	var t := get_tree().create_timer(duration_seconds)
	_speech_hide_timer = t
	t.timeout.connect(func() -> void:
		# 仅在没有更新过台词时才隐藏
		if speech_label.text == snapshot_text:
			speech_bubble.visible = false
	)


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
