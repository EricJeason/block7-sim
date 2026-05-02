extends Node

## 后端 HTTP / WebSocket 客户端(autoload 单例)。
## Block A 仅实现 /health 探活,后续 Block H 接入 WebSocket 事件流。

const BACKEND_URL: String = "http://127.0.0.1:8000"

var _http: HTTPRequest


func _ready() -> void:
	_http = HTTPRequest.new()
	add_child(_http)
	_http.request_completed.connect(_on_health_completed)
	health_check()


func health_check() -> void:
	var url: String = BACKEND_URL + "/health"
	var err: int = _http.request(url)
	if err != OK:
		push_warning("[backend_client] health_check request error: %s" % err)


func _on_health_completed(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	if result != HTTPRequest.RESULT_SUCCESS or response_code != 200:
		print("[backend_client] Backend health check: FAILED (result=%s code=%s)" % [result, response_code])
		return
	var text: String = body.get_string_from_utf8()
	var parsed: Variant = JSON.parse_string(text)
	if typeof(parsed) == TYPE_DICTIONARY and parsed.has("status"):
		print("[backend_client] Backend health check: %s" % parsed["status"])
	else:
		print("[backend_client] Backend health check raw: %s" % text)
