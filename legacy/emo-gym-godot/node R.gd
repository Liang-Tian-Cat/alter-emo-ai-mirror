extends Panel

@onready var label = $RichTextLabel
@onready var button = $RecordButton
@onready var http = $HTTPRequest
@onready var e1 = $"../Panel/E1"
@onready var e2 = $"../Panel/E2"
@onready var e3 = $"../Panel/E3"
@onready var finish_button = $FinishButton
@onready var text_input = $TextEdit
@onready var send_button = $"Send button"

var recording = false
var server_url = "http://127.0.0.1:5000"
var current_mode = ""
var is_recording = false

# ✅ 打字机相关变量
var typing_speed := 0.05
var typing_timer := Timer.new()
var typing_text := ""
var typing_index := 0

func _ready():
	add_child(typing_timer)
	typing_timer.wait_time = typing_speed
	typing_timer.one_shot = true
	typing_timer.timeout.connect(_on_typing_timer_timeout)

	button.text = "🎙️Click here to Start Record"
	http.request_completed.connect(_on_HTTPRequest_request_completed)
	button.pressed.connect(_on_record_button_pressed)
	send_button.pressed.connect(_on_send_button_pressed)
	connect("visibility_changed", _on_visibility_changed)

	finish_button.visible = false
	e1.visible = false
	e2.visible = false
	e3.visible = false
	text_input.visible = true
	send_button.visible = true
	finish_button.pressed.connect(_on_finish_button_pressed)
	text_input.gui_input.connect(_on_text_edit_gui_input)

func _on_finish_button_pressed():
	self.visible = false
	e1.visible = true
	e2.visible = true
	e3.visible = true

func begin_interview():
	reset_panel()
	print("✅ 访谈正式开始")
	get_next_question()

func _on_visibility_changed():
	print("👁️ InterviewPanel visibility changed. visible =", visible)
	if visible:
		begin_interview()

func _on_record_button_pressed():
	print("🔘 按钮被点击了")
	if is_recording:
		stop_recording()
	else:
		start_recording()

func start_recording():
	is_recording = true
	button.text = "🎙️...Recording...(Click here to Stop)"
	current_mode = "start_recording"
	http.request(server_url + "/start_recording", [], HTTPClient.METHOD_GET)

func stop_recording():
	is_recording = false
	button.text = "🎙️Click here to Start Record"
	current_mode = "stop_recording"
	http.request(server_url + "/stop_recording", [], HTTPClient.METHOD_GET)

func get_next_question():
	current_mode = "question"
	http.request(server_url + "/next_question", [], HTTPClient.METHOD_GET)

func _on_send_button_pressed():
	var user_input = text_input.text.strip_edges()
	if user_input.is_empty():
		show_typing_text("❌ 请输入内容后再发送。", true)
		return

	print("📝 正在发送用户输入文本:", user_input)

	current_mode = "text_input"
	var json_body = JSON.stringify({
		"content": user_input
	})

	http.request(
		server_url + "/text_input",
		["Content-Type: application/json"],
		HTTPClient.METHOD_POST,
		json_body
	)

	text_input.text = ""

func _on_HTTPRequest_request_completed(result, response_code, headers, body):
	var json = JSON.parse_string(body.get_string_from_utf8())
	if json == null:
		label.text = "❌ 无法解析服务器响应"
		return

	if current_mode == "question":
		if json.get("stop", false):
			show_typing_text("🔴", true)
			button.visible = false
			text_input.visible = false
			send_button.visible = false
			finish_button.visible = true
			var agent_name = json.get("agent_name", "Agent")
			print("🧠 接收到 agent_name:", agent_name)
			on_interview_complete(agent_name)
		else:
			show_typing_text(json.get("question", "(无内容)"), true)

	elif current_mode == "stop_recording" or current_mode == "text_input":
		var reply = json.get("reply", "")
		if reply != "":
			show_typing_text(reply, true)
		else:
			show_typing_text("🤖 无有效回复", true)

		if json.get("stop", false):
			show_typing_text("🎉 Interview is complete. Thank you! Choose one of the three events that resonates with you. This will reveal how your personality interprets emotions and how they are formed", true)
			button.visible = false
			text_input.visible = false
			send_button.visible = false
			finish_button.visible = true
			var agent_name = json.get("agent_name", "Agent")
			print("🧠 接收到 agent_name:", agent_name)
			on_interview_complete(agent_name)

		print("📦 服务器响应:", body.get_string_from_utf8())

func reset_panel():
	label.clear()
	current_mode = ""
	is_recording = false

	button.text = "🎙️Click here to Start Record"
	button.disabled = false
	button.visible = true

	finish_button.visible = false
	text_input.visible = true
	text_input.text = ""  # ✅ 清空输入内容
	send_button.visible = true

	# ✅ 关闭事件按钮
	if e1: e1.visible = false
	if e2: e2.visible = false
	if e3: e3.visible = false

# ✅ 打字机逻辑：开始显示文本，可选是否清除旧内容
func show_typing_text(full_text: String, should_clear := true):
	if should_clear:
		label.text = ""
	else:
		label.text += "\n"

	typing_text = full_text
	typing_index = 0
	label.text += typing_text.substr(0, 1)
	typing_index = 1
	typing_timer.start()

# ✅ 打字机逻辑：逐字追加字符
func _on_typing_timer_timeout():
	if typing_index < typing_text.length():
		label.text += typing_text.substr(typing_index, 1)
		typing_index += 1
		typing_timer.start()

# ✅ 当访谈结束，显示事件按钮并传入 agent name
func on_interview_complete(agent_name: String):
	print("📞 [on_interview_complete] 被调用，agent_name =", agent_name)

	var event_panel = get_parent().get_node("Panel")
	if event_panel == null:
		push_error("❌ 找不到事件按钮容器 Main/Panel")
		return

	var found = false
	for child in event_panel.get_children():
		if child.name.begins_with("E"):
			found = true
			if child.has_method("set_agent_name"):
				child.set_agent_name(agent_name)
				print("✅ 已调用 set_agent_name ->", agent_name)
			else:
				push_warning("⚠️ " + child.name + " 没有 set_agent_name 方法")

	if not found:
		push_warning("⚠️ Panel 中没有以 'E' 开头的事件子节点")

	event_panel.visible = true
	print("🎯 事件按钮面板已显示")





func _on_text_edit_gui_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed:
		if event.keycode == KEY_ENTER and not event.shift_pressed:
			_on_send_button_pressed()
