extends Node2D

## 主场景控制 — Block A 仅打印日志并显示一行状态文字。

@onready var status_label: Label = $StatusLabel


func _ready() -> void:
	print("[main.gd] Block-7 Sim — Day 1 Block A OK")
	if status_label:
		status_label.text = "Block-7 Sim — Day 1 Block A OK"
