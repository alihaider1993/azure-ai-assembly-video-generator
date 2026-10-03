"""
Proxy Geometry Builder — v2

Now a thin pass-through: part_shape_extractor_agent.py already computes
correct canonical part_uid, primitive, shape_type, and real-measurement
dimensions. This stage no longer re-buckets dimensions or invents a grid
layout (the "location"/"rotation" fields were never actually used by
blender_builder_v3.py anyway — object placement comes from
scene_layout.json's start_position via the parent empty).
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from config import PART_SHAPES_JSON, PROXY_GEOMETRY_JSON


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


DEFAULT_DIMENSIONS = [0.5, 0.1, 0.3]


def valid_dimensions(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 3
        and all(isinstance(x, (int, float)) and x > 0 for x in value)
    )


def build_proxy_geometry():
    part_shapes = load_json(PART_SHAPES_JSON)

    if not part_shapes.get("parts"):
        raise ValueError(f"{PART_SHAPES_JSON} has no parts; upstream extraction produced nothing to render")

    proxy_geometry = {
        "metadata": {
            "created_at": datetime.utcnow().isoformat(),
            "source": "part_shapes.json",
            "note": "Canonical-ID-keyed proxy geometry for Blender MVP render",
        },
        "objects": [],
    }

    for index, shape in enumerate(part_shapes["parts"], start=1):
        part_uid = shape["part_uid"]  # canonical OBJ*/FAST* id — matched directly by blender_builder_v3.py

        dimensions = shape.get("dimensions")
        if not valid_dimensions(dimensions):
            # A zero/negative/missing size would build an invisible or broken mesh.
            print(f"[WARNING] {part_uid}: invalid dimensions {dimensions!r}; using {DEFAULT_DIMENSIONS}")
            dimensions = DEFAULT_DIMENSIONS

        proxy_geometry["objects"].append({
            "object_uid": f"OBJ_PROXY_{index:04d}",
            "part_uid": part_uid,
            "name": shape.get("canonical_name", part_uid)[:80],
            "primitive": shape.get("primitive", "box"),
            "shape_type": shape.get("shape_type", "proxy_block"),
            "dimensions": dimensions,
            # Local offset/rotation of the mesh relative to its scene node.
            # World placement comes from scene_layout.json.
            "location": [0.0, 0.0, 0.0],
            "rotation": [0.0, 0.0, 0.0],
            "holes": shape.get("holes", []),
            "anchor_points": shape.get("anchor_points", []),
            "visual_features": {
                "rounded_corners": shape.get("has_rounded_corners", False),
                "labels": shape.get("labels", []),
            },
            "render_style": {
                "material": "manual_proxy",
                "show_holes_as_markers": True,
                "show_labels": True,
            },
        })

    PROXY_GEOMETRY_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(PROXY_GEOMETRY_JSON, "w", encoding="utf-8") as f:
        json.dump(proxy_geometry, f, indent=2)

    print("[SUCCESS] Proxy Geometry Builder complete")
    print(f"Proxy objects: {len(proxy_geometry['objects'])}")
    print(f"Output: {PROXY_GEOMETRY_JSON}")


if __name__ == "__main__":
    build_proxy_geometry()