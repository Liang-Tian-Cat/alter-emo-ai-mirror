extends Node2D

const TILE_SIZE := Vector2i(32, 32)
const MAP_SIZE := Vector2i(13, 15)

@onready var ground: TileMapLayer = $Ground
@onready var navigation_region: NavigationRegion2D = $NavigationRegion2D
@onready var player: MirrorWorldPlayer = $Player
@onready var api: AlterEmoApi = $Api
@onready var bridge_status: Label = $UI/Panel/Margin/Column/BridgeStatus
@onready var movement_status: Label = $UI/Panel/Margin/Column/MovementStatus


func _ready() -> void:
	_build_tile_map()
	_build_navigation_region()
	player.configure_targets($NavigationRegion2D/Targets)
	player.destination_changed.connect(_on_destination_changed)
	player.destination_reached.connect(_on_destination_reached)
	$UI/Panel/Margin/Column/Targets/Sofa.pressed.connect(player.go_to_target.bind("sofa"))
	$UI/Panel/Margin/Column/Targets/Eat.pressed.connect(player.go_to_target.bind("eat"))
	$UI/Panel/Margin/Column/Targets/Cook.pressed.connect(player.go_to_target.bind("cook"))
	$UI/Panel/Margin/Column/Targets/Study.pressed.connect(player.go_to_target.bind("study"))
	$UI/Panel/Margin/Column/Back.pressed.connect(_return_to_mirror)
	api.health_received.connect(_on_health_received)
	api.request_failed.connect(_on_bridge_failed)
	api.check_health()


func _build_tile_map() -> void:
	var tile_set := TileSet.new()
	tile_set.tile_size = TILE_SIZE
	var atlas := TileSetAtlasSource.new()
	atlas.texture_region_size = TILE_SIZE
	atlas.texture = _create_tile_texture()
	for tile_index in range(3):
		atlas.create_tile(Vector2i(tile_index, 0))
	tile_set.add_source(atlas, 0)
	ground.tile_set = tile_set

	for y in range(MAP_SIZE.y):
		for x in range(MAP_SIZE.x):
			var edge := x == 0 or y == 0 or x == MAP_SIZE.x - 1 or y == MAP_SIZE.y - 1
			var atlas_coordinate := Vector2i(2 if edge else (x + y) % 2, 0)
			ground.set_cell(Vector2i(x, y), 0, atlas_coordinate)


func _create_tile_texture() -> ImageTexture:
	var image := Image.create(TILE_SIZE.x * 3, TILE_SIZE.y, false, Image.FORMAT_RGBA8)
	var colors := [Color("#27213b"), Color("#302947"), Color("#171322")]
	for tile_index in range(colors.size()):
		for y in range(TILE_SIZE.y):
			for x in range(TILE_SIZE.x):
				var color: Color = colors[tile_index]
				if x == 0 or y == 0:
					color = color.lightened(0.08)
				image.set_pixel(tile_index * TILE_SIZE.x + x, y, color)
	return ImageTexture.create_from_image(image)


func _build_navigation_region() -> void:
	var polygon := NavigationPolygon.new()
	polygon.vertices = PackedVector2Array([
		Vector2(36, 36),
		Vector2(380, 36),
		Vector2(380, 444),
		Vector2(36, 444),
	])
	polygon.add_polygon(PackedInt32Array([0, 1, 2, 3]))
	navigation_region.navigation_polygon = polygon


func _on_destination_changed(destination: String) -> void:
	movement_status.text = "Moving to %s · arrows take manual control" % destination.capitalize()


func _on_destination_reached(destination: String) -> void:
	movement_status.text = "Reached %s · autonomous patrol continues" % destination.capitalize()


func _on_health_received(data: Dictionary) -> void:
	var capabilities: Dictionary = data.get("capabilities", {})
	bridge_status.text = "Flask bridge online · text %s · events %s" % [
		"on" if capabilities.get("text", false) else "off",
		"on" if capabilities.get("events", false) else "off",
	]


func _on_bridge_failed(message: String) -> void:
	bridge_status.text = "Bridge offline · start python -m server.app (%s)" % message


func _return_to_mirror() -> void:
	get_tree().change_scene_to_file("res://Main.tscn")
