import json
from pathlib import Path
from typing import Any, Dict, List, Optional


GRAPH_PATH = Path("v2/outputs/json/universal_assembly_graph.json")
OUTPUT_PATH = Path("v2/outputs/json/motion_plan.json")


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def norm(value: Any) -> str:
    return str(value or "").strip().lower()


def node_name(node_ref: str, node_lookup: Dict[str, Dict[str, Any]]) -> str:
    node = node_lookup.get(node_ref, {})

    if node_ref.startswith("ASM"):
        return node.get("canonical_name", node_ref)

    return node.get("canonical_name", node_ref)


def build_node_lookup(graph: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    lookup: Dict[str, Dict[str, Any]] = {}

    for part in graph.get("parts", []):
        uid = part.get("part_uid")
        if uid:
            item = dict(part)
            item["node_uid"] = uid
            item["node_type"] = "part"
            lookup[uid] = item

    for assembly in graph.get("assemblies", []):
        uid = assembly.get("assembly_uid")
        if uid:
            item = dict(assembly)
            item["node_uid"] = uid
            item["node_type"] = "assembly"
            lookup[uid] = item
            
    for fastener in graph.get("fasteners", []):
        uid = fastener.get("fastener_uid")
        if uid:
            item = dict(fastener)
            item["node_uid"] = uid
            item["node_type"] = "fastener"
            item["canonical_name"] = fastener.get("name", uid)
            lookup[uid] = item

    return lookup


def motion_style_for_connection(connection_type: str) -> str:
    c = norm(connection_type)

    if c in {"inserted", "slotted"}:
        return "slide"

    if c in {"screwed", "bolted"}:
        return "rotate"

    if c in {"placed_on", "attached", "aligned"}:
        return "lower"

    if c == "hinged":
        return "arc"

    return "linear"


def action_type_for_connection(connection_type: str) -> str:
    c = norm(connection_type)

    if c in {"screwed", "bolted"}:
        return "insert_and_rotate"

    if c in {"inserted", "slotted"}:
        return "insert"

    if c == "placed_on":
        return "place"

    if c == "attached":
        return "attach"

    if c == "hinged":
        return "rotate_into_place"

    return "move_to_connect"


def duration_for_motion(motion_style: str) -> int:
    durations = {
        "rotate": 72,
        "slide": 60,
        "lower": 60,
        "arc": 72,
        "linear": 48,
    }

    return durations.get(motion_style, 48)


def camera_for_motion(motion_style: str, connection_type: str) -> str:
    c = norm(connection_type)

    if motion_style == "rotate" or c in {"screwed", "bolted"}:
        return "close_up"

    if motion_style == "slide":
        return "side"

    if motion_style == "arc":
        return "side"

    return "isometric"


def make_title(
    connection: Dict[str, Any],
    node_lookup: Dict[str, Dict[str, Any]]
) -> str:
    from_name = node_name(connection.get("from_node_ref", ""), node_lookup)
    to_name = node_name(connection.get("to_node_ref", ""), node_lookup)

    ctype = connection.get("connection_type", "connect")
    ctype = ctype.replace("_", " ").title()

    return f"{ctype}: {from_name} to {to_name}"


def make_narration(
    connection: Dict[str, Any],
    node_lookup: Dict[str, Dict[str, Any]]
) -> str:
    from_name = node_name(connection.get("from_node_ref", ""), node_lookup)
    to_name = node_name(connection.get("to_node_ref", ""), node_lookup)

    ctype = norm(connection.get("connection_type"))

    if ctype in {"screwed", "bolted"}:
        return f"Insert and tighten {from_name} into {to_name}."

    if ctype in {"inserted", "slotted"}:
        return f"Slide {from_name} into {to_name}."

    if ctype == "placed_on":
        return f"Place {from_name} onto {to_name}."

    if ctype == "attached":
        return f"Attach {from_name} to {to_name}."

    if ctype == "hinged":
        return f"Rotate {from_name} into position on {to_name}."

    return f"Move {from_name} into position with {to_name}."


def validate_connection(
    connection: Dict[str, Any],
    node_lookup: Dict[str, Dict[str, Any]]
) -> List[str]:
    warnings: List[str] = []

    conn_id = connection.get("connection_uid", "unknown_connection")
    from_ref = connection.get("from_node_ref", "")
    to_ref = connection.get("to_node_ref", "")

    if not from_ref:
        warnings.append(f"{conn_id}: missing from_node_ref")

    if not to_ref:
        warnings.append(f"{conn_id}: missing to_node_ref")

    if from_ref and from_ref not in node_lookup:
        warnings.append(f"{conn_id}: from_node_ref does not exist: {from_ref}")

    if to_ref and to_ref not in node_lookup:
        warnings.append(f"{conn_id}: to_node_ref does not exist: {to_ref}")

    if from_ref and to_ref and from_ref == to_ref:
        warnings.append(f"{conn_id}: invalid self-connection {from_ref} -> {to_ref}")

    return warnings

def build_motion_plan(
    graph_path: Path = GRAPH_PATH,
    output_path: Path = OUTPUT_PATH,
) -> Dict[str, Any]:

    graph = load_json(graph_path)

    node_lookup = build_node_lookup(graph)

    connections = graph.get("connections", [])
    assembly_order = graph.get("assembly_order", [])

    connection_lookup = {
        c["connection_uid"]: c
        for c in connections
        if c.get("connection_uid")
    }

    ordered_connections: List[Dict[str, Any]] = []

    for conn_id in assembly_order:
        if conn_id in connection_lookup:
            ordered_connections.append(connection_lookup[conn_id])

    for conn in connections:
        if conn not in ordered_connections:
            ordered_connections.append(conn)

    steps: List[Dict[str, Any]] = []
    warnings: List[str] = []

    current_frame = 1
    gap = 12
    step_number = 1

    for connection in ordered_connections:

        validation = validate_connection(connection, node_lookup)

        if validation:
            warnings.extend(validation)

            if any("invalid self-connection" in x for x in validation):
                print(f"Skipping self connection {connection['connection_uid']}")
                continue

            if any("does not exist" in x for x in validation):
                print(f"Skipping invalid connection {connection['connection_uid']}")
                continue

        motion_style = motion_style_for_connection(
            connection.get("connection_type", "")
        )

        action_type = action_type_for_connection(
            connection.get("connection_type", "")
        )

        duration = duration_for_motion(motion_style)

        moving_nodes = []

        target_nodes = []

        if connection.get("from_node_ref"):
            moving_nodes.append(connection["from_node_ref"])

        if connection.get("to_node_ref"):
            target_nodes.append(connection["to_node_ref"])

        for fastener in connection.get("fasteners", []):

            if fastener:
                moving_nodes.append(fastener)

        start_frame = current_frame
        end_frame = start_frame + duration

        step = {

            "step_uid": f"M{step_number:04d}",

            "source_page": connection.get("created_on_page"),

            "title": make_title(connection, node_lookup),

            "action_type": action_type,

            "moving_nodes": moving_nodes,

            "target_nodes": target_nodes,

            "connection_refs": [
                connection.get("connection_uid")
            ],

            "start_pose": {
                "position": "exploded",
                "orientation": "default"
            },

            "end_pose": {
                "position": "assembled",
                "orientation": "aligned"
            },

            "motion_style": motion_style,

            "camera": camera_for_motion(
                motion_style,
                connection.get("connection_type", "")
            ),

            "start_frame": start_frame,

            "end_frame": end_frame,

            "duration_frames": duration,

            "narration": make_narration(
                connection,
                node_lookup
            ),

            "visual_evidence": connection.get(
                "visual_evidence",
                ""
            )
        }

        steps.append(step)

        step_number += 1

        current_frame = end_frame + gap

    motion_plan = {

        "schema_version": "2.1",

        "fps": 24,

        "total_frames": max(current_frame, 1),

        "steps": steps,

        "warnings": warnings

    }

    save_json(motion_plan, output_path)

    print()
    print("Motion Planner Summary")
    print("----------------------")
    print(f"Nodes: {len(node_lookup)}")
    print(f"Connections: {len(connections)}")
    print(f"Motion Steps: {len(steps)}")
    print(f"Warnings: {len(warnings)}")
    print(f"Frames: {motion_plan['total_frames']}")
    print()

    return motion_plan


if __name__ == "__main__":
    build_motion_plan()