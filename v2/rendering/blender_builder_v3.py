import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from config import RENDER_TIMELINE_JSON


GRAPH_PATH = Path("v2/outputs/json/universal_assembly_graph.json")
MOTION_PATH = Path("v2/outputs/json/motion_plan.json")
SCENE_LAYOUT_PATH = Path("v2/outputs/json/scene_layout.json")
PROXY_GEOMETRY_PATH = Path("v2/output/proxy_geometry.json")
OUTPUT_SCRIPT = Path("blender/generated/v3_generated_blender_scene.py")

# Video timing, in frames at 24 fps. Steps that only move fasteners are
# shorter than steps that move parts; the gap between steps is when the
# camera re-frames.
INTRO_FRAMES = 24
PART_STEP_FRAMES = 32
FASTENER_STEP_FRAMES = 22
STEP_GAP_FRAMES = 10
FINALE_PAUSE_FRAMES = 12
FLIP_FRAMES = 60
ORBIT_FRAMES = 120
END_HOLD_FRAMES = 24

ACTION_VERBS = {
    "insert": ("Insert", "into"),
    "attach": ("Attach", "to"),
    "insert_and_rotate": ("Screw in", "into"),
    "rotate": ("Turn", "on"),
    "slide": ("Slide", "onto"),
    "lower": ("Lower", "onto"),
}


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_text(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    value = int(raw)
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}, got {value}")
    return value


def base_uid(scene_object: Dict[str, Any]) -> str:
    """The graph node a scene object stands for (a fastener instance
    stands for its fastener)."""
    return scene_object.get("instance_of") or scene_object.get("node_uid", "")


def validate_inputs(motion: Any, scene_layout: Any) -> None:
    """Refuse to generate a script that would render an empty or static scene."""
    layout_uids = {
        base_uid(obj)
        for obj in scene_layout.get("scene_objects", [])
        if obj.get("node_uid")
    }
    if not layout_uids:
        raise ValueError(f"{SCENE_LAYOUT_PATH} has no scene_objects; nothing to render")

    steps = motion.get("steps", [])
    if not steps:
        raise ValueError(f"{MOTION_PATH} has no steps; nothing to animate")

    animatable = [
        uid
        for step in steps
        for uid in step.get("moving_nodes", [])
        if uid in layout_uids
    ]
    if not animatable:
        raise ValueError(
            "No motion step moves a node that exists in scene_layout.json; "
            "the render would be a static scene"
        )


def display_name(name: str) -> str:
    """'long rail 2/2' -> 'long rail'."""
    return re.sub(r"\s+\d+\s*/\s*\d+$", "", str(name)).strip()


def step_caption(step: Dict[str, Any], moving: List[str], by_uid: Dict[str, Dict[str, Any]]) -> str:
    verb, preposition = ACTION_VERBS.get(step.get("action_type", ""), ("Fit", "to"))

    counts: Dict[str, int] = {}
    for uid in moving:
        name = display_name(by_uid[uid].get("name", uid))
        counts[name] = counts.get(name, 0) + 1
    items = [f"{count} x {name}" if count > 1 else name for name, count in counts.items()]
    text = f"{verb} {' and '.join(items)}"

    targets = [by_uid[t] for t in step.get("target_nodes", []) if t in by_uid and t not in moving]
    if targets:
        text += f" {preposition} {display_name(targets[0].get('name', ''))}"
    return text


