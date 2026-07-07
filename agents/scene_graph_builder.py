import json
from pathlib import Path


def make_obj(object_id, name, shape, dims, start, end, material="wood", rotation=0):
    return {
        "object_id": object_id,
        "name": name,
        "shape": shape,
        "dimensions": {
            "length": dims[0],
            "width": dims[1],
            "height": dims[2],
            "unit": "generic"
        },
        "start_position": {"x": start[0], "y": start[1], "z": start[2]},
        "end_position": {"x": end[0], "y": end[1], "z": end[2]},
        "rotation": {"axis": "z", "degrees": rotation},
        "material": material
    }


def build_table_scene(product):
    objects = []

    objects.append(
        make_obj(
            "tabletop",
            "Tabletop",
            "cuboid",
            (5.0, 3.0, 0.18),
            (0, 0, 2.8),
            (0, 0, 2.8)
        )
    )

    objects.extend([
        make_obj("front_rail", "Front Rail", "cuboid", (5.0, 0.18, 0.25), (0, -5, 2.45), (0, -1.35, 2.45)),
        make_obj("back_rail", "Back Rail", "cuboid", (5.0, 0.18, 0.25), (0, 5, 2.45), (0, 1.35, 2.45)),
        make_obj("left_rail", "Left Rail", "cuboid", (0.18, 3.0, 0.25), (-5, 0, 2.45), (-2.35, 0, 2.45)),
        make_obj("right_rail", "Right Rail", "cuboid", (0.18, 3.0, 0.25), (5, 0, 2.45), (2.35, 0, 2.45)),
    ])

    objects.extend([
        make_obj("leg_1", "Front Left Leg", "cuboid", (0.25, 0.25, 2.4), (-2.35, -1.35, -1.5), (-2.35, -1.35, 1.3)),
        make_obj("leg_2", "Front Right Leg", "cuboid", (0.25, 0.25, 2.4), (2.35, -1.35, -1.5), (2.35, -1.35, 1.3)),
        make_obj("leg_3", "Back Left Leg", "cuboid", (0.25, 0.25, 2.4), (-2.35, 1.35, -1.5), (-2.35, 1.35, 1.3)),
        make_obj("leg_4", "Back Right Leg", "cuboid", (0.25, 0.25, 2.4), (2.35, 1.35, -1.5), (2.35, 1.35, 1.3)),
    ])

    screw_positions = [
        (-2.1, -1.25), (0, -1.25), (2.1, -1.25),
        (-2.1, 1.25), (0, 1.25), (2.1, 1.25),
        (-2.25, 0), (2.25, 0)
    ]

    for i, (x, y) in enumerate(screw_positions, start=1):
        objects.append(
            make_obj(
                f"screw_{i}",
                f"Screw {i}",
                "cylinder",
                (0.08, 0.08, 0.45),
                (x, y, 4.0),
                (x, y, 2.55),
                material="metal",
                rotation=360
            )
        )

    return {
        "scene_number": 1,
        "title": "Table Assembly",
        "manual_category": "table",
        "duration_seconds": 8,
        "objects": objects,
        "camera": {
            "angle": "isometric",
            "zoom": 1.2,
            "focus_object": "tabletop"
        },
        "narration": "Slide the rails into position, raise the legs into the corners, and secure the table using the supplied screws.",
        "warnings": []
    }


def build_chair_scene(product):
    objects = [
        make_obj("seat", "Seat Panel", "cuboid", (3, 3, 0.22), (0, 0, 2.2), (0, 0, 2.2)),
        make_obj("backrest", "Backrest", "cuboid", (3, 0.25, 2.4), (0, 4, 3.2), (0, 1.4, 3.2)),
        make_obj("leg_1", "Front Left Leg", "cuboid", (0.22, 0.22, 2), (-1.2, -1.2, -1.4), (-1.2, -1.2, 1.1)),
        make_obj("leg_2", "Front Right Leg", "cuboid", (0.22, 0.22, 2), (1.2, -1.2, -1.4), (1.2, -1.2, 1.1)),
        make_obj("leg_3", "Back Left Leg", "cuboid", (0.22, 0.22, 2.3), (-1.2, 1.2, -1.5), (-1.2, 1.2, 1.2)),
        make_obj("leg_4", "Back Right Leg", "cuboid", (0.22, 0.22, 2.3), (1.2, 1.2, -1.5), (1.2, 1.2, 1.2)),
        make_obj("support_1", "Left Support Rail", "cuboid", (2.5, 0.12, 0.16), (-4, -1.1, 1.7), (0, -1.1, 1.7)),
        make_obj("support_2", "Right Support Rail", "cuboid", (2.5, 0.12, 0.16), (4, 1.1, 1.7), (0, 1.1, 1.7)),
    ]

    return {
        "scene_number": 1,
        "title": "Chair Assembly",
        "manual_category": "chair",
        "duration_seconds": 8,
        "objects": objects,
        "camera": {"angle": "isometric", "zoom": 1.2, "focus_object": "seat"},
        "narration": "Attach the legs to the seat, slide the supports into place, and install the backrest.",
        "warnings": []
    }


def build_generic_scene(product):
    objects = [
        make_obj("base", "Base Panel", "cuboid", (4, 2.5, 0.2), (0, 0, 1), (0, 0, 1)),
        make_obj("part_a", "Component A", "cuboid", (2, 0.25, 1.5), (-4, 0, 1.8), (-1, 0, 1.8)),
        make_obj("part_b", "Component B", "cuboid", (2, 0.25, 1.5), (4, 0, 1.8), (1, 0, 1.8)),
        make_obj("fastener_1", "Fastener 1", "cylinder", (0.08, 0.08, 0.5), (0, -3, 2.2), (0, -0.8, 1.2), material="metal", rotation=360),
        make_obj("fastener_2", "Fastener 2", "cylinder", (0.08, 0.08, 0.5), (0, 3, 2.2), (0, 0.8, 1.2), material="metal", rotation=360),
    ]

    return {
        "scene_number": 1,
        "title": "Generic Assembly",
        "manual_category": "generic_diy",
        "duration_seconds": 8,
        "objects": objects,
        "camera": {"angle": "isometric", "zoom": 1.2, "focus_object": "base"},
        "narration": "Align the main components and secure them using the supplied fasteners.",
        "warnings": []
    }


def build_scene_graph_from_product(
    product_model_path="outputs/json/product_model.json",
    output_path="outputs/json/scene_graph_layout.json"
):
    product = json.loads(Path(product_model_path).read_text(encoding="utf-8"))

    product_type = product.get("product_type", "").lower()
    product_name = product.get("product_name", "").lower()

    if "table" in product_type or "table" in product_name:
        scene = build_table_scene(product)
    elif "chair" in product_type or "chair" in product_name:
        scene = build_chair_scene(product)
    else:
        scene = build_generic_scene(product)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(scene, indent=2), encoding="utf-8")

    print(f"Scene graph created from product model: {output_path}")
    return scene


if __name__ == "__main__":
    build_scene_graph_from_product()