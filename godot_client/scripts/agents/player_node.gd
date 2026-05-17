extends Node2D

# preload 保证不依赖 .godot/global_script_class_cache.cfg(被 .gitignore)
const ChromeTheme := preload("res://scripts/ui/chrome_theme.gd")

var _speech_panel: PanelContainer = null
var _speech_label: Label = null
var _speech_timer: SceneTreeTimer = null

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

## F2 边界切场所:玩家撞边界 + 推该方向键 N 秒后触发切场所
var _boundary_press_time: float = 0.0
const _BOUNDARY_TRIGGER_SEC: float = 1.0
# 边界提示浮气泡(动态创建)
var _boundary_hint_panel: PanelContainer = null
var _boundary_hint_label: Label = null


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

	# F2 边界提示浮气泡(羊皮纸 + 旧橡木墨边)
	_build_boundary_hint()
	# F2 打招呼气泡(玩家说"你好,XX"用)
	_build_speech_bubble()


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

	# F2 边界切场所:撞到边界 + 朝该方向继续推 → 累计 0.35 秒后切下一场所
	_check_boundary_transition(dx, dy, delta)


func _check_boundary_transition(dx: float, dy: float, delta: float) -> void:
	"""玩家撞边界 + 仍朝该方向推 → 切到下一场所。"""
	var boundary_dir: String = ""
	if position.x <= BOUND_X_MIN + 0.5 and dx < 0:
		boundary_dir = "w"
	elif position.x >= BOUND_X_MAX - 0.5 and dx > 0:
		boundary_dir = "e"
	elif position.y <= BOUND_Y_MIN + 0.5 and dy < 0:
		boundary_dir = "n"
	elif position.y >= BOUND_Y_MAX - 0.5 and dy > 0:
		boundary_dir = "s"

	# 不在边界 → 隐藏提示 + 重置计时
	if boundary_dir == "":
		_boundary_press_time = 0.0
		_hide_boundary_hint()
		return

	# 查目标场所名
	var target: String = _get_exit_target(boundary_dir)
	if target == "":
		# 该方向没有出口(如 plaza 西边酒馆未实装)
		_boundary_press_time = 0.0
		_show_boundary_hint("× 此方向暂无出口", 1.0)
		return

	# 显示边界提示("→ 寂塔遗迹  · 继续推 0.X 秒"),实时更新进度
	_boundary_press_time += delta
	var remaining: float = max(0.0, _BOUNDARY_TRIGGER_SEC - _boundary_press_time)
	var target_loc: Dictionary = GameWorld.get_location(target)
	var target_name: String = target_loc.get("name", target)
	if remaining > 0.0:
		_show_boundary_hint(
			"→ %s    · 继续推 %.1fs" % [target_name, remaining],
			remaining / _BOUNDARY_TRIGGER_SEC
		)
		return

	# 触发切场所
	print("[player] boundary %s → switch_view_to(%s)" % [boundary_dir, target])
	_hide_boundary_hint()
	GameWorld.switch_view_to(target)
	_boundary_press_time = 0.0


func _build_boundary_hint() -> void:
	"""边界推方向键时浮现的提示气泡 — 显示目标场所 + 倒计时。"""
	_boundary_hint_panel = PanelContainer.new()
	_boundary_hint_panel.add_theme_stylebox_override("panel", ChromeTheme.make_parchment_floating(0.92))
	_boundary_hint_panel.visible = false
	_boundary_hint_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_boundary_hint_panel.position = Vector2(-130, -220)  # 头顶上方,比 YOU 更高
	_boundary_hint_panel.size = Vector2(260, 0)

	_boundary_hint_label = Label.new()
	_boundary_hint_label.add_theme_font_override("font", ChromeTheme.font_serif(600))
	_boundary_hint_label.add_theme_font_size_override("font_size", 14)
	_boundary_hint_label.add_theme_color_override("font_color", ChromeTheme.COLOR_DEEP_INK)
	_boundary_hint_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_boundary_hint_panel.add_child(_boundary_hint_label)

	add_child(_boundary_hint_panel)


func _show_boundary_hint(text: String, _progress: float = 0.0) -> void:
	if _boundary_hint_panel == null:
		return
	_boundary_hint_label.text = text
	_boundary_hint_panel.visible = true


func _hide_boundary_hint() -> void:
	if _boundary_hint_panel != null:
		_boundary_hint_panel.visible = false


# ----------------------------------------------------- 玩家说话气泡

func _build_speech_bubble() -> void:
	"""玩家头顶说话气泡(对话 stub 用)。"""
	_speech_panel = PanelContainer.new()
	_speech_panel.add_theme_stylebox_override("panel", ChromeTheme.make_parchment_floating(0.92))
	_speech_panel.visible = false
	_speech_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_speech_panel.position = Vector2(-110, -180)
	_speech_panel.size = Vector2(220, 0)

	_speech_label = Label.new()
	_speech_label.add_theme_font_override("font", ChromeTheme.font_serif(500))
	_speech_label.add_theme_font_size_override("font_size", 14)
	_speech_label.add_theme_color_override("font_color", ChromeTheme.COLOR_DEEP_INK)
	_speech_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_speech_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_speech_panel.add_child(_speech_label)

	add_child(_speech_panel)


func show_speech(text: String, duration: float = 0.0) -> void:
	"""玩家头顶气泡说话,duration 秒后自动隐藏。
	duration=0 用字数自适应(对照 AgentNode.show_speech_line:max(4, 字数×0.18))"""
	if _speech_panel == null:
		return
	if duration <= 0.0:
		duration = max(3.0, float(text.length()) * 0.18)
	_speech_label.text = text
	_speech_panel.visible = true
	_speech_timer = get_tree().create_timer(duration)
	var snapshot := _speech_timer
	var snapshot_text := text
	snapshot.timeout.connect(func() -> void:
		# 仅在没被新台词覆盖时才隐藏
		if _speech_timer == snapshot and _speech_label.text == snapshot_text:
			_speech_panel.visible = false
	)


func _get_exit_target(direction: String) -> String:
	"""按当前场所 + 方向决定出口目的地。
	老松广场:N→北霜 / S→暖谷 / E→寂塔 / W→暂无(酒馆未实装)
	其他场所:任意方向 → 回老松广场(adjacent_to 唯一)。"""
	var loc_id: String = GameWorld.current_view_location
	if loc_id == "lao_song_plaza":
		match direction:
			"n": return "north_frost_workshop"
			"s": return "warm_valley_farm"
			"e": return "silent_tower_ruins"
			_:   return ""  # 西边酒馆未实装
	# 其他 3 个场所:回 plaza
	var adjacents: Array = GameWorld.get_location(loc_id).get("adjacent_to", [])
	if adjacents.is_empty():
		return ""
	return adjacents[0]


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
	# Eric 反馈:艾琳素材中 walk_e.png 实际是朝 W,walk_w.png 实际朝 E。
	# 这里交换文件名映射,不动 _facing 内部状态(GameWorld.player_facing 仍正确)。
	var sprite_dir: String = _facing
	if _facing == "e":
		sprite_dir = "w"
	elif _facing == "w":
		sprite_dir = "e"
	var candidates := [
		"res://assets/characters/%s/walk_%s.png" % [aid, sprite_dir],
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
