extends Node2D
class_name LocationView

## 单个场所的视图节点。Main.tscn 在切场所时 instantiate 4 个其中之一。
##
## 职责:
## 1. 显示场所背景图(若存在 res://assets/locations/{id}/background.png)
## 2. 持续追踪 GameWorld.agents,把 current_location == self.location_id 的 agent
##    显示为子节点(AgentNode);离开时移除
## 3. 监听 agent_moved / agent_started_action / agent_completed_action,
##    forward 给对应 AgentNode

const AgentNodeScene := preload("res://scenes/AgentNode.tscn")
const PlayerNodeScene := preload("res://scenes/PlayerNode.tscn")

# 通过 .tscn 中的 export 字段或 Main 切场所时设置
@export var location_id: String = ""

## 占位背景色(场所未提供 background.png 时使用)
@export var placeholder_color: Color = Color(0.2, 0.2, 0.25)

## agent_id → AgentNode 实例
var _agent_nodes: Dictionary = {}

## F2 玩家节点(每个 LocationView 一份,场所切换时随之销毁重建)
var _player_node: Node2D = null

## F2 hover/interaction 距离阈值 (px,设计稿 main-screen.jsx 第 11-13 行)
const HOVER_RADIUS: float = 140.0
const INTERACT_RADIUS: float = 110.0
# Eric 反馈"工作状态弹窗有点短暂"→ 加滞后区:进 140 触发显示,出 240 才消失
const HOVER_KEEP_RADIUS: float = 240.0

## F2 最近 NPC 的 agent_id(用于 BubbleMenu 锁定目标 + 单点 E-prompt)
var _nearest_npc_id: String = ""
var _nearest_npc_dist: float = 1e9

## F2 hover 滞后状态: {agent_id: bool} 跟踪每 NPC 当前是否在 hover 显示中
var _hover_state: Dictionary = {}

@onready var bg_rect: ColorRect = $BackgroundRect
@onready var bg_sprite: Sprite2D = $BackgroundSprite
@onready var location_label: Label = $UILayer/LocationLabel
@onready var agents_container: Node2D = $AgentsContainer


func _ready() -> void:
	bg_rect.color = placeholder_color
	_load_background_if_exists()
	_update_location_label()

	# 连接 GameWorld signal
	GameWorld.agent_moved.connect(_on_agent_moved)
	GameWorld.agent_started_action.connect(_on_agent_started_action)
	GameWorld.agent_completed_action.connect(_on_agent_completed_action)
	GameWorld.agent_thinking_started.connect(_on_agent_thinking_started)
	GameWorld.agent_thinking_completed.connect(_on_agent_thinking_completed)
	GameWorld.world_initialized.connect(_on_world_initialized)
	GameWorld.dialogue_line.connect(_on_dialogue_line)
	GameWorld.dialogue_ended.connect(_on_dialogue_ended)

	# 若 world 已经初始化(切场所重新进入时),立即填充
	_populate_agents()

	# F2: 实例化玩家节点(扮演 agent_04 艾琳)
	_spawn_player_node()


# --------------------------------------------------------- background

func _load_background_if_exists() -> void:
	"""若 res://assets/locations/{id}/background.png 存在,按 cover 策略撑满视口。

	cover 策略:
	- 等比缩放使图宽 = 视口宽(1280)
	- 中心对齐于视口中心(640, 360)
	- 图高若 > 720,上下溢出部分被视口裁掉
	- 大多数 AI 生图主要内容在中段,上下裁的是天空/地面延伸,可接受
	"""
	if location_id == "":
		return
	var path: String = "res://assets/locations/%s/background.png" % location_id
	if not ResourceLoader.exists(path):
		return
	var tex: Texture2D = load(path) as Texture2D
	if tex == null:
		return

	var viewport_size := Vector2(1280, 720)
	var tex_size: Vector2 = tex.get_size()
	if tex_size.x <= 0 or tex_size.y <= 0:
		return

	# cover:取 max(横向缩放, 纵向缩放),保证图覆盖整个视口
	var scale_x: float = viewport_size.x / tex_size.x
	var scale_y: float = viewport_size.y / tex_size.y
	var s: float = max(scale_x, scale_y)

	bg_sprite.texture = tex
	bg_sprite.centered = true
	bg_sprite.position = viewport_size / 2
	bg_sprite.scale = Vector2(s, s)
	bg_sprite.visible = true
	bg_rect.visible = false  # 有真实背景就隐藏色块


