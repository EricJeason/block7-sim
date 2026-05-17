class_name KeyHints
extends VBoxContainer

# preload 保证不依赖 .godot/global_script_class_cache.cfg(被 .gitignore)
const ChromeTheme := preload("res://scripts/ui/chrome_theme.gd")
const KeyCapClass := preload("res://scripts/ui/key_cap.gd")

## 右下键位提示列阵 — 8 个 KeyCap + label。
## 设计稿 ui-elements.jsx KeyHints()。
##
## 视觉:KeyCap 半透明羊皮纸 + 旁边 11px Plex Mono 0.7α 标签。
## 锚点:右 32px,底 28px(由父节点 anchor 定位,VBox 内部右对齐)

const KeyCapScene := preload("res://scenes/ui/KeyCap.tscn")

## hint = { key: "E", label: "与 林秋 互动", dim: bool(optional) }
@export var hints: Array[Dictionary] = []:
	set(value):
		hints = value
		if is_inside_tree():
			_rebuild()


func _ready() -> void:
	add_theme_constant_override("separation", 4)
	alignment = BoxContainer.ALIGNMENT_END  # 右对齐(实际生效靠父节点 size + anchor)
	_rebuild()


func _rebuild() -> void:
	for child in get_children():
		child.queue_free()

	for h in hints:
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 6)
		row.alignment = BoxContainer.ALIGNMENT_END

		var cap = KeyCapScene.instantiate()  # 类型实际为 KeyCap,避免 class_name cache 依赖
		cap.text = h.get("key", "?")
		cap.dim = h.get("dim", false)
		row.add_child(cap)

		var label := Label.new()
		label.text = h.get("label", "")
		label.add_theme_font_override("font", ChromeTheme.font_mono(400))
		label.add_theme_font_size_override("font_size", 11)
		var ink := Color(0.157, 0.118, 0.078, 0.7)  # rgba(40,30,20,0.7)
		label.add_theme_color_override("font_color", ink)
		# 暖色文字外光(模拟 textShadow)
		label.add_theme_color_override("font_outline_color", Color(0.96, 0.92, 0.78, 0.5))
		label.add_theme_constant_override("outline_size", 2)
		label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		if h.get("dim", false):
			label.modulate.a = 0.6
		row.add_child(label)

		add_child(row)


## 标准 v0.2 的 hints(C/I/J/P 在 v0.2 未实装,标 dim)
static func default_hints_v02(e_target_name: String = "") -> Array[Dictionary]:
	var e_label: String
	if e_target_name == "":
		e_label = "靠近 NPC 互动"
	else:
		e_label = "与 %s 互动" % e_target_name
	return [
		{"key": "WASD", "label": "移动"},
		{"key": "E", "label": e_label},
		{"key": "Tab", "label": "暂停"},
		{"key": "F11", "label": "全屏"},
		{"key": "C", "label": "角色", "dim": true},
		{"key": "I", "label": "背包", "dim": true},
		{"key": "J", "label": "线索 / 任务", "dim": true},
		{"key": "P", "label": "图鉴", "dim": true},
		{"key": "Q", "label": "场所概览", "dim": true},
		{"key": "F", "label": "读自己的心", "dim": true},
		{"key": "Esc", "label": "菜单", "dim": true},
	]
