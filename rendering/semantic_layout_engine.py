import json
from pathlib import Path


def safe_float(value, default):
    try:
        return float(value)
    except Exception:
        return default


def normalize(text):
    return str(text or "").lower().strip()


def get_dims(node):
    dims = node.get("dimensions", {}) or {}

    length = safe_float(dims.get("length"), 1.0)
    width = safe_float(dims.get("width"), 0.25)
    height = safe_float(dims.get("height"), 0.25)

    role = normalize(node.get("semantic_role"))
    geometry = normalize(node.get("geometry_type"))

    if geometry == "thin_panel" or "panel" in role or "shelf" in role or "door" in role:
        return max(length, 1.4), max(width, 0.12), max(height, 0.08)

    if geometry in ["long_beam", "tube"] or "rail" in role or "beam" in role or "rod" in role:
        return max(length, 1.4), max(width, 0.12), max(height, 0.12)

    if "leg" in role:
        return 0.18, 0.18, max(height, 1.5)

    if "fastener" in role or "screw" in role or "bolt" in role:
        return 0.08, 0.08, 0.45

    if "wheel" in role:
        return 0.35, 0.35, 0.12

    if "hinge" in role or "bracket" in role:
        return 0.35, 0.08, 0.35

    if "electronics" in role or "motor" in role or "board" in role:
        return 0.7, 0.45, 0.12

    return max(length, 0.5), max(width, 0.25), max(height, 0.25)


def shape_for_node(node):
    role = normalize(node.get("semantic_role"))
    geometry = normalize(node.get("geometry_type"))

    if geometry in ["cylinder", "tube", "screw", "bolt", "nut", "washer"] or any(k in role for k in ["screw", "bolt", "nut", "washer", "fastener", "rod", "tube"]):
        return "cylinder"

    if geometry in ["wheel"]:
        return "wheel"

    if geometry in ["bracket"]:
        return "bracket"

    if geometry in ["hinge"]:
        return "hinge"

    if geometry in ["curved_part"]:
        return "curved"

    return "cuboid"


def material_for_node(node):
    material = normalize(node.get("material"))

    if material:
        return material

    role = normalize(node.get("semantic_role"))

    if any(k in role for k in ["screw", "bolt", "nut", "washer", "fastener", "hinge", "bracket", "tube", "rod"]):
        return "metal"

    if any(k in role for k in ["cable", "cover", "electronics", "motor", "board"]):
        return "plastic"

    if "cushion" in role or "fabric" in role:
        return "fabric"

    return "wood"


def default_position_for_role(role, index):
    role = normalize(role)

    # Chair/table/bench style
    if "leg" in role:
        positions = [(-1.1, -0.8, 0.75), (1.1, -0.8, 0.75), (-1.1, 0.8, 0.75), (1.1, 0.8, 0.75)]
        return positions[index % len(positions)]

    if "seat" in role or "top_panel" in role or "surface" in role:
        return (0, 0, 1.55)

    if "back" in role:
        return (0, 1.05, 2.5)

    if "rail" in role or "beam" in role:
        return (0, 0, 1.15 + 0.18 * index)

    # Cabinet/wardrobe/shelf style
    if "side_panel" in role:
        return (-1.2 if index % 2 == 0 else 1.2, 0, 1.5)

    if "bottom_panel" in role:
        return (0, 0, 0.25)

    if "top_panel" in role:
        return (0, 0, 3.0)

    if "shelf" in role:
        return (0, 0, 0.9 + 0.45 * index)

    if "door" in role:
        return (-0.65 if index % 2 == 0 else 0.65, -0.9, 1.6)

    if "drawer" in role:
        return (0, -0.95, 0.7 + 0.35 * index)

    if "wheel" in role:
        positions = [(-0.8, -0.6, 0.25), (0.8, -0.6, 0.25), (-0.8, 0.6, 0.25), (0.8, 0.6, 0.25)]
        return positions[index % len(positions)]

    if "fastener" in role or "screw" in role or "bolt" in role:
        grid = [(-1.0, -0.7), (1.0, -0.7), (-1.0, 0.7), (1.0, 0.7), (0, -0.7), (0, 0.7)]
        x, y = grid[index % len(grid)]
        return (x, y, 2.4)

    return (0, 0, 1.0 + 0.25 * index)


def start_position_for_motion(end, motion, index):
    motion = normalize(motion)
    x, y, z = end

    if "lower" in motion:
        return (x, y, z + 3.0)

    if "rise" in motion:
        return (x, y, z - 2.0)

    if "slide" in motion or "insert" in motion:
        direction = -1 if index % 2 == 0 else 1
        return (x + 3.2 * direction, y, z)

    if "rotate" in motion:
        return (x, y, z + 1.6)

    if "place" in motion:
        return (x - 2.5, y - 1.5, z + 1.2)

    return (x - 3.0, y, z + 1.0)


