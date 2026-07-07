import json
from pathlib import Path
from typing import Any, Dict, List, Optional


PAGE_STATES_PATH = Path("v2/outputs/json/page_states.json")
OUTPUT_PATH = Path("v2/outputs/json/assembly_deltas.json")


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def norm(value: Any) -> str:
    return str(value or "").strip().lower()


def make_part_key(part: Dict[str, Any]) -> str:
    return norm(
        part.get("manual_label")
        or part.get("name")
        or part.get("visual_description")
        or part.get("part_uid")
    )


def make_fastener_key(fastener: Dict[str, Any]) -> str:
    return norm(
        fastener.get("manual_label")
        or fastener.get("name")
        or fastener.get("fastener_uid")
    )


def find_part_by_ref(parts: List[Dict[str, Any]], ref: str) -> Optional[Dict[str, Any]]:
    ref_n = norm(ref)
    if not ref_n:
        return None

    for part in parts:
        candidates = [
            part.get("part_uid"),
            part.get("manual_label"),
            part.get("name"),
        ]
        if ref_n in [norm(c) for c in candidates]:
            return part

    return None


def find_fastener_by_ref(fasteners: List[Dict[str, Any]], ref: str) -> Optional[Dict[str, Any]]:
    ref_n = norm(ref)
    if not ref_n:
        return None

    for fastener in fasteners:
        candidates = [
            fastener.get("fastener_uid"),
            fastener.get("manual_label"),
            fastener.get("name"),
        ]
        if ref_n in [norm(c) for c in candidates]:
            return fastener

    return None


def action_to_connection_type(action_type: str) -> str:
    action = norm(action_type)

    if action in {"tighten", "rotate"}:
        return "screwed"
    if action == "insert":
        return "inserted"
    if action == "slide":
        return "slotted"
    if action == "attach":
        return "attached"
    if action == "place":
        return "placed_on"
    if action == "align":
        return "aligned"
    if action == "flip":
        return "flipped"

    return "unknown"


def build_delta(
    previous_page: Optional[Dict[str, Any]],
    current_page: Dict[str, Any],
) -> Dict[str, Any]:
    page_number = int(current_page.get("page_number", 0))

    previous_parts = previous_page.get("visible_parts", []) if previous_page else []
    current_parts = current_page.get("visible_parts", [])

    previous_fasteners = previous_page.get("visible_fasteners", []) if previous_page else []
    current_fasteners = current_page.get("visible_fasteners", [])

    previous_part_keys = {make_part_key(p) for p in previous_parts}
    previous_fastener_keys = {make_fastener_key(f) for f in previous_fasteners}

    added_parts = []
    for part in current_parts:
        key = make_part_key(part)
        if key and key not in previous_part_keys:
            added_parts.append(part.get("part_uid") or part.get("manual_label") or part.get("name"))

    added_fasteners = []
    for fastener in current_fasteners:
        key = make_fastener_key(fastener)
        if key and key not in previous_fastener_keys:
            added_fasteners.append(
                fastener.get("fastener_uid")
                or fastener.get("manual_label")
                or fastener.get("name")
            )

    moved_parts = []
    new_connections = []
    actions = []

    for idx, action in enumerate(current_page.get("observed_actions", []), start=1):
        action_type = action.get("action_type", "unknown")

        moving_ref = action.get("moving_part_ref", "")
        target_ref = action.get("target_part_ref", "")
        fastener_ref = action.get("fastener_ref", "")
        tool_ref = action.get("tool_ref", "")

        moving_part = find_part_by_ref(current_parts, moving_ref)
        target_part = find_part_by_ref(current_parts, target_ref)
        fastener = find_fastener_by_ref(current_fasteners, fastener_ref)

        moving_uid = (
            moving_part.get("part_uid")
            if moving_part
            else moving_ref
        )

        target_uid = (
            target_part.get("part_uid")
            if target_part
            else target_ref
        )

        fastener_uid = (
            fastener.get("fastener_uid")
            if fastener
            else fastener_ref
        )

        if moving_uid:
            moved_parts.append({
                "part_ref": moving_uid,
                "from_state": "separate_or_previous_page",
                "to_state": action_type,
                "evidence_page": page_number,
            })

        if moving_uid and target_uid:
            connection_uid = f"c_p{page_number}_{idx}"

            new_connections.append({
                "connection_uid": connection_uid,
                "from_part_ref": moving_uid,
                "to_part_ref": target_uid,
                "connection_type": action_to_connection_type(action_type),
                "fastener_ref": fastener_uid,
                "tool_ref": tool_ref,
                "confidence": 0.75,
                "evidence_page": page_number,
                "visual_evidence": action.get("visual_evidence", ""),
            })

        actions.append({
            "action_type": action_type,
            "part_ref": moving_uid,
            "target_ref": target_uid,
            "fastener_ref": fastener_uid,
            "tool_ref": tool_ref,
            "direction_hint": action.get("direction_hint", "unknown"),
            "evidence_page": page_number,
            "visual_evidence": action.get("visual_evidence", ""),
        })

    return {
        "delta_id": f"d_p{page_number}",
        "from_page": int(previous_page.get("page_number", 0)) if previous_page else None,
        "to_page": page_number,
        "added_parts": added_parts,
        "added_fasteners": added_fasteners,
        "moved_parts": moved_parts,
        "new_connections": new_connections,
        "actions": actions,
        "warnings": current_page.get("warnings", []),
        "uncertainties": current_page.get("uncertainties", []),
    }


def build_assembly_deltas(
    page_states_path: Path = PAGE_STATES_PATH,
    output_path: Path = OUTPUT_PATH,
) -> List[Dict[str, Any]]:
    page_states = load_json(page_states_path)

    if not isinstance(page_states, list):
        raise ValueError("page_states.json must contain a list of page states.")

    page_states = sorted(
        page_states,
        key=lambda p: int(p.get("page_number", 0))
    )

    deltas = []

    previous_page = None
    for current_page in page_states:
        page_type = norm(current_page.get("page_type"))

        if page_type in {"cover", "warning", "unknown"}:
            previous_page = current_page
            continue

        delta = build_delta(previous_page, current_page)
        deltas.append(delta)

        previous_page = current_page

    save_json(deltas, output_path)

    print(f"Saved assembly deltas to {output_path}")
    print(f"Deltas created: {len(deltas)}")

    total_connections = sum(len(d.get("new_connections", [])) for d in deltas)
    total_actions = sum(len(d.get("actions", [])) for d in deltas)

    print(f"Connections detected: {total_connections}")
    print(f"Actions detected: {total_actions}")

    return deltas


if __name__ == "__main__":
    build_assembly_deltas()