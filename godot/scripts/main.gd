extends Control

@onready var api: AlterEmoApi = $Api
@onready var persona_input: LineEdit = $Margin/Column/PersonaRow/Persona
@onready var start_button: Button = $Margin/Column/PersonaRow/Start
@onready var perspective_option: OptionButton = $Margin/Column/ConsentRow/Perspective
@onready var consent_check: CheckBox = $Margin/Column/ConsentRow/Consent
@onready var status_label: Label = $Margin/Column/Status
@onready var transcript: RichTextLabel = $Margin/Column/Transcript
@onready var message_input: TextEdit = $Margin/Column/Message
@onready var send_button: Button = $Margin/Column/Send
@onready var event_input: LineEdit = $Margin/Column/EventRow/Event
@onready var reflect_button: Button = $Margin/Column/EventRow/Reflect
@onready var reset_button: Button = $Margin/Column/Reset
@onready var world_button: Button = $Margin/Column/World
@onready var privacy_button: Button = $Margin/Column/Privacy
@onready var record_button: Button = $Margin/Column/VoiceRow/Record
@onready var speak_button: Button = $Margin/Column/VoiceRow/Speak
@onready var export_button: Button = $Margin/Column/VoiceRow/Export
@onready var narrative_input: TextEdit = $Margin/Column/Narrative
@onready var narrative_button: Button = $Margin/Column/NarrativeRow/SaveNarrative
@onready var memory_pause: CheckButton = $Margin/Column/NarrativeRow/PauseMemory
@onready var audio_player: AudioStreamPlayer = $AudioPlayer

var session_id := ""
var stage := "interview"
var persona_id := "demo-persona"
var is_recording := false
var last_mirror_reply := ""
var perspective_ids: Array[String] = []


func _ready() -> void:
	start_button.pressed.connect(_start_session)
	send_button.pressed.connect(_send_message)
	reflect_button.pressed.connect(_reflect_event)
	reset_button.pressed.connect(_reset_session)
	world_button.pressed.connect(_open_world)
	privacy_button.pressed.connect(_open_privacy)
	record_button.pressed.connect(_toggle_recording)
	speak_button.pressed.connect(_speak_last_reply)
	export_button.pressed.connect(_export_persona)
	narrative_button.pressed.connect(_save_narrative)
	memory_pause.toggled.connect(_set_memory_paused)
	perspective_option.item_selected.connect(_set_perspective)
	message_input.gui_input.connect(_on_message_input)
	api.health_received.connect(_on_health)
	api.session_started.connect(_on_session_started)
	api.message_received.connect(_on_message_received)
	api.reflection_received.connect(_on_reflection_received)
	api.session_reset.connect(_on_session_reset)
	api.request_failed.connect(_on_request_failed)
	api.perspectives_received.connect(_on_perspectives)
	api.narrative_received.connect(_on_narrative_received)
	api.memory_state_received.connect(_on_memory_state)
	api.perspective_changed.connect(_on_perspective_changed)
	api.recording_received.connect(_on_recording_received)
	api.speech_received.connect(_on_speech_received)
	api.export_received.connect(_on_export_received)
	api.check_health()
	api.get_perspectives()


func _open_world() -> void:
	get_tree().change_scene_to_file("res://scenes/MirrorWorld.tscn")


func _open_privacy() -> void:
	ProjectSettings.set_setting("alter_emo/persona_id", persona_id)
	get_tree().change_scene_to_file("res://scenes/Privacy.tscn")


func _start_session() -> void:
	persona_id = persona_input.text.strip_edges()
	if persona_id.is_empty():
		persona_id = "demo-persona"
	ProjectSettings.set_setting("alter_emo/persona_id", persona_id)
	if not consent_check.button_pressed:
		status_label.text = "Consent is required before any personal memory is stored."
		return
	var perspective := perspective_ids[perspective_option.selected] if perspective_option.selected >= 0 and perspective_option.selected < perspective_ids.size() else "balanced"
	_set_busy(true, "Starting private session…")
	api.start_session(persona_id, "self", perspective, true)


func _set_perspective(index: int) -> void:
	if session_id.is_empty() or index < 0 or index >= perspective_ids.size():
		return
	api.set_perspective(session_id, perspective_ids[index])


func _save_narrative() -> void:
	var content := narrative_input.text.strip_edges()
	if session_id.is_empty() or content.is_empty():
		return
	_set_busy(true, "Parsing events, feelings, choices, and values…")
	api.add_daily_narrative(persona_id, content)


func _set_memory_paused(paused: bool) -> void:
	if session_id.is_empty():
		return
	api.set_memory_paused(persona_id, paused)


func _toggle_recording() -> void:
	_set_busy(true, "Stopping and transcribing…" if is_recording else "Starting microphone…")
	if is_recording:
		api.stop_recording()
	else:
		api.start_recording()


func _speak_last_reply() -> void:
	if not last_mirror_reply.is_empty():
		api.speak(last_mirror_reply)


func _export_persona() -> void:
	if not session_id.is_empty():
		_set_busy(true, "Exporting your private data…")
		api.export_persona(persona_id)


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
		last_mirror_reply = reply
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


func _on_perspectives(data: Dictionary) -> void:
	perspective_option.clear()
	perspective_ids.clear()
	for item in data.get("items", []):
		perspective_ids.append(str(item.get("id", "balanced")))
		perspective_option.add_item(str(item.get("name", item.get("id", "Perspective"))))


func _on_narrative_received(data: Dictionary) -> void:
	narrative_input.clear()
	transcript.append_text("\n[color=#9fe6bd]Daily narrative saved:[/color] %s events · %s choices\n" % [
		data.get("events", []).size(), data.get("choices", []).size()
	])
	_set_busy(false, "Narrative parsed and salience-gated")


func _on_memory_state(data: Dictionary) -> void:
	status_label.text = "Long-term memory paused" if data.get("memory_paused", false) else "Long-term memory active"


func _on_perspective_changed(data: Dictionary) -> void:
	status_label.text = "Perspective: %s" % str(data.get("perspective", "balanced"))


func _on_recording_received(data: Dictionary) -> void:
	is_recording = bool(data.get("recording", false))
	record_button.text = "Stop & transcribe" if is_recording else "Record"
	if data.has("transcript"):
		var spoken := str(data.get("transcript", ""))
		transcript.append_text("\n[color=#f0d1ff]You (voice):[/color] %s\n" % spoken)
		stage = str(data.get("stage", stage))
		var reply := str(data.get("question", ""))
		if reply.is_empty():
			reply = str(data.get("reply", ""))
		if not reply.is_empty():
			transcript.append_text("[color=#9fe6bd]Mirror:[/color] %s\n" % reply)
			last_mirror_reply = reply
	_set_busy(false, "Recording" if is_recording else "Voice processed")


func _on_speech_received(audio: PackedByteArray) -> void:
	var stream := AudioStreamMP3.load_from_buffer(audio)
	if stream:
		audio_player.stream = stream
		audio_player.play()
	status_label.text = "Speaking mirror reply"


func _on_export_received(data: PackedByteArray) -> void:
	var path := "user://%s-alter-emo-export.zip" % persona_id
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file:
		file.store_buffer(data)
		file.close()
	status_label.text = "Export saved: %s" % ProjectSettings.globalize_path(path)


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
