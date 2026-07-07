import bpy
import math
from pathlib import Path


# Make sure output folders exist
Path("outputs/frames").mkdir(parents=True, exist_ok=True)


# Clear scene
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()


def create_cube(name, location, scale):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    return obj


# Create simple table parts
tabletop = create_cube("Tabletop", (0, 0, 2.8), (3, 2, 0.12))

legs = [
    create_cube("Leg_1", (-2.4, -1.4, 1.2), (0.15, 0.15, 1.2)),
    create_cube("Leg_2", (2.4, -1.4, 1.2), (0.15, 0.15, 1.2)),
    create_cube("Leg_3", (-2.4, 1.4, 1.2), (0.15, 0.15, 1.2)),
    create_cube("Leg_4", (2.4, 1.4, 1.2), (0.15, 0.15, 1.2)),
]


# Animate legs moving upward into tabletop
for i, leg in enumerate(legs):
    start_frame = 1 + i * 15
    end_frame = start_frame + 40

    leg.location.z = -1
    leg.keyframe_insert(data_path="location", frame=start_frame)

    leg.location.z = 1.2
    leg.keyframe_insert(data_path="location", frame=end_frame)

    leg.rotation_euler[2] = 0
    leg.keyframe_insert(data_path="rotation_euler", frame=start_frame)

    leg.rotation_euler[2] = math.radians(360)
    leg.keyframe_insert(data_path="rotation_euler", frame=end_frame)


# Animate tabletop slight drop
tabletop.location.z = 3.3
tabletop.keyframe_insert(data_path="location", frame=1)

tabletop.location.z = 2.8
tabletop.keyframe_insert(data_path="location", frame=80)


# Add camera
bpy.ops.object.camera_add(
    location=(4, -6, 4),
    rotation=(math.radians(60), 0, math.radians(35))
)
bpy.context.scene.camera = bpy.context.object


# Add light
bpy.ops.object.light_add(type="AREA", location=(0, -4, 6))
light = bpy.context.object
light.name = "Main_Light"
light.data.energy = 600
light.data.size = 5


# Set timeline
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = 100
bpy.context.scene.render.fps = 24


# Render settings
bpy.context.scene.render.engine = "BLENDER_EEVEE"

# This may not exist in all Blender builds, so keep it safe
if hasattr(bpy.context.scene, "eevee"):
    bpy.context.scene.eevee.taa_render_samples = 32

bpy.context.scene.render.resolution_x = 1280
bpy.context.scene.render.resolution_y = 720

# Render PNG frames, not MP4 directly
bpy.context.scene.render.filepath = "outputs/frames/frame_"
bpy.context.scene.render.image_settings.file_format = "PNG"


# Render animation as image sequence
bpy.ops.render.render(animation=True)