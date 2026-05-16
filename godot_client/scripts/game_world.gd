extends Node

## GameWorld — autoload 单例,Block H Godot 端的"客户端世界状态镜像"。
##
## 职责:
## 1. 缓存后端 /world 返回的 4 个场所 + 12 个 agent 初始状态
## 2. 接收 BackendClient 转发的 WS 事件,更新本地 agent 状态
## 3. 用 signal 通知各 LocationScene / HUD / AgentNode 状态变化
## 4. 维护"玩家当前查看的场所" — 影响 Main 切场景与 inspector 焦点
##
## 设计要点:
## - agent state 用 Dictionary 而不是自定义类,便于 GDScript 端动态扩展
## - signal 颗粒度细(per agent),减少 UI 刷新成本
## - location_switched 由用户操作触发,与后端 sim 状态独立

# ---------------------------------------------------------------- signals

## 后端 /world 响应到达后触发一次。world: 完整 world snapshot dict。
signal world_initialized(world: Dictionary)

## 后端 WS hello 帧到达后触发一次。携带 agent_count / time_scale 等元数据。
signal hello_received(payload: Dictionary)

## 单个 agent 启动了一个 action。action 是 dict: action_type / args / duration_seconds / current_location 等。
signal agent_started_action(agent_id: String, action: Dictionary)

## 单个 agent 完成了一个 action。
signal agent_completed_action(agent_id: String, action: Dictionary)

## agent 进入背景思考(LLM planning 触发)。UI 可显示灯泡 emoji。
signal agent_thinking_started(agent_id: String)

## agent 完成思考,新 actions 已追加到队列。
signal agent_thinking_completed(agent_id: String, appended_count: int)

## agent 的 current_location 变化(由后端 perception 的 move_to 副作用推断)。
signal agent_moved(agent_id: String, from_loc: String, to_loc: String)

## tick 推进,game_time 更新。监听者:HUD 时钟。
signal sim_ticked(game_time: float)

## 玩家切换查看的场所(本地操作,不发给后端)。
signal location_switched(new_location_id: String)

## 后端连接状态变化。connected=true 表示 WS 已连;false 表示断开或未连。
signal connection_changed(connected: bool)

## sim 运行状态变化(后端 /sim/pause / /sim/resume 触发)。
signal paused_changed(paused: bool)

## Block I:对话事件。
signal dialogue_started(session_id: String, initiator_id: String, target_id: String, location: String)
signal dialogue_line(session_id: String, speaker_id: String, text: String, turn_idx: int)
signal dialogue_ended(session_id: String, initiator_id: String, target_id: String, total_turns: int, reason: String)

# ----------------------------------------------------------------- state

## locations[location_id] = { id, name, type, description, open_hours, adjacent_to[] }
var locations: Dictionary = {}

## agents[agent_id] = { agent_id, display_name, current_location, current_mood, current_action, queue, ... }
## 字段与后端 AgentRuntime.snapshot() 兼容,WS 事件会增量更新部分字段。
var agents: Dictionary = {}

## 玩家当前查看的场所 id;默认 lao_song_plaza。
var current_view_location: String = "lao_song_plaza"

## 最近一次 tick 的 game_time。
var game_time: float = 0.0

## 后端配置:1 现实秒 = N 游戏秒。
var time_scale: float = 60.0

## sim 是否暂停(后端 /world 返回 + WS paused_changed 同步)。
var paused: bool = true  # 默认暂停假设(BLOCK7_START_PAUSED=1)

var _connected: bool = false


# ---------------------------------------------------------- world init

func apply_world_snapshot(world: Dictionary) -> void:
	"""把 /world 响应灌入本地缓存,广播 world_initialized。"""
	locations.clear()
	for loc in world.get("locations", []):
		locations[loc["id"]] = loc

	agents.clear()
	for a in world.get("agents", []):
		agents[a["agent_id"]] = a

	game_time = float(world.get("game_time", 0.0))
	time_scale = float(world.get("time_scale", 60.0))
	# 兜底 true:后端没返回该字段时假设暂停(防意外烧 token)
	var raw_paused = world.get("paused")
	var new_paused: bool = bool(raw_paused) if raw_paused != null else true
	if new_paused != paused:
		paused = new_paused
		paused_changed.emit(paused)
	world_initialized.emit(world)


func apply_hello(payload: Dictionary) -> void:
	hello_received.emit(payload)


# ----------------------------------------------------------- ws events

