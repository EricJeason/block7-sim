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

# 通过 .tscn 中的 export 字段或 Main 切场所时设置
@export var location_id: String = ""

## 占位背景色(场所未提供 background.png 时使用)
@export var placeholder_color: Color = Color(0.2, 0.2, 0.25)

## agent_id → AgentNode 实例
var _agent_nodes: Dictionary = {}

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

	# 若 world 已经初始化(切场所重新进入时),立即填充
	_populate_agents()


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
	"""扫描 GameWorld.agents,把当前在本场所的 agent 实例化为子节点。"""
	if location_id == "":
		return
	for agent in GameWorld.get_agents_in_location(location_id):
		_ensure_agent_node(agent["agent_id"])


func _ensure_agent_node(agent_id: String) -> Node2D:
	if _agent_nodes.has(agent_id):
		return _agent_nodes[agent_id]
	var node: Node2D = AgentNodeScene.instantiate()
	node.name = agent_id
	node.set("agent_id", agent_id)
	# 随机分布:避免角色叠一起。简单的伪随机靠 agent_id hash。
	node.position = _slot_position_for(agent_id)
	agents_container.add_child(node)
	_agent_nodes[agent_id] = node
	return node


func _remove_agent_node(agent_id: String) -> void:
	if not _agent_nodes.has(agent_id):
		return
	var node: Node = _agent_nodes[agent_id]
	_agent_nodes.erase(agent_id)
	node.queue_free()


func _slot_position_for(agent_id: String) -> Vector2:
	"""按 agent_id 哈希分配场内站位。简单 4x3 网格,后续可改寻路。
	x 范围 220-940(避开右侧 inspector 280px 占位区),y 范围 320-580。"""
	@warning_ignore("integer_division")
	var h: int = absi(agent_id.hash())
	var col: int = h % 4
	@warning_ignore("integer_division")
	var row: int = (h / 4) % 3
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