func _update_location_label() -> void:
	if location_id == "":
		location_label.text = "(unknown location)"
		return
	var loc: Dictionary = GameWorld.get_location(location_id)
	location_label.text = loc.get("name", location_id)


# ----------------------------------------------------- agent visibility

func _populate_agents() -> void:
	"""扫描 GameWorld.agents,把当前在本场所的 agent 实例化为子节点。
	F2: 跳过 player_agent_id(玩家由 PlayerNode 单独渲染,不重复)。"""
	if location_id == "":
		return
	for agent in GameWorld.get_agents_in_location(location_id):
		var aid: String = agent["agent_id"]
		if GameWorld.is_player_agent(aid):
			continue
		_ensure_agent_node(aid)


func _ensure_agent_node(agent_id: String) -> Node2D:
	if _agent_nodes.has(agent_id):
		return _agent_nodes[agent_id]
	# F2: 玩家 agent 不渲染 AgentNode(由 PlayerNode 处理)
	if GameWorld.is_player_agent(agent_id):
		return null
	var node: Node2D = AgentNodeScene.instantiate()
	node.name = agent_id
	node.set("agent_id", agent_id)
	# F2: 用锚点站位代替 4×3 网格
	node.position = _anchor_position_for(agent_id)
	# F2: z_index 跟随 y(前后遮挡)
	node.z_index = int(node.position.y)
	agents_container.add_child(node)
	_agent_nodes[agent_id] = node
	return node


func _process(_delta: float) -> void:
	"""F2: 每帧算玩家到各 AgentNode 距离 → 调度 hover whisper + E-prompt。
	找最近 NPC,只在它身上显 E-prompt(避免多个 E 浮气泡重叠)。"""
	if _player_node == null:
		return
	var player_pos: Vector2 = _player_node.position

	_nearest_npc_id = ""
	_nearest_npc_dist = 1e9

	for aid in _agent_nodes:
		var node: Node2D = _agent_nodes[aid]
		if node == null or not is_instance_valid(node):
			continue
		var d: float = player_pos.distance_to(node.position)
		# F2 Hover whisper 滞后(hysteresis):
		# - 距离 <140 → 触发显示(状态=true)
		# - 距离 >240 → 隐藏(状态=false)
		# - 140-240 之间 → 保持上次状态(防止边缘距离玩家走开瞬间就消失)
		var prev_hover: bool = _hover_state.get(aid, false)
		var new_hover: bool = prev_hover
		if d < HOVER_RADIUS:
			new_hover = true
		elif d > HOVER_KEEP_RADIUS:
			new_hover = false
		if new_hover != prev_hover:
			_hover_state[aid] = new_hover
			if node.has_method("set_hover_whisper"):
				node.set_hover_whisper(new_hover)
		if d < _nearest_npc_dist:
			_nearest_npc_dist = d
			_nearest_npc_id = aid

	# 只在"最近 NPC 且 < INTERACT_RADIUS"时显示 E-prompt
	for aid in _agent_nodes:
		var node2: Node2D = _agent_nodes[aid]
		if node2 == null or not is_instance_valid(node2):
			continue
		if node2.has_method("set_e_prompt"):
			var is_target: bool = (aid == _nearest_npc_id and _nearest_npc_dist < INTERACT_RADIUS)
			node2.set_e_prompt(is_target)


## F2D BubbleMenu 用:返回当前可互动的最近 NPC agent_id,无则空串。
func get_interactable_npc_id() -> String:
	if _nearest_npc_dist < INTERACT_RADIUS:
		return _nearest_npc_id
	return ""


func get_player_node() -> Node2D:
	return _player_node


func _spawn_player_node() -> void:
	"""F2: 在本 LocationView 加 PlayerNode(扮演 agent_04)。
	切换场所时旧 LocationView free → 旧 PlayerNode 一起销毁;新 LocationView 重建。
	位置:从 GameWorld.player_x/y 恢复(默认 640, 540 场所中央)。"""
	if _player_node != null:
		return
	_player_node = PlayerNodeScene.instantiate()
	_player_node.name = "PlayerNode"
	agents_container.add_child(_player_node)


func _remove_agent_node(agent_id: String) -> void:
	if not _agent_nodes.has(agent_id):
		return
	var node: Node = _agent_nodes[agent_id]
	_agent_nodes.erase(agent_id)
	node.queue_free()


