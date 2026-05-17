extends Control

## API key 输入弹窗 — 首次启动时若 backend 未配置 key 则显示。
##
## 流程:
## 1. BackendClient.start() 检测到 /sim/api_key/status configured=false
## 2. emit GameWorld.api_key_required → main.gd 显示本弹窗
## 3. 用户填 sk-... + 点 "提交"
## 4. POST /sim/api_key/set → 成功后:
##    - 弹窗隐藏
##    - emit GameWorld.api_key_configured
##    - BackendClient 继续 fetch_world / 开 WS
##
## 安全:
## - LineEdit secret=true,默认 • 显示;勾"显示明文"可临时看清
## - 提交后 key 只发给本地 backend,绝不传任何远程
## - backend 写到本地 .env 文件(已 .gitignore)

@onready var key_line_edit: LineEdit = $Panel/KeyLineEdit
@onready var submit_button: Button = $Panel/SubmitButton
@onready var show_key_button: CheckBox = $Panel/ShowKeyButton
@onready var status_label: Label = $Panel/StatusLabel


func _ready() -> void:
	visible = false  # 默认隐藏,等 GameWorld.api_key_required 才显示
	submit_button.pressed.connect(_on_submit)
	show_key_button.toggled.connect(_on_show_key_toggled)
	key_line_edit.text_submitted.connect(func(_t: String) -> void: _on_submit())
	GameWorld.api_key_required.connect(_on_api_key_required)


func _on_api_key_required() -> void:
	visible = true
	status_label.text = ""
	key_line_edit.text = ""
	key_line_edit.grab_focus()


func _on_show_key_toggled(pressed: bool) -> void:
	key_line_edit.secret = not pressed


func _on_submit() -> void:
	var key: String = key_line_edit.text.strip_edges()
	# 客户端预校验(backend 端会再校验一次)
	if not key.begins_with("sk-"):
		_set_error("× key 必须以 sk- 开头")
		return
	if key.length() < 20:
		_set_error("× key 长度过短(应 ≥ 20 字符)")
		return
	# 锁按钮防重复点击
	submit_button.disabled = true
	submit_button.text = "提交中..."
	status_label.text = ""
	status_label.modulate = Color(0.85, 0.85, 0.95, 1)
	BackendClient.submit_api_key(key, _on_submit_result)


func _on_submit_result(success: bool, masked: String, persisted: bool, error: String) -> void:
	submit_button.disabled = false
	submit_button.text = "✓ 提交并启动"
	if success:
		var msg = "✓ 已设置 %s · " % masked
		msg += "已持久化到 .env" if persisted else "(仅运行时,重启失效)"
		status_label.text = msg
		status_label.modulate = Color(0.5, 0.95, 0.6, 1)
		# 通知 GameWorld + main.gd 隐藏弹窗
		GameWorld.api_key_configured.emit()
		# 1 秒后真正隐藏(让用户看到成功消息)
		await get_tree().create_timer(1.0).timeout
		visible = false
	else:
		_set_error("× 提交失败:%s" % error)


func _set_error(msg: String) -> void:
	status_label.text = msg
	status_label.modulate = Color(0.95, 0.5, 0.5, 1)
