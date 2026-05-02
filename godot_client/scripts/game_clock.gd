extends Node

## 游戏时间系统(autoload 单例)— 维护虚拟世界时钟,单位:秒。
## time_scale 表示「现实 1 秒 == 虚拟 N 秒」,默认 60(1 现实秒 == 1 虚拟分钟)。

var game_time: float = 0.0
var time_scale: float = 60.0


func _process(delta: float) -> void:
	game_time += delta * time_scale
