extends Node2D

## 主场景:管理当前 LocationView 的加载切换 + HUD 联动。
##
## 启动顺序:
## 1. _ready:连接 GameWorld signal,等待 world_initialized
## 2. world_initialized 到达:把 GameWorld.current_view_location 对应场所加载进来
## 3. 用户按 1/2/3/4 切场所;按 R 刷新右侧 inspector

const LOCATION_SCENES := {
	"lao_song_plaza":        preload("res://scenes/locations/LaoSongPlaza.tscn"),
	"north_frost_workshop":  preload("res://scenes/locations/NorthFrostWorkshop.tscn"),
	"warm_valley_farm":      preload("res://scenes/locations/WarmValleyFarm.tscn"),
	"silent_tower_ruins":    preload("res://scenes/locations/SilentTowerRuins.tscn"),
}

# F1 新 HUD 控件类型 preload(保证不依赖 .godot/ class_name cache)
const ChromeTheme := preload("res://scripts/ui/chrome_theme.gd")
const WoodClock := preload("res://scripts/ui/wood_clock.gd")
const LocationLabel := preload("res://scripts/ui/location_label.gd")
const KeyHints := preload("res://scripts/ui/key_hints.gd")
const PausedChip := preload("res://scripts/ui/paused_chip.gd")

# F2 BubbleMenu(E 互动气泡)
const BubbleMenuScene := preload("res://scenes/ui/BubbleMenu.tscn")

# F3 modal scenes
const LocationCardScene := preload("res://scenes/ui/LocationCard.tscn")
const SystemMenuScene := preload("res://scenes/ui/SystemMenu.tscn")

# F4.2 modal scenes
const InnerHeartScene := preload("res://scenes/ui/InnerHeart.tscn")
const RelationshipNetworkScene := preload("res://scenes/ui/RelationshipNetwork.tscn")

@onready var location_container: Node2D = $LocationContainer
@onready var time_label: Label = $HUD/TimePanel/TimeLabel
@onready var connection_dot: Label = $HUD/TimePanel/ConnectionDot
@onready var nav_label: Label = $HUD/NavLabel
# Inspector / MemoryPanel 在 Main.tscn 里是 ColorRect(半透明背景);
# 这里用 Control 基类引用,避免类型不匹配
@onready var inspector_panel: Control = $HUD/Inspector
@onready var inspector_title: Label = $HUD/Inspector/Title
@onready var inspector_list: VBoxContainer = $HUD/Inspector/Scroll/AgentList
@onready var memory_panel: Control = $HUD/MemoryPanel
@onready var memory_title: Label = $HUD/MemoryPanel/Title
@onready var memory_content: RichTextLabel = $HUD/MemoryPanel/Content
@onready var pause_button: Button = $HUD/PausePanel/PauseButton
@onready var loading_overlay: ColorRect = $HUD/LoadingOverlay
@onready var loading_progress: Label = $HUD/LoadingOverlay/Progress
@onready var reflection_label: Label = $HUD/ReflectionPanel/ReflectionLabel
@onready var dialogue_label: Label = $HUD/ReflectionPanel/DialogueLabel
@onready var btn_filter_all: Button = $HUD/MemoryPanel/FilterBar/BtnAll
@onready var btn_filter_reflection: Button = $HUD/MemoryPanel/FilterBar/BtnReflection
@onready var btn_filter_observation: Button = $HUD/MemoryPanel/FilterBar/BtnObservation
@onready var btn_filter_plan: Button = $HUD/MemoryPanel/FilterBar/BtnPlan
@onready var cost_hint: Label = $HUD/PausePanel/CostHint

# F1 新 HUD 控件(羊皮纸 / 木板风,设计稿 main-screen.jsx)
@onready var wood_clock: WoodClock = $HUD/WoodClock
@onready var location_label: LocationLabel = $HUD/LocationLabel
@onready var key_hints: KeyHints = $HUD/KeyHints
@onready var paused_chip: PausedChip = $HUD/PausedChip

# F2 BubbleMenu 单实例(挂在 HUD 上,弹出时锁玩家移动)
var _bubble_menu: Control = null

# F2 边界提示(玩家撞边界 + 推方向时浮现,固定在 WoodClock 下方)
var _boundary_hint: PanelContainer = null
var _boundary_hint_label: Label = null

# F3 modal 单实例(同时只允许一个 modal,Q/Esc 互斥)
var _location_card: Control = null
var _system_menu: Control = null

# F4.2 InnerHeart modal
var _inner_heart: Control = null

