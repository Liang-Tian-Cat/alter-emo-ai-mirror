extends Panel

@onready var button = $RestartButton
@onready var http = $HTTPRequest

var server_url = "http://127.0.0.1:5000/reset_interview"

func _ready():
	button.pressed.connect(_on_restart_pressed)
	http.request_completed.connect(_on_http_done)

func _on_restart_pressed():
	print("🔁 发送重置请求中...")
	http.request(
		server_url,
		["Content-Type: application/json"],
		HTTPClient.METHOD_POST
	)

func _on_http_done(result, response_code, headers, body):
	if response_code == 200:
		print("✅ 访谈会话已重置成功")
	else:
		print("❌ 重置失败，状态码:", response_code)
