extends Control

@onready var api: AlterEmoApi = $Api
@onready var persona_input: LineEdit = $Margin/Column/PersonaRow/Persona
@onready var start_button: Button = $Margin/Column/PersonaRow/Start
@onready var status_label: Label = $Margin/Column/Status
@onready var transcript: RichTextLabel = $Margin/Column/Transcript
@onready var message_input: TextEdit = $Margin/Column/Message
@onready var send_button: Button = $Margin/Column/Send
@onready var event_input: LineEdit = $Margin/Column/EventRow/Event
@onready var reflect_button: Button = $Margin/Column/EventRow/Reflect
@onready var reset_button: Button = $Margin/Column/Reset
@onready var world_button: Button = $Margin/Column/World

var session_id := ""
var stage := "interview"


func _ready() -> void:
	start_button.pressed.connect(_start_session)
	send_button.pressed.connect(_send_message)
	reflect_button.pressed.connect(_reflect_event)
	reset_button.pressed.connect(_reset_session)
	world_button.pressed.connect(_open_world)
	message_input.gui_input.connect(_on_message_input)
	api.health_received.connect(_on_health)
	api.session_started.connect(_on_session_started)
	api.message_received.connect(_on_message_received)
	api.reflection_received.connect(_on_reflection_received)
	api.session_reset.connect(_on_session_reset)
	api.request_failed.connect(_on_request_failed)
	api.check_health()


func _open_world() -> void:
	get_tree().change_scene_to_file("res://scenes/MirrorWorld.tscn")


func _start_session() -> void:
	var persona := persona_input.text.strip_edges()
	if persona.is_empty():
		persona = "demo-persona"
	_set_busy(true, "Starting private session…")
	api.start_session(persona)


func _send_message() -> void:
	var content := message_input.text.strip_edges()
	if session_id.is_empty() or content.is_empty():
		return
	transcript.append_text("\n[color=#f0d1ff]You:[/color] %s\n" % content)
	message_input.clear()
	_set_busy(true, "Thinking…")
	api.send_message(session_id, content)


func _reflect_event() -> void:
	var event := event_input.text.strip_edges()
	if session_id.is_empty() or event.is_empty() or stage != "mirror":
		return
	transcript.append_text("\n[color=#f0d1ff]Event:[/color] %s\n" % event)
	event_input.clear()
	_set_busy(true, "Reopening relevant narrative memory…")
	api.reflect_event(session_id, event)


func _reset_session() -> void:
	if session_id.is_empty():
		return
	_set_busy(true, "Removing session…")
	api.reset_session(session_id)


func _on_message_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and event.keycode == KEY_ENTER and event.ctrl_pressed:
		_send_message()
		accept_event()


func _on_health(data: Dictionary) -> void:
	var capabilities: Dictionary = data.get("capabilities", {})
	status_label.text = "Bridge ready · text %s · event reflection %s" % [
		_enabled_word(bool(capabilities.get("text", false))),
		_enabled_word(bool(capabilities.get("events", false))),
	]


func _on_session_started(data: Dictionary) -> void:
	session_id = str(data.get("session_id", ""))
	stage = str(data.get("stage", "interview"))
	transcript.clear()
	transcript.append_text("[color=#9fe6bd]Mirror session %s started.[/color]\n" % session_id)
	_append_question(data)
	_set_busy(false, "Adaptive interview in progress")
	reset_button.disabled = false


func _on_message_received(data: Dictionary) -> void:
	stage = str(data.get("stage", stage))
	var reply := str(data.get("reply", ""))
	if not reply.is_empty() and reply != "Answer captured.":
		transcript.append_text("[color=#9fe6bd]Mirror:[/color] %s\n" % reply)
	_append_question(data)
	var ready := stage == "mirror"
	_set_busy(false, "Mirror ready" if ready else "Adaptive interview in progress")
	reflect_button.disabled = not ready


func _on_reflection_received(data: Dictionary) -> void:
	transcript.append_text("\n[color=#9fe6bd]Recall:[/color] %s\n" % data.get("first_person_recall", ""))
	transcript.append_text("[color=#9fe6bd]Reflection:[/color] %s\n" % data.get("reflection", ""))
	transcript.append_text("[color=#9fe6bd]Try next:[/color] %s\n" % data.get("what_could_be_better", ""))
	transcript.append_text("[color=#9fe6bd]Self-talk:[/color] %s\n" % data.get("supportive_self_talk", ""))
	_set_busy(false, "Mirror ready")


func _on_session_reset(_data: Dictionary) -> void:
	session_id = ""
	stage = "interview"
	transcript.text = "[color=#b8afc7]Session removed. Start again when ready.[/color]"
	send_button.disabled = true
	reflect_button.disabled = true
	reset_button.disabled = true
	start_button.disabled = false
	status_label.text = "No active session"


func _on_request_failed(message: String) -> void:
	status_label.text = "Bridge error: %s" % message
	start_button.disabled = false
	send_button.disabled = session_id.is_empty()
	reflect_button.disabled = session_id.is_empty() or stage != "mirror"
	reset_button.disabled = session_id.is_empty()


func _append_question(data: Dictionary) -> void:
	var question = data.get("question")
	if question != null and not str(question).is_empty():
		transcript.append_text("[color=#9fe6bd]Mirror asks:[/color] %s\n" % question)


func _set_busy(busy: bool, message: String) -> void:
	status_label.text = message
	start_button.disabled = busy
	send_button.disabled = busy or session_id.is_empty()
	reflect_button.disabled = busy or session_id.is_empty() or stage != "mirror"
	reset_button.disabled = busy or session_id.is_empty()


func _enabled_word(value: bool) -> String:
	return "on" if value else "off"
