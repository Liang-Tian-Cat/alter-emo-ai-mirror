extends TextEdit

func _ready():
	# 获取横向滚动条
	var h_scroll = get_h_scroll_bar()
	h_scroll.custom_minimum_size = Vector2(0, 6)  # 设置高度为 6 像素

	# 创建滑块样式
	var grabber_style = StyleBoxFlat.new()
	grabber_style.bg_color = Color(1, 1, 1, 0.4)  # 半透明白
	grabber_style.corner_radius_top_left = 3
	grabber_style.corner_radius_bottom_left = 3
	grabber_style.corner_radius_top_right = 3
	grabber_style.corner_radius_bottom_right = 3
	grabber_style.set_content_margin_all(0)

	# 应用样式到横向滚动条
	h_scroll.add_theme_stylebox_override("scroll", grabber_style)
