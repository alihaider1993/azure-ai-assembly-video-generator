import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


GRAPH_PATH = Path("v2/outputs/json/universal_assembly_graph.json")
MOTION_PLAN_PATH = Path("v2/outputs/json/motion_plan.json")
OUTPUT_PATH = Path("v2/outputs/json/geometry_spec.json")


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def norm(value: Any) -> str:
    return str(value or "").strip().lower()


def new_geometry_uid(index: int) -> str:
    return f"G{index:04d}"


def material_category(material_hint: str, shape_family: str) -> str:
    material = norm(material_hint)
    shape = norm(shape_family)

    allowed = {"wood", "metal", "plastic", "glass", "fabric", "rubber", "mixed", "unknown"}

    if material in allowed:
        return material

    if shape in {"screw", "bolt", "nut", "washer", "bracket", "hinge", "cylinder"}:
        return "metal"

    return "unknown"


def semantic_type(shape_family: str) -> str:
    shape = norm(shape_family)

    mapping = {
        "panel": "panel",
        "beam": "beam",
        "frame": "frame",
        "curved": "curved",
        "cylinder": "cylinder",
        "bracket": "bracket",
        "hinge": "hinge",
        "wheel": "wheel",
        "cable": "cable",
        "electronics": "electronics_box",
        "irregular": "irregular",
        "screw": "cylinder",
        "bolt": "cylinder",
        "washer": "cylinder",
        "nut": "cylinder",
    }

    return mapping.get(shape, "irregular")


def default_dimensions(shape_family: str, quantity: int = 1) -> Tuple[float, float, float]:
    shape = norm(shape_family)

    if shape == "panel":
        return 1.2, 0.08, 0.8

    if shape == "beam":
        return 1.2, 0.08, 0.08

    if shape == "frame":
        return 1.4, 0.12, 1.4

    if shape == "curved":
        return 1.0, 0.08, 0.35

    if shape == "bracket":
        return 0.25, 0.05, 0.25

    if shape in {"cylinder", "screw", "bolt"}:
        return 0.08, 0.08, 0.45

    if shape in {"washer", "nut"}:
        return 0.14, 0.14, 0.05

    if shape == "hinge":
        return 0.25, 0.05, 0.18

    if shape == "wheel":
        return 0.35, 0.08, 0.35

    if shape == "cable":
        return 0.8, 0.03, 0.03

    if shape == "electronics":
        return 0.5, 0.08, 0.35

    return 0.5, 0.1, 0.3


def primitive_cuboid(size, offset=None, rotation=None) -> Dict[str, Any]:
    return {
        "primitive": "cuboid",
        "size": size,
        "offset": offset or [0.0, 0.0, 0.0],
        "rotation": rotation or [0.0, 0.0, 0.0]
    }


def primitive_cylinder(size, offset=None, rotation=None) -> Dict[str, Any]:
    return {
        "primitive": "cylinder",
        "size": size,
        "offset": offset or [0.0, 0.0, 0.0],
        "rotation": rotation or [0.0, 0.0, 0.0]
    }


def primitive_curve(size, offset=None, rotation=None) -> Dict[str, Any]:
    return {
        "primitive": "curve",
        "size": size,
        "offset": offset or [0.0, 0.0, 0.0],
        "rotation": rotation or [0.0, 0.0, 0.0],
        "curve_type": "arc"
    }


def build_panel(size: Tuple[float, float, float]) -> List[Dict[str, Any]]:
    x, y, z = size
    return [primitive_cuboid([x, max(y, 0.04), max(z, 0.04)])]


def build_beam(size: Tuple[float, float, float]) -> List[Dict[str, Any]]:
    x, y, z = size
    return [primitive_cuboid([max(x, 0.5), max(y, 0.05), max(z, 0.05)])]