# F4.3 RelationshipNetwork modal
var _relationship_network: Control = null

var _current_view: Node2D = null
var _selected_agent_id: String = ""
# memory filter: "all" / "reflection" / "observation" / "plan"
var _memory_filter: String = "all"
var _memory_cache: Array = []  # 最近一次拉到的 raw memories,切 tab 时直接重渲
var _health_poll_timer: float = 0.0
const _HEALTH_POLL_INTERVAL := 5.0


func _ready() -> void:
	print("[main] Block-7 Sim — Block H Godot 端启动")

	GameWorld.world_initialized.connect(_on_world_initialized)
	GameWorld.location_switched.connect(_on_location_switched)
	GameWorld.sim_ticked.connect(_on_sim_ticked)
	GameWorld.connection_changed.connect(_on_connection_changed)
	GameWorld.paused_changed.connect(_on_paused_changed)
	GameWorld.agent_started_action.connect(_on_agent_action_changed)
	GameWorld.agent_completed_action.connect(_on_agent_action_changed)
	GameWorld.agent_moved.connect(_on_agent_moved_anywhere)
	GameWorld.agent_thinking_started.connect(_on_agent_thinking_changed)
	GameWorld.agent_thinking_completed.connect(_on_agent_thinking_changed2)
	GameWorld.warmup_progress.connect(_on_warmup_progress)
	GameWorld.daily_reflection_started.connect(_on_daily_reflection_started)
	GameWorld.daily_reflection_completed.connect(_on_daily_reflection_completed)
	GameWorld.agent_clicked.connect(_show_agent_memories)  # 点 sprite 直接弹 memory
	pause_button.pressed.connect(_on_pause_button_pressed)
	btn_filter_all.pressed.connect(func() -> void: _set_memory_filter("all"))
	btn_filter_reflection.pressed.connect(func() -> void: _set_memory_filter("reflection"))
	btn_filter_observation.pressed.connect(func() -> void: _set_memory_filter("observation"))
	btn_filter_plan.pressed.connect(func() -> void: _set_memory_filter("plan"))

	_update_nav_label()
	_update_time_label()
	_update_connection_dot(false)
	_update_pause_button()
	_update_loading_overlay()
	memory_panel.visible = false

	# F1 新 HUD 初始化
	_update_wood_clock()
	_update_location_label()
	key_hints.hints = KeyHints.default_hints_v02()
	paused_chip.visible = false

	# F2 边界提示(挂 HUD,默认隐藏)
	_build_boundary_hint()
	GameWorld.boundary_hint_changed.connect(_on_boundary_hint_changed)

	# F4.1 玩家发起对话的 WS 回流(NPC 那一句由 LocationView 接,玩家那一句由这里接)
	GameWorld.dialogue_line.connect(_on_dialogue_line_for_player)


func _on_world_initialized(_world: Dictionary) -> void:
	# 第一次或重连时灌入了 world,加载默认场所
	_switch_location_view(GameWorld.current_view_location)
	_refresh_inspector()
	_update_location_label()
	_update_loading_overlay()


func _on_location_switched(new_location_id: String) -> void:
	_switch_location_view(new_location_id)
	_refresh_inspector()
	_clear_memory_panel()
	_update_location_label()


func _switch_location_view(location_id: String) -> void:
	# 卸载旧场景
	if _current_view != null:
		_current_view.queue_free()
		_current_view = null

	# 加载新场景
	if not LOCATION_SCENES.has(location_id):
		push_warning("[main] no scene for location: %s" % location_id)
		return
	var scene: PackedScene = LOCATION_SCENES[location_id]
	_current_view = scene.instantiate()
	location_container.add_child(_current_view)
	_update_nav_label()


func _on_sim_ticked(_game_time: float) -> void:
	_update_time_label()
	_update_wood_clock()


func _on_connection_changed(connected: bool) -> void:
	_update_connection_dot(connected)
	_update_loading_overlay()


func _on_paused_changed(paused: bool) -> void:
	_update_pause_button()
	_update_loading_overlay()
	paused_chip.visible = paused


func _on_pause_button_pressed() -> void:
	# 翻转当前 paused 状态;真正状态变化通过 WS paused_changed 事件回来更新按钮
	BackendClient.set_sim_paused(not GameWorld.paused)
	# 即时反馈:按钮文字暂时显示"切换中"
	pause_button.text = "...切换中..."
	pause_button.disabled = true
	# 1.5 秒后无论是否收到事件都恢复按钮可点击,防止 stuck
	get_tree().create_timer(1.5).timeout.connect(func() -> void:
		pause_button.disabled = false
		_update_pause_button()
	)


