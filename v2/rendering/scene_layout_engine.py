import json
from pathlib import Path
from typing import Any, Dict, List


GRAPH_PATH = Path("v2/outputs/json/universal_assembly_graph.json")
MOTION_PATH = Path("v2/outputs/json/motion_plan.json")
GEOMETRY_PATH = Path("v2/outputs/json/geometry_spec.json")
OUTPUT_PATH = Path("v2/outputs/json/scene_layout.json")


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def build_node_lookup(graph: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    nodes = {}

    for part in graph.get("parts", []):
        uid = part.get("part_uid")
        if uid:
            item = dict(part)
            item["node_uid"] = uid
            item["node_type"] = "part"
            nodes[uid] = item

    for asm in graph.get("assemblies", []):
        uid = asm.get("assembly_uid")
        if uid:
            item = dict(asm)
            item["node_uid"] = uid
            item["node_type"] = "assembly"
            nodes[uid] = item

    for fastener in graph.get("fasteners", []):
        uid = fastener.get("fastener_uid")
        if uid:
            item = dict(fastener)
            item["node_uid"] = uid
            item["node_type"] = "fastener"
            item["canonical_name"] = fastener.get("name", uid)
            nodes[uid] = item

    return nodes


def geometry_lookup(geometry: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        obj["part_ref"]: obj
        for obj in geometry.get("objects", [])
        if obj.get("part_ref")
    }


def final_position(index: int, node_type: str) -> List[float]:
    if node_type == "assembly":
        return [0.0, 0.0, 1.2]

    row = index // 4
    col = index % 4

    return [
        (col - 1.5) * 1.35,
        row * 0.85,
        1.0
    ]


def exploded_position(index: int, final: List[float], node_type: str) -> List[float]:
    if node_type == "assembly":
        return final

    directions = [
        [-1, -1, 1],
        [1, -1, 1],
        [-1, 1, 1],
        [1, 1, 1],
        [0, -1, 1],
        [0, 1, 1],
        [-1, 0, 1],
        [1, 0, 1],
    ]

    direction = directions[index % len(directions)]
    layer = index // len(directions)

    spread = 3.4 + layer * 0.8
    height = 1.4 + layer * 0.35

    if node_type == "fastener":
        spread *= 0.55
        height *= 0.65

    return [
        final[0] + direction[0] * spread,
        final[1] + direction[1] * spread,
        final[2] + direction[2] * height
    ]


def moving_nodes_from_motion(motion: Dict[str, Any]) -> set:
    moving = set()

    for step in motion.get("steps", []):
        for uid in step.get("moving_nodes", []):
            moving.add(uid)

    return moving


def target_nodes_from_motion(motion: Dict[str, Any]) -> set:
    targets = set()

    for step in motion.get("steps", []):
        for uid in step.get("target_nodes", []):
            targets.add(uid)

    return targets


def node_is_moving(node_uid: str, motion: Dict[str, Any]) -> bool:
    return node_uid in moving_nodes_from_motion(motion)


def first_motion_step(node_uid: str, motion: Dict[str, Any]) -> str:
    for step in motion.get("steps", []):
        if node_uid in step.get("moving_nodes", []) or node_uid in step.get("target_nodes", []):
            return step.get("step_uid", "")
    return ""


def build_scene_layout(
    graph_path: Path = GRAPH_PATH,
    motion_path: Path = MOTION_PATH,
    geometry_path: Path = GEOMETRY_PATH,
    output_path: Path = OUTPUT_PATH,
) -> Dict[str, Any]:
    graph = load_json(graph_path)
    motion = load_json(motion_path)
    geometry = load_json(geometry_path)

    nodes = build_node_lookup(graph)
    geom_by_part = geometry_lookup(geometry)

    moving_nodes = moving_nodes_from_motion(motion)
    target_nodes = target_nodes_from_motion(motion)

    scene_objects = []
    warnings = []

    sorted_nodes = sorted(nodes.values(), key=lambda n: n["node_uid"])

    for index, node in enumerate(sorted_nodes):
        uid = node["node_uid"]
        node_type = node["node_type"]

        geom = geom_by_part.get(uid)
        geometry_uid = geom.get("geometry_uid") if geom else ""

        final = final_position(index, node_type)

        is_moving = uid in moving_nodes

        if is_moving:
            start = exploded_position(index, final, node_type)
        else:
            start = final

        parent = ""
        for asm in graph.get("assemblies", []):
            if uid in asm.get("members", []):
                parent = asm.get("assembly_uid", "")
                break

        scene_objects.append({
            "node_uid": uid,
            "node_type": node_type,
            "name": node.get("canonical_name") or node.get("name") or uid,
            "geometry_uid": geometry_uid,
            "start_position": start,
            "final_position": final,
            "exploded_position": exploded_position(index, final, node_type),
            "rotation": [0.0, 0.0, 0.0],
            "scale": [1.0, 1.0, 1.0],
            "parent": parent,
            "is_moving": is_moving,
            "is_target": uid in target_nodes,
            "first_motion_step": first_motion_step(uid, motion),
            "visible": True
        })

        if node_type == "part" and not geometry_uid:
            warnings.append(f"No geometry found for part node {uid}")

    layout = {
        "schema_version": "2.1",
        "scene_objects": scene_objects,
        "camera": {
            "position": [6.0, -8.0, 5.0],
            "target": [0.0, 0.0, 1.0],
            "lens": 35
        },
        "render": {
            "resolution_x": 1280,
            "resolution_y": 720,
            "fps": motion.get("fps", 24),
            "total_frames": motion.get("total_frames", 1)
        },
        "debug": {
            "moving_nodes": sorted(list(moving_nodes)),
            "target_nodes": sorted(list(target_nodes))
        },
        "warnings": warnings
    }

    save_json(layout, output_path)

    print(f"Saved scene layout to {output_path}")
    print(f"Scene objects: {len(scene_objects)}")
    print(f"Moving objects: {sum(1 for o in scene_objects if o['is_moving'])}")
    print(f"Target objects: {sum(1 for o in scene_objects if o.get('is_target'))}")
    print(f"Warnings: {len(warnings)}")

    return layout


if __name__ == "__main__":
    build_scene_layout()