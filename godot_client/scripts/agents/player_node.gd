extends Node2D

# preload 保证不依赖 .godot/global_script_class_cache.cfg(被 .gitignore)
const ChromeTheme := preload("res://scripts/ui/chrome_theme.gd")

## F2 玩家节点(扮演艾琳)— LocationView 实例化的唯一玩家可控角色。
##
## 视觉:艾琳 sprite + 头顶 "YOU" 标签 + 暖色 drop-shadow
## 控制:WASD 移动,250 px/sec(对照设计稿 main-screen.jsx 0.25 px/ms),朝向跟随移动方向
## 边界:[60, 1220] × [380, 680](保留 HUD 安全区,设计稿一致)
##
## 注意:GameWorld.player_x/y/facing 同步更新,F4 阶段后端反射玩家位置。

const MOVE_SPEED_PX_PER_SEC: float = 250.0

const BOUND_X_MIN: float = 60.0
const BOUND_X_MAX: float = 1220.0
const BOUND_Y_MIN: float = 380.0
const BOUND_Y_MAX: float = 680.0

@onready var sprite: Sprite2D = $Sprite
@onready var shadow: ColorRect = $Shadow
@onready var you_label: Label = $YouLabel

var _facing: String = "s"
var _move_blocked: bool = false  # F3 BubbleMenu 弹出时由外部置 true,锁住移动


func _ready() -> void:
	# 初始位置从 GameWorld(跨 LocationView 持久)
	position = Vector2(GameWorld.player_x, GameWorld.player_y)
	_facing = GameWorld.player_facing
	_apply_facing_sprite()

	# 头顶 YOU 标签:Plex Mono 9px 字距 0.18em 暖白
	you_label.add_theme_font_override("font", ChromeTheme.font_mono(600))
	you_label.add_theme_font_size_override("font_size", 9)
	you_label.add_theme_color_override("font_color", Color(0.96, 0.92, 0.78, 0.85))
	you_label.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.6))
	you_label.add_theme_constant_override("outline_size", 2)
	you_label.text = "Y O U"
	you_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER

	# 玩家点击不响应(玩家自己不能对自己用 E)
	mouse_filter_recursive(self)


func _process(delta: float) -> void:
	if _move_blocked:
		return
	var dx: float = 0.0
	var dy: float = 0.0
	if Input.is_key_pressed(KEY_W) or Input.is_key_pressed(KEY_UP):
		dy -= 1.0
	if Input.is_key_pressed(KEY_S) or Input.is_key_pressed(KEY_DOWN):
		dy += 1.0
	if Input.is_key_pressed(KEY_A) or Input.is_key_pressed(KEY_LEFT):
		dx -= 1.0
	if Input.is_key_pressed(KEY_D) or Input.is_key_pressed(KEY_RIGHT):
		dx += 1.0
	if dx == 0.0 and dy == 0.0:
		return

	# 标准化(对角线不超速)
	var length: float = sqrt(dx * dx + dy * dy)
	dx /= length
	dy /= length

	var new_x: float = clampf(position.x + dx * MOVE_SPEED_PX_PER_SEC * delta, BOUND_X_MIN, BOUND_X_MAX)
	var new_y: float = clampf(position.y + dy * MOVE_SPEED_PX_PER_SEC * delta, BOUND_Y_MIN, BOUND_Y_MAX)
	position = Vector2(new_x, new_y)

	# 朝向跟随移动方向(主轴)
	var new_facing: String = _facing
	if abs(dx) > abs(dy):
		new_facing = "e" if dx > 0.0 else "w"
	else:
		new_facing = "s" if dy > 0.0 else "n"
	if new_facing != _facing:
		_facing = new_facing
		_apply_facing_sprite()

	# 同步全局状态(F4 后端反射 / F3 exit zone 检测都依赖)
	GameWorld.player_x = position.x
	GameWorld.player_y = position.y
	GameWorld.player_facing = _facing

	# z_index 跟 y 走(前后遮挡)
	z_index = int(position.y) + 1


## 切场所时由 LocationView 调用,跳过 WASD 处理一帧 + 重置位置
func reset_to(x: float, y: float, facing: String = "s") -> void:
	position = Vector2(x, y)
	_facing = facing
	GameWorld.player_x = x
	GameWorld.player_y = y
	GameWorld.player_facing = facing
	_apply_facing_sprite()


func set_move_blocked(blocked: bool) -> void:
	_move_blocked = blocked


func _apply_facing_sprite() -> void:
	# 尝试加载艾琳 walk_{facing}.png,失败则 idle.png 兜底
	var aid: String = GameWorld.player_agent_id
	if aid == "":
		aid = "agent_04"
	var candidates := [
		"res://assets/characters/%s/walk_%s.png" % [aid, _facing],
		"res://assets/characters/%s/idle.png" % aid,
		"res://assets/characters/%s/walk_s.png" % aid,
	]
	var loaded: Texture2D = null
	for path in candidates:
		if ResourceLoader.exists(path):
			loaded = load(path) as Texture2D
			if loaded != null:
				break
	if loaded == null:
		# 兜底色块(粉色)— 不应发生,因为艾琳有完整素材
		sprite.visible = false
		return
	sprite.texture = loaded
	# 缩放到约 120 像素高(对齐 AgentNode)
	var orig_h: float = loaded.get_height()
	if orig_h > 0.0:
		sprite.scale = Vector2(120.0 / orig_h, 120.0 / orig_h)
	sprite.visible = true


## 让所有子控件(Label / Sprite)不响应鼠标(玩家自己不能被点击)
func mouse_filter_recursive(node: Node) -> void:
	if node is Control:
		(node as Control).mouse_filter = Control.MOUSE_FILTER_IGNORE
	for child in node.get_children():
		mouse_filter_recursive(child)
