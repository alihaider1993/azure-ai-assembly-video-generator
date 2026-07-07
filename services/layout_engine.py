import json
from pathlib import Path


def normalize_scene_graph(
    input_path: str = "outputs/json/scene_graph.json",
    output_path: str = "outputs/json/scene_graph_layout.json"
):
    scene = json.loads(Path(input_path).read_text(encoding="utf-8"))

    category = scene.get("manual_category", "").lower()
    title = scene.get("title", "").lower()

    if "chair" in category or "chair" in title:
        scene = apply_chair_layout(scene)
    elif "sofa" in category or "sofa" in title:
        scene = apply_sofa_layout(scene)
    elif "shelf" in category or "bookcase" in category:
        scene = apply_shelf_layout(scene)
    elif "cabinet" in category or "drawer" in category:
        scene = apply_cabinet_layout(scene)
    elif "bed" in category:
        scene = apply_bed_layout(scene)
    elif "table" in category or "table" in title or "furniture" in category:
        scene = apply_table_layout(scene)
    else:
        scene = apply_generic_layout(scene)

    scene["camera"] = {
        "angle": "isometric",
        "zoom": 1.2,
        "focus_object": "product_center"
    }

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(scene, indent=2), encoding="utf-8")

    print(f"Layout scene saved to {output_path}")
    return scene


def obj(object_id, name, shape, dims, start, end, rotation=0):
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
        "rotation": {"axis": "z", "degrees": rotation}
    }


def apply_table_layout(scene):
    scene["manual_category"] = "table"
    scene["title"] = scene.get("title") or "Table Assembly"

    objects = [
        obj("tabletop", "Tabletop", "cuboid", (5, 3, 0.18), (0, 0, 2.8), (0, 0, 2.8)),
        obj("front_rail", "Front Rail", "cuboid", (5, 0.18, 0.25), (0, -5, 2.45), (0, -1.35, 2.45)),
        obj("back_rail", "Back Rail", "cuboid", (5, 0.18, 0.25), (0, 5, 2.45), (0, 1.35, 2.45)),
        obj("left_rail", "Left Rail", "cuboid", (0.18, 3, 0.25), (-5, 0, 2.45), (-2.35, 0, 2.45)),
        obj("right_rail", "Right Rail", "cuboid", (0.18, 3, 0.25), (5, 0, 2.45), (2.35, 0, 2.45)),

        obj("leg_1", "Leg 1", "cuboid", (0.25, 0.25, 2.4), (-2.35, -1.35, -1.5), (-2.35, -1.35, 1.3)),
        obj("leg_2", "Leg 2", "cuboid", (0.25, 0.25, 2.4), (2.35, -1.35, -1.5), (2.35, -1.35, 1.3)),
        obj("leg_3", "Leg 3", "cuboid", (0.25, 0.25, 2.4), (-2.35, 1.35, -1.5), (-2.35, 1.35, 1.3)),
        obj("leg_4", "Leg 4", "cuboid", (0.25, 0.25, 2.4), (2.35, 1.35, -1.5), (2.35, 1.35, 1.3)),
    ]

    screw_positions = [
        (-2, -1.2), (0, -1.2), (2, -1.2),
        (-2, 1.2), (0, 1.2), (2, 1.2),
        (-2.2, 0), (2.2, 0)
    ]

    for i, (x, y) in enumerate(screw_positions, start=1):
        objects.append(
            obj(
                f"screw_{i}",
                f"Screw {i}",
                "cylinder",
                (0.08, 0.08, 0.45),
                (x, y, 4.0),
                (x, y, 2.55),
                360
            )
        )

    scene["objects"] = objects
    scene["narration"] = "Slide the frame rails into position, raise the four legs into the corners, and secure the table using the supplied screws."
    return scene


def apply_chair_layout(scene):
    scene["manual_category"] = "chair"
    scene["title"] = scene.get("title") or "Chair Assembly"

    scene["objects"] = [
        obj("seat", "Seat Panel", "cuboid", (3, 3, 0.22), (0, 0, 2.2), (0, 0, 2.2)),
        obj("backrest", "Backrest", "cuboid", (3, 0.25, 2.5), (0, 4, 3.2), (0, 1.4, 3.2), 0),
        obj("leg_1", "Front Left Leg", "cuboid", (0.22, 0.22, 2), (-1.2, -1.2, -1.3), (-1.2, -1.2, 1.1)),
        obj("leg_2", "Front Right Leg", "cuboid", (0.22, 0.22, 2), (1.2, -1.2, -1.3), (1.2, -1.2, 1.1)),
        obj("leg_3", "Back Left Leg", "cuboid", (0.22, 0.22, 2.4), (-1.2, 1.2, -1.4), (-1.2, 1.2, 1.2)),
        obj("leg_4", "Back Right Leg", "cuboid", (0.22, 0.22, 2.4), (1.2, 1.2, -1.4), (1.2, 1.2, 1.2)),
        obj("support_1", "Side Support", "cuboid", (2.5, 0.12, 0.16), (-4, -1.1, 1.7), (0, -1.1, 1.7)),
        obj("support_2", "Back Support", "cuboid", (2.5, 0.12, 0.16), (4, 1.1, 1.7), (0, 1.1, 1.7)),
    ]

    scene["narration"] = "Attach the legs to the seat, slide the supports into position, and install the backrest."
    return scene


