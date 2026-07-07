import json
from pathlib import Path

from rendering.animation_engine import get_animation_code, get_step_frames
from rendering.camera_engine import get_camera_code
from rendering.material_engine import get_material_name


class BlenderBuilder:
    def build_script(
        self,
        scene_graph_path="outputs/json/scene_graph_layout.json",
        output_script_path="blender/generated/generated_blender_scene.py"
    ):
        scene = json.loads(Path(scene_graph_path).read_text(encoding="utf-8"))

        project_root = Path.cwd()
        frames_dir = project_root / "outputs" / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)

        blender_filepath = str(frames_dir / "scene_frame_").replace("\\", "/")

        script = f'''
import bpy
import math
from pathlib import Path
from mathutils import Vector

Path(r"{frames_dir}").mkdir(parents=True, exist_ok=True)

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()

def make_material(name, color):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = 0.45
    return mat

materials = {{
    "wood": make_material("Wood", (0.72, 0.42, 0.18, 1)),
    "light_wood": make_material("Light Wood", (0.90, 0.58, 0.25, 1)),
    "dark_wood": make_material("Dark Wood", (0.28, 0.13, 0.04, 1)),
    "metal": make_material("Metal", (0.82, 0.82, 0.88, 1)),
    "plastic": make_material("Plastic", (0.02, 0.02, 0.02, 1)),
    "fabric": make_material("Fabric", (0.15, 0.25, 0.70, 1)),
    "highlight": make_material("Highlight", (1.0, 0.45, 0.05, 1)),
}}

def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

def assign_material(obj, material_name):
    mat = materials.get(material_name, materials.get("wood"))
    obj.data.materials.append(mat)

def create_cuboid(name, location, scale, material_name):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    assign_material(obj, material_name)
    return obj

def create_cylinder(name, location, scale, material_name):
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=1, depth=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    assign_material(obj, material_name)
    return obj

def create_wheel(name, location, scale, material_name):
    bpy.ops.mesh.primitive_torus_add(
        major_radius=max(scale[0], scale[1]),
        minor_radius=max(0.04, scale[2]),
        location=location
    )
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler[1] = math.radians(90)
    assign_material(obj, material_name)
    return obj

def create_bracket(name, location, scale, material_name):
    main = create_cuboid(name, location, (scale[0], scale[1], scale[2]), material_name)

    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=(location[0] + scale[0] * 0.45, location[1], location[2] + scale[2] * 0.45)
    )
    lip = bpy.context.object
    lip.name = name + "_lip"
    lip.scale = (scale[2], scale[1], scale[0])
    assign_material(lip, material_name)
    lip.parent = main

    return main

def create_hinge(name, location, scale, material_name):
    plate = create_cuboid(name, location, scale, material_name)

    bpy.ops.mesh.primitive_cylinder_add(
        vertices=32,
        radius=0.08,
        depth=scale[0] * 1.2,
        location=(location[0], location[1], location[2] + scale[2] * 0.6),
        rotation=(0, math.radians(90), 0)
    )
    pin = bpy.context.object
    pin.name = name + "_pin"
    assign_material(pin, material_name)
    pin.parent = plate

    return plate

def create_curved(name, location, scale, material_name):
    bpy.ops.mesh.primitive_torus_add(
        major_radius=max(scale[0], scale[2]) * 0.45,
        minor_radius=max(0.04, scale[1] * 0.4),
        location=location
    )
    obj = bpy.context.object
    obj.name = name
    obj.scale = (1, 0.25, 1)
    assign_material(obj, material_name)
    return obj

def add_fastener_slot(parent, location):
    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=(location[0], location[1], location[2] + 0.35)
    )
    slot = bpy.context.object
    slot.name = parent.name + "_black_slot"
    slot.scale = (0.18, 0.025, 0.02)
    assign_material(slot, "plastic")
    slot.parent = parent
    return slot

def create_object(name, shape, geometry_type, location, scale, material_name):
    shape = shape.lower()
    geometry_type = geometry_type.lower()

    if shape == "cylinder":
        obj = create_cylinder(name, location, scale, material_name)
        add_fastener_slot(obj, location)
        return obj

    if shape == "wheel":
        return create_wheel(name, location, scale, material_name)

    if shape == "bracket":
        return create_bracket(name, location, scale, material_name)

    if shape == "hinge":
        return create_hinge(name, location, scale, material_name)

    if shape == "curved":
        return create_curved(name, location, scale, material_name)

    return create_cuboid(name, location, scale, material_name)

objects = []
'''

        for obj in scene["objects"]:
            dims = obj["dimensions"]
            start = obj["start_position"]
            material_name = get_material_name(
                obj.get("name", ""),
                obj.get("material", "")
            )

            scale = (
                max(0.04, float(dims.get("length", 1))),
                max(0.04, float(dims.get("width", 1))),
                max(0.04, float(dims.get("height", 1))),
            )

            start_frame, end_frame = get_step_frames(obj)

            safe_name = str(obj.get("name", "Object")).replace('"', "'")
            shape = obj.get("shape", "cuboid")
            geometry_type = obj.get("geometry_type", shape)

            script += f'''
obj = create_object(
    name="{safe_name}",
    shape="{shape}",
    geometry_type="{geometry_type}",
    location=({start["x"]}, {start["y"]}, {start["z"]}),
    scale={scale},
    material_name="{material_name}"
)

{get_animation_code(obj, start_frame, end_frame)}

objects.append(obj)
'''

        script += f'''
{get_camera_code()}

bpy.ops.object.light_add(type="AREA", location=(0, -6, 8))
light = bpy.context.object
light.data.energy = 1300
light.data.size = 7

bpy.ops.object.light_add(type="POINT", location=(4, -4, 5))
point_light = bpy.context.object
point_light.data.energy = 260

bpy.ops.mesh.primitive_plane_add(size=18, location=(0, 0, -0.05))
floor = bpy.context.object
floor.name = "Assembly Floor"
assign_material(floor, "plastic")

bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = 260
bpy.context.scene.render.fps = 24

bpy.context.scene.render.engine = "BLENDER_EEVEE"
bpy.context.scene.render.resolution_x = 1280
bpy.context.scene.render.resolution_y = 720
bpy.context.scene.render.filepath = r"{blender_filepath}"
bpy.context.scene.render.image_settings.file_format = "PNG"

bpy.context.scene.world.color = (1, 1, 1)

bpy.context.scene.view_settings.view_transform = "Standard"
bpy.context.scene.view_settings.look = "Medium High Contrast"
bpy.context.scene.view_settings.exposure = 0
bpy.context.scene.view_settings.gamma = 1

bpy.ops.render.render(animation=True)
'''

        Path(output_script_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_script_path).write_text(script, encoding="utf-8")

        print(f"Blender script generated: {output_script_path}")