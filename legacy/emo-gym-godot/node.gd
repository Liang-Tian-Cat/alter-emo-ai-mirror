extends Node
#
#var api_key : String = OS.get_environment("OPENAI_API_KEY")  # Sanitized legacy reference; never embed keys.
#var url : String = "https://api.openai.com/v1/chat/completions"
#var temperature : float = 0.5
#var max_tokens : int = 1024
#var headers = ["Content-type: application/json", "Authorization: Bearer " + api_key]
#var model : String = "gpt-4o-mini"
#var messages = []
#var request : HTTPRequest
#
#@onready var dialogue_box = get_node("/root/Gpt/Player/DialogueBox")
#@export var default_npc : Node
#@export_multiline var dialogue_rules : String
#
#var Player
#var is_manual_dialogue := false
#var is_npc_thinking := false
#var is_request_pending := false  # 新增：防止重复请求
#
#signal on_player_talk
#signal on_npc_talk(npc_dialogue)
#
#var think_timer := Timer.new()
#var retry_count := 0  # 新增：重试计数器
#var max_retries := 1  # 最大重试次数
#
#func _ready():
	#dialogue_box.visible = false
#
	#request = HTTPRequest.new()
	#add_child(request)
	#request.connect("request_completed", _on_request_completed)
	#
	## 增加超时设置
	#request.timeout = 10.0
#
	#think_timer.wait_time = 30.0
	#think_timer.one_shot = false
	#think_timer.connect("timeout", _on_think_timer_timeout)
	#add_child(think_timer)
#
	#await get_tree().process_frame
	#if default_npc:
		#print("🟢 default_npc detected, starting autonomous thinking...")
		#start_autonomous_thinking(default_npc)
	#else:
		#print("❌ No default_npc found! Please assign one in the Inspector.")
#
#func start_autonomous_thinking(npc):
	#Player = npc
	#is_manual_dialogue = false
	#is_npc_thinking = true
	#dialogue_box.visible = false
	#think_timer.start()
	#if messages.is_empty():
		#dialogue_request()  # 首次思考
	#print("🤖 开启 NPC 自主思考模式")
#
#func enter_new_dialogue(npc):
	#print("🗣️ 玩家开始与 NPC 对话:", npc)
	#Player = npc
	#is_manual_dialogue = true
	#is_npc_thinking = false
	#think_timer.stop()
	#dialogue_box.visible = true
	#dialogue_box.initialize_with_npc(npc)
	#dialogue_request("")
#
#func exit_dialogue():
	#if is_manual_dialogue:
		#print("🚪 玩家结束对话，NPC 恢复自主思考")
		#is_manual_dialogue = false
		#is_npc_thinking = true
		#dialogue_box.visible = false
		#think_timer.start()
		#dialogue_request()
	#else:
		#print("🔁 忽略退出请求，当前为 NPC 自主对话状态")
#
#func dialogue_request(player_dialogue := ""):
	## 防止重复请求
	#if is_request_pending:
		#print("⏸️ 请求进行中，跳过此次请求")
		#return
	#
	#var prompt : String
#
	#if messages.is_empty():
		#prompt = """
#You are a reflective and sentient NPC in a fantasy world. You should observe the current situation, remember your goals, and decide what to say or do next — even if the player says nothing.
#He'll make a random move each round, Choose a random action, not the same every time.
#Always respond with this JSON format:
#
#{
  #"speak": true or false,
  #"dialogue": "<Your reply, no longer than 2 sentences>",
  #"action": "<An action keyword, or null if no action>",
  #"reason": "<Explain why you chose to speak and/or act, or not>"
#}
#
#Available action keywords:
#- "turn_on_lights"
#- "go_to_sofa"
#- "go_to_bed"
#- "drink_water"
#- "null"
#- "idle_right"
#- "idle_left"
#- "idle_front"
#- "idle_back"
#
#You are: """ + Player.physical_description + "\nYour personality is: " + Player.personality + "\nLocation: " + Player.location_description + "\n"
		#prompt += "Here are the dialogue rules:\n" + dialogue_rules + "\n"
		#prompt += "Begin by assessing the current situation and responding accordingly."
	#else:
		#if is_manual_dialogue and player_dialogue != "":
			#prompt = "The player said: \"%s\"\nReflect on it and respond with dialogue, optional action, and reason." % player_dialogue
		#else:
			#prompt = "As a sentient NPC, reflect on the current situation and decide what to say or do next, and why."
#
	## 限制消息历史长度，避免请求过大
	#if messages.size() > 20:
		## 保留系统消息和最近的几条对话
		#var recent_messages = messages.slice(-15)  # 保留最近8条消息
		#messages = recent_messages
		#print("📝 消息历史已清理，保留最近8条消息")
#
	#messages.append({
		#"role": "user",
		#"content": prompt
	#})
#
	#on_player_talk.emit()
#
	#var body = JSON.new().stringify({
		#"messages": messages,
		#"temperature": temperature,
		#"max_tokens": max_tokens,
		#"model": model
	#})