func _anchor_position_for(agent_id: String) -> Vector2:
	"""F2 锚点站位:NPC 按 sorted index 映射到 location 的锚点。

	设计稿原则:每个场所 6-7 个语义锚点(井边/老松下/酒馆门口...)。
	NPC 不再 4×3 撞位,而是分布在场景里有语义的点上。

	算法:取 GameWorld.is_in_location(agent_id, location_id) 的 NPC list sorted,
	找到本 agent 的 index,映射到 anchors[index % anchor_count]。

	若 location 没有 anchors(后端 yaml 没配)→ fallback 4×3 网格(老版本)。
	"""
	var anchors: Array = GameWorld.get_location_anchors(location_id)
	if anchors.is_empty():
		return _fallback_grid_position(agent_id)

	# 取当前在本场所的 agent list(不含玩家),sorted
	var here_ids: Array = []
	for a in GameWorld.get_agents_in_location(location_id):
		var aid: String = a.get("agent_id", "")
		if aid != "" and not GameWorld.is_player_agent(aid):
			here_ids.append(aid)
	here_ids.sort()
	var idx: int = here_ids.find(agent_id)
	if idx < 0:
		idx = 0
	var anchor: Dictionary = anchors[idx % anchors.size()]
	return Vector2(float(anchor.get("x", 640)), float(anchor.get("y", 540)))


func _fallback_grid_position(agent_id: String) -> Vector2:
	"""无 anchors 时的 fallback,旧 4×3 网格逻辑。"""
	var all_ids: Array = GameWorld.agents.keys()
	all_ids.sort()
	var idx: int = all_ids.find(agent_id)
	if idx < 0:
		idx = absi(agent_id.hash()) % 12
	var col: int = idx % 4
	@warning_ignore("integer_division")
	var row: int = idx / 4
	var x: float = 220.0 + col * 240.0
	var y: float = 320.0 + row * 130.0
	return Vector2(x, y)


# -------------------------------------------------------- signal handlers

func _on_world_initialized(_world: Dictionary) -> void:
	_update_location_label()
	_populate_agents()


func _on_agent_moved(agent_id: String, from_loc: String, to_loc: String) -> void:
	# 进来:实例化;离开:销毁
	if to_loc == location_id:
		_ensure_agent_node(agent_id)
	elif from_loc == location_id:
		_remove_agent_node(agent_id)


func _on_agent_started_action(agent_id: String, action: Dictionary) -> void:
	var node: Node = _agent_nodes.get(agent_id)
	if node == null:
		# action_started 可能携带 current_location 更新,触发上面 _on_agent_moved。
		# 这里再扫一次:如果 agent 现在属于本场所但还没实例化,补上。
		var a: Dictionary = GameWorld.get_agent(agent_id)
		if a.get("current_location", "") == location_id:
			node = _ensure_agent_node(agent_id)
	if node != null and node.has_method("on_action_started"):
		node.on_action_started(action)


func _on_agent_completed_action(agent_id: String, action: Dictionary) -> void:
	var node: Node = _agent_nodes.get(agent_id)
	if node != null and node.has_method("on_action_completed"):
		node.on_action_completed(action)


func _on_agent_thinking_started(agent_id: String) -> void:
	var node: Node = _agent_nodes.get(agent_id)
	if node != null and node.has_method("on_thinking_started"):
		node.on_thinking_started()


func _on_agent_thinking_completed(agent_id: String, appended_count: int) -> void:
	var node: Node = _agent_nodes.get(agent_id)
	if node != null and node.has_method("on_thinking_completed"):
		node.on_thinking_completed(appended_count)


func _on_dialogue_line(_session_id: String, speaker_id: String, text: String, _turn_idx: int) -> void:
	# F4.4: 全屏 DialogueSession modal 打开时跳过 NPC 头顶气泡
	if GameWorld.dialogue_modal_active:
		return
	var node: Node = _agent_nodes.get(speaker_id)
	if node != null and node.has_method("show_speech_line"):
		node.show_speech_line(text)


func _on_dialogue_ended(_sess: String, _initiator_id: String, _target_id: String, _turns: int, _reason: String) -> void:
	# Block I 精修:不再立刻隐藏气泡 — 让最后一句的 timer 按字数自然消失,
	# 避免短台词刚弹出就被强制清掉
	pass
