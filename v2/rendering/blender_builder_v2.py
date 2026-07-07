import json
from pathlib import Path
from typing import Any


GRAPH_PATH = Path("v2/outputs/json/universal_assembly_graph.json")
MOTION_PATH = Path("v2/outputs/json/motion_plan.json")
SCENE_LAYOUT_PATH = Path("v2/outputs/json/scene_layout.json")
PROXY_GEOMETRY_PATH = Path("v2/output/proxy_geometry.json")
OUTPUT_SCRIPT = Path("blender/generated/v2_generated_blender_scene.py")


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_text(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_blender_script(
    graph_path: Path = GRAPH_PATH,
    motion_path: Path = MOTION_PATH,
    scene_layout_path: Path = SCENE_LAYOUT_PATH,
    proxy_geometry_path: Path = PROXY_GEOMETRY_PATH,
    output_script: Path = OUTPUT_SCRIPT,
) -> None:
    project_root = Path(__file__).resolve().parents[2]

    graph = load_json(project_root / graph_path)
    motion = load_json(project_root / motion_path)
    scene_layout = load_json(project_root / scene_layout_path)
    proxy_geometry = load_json(project_root / proxy_geometry_path)

    output_script = project_root / output_script

    script = f"""
import bpy
import math
import sys
from pathlib import Path
from mathutils import Vector

PROJECT_ROOT = Path(r"{project_root}")
sys.path.insert(0, str(PROJECT_ROOT))

from config import FRAMES_V2_DIR, ensure_project_dirs

GRAPH = {repr(graph)}
MOTION = {repr(motion)}
SCENE_LAYOUT = {repr(scene_layout)}
PROXY_GEOMETRY = {repr(proxy_geometry)}

ensure_project_dirs()

OUTPUT_DIR = FRAMES_V2_DIR
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Clear old frames before rendering
for old_frame in OUTPUT_DIR.glob("*.png"):
    old_frame.unlink()

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()


def material(name, color):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    return mat


MATERIALS = {{
    "proxy": material("Manual Proxy", (0.64, 0.64, 0.64, 1)),
    "metal": material("Metal", (0.75, 0.75, 0.78, 1)),
    "hole": material("Hole Marker", (0.02, 0.02, 0.02, 1)),
    "floor": material("Floor", (0.45, 0.45, 0.45, 1)),
}}


def look_at(obj, target):
    direction = target - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def make_empty(name, location):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    obj.empty_display_type = "CUBE"
    obj.empty_display_size = 0.35
    obj.location = Vector(location)
    return obj


def create_box(name, dimensions, location, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    return obj


def create_cylinder(name, dimensions, location, rotation, mat):
    radius = max(dimensions[0], dimensions[1]) / 2
    depth = dimensions[2]

    bpy.ops.mesh.primitive_cylinder_add(
        vertices=32,
        radius=radius,
        depth=depth,
        location=location
    )

    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = [math.radians(x) for x in rotation]
    obj.data.materials.append(mat)
    return obj


def create_rounded_box(name, dimensions, location, mat):
    obj = create_box(name, dimensions, location, mat)
    bevel = obj.modifiers.new("MVP_Rounded_Corners", "BEVEL")
    bevel.width = 0.08
    bevel.segments = 4
    obj.modifiers.new("MVP_Smooth", "WEIGHTED_NORMAL")
    return obj


def add_hole_markers(parent_obj, obj_data):
    holes = obj_data.get("holes", [])
    dims = obj_data.get("dimensions", [1, 1, 1])

    for i, hole in enumerate(holes, start=1):
        rel = hole.get("relative_position", [0.5, 0.5])

        x = (rel[0] - 0.5) * dims[0]
        y = -dims[1] / 2 - 0.015
        z = (rel[1] - 0.5) * dims[2]

        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=16,
            ring_count=8,
            radius=hole.get("radius_hint", 0.04),
            location=(x, y, z)
        )

        marker = bpy.context.object
        marker.name = f"{{parent_obj.name}}_hole_{{i}}"
        marker.data.materials.append(MATERIALS["hole"])
        marker.parent = parent_obj


def get_layout_lookup():
    return {{
        obj.get("node_uid"): obj
        for obj in SCENE_LAYOUT.get("scene_objects", [])
        if obj.get("node_uid")
    }}


def get_proxy_lookup():
    lookup = {{}}

    for obj in PROXY_GEOMETRY.get("objects", []):
        part_uid = obj.get("part_uid")
        if part_uid:
            lookup[part_uid] = obj

    return lookup


def create_proxy_mesh(parent, obj_data):
    primitive = obj_data.get("primitive", "box")
    shape_type = obj_data.get("shape_type", "proxy_block")
    dimensions = obj_data.get("dimensions", [1, 1, 1])
    rotation = obj_data.get("rotation", [0, 0, 0])

    mesh_name = f"{{parent.name}}_mesh"

    if primitive == "cylinder":
        mesh = create_cylinder(
            mesh_name,
            dimensions,
            (0, 0, 0),
            rotation,
            MATERIALS["metal"]
        )
    elif primitive == "rounded_box" or shape_type == "rounded_panel":
        mesh = create_rounded_box(
            mesh_name,
            dimensions,
            (0, 0, 0),
            MATERIALS["proxy"]
        )
    else:
        mesh = create_box(
            mesh_name,
            dimensions,
            (0, 0, 0),
            MATERIALS["proxy"]
        )

    mesh.parent = parent
    add_hole_markers(mesh, obj_data)
    return mesh


def create_fallback_part_mesh(parent, layout_obj):
    node_type = layout_obj.get("node_type", "part")
    name = layout_obj.get("name", "").lower()

    if node_type == "assembly":
        dimensions = [1.8, 0.18, 1.4]
    elif "seat" in name:
        dimensions = [1.6, 1.2, 0.18]
    elif "back" in name or "frame" in name:
        dimensions = [1.8, 0.18, 1.6]
    elif "rail" in name or "beam" in name:
        dimensions = [1.8, 0.18, 0.18]
    elif "leg" in name:
        dimensions = [0.22, 0.22, 1.4]
    elif node_type == "part":
        dimensions = [1.0, 0.25, 0.35]
    else:
        return None

    mesh = create_box(
        f"{{parent.name}}_fallback_mesh",
        dimensions,
        (0, 0, 0),
        MATERIALS["proxy"]
    )

    mesh.parent = parent
    return mesh


def create_fastener_proxy(parent, node_type):
    if node_type == "fastener":
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=24,
            radius=0.055,
            depth=0.32,
            location=(0, 0, 0)
        )
        mesh = bpy.context.object
        mesh.name = f"{{parent.name}}_fastener_mesh"
        mesh.data.materials.append(MATERIALS["metal"])
        mesh.parent = parent
        return mesh

    return None


def keyframe_node(obj, start, end, start_frame, end_frame):
    obj.location = Vector(start)
    obj.keyframe_insert(data_path="location", frame=start_frame)

    obj.location = Vector(end)
    obj.keyframe_insert(data_path="location", frame=end_frame)


layout_by_uid = get_layout_lookup()
proxy_by_uid = get_proxy_lookup()

node_objects = {{}}

for uid, layout_obj in layout_by_uid.items():
    start = layout_obj.get("start_position", [0, 0, 1])
    node_type = layout_obj.get("node_type", "part")

    parent = make_empty(uid, start)
    node_objects[uid] = parent

    proxy_obj = proxy_by_uid.get(uid)

    if proxy_obj:
        create_proxy_mesh(parent, proxy_obj)
    else:
        created = create_fastener_proxy(parent, node_type)

        if created is None:
            create_fallback_part_mesh(parent, layout_obj)


for step in MOTION.get("steps", []):
    start_frame = step.get("start_frame", 1)
    end_frame = step.get("end_frame", start_frame + 30)

    for moving_ref in step.get("moving_nodes", []):
        obj = node_objects.get(moving_ref)
        layout_obj = layout_by_uid.get(moving_ref)

        if not obj or not layout_obj:
            continue

        start_pos = layout_obj.get("start_position", [0, 0, 1])
        final_pos = layout_obj.get("final_position", [0, 0, 1])

        keyframe_node(obj, start_pos, final_pos, start_frame, end_frame)


animated = [
    obj for obj in node_objects.values()
    if obj.animation_data and obj.animation_data.action
]

if len(animated) == 0:
    print("WARNING: No motion steps matched layout objects.")
    print("Applying fallback layout animation.")

    total_frames = MOTION.get("total_frames", 145)

    for uid, layout_obj in layout_by_uid.items():
        if not layout_obj.get("is_moving"):
            continue

        obj = node_objects.get(uid)

        if not obj:
            continue

        start_pos = layout_obj.get("start_position", [0, 0, 1])
        final_pos = layout_obj.get("final_position", [0, 0, 1])

        keyframe_node(obj, start_pos, final_pos, 1, total_frames)

animated_count = sum(
    1 for obj in node_objects.values()
    if obj.animation_data and obj.animation_data.action
)


def get_world_bbox():
    mesh_objects = [
        obj for obj in bpy.context.scene.objects
        if obj.type == "MESH" and obj.name != "Floor"
    ]

    if not mesh_objects:
        return Vector((0, 0, 1)), 5

    world_points = []

    for obj in mesh_objects:
        for corner in obj.bound_box:
            world_points.append(obj.matrix_world @ Vector(corner))

    min_x = min(p.x for p in world_points)
    max_x = max(p.x for p in world_points)
    min_y = min(p.y for p in world_points)
    max_y = max(p.y for p in world_points)
    min_z = min(p.z for p in world_points)
    max_z = max(p.z for p in world_points)

    center = Vector((
        (min_x + max_x) / 2,
        (min_y + max_y) / 2,
        (min_z + max_z) / 2
    ))

    size = max(
        max_x - min_x,
        max_y - min_y,
        max_z - min_z,
        3.5
    )

    return center, size


center, scene_size = get_world_bbox()
target = center + Vector((0, 0, scene_size * 0.10))
camera_distance = scene_size * 1.25

camera_location = Vector((
    target.x + camera_distance * 0.95,
    target.y - camera_distance * 1.25,
    target.z + camera_distance * 0.75
))

bpy.ops.object.camera_add(location=camera_location)
camera = bpy.context.object
camera.name = "AutoFit_Assembly_Camera"
look_at(camera, target)

camera.data.lens = 40
camera.data.clip_end = 1000
bpy.context.scene.camera = camera

camera.keyframe_insert(data_path="location", frame=1)
camera.keyframe_insert(data_path="rotation_euler", frame=1)

final_camera_location = Vector((
    target.x + camera_distance * 0.85,
    target.y - camera_distance * 1.10,
    target.z + camera_distance * 0.68
))

camera.location = final_camera_location
look_at(camera, target)

camera.keyframe_insert(data_path="location", frame=MOTION.get("total_frames", 145))
camera.keyframe_insert(data_path="rotation_euler", frame=MOTION.get("total_frames", 145))

bpy.ops.object.light_add(
    type="AREA",
    location=(
        target.x,
        target.y - scene_size * 1.5,
        target.z + scene_size * 1.8
    )
)
key_light = bpy.context.object
key_light.name = "Key Light"
key_light.data.energy = 1400
key_light.data.size = scene_size * 1.3

bpy.ops.object.light_add(
    type="AREA",
    location=(
        target.x - scene_size,
        target.y + scene_size,
        target.z + scene_size * 1.2
    )
)
fill_light = bpy.context.object
fill_light.name = "Fill Light"
fill_light.data.energy = 500
fill_light.data.size = scene_size

bpy.ops.mesh.primitive_plane_add(
    size=scene_size * 1.6,
    location=(center.x, center.y, -0.05)
)
floor = bpy.context.object
floor.name = "Floor"
floor.data.materials.append(MATERIALS["floor"])

bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = MOTION.get("total_frames", 145)
bpy.context.scene.render.fps = MOTION.get("fps", 24)
bpy.context.scene.render.resolution_x = 1280
bpy.context.scene.render.resolution_y = 720
bpy.context.scene.render.filepath = str(OUTPUT_DIR / "frame_")
bpy.context.scene.render.image_settings.file_format = "PNG"

bpy.context.scene.view_settings.view_transform = "Filmic"
bpy.context.scene.view_settings.look = "Medium High Contrast"

print("V2 project root:", PROJECT_ROOT)
print("V2 frames output:", OUTPUT_DIR)
print("Layout objects created:", len(node_objects))
print("Animated objects:", animated_count)
print("Motion steps:", len(MOTION.get("steps", [])))
print("Rendering frames...")

bpy.ops.render.render(animation=True)
"""

    save_text(script, output_script)
    print(f"Saved Blender V2 script to {output_script}")


if __name__ == "__main__":
    build_blender_script()
