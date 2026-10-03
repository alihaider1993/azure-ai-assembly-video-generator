import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Dict, List


GRAPH_PATH = Path("v2/outputs/json/universal_assembly_graph.json")
PAGE_STATES_PATH = Path("v2/outputs/json/page_states.json")
ACTIONS_PATH = Path("v2/outputs/json/assembly_actions.json")
IDENTITY_MAP_PATH = Path("v2/outputs/json/object_identity_map.json")

OUTPUT_PATH = Path("v2/outputs/json/resolved_assembly_actions.json")


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def norm(value: Any) -> str:
    return str(value or "").strip().lower()


def build_fastener_lookup(graph: Dict[str, Any], page_states: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    Converts local fastener IDs like F004_003 into canonical IDs like FAST0003.
    Uses the same key as universal_graph_engine.py: the printed label, or
    the normalised name for an unlabelled fastener.
    """
    key_to_fastener = {}

    for fastener in graph.get("fasteners", []):
        uid = fastener.get("fastener_uid")
        if not uid:
            continue

        for label in fastener.get("manual_labels", []):
            label = str(label).strip()
            if label:
                key_to_fastener[label] = uid

        if not fastener.get("manual_labels"):
            key_to_fastener[norm(fastener.get("name"))] = uid

    local_to_fastener = {}

    for page in page_states:
        for fastener in page.get("visible_fasteners", []):
            local_uid = fastener.get("fastener_uid")
            key = str(fastener.get("manual_label", "")).strip() or norm(fastener.get("name"))

            if local_uid and key in key_to_fastener:
                local_to_fastener[local_uid] = key_to_fastener[key]

    return local_to_fastener


def build_tool_lookup(graph: Dict[str, Any], page_states: List[Dict[str, Any]]) -> Dict[str, str]:
    """Local tool IDs like T004_001 -> canonical TOOL0001, matched by name."""
    name_to_tool = {
        norm(tool.get("name")): tool.get("tool_uid")
        for tool in graph.get("tools", [])
        if tool.get("tool_uid")
    }

    return {
        tool.get("tool_uid"): name_to_tool[norm(tool.get("name"))]
        for page in page_states
        for tool in page.get("visible_tools", [])
        if tool.get("tool_uid") and norm(tool.get("name")) in name_to_tool
    }


def choose_anchor_part(actions: List[Dict[str, Any]], resolve: Callable[[str], str]) -> str:
    """The part everything else is built onto: the most frequent target
    that never moves itself (e.g. the tabletop). Used in place of the
    abstract assembly node, which has no geometry of its own."""
    targets: Counter = Counter()
    movers = set()

    for action in actions:
        moving = resolve(action.get("moving_ref", ""))
        target = resolve(action.get("target_ref", ""))
        if moving.startswith("OBJ"):
            movers.add(moving)
        if target.startswith("OBJ"):
            targets[target] += 1

    for uid, _ in targets.most_common():
        if uid not in movers:
            return uid

    return targets.most_common(1)[0][0] if targets else ""


def resolve_ref(
    ref: str,
    local_part_lookup: Dict[str, str],
    local_fastener_lookup: Dict[str, str],
) -> str:
    if not ref:
        return ""

    if ref in local_part_lookup:
        return local_part_lookup[ref]

    if ref in local_fastener_lookup:
        return local_fastener_lookup[ref]

    if ref.startswith(("OBJ", "FAST", "ASM", "TOOL")):
        return ref

    # A local page ID (e.g. P004_002) the identity map could not place.
    # Passing it through only creates a connection to a node that doesn't
    # exist, which motion_planner.py then drops.
    return ""


def infer_moving_from_fastener(action: Dict[str, Any], moving: str, fastener: str) -> str:
    """
    If the action has no moving part but has a fastener, treat the fastener
    as the moving object.
    """
    if not moving and fastener:
        return fastener
    return moving


def should_skip_self_action(action_uid: str, moving: str, target: str, warnings: List[str]) -> bool:
    if moving and target and moving == target:
        warnings.append(f"{action_uid}: skipped self-action {moving} -> {target}")
        return True
    return False


def resolve_actions(
    graph: Dict[str, Any],
    page_states: List[Dict[str, Any]],
    actions_json: Dict[str, Any],
    identity_map: Dict[str, Any],
) -> Dict[str, Any]:

    local_part_lookup = identity_map.get("local_to_canonical", {})
    local_fastener_lookup = build_fastener_lookup(graph, page_states)
    local_tool_lookup = build_tool_lookup(graph, page_states)

    def resolve(ref: str) -> str:
        return resolve_ref(ref, local_part_lookup, local_fastener_lookup)

    actions = actions_json.get("actions", [])
    anchor_part = choose_anchor_part(actions, resolve)

    def resolve_node(ref: str) -> str:
        uid = resolve(ref)
        if uid.startswith("ASM") and anchor_part:
            return anchor_part
        return uid

    resolved_actions = []
    warnings = []

    for action in actions:
        action_uid = action.get("action_uid", "")

        moving = resolve_node(action.get("moving_ref", ""))
        target = resolve_node(action.get("target_ref", ""))
        fastener = resolve(action.get("fastener_ref", ""))

        moving = infer_moving_from_fastener(action, moving, fastener)

        if should_skip_self_action(action_uid, moving, target, warnings):
            continue

        if not moving or not target:
            warnings.append(
                f"{action_uid}: missing moving or target after identity resolution "
                f"(moving={moving}, target={target})"
            )
            continue

        new_action = dict(action)

        new_action["original_moving_ref"] = action.get("moving_ref", "")
        new_action["original_target_ref"] = action.get("target_ref", "")
        new_action["original_fastener_ref"] = action.get("fastener_ref", "")

        new_action["moving_ref"] = moving
        new_action["target_ref"] = target
        new_action["fastener_ref"] = fastener
        new_action["tool_ref"] = local_tool_lookup.get(action.get("tool_ref", ""), action.get("tool_ref", ""))

        new_action["resolved"] = True
        new_action["resolution_source"] = "object_identity_map"

        new_action["warnings"] = action.get("warnings", [])

        resolved_actions.append(new_action)

    return {
        "schema_version": "2.4",
        "actions": resolved_actions,
        "warnings": warnings,
        "debug": {
            "identity_map_path": str(IDENTITY_MAP_PATH),
            "local_part_lookup": local_part_lookup,
            "local_fastener_lookup": local_fastener_lookup,
            "local_tool_lookup": local_tool_lookup,
            "assembly_anchor_part": anchor_part,
            "actions_before": len(actions),
            "actions_after": len(resolved_actions),
        },
    }


def main():
    graph = load_json(GRAPH_PATH)
    page_states = load_json(PAGE_STATES_PATH)
    actions_json = load_json(ACTIONS_PATH)
    identity_map = load_json(IDENTITY_MAP_PATH)

    output = resolve_actions(
        graph=graph,
        page_states=page_states,
        actions_json=actions_json,
        identity_map=identity_map,
    )

    save_json(output, OUTPUT_PATH)

    print(f"Saved resolved actions to {OUTPUT_PATH}")
    print(f"Actions before: {output['debug']['actions_before']}")
    print(f"Actions after : {output['debug']['actions_after']}")
    print(f"Warnings      : {len(output['warnings'])}")

    print("\nResolved actions:")
    for action in output["actions"]:
        print(
            f"  {action['action_uid']}: "
            f"{action['moving_ref']} -> {action['target_ref']} "
            f"({action['action_type']})"
        )

    if output["warnings"]:
        print("\nWarnings:")
        for warning in output["warnings"]:
            print(f"  {warning}")

    if not output["actions"]:
        sys.exit(
            "ERROR: no action could be resolved to canonical parts, so there is nothing "
            "to animate. See the warnings above and object_identity_map.json."
        )


if __name__ == "__main__":
    main()
