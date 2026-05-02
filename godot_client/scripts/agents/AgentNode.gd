extends Node2D

## 单个 agent 在场景里的可视节点。Block A 只声明 agent_id,后续 Block 填充贴图与动作播放逻辑。

@export var agent_id: String = ""


func _ready() -> void:
	pass # Block H: implement this — 订阅 BackendClient 推送的 agent 事件并更新展示
