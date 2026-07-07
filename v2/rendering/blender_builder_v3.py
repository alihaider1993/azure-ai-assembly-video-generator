import json
from pathlib import Path
from typing import Any


GRAPH_PATH = Path("v2/outputs/json/universal_assembly_graph.json")
MOTION_PATH = Path("v2/outputs/json/motion_plan.json")
SCENE_LAYOUT_PATH = Path("v2/outputs/json/scene_layout.json")
PROXY_GEOMETRY_PATH = Path("v2/output/proxy_geometry.json")
OUTPUT_SCRIPT = Path("blender/generated/v3_generated_blender_scene.py")


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_text(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_blender_script():
    project_root = Path(__file__).resolve().parents[2]

    graph = load_json(project_root / GRAPH_PATH)
    motion = load_json(project_root / MOTION_PATH)
    scene_layout = load_json(project_root / SCENE_LAYOUT_PATH)
    proxy_geometry = load_json(project_root / PROXY_GEOMETRY_PATH)

    output_script = project_root / OUTPUT_SCRIPT

    script = f"""
import bpy
import math
import sys
from pathlib import Path
from mathutils import Vector

PROJECT_ROOT = Path(r"{project_root}")
sys.path.insert(0, str(PROJECT_ROOT))

from config import FRAMES_V3_DIR, ensure_project_dirs

GRAPH = {repr(graph)}
MOTION = {repr(motion)}
SCENE_LAYOUT = {repr(scene_layout)}
PROXY_GEOMETRY = {repr(proxy_geometry)}

ensure_project_dirs()

OUTPUT_DIR = FRAMES_V3_DIR
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Clear old frames before rendering
for old_frame in OUTPUT_DIR.glob("*.png"):
    old_frame.unlink()

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()


def mat(name, color, roughness=0.45, metallic=0.0):
    material = bpy.data.materials.new(name)
    material.use_nodes = True

    bsdf = material.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic

    material.diffuse_color = color
    return material


MATERIALS = {{
    "wood": mat("Warm Wood Proxy", (0.72, 0.52, 0.32, 1), 0.42, 0.0),
    "metal": mat("Dark Metal Proxy", (0.08, 0.09, 0.10, 1), 0.32, 0.20),
    "fabric": mat("Light Fabric Proxy", (0.78, 0.78, 0.74, 1), 0.65, 0.0),
    "moving": mat("Azure Moving Part", (0.05, 0.38, 0.95, 1), 0.30, 0.05),
    "fastener": mat("Orange Fastener", (1.0, 0.48, 0.10, 1), 0.35, 0.15),
    "hole": mat("Black Hole Marker", (0.01, 0.01, 0.01, 1), 0.5, 0.0),
    "floor": mat("Clean Studio Floor", (0.94, 0.95, 0.97, 1), 0.55, 0.0),
}}


def look_at(obj, target):
    direction = target - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def create_empty(uid, location):
    obj = bpy.data.objects.new(uid, None)
    bpy.context.collection.objects.link(obj)
    obj.empty_display_type = "CUBE"
    obj.empty_display_size = 0.25
    obj.location = Vector(location)
    return obj


def create_box(name, dimensions, material):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    return obj


def create_cylinder(name, dimensions, material):
    radius = max(dimensions[0], dimensions[1]) / 2
    depth = dimensions[2]
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=32,
        radius=radius,
        depth=depth,
        location=(0, 0, 0)
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    return obj


def create_rounded_box(name, dimensions, material):
    obj = create_box(name, dimensions, material)
    bevel = obj.modifiers.new("Rounded_Corners", "BEVEL")
    bevel.width = 0.08
    bevel.segments = 4
    obj.modifiers.new("Weighted_Normal", "WEIGHTED_NORMAL")
    return obj


def add_holes(mesh, holes, dimensions):
    for i, hole in enumerate(holes, start=1):
        rel = hole.get("relative_position", [0.5, 0.5])
        x = (rel[0] - 0.5) * dimensions[0]
        y = -dimensions[1] / 2 - 0.02
        z = (rel[1] - 0.5) * dimensions[2]

        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=12,
            ring_count=6,
            radius=hole.get("radius_hint", 0.04),
            location=(x, y, z)
        )
        h = bpy.context.object
        h.name = f"{{mesh.name}}_hole_{{i}}"
        h.data.materials.append(MATERIALS["hole"])
        h.parent = mesh


def proxy_lookup():
    result = {{}}
    for obj in PROXY_GEOMETRY.get("objects", []):
        part_uid = obj.get("part_uid")
        if part_uid:
            result[part_uid] = obj
    return result


def graph_node_lookup():
    result = {{}}

    for p in GRAPH.get("parts", []):
        uid = p.get("part_uid")
        if uid:
            result[uid] = p

    for a in GRAPH.get("assemblies", []):
        uid = a.get("assembly_uid")
        if uid:
            result[uid] = a

    for f in GRAPH.get("fasteners", []):
        uid = f.get("fastener_uid")
        if uid:
            result[uid] = f

    return result


def is_moving_node(uid):
    for step in MOTION.get("steps", []):
        if uid in step.get("moving_nodes", []):
            return True
    return False


def choose_material(uid, layout_obj, graph_obj, proxy_obj):
    node_type = layout_obj.get("node_type", "")
    name = str(layout_obj.get("name", "")).lower()

    if node_type == "fastener":
        return MATERIALS["fastener"]

    if is_moving_node(uid):
        return MATERIALS["moving"]

    if "bolt" in name or "screw" in name or "washer" in name:
        return MATERIALS["fastener"]

    if "leg" in name or "rail" in name or "support" in name:
        return MATERIALS["metal"]

    if "seat" in name or "fabric" in str(graph_obj.get("material_hint", "")).lower():
        return MATERIALS["fabric"]

    return MATERIALS["wood"]


def fallback_dimensions(layout_obj, graph_obj):
    node_type = layout_obj.get("node_type", "")
    name = str(layout_obj.get("name", "")).lower()
    shape = str(graph_obj.get("shape_family", "") if graph_obj else "").lower()
    material_hint = str(graph_obj.get("material_hint", "") if graph_obj else "").lower()

    if node_type == "fastener":
        return "cylinder", [0.08, 0.08, 0.35], MATERIALS["fastener"]

    if "seat" in name or material_hint == "fabric":
        return "rounded_box", [1.6, 1.2, 0.18], MATERIALS["fabric"]

    if "back" in name or "frame" in name or shape == "frame":
        return "box", [1.6, 0.18, 1.35], MATERIALS["wood"]

    if "rail" in name or "beam" in name or shape == "beam":
        return "box", [1.8, 0.18, 0.18], MATERIALS["wood"]

    if "leg" in name:
        return "box", [0.22, 0.22, 1.25], MATERIALS["wood"]

    if shape == "panel":
        return "box", [1.2, 0.2, 0.45], MATERIALS["wood"]

    if node_type == "assembly":
        return "box", [1.8, 0.25, 1.4], MATERIALS["wood"]

    return "box", [0.6, 0.3, 0.3], MATERIALS["wood"]


def create_mesh_for_layout(parent, layout_obj, graph_obj, proxy_obj):
    uid = layout_obj.get("node_uid")
    chosen_material = choose_material(uid, layout_obj, graph_obj, proxy_obj)

    if proxy_obj:
        primitive = proxy_obj.get("primitive", "box")
        shape_type = proxy_obj.get("shape_type", "")
        dimensions = proxy_obj.get("dimensions", [1, 1, 1])
        holes = proxy_obj.get("holes", [])

        if primitive == "cylinder":
            mesh = create_cylinder(f"{{uid}}_mesh", dimensions, chosen_material)
        elif primitive == "rounded_box" or shape_type == "rounded_panel":
            mesh = create_rounded_box(f"{{uid}}_mesh", dimensions, chosen_material)
        else:
            mesh = create_box(f"{{uid}}_mesh", dimensions, chosen_material)

        add_holes(mesh, holes, dimensions)
        mesh.parent = parent
        return mesh

    primitive, dimensions, material = fallback_dimensions(layout_obj, graph_obj)

    if is_moving_node(uid):
        material = MATERIALS["moving"]

    if primitive == "cylinder":
        mesh = create_cylinder(f"{{uid}}_fallback", dimensions, material)
    elif primitive == "rounded_box":
        mesh = create_rounded_box(f"{{uid}}_fallback", dimensions, material)
    else:
        mesh = create_box(f"{{uid}}_fallback", dimensions, material)

    mesh.parent = parent
    return mesh


def keyframe(obj, start, end, start_frame, end_frame):
    obj.location = Vector(start)
    obj.keyframe_insert(data_path="location", frame=start_frame)

    obj.location = Vector(end)
    obj.keyframe_insert(data_path="location", frame=end_frame)


layout_objects = SCENE_LAYOUT.get("scene_objects", [])
layout_by_uid = {{
    obj.get("node_uid"): obj
    for obj in layout_objects
    if obj.get("node_uid")
}}

proxy_by_uid = proxy_lookup()
graph_by_uid = graph_node_lookup()

node_objects = {{}}

for layout_obj in layout_objects:
    uid = layout_obj.get("node_uid")
    if not uid:
        continue

    start = layout_obj.get("start_position", [0, 0, 1])
    parent = create_empty(uid, start)

    graph_obj = graph_by_uid.get(uid, {{}})
    proxy_obj = proxy_by_uid.get(uid)

    create_mesh_for_layout(parent, layout_obj, graph_obj, proxy_obj)

    node_objects[uid] = parent


# Animate exactly from scene_layout start_position to final_position
for step in MOTION.get("steps", []):
    start_frame = step.get("start_frame", 1)
    end_frame = step.get("end_frame", start_frame + 30)

    for moving_uid in step.get("moving_nodes", []):
        obj = node_objects.get(moving_uid)
        layout_obj = layout_by_uid.get(moving_uid)

        if not obj or not layout_obj:
            continue

        keyframe(
            obj,
            layout_obj.get("start_position", [0, 0, 1]),
            layout_obj.get("final_position", [0, 0, 1]),
            start_frame,
            end_frame
        )


animated_count = sum(
    1 for obj in node_objects.values()
    if obj.animation_data and obj.animation_data.action
)

# Fallback animate layout objects marked moving
if animated_count == 0:
    total_frames = MOTION.get("total_frames", 145)

    for layout_obj in layout_objects:
        if not layout_obj.get("is_moving"):
            continue

        uid = layout_obj.get("node_uid")
        obj = node_objects.get(uid)

        if not obj:
            continue

        keyframe(
            obj,
            layout_obj.get("start_position", [0, 0, 1]),
            layout_obj.get("final_position", [0, 0, 1]),
            1,
            total_frames
        )

    animated_count = sum(
        1 for obj in node_objects.values()
        if obj.animation_data and obj.animation_data.action
    )


# Auto camera
def get_bbox():
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH" and o.name != "Floor"]

    if not meshes:
        return Vector((0, 0, 1)), 5

    points = []
    for obj in meshes:
        for corner in obj.bound_box:
            points.append(obj.matrix_world @ Vector(corner))

    min_x = min(p.x for p in points)
    max_x = max(p.x for p in points)
    min_y = min(p.y for p in points)
    max_y = max(p.y for p in points)
    min_z = min(p.z for p in points)
    max_z = max(p.z for p in points)

    center = Vector((
        (min_x + max_x) / 2,
        (min_y + max_y) / 2,
        (min_z + max_z) / 2
    ))

    size = max(max_x - min_x, max_y - min_y, max_z - min_z, 4)
    return center, size


center, size = get_bbox()
target = center + Vector((0, 0, size * 0.08))
distance = size * 1.45

camera_location = Vector((
    target.x + distance * 0.95,
    target.y - distance * 1.20,
    target.z + distance * 0.72
))

bpy.ops.object.camera_add(location=camera_location)
camera = bpy.context.object
camera.name = "Assembly_Camera"
look_at(camera, target)
camera.data.lens = 35
camera.data.clip_end = 1000
bpy.context.scene.camera = camera

# Bright studio background
world = bpy.context.scene.world or bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.color = (0.98, 0.985, 1.0)

# Large soft key light
bpy.ops.object.light_add(
    type="AREA",
    location=(target.x, target.y - size * 1.5, target.z + size * 1.9)
)
key_light = bpy.context.object
key_light.name = "Large Softbox Key Light"
key_light.data.energy = 3500
key_light.data.size = size * 1.8

# Fill light
bpy.ops.object.light_add(
    type="AREA",
    location=(target.x - size * 1.2, target.y + size * 1.1, target.z + size * 1.2)
)
fill_light = bpy.context.object
fill_light.name = "Cool Fill Light"
fill_light.data.energy = 900
fill_light.data.size = size * 1.4

# Rim light for contrast
bpy.ops.object.light_add(
    type="POINT",
    location=(target.x + size, target.y - size, target.z + size * 1.6)
)
rim_light = bpy.context.object
rim_light.name = "Rim Light"
rim_light.data.energy = 350
rim_light.data.shadow_soft_size = size * 0.35

bpy.ops.mesh.primitive_plane_add(size=size * 2.1, location=(center.x, center.y, -0.05))
floor = bpy.context.object
floor.name = "Floor"
floor.data.materials.append(MATERIALS["floor"])

scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = MOTION.get("total_frames", 145)
scene.render.fps = MOTION.get("fps", 24)
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.filepath = str(OUTPUT_DIR / "frame_")
scene.render.image_settings.file_format = "PNG"

# Higher contrast but bright render
scene.render.engine = "CYCLES"
scene.cycles.samples = 64
scene.cycles.use_denoising = True
scene.view_settings.view_transform = "Filmic"
scene.view_settings.look = "Medium High Contrast"
scene.view_settings.exposure = 0
scene.view_settings.gamma = 1

print("V3 project root:", PROJECT_ROOT)
print("V3 frames output:", OUTPUT_DIR)
print("V3 layout objects:", len(layout_objects))
print("V3 created objects:", len(node_objects))
print("V3 animated objects:", animated_count)
print("V3 motion steps:", len(MOTION.get("steps", [])))
print("Rendering V3 frames...")

bpy.ops.render.render(animation=True)
"""

    save_text(script, output_script)
    print(f"Saved Blender V3 script to {output_script}")


if __name__ == "__main__":
    build_blender_script()
