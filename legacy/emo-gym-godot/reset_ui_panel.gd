extends Panel

@onready var reset_button = $ResetUIButton
@onready var interview_panel = get_parent().get_node_or_null("InterviewPanel")
@onready var reflection_panel = get_parent().get_node_or_null("ReflectionPanel")
@onready var e1 = get_parent().get_node_or_null("E1")
@onready var e2 = get_parent().get_node_or_null("E2")
@onready var e3 = get_parent().get_node_or_null("E3")

func _ready():
	reset_button.pressed.connect(_on_reset_ui_pressed)

func _on_reset_ui_pressed():
	print("🔄 重置 UI 中...")

	# 关闭其他面板
	if reflection_panel:
		reflection_panel.visible = false
	if e1:
		e1.visible = false
	if e2:
		e2.visible = false
	if e3:
		e3.visible = false

	# 重启访谈界面
	if interview_panel:
		interview_panel.visible = false
