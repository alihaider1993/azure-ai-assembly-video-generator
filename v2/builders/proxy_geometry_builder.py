import json
from pathlib import Path
from datetime import datetime


INPUT_PART_SHAPES = Path("v2/output/part_shapes.json")
INPUT_SCENE_LAYOUT = Path("v2/output/scene_layout.json")
OUTPUT_PROXY_GEOMETRY = Path("v2/output/proxy_geometry.json")


def load_json(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def dimensions_for_shape(shape):
    shape_type = shape.get("shape_type", "proxy_block")
    aspect = shape.get("aspect_ratio", 1.0)

    if shape_type == "rounded_panel":
        return [2.2, 1.6, 0.18]

    if shape_type == "thin_plate":
        return [1.2, 0.6, 0.12]

    if shape_type == "rectangular_beam":
        return [0.25, 0.25, 1.8]

    if shape_type == "long_cylinder":
        return [0.18, 0.18, 1.8]

    if shape_type == "cylinder":
        return [0.12, 0.12, 0.5]

    return [max(0.6, aspect), 0.5, 0.3]


def primitive_for_shape(shape_type):
    if shape_type in ["cylinder", "long_cylinder"]:
        return "cylinder"
    if shape_type == "rounded_panel":
        return "rounded_box"
    return "box"


def build_proxy_geometry():
    part_shapes = load_json(INPUT_PART_SHAPES)

    scene_layout = {}
    if INPUT_SCENE_LAYOUT.exists():
        scene_layout = load_json(INPUT_SCENE_LAYOUT)

    proxy_geometry = {
        "metadata": {
            "created_at": datetime.utcnow().isoformat(),
            "source": "part_shapes.json",
            "mvp_note": "Simple recognisable proxy geometry for Blender MVP"
        },
        "objects": []
    }

    for idx, shape in enumerate(part_shapes.get("parts", []), start=1):
        part_uid = shape["part_uid"]
        shape_type = shape.get("shape_type", "proxy_block")

        dimensions = dimensions_for_shape(shape)

        obj = {
            "object_uid": f"OBJ_PROXY_{idx:04d}",
            "part_uid": part_uid,
            "name": shape.get("description", part_uid)[:80],
            "primitive": primitive_for_shape(shape_type),
            "shape_type": shape_type,
            "dimensions": dimensions,
            "location": [
                (idx % 4) * 1.4 - 2.8,
                (idx // 4) * 1.2,
                1.0
            ],
            "rotation": [0, 0, 0],
            "holes": shape.get("holes", []),
            "anchor_points": shape.get("anchor_points", []),
            "visual_features": {
                "rounded_corners": shape.get("has_rounded_corners", False),
                "slots": shape.get("has_slots", False),
                "labels": shape.get("labels", []),
                "contains_fasteners": shape.get("contains_fasteners", False)
            },
            "render_style": {
                "material": "manual_proxy",
                "show_holes_as_markers": True,
                "show_labels": True
            }
        }

        proxy_geometry["objects"].append(obj)

    OUTPUT_PROXY_GEOMETRY.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PROXY_GEOMETRY, "w", encoding="utf-8") as f:
        json.dump(proxy_geometry, f, indent=2)

    print("[SUCCESS] Proxy Geometry Builder complete")
    print(f"Proxy objects: {len(proxy_geometry['objects'])}")
    print(f"Output: {OUTPUT_PROXY_GEOMETRY}")


if __name__ == "__main__":
    build_proxy_geometry()