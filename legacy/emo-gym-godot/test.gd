extends Node

@onready var btn := $simulateButton
@onready var label := $outputLabel
@onready var http := $http

var server_url := "http://127.0.0.1:5000/simulate_event"

func _ready():
	btn.text = "📥 Test Reflection"
	btn.pressed.connect(_on_button_pressed)
	http.request_completed.connect(_on_request_done)


func _on_button_pressed():
	var event_data = {
		"agent_name": "K",  # ✅ 换成你已有的 Agent 名字
		"event": "Switching careers midway, I often feel out of place among others who seem more experienced, better suited, and even younger. Starting over has challenged both my confidence and sense of identity."
	}
	var json_body := JSON.stringify(event_data)

	http.request(
		server_url,
		["Content-Type: application/json"],
		HTTPClient.METHOD_POST,
		json_body
	)
	label.text = "⏳ Sending event to agent..."


func _on_request_done(result, response_code, headers, body):
	if response_code == 200:
		var res = JSON.parse_string(body.get_string_from_utf8())
		label.text = "✅ Reflection:\n\n"
		label.text += "[b]Recall:[/b] " + res.get("first_person_recall", "") + "\n\n"
		label.text += "[b]Reflection:[/b] " + res.get("reflection", "") + "\n\n"
		label.text += "[b]Better?:[/b] " + res.get("what_could_be_better", "") + "\n\n"
		label.text += "[b]Support:[/b] " + res.get("supportive_self_talk", "")
	else:
		label.text = "❌ Error: " + str(response_code) + "\n" + body.get_string_from_utf8()
