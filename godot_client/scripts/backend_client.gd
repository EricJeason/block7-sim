extends Node

## BackendClient — autoload 单例,与 Python 后端的全部通讯。
##
## 启动顺序:
##   _ready  → start() → _check_health() → _fetch_world() → _open_websocket()
##
## 持续运行:
##   _process(delta):WebSocketPeer.poll() + 读包 → GameWorld.handle_sim_event()
##   断线后 RECONNECT_INTERVAL 秒后自动重连
##   PING_INTERVAL 秒一次保活 ping
##
## 调用方一般不直接用此类 — 监听 GameWorld 的 signal 即可。

const BACKEND_URL: String = "http://127.0.0.1:8000"
const WS_URL: String = "ws://127.0.0.1:8000/ws/sim"

const RECONNECT_INTERVAL: float = 5.0  # WS 断线 N 秒后重连
const PING_INTERVAL: float = 30.0       # WS 保活 ping 间隔


# HTTP 请求节点(每次创建新节点,避免重入冲突)
var _ws: WebSocketPeer
var _ws_state: int = -1  # -1 = 未初始化, 0..3 为 WebSocketPeer.STATE_*
var _reconnect_timer: float = 0.0
var _ping_timer: float = 0.0
var _started: bool = false
var _ws_handshake_started: bool = false  # 第一次 connect_to_url 之后置 true
var _ws_ever_connected: bool = false     # 曾经 STATE_OPEN 过


func _ready() -> void:
	_ws = WebSocketPeer.new()
	# 延迟一帧再启动,等其它 autoload 就绪
	call_deferred("start")


func start() -> void:
	if _started:
		return
	_started = true
	_check_health()


# ------------------------------------------------------------------ HTTP

func _check_health() -> void:
	"""沿用 Block A 的 /health 探活,通过后才拉 /world。"""
	var http := HTTPRequest.new()
	add_child(http)
	http.request_completed.connect(
		func(result: int, code: int, _h: PackedStringArray, body: PackedByteArray) -> void:
			http.queue_free()
			if result != HTTPRequest.RESULT_SUCCESS or code != 200:
				push_warning("[backend_client] /health failed: result=%d code=%d" % [result, code])
				# 5 秒后再试
				get_tree().create_timer(RECONNECT_INTERVAL).timeout.connect(_check_health)
				return
			print("[backend_client] /health ok")
			_fetch_world()
	)
	var err: int = http.request(BACKEND_URL + "/health")
	if err != OK:
		push_warning("[backend_client] /health request err=%d" % err)
		http.queue_free()
		get_tree().create_timer(RECONNECT_INTERVAL).timeout.connect(_check_health)


func _fetch_world() -> void:
	var http := HTTPRequest.new()
	add_child(http)
	http.request_completed.connect(
		func(result: int, code: int, _h: PackedStringArray, body: PackedByteArray) -> void:
			http.queue_free()
			if result != HTTPRequest.RESULT_SUCCESS or code != 200:
				push_warning("[backend_client] /world failed: result=%d code=%d" % [result, code])
				return
			var text: String = body.get_string_from_utf8()
			var parsed: Variant = JSON.parse_string(text)
			if typeof(parsed) != TYPE_DICTIONARY:
				push_warning("[backend_client] /world parse failed: %s" % text.substr(0, 200))
				return
			print("[backend_client] /world ok: %d agents, %d locations" % [
				parsed.get("agents", []).size(),
				parsed.get("locations", []).size(),
			])
			GameWorld.apply_world_snapshot(parsed)
			_open_websocket()
	)
	var err: int = http.request(BACKEND_URL + "/world")
	if err != OK:
		push_warning("[backend_client] /world request err=%d" % err)
		http.queue_free()


## 请求 sim pause / resume(成本控制)。
## paused=true → POST /sim/pause, false → /sim/resume。
## 状态变化最终通过 WS paused_changed 事件回到 GameWorld。
func set_sim_paused(paused: bool) -> void:
	var http := HTTPRequest.new()
	add_child(http)
	http.request_completed.connect(
		func(result: int, code: int, _h: PackedStringArray, _body: PackedByteArray) -> void:
			http.queue_free()
			if result != HTTPRequest.RESULT_SUCCESS or code != 200:
				push_warning("[backend_client] /sim/%s failed: result=%d code=%d" % [
					"pause" if paused else "resume", result, code
				])
	)
	var url: String = BACKEND_URL + ("/sim/pause" if paused else "/sim/resume")
	# FastAPI POST 端点无需 body
	var err: int = http.request(url, [], HTTPClient.METHOD_POST, "")
	if err != OK:
		push_warning("[backend_client] POST /sim/%s err=%d" % ["pause" if paused else "resume", err])
		http.queue_free()


