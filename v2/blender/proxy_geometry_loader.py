import bpy
import json
from pathlib import Path
from mathutils import Vector


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def create_material(name, color):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    return mat


def add_box(obj_data, material):
    dims = obj_data.get("dimensions", [1, 1, 1])
    loc = obj_data.get("location", [0, 0, 0])

    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.object
    obj.name = obj_data.get("object_uid", "proxy_box")
    obj.dimensions = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    return obj


def add_cylinder(obj_data, material):
    dims = obj_data.get("dimensions", [0.2, 0.2, 1.0])
    loc = obj_data.get("location", [0, 0, 0])

    radius = max(dims[0], dims[1]) / 2
    depth = dims[2]

    bpy.ops.mesh.primitive_cylinder_add(
        vertices=32,
        radius=radius,
        depth=depth,
        location=loc
    )

    obj = bpy.context.object
    obj.name = obj_data.get("object_uid", "proxy_cylinder")
    obj.data.materials.append(material)
    return obj


def add_hole_markers(parent_obj, obj_data, material):
    holes = obj_data.get("holes", [])
    dims = obj_data.get("dimensions", [1, 1, 1])
    base_loc = Vector(obj_data.get("location", [0, 0, 0]))

    for hole in holes:
        rel = hole.get("relative_position", [0.5, 0.5])
        x = base_loc.x + (rel[0] - 0.5) * dims[0]
        y = base_loc.y - dims[1] / 2 - 0.01
        z = base_loc.z + (rel[1] - 0.5) * dims[2]

        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=16,
            ring_count=8,
            radius=hole.get("radius_hint", 0.04),
            location=[x, y, z]
        )

        marker = bpy.context.object
        marker.name = f"{parent_obj.name}_hole_marker"
        marker.data.materials.append(material)


def load_proxy_geometry(proxy_geometry_path):
    path = Path(proxy_geometry_path)

    if not path.exists():
        raise FileNotFoundError(f"Missing proxy geometry file: {path}")

    with open(path, "r", encoding="utf-8") as f:
        proxy_geometry = json.load(f)

    proxy_mat = create_material("manual_proxy_material", (0.65, 0.65, 0.65, 1))
    hole_mat = create_material("hole_marker_material", (0.02, 0.02, 0.02, 1))

    created_objects = []

    for obj_data in proxy_geometry.get("objects", []):
        primitive = obj_data.get("primitive", "box")

        if primitive == "cylinder":
            obj = add_cylinder(obj_data, proxy_mat)
        else:
            obj = add_box(obj_data, proxy_mat)

        add_hole_markers(obj, obj_data, hole_mat)
        created_objects.append(obj)

    return created_objects


def setup_camera():
    bpy.ops.object.light_add(type="AREA", location=(0, -5, 7))
    light = bpy.context.object
    light.name = "Main_Area_Light"
    light.data.energy = 500
    light.data.size = 5

    bpy.ops.object.camera_add(location=(4, -7, 4), rotation=(1.1, 0, 0.55))
    bpy.context.scene.camera = bpy.context.object


def main():
    clear_scene()
    load_proxy_geometry("v2/output/proxy_geometry.json")
    setup_camera()

    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = 120

    bpy.ops.wm.save_as_mainfile(filepath="v2/output/proxy_geometry_scene.blend")

    print("✅ Proxy geometry scene created")


if __name__ == "__main__":
    main()