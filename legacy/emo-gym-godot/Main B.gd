
extends Panel

@export var event_text: String  # 在编辑器中设置事件文本
var agent_name: String = "Don"  # 默认为 Don，可动态设置

@onready var label = $RichTextLabel
@onready var btn = $eventButton
@onready var http = $HTTPRequest

func _ready():
	btn.text = "I submitted the project too late and missed the review session."
	btn.pressed.connect(_on_pressed)
	http.request_completed.connect(_on_request_completed)

# ✅ 外部设置 agent name（访谈结束后调用）
func set_agent_name(name: String) -> void:
	agent_name = name

# ✅ 点击按钮后发出事件请求
func _on_pressed():
	var json_body = JSON.stringify({
		"event": event_text,
		"agent_name": agent_name
	})

	http.request(
		"http://127.0.0.1:5000/simulate_event",
		["Content-Type: application/json"],
		HTTPClient.METHOD_POST,
		json_body
	)

# ✅ 接收返回内容并显示反思
func _on_request_completed(result, code, headers, body):
	if code == 200:
		var data = JSON.parse_string(body.get_string_from_utf8())

		# 关闭所有事件按钮面板（E1/E2/E3）
		for sibling in get_parent().get_children():
			if sibling.name.begins_with("E"):
				sibling.visible = false

		# 激活中央展示 ReflectionPanel
		var reflection = get_tree().get_root().get_node("ReflectionPanel")
		reflection.show_reflection(data)