func _update_pause_button() -> void:
	if GameWorld.paused:
		pause_button.text = "▶ 开始(暂停中)"
		pause_button.modulate = Color(0.6, 1.0, 0.6, 1)
	else:
		pause_button.text = "⏸ 暂停(运行中)"
		pause_button.modulate = Color(1.0, 0.9, 0.5, 1)


# ----------------------------------------------------- cost polling

func _process(delta: float) -> void:
	"""每 _HEALTH_POLL_INTERVAL 秒拉 /sim/health 更新成本显示。"""
	if not GameWorld.is_connected_to_backend():
		return
	_health_poll_timer += delta
	if _health_poll_timer < _HEALTH_POLL_INTERVAL:
		return
	_health_poll_timer = 0.0
	BackendClient.fetch_sim_health(_on_health_received)


func _on_health_received(data: Dictionary) -> void:
	if data.is_empty():
		return
	var llm: Dictionary = data.get("llm", {})
	var total_cost: float = float(llm.get("total_cost_yuan", 0.0))
	var uptime: float = float(data.get("uptime_seconds", 0.0))
	var rate_per_min: float = 0.0
	if uptime > 1.0:
		rate_per_min = total_cost * 60.0 / uptime
	var cache_hit: float = float(llm.get("cache_hit_rate", 0.0))
	cost_hint.text = "¥%.3f\n%.2f/min\n命中 %d%%" % [
		total_cost, rate_per_min, int(cache_hit * 100)
	]
	# Block I 对话统计
	var dlg: Dictionary = data.get("dialogue", {})
	var sessions: int = int(dlg.get("total_sessions_started", 0))
	var lines: int = int(dlg.get("total_lines", 0))
	var active: int = int(dlg.get("active_sessions", 0))
	if active > 0:
		dialogue_label.text = "💬 对话: %d 场(%d 句)· %d 进行中" % [sessions, lines, active]
	else:
		dialogue_label.text = "💬 对话: %d 场(%d 句)" % [sessions, lines]


# ----------------------------------------------------- loading overlay

func _on_warmup_progress(ready_count: int, total: int) -> void:
	loading_progress.text = "等待 agent 完成首轮思考...  %d / %d" % [ready_count, total]
	if GameWorld.is_warmup_complete():
		loading_overlay.visible = false


# ----------------------------------------------------- reflection

func _on_daily_reflection_started(game_day: int, agent_count: int) -> void:
	reflection_label.text = "🌒 Day %d 反思中... (%d agent)" % [game_day, agent_count]
	reflection_label.modulate = Color(1.0, 0.9, 0.6, 1.0)


func _on_daily_reflection_completed(
	game_day: int, reflection_count: int, _merged: int, _archived: int, cost_yuan: float
) -> void:
	reflection_label.text = "⭐ 反思: %d 条 / 最近 Day %d (¥%.3f)" % [
		GameWorld.total_reflections, game_day, cost_yuan
	]
	reflection_label.modulate = Color(0.85, 0.78, 1.0, 1.0)


func _update_loading_overlay() -> void:
	"""根据当前状态显示/隐藏 LoadingOverlay。
	已预热完成 → 隐藏;否则按 paused 状态显示不同提示。"""
	if GameWorld.is_warmup_complete():
		loading_overlay.visible = false
		return
	loading_overlay.visible = true
	if not GameWorld.is_connected_to_backend():
		loading_progress.text = "等待 backend 连接..."
	elif GameWorld.paused:
		loading_progress.text = "暂停中 — 按 Tab 启动预热"
	else:
		var ready: int = GameWorld._ready_agents.size()
		var total: int = GameWorld.agents.size()
		loading_progress.text = "等待 agent 完成首轮思考...  %d / %d" % [ready, total]


