import json
import sys
from pathlib import Path
from typing import Any, Dict, List


GRAPH_PATH = Path("v2/outputs/json/universal_assembly_graph.json")
OUTPUT_PATH = Path("v2/outputs/json/motion_plan.json")


# ---------------------------------------------------------------------
# MVP SPEED CONTROL
# ---------------------------------------------------------------------
# FAST_MVP_MODE = True gives quicker preview renders for development/GitHub demo.
# Set to False later if you want slower, smoother animations.
FAST_MVP_MODE = True

if FAST_MVP_MODE:
    FRAME_GAP = 6
    MOTION_DURATIONS = {
        "rotate": 36,
        "slide": 30,
        "lower": 30,
        "arc": 36,
        "linear": 24,
    }
else:
    FRAME_GAP = 12
    MOTION_DURATIONS = {
        "rotate": 72,
        "slide": 60,
        "lower": 60,
        "arc": 72,
        "linear": 48,
    }


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

    return node.get("canonical_name", node.get("name", node_ref))


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

    for tool in graph.get("tools", []):
        uid = tool.get("tool_uid")
        if uid:
            item = dict(tool)
            item["node_uid"] = uid
            item["node_type"] = "tool"
            item["canonical_name"] = tool.get("name", uid)
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
    return MOTION_DURATIONS.get(motion_style, MOTION_DURATIONS["linear"])


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
    node_lookup: Dict[str, Dict[str, Any]],
) -> str:
    from_name = node_name(connection.get("from_node_ref", ""), node_lookup)
    to_name = node_name(connection.get("to_node_ref", ""), node_lookup)

    ctype = connection.get("connection_type", "connect")
    ctype = ctype.replace("_", " ").title()

    return f"{ctype}: {from_name} to {to_name}"


def make_narration(
    connection: Dict[str, Any],
    node_lookup: Dict[str, Dict[str, Any]],
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
    node_lookup: Dict[str, Dict[str, Any]],
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


def ordered_connections_from_graph(graph: Dict[str, Any]) -> List[Dict[str, Any]]:
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

    return ordered_connections


def moving_and_target_nodes(connection: Dict[str, Any]) -> tuple[List[str], List[str]]:
    moving_nodes: List[str] = []
    target_nodes: List[str] = []

    from_ref = connection.get("from_node_ref", "")
    to_ref = connection.get("to_node_ref", "")

    if from_ref:
        moving_nodes.append(from_ref)

    if to_ref:
        target_nodes.append(to_ref)

    for fastener in connection.get("fasteners", []):
        if fastener and fastener not in moving_nodes:
            moving_nodes.append(fastener)

    return moving_nodes, target_nodes


def build_motion_step(
    step_number: int,
    connection: Dict[str, Any],
    node_lookup: Dict[str, Dict[str, Any]],
    start_frame: int,
) -> Dict[str, Any]:
    motion_style = motion_style_for_connection(
        connection.get("connection_type", "")
    )

    action_type = action_type_for_connection(
        connection.get("connection_type", "")
    )

    duration = duration_for_motion(motion_style)

    moving_nodes, target_nodes = moving_and_target_nodes(connection)

    end_frame = start_frame + duration

    return {
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


def build_motion_plan(
    graph_path: Path = GRAPH_PATH,
    output_path: Path = OUTPUT_PATH,
) -> Dict[str, Any]:

    graph = load_json(graph_path)

    node_lookup = build_node_lookup(graph)
    connections = graph.get("connections", [])
    ordered_connections = ordered_connections_from_graph(graph)

    steps: List[Dict[str, Any]] = []
    warnings: List[str] = []
    # node -> the step that moves it into place. blender_builder_v3.py
    # keyframes every step's moving nodes from start_position to
    # final_position, so a node moving in two steps would jump back to its
    # exploded position. Each node therefore moves once; later connections
    # that move nothing new are folded into the step that placed the node.
    placed_by: Dict[str, Dict[str, Any]] = {}
    merged_count = 0

    current_frame = 1
    step_number = 1

    for connection in ordered_connections:
        validation = validate_connection(connection, node_lookup)

        if validation:
            warnings.extend(validation)

            if any("invalid self-connection" in x for x in validation):
                print(f"Skipping self connection {connection.get('connection_uid', '')}")
                continue

            if any("does not exist" in x for x in validation):
                print(f"Skipping invalid connection {connection.get('connection_uid', '')}")
                continue

        moving_nodes, _ = moving_and_target_nodes(connection)
        new_movers = [uid for uid in moving_nodes if uid not in placed_by]

        if not moving_nodes:
            continue

        if not new_movers:
            owner = placed_by[moving_nodes[0]]
            owner["connection_refs"].append(connection.get("connection_uid"))
            merged_count += 1
            continue

        step = build_motion_step(
            step_number=step_number,
            connection=connection,
            node_lookup=node_lookup,
            start_frame=current_frame,
        )
        step["moving_nodes"] = new_movers

        for uid in new_movers:
            placed_by[uid] = step

        steps.append(step)

        step_number += 1
        current_frame = step["end_frame"] + FRAME_GAP

    motion_plan = {
        "schema_version": "2.2",
        "fps": 24,
        "fast_mvp_mode": FAST_MVP_MODE,
        "frame_gap": FRAME_GAP,
        "duration_profile": MOTION_DURATIONS,
        "total_frames": max(current_frame, 1),
        "steps": steps,
        "warnings": warnings,
    }

    save_json(motion_plan, output_path)

    print()
    print("Motion Planner Summary")
    print("----------------------")
    print(f"Fast MVP Mode: {FAST_MVP_MODE}")
    print(f"Frame gap: {FRAME_GAP}")
    print(f"Nodes: {len(node_lookup)}")
    print(f"Connections: {len(connections)}")
    print(f"Motion Steps: {len(steps)}")
    print(f"Connections folded into earlier steps: {merged_count}")
    print(f"Warnings: {len(warnings)}")
    print(f"Frames: {motion_plan['total_frames']}")
    print()

    return motion_plan


if __name__ == "__main__":
    result = build_motion_plan()

    if not result["steps"]:
        sys.exit(
            "ERROR: the motion plan has no steps, so the video would be a single still "
            "frame. See the warnings above and universal_assembly_graph.json."
        )
