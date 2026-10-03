"""
Action Replicator — v1

Root cause this fixes:
Assembly manuals often show one step and label it "Repeat x2" / "Repeat x4"
instead of drawing every physical copy. Earlier stages correctly resolve
actions for ONE representative instance per manual label (e.g. label "1"
-> OBJ0001), but never replicate that action across the other physical
copies of the same part (OBJ0002, OBJ0003, OBJ0004 for a 4x side rail).
Result: only 1 of 4 rails, 1 of 2 legs, 1 of 2 chair backs, etc. ever
appear in the motion plan, so most parts sit static in the render.

This expands each resolved action across sibling instances, stepping both
ends of the action through their sibling groups together (cycling if group
sizes differ), so the first replica is the action as resolved. Actions
between two parts of the same kind are not expanded, and replicas never
duplicate an action already stated for that instance. This is a heuristic,
not a guaranteed-correct left/right pairing for every product geometry —
review the expanded output for non-symmetric designs.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

GRAPH_PATH = Path("v2/outputs/json/universal_assembly_graph.json")
RESOLVED_ACTIONS_PATH = Path("v2/outputs/json/resolved_assembly_actions.json")
OUTPUT_PATH = Path("v2/outputs/json/resolved_assembly_actions.json")  # overwrite in place


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def build_sibling_groups(graph: Dict[str, Any]) -> Dict[str, List[str]]:
    """part_uid -> ordered list of its sibling instances, e.g.
    OBJ0001 -> [OBJ0001, OBJ0002, OBJ0003, OBJ0004]."""
    groups: Dict[str, List[str]] = {}
    by_base: Dict[str, List[Dict[str, Any]]] = {}

    for part in graph.get("parts", []):
        # identity_keys separates two kinds of part that share a display
        # name (e.g. two different "bracket" labels).
        keys = part.get("identity_keys") or [part.get("base_name", "")]
        by_base.setdefault(keys[0], []).append(part)

    for base, parts in by_base.items():
        ordered = sorted(parts, key=lambda p: p.get("instance_index", 1))
        uids = [p["part_uid"] for p in ordered if p.get("part_uid")]
        for uid in uids:
            groups[uid] = uids

    return groups


def paired_uid(ref_uid: str, pair_index: int, groups: Dict[str, List[str]]) -> str:
    """The sibling `pair_index` places after `ref_uid` in its group, so
    replica 0 is the action as resolved and the pairing between moving
    and target instances is kept as the action stated it."""
    group = groups.get(ref_uid)
    if not group or len(group) <= 1:
        return ref_uid
    return group[(group.index(ref_uid) + pair_index) % len(group)]


def action_key(action: Dict[str, Any]) -> tuple:
    return (action.get("moving_ref", ""), action.get("target_ref", ""), action.get("action_type", ""))


def replicate_actions(graph: Dict[str, Any], resolved: Dict[str, Any]) -> Dict[str, Any]:
    groups = build_sibling_groups(graph)
    actions = resolved.get("actions", [])
    expanded: List[Dict[str, Any]] = []
    skipped_self = 0
    skipped_duplicates = 0

    if any(action.get("replicated_from") for action in actions):
        # This stage overwrites its input; running it twice would multiply
        # every action again.
        print("Actions are already replicated; leaving them unchanged.")
        return resolved

    # A replica never repeats an action the manual already states for that
    # instance (e.g. "leg 2 onto top" shown on its own as well as "leg 1").
    stated = {action_key(action) for action in actions}
    seen = set()

    for action in actions:
        moving = action.get("moving_ref", "")
        target = action.get("target_ref", "")

        # Two parts of the same kind joined to each other (panel to panel)
        # are one specific connection; shifting both ends would only turn
        # it into self-joins or a reversed copy.
        same_kind = moving in groups and groups.get(moving) is groups.get(target)

        repeat_count = 1
        if not same_kind:
            for ref in (moving, target):
                group = groups.get(ref)
                if group:
                    repeat_count = max(repeat_count, len(group))

        for pair_index in range(repeat_count):
            new_action = dict(action)
            new_action["moving_ref"] = paired_uid(moving, pair_index, groups)
            new_action["target_ref"] = paired_uid(target, pair_index, groups)
            new_action["fastener_ref"] = action.get("fastener_ref", "")

            if new_action["moving_ref"] == new_action["target_ref"]:
                skipped_self += 1
                continue

            key = action_key(new_action)
            if key in seen or (pair_index > 0 and key in stated):
                skipped_duplicates += 1
                continue
            seen.add(key)

            if repeat_count > 1:
                new_action["action_uid"] = f"{action.get('action_uid', 'ACT')}_R{pair_index}"
                new_action["replicated_from"] = action.get("action_uid", "")
                new_action["replica_index"] = pair_index

            expanded.append(new_action)

    resolved["actions"] = expanded
    resolved.setdefault("debug", {})["replication"] = {
        "actions_before_replication": len(actions),
        "actions_after_replication": len(expanded),
        "self_pairs_skipped": skipped_self,
        "duplicates_skipped": skipped_duplicates,
    }
    return resolved


def main():
    graph = load_json(GRAPH_PATH)
    resolved = load_json(RESOLVED_ACTIONS_PATH)

    output = replicate_actions(graph, resolved)
    save_json(output, OUTPUT_PATH)

    replication = output.get("debug", {}).get("replication", {})
    print(f"Saved replicated actions to {OUTPUT_PATH}")
    print(f"Actions before replication: {replication.get('actions_before_replication')}")
    print(f"Actions after replication : {replication.get('actions_after_replication')}")


if __name__ == "__main__":
    main()