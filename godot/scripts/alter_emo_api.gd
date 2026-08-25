extends Node
class_name AlterEmoApi

signal health_received(data: Dictionary)
signal session_started(data: Dictionary)
signal message_received(data: Dictionary)
signal reflection_received(data: Dictionary)
signal session_reset(data: Dictionary)
signal request_failed(message: String)

@export var base_url := "http://127.0.0.1:5000"

var _http: HTTPRequest
var _operation := ""


func _ready() -> void:
	_http = HTTPRequest.new()
	add_child(_http)
	_http.request_completed.connect(_on_request_completed)


func check_health() -> void:
	_send("health", HTTPClient.METHOD_GET, "/health")


func start_session(persona_id: String, interlocutor := "self") -> void:
	_send("start", HTTPClient.METHOD_POST, "/v1/sessions", {
		"persona_id": persona_id,
		"interlocutor": interlocutor,
	})


func send_message(session_id: String, content: String) -> void:
	_send("message", HTTPClient.METHOD_POST, "/v1/sessions/%s/messages" % session_id, {
		"content": content,
	})


func reflect_event(session_id: String, event: String) -> void:
	_send("reflection", HTTPClient.METHOD_POST, "/v1/sessions/%s/events" % session_id, {
		"event": event,
	})


func reset_session(session_id: String) -> void:
	_send("reset", HTTPClient.METHOD_DELETE, "/v1/sessions/%s" % session_id)


func _send(operation: String, method: HTTPClient.Method, path: String, payload := {}) -> void:
	if _http.get_http_client_status() != HTTPClient.STATUS_DISCONNECTED:
		request_failed.emit("A request is already in progress.")
		return
	_operation = operation
	var headers := PackedStringArray(["Content-Type: application/json"])
	var body := "" if method == HTTPClient.METHOD_GET else JSON.stringify(payload)
	var error := _http.request(base_url + path, headers, method, body)
	if error != OK:
		_operation = ""
		request_failed.emit("Could not start HTTP request (error %s)." % error)


func _on_request_completed(
	result: int,
	response_code: int,
	_headers: PackedStringArray,
	body: PackedByteArray,
) -> void:
	var operation := _operation
	_operation = ""
	var decoded = JSON.parse_string(body.get_string_from_utf8())
	var data: Dictionary = decoded if decoded is Dictionary else {}
	if result != HTTPRequest.RESULT_SUCCESS or response_code < 200 or response_code >= 300:
		request_failed.emit(str(data.get("error", "Bridge request failed (HTTP %s)." % response_code)))
		return

	match operation:
		"health":
			health_received.emit(data)
		"start":
			session_started.emit(data)
		"message":
			message_received.emit(data)
		"reflection":
			reflection_received.emit(data)
		"reset":
			session_reset.emit(data)
		_:
			request_failed.emit("Received a response for an unknown operation.")