# ----------------------------------------------------- input

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("view_lao_song_plaza"):
		GameWorld.switch_view_to("lao_song_plaza")
	elif event.is_action_pressed("view_north_frost_workshop"):
		GameWorld.switch_view_to("north_frost_workshop")
	elif event.is_action_pressed("view_warm_valley_farm"):
		GameWorld.switch_view_to("warm_valley_farm")
	elif event.is_action_pressed("view_silent_tower_ruins"):
		GameWorld.switch_view_to("silent_tower_ruins")
	elif event is InputEventKey and event.pressed and event.keycode == KEY_R and not event.echo:
		# F4.3: R 关系网(原 KEY_R 是旧 inspector 刷新,inspector 已 visible=false)
		get_viewport().set_input_as_handled()
		_toggle_relationship_network()
	elif event is InputEventKey and event.pressed and event.keycode == KEY_TAB and not event.echo:
		# F1: Tab 切换暂停状态(等价旧 PauseButton)
		get_viewport().set_input_as_handled()
		BackendClient.set_sim_paused(not GameWorld.paused)
	elif event is InputEventKey and event.pressed and event.keycode == KEY_E and not event.echo:
		# F2: E 互动 — 走近 NPC 弹气泡菜单(只在 INTERACT_RADIUS 内才响应)
		get_viewport().set_input_as_handled()
		_try_open_bubble_menu()
	elif event is InputEventKey and event.pressed and event.keycode == KEY_F11 and not event.echo:
		# F2: F11 切全屏
		get_viewport().set_input_as_handled()
		_toggle_fullscreen()
	elif event is InputEventKey and event.pressed and event.keycode == KEY_Q and not event.echo:
		# F3: Q 场所概览
		get_viewport().set_input_as_handled()
		_toggle_location_card()
	elif event is InputEventKey and event.pressed and event.keycode == KEY_ESCAPE and not event.echo:
		# F3: Esc 系统菜单
		get_viewport().set_input_as_handled()
		_toggle_system_menu()
	elif event is InputEventKey and event.pressed and event.keycode == KEY_F and not event.echo:
		# F4.2: F 读自己的心
		get_viewport().set_input_as_handled()
		_toggle_inner_heart()


func _toggle_fullscreen() -> void:
	var current: int = DisplayServer.window_get_mode()
	if current == DisplayServer.WINDOW_MODE_FULLSCREEN or current == DisplayServer.WINDOW_MODE_EXCLUSIVE_FULLSCREEN:
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_MAXIMIZED)
	else:
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN)


# ------------------------------------------------------- HUD updates

func _update_time_label() -> void:
	# 预热期间显示占位,避免给用户"时间却仍在流动"的认知冲突
	if not GameWorld.is_warmup_complete():
		if GameWorld.paused:
			time_label.text = "Day --, --:--"
		else:
			time_label.text = "Day --, 预热中"
		return
	var gt: float = GameWorld.game_time
	var seconds_per_day: float = 86400.0
	var day: int = int(gt / seconds_per_day) + 1
	var seconds_today: float = fmod(gt, seconds_per_day)
	var hour: int = int(seconds_today / 3600.0)
	# 加速模式 (time_scale ≥ 600, 即 1 现实秒 ≥ 10 游戏分钟) 下 minute 字段
	# 跳变太快没有信息价值,只显示 hour
	if GameWorld.time_scale >= 600.0:
		time_label.text = "Day %d, %02d:00" % [day, hour]
	else:
		var minute: int = int(fmod(seconds_today, 3600.0) / 60.0)
		time_label.text = "Day %d, %02d:%02d" % [day, hour, minute]


func _update_connection_dot(connected: bool) -> void:
	if connected:
		connection_dot.text = "● 已连接"
		connection_dot.modulate = Color(0.4, 0.95, 0.5, 1)
	else:
		connection_dot.text = "● 未连接"
		connection_dot.modulate = Color(0.95, 0.4, 0.4, 1)


func _update_nav_label() -> void:
	var current_id: String = GameWorld.current_view_location
	var current_loc: Dictionary = GameWorld.get_location(current_id)
	var current_name: String = current_loc.get("name", current_id)
	nav_label.text = "[当前] %s    切换:[1] 老松广场  [2] 北霜工坊  [3] 暖谷农场  [4] 寂塔遗迹    [R] 刷新" % current_name


# ----------------------------------------------------- inspector

func _on_agent_action_changed(_agent_id: String, _action: Dictionary) -> void:
	_refresh_inspector()


func _on_agent_moved_anywhere(_agent_id: String, _from: String, _to: String) -> void:
	_refresh_inspector()


func _on_agent_thinking_changed(_agent_id: String) -> void:
	_refresh_inspector()


func _on_agent_thinking_changed2(_agent_id: String, _appended_count: int) -> void:
	_refresh_inspector()


