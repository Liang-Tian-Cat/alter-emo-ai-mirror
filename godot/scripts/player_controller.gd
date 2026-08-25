extends CharacterBody2D
class_name MirrorWorldPlayer

signal destination_changed(destination: String)
signal destination_reached(destination: String)

@export var speed := 120.0
@export var autonomous_patrol := true
@export var patrol_delay_range := Vector2(4.0, 7.0)

@onready var navigation_agent: NavigationAgent2D = $NavigationAgent2D

var _targets: Dictionary = {}
var _target_name := ""
var _navigation_active := false
var _manual_control_active := false


func _ready() -> void:
	navigation_agent.path_desired_distance = 4.0
	navigation_agent.target_desired_distance = 8.0
	call_deferred("_start_patrol_loop")


func configure_targets(target_root: Node) -> void:
	_targets.clear()
	for marker in target_root.get_children():
		if marker is Marker2D:
			_targets[marker.name.to_snake_case()] = marker.global_position


func go_to_target(target_name: String) -> void:
	if not _targets.has(target_name):
		push_warning("Unknown mirror-world target: %s" % target_name)
		return
	_target_name = target_name
	_manual_control_active = false
	_navigation_active = true
	navigation_agent.target_position = _targets[target_name]
	destination_changed.emit(target_name)


func pause_autonomous_patrol() -> void:
	autonomous_patrol = false
	_stop_navigation()


func resume_autonomous_patrol() -> void:
	autonomous_patrol = true


func _physics_process(_delta: float) -> void:
	var manual_direction := Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
	if manual_direction != Vector2.ZERO:
		_manual_control_active = true
		_stop_navigation()
		velocity = manual_direction.normalized() * speed
		move_and_slide()
		return

	if _manual_control_active:
		velocity = Vector2.ZERO
		move_and_slide()
		_manual_control_active = false

	if _navigation_active:
		_follow_navigation_path()


func _unhandled_input(event: InputEvent) -> void:
	if event is not InputEventKey or not event.pressed or event.echo:
		return
	match event.keycode:
		KEY_1:
			go_to_target("sofa")
		KEY_2:
			go_to_target("eat")
		KEY_3:
			go_to_target("cook")
		KEY_4:
			go_to_target("study")


func _follow_navigation_path() -> void:
	if navigation_agent.is_navigation_finished():
		var reached := _target_name
		_stop_navigation()
		if not reached.is_empty():
			destination_reached.emit(reached)
		return

	var next_position := navigation_agent.get_next_path_position()
	var direction := global_position.direction_to(next_position)
	velocity = direction * speed
	move_and_slide()


func _stop_navigation() -> void:
	_navigation_active = false
	velocity = Vector2.ZERO
	if not navigation_agent.is_navigation_finished():
		navigation_agent.target_position = global_position


func _start_patrol_loop() -> void:
	await get_tree().physics_frame
	await get_tree().physics_frame
	while is_inside_tree():
		await get_tree().create_timer(
			randf_range(patrol_delay_range.x, patrol_delay_range.y)
		).timeout
		if not autonomous_patrol or _navigation_active or _manual_control_active or _targets.is_empty():
			continue
		var target_names := _targets.keys()
		go_to_target(str(target_names.pick_random()))