def build_timeline(motion: Dict[str, Any], scene_layout: Dict[str, Any]) -> Dict[str, Any]:
    """Frame timing for the video: one entry per motion step that still has
    something to move (a node moved by an earlier step stays assembled),
    then the finale (turn-over, if the layout asks for it) and a slow orbit
    around the finished assembly. Also the on-screen captions."""
    scene_objects = scene_layout.get("scene_objects", [])
    by_uid = {obj["node_uid"]: obj for obj in scene_objects if obj.get("node_uid")}
    instances: Dict[str, List[str]] = {}
    for uid, obj in by_uid.items():
        instances.setdefault(base_uid(obj), []).append(uid)

    # A run of steps doing the same thing to the same kind of part (four
    # legs attached one after another) plays as one step that moves them
    # all together.
    moved = set()
    merged: List[Dict[str, Any]] = []
    for step in sorted(motion.get("steps", []), key=lambda s: s.get("start_frame", 1)):
        moving = [
            uid
            for node in step.get("moving_nodes", [])
            for uid in instances.get(node, [])
            if uid not in moved
        ]
        if not moving:
            continue
        moved.update(moving)

        kinds = sorted({display_name(by_uid[uid].get("name", uid)) for uid in moving})
        previous = merged[-1] if merged else None
        if previous and previous["step"].get("action_type") == step.get("action_type") and previous["kinds"] == kinds:
            previous["moving"].extend(moving)
        else:
            merged.append({"step": step, "moving": moving, "kinds": kinds})

    steps = []
    frame = 1 + INTRO_FRAMES
    for entry in merged:
        step, moving = entry["step"], entry["moving"]
        fasteners_only = all(by_uid[uid].get("node_type") == "fastener" for uid in moving)
        duration = FASTENER_STEP_FRAMES if fasteners_only else PART_STEP_FRAMES
        steps.append({
            "step_uid": step.get("step_uid", ""),
            "moving_nodes": moving,
            "start_frame": frame,
            "end_frame": frame + duration,
            "caption": step_caption(step, moving, by_uid),
        })
        frame += duration + STEP_GAP_FRAMES

    last_end = steps[-1]["end_frame"] if steps else 1
    flips = scene_layout.get("finale", {}).get("type") == "flip"
    flip_start = last_end + FINALE_PAUSE_FRAMES
    flip_end = flip_start + FLIP_FRAMES if flips else flip_start
    orbit_start = flip_end + STEP_GAP_FRAMES
    orbit_end = orbit_start + ORBIT_FRAMES
    frame_end = orbit_end + END_HOLD_FRAMES

    captions = []
    for index, step in enumerate(steps):
        captions.append({
            "start_frame": step["start_frame"] - STEP_GAP_FRAMES // 2,
            "end_frame": step["end_frame"] + STEP_GAP_FRAMES // 2,
            "label": f"Step {index + 1} of {len(steps)}",
            "text": step["caption"],
        })
    if flips:
        captions.append({
            "start_frame": flip_start - FINALE_PAUSE_FRAMES // 2,
            "end_frame": flip_end,
            "label": "Finish",
            "text": "Turn the assembly over",
        })
    captions.append({
        "start_frame": orbit_start,
        "end_frame": frame_end,
        "label": "Done",
        "text": "Assembly complete",
    })

    return {
        "fps": motion.get("fps", 24),
        "steps": steps,
        "flip": {"start_frame": flip_start, "end_frame": flip_end} if flips else None,
        "orbit": {"start_frame": orbit_start, "end_frame": orbit_end},
        "frame_end": frame_end,
        "captions": captions,
    }


