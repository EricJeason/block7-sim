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

var _current_view: Node2D = null
var _selected_agent_id: String = ""


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
	pause_button.pressed.connect(_on_pause_button_pressed)

	_update_nav_label()
	_update_time_label()
	_update_connection_dot(false)
	_update_pause_button()
	memory_panel.visible = false


func _on_world_initialized(_world: Dictionary) -> void:
	# 第一次或重连时灌入了 world,加载默认场所
	_switch_location_view(GameWorld.current_view_location)
	_refresh_inspector()


func _on_location_switched(new_location_id: String) -> void:
	_switch_location_view(new_location_id)
	_refresh_inspector()
	_clear_memory_panel()


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


func _on_connection_changed(connected: bool) -> void:
	_update_connection_dot(connected)


func _on_paused_changed(_paused: bool) -> void:
	_update_pause_button()


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


# ------------------------------------------------------- HUD updates

func _update_time_label() -> void:
	var gt: float = GameWorld.game_time
	var seconds_per_day: float = 86400.0
	var day: int = int(gt / seconds_per_day) + 1
	var seconds_today: float = fmod(gt, seconds_per_day)
	var hour: int = int(seconds_today / 3600.0)
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
	var a: Dictionary = GameWorld.get_agent(agent_id)
	memory_title.text = "%s · 最近 8 条记忆" % a.get("display_name", agent_id)
	memory_panel.visible = true
	memory_content.text = "[正在拉取...]"

	BackendClient.fetch_agent_memories(agent_id, 8, func(memories: Array) -> void:
		if _selected_agent_id != agent_id:
			return  # 已切到别人
		if memories.is_empty():
			memory_content.text = "[无记忆]"
			return
		var lines: PackedStringArray = []
		for m in memories:
			var mtype: String = m.get("memory_type", "?")
			var imp: int = int(m.get("importance", 0))
			var content: String = str(m.get("content", "")).replace("\n", " ")
			var tag: String = mtype.substr(0, 1).to_upper()
			lines.append("[color=#a8b3c2][%s imp=%d][/color] %s" % [tag, imp, content])
		memory_content.text = "\n\n".join(lines)
	)


func _clear_memory_panel() -> void:
	_selected_agent_id = ""
	memory_panel.visible = false