def build_frame(size: Tuple[float, float, float]) -> List[Dict[str, Any]]:
    width, thickness, height = size
    t = max(thickness, 0.06)
    w = max(width, 1.0)
    h = max(height, 1.0)

    return [
        primitive_cuboid([w, t, t], [0.0, 0.0, h / 2]),
        primitive_cuboid([w, t, t], [0.0, 0.0, -h / 2]),
        primitive_cuboid([t, t, h], [-w / 2, 0.0, 0.0]),
        primitive_cuboid([t, t, h], [w / 2, 0.0, 0.0]),
    ]


def build_curved(size: Tuple[float, float, float]) -> List[Dict[str, Any]]:
    return [primitive_curve(list(size))]


def build_bracket(size: Tuple[float, float, float]) -> List[Dict[str, Any]]:
    x, y, z = size
    return [
        primitive_cuboid([x, y, max(0.04, y)], [0.0, 0.0, 0.0]),
        primitive_cuboid([max(0.04, y), y, z], [-x / 2, 0.0, z / 2]),
    ]


def build_hinge(size: Tuple[float, float, float]) -> List[Dict[str, Any]]:
    x, y, z = size
    return [
        primitive_cuboid([x, y, z], [0.0, 0.0, 0.0]),
        primitive_cylinder([y, y, x], [0.0, 0.0, z / 2], [0.0, 90.0, 0.0]),
    ]


def build_wheel(size: Tuple[float, float, float]) -> List[Dict[str, Any]]:
    x, y, z = size
    return [primitive_cylinder([x, y, z], [0.0, 0.0, 0.0], [90.0, 0.0, 0.0])]


def build_cable(size: Tuple[float, float, float]) -> List[Dict[str, Any]]:
    return [primitive_curve(list(size))]


def build_electronics_box(size: Tuple[float, float, float]) -> List[Dict[str, Any]]:
    return [primitive_cuboid(list(size))]


def build_cylinder(size: Tuple[float, float, float]) -> List[Dict[str, Any]]:
    return [primitive_cylinder(list(size))]


def build_irregular(size: Tuple[float, float, float]) -> List[Dict[str, Any]]:
    return [primitive_cuboid(list(size))]


def build_primitives(shape_family: str, size: Tuple[float, float, float]) -> List[Dict[str, Any]]:
    stype = semantic_type(shape_family)

    if stype == "panel":
        return build_panel(size)
    if stype == "beam":
        return build_beam(size)
    if stype == "frame":
        return build_frame(size)
    if stype == "curved":
        return build_curved(size)
    if stype == "bracket":
        return build_bracket(size)
    if stype == "hinge":
        return build_hinge(size)
    if stype == "wheel":
        return build_wheel(size)
    if stype == "cable":
        return build_cable(size)
    if stype == "electronics_box":
        return build_electronics_box(size)
    if stype == "cylinder":
        return build_cylinder(size)

    return build_irregular(size)


def collect_motion_refs(part_uid: str, motion_plan: Dict[str, Any]) -> List[str]:
    refs = []

    for step in motion_plan.get("steps", []):
        moving = step.get("moving_objects", [])
        targets = step.get("target_objects", [])

        if part_uid in moving or part_uid in targets:
            refs.append(step.get("step_uid"))

    return refs


def build_geometry_object(
    part: Dict[str, Any],
    geometry_uid: str,
    motion_plan: Dict[str, Any],
) -> Dict[str, Any]:
    part_uid = part["part_uid"]
    shape_family = part.get("shape_family", "unknown")
    quantity = int(part.get("quantity_total", 1) or 1)

    size = default_dimensions(shape_family, quantity)
    primitives = build_primitives(shape_family, size)
    material = material_category(part.get("material_hint", "unknown"), shape_family)
    stype = semantic_type(shape_family)

    motion_refs = collect_motion_refs(part_uid, motion_plan)

    return {
        "geometry_uid": geometry_uid,
        "part_ref": part_uid,
        "semantic_geometry": {
            "type": stype,
            "role": "structural" if stype in {"frame", "beam", "panel", "curved"} else "connector",
            "is_composite": len(primitives) > 1,
            "symmetry": "bilateral" if stype in {"frame", "panel", "beam"} else "none",
            "estimated_scale": "medium"
        },
        "primitive_geometry": primitives,
        "material": {
            "category": material,
            "color_hint": "light" if material == "wood" else "neutral",
            "finish": "matte"
        },
        "origin": {
            "pivot": "center",
            "initial_position": [0.0, 0.0, 0.0]
        },
        "assembly_anchor": {
            "type": "center",
            "local_position": [0.0, 0.0, 0.0]
        },
        "bounding_box": {
            "width": size[0],
            "height": size[2],
            "depth": size[1]
        },
        "render_metadata": {
            "lod": "medium",
            "subdivision": 0,
            "bevel": True,
            "motion_refs": motion_refs,
            "source_pages": [
                obs.get("page_number")
                for obs in part.get("observations", [])
                if obs.get("page_number") is not None
            ]
        }
    }