#
	#print("📤 发送请求，当前消息数量:", messages.size())
	#
	#is_request_pending = true
	#var send_request = request.request(url, headers, HTTPClient.METHOD_POST, body)
	#if send_request != OK:
		#print("❌ Error sending request, error code:", send_request)
		#is_request_pending = false
		## 检查常见错误
		#match send_request:
			#ERR_INVALID_PARAMETER:
				#print("❌ 无效参数 - 检查URL或headers")
			#ERR_CANT_CONNECT:
				#print("❌ 无法连接 - 检查网络连接")
			#ERR_CANT_RESOLVE:
				#print("❌ 无法解析域名 - 检查DNS设置")
	#else:
		#print("✅ 请求已发送")
#
#func _on_request_completed(result, response_code, headers, body):
	#is_request_pending = false
	#
	#print("📡 请求完成 - 结果码:", result, "HTTP状态:", response_code)
	#
	## 检查HTTP错误
	#if response_code != 200:
		#print("❌ HTTP错误:", response_code)
		#retry_count += 1
		#if response_code == 401:
			#print("❌ API密钥无效")
		#elif response_code == 429:
			#print("❌ 请求过于频繁，等待重试...")
			#if retry_count <= max_retries:
				#await get_tree().create_timer(2.0).timeout  # 等待2秒后重试
				#dialogue_request()
			#else:
				#print("❌ 重试次数已达上限")
				#retry_count = 0
		#elif response_code == 500:
			#print("❌ 服务器内部错误")
		#return
	#
	## 请求成功，重置重试计数
	#retry_count = 0
	#
	## 检查请求结果
	#if result != HTTPRequest.RESULT_SUCCESS:
		#print("❌ 请求失败，错误类型:", result)
		#return
#
	#var json = JSON.new()
	#var body_string = body.get_string_from_utf8()
	#
	#print("📥 收到原始响应:", body_string.substr(0, 500), "...")  # 显示前500字符
	#
	#if json.parse(body_string) != OK:
		#print("❌ Failed to parse response!")
		#print("完整响应内容:", body_string)
		#return
#
	#var response = json.get_data()
	#print("📋 解析后的响应类型:", typeof(response))
	#print("📋 响应内容:", response)
	#
	#if typeof(response) != TYPE_DICTIONARY:
		#print("❌ 响应不是字典类型，而是:", typeof(response))
		#return
		#
	#if not response.has("choices"):
		#print("❌ 响应中没有 'choices' 字段")
		#print("❌ 可用字段:", response.keys() if response.has_method("keys") else "无法获取字段")
		#
		## 检查是否是错误响应
		#if response.has("error"):
			#print("❌ API 错误:", response["error"])
		#return
#
	#var choices = response["choices"]
	#if typeof(choices) != TYPE_ARRAY or choices.size() == 0:
		#print("❌ 'choices' is empty")
		#return
#
	#var message = choices[0].get("message", {})
	#var content = message.get("content", "")
	#if content == "":
		#print("❌ No content in AI response")
		#return
#
	#var content_json = JSON.new()
	#if content_json.parse(content) != OK:
		#print("❌ AI response is not valid JSON:\n", content)
		#return
#
	#var parsed_response = content_json.get_data()
	#var npc_dialogue = parsed_response.get("dialogue", "")
	#var npc_action = parsed_response.get("action", "null")
	#var should_speak = parsed_response.get("speak", true)
	#var reason = parsed_response.get("reason", "No reason provided.")
#
	#messages.append({
		#"role": "assistant",
		#"content": content
	#})
#
	#print("✅ 请求成功处理")
	#print("🤔 NPC 思考理由：", reason)
	#print("✍ 动作",npc_action)
#
	#if should_speak:
		#dialogue_box.visible = true
		#on_npc_talk.emit(npc_dialogue)
		#print("💬 NPC 说：", npc_dialogue)
		#
		## 只有在自主思考模式下才自动隐藏对话框
		#if not is_manual_dialogue:
			#await get_tree().create_timer(4.0).timeout
			#dialogue_box.visible = false
	#else:
		#print("💭 NPC 选择沉默")
#
	#match npc_action:
		#"go_to_bed":
			#if Player and Player.has_method("go_to_bed"):
				#Player.go_to_bed()
		#"drink_water":
			#if Player and Player.has_method("drink_water"):
				#Player.drink_water()
		#"turn_on_lights":
			#if Player and Player.has_method("turn_on_lights"):
				#Player.turn_on_lights()
		#"go_to_sofa":
			#if Player and Player.has_method("go_to_sofa"):
				#Player.go_to_sofa()
		#"idle_left":
			#if Player and Player.has_method("idle_left"):
				#Player.idle_left()
		#"idle_right":
			#if Player and Player.has_method("idle_right"):
				#Player.idle_right()
		#"idle_front":
			#if Player and Player.has_method("idle_front"):
				#Player.idle_front()
		#"idle_back":
			#if Player and Player.has_method("idle_back"):
				#Player.idle_back()
		#_:
			#pass
#
#func _on_think_timer_timeout():
	#print("⏰ 自主思考触发，当前是否手动对话中：", is_manual_dialogue)
	#if Player and not is_manual_dialogue and not is_request_pending:  # 添加请求状态检查
		#print("🧠 NPC 自主思考...")
		#dialogue_request()
	#elif is_request_pending:
		#print("⏸️ 请求进行中，跳过此次自主思考")
