extends CharacterBody2D

@onready var sprite = $AnimatedSprite2D

@export var speed := 100.0

func _physics_process(delta):
	var direction = Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
	velocity = direction * speed
	move_and_slide()
	_play_animation(direction)


func _play_animation(direction: Vector2):
	if direction == Vector2.ZERO:
		sprite.play("idle_front")
	elif abs(direction.x) > abs(direction.y):
		if direction.x > 0:
			sprite.play("walk_right")
		else:
			sprite.play("walk_left")
	else:
		if direction.y > 0:
			sprite.play("walk_front")
		else:
			sprite.play("walk_back")