def scene_for_node(node, graph, manual_plan):
    node_id = node.get("node_id")

    related_steps = []

    for edge in graph.get("edges", []):
        if edge.get("from") == node_id or edge.get("to") == node_id:
            if edge.get("step"):
                related_steps.append(int(edge["step"]))

    if related_steps:
        return min(related_steps)

    if manual_plan:
        text = normalize(f"{node.get('name')} {node.get('semantic_role')} {node.get('manual_label')}")
        for scene in manual_plan.get("scenes", []):
            combined = normalize(
                f"{scene.get('title')} "
                f"{scene.get('action')} "
                f"{scene.get('motion')} "
                f"{' '.join(scene.get('active_parts', []))} "
                f"{' '.join(scene.get('active_fasteners', []))}"
            )

            for token in text.split():
                if len(token) > 3 and token in combined:
                    return int(scene.get("scene_number", 1))

    return 1


def build_semantic_scene(
    graph_path="outputs/json/assembly_graph.json",
    product_model_path="outputs/json/product_model.json",
    output_path="outputs/json/scene_graph_layout.json",
    manual_scene_plan_path="outputs/json/manual_scene_plan.json"
):
    graph = json.loads(Path(graph_path).read_text(encoding="utf-8"))
    product = json.loads(Path(product_model_path).read_text(encoding="utf-8"))

    manual_plan = None
    if Path(manual_scene_plan_path).exists():
        manual_plan = json.loads(Path(manual_scene_plan_path).read_text(encoding="utf-8"))

    role_counts = {}
    objects = []

    for node in graph.get("nodes", []):
        role = node.get("semantic_role", "unknown_part")
        index = role_counts.get(role, 0)
        role_counts[role] = index + 1

        dims = get_dims(node)
        shape = shape_for_node(node)
        material = material_for_node(node)

        motion = node.get("assembly_motion", "move_to_position")

        for edge in graph.get("edges", []):
            if edge.get("from") == node.get("node_id"):
                motion = edge.get("motion", motion)
                break

        end = default_position_for_role(role, index)
        start = start_position_for_motion(end, motion, index)
        scene_number = scene_for_node(node, graph, manual_plan)

        rotation_degrees = 0
        if shape == "cylinder":
            rotation_degrees = 2880 if node.get("type") == "fastener" else 0
        if "rotate" in normalize(motion):
            rotation_degrees = max(rotation_degrees, 720)

        objects.append({
            "object_id": node.get("node_id"),
            "name": node.get("name", node.get("node_id")),
            "manual_label": node.get("manual_label", ""),
            "role": role,
            "shape": shape,
            "geometry_type": node.get("geometry_type", shape),
            "dimensions": {
                "length": dims[0],
                "width": dims[1],
                "height": dims[2],
                "unit": "generic"
            },
            "start_position": {
                "x": start[0],
                "y": start[1],
                "z": start[2]
            },
            "end_position": {
                "x": end[0],
                "y": end[1],
                "z": end[2]
            },
            "rotation": {
                "axis": "z",
                "degrees": rotation_degrees
            },
            "material": material,
            "scene_number": scene_number,
            "motion": motion
        })

    scene_count = len(manual_plan.get("scenes", [])) if manual_plan else max(1, len(graph.get("edges", [])))

    narration = product.get("summary", "")
    if manual_plan:
        narration = " ".join(
            s.get("narration", "")
            for s in manual_plan.get("scenes", [])
            if s.get("narration")
        )

    scene = {
        "scene_number": 1,
        "title": f"{graph.get('product_name', product.get('product_name', 'DIY Product'))} Assembly",
        "manual_category": graph.get("product_type", product.get("product_type", "generic_diy")),
        "duration_seconds": max(12, scene_count * 4),
        "objects": objects,
        "edges": graph.get("edges", []),
        "camera": {
            "angle": "isometric",
            "zoom": 1.2,
            "focus_object": "product_center"
        },
        "narration": narration,
        "manual_scene_plan": manual_plan,
        "warnings": []
    }

    if len(graph.get("edges", [])) == 0:
        scene["warnings"].append("Assembly graph has no edges. Animation may still appear generic.")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(scene, indent=2), encoding="utf-8")

    print(f"Semantic scene graph saved to {output_path}")
    print(f"Objects generated: {len(objects)}")
    print(f"Roles used: {role_counts}")
    print(f"Edges used: {len(graph.get('edges', []))}")

    return scene


if __name__ == "__main__":
    build_semantic_scene()