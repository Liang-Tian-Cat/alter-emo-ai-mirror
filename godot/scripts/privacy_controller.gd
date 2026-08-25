extends Control

@onready var api: AlterEmoApi = $Api
@onready var persona_input: LineEdit = $Margin/Column/Top/Persona
@onready var memory_list: ItemList = $Margin/Column/Memories
@onready var editor: TextEdit = $Margin/Column/Editor
@onready var status: Label = $Margin/Column/Status

var memories: Array = []
var selected_id := ""


func _ready() -> void:
	persona_input.text = str(ProjectSettings.get_setting("alter_emo/persona_id", "demo-persona"))
	$Margin/Column/Top/Load.pressed.connect(_load_memories)
	$Margin/Column/Actions/Save.pressed.connect(_save_selected)
	$Margin/Column/Actions/Delete.pressed.connect(_delete_selected)
	$Margin/Column/Actions/Pause.toggled.connect(_pause_memory)
	$Margin/Column/Actions/Export.pressed.connect(_export)
	$Margin/Column/Revoke.pressed.connect(_revoke_consent)
	$Margin/Column/Back.pressed.connect(_back)
	memory_list.item_selected.connect(_select_memory)
	api.memories_received.connect(_on_memories)
	api.memory_revised.connect(_on_memory_revised)
	api.memory_deleted.connect(_on_memory_deleted)
	api.memory_state_received.connect(_on_memory_state)
	api.export_received.connect(_on_export)
	api.consent_changed.connect(_on_consent_changed)
	api.request_failed.connect(_on_failed)
	_load_memories()


func _persona() -> String:
	return persona_input.text.strip_edges() if not persona_input.text.strip_edges().is_empty() else "demo-persona"


func _load_memories() -> void:
	status.text = "Loading private memory stream…"
	api.list_memories(_persona())


func _select_memory(index: int) -> void:
	if index < 0 or index >= memories.size():
		return
	var item: Dictionary = memories[index]
	selected_id = str(item.get("id", ""))
	editor.text = str(item.get("content", ""))
	status.text = "Selected %s · salience %.3f" % [selected_id, float((item.get("salience", {}) as Dictionary).get("score", 0.0))]


func _save_selected() -> void:
	if not selected_id.is_empty() and not editor.text.strip_edges().is_empty():
		api.revise_memory(_persona(), selected_id, editor.text.strip_edges())


func _delete_selected() -> void:
	if not selected_id.is_empty():
		api.delete_memory(_persona(), selected_id)


func _pause_memory(paused: bool) -> void:
	api.set_memory_paused(_persona(), paused)


func _export() -> void:
	api.export_persona(_persona())


func _revoke_consent() -> void:
	api.revoke_persona_consent(_persona())


func _back() -> void:
	get_tree().change_scene_to_file("res://Main.tscn")


func _on_memories(data: Dictionary) -> void:
	memories = data.get("items", [])
	memory_list.clear()
	for item in memories:
		memory_list.add_item("%s · %s" % [str(item.get("type", "memory")), str(item.get("summary", item.get("content", ""))).left(70)])
	status.text = "%s long-term memories · select one to inspect" % data.get("total", 0)


func _on_memory_revised(_data: Dictionary) -> void:
	status.text = "Memory revised and semantic embedding refreshed"
	_load_memories()


func _on_memory_deleted(_data: Dictionary) -> void:
	selected_id = ""
	editor.clear()
	status.text = "Memory deleted"
	_load_memories()


func _on_memory_state(data: Dictionary) -> void:
	status.text = "Long-term writes paused" if data.get("memory_paused", false) else "Long-term writes resumed"


func _on_export(data: PackedByteArray) -> void:
	var path := "user://%s-alter-emo-export.zip" % _persona()
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file:
		file.store_buffer(data)
		file.close()
	status.text = "Export saved: %s" % ProjectSettings.globalize_path(path)


func _on_consent_changed(_data: Dictionary) -> void:
	status.text = "Consent revoked. Long-term memory is stopped until you explicitly grant it again."


func _on_failed(message: String) -> void:
	status.text = "Privacy operation failed: %s" % message