func handle_sim_event(event: Dictionary) -> void:
	"""BackendClient 收到 WS SimEvent 后调此。
	event = { type, agent_id, game_time, payload }

	注意:backend 用 Python None → JSON null,GDScript 严格类型不接受 null。
	这里对每个字段做兜底转型。"""
	var ev_type: String = _str_or_empty(event.get("type"))
	var agent_id: String = _str_or_empty(event.get("agent_id"))
	var gt: float = _float_or_zero(event.get("game_time"))
	var raw_payload = event.get("payload")
	var payload: Dictionary = raw_payload if raw_payload is Dictionary else {}

	if gt > 0.0:
		game_time = gt
		sim_ticked.emit(game_time)

	match ev_type:
		"hello":
			apply_hello(payload)
		"action_started":
			_apply_action_started(agent_id, payload)
		"action_completed":
			_apply_action_completed(agent_id, payload)
		"thinking_started":
			agent_thinking_started.emit(agent_id)
		"thinking_completed":
			agent_thinking_completed.emit(agent_id, int(payload.get("appended_count", 0)))
		"paused_changed":
			var new_paused: bool = bool(payload.get("paused", false))
			if new_paused != paused:
				paused = new_paused
				paused_changed.emit(paused)
		"dialogue_started":
			dialogue_started.emit(
				_str_or_empty(payload.get("session_id")),
				_str_or_empty(payload.get("initiator_id")),
				_str_or_empty(payload.get("target_id")),
				_str_or_empty(payload.get("location")),
			)
		"dialogue_line":
			dialogue_line.emit(
				_str_or_empty(payload.get("session_id")),
				_str_or_empty(payload.get("speaker_id")),
				_str_or_empty(payload.get("text")),
				int(_float_or_zero(payload.get("turn_idx"))),
			)
		"dialogue_ended":
			dialogue_ended.emit(
				_str_or_empty(payload.get("session_id")),
				_str_or_empty(payload.get("initiator_id")),
				_str_or_empty(payload.get("target_id")),
				int(_float_or_zero(payload.get("total_turns"))),
				_str_or_empty(payload.get("reason")),
			)
		"tick_error":
			push_warning("[game_world] tick_error agent=%s err=%s" % [agent_id, payload.get("error", "?")])
		"pong":
			pass
		_:
			pass # 未知事件类型,留待后续 Block 扩展


func _apply_action_started(agent_id: String, payload: Dictionary) -> void:
	if agent_id == "" or not agents.has(agent_id):
		return
	var raw_args = payload.get("args")
	var action := {
		"action_type": _str_or_empty(payload.get("action_type")),
		"args": raw_args if raw_args is Dictionary else {},
		"duration_seconds": _float_or_zero(payload.get("duration_seconds")),
	}

	# 检测移动:current_location 变化时,广播 agent_moved
	var new_loc: String = _str_or_empty(payload.get("current_location"))
	var old_loc: String = _str_or_empty(agents[agent_id].get("current_location"))
	if new_loc != "" and new_loc != old_loc:
		agents[agent_id]["current_location"] = new_loc
		agent_moved.emit(agent_id, old_loc, new_loc)

	agents[agent_id]["current_action"] = action
	agent_started_action.emit(agent_id, action)


func _apply_action_completed(agent_id: String, payload: Dictionary) -> void:
	if agent_id == "" or not agents.has(agent_id):
		return
	var raw_args = payload.get("args")
	var action := {
		"action_type": _str_or_empty(payload.get("action_type")),
		"args": raw_args if raw_args is Dictionary else {},
	}
	agents[agent_id]["current_action"] = null
	agent_completed_action.emit(agent_id, action)


# --------------------------------------------------------- queries

func get_agents_in_location(location_id: String) -> Array:
	"""返回当前位于指定场所的所有 agent dict。"""
	var out: Array = []
	for agent_id in agents:
		var a: Dictionary = agents[agent_id]
		if a.get("current_location", "") == location_id:
			out.append(a)
	return out


func get_agent(agent_id: String) -> Dictionary:
	return agents.get(agent_id, {})


func get_location(location_id: String) -> Dictionary:
	return locations.get(location_id, {})


func get_location_ids() -> Array:
	return locations.keys()


# ----------------------------------------------------- view location

func switch_view_to(location_id: String) -> void:
	"""玩家请求切到某场所。校验存在性,广播 location_switched。"""
	if not locations.has(location_id):
		push_warning("[game_world] unknown location: %s" % location_id)
		return
	if location_id == current_view_location:
		return
	current_view_location = location_id
	location_switched.emit(location_id)


# ----------------------------------------------------- connection

func set_connected(connected: bool) -> void:
	if _connected == connected:
		return
	_connected = connected
	connection_changed.emit(connected)


func is_connected_to_backend() -> bool:
	return _connected


# ----------------------------------------------------- helpers

static func _str_or_empty(value) -> String:
	"""null / 非字符串 → 空串;String → 原值;其它 → str()。
	GDScript 4 strict typing 不允许 null 赋给 String,这里兜底。"""
	if value == null:
		return ""
	if value is String:
		return value
	return str(value)


static func _float_or_zero(value) -> float:
	if value == null:
		return 0.0
	if value is float or value is int:
		return float(value)
	return 0.0
