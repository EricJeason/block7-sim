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
const WoodClock := preload("res://scripts/ui/wood_clock.gd")
const LocationLabel := preload("res://scripts/ui/location_label.gd")
const KeyHints := preload("res://scripts/ui/key_hints.gd")
const PausedChip := preload("res://scripts/ui/paused_chip.gd")

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
		loading_progress.text = "暂停中 — 点左下 ▶ 开始按钮启动预热"
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
	elif event is InputEventKey and event.pressed and event.keycode == KEY_R:
		_refresh_inspector()
	elif event is InputEventKey and event.pressed and event.keycode == KEY_TAB and not event.echo:
		# F1: Tab 切换暂停状态(等价旧 PauseButton)
		get_viewport().set_input_as_handled()
		BackendClient.set_sim_paused(not GameWorld.paused)


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
