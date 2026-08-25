extends CharacterBody2D

signal clicked

@onready var sprite = $AnimatedSprite2D
@onready var nav_agent = $NavigationAgent2D

@onready var sofa_target = get_node("/root/Gpt/NavigationRegion2D/sofa")
@onready var eat_target = get_node("/root/Gpt/NavigationRegion2D/eat")
@onready var cook_target = get_node("/root/Gpt/NavigationRegion2D/cook")
@onready var study_target = get_node("/root/Gpt/NavigationRegion2D/study")
@onready var light_target = get_node("/root/Gpt/NavigationRegion2D/light")

@onready var dialogue_panel = get_parent().get_node("DialoguePanel")
@onready var interview_panel = get_parent().get_node("InterviewPanel")
@onready var start_button = get_parent().get_node("DialoguePanel/InterviewButton")

@export var icon : Texture
@export_multiline var physical_description : String
@export_multiline var location_description : String
@export_multiline var personality : String
@export_multiline var secret_knowledge : String

var speed : float = 60.0
var is_auto_moving := false
var final_animation: String = ""
var just_arrived := false

var random_actions = []  # ✅ 随机行动列表
var autonomous_mode := true  # ✅ 是否自动巡逻

func _ready():
	print("🗺️ 初始位置：", global_position)

	# 面板初始隐藏
	dialogue_panel.visible = false
	interview_panel.visible = false

	# 点击连接
	$ClickArea.input_event.connect(_on_input_event)
	start_button.pressed.connect(_on_start_pressed)

	# ✅ 初始化自动巡逻目标列表
	random_actions = [
		{ "target": sofa_target, "anim": "reading" },
		{ "target": eat_target, "anim": "idle_right" },
		{ "target": cook_target, "anim": "idle_back" },
		{ "target": light_target, "anim": "idle_left" },
		{ "target": study_target, "anim": "idle_front" }
	]

	# ✅ 开始自动巡逻协程
	_auto_random_walk()

func _physics_process(delta):
	if is_auto_moving:
		_auto_move_to_target(delta)
	else:
		_manual_player_control(delta)

func _process(delta):
	if Input.is_action_just_pressed("go_to_sofa"):
		go_to(sofa_target.global_position, "reading")
	if Input.is_action_just_pressed("go_to_eat"):
		go_to(eat_target.global_position, "idle_right")
	if Input.is_action_just_pressed("go_to_cook"):
		go_to(cook_target.global_position, "idle_back")
	if Input.is_action_just_pressed("turn_light"):
		go_to(light_target.global_position, "idle_left")

# ✅ 点击角色触发对话框
func _on_input_event(viewport, event, shape_idx):
	if event is InputEventMouseButton and event.pressed:
		dialogue_panel.begin_typing()

# ✅ 点击按钮进入访谈
func _on_start_pressed():
	dialogue_panel.visible = false
	interview_panel.visible = true

# ✅ 手动控制
func _manual_player_control(delta):
	var dir = Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
	velocity = dir * speed
	move_and_slide()
	_play_walk_animation(dir)

# ✅ 自动导航逻辑
func go_to(target: Vector2, final_anim := ""):
	final_animation = final_anim
	just_arrived = false

	var nav_map_rid = nav_agent.get_navigation_map()
	var fixed_target = target

	if nav_map_rid.is_valid():
		fixed_target = NavigationServer2D.map_get_closest_point(nav_map_rid, target)
	else:
		print("⚠️ 无效的导航地图 RID！")

	nav_agent.set_target_position(fixed_target)
	is_auto_moving = true

	await get_tree().process_frame
	print("🎯 原目标点：", target)
	print("📍 修正后目标点：", fixed_target)
	print("🛣️ 当前路径：", nav_agent.get_current_navigation_path())

func _auto_move_to_target(delta):
	if nav_agent.is_navigation_finished():
		is_auto_moving = false
		velocity = Vector2.ZERO
		just_arrived = true

		if final_animation != "":
			print("🎬 播放动画：", final_animation)
			sprite.play(final_animation)
		else:
			sprite.play("idle_front")

		print("✅ 已到达目标")
		return

	if just_arrived:
		return

	var next_point = nav_agent.get_next_path_position()
	if next_point == Vector2.ZERO:
		print("⚠️ 路径无效，跳过")
		return

	var dir = (next_point - global_position).normalized()
	velocity = dir * speed
	move_and_slide()
	_play_walk_animation(dir)

	if global_position.distance_to(next_point) < 4.0:
		nav_agent.advance_to_next_path_position()

# ✅ 行走动画播放
func _play_walk_animation(dir: Vector2):
	if dir == Vector2.ZERO:
		if not just_arrived:
			sprite.play("idle_front")
	elif abs(dir.x) > abs(dir.y):
		sprite.play("walk_right" if dir.x > 0 else "walk_left")
	else:
		sprite.play("walk_front" if dir.y > 0 else "walk_back")

# ✅ 自动巡逻逻辑（无限循环）
func _auto_random_walk():
	await get_tree().process_frame  # 确保初始化完成

	while true:
		await get_tree().create_timer(randf_range(5.0, 9.0)).timeout

		if !autonomous_mode or is_auto_moving:
			continue

		var action = random_actions[randi() % random_actions.size()]
		go_to(action["target"].global_position, action["anim"])

func pause_autonomous_and_face_player():
	print("⏸️ 停止导航、停止巡逻、面向前方")

	# ✅ 关闭自动巡逻模式
	autonomous_mode = false

	# ✅ 停止移动
	is_auto_moving = false
	velocity = Vector2.ZERO
	move_and_slide()

	# ✅ 清除导航路径（立即终止导航）
	if nav_agent.is_navigation_finished() == false:
		nav_agent.set_target_position(global_position)  # 强制目标设为当前位置
		if nav_agent.has_method("clear_path"):
			nav_agent.clear_path()  # ✅ Godot 4.2+

	# ✅ 播放朝向前方的 idle 动画（面向玩家）
	sprite.play("idle_front")

func resume_autonomous_mode():
	print("▶️ 恢复角色自主巡逻")
	autonomous_mode = true
	is_auto_moving = false  # 可以设为 true 触发一次导航