func _refresh_inspector() -> void:
	"""更新右侧 inspector:展示"当前场所有谁 + 各自正在做什么"。"""
	var location_id: String = GameWorld.current_view_location
	var loc: Dictionary = GameWorld.get_location(location_id)
	var loc_name: String = loc.get("name", location_id)
	var agents: Array = GameWorld.get_agents_in_location(location_id)
	inspector_title.text = "「%s」%d 人在此" % [loc_name, agents.size()]

	# 清空旧列表
	for child in inspector_list.get_children():
		child.queue_free()

	for a in agents:
		var btn := Button.new()
		btn.flat = false
		btn.alignment = HORIZONTAL_ALIGNMENT_LEFT
		var thinking: bool = false  # 暂存,无法直接知道
		var action = a.get("current_action")
		var action_text: String = "..."
		if action != null and typeof(action) == TYPE_DICTIONARY:
			action_text = _format_action_summary(action)
		btn.text = "%s  · %s" % [a.get("display_name", a.get("agent_id", "?")), action_text]
		btn.add_theme_font_size_override("font_size", 14)
		var aid: String = a.get("agent_id", "")
		btn.pressed.connect(func() -> void: _show_agent_memories(aid))
		inspector_list.add_child(btn)


func _format_action_summary(action: Dictionary) -> String:
	var a_type: String = action.get("action_type", "?")
	var args: Dictionary = action.get("args", {})
	match a_type:
		"move_to":
			return "→ " + str(args.get("location", "?"))
		"work":
			return "工作:" + str(args.get("task", "..."))
		"rest":
			return "休息"
		"observe":
			return "观察:" + str(args.get("target", "?"))
		"interact":
			return "互动:" + str(args.get("target", "?"))
		"talk_to":
			return "说话→" + str(args.get("agent_id", "?"))
		"idle":
			return "..."
		_:
			return a_type


# ----------------------------------------------------- memory panel

func _show_agent_memories(agent_id: String) -> void:
	_selected_agent_id = agent_id
	_memory_cache = []
	var a: Dictionary = GameWorld.get_agent(agent_id)
	memory_title.text = "%s · 最近 20 条" % a.get("display_name", agent_id)
	memory_panel.visible = true
	memory_content.text = "[正在拉取...]"

	BackendClient.fetch_agent_memories(agent_id, 20, func(memories: Array) -> void:
		if _selected_agent_id != agent_id:
			return  # 已切到别人
		_memory_cache = memories
		_render_memory_content()
	)


func _set_memory_filter(filter: String) -> void:
	_memory_filter = filter
	# 同步 toggle 状态(其它 button 取消)
	btn_filter_all.button_pressed = (filter == "all")
	btn_filter_reflection.button_pressed = (filter == "reflection")
	btn_filter_observation.button_pressed = (filter == "observation")
	btn_filter_plan.button_pressed = (filter == "plan")
	_render_memory_content()


func _render_memory_content() -> void:
	"""按 _memory_filter 渲染 _memory_cache 到 memory_content。"""
	if _memory_cache.is_empty():
		memory_content.text = "[无记忆]"
		return

	# 应用 filter
	var filtered: Array = _memory_cache
	if _memory_filter != "all":
		filtered = []
		for m in _memory_cache:
			if m.get("memory_type") == _memory_filter:
				filtered.append(m)
	if filtered.is_empty():
		memory_content.text = "[此分类下无记忆]"
		return

	# all 模式:反思单独分组放前面
	if _memory_filter == "all":
		var reflections: Array = []
		var others: Array = []
		for m in filtered:
			if m.get("memory_type") == "reflection":
				reflections.append(m)
			else:
				others.append(m)
		var lines: PackedStringArray = []
		if not reflections.is_empty():
			lines.append("[color=#c8b8e2][b]🌒 反思(%d 条)[/b][/color]" % reflections.size())
			for m in reflections:
				var imp: int = int(m.get("importance", 0))
				var content: String = str(m.get("content", "")).replace("\n", " ")
				lines.append("[color=#c8b8e2]· [imp=%d] %s[/color]" % [imp, content])
			lines.append("")
			lines.append("[color=#777777]── 观察 / 计划 ──[/color]")
		for m in others:
			lines.append(_format_memory_line(m))
		memory_content.text = "\n\n".join(lines)
	else:
		# 单类型 filter:直接按时间顺序铺开
		var lines2: PackedStringArray = []
		for m in filtered:
			lines2.append(_format_memory_line(m))
		memory_content.text = "\n\n".join(lines2)