## 拉取单个 agent 最近 N 条 memory(inspector 面板用)。
## callback 形如: func(memories: Array) -> void
func fetch_agent_memories(agent_id: String, limit: int, callback: Callable) -> void:
	var http := HTTPRequest.new()
	add_child(http)
	http.request_completed.connect(
		func(result: int, code: int, _h: PackedStringArray, body: PackedByteArray) -> void:
			http.queue_free()
			if result != HTTPRequest.RESULT_SUCCESS or code != 200:
				callback.call([])
				return
			var text: String = body.get_string_from_utf8()
			var parsed: Variant = JSON.parse_string(text)
			if typeof(parsed) != TYPE_ARRAY:
				callback.call([])
				return
			callback.call(parsed)
	)
	var url: String = "%s/agent/%s/memories?limit=%d" % [BACKEND_URL, agent_id, limit]
	var err: int = http.request(url)
	if err != OK:
		http.queue_free()
		callback.call([])


# ---------------------------------------------------------- WebSocket

func _open_websocket() -> void:
	print("[backend_client] connecting WS: %s" % WS_URL)
	var err: int = _ws.connect_to_url(WS_URL)
	if err != OK:
		push_warning("[backend_client] WS connect err=%d, retry in %ds" % [err, RECONNECT_INTERVAL])
		_reconnect_timer = RECONNECT_INTERVAL
		return
	_ws_handshake_started = true
	_reconnect_timer = 0.0  # 清掉可能挂着的旧倒计时


func _process(delta: float) -> void:
	if _ws == null:
		return

	# 重连倒计时 — 注意:这里 *不能* return,否则 poll 不到, 握手永远完不成
	if _reconnect_timer > 0.0:
		_reconnect_timer -= delta
		if _reconnect_timer <= 0.0:
			_reconnect_timer = 0.0
			_open_websocket()

	# 第一次 connect_to_url 之前 _ws 状态总是 CLOSED,不要 poll(没意义且会触发误判)
	if not _ws_handshake_started:
		return

	_ws.poll()
	var state: int = _ws.get_ready_state()

	if state != _ws_state:
		_on_state_change(state)
		_ws_state = state

	if state == WebSocketPeer.STATE_OPEN:
		# 读所有待处理消息
		while _ws.get_available_packet_count() > 0:
			_handle_packet(_ws.get_packet())
		# 保活 ping
		_ping_timer += delta
		if _ping_timer >= PING_INTERVAL:
			_ping_timer = 0.0
			_ws.send_text("ping")


func _on_state_change(new_state: int) -> void:
	# 重连决策只在这里做(由 state 真的*变化*触发),避免每帧 match STATE_CLOSED 反复设 timer
	match new_state:
		WebSocketPeer.STATE_OPEN:
			print("[backend_client] WS connected")
			GameWorld.set_connected(true)
			_ping_timer = 0.0
			_ws_ever_connected = true
		WebSocketPeer.STATE_CLOSED:
			# 仅在曾经握手过(CONNECTING 或更后)的前提下视为断开
			if _ws_state == WebSocketPeer.STATE_OPEN:
				var code: int = _ws.get_close_code()
				var reason: String = _ws.get_close_reason()
				print("[backend_client] WS closed code=%d reason=%s" % [code, reason])
			elif _ws_state == WebSocketPeer.STATE_CONNECTING:
				print("[backend_client] WS handshake failed")
			GameWorld.set_connected(false)
			# 安排重连(不立即,避免 hot loop)
			if _reconnect_timer <= 0.0:
				_reconnect_timer = RECONNECT_INTERVAL
		WebSocketPeer.STATE_CONNECTING:
			print("[backend_client] WS handshake started")
		WebSocketPeer.STATE_CLOSING:
			pass


func _handle_packet(packet: PackedByteArray) -> void:
	var text: String = packet.get_string_from_utf8()
	var parsed: Variant = JSON.parse_string(text)
	if typeof(parsed) != TYPE_DICTIONARY:
		push_warning("[backend_client] WS bad payload: %s" % text.substr(0, 200))
		return
	GameWorld.handle_sim_event(parsed)
