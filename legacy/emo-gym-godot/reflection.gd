extends Panel

@onready var label = $RichTextLabel
@onready var restart_button = $RestartButton
@onready var http = $HTTPRequest


var reflection_data := {}
var content_keys := [
	"first_person_recall",
	"reflection",
	"what_could_be_better",
	"supportive_self_talk"
]
var current_index := 0
var is_typing := false

func _ready():
	visible = false
	restart_button.visible = false
	restart_button.text = "Have REPORT"
	restart_button.pressed.connect(_on_restart_button_pressed)
	http.request_completed.connect(_on_reset_complete)

# ✅ 主入口：展示反思内容
func show_reflection(data: Dictionary, agent_name: String) -> void:
	reflection_data = data
	current_index = 0
	label.clear()
	visible = true
	restart_button.visible = false
	await get_tree().create_timer(0.5).timeout
	await _play_all_parts()

# ✅ 自动播放每段内容（段落间隔 + 打字机效果）
func _play_all_parts():
	while current_index < content_keys.size():
		var key = content_keys[current_index]
		var content = reflection_data.get(key, "")

		label.clear()
		is_typing = true
		await typewriter_append(content)
		is_typing = false

		current_index += 1
		await get_tree().create_timer(1.0).timeout

	restart_button.visible = true

# ✅ 打字机效果
func typewriter_append(text: String) -> void:
	for i in text.length():
		label.append_text(text[i])
		await get_tree().create_timer(0.05).timeout

# ✅ 点击按钮：通知 Python 重置访谈状态
func _on_restart_button_pressed():
	print("🔁 请求重置访谈状态")

	# ✅ 先请求打印小票
	var print_url = "http://127.0.0.1:5000/simulate_and_print"
	var headers = ["Content-Type: application/json"]  # ✅ 添加请求头
	var body = "{}"  # ✅ 发送空 JSON 也可以
	var err = http.request(print_url, headers, HTTPClient.METHOD_POST, body)
	if err != OK:
		print("❌ 打印请求失败，错误码: ", err)
	else:
		print("🖨️ 已向 Python 请求打印小票")

	# ✅ 再请求重置访谈状态
	var reset_url = "http://127.0.0.1:5000/reset_interview"
	http.request(reset_url, [], HTTPClient.METHOD_POST)

	# ✅ 清空界面
	label.clear()
	visible = false
	restart_button.visible = false

	# ✅ 隐藏采访面板
	var interview_panel = get_tree().get_root().get_node_or_null("Gpt/Player/InterviewPanel")
	if interview_panel:
		interview_panel.visible = false
	else:
		print("⚠️ InterviewPanel 节点未找到")

	# ✅ 恢复角色自由行动
	var player = get_tree().get_root().get_node_or_null("Gpt/Player")
	if player and player.has_method("resume_autonomous_mode"):
		player.resume_autonomous_mode()
	else:
		print("⚠️ 未找到 player 节点或其缺少 resume_autonomous_mode 方法")

	# ✅ 恢复 DialogueBox（随机说话面板）
	var dialogue_box = get_tree().get_root().get_node_or_null("Gpt/Player/DialogueBox")
	if dialogue_box:
		dialogue_box.visible = true
		var timer = dialogue_box.get_node_or_null("Timer")
		if timer:
			timer.start()
			print("⏱️ DialogueBox 定时器已重新启动")
	else:
		print("⚠️ DialogueBox 未找到或未命名为 DialogueBox")


# ✅ 当 Python 完成重置后打印确认（可用于调试）
func _on_reset_complete(result, code, headers, body):
	if code == 200:
		print("✅ Python 会话已重置，等待用户点击角色重新开始采访")
	else:
		push_error("❌ Python 重置失败，状态码: " + str(code))