func _format_memory_line(m: Dictionary) -> String:
	var mtype: String = m.get("memory_type", "?")
	var imp: int = int(m.get("importance", 0))
	var content: String = str(m.get("content", "")).replace("\n", " ")
	var emoji: String
	var color: String
	match mtype:
		"reflection":
			emoji = "🌒"
			color = "#c8b8e2"
			return "[color=%s]%s [imp=%d] %s[/color]" % [color, emoji, imp, content]
		"plan":
			emoji = "📋"
			color = "#b8c2a8"
		"observation":
			emoji = "👁"
			color = "#a8b3c2"
		_:
			emoji = "?"
			color = "#888888"
	return "[color=%s]%s imp=%d[/color] %s" % [color, emoji, imp, content]


func _clear_memory_panel() -> void:
	_selected_agent_id = ""
	memory_panel.visible = false


# ============================== F1 新 HUD 更新 ==============================

## 把 GameWorld.game_time 映射到 WoodClock 的 day/hour/minute。
## 预热期间显示 Day 1 / 00:00 占位。
func _update_wood_clock() -> void:
	if wood_clock == null:
		return
	if not GameWorld.is_warmup_complete():
		wood_clock.day = 1
		wood_clock.hour = 0
		wood_clock.minute = 0
		return
	var gt: float = GameWorld.game_time
	var seconds_per_day: float = 86400.0
	var day: int = int(gt / seconds_per_day) + 1
	var seconds_today: float = fmod(gt, seconds_per_day)
	var hour: int = int(seconds_today / 3600.0)
	var minute: int = int(fmod(seconds_today, 3600.0) / 60.0)
	wood_clock.day = day
	wood_clock.hour = hour
	wood_clock.minute = minute


## 更新左下场所标:中文 + 英文 + 在场人数。
## 英文名 fallback:location_id underscore → space + 首字母大写。
func _update_location_label() -> void:
	if location_label == null:
		return
	var location_id: String = GameWorld.current_view_location
	if location_id == "":
		return
	var loc: Dictionary = GameWorld.get_location(location_id)
	var cn_name: String = loc.get("name", location_id)
	var en_name: String = loc.get("name_en", _fallback_en_name(location_id))
	var agents: Array = GameWorld.get_agents_in_location(location_id)
	location_label.location_name = cn_name
	location_label.location_name_en = en_name
	location_label.count = agents.size()


## v0.2 阶段右下 KeyHints:除 E 之外的 C/I/J/P/Q/F/Esc 都标 dim(待 v0.3+ 解锁)。
## F2 阶段会根据"是否走近 NPC"动态把 E hint 改为"与 XX 互动"。
func _update_key_hints(e_target_name: String = "") -> void:
	if key_hints == null:
		return
	key_hints.hints = KeyHints.default_hints_v02(e_target_name)


## 没有 name_en 字段时,从 location_id 推一个:lao_song_plaza → Lao Song Plaza
func _fallback_en_name(location_id: String) -> String:
	var parts: Array = location_id.split("_")
	var capitalized: Array = []
	for p in parts:
		var s: String = p
		if s.length() > 0:
			capitalized.append(s.substr(0, 1).to_upper() + s.substr(1))
	return " ".join(capitalized)


# ============================================================================
# F2 E 互动:BubbleMenu 弹出 + 选项处理
# ============================================================================

func _try_open_bubble_menu() -> void:
	"""按 E 时调用。查询当前 LocationView 是否有可互动 NPC,有则弹气泡菜单。"""
	if _bubble_menu != null and is_instance_valid(_bubble_menu):
		return  # 已有菜单
	if _current_view == null or not _current_view.has_method("get_interactable_npc_id"):
		return
	var npc_id: String = _current_view.get_interactable_npc_id()
	if npc_id == "":
		return  # 没靠近任何 NPC

	# 取 NPC 节点 + 名字
	var npc_agent: Dictionary = GameWorld.get_agent(npc_id)
	var npc_name: String = npc_agent.get("display_name", npc_id)
	var npc_node: Node2D = _current_view.get_node_or_null("AgentsContainer/" + npc_id)
	if npc_node == null:
		return

	# 实例化 BubbleMenu + 定位到 NPC 头顶
	var menu = BubbleMenuScene.instantiate()
	$HUD.add_child(menu)
	menu.setup(npc_name)
	# NPC.position 是 LocationView 内坐标(LocationContainer 在 0,0,直接当 viewport 坐标用)
	menu.position = Vector2(npc_node.position.x - 70, npc_node.position.y - 250)
	menu.option_chosen.connect(_on_bubble_option_chosen.bind(npc_id))
	menu.cancelled.connect(_on_bubble_cancelled)
	_bubble_menu = menu

	# 锁住玩家移动
	var player: Node = _current_view.get_player_node() if _current_view.has_method("get_player_node") else null
	if player != null and player.has_method("set_move_blocked"):
		player.set_move_blocked(true)