def build_blender_script():
    project_root = PROJECT_ROOT

    graph = load_json(project_root / GRAPH_PATH)
    motion = load_json(project_root / MOTION_PATH)
    scene_layout = load_json(project_root / SCENE_LAYOUT_PATH)
    proxy_geometry = load_json(project_root / PROXY_GEOMETRY_PATH)

    validate_inputs(motion, scene_layout)

    timeline = build_timeline(motion, scene_layout)
    if not timeline["steps"]:
        raise ValueError("No motion step moves an object in scene_layout.json; nothing to animate")

    RENDER_TIMELINE_JSON.parent.mkdir(parents=True, exist_ok=True)
    RENDER_TIMELINE_JSON.write_text(json.dumps(timeline, indent=2), encoding="utf-8")

    # Optional overrides for quick preview renders; defaults keep full quality.
    resolution_percent = env_int("V3_RESOLUTION_PERCENT", 100, 10, 100)
    frame_step = env_int("V3_FRAME_STEP", 1, 1, 24)

    output_script = project_root / OUTPUT_SCRIPT

    script = f"""
import bpy
import math
import sys
from pathlib import Path
from mathutils import Matrix, Vector

PROJECT_ROOT = Path(r"{project_root}")
sys.path.insert(0, str(PROJECT_ROOT))

from config import FRAMES_V3_DIR, ensure_project_dirs

GRAPH = {repr(graph)}
SCENE_LAYOUT = {repr(scene_layout)}
PROXY_GEOMETRY = {repr(proxy_geometry)}
TIMELINE = {repr(timeline)}

ensure_project_dirs()

OUTPUT_DIR = FRAMES_V3_DIR
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Clear old frames before rendering
for old_frame in OUTPUT_DIR.glob("*.png"):
    old_frame.unlink()

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()


# A part glows in this colour while it moves: each material mixes it in by
# the object's "highlight" property (0..1), which is keyframed per step.
HIGHLIGHT_COLOR = (1.0, 0.42, 0.05, 1.0)
HIGHLIGHT_EMISSION = 0.35


def socket(sockets, name, kind):
    return next(s for s in sockets if s.name == name and s.type == kind)


def mat(name, color, roughness=0.45, metallic=0.0):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Emission Color"].default_value = HIGHLIGHT_COLOR

    highlight = nodes.new("ShaderNodeAttribute")
    highlight.attribute_type = "OBJECT"
    highlight.attribute_name = "highlight"

    mix = nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    socket(mix.inputs, "A", "RGBA").default_value = color
    socket(mix.inputs, "B", "RGBA").default_value = HIGHLIGHT_COLOR
    links.new(highlight.outputs["Fac"], mix.inputs["Factor"])
    links.new(socket(mix.outputs, "Result", "RGBA"), bsdf.inputs["Base Color"])

    glow = nodes.new("ShaderNodeMath")
    glow.operation = "MULTIPLY"
    glow.inputs[1].default_value = HIGHLIGHT_EMISSION
    links.new(highlight.outputs["Fac"], glow.inputs[0])
    links.new(glow.outputs["Value"], bsdf.inputs["Emission Strength"])

    material.diffuse_color = color
    return material


MATERIALS = {{
    "wood": mat("Birch Wood Proxy", (0.66, 0.45, 0.26, 1), 0.5, 0.0),
    "metal": mat("Dark Metal Proxy", (0.10, 0.11, 0.13, 1), 0.35, 0.6),
    "fabric": mat("Light Fabric Proxy", (0.70, 0.70, 0.66, 1), 0.7, 0.0),
    "fastener": mat("Steel Fastener", (0.62, 0.63, 0.66, 1), 0.3, 0.9),
    "hole": mat("Black Hole Marker", (0.01, 0.01, 0.01, 1), 0.5, 0.0),
    "floor": mat("Studio Floor", (0.50, 0.53, 0.58, 1), 0.6, 0.0),
}}


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
    bevel.width = min(0.08, min(dimensions) * 0.3)
    bevel.segments = 4
    obj.modifiers.new("Weighted_Normal", "WEIGHTED_NORMAL")
    return obj


MIN_HOLE_RADIUS = 0.008


def add_holes(mesh, holes, dimensions):
    # Holes go on the largest face: the underside of a flat part (thinnest
    # along Z), otherwise the -Y face.
    flat = dimensions[2] <= min(dimensions[0], dimensions[1])
    for i, hole in enumerate(holes, start=1):
        rel = hole.get("relative_position", [0.5, 0.5])
        x = (rel[0] - 0.5) * dimensions[0]
        if flat:
            y = (rel[1] - 0.5) * dimensions[1]
            z = -dimensions[2] / 2
        else:
            y = -dimensions[1] / 2
            z = (rel[1] - 0.5) * dimensions[2]

        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=12,
            ring_count=6,
            radius=max(hole.get("radius_hint", 0.04), MIN_HOLE_RADIUS),
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


def choose_material(layout_obj, graph_obj):
    node_type = layout_obj.get("node_type", "")
    name = str(layout_obj.get("name", "")).lower()
    material_hint = str(graph_obj.get("material_hint", "")).lower()

    if node_type == "fastener":
        return MATERIALS["fastener"]

    if "bolt" in name or "screw" in name or "washer" in name:
        return MATERIALS["fastener"]

    if material_hint in ("wood", "metal", "fabric"):
        return MATERIALS[material_hint]

    if "leg" in name or "rail" in name or "support" in name:
        return MATERIALS["metal"]

    if "seat" in name:
        return MATERIALS["fabric"]

    return MATERIALS["wood"]


def fallback_dimensions(layout_obj, graph_obj):
    node_type = layout_obj.get("node_type", "")
    name = str(layout_obj.get("name", "")).lower()
    shape = str(graph_obj.get("shape_family", "")).lower()
    material_hint = str(graph_obj.get("material_hint", "")).lower()

    if node_type == "fastener":
        return "cylinder", [0.08, 0.08, 0.35]

    if "seat" in name or material_hint == "fabric":
        return "rounded_box", [1.6, 1.2, 0.18]

    if "back" in name or "frame" in name or shape == "frame":
        return "box", [1.6, 0.18, 1.35]

    if "rail" in name or "beam" in name or shape == "beam":
        return "box", [1.8, 0.18, 0.18]

    if "leg" in name:
        return "box", [0.22, 0.22, 1.25]

    if shape == "panel":
        return "box", [1.2, 0.2, 0.45]

    return "box", [0.6, 0.3, 0.3]


# Real-scale fasteners (a few mm across) vanish in a whole-product shot,
# so they are enlarged to at least this size (metres, longest side).
MIN_FASTENER_SIZE = 0.08


def visible_dimensions(layout_obj, dimensions):
    if layout_obj.get("node_type") != "fastener":
        return dimensions
    factor = max(1.0, MIN_FASTENER_SIZE / max(max(dimensions), 1e-6))
    return [d * factor for d in dimensions]


def create_mesh_for_layout(parent, layout_obj, graph_obj, proxy_obj):
    uid = layout_obj.get("node_uid")
    material = choose_material(layout_obj, graph_obj)

    if proxy_obj:
        name = f"{{uid}}_mesh"
        primitive = proxy_obj.get("primitive", "box")
        if proxy_obj.get("shape_type") == "rounded_panel":
            primitive = "rounded_box"
        dimensions = proxy_obj.get("dimensions", [1, 1, 1])
        holes = proxy_obj.get("holes", [])
    else:
        name = f"{{uid}}_fallback"
        primitive, dimensions = fallback_dimensions(layout_obj, graph_obj)
        holes = []

    dimensions = visible_dimensions(layout_obj, dimensions)

    if primitive == "cylinder":
        mesh = create_cylinder(name, dimensions, material)
    elif primitive == "rounded_box":
        mesh = create_rounded_box(name, dimensions, material)
    else:
        mesh = create_box(name, dimensions, material)

    add_holes(mesh, holes, dimensions)
    mesh.parent = parent
    # scene_layout rotation is XYZ Euler in degrees (e.g. a short rail
    # turned 90 degrees about Z to run along Y).
    mesh.rotation_euler = [math.radians(a) for a in layout_obj.get("rotation", [0, 0, 0])]
    mesh.scale = layout_obj.get("scale", [1, 1, 1])
    mesh["highlight"] = 0.0
    return mesh, primitive


def keyframe_location(obj, location, frame):
    obj.location = Vector(location)
    obj.keyframe_insert(data_path="location", frame=frame)


def keyframe_scale(obj, value, frame):
    obj.scale = (value, value, value)
    obj.keyframe_insert(data_path="scale", frame=frame)


def keyframe_highlight(mesh, value, frame):
    mesh["highlight"] = value
    mesh.keyframe_insert(data_path='["highlight"]', frame=frame)


layout_objects = SCENE_LAYOUT.get("scene_objects", [])
layout_by_uid = {{
    obj.get("node_uid"): obj
    for obj in layout_objects
    if obj.get("node_uid")
}}

proxy_by_uid = proxy_lookup()
graph_by_uid = graph_node_lookup()

# Everything hangs off one pivot so the finished assembly can be turned
# over as a whole. Node empties are keyframed in pivot space; the pivot
# doesn't move until the finale, so pivot space is world space minus PIVOT.
FINALE = SCENE_LAYOUT.get("finale") or {{}}
PIVOT = Vector(FINALE.get("pivot", [0, 0, 0]))
pivot_obj = create_empty("Assembly_Pivot", PIVOT)


def local(position):
    return Vector(position) - PIVOT


node_objects = {{}}
node_meshes = {{}}
spinning = set()
# uid -> (local min corner, local max corner) of the node's mesh
node_extents = {{}}

for layout_obj in layout_objects:
    uid = layout_obj.get("node_uid")
    if not uid:
        continue

    parent = create_empty(uid, local(layout_obj.get("start_position", [0, 0, 1])))
    parent.parent = pivot_obj
    node_objects[uid] = parent

    # An assembly node is a logical group of the parts that are drawn
    # individually; giving it a solid mesh would hide those parts. A
    # fastener no step uses would just float loose in the scene.
    if layout_obj.get("node_type") == "assembly":
        continue
    if layout_obj.get("node_type") == "fastener" and not layout_obj.get("is_moving"):
        continue

    graph_uid = layout_obj.get("instance_of") or uid
    graph_obj = graph_by_uid.get(graph_uid, {{}})
    proxy_obj = proxy_by_uid.get(graph_uid)

    mesh, primitive = create_mesh_for_layout(parent, layout_obj, graph_obj, proxy_obj)
    node_meshes[uid] = mesh
    if primitive == "cylinder" and layout_obj.get("node_type") == "fastener":
        spinning.add(uid)

    corners = [mesh.matrix_basis @ Vector(c) for c in mesh.bound_box]
    node_extents[uid] = (
        Vector([min(c[i] for c in corners) for i in range(3)]),
        Vector([max(c[i] for c in corners) for i in range(3)]),
    )


# Each part pops in just before its step, glows while it moves into place,
# and fades back to its own colour. Screws and bolts turn as they go in.
APPEAR_FRAMES = 8
HIDDEN_SCALE = 0.001
HIGHLIGHT_FADE_FRAMES = 10
SPIN_TURNS = 2

steps = TIMELINE["steps"]
first_step_of = {{}}

for index, step in enumerate(steps):
    start_frame = step["start_frame"]
    end_frame = step["end_frame"]

    for uid in step["moving_nodes"]:
        obj = node_objects.get(uid)
        layout_obj = layout_by_uid.get(uid)
        if not obj or not layout_obj:
            continue

        first_step_of[uid] = index

        appear_frame = start_frame - APPEAR_FRAMES
        if appear_frame > 1:
            keyframe_scale(obj, HIDDEN_SCALE, appear_frame)
            keyframe_scale(obj, 1.0, start_frame)

        keyframe_location(obj, local(layout_obj.get("start_position", [0, 0, 1])), start_frame)
        keyframe_location(obj, local(layout_obj.get("final_position", [0, 0, 1])), end_frame)

        mesh = node_meshes.get(uid)
        if mesh is None:
            continue

        keyframe_highlight(mesh, 1.0, start_frame)
        keyframe_highlight(mesh, 1.0, end_frame)
        keyframe_highlight(mesh, 0.0, end_frame + HIGHLIGHT_FADE_FRAMES)

        if uid in spinning:
            base_angle = mesh.rotation_euler[2]
            mesh.keyframe_insert(data_path="rotation_euler", index=2, frame=start_frame)
            mesh.rotation_euler[2] = base_angle + SPIN_TURNS * 2 * math.pi
            mesh.keyframe_insert(data_path="rotation_euler", index=2, frame=end_frame)

animated_count = len(first_step_of)

if animated_count == 0:
    print("ERROR: V3 no motion step moves an object in the scene; refusing to render a static video")
    sys.exit(1)


def bounds_of(entries, upright=False):
    # World-space box around each (uid, position) entry. With upright=True
    # the positions are mapped through the finale's turn-over (180 degrees
    # about X through PIVOT), i.e. where they end up after it.
    lo = None
    hi = None
    for uid, position in entries:
        extent = node_extents.get(uid)
        if not extent:
            continue
        p = Vector(position)
        a = p + extent[0]
        b = p + extent[1]
        if upright:
            a, b = (
                Vector((a.x, -b.y, 2 * PIVOT.z - b.z)),
                Vector((b.x, -a.y, 2 * PIVOT.z - a.z)),
            )
        lo = a if lo is None else Vector([min(lo[i], a[i]) for i in range(3)])
        hi = b if hi is None else Vector([max(hi[i], b[i]) for i in range(3)])
    return lo, hi


def union(box_a, box_b):
    if box_a[0] is None:
        return box_b
    if box_b[0] is None:
        return box_a
    return (
        Vector([min(box_a[0][i], box_b[0][i]) for i in range(3)]),
        Vector([max(box_a[1][i], box_b[1][i]) for i in range(3)]),
    )


static_entries = [
    (uid, layout_by_uid[uid].get("start_position", [0, 0, 1]))
    for uid in node_objects
    if uid not in first_step_of
]


def entries_for_step(index):
    # Everything on screen while step `index` plays.
    entries = list(static_entries)
    for uid, step_index in first_step_of.items():
        layout_obj = layout_by_uid[uid]
        if step_index < index:
            entries.append((uid, layout_obj.get("final_position", [0, 0, 1])))
        elif step_index == index:
            entries.append((uid, layout_obj.get("start_position", [0, 0, 1])))
            entries.append((uid, layout_obj.get("final_position", [0, 0, 1])))
    return entries


final_entries = [
    (uid, layout_obj.get("final_position", [0, 0, 1]))
    for uid, layout_obj in layout_by_uid.items()
]
upright_box = bounds_of(final_entries, upright=bool(FINALE))

all_entries = []
for uid, layout_obj in layout_by_uid.items():
    all_entries.append((uid, layout_obj.get("start_position", [0, 0, 1])))
    all_entries.append((uid, layout_obj.get("final_position", [0, 0, 1])))

scene_lo, scene_hi = union(bounds_of(all_entries), upright_box)
if scene_lo is None:
    print("ERROR: V3 scene has no visible meshes; refusing to render")
    sys.exit(1)

scene_size = max(max(scene_hi - scene_lo), 0.5)

scene = bpy.context.scene
fps = TIMELINE.get("fps", 24)
frame_end = TIMELINE["frame_end"]

scene.frame_start = 1
scene.frame_end = frame_end
scene.frame_step = {frame_step}
scene.render.fps = fps
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.resolution_percentage = {resolution_percent}
scene.render.filepath = str(OUTPUT_DIR / "frame_")
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGB"


# Finale: lift the assembly just enough to clear the floor, turn it over
# about X, and set it back down upright.
flip = TIMELINE.get("flip")
lift = 0.0
if flip:
    radius = 0.0
    for uid, position in final_entries:
        extent = node_extents.get(uid)
        if not extent:
            continue
        for y in (position[1] + extent[0].y, position[1] + extent[1].y):
            for z in (position[2] + extent[0].z, position[2] + extent[1].z):
                radius = max(radius, math.hypot(y - PIVOT.y, z - PIVOT.z))
    lift = max(0.0, radius - PIVOT.z) + 0.03

    flip_start = flip["start_frame"]
    flip_end = flip["end_frame"]
    flip_mid = (flip_start + flip_end) // 2

    pivot_obj.keyframe_insert(data_path="rotation_euler", frame=flip_start)
    pivot_obj.rotation_euler = (math.radians(FINALE.get("angle", 180.0)), 0, 0)
    pivot_obj.keyframe_insert(data_path="rotation_euler", frame=flip_end)

    keyframe_location(pivot_obj, PIVOT, flip_start)
    keyframe_location(pivot_obj, PIVOT + Vector((0, 0, lift)), flip_mid)
    keyframe_location(pivot_obj, PIVOT, flip_end)


# Camera: a fixed viewing angle that eases between framings. During the
# build the framing only ever grows (all parts so far plus the moving
# ones), so it widens gradually instead of jumping in and out. It then
# frames the turn-over and slowly orbits the finished assembly.
CAMERA_DIRECTION = Vector((0.95, -1.20, 0.72)).normalized()
ORBIT_DEGREES = 100
ORBIT_KEY_SPACING = 6

bpy.ops.object.camera_add(location=(0, 0, 0))
camera = bpy.context.object
camera.name = "Assembly_Camera"
camera.data.lens = 35
camera.data.clip_start = 0.01
camera.data.clip_end = 1000
scene.camera = camera

camera_target = create_empty("Camera_Target", (0, 0, 0))
track = camera.constraints.new(type="TRACK_TO")
track.target = camera_target
track.track_axis = "TRACK_NEGATIVE_Z"
track.up_axis = "UP_Y"

# Sensor fit AUTO puts the sensor width on the longer (horizontal) side.
tan_half_x = camera.data.sensor_width / (2 * camera.data.lens)
tan_half_y = tan_half_x * scene.render.resolution_y / scene.render.resolution_x
FRAME_MARGIN = 1.06


def framing(box, direction=CAMERA_DIRECTION):
    # (target, camera location) at the smallest distance along `direction`
    # that keeps every corner of the box in frame.
    lo, hi = box
    center = (lo + hi) / 2
    forward = -direction
    right = forward.cross(Vector((0, 0, 1))).normalized()
    up = right.cross(forward).normalized()

    distance = 0.3
    for corner in (Vector((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)):
        offset = corner - center
        depth = offset.dot(forward)
        distance = max(
            distance,
            abs(offset.dot(right)) * FRAME_MARGIN / tan_half_x - depth,
            abs(offset.dot(up)) * FRAME_MARGIN / tan_half_y - depth,
        )
    return center, center + direction * distance


def keyframe_camera(shot, frame):
    target, location = shot
    keyframe_location(camera_target, target, frame)
    keyframe_location(camera, location, frame)


build_box = (None, None)
for index, step in enumerate(steps):
    build_box = union(build_box, bounds_of(entries_for_step(index)))
    shot = framing(build_box)
    if index == 0:
        keyframe_camera(shot, 1)
    keyframe_camera(shot, step["start_frame"])
    keyframe_camera(shot, step["end_frame"])

if flip:
    lifted_hi = Vector((upright_box[1].x, upright_box[1].y, upright_box[1].z + lift))
    flip_box = union(union(build_box, upright_box), (upright_box[0], lifted_hi))
    flip_shot = framing(flip_box)
    keyframe_camera(flip_shot, flip["start_frame"])
    keyframe_camera(flip_shot, flip["end_frame"])

orbit = TIMELINE["orbit"]
orbit_frames = orbit["end_frame"] - orbit["start_frame"]
key_frames = list(range(orbit["start_frame"], orbit["end_frame"], ORBIT_KEY_SPACING)) + [orbit["end_frame"]]
for frame in key_frames:
    angle = math.radians(ORBIT_DEGREES) * (frame - orbit["start_frame"]) / orbit_frames
    direction = Matrix.Rotation(angle, 3, "Z") @ CAMERA_DIRECTION
    keyframe_camera(framing(upright_box, direction), frame)


# Studio background (EEVEE/Cycles read the world node tree, not world.color).
world = scene.world or bpy.data.worlds.new("World")
scene.world = world
world.color = (0.80, 0.82, 0.86)
if world.node_tree is None:
    world.use_nodes = True
background = world.node_tree.nodes.get("Background")
if background:
    background.inputs["Color"].default_value = (0.80, 0.82, 0.86, 1.0)
    background.inputs["Strength"].default_value = 0.35


def look_at(obj, target):
    direction = target - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


# Light energy scales with the square of the distance to the scene.
light_scale = (scene_size / 4) ** 2
scene_center = (scene_lo + scene_hi) / 2

# Large soft key light
bpy.ops.object.light_add(
    type="AREA",
    location=(scene_center.x + scene_size * 0.6, scene_center.y - scene_size * 1.5, scene_center.z + scene_size * 1.9)
)
key_light = bpy.context.object
key_light.name = "Large Softbox Key Light"
key_light.data.energy = 1500 * light_scale
key_light.data.size = scene_size * 1.2
look_at(key_light, scene_center)

# Dimmer fill from the other side keeps the shadow side readable.
bpy.ops.object.light_add(
    type="AREA",
    location=(scene_center.x - scene_size * 1.4, scene_center.y + scene_size * 0.4, scene_center.z + scene_size * 1.0)
)
fill_light = bpy.context.object
fill_light.name = "Cool Fill Light"
fill_light.data.energy = 450 * light_scale
fill_light.data.size = scene_size * 1.4
fill_light.data.color = (0.85, 0.9, 1.0)
look_at(fill_light, scene_center)

# Rim light from behind separates the parts from the background.
bpy.ops.object.light_add(
    type="AREA",
    location=(scene_center.x - scene_size * 0.4, scene_center.y + scene_size * 1.6, scene_center.z + scene_size * 1.4)
)
rim_light = bpy.context.object
rim_light.name = "Rim Light"
rim_light.data.energy = 700 * light_scale
rim_light.data.size = scene_size * 0.6
look_at(rim_light, scene_center)

# Floor just under the lowest point any part reaches.
bpy.ops.mesh.primitive_plane_add(
    size=scene_size * 20,
    location=(scene_center.x, scene_center.y, scene_lo.z - 0.002)
)
floor = bpy.context.object
floor.name = "Floor"
floor.data.materials.append(MATERIALS["floor"])

scene.render.engine = "BLENDER_EEVEE"
scene.eevee.taa_render_samples = 32
scene.view_settings.view_transform = "Filmic"
scene.view_settings.look = "Medium High Contrast"
scene.view_settings.exposure = -0.3
scene.view_settings.gamma = 1

print("V3 project root:", PROJECT_ROOT)
print("V3 frames output:", OUTPUT_DIR)
print("V3 layout objects:", len(layout_objects))
print("V3 created objects:", len(node_objects))
print("V3 animated objects:", animated_count)
print("V3 motion steps:", len(steps))
print("V3 frame range:", scene.frame_start, "-", scene.frame_end, "step", scene.frame_step)
print("Rendering V3 frames...")

bpy.ops.render.render(animation=True)
"""

    save_text(script, output_script)
    print(f"Saved Blender V3 script to {output_script}")
    print(f"Saved render timeline to {RENDER_TIMELINE_JSON}")


if __name__ == "__main__":
    build_blender_script()
