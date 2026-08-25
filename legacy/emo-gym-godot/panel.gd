extends Panel

@onready var timer = $Timer
@onready var label = $DialogueLabel  # 因为 DialogueLabel 是 DialogueBox 的直接子节点

var preset_lines = [
	"Time for a little break.",
	"Sometimes I think about the stars.",
	"I wonder what you'll ask me next.",
	"That coffee smells nice.",
	"I'm just reflecting a bit...",
	"Do you ever feel like time loops?"
]

func _ready():
	visible = false  # 当前 Panel 自身就是 DialogueBox，所以直接隐藏自己
	timer.wait_time = 10.0
	timer.timeout.connect(_on_timer_timeout)
	timer.start()

func _on_timer_timeout():
	var line = preset_lines[randi() % preset_lines.size()]
	label.text = line
	visible = true

	# 2 秒后自动隐藏
	var hide_timer = get_tree().create_timer(2.0)
	hide_timer.timeout.connect(func():
		visible = false
	)