func _on_bubble_option_chosen(action_id: String, npc_id: String) -> void:
	"""玩家在气泡菜单选了某项。F2 stub 实装(LLM 接入到 v0.4)。"""
	_bubble_menu = null
	_unlock_player()
	match action_id:
		"greet":
			_stub_greet(npc_id)
		"read_mind":
			pass  # disabled,不应到达
		"leave":
			pass  # 直接关菜单


func _stub_greet(npc_id: String) -> void:
	"""F4.1 玩家打招呼 — 调 backend /dialogue/player_greet:
	- 玩家说什么:Godot 端固定 3 句备选(seed 由 game_time)
	- NPC 回复:**真 LLM 生成**(DialogueManager.try_start_player_session)
	- 双方气泡通过 WS dialogue_line 事件流推回前端显示
	"""
	if _current_view == null:
		return
	var npc_agent: Dictionary = GameWorld.get_agent(npc_id)
	var npc_name: String = npc_agent.get("display_name", npc_id)

	# 玩家说什么(F4.1 仍是 3 句固定备选,v0.4 全屏对话 modal 加自由输入)
	var greet_lines: Array = [
		"你好,%s。" % npc_name,
		"嗨,%s。" % npc_name,
		"%s,在忙吗?" % npc_name,
	]
	var seed_int: int = int(GameWorld.game_time) % 100
	var player_line: String = greet_lines[seed_int % greet_lines.size()]

	# 后台调 LLM,WS 推回 dialogue_line 由 _on_player_dialogue_line / LocationView 渲染
	BackendClient.player_greet(npc_id, player_line, func(ok: bool, _sid: String) -> void:
		if not ok:
			push_warning("[interact] player_greet failed for %s" % npc_id)
	)


func _on_dialogue_line_for_player(_session_id: String, speaker_id: String, text: String, _turn_idx: int) -> void:
	"""F4.1: WS dialogue_line 事件 — 如果 speaker 是玩家,显示在 PlayerNode 头顶。
	NPC 的对话气泡由 LocationView._on_dialogue_line → AgentNode.show_speech_line 处理。"""
	if speaker_id != GameWorld.player_agent_id:
		return
	if _current_view == null or not _current_view.has_method("get_player_node"):
		return
	var player_node: Node = _current_view.get_player_node()
	if player_node != null and player_node.has_method("show_speech"):
		player_node.show_speech(text)


func _on_bubble_cancelled() -> void:
	_bubble_menu = null
	_unlock_player()


func _unlock_player() -> void:
	if _current_view == null:
		return
	var player: Node = _current_view.get_player_node() if _current_view.has_method("get_player_node") else null
	if player != null and player.has_method("set_move_blocked"):
		player.set_move_blocked(false)


# ============================================================================
# F2 边界提示(HUD 固定位置,在 WoodClock 下方)
# ============================================================================

func _build_boundary_hint() -> void:
	"""构造边界提示气泡 + 挂到 HUD CanvasLayer。
	位置:屏幕顶部中央,WoodClock (top:-4~48) 下方,跟 PausedChip 同高度区间。"""
	_boundary_hint = PanelContainer.new()
	_boundary_hint.add_theme_stylebox_override("panel", ChromeTheme.make_parchment_floating(0.92))
	_boundary_hint.visible = false
	_boundary_hint.mouse_filter = Control.MOUSE_FILTER_IGNORE
	# WoodClock 在 viewport 顶部 -4~48,PausedChip 在 60~80。边界提示放 90~120。
	_boundary_hint.offset_left = 480
	_boundary_hint.offset_top = 90
	_boundary_hint.offset_right = 800
	_boundary_hint.offset_bottom = 120

	_boundary_hint_label = Label.new()
	_boundary_hint_label.add_theme_font_override("font", ChromeTheme.font_serif(600))
	_boundary_hint_label.add_theme_font_size_override("font_size", 14)
	_boundary_hint_label.add_theme_color_override("font_color", ChromeTheme.COLOR_DEEP_INK)
	_boundary_hint_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_boundary_hint.add_child(_boundary_hint_label)

	$HUD.add_child(_boundary_hint)


func _on_boundary_hint_changed(should_show: bool, text: String) -> void:
	if _boundary_hint == null:
		return
	if should_show:
		_boundary_hint_label.text = text
		_boundary_hint.visible = true
	else:
		_boundary_hint.visible = false