def apply_sofa_layout(scene):
    scene["manual_category"] = "sofa"
    scene["objects"] = [
        obj("base", "Sofa Base", "cuboid", (5, 2.5, 0.5), (0, 0, 1.2), (0, 0, 1.2)),
        obj("left_arm", "Left Arm", "cuboid", (0.4, 2.5, 1.4), (-4, 0, 1.8), (-2.7, 0, 1.8)),
        obj("right_arm", "Right Arm", "cuboid", (0.4, 2.5, 1.4), (4, 0, 1.8), (2.7, 0, 1.8)),
        obj("back", "Back Panel", "cuboid", (5, 0.35, 1.6), (0, 4, 2), (0, 1.4, 2)),
        obj("cushion_1", "Seat Cushion 1", "cuboid", (1.5, 2.2, 0.3), (-1.2, -4, 1.65), (-1.2, 0, 1.65)),
        obj("cushion_2", "Seat Cushion 2", "cuboid", (1.5, 2.2, 0.3), (1.2, -4, 1.65), (1.2, 0, 1.65)),
    ]
    scene["narration"] = "Assemble the sofa base, attach the side arms and back panel, then place the seat cushions."
    return scene


def apply_shelf_layout(scene):
    scene["manual_category"] = "shelf"
    scene["objects"] = [
        obj("left_side", "Left Side Panel", "cuboid", (0.25, 2.5, 4), (-4, 0, 2), (-1.6, 0, 2)),
        obj("right_side", "Right Side Panel", "cuboid", (0.25, 2.5, 4), (4, 0, 2), (1.6, 0, 2)),
        obj("bottom_shelf", "Bottom Shelf", "cuboid", (3.2, 2.4, 0.2), (0, -4, 0.4), (0, 0, 0.4)),
        obj("middle_shelf", "Middle Shelf", "cuboid", (3.2, 2.4, 0.2), (0, -4, 2), (0, 0, 2)),
        obj("top_shelf", "Top Shelf", "cuboid", (3.2, 2.4, 0.2), (0, -4, 3.8), (0, 0, 3.8)),
        obj("back_panel", "Back Panel", "cuboid", (3.2, 0.12, 4), (0, 4, 2), (0, 1.25, 2)),
    ]
    scene["narration"] = "Attach the side panels, slide the shelves into position, and secure the back panel."
    return scene


def apply_cabinet_layout(scene):
    scene["manual_category"] = "cabinet"
    scene["objects"] = [
        obj("left_panel", "Left Panel", "cuboid", (0.25, 2.5, 3), (-4, 0, 1.5), (-1.6, 0, 1.5)),
        obj("right_panel", "Right Panel", "cuboid", (0.25, 2.5, 3), (4, 0, 1.5), (1.6, 0, 1.5)),
        obj("top_panel", "Top Panel", "cuboid", (3.2, 2.4, 0.2), (0, 4, 3), (0, 0, 3)),
        obj("bottom_panel", "Bottom Panel", "cuboid", (3.2, 2.4, 0.2), (0, -4, 0.2), (0, 0, 0.2)),
        obj("door_left", "Left Door", "cuboid", (1.5, 0.15, 2.5), (-4, -1.35, 1.5), (-0.8, -1.35, 1.5)),
        obj("door_right", "Right Door", "cuboid", (1.5, 0.15, 2.5), (4, -1.35, 1.5), (0.8, -1.35, 1.5)),
    ]
    scene["narration"] = "Assemble the cabinet frame and attach the doors to the front."
    return scene


def apply_bed_layout(scene):
    scene["manual_category"] = "bed"
    scene["objects"] = [
        obj("headboard", "Headboard", "cuboid", (4.5, 0.3, 2), (0, 5, 1.5), (0, 2, 1.5)),
        obj("footboard", "Footboard", "cuboid", (4.5, 0.3, 1.2), (0, -5, 1), (0, -2, 1)),
        obj("left_rail", "Left Side Rail", "cuboid", (0.25, 4, 0.4), (-5, 0, 0.8), (-2.1, 0, 0.8)),
        obj("right_rail", "Right Side Rail", "cuboid", (0.25, 4, 0.4), (5, 0, 0.8), (2.1, 0, 0.8)),
    ]

    for i in range(6):
        y = -1.5 + i * 0.6
        scene["objects"].append(
            obj(f"slat_{i+1}", f"Bed Slat {i+1}", "cuboid", (4, 0.12, 0.12), (0, -5, 1.1), (0, y, 1.1))
        )

    scene["narration"] = "Connect the headboard, footboard, side rails, and place the support slats."
    return scene


def apply_generic_layout(scene):
    scene["manual_category"] = "generic_diy"
    scene["objects"] = [
        obj("base_panel", "Base Panel", "cuboid", (4, 2.5, 0.2), (0, 0, 1), (0, 0, 1)),
        obj("part_a", "Panel A", "cuboid", (2, 0.25, 1.5), (-4, 0, 1.8), (-1, 0, 1.8)),
        obj("part_b", "Panel B", "cuboid", (2, 0.25, 1.5), (4, 0, 1.8), (1, 0, 1.8)),
        obj("fastener_1", "Fastener 1", "cylinder", (0.08, 0.08, 0.5), (0, -3, 2.2), (0, -0.8, 1.2), 360),
        obj("fastener_2", "Fastener 2", "cylinder", (0.08, 0.08, 0.5), (0, 3, 2.2), (0, 0.8, 1.2), 360),
    ]
    scene["narration"] = "Align the main components and secure them using the supplied fasteners."
    return scene


if __name__ == "__main__":
    normalize_scene_graph()