def validate_geometry_spec(spec: Dict[str, Any], graph: Dict[str, Any], motion_plan: Dict[str, Any]) -> List[str]:
    warnings = []

    parts = graph.get("parts", [])
    objects = spec.get("objects", [])
    geometry_map = spec.get("geometry_to_object_map", {})

    part_ids = {p.get("part_uid") for p in parts if p.get("part_uid")}
    geometry_ids = [o.get("geometry_uid") for o in objects]

    if len(geometry_ids) != len(set(geometry_ids)):
        warnings.append("Duplicate geometry_uid detected.")

    for part_id in part_ids:
        if part_id not in geometry_map:
            warnings.append(f"Missing geometry mapping for part {part_id}.")

    mapped_geometry = set(geometry_map.values())

    for obj in objects:
        gid = obj.get("geometry_uid")
        part_ref = obj.get("part_ref")

        if gid not in mapped_geometry:
            warnings.append(f"Orphan geometry object not in map: {gid}")

        if part_ref not in part_ids:
            warnings.append(f"Geometry object references unknown part: {part_ref}")

        if not obj.get("semantic_geometry"):
            warnings.append(f"Geometry object missing semantic_geometry: {gid}")

        if not obj.get("primitive_geometry"):
            warnings.append(f"Geometry object has no primitives: {gid}")

    for step in motion_plan.get("steps", []):
        for obj_ref in step.get("moving_objects", []) + step.get("target_objects", []):
            if obj_ref.startswith("OBJ") and obj_ref not in geometry_map:
                warnings.append(f"Motion step {step.get('step_uid')} references object without geometry: {obj_ref}")

    return warnings


def build_geometry_spec(
    graph_path: Path = GRAPH_PATH,
    motion_plan_path: Path = MOTION_PLAN_PATH,
    output_path: Path = OUTPUT_PATH,
) -> Dict[str, Any]:
    graph = load_json(graph_path)
    motion_plan = load_json(motion_plan_path)

    parts = graph.get("parts", [])

    objects = []
    geometry_to_object_map = {}

    for index, part in enumerate(parts, start=1):
        if not part.get("part_uid"):
            continue

        geometry_uid = new_geometry_uid(index)
        geometry_to_object_map[part["part_uid"]] = geometry_uid

        objects.append(
            build_geometry_object(
                part=part,
                geometry_uid=geometry_uid,
                motion_plan=motion_plan,
            )
        )

    spec = {
        "schema_version": "2.0",
        "units": "meters",
        "objects": objects,
        "geometry_to_object_map": geometry_to_object_map,
        "warnings": []
    }

    spec["warnings"] = validate_geometry_spec(spec, graph, motion_plan)

    save_json(spec, output_path)

    print(f"Saved geometry spec to {output_path}")
    print(f"Geometry objects: {len(objects)}")
    print(f"Geometry mappings: {len(geometry_to_object_map)}")
    print(f"Warnings: {len(spec['warnings'])}")

    if spec["warnings"]:
        for warning in spec["warnings"]:
            print(f"WARNING: {warning}")

    return spec


if __name__ == "__main__":
    build_geometry_spec()