# ============================================================================
# F3 Q 场所概览 + Esc 系统菜单
# ============================================================================

func _toggle_location_card() -> void:
	"""按 Q 切换 LocationCard 显隐。已显示则关闭。"""
	if _location_card != null and is_instance_valid(_location_card):
		_location_card.queue_free()
		_location_card = null
		_unlock_player()
		return
	# 关闭其他 modal
	if _system_menu != null and is_instance_valid(_system_menu):
		_system_menu.queue_free()
		_system_menu = null
	# 创建
	var card = LocationCardScene.instantiate()
	$HUD.add_child(card)
	card.setup(GameWorld.current_view_location)
	card.closed.connect(func() -> void:
		_location_card = null
		_unlock_player()
	)
	_location_card = card
	_lock_player()


func _toggle_system_menu() -> void:
	"""按 Esc 切换 SystemMenu 显隐。已显示则关闭。"""
	if _system_menu != null and is_instance_valid(_system_menu):
		_system_menu.queue_free()
		_system_menu = null
		_unlock_player()
		return
	# 如果当前有 BubbleMenu 或 LocationCard,Esc 优先关它们
	if _bubble_menu != null and is_instance_valid(_bubble_menu):
		return  # BubbleMenu 自己处理 Esc(取消)
	if _location_card != null and is_instance_valid(_location_card):
		_location_card.queue_free()
		_location_card = null
		_unlock_player()
		return
	# 创建
	var menu = SystemMenuScene.instantiate()
	$HUD.add_child(menu)
	menu.closed.connect(func() -> void:
		_system_menu = null
		_unlock_player()
	)
	_system_menu = menu
	_lock_player()


func _lock_player() -> void:
	if _current_view == null:
		return
	var player: Node = _current_view.get_player_node() if _current_view.has_method("get_player_node") else null
	if player != null and player.has_method("set_move_blocked"):
		player.set_move_blocked(true)


# ============================================================================
# F4.2 F 读自己的心
# ============================================================================

func _toggle_inner_heart() -> void:
	"""按 F 切换 InnerHeart modal。已显示则关闭;否则拉玩家 reflections 后弹出。"""
	if _inner_heart != null and is_instance_valid(_inner_heart):
		_inner_heart.queue_free()
		_inner_heart = null
		_unlock_player()
		return

	# 关闭其他 modal
	if _location_card != null and is_instance_valid(_location_card):
		_location_card.queue_free()
		_location_card = null
	if _system_menu != null and is_instance_valid(_system_menu):
		_system_menu.queue_free()
		_system_menu = null

	# 立即弹出(空 reflections 显示 placeholder),后台拉数据
	var modal = InnerHeartScene.instantiate()
	$HUD.add_child(modal)
	var player_agent: Dictionary = GameWorld.get_agent(GameWorld.player_agent_id)
	var player_name: String = player_agent.get("display_name", "我")
	modal.setup(player_name, [])  # 空 reflections 显示 placeholder
	modal.closed.connect(func() -> void:
		_inner_heart = null
		_unlock_player()
	)
	_inner_heart = modal
	_lock_player()

	# 后台拉真实 reflections
	BackendClient.fetch_agent_memories(
		GameWorld.player_agent_id, 10,
		func(memories: Array) -> void:
			if _inner_heart == null or not is_instance_valid(_inner_heart):
				return
			# 过滤只要 reflection
			var reflections: Array = []
			for m in memories:
				if m.get("memory_type", "") == "reflection":
					reflections.append(m)
			_inner_heart.setup(player_name, reflections)
	)


# ============================================================================
# F4.3 R 关系网
# ============================================================================

func _toggle_relationship_network() -> void:
	"""按 R 切换 RelationshipNetwork modal。"""
	if _relationship_network != null and is_instance_valid(_relationship_network):
		_relationship_network.queue_free()
		_relationship_network = null
		_unlock_player()
		return

	# 关闭其他 modal
	if _inner_heart != null and is_instance_valid(_inner_heart):
		_inner_heart.queue_free()
		_inner_heart = null
	if _location_card != null and is_instance_valid(_location_card):
		_location_card.queue_free()
		_location_card = null
	if _system_menu != null and is_instance_valid(_system_menu):
		_system_menu.queue_free()
		_system_menu = null

	var modal = RelationshipNetworkScene.instantiate()
	$HUD.add_child(modal)
	modal.closed.connect(func() -> void:
		_relationship_network = null
		_unlock_player()
	)
	_relationship_network = modal
	_lock_player()
