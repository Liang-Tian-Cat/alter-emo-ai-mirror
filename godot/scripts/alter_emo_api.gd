extends Node
class_name AlterEmoApi

signal health_received(data: Dictionary)
signal session_started(data: Dictionary)
signal message_received(data: Dictionary)
signal reflection_received(data: Dictionary)
signal session_reset(data: Dictionary)
signal perspectives_received(data: Dictionary)
signal narrative_received(data: Dictionary)
signal memory_state_received(data: Dictionary)
signal perspective_changed(data: Dictionary)
signal recording_received(data: Dictionary)
signal speech_received(audio: PackedByteArray)
signal export_received(data: PackedByteArray)
signal memories_received(data: Dictionary)
signal memory_revised(data: Dictionary)
signal memory_deleted(data: Dictionary)
signal consent_changed(data: Dictionary)
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


func start_session(persona_id: String, interlocutor := "self", perspective := "balanced", consent := false) -> void:
	_send("start", HTTPClient.METHOD_POST, "/v1/sessions", {
		"persona_id": persona_id,
		"interlocutor": interlocutor,
		"perspective": perspective,
		"consent": consent,
		"consent_scope": "private-reflection",
	})


func get_perspectives() -> void:
	_send("perspectives", HTTPClient.METHOD_GET, "/v1/perspectives")


func set_perspective(session_id: String, perspective: String) -> void:
	_send("perspective", HTTPClient.METHOD_PUT, "/v1/sessions/%s/perspective" % session_id, {
		"perspective": perspective,
	})


func add_daily_narrative(persona_id: String, content: String) -> void:
	_send("narrative", HTTPClient.METHOD_POST, "/v1/personas/%s/narratives" % persona_id.uri_encode(), {
		"content": content,
	})


func set_memory_paused(persona_id: String, paused: bool) -> void:
	_send("memory_state", HTTPClient.METHOD_PUT, "/v1/personas/%s/memory-state" % persona_id.uri_encode(), {
		"paused": paused,
	})


func start_recording() -> void:
	_send("record_start", HTTPClient.METHOD_POST, "/start_recording")


func stop_recording() -> void:
	_send("record_stop", HTTPClient.METHOD_POST, "/stop_recording")


func speak(text: String) -> void:
	_send("speech", HTTPClient.METHOD_POST, "/v1/audio/speech", {"text": text})


func export_persona(persona_id: String) -> void:
	_send("export", HTTPClient.METHOD_GET, "/v1/personas/%s/export" % persona_id.uri_encode())


func list_memories(persona_id: String) -> void:
	_send("memories", HTTPClient.METHOD_GET, "/v1/personas/%s/memories?limit=500" % persona_id.uri_encode())


func revise_memory(persona_id: String, memory_id: String, content: String) -> void:
	_send("memory_revise", HTTPClient.METHOD_PATCH, "/v1/personas/%s/memories/%s" % [persona_id.uri_encode(), memory_id.uri_encode()], {
		"content": content,
		"summary": content.left(120),
	})


func delete_memory(persona_id: String, memory_id: String) -> void:
	_send("memory_delete", HTTPClient.METHOD_DELETE, "/v1/personas/%s/memories/%s" % [persona_id.uri_encode(), memory_id.uri_encode()])


func revoke_persona_consent(persona_id: String) -> void:
	_send("consent_revoke", HTTPClient.METHOD_PUT, "/v1/personas/%s/consent" % persona_id.uri_encode(), {
		"granted": false,
		"scope": "none",
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
	if result == HTTPRequest.RESULT_SUCCESS and response_code >= 200 and response_code < 300:
		if operation == "speech":
			speech_received.emit(body)
			return
		if operation == "export":
			export_received.emit(body)
			return
	var decoded = JSON.parse_string(body.get_string_from_utf8())
	var data: Dictionary = decoded if decoded is Dictionary else {}
	if result != HTTPRequest.RESULT_SUCCESS or response_code < 200 or response_code >= 300:
		request_failed.emit(str(data.get("error", "Bridge request failed (HTTP %s)." % response_code)))
		return

	match operation:
		"health":
			health_received.emit(data)
		"perspectives":
			perspectives_received.emit(data)
		"start":
			session_started.emit(data)
		"perspective":
			perspective_changed.emit(data)
		"message":
			message_received.emit(data)
		"reflection":
			reflection_received.emit(data)
		"reset":
			session_reset.emit(data)
		"narrative":
			narrative_received.emit(data)
		"memory_state":
			memory_state_received.emit(data)
		"memories":
			memories_received.emit(data)
		"memory_revise":
			memory_revised.emit(data)
		"memory_delete":
			memory_deleted.emit(data)
		"consent_revoke":
			consent_changed.emit(data)
		"record_start", "record_stop":
			recording_received.emit(data)
		_:
			request_failed.emit("Received a response for an unknown operation.")
