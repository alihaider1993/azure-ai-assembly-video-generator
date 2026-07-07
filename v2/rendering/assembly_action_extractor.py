import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple


PAGE_STATES_PATH = Path("v2/outputs/json/page_states.json")
ASSEMBLY_DELTAS_PATH = Path("v2/outputs/json/assembly_deltas.json")
OUTPUT_PATH = Path("v2/outputs/json/assembly_actions.json")


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def norm(value: Any) -> str:
    return str(value or "").strip().lower()


def action_to_connection_type(action_type: str) -> str:
    action = norm(action_type)

    if action in {"tighten", "rotate"}:
        return "screwed"
    if action == "insert":
        return "inserted"
    if action == "slide":
        return "slotted"
    if action in {"attach", "place", "lower"}:
        return "attached"
    if action == "align":
        return "aligned"
    if action == "flip":
        return "reoriented"

    return "unknown"


def label_in_text(label: str, text: str) -> bool:
    if not label:
        return False

    label = re.escape(str(label).strip())
    return re.search(rf"\b{label}\b", text, re.IGNORECASE) is not None


def part_exists(page: Dict[str, Any], ref: str) -> bool:
    return bool(ref) and any(
        p.get("part_uid") == ref for p in page.get("visible_parts", [])
    )


def fastener_exists(page: Dict[str, Any], ref: str) -> bool:
    return bool(ref) and any(
        f.get("fastener_uid") == ref for f in page.get("visible_fasteners", [])
    )


def tool_exists(page: Dict[str, Any], ref: str) -> bool:
    return bool(ref) and any(
        t.get("tool_uid") == ref for t in page.get("visible_tools", [])
    )


def find_fastener_by_label_or_text(page: Dict[str, Any], evidence: str) -> str:
    evidence_n = norm(evidence)

    best_uid = ""
    best_score = 0

    for fastener in page.get("visible_fasteners", []):
        uid = fastener.get("fastener_uid", "")
        label = fastener.get("manual_label", "")
        name = norm(fastener.get("name", ""))
        shape = norm(fastener.get("shape_family", ""))

        score = 0

        if label and label_in_text(label, evidence):
            score += 10
        if name and name in evidence_n:
            score += 5
        if shape and shape in evidence_n:
            score += 3

        if score > best_score:
            best_score = score
            best_uid = uid

    return best_uid


def find_tool_by_text(page: Dict[str, Any], evidence: str) -> str:
    evidence_n = norm(evidence)

    best_uid = ""
    best_score = 0

    for tool in page.get("visible_tools", []):
        uid = tool.get("tool_uid", "")
        name = norm(tool.get("name", ""))

        score = 0

        if name and name in evidence_n:
            score += 5
        if "allen" in evidence_n and "allen" in name:
            score += 4
        if "screwdriver" in evidence_n and "screwdriver" in name:
            score += 4

        if score > best_score:
            best_score = score
            best_uid = uid

    return best_uid


def find_mentioned_parts(page: Dict[str, Any], evidence: str) -> List[Tuple[int, str]]:
    """
    Finds visible parts mentioned in visual_evidence.

    Returns:
        List of (score, part_uid), highest score first.
    """
    evidence_n = norm(evidence)
    results = []

    for part in page.get("visible_parts", []):
        uid = part.get("part_uid", "")
        label = part.get("manual_label", "")
        name = norm(part.get("name", ""))
        desc = norm(part.get("visual_description", ""))
        shape = norm(part.get("shape_family", ""))

        score = 0

        if label and label_in_text(label, evidence):
            score += 12

        if name and name in evidence_n:
            score += 8

        # Token-level partial match for names like "horizontal beam"
        for token in name.split():
            if len(token) >= 4 and token in evidence_n:
                score += 2

        if shape and shape in evidence_n:
            score += 2

        if "assembled" in name or "assembled" in desc:
            score += 4
        if "frame" in name or shape == "frame":
            score += 3
        if "panel" in name or shape == "panel":
            score += 2
        if "beam" in name or shape == "beam":
            score += 2

        if score > 0 and uid:
            results.append((score, uid))

    results.sort(reverse=True)
    return results


def choose_target_from_page(page: Dict[str, Any], moving_ref: str = "") -> str:
    candidates = []

    for part in page.get("visible_parts", []):
        uid = part.get("part_uid", "")
        if not uid or uid == moving_ref:
            continue

        text = norm(
            f"{part.get('name')} {part.get('visual_description')} {part.get('shape_family')}"
        )

        score = 0

        if "assembled" in text:
            score += 8
        if "frame" in text:
            score += 6
        if "structure" in text:
            score += 5
        if "panel" in text:
            score += 3
        if "beam" in text:
            score += 2

        if score > 0:
            candidates.append((score, uid))

    if not candidates:
        parts = page.get("visible_parts", [])
        return parts[0].get("part_uid", "") if parts else ""

    candidates.sort(reverse=True)
    return candidates[0][1]


def resolve_fastener_action_refs(
    page: Dict[str, Any],
    observed: Dict[str, Any],
) -> Dict[str, str]:
    evidence = observed.get("visual_evidence", "")
    action_type = norm(observed.get("action_type", ""))

    moving_ref = observed.get("moving_part_ref", "")
    target_ref = observed.get("target_part_ref", "")
    fastener_ref = observed.get("fastener_ref", "")
    tool_ref = observed.get("tool_ref", "")

    if not fastener_ref:
        fastener_ref = find_fastener_by_label_or_text(page, evidence)

    if not tool_ref:
        tool_ref = find_tool_by_text(page, evidence)

    if not moving_ref:
        if action_type in {"tighten", "insert"} and fastener_ref:
            moving_ref = fastener_ref
        else:
            mentioned_parts = find_mentioned_parts(page, evidence)
            moving_ref = mentioned_parts[0][1] if mentioned_parts else ""

    if not target_ref:
        mentioned_parts = find_mentioned_parts(page, evidence)

        for _, uid in mentioned_parts:
            if uid != moving_ref:
                target_ref = uid
                break

        if not target_ref:
            target_ref = choose_target_from_page(page, moving_ref)

    return {
        "moving_ref": moving_ref,
        "target_ref": target_ref,
        "fastener_ref": fastener_ref,
        "tool_ref": tool_ref,
    }


def build_action(
    action_uid: str,
    source_page: int,
    action_type: str,
    moving_ref: str,
    target_ref: str,
    fastener_ref: str,
    tool_ref: str,
    direction_hint: str,
    visual_evidence: str,
    confidence: float,
    page: Dict[str, Any],
    synthetic_reason: str = "",
) -> Dict[str, Any]:
    action = {
        "action_uid": action_uid,
        "source_page": source_page,
        "action_type": action_type,
        "connection_type": action_to_connection_type(action_type),
        "moving_ref": moving_ref,
        "target_ref": target_ref,
        "fastener_ref": fastener_ref if fastener_exists(page, fastener_ref) else "",
        "tool_ref": tool_ref if tool_exists(page, tool_ref) else "",
        "direction_hint": direction_hint,
        "creates_or_updates_assembly": True,
        "confidence": confidence,
        "visual_evidence": visual_evidence,
        "synthetic_reason": synthetic_reason,
        "warnings": []
    }

    if not part_exists(page, moving_ref) and not fastener_exists(page, moving_ref):
        action["warnings"].append(f"moving_ref not found on page: {moving_ref}")

    if not part_exists(page, target_ref):
        action["warnings"].append(f"target_ref not found on page: {target_ref}")

    return action


def extract_actions(page_states: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    actions = []
    action_counter = 1
    seen_pairs = set()

    for page in page_states:
        page_number = int(page.get("page_number", 0))

        if page.get("page_type") != "assembly_step":
            continue

        for observed in page.get("observed_actions", []):
            action_type = observed.get("action_type", "unknown")
            direction_hint = observed.get("direction_hint", "unknown")
            visual_evidence = observed.get("visual_evidence", "")

            # 1) Existing fastener/tool action
            resolved = resolve_fastener_action_refs(page, observed)

            moving_ref = resolved["moving_ref"]
            target_ref = resolved["target_ref"]
            fastener_ref = resolved["fastener_ref"]
            tool_ref = resolved["tool_ref"]

            if moving_ref and target_ref:
                pair_key = (page_number, action_type, moving_ref, target_ref, fastener_ref)

                if pair_key not in seen_pairs:
                    actions.append(
                        build_action(
                            action_uid=f"ACT{action_counter:04d}",
                            source_page=page_number,
                            action_type=action_type,
                            moving_ref=moving_ref,
                            target_ref=target_ref,
                            fastener_ref=fastener_ref,
                            tool_ref=tool_ref,
                            direction_hint=direction_hint,
                            visual_evidence=visual_evidence,
                            confidence=0.65,
                            page=page,
                            synthetic_reason=""
                        )
                    )
                    seen_pairs.add(pair_key)
                    action_counter += 1

            # 2) NEW MVP structural part-to-part action
            mentioned_parts = find_mentioned_parts(page, visual_evidence)

            if len(mentioned_parts) >= 2:
                structural_moving = mentioned_parts[0][1]
                structural_target = mentioned_parts[1][1]

                if structural_moving != structural_target:
                    structural_type = action_type

                    if structural_type in {"tighten", "insert"}:
                        structural_type = "attach"

                    pair_key = (
                        page_number,
                        "structural",
                        structural_type,
                        structural_moving,
                        structural_target,
                    )

                    if pair_key not in seen_pairs:
                        actions.append(
                            build_action(
                                action_uid=f"ACT{action_counter:04d}",
                                source_page=page_number,
                                action_type=structural_type,
                                moving_ref=structural_moving,
                                target_ref=structural_target,
                                fastener_ref=fastener_ref,
                                tool_ref=tool_ref,
                                direction_hint=direction_hint,
                                visual_evidence=visual_evidence,
                                confidence=0.72,
                                page=page,
                                synthetic_reason="MVP structural action inferred from multiple visible parts mentioned in visual evidence."
                            )
                        )
                        seen_pairs.add(pair_key)
                        action_counter += 1

            # 3) If only one part is mentioned and there are multiple parts on page,
            # create a conservative structural action from that part to best target.
            elif len(mentioned_parts) == 1:
                structural_moving = mentioned_parts[0][1]
                structural_target = choose_target_from_page(page, structural_moving)

                if structural_moving and structural_target and structural_moving != structural_target:
                    structural_type = action_type

                    if structural_type in {"tighten", "insert"}:
                        structural_type = "attach"

                    pair_key = (
                        page_number,
                        "structural_single",
                        structural_type,
                        structural_moving,
                        structural_target,
                    )

                    if pair_key not in seen_pairs:
                        actions.append(
                            build_action(
                                action_uid=f"ACT{action_counter:04d}",
                                source_page=page_number,
                                action_type=structural_type,
                                moving_ref=structural_moving,
                                target_ref=structural_target,
                                fastener_ref=fastener_ref,
                                tool_ref=tool_ref,
                                direction_hint=direction_hint,
                                visual_evidence=visual_evidence,
                                confidence=0.58,
                                page=page,
                                synthetic_reason="MVP structural action inferred from one mentioned part and strongest visible target."
                            )
                        )
                        seen_pairs.add(pair_key)
                        action_counter += 1

    return actions


def build_assembly_actions(
    page_states_path: Path = PAGE_STATES_PATH,
    assembly_deltas_path: Path = ASSEMBLY_DELTAS_PATH,
    output_path: Path = OUTPUT_PATH,
) -> Dict[str, Any]:
    page_states = load_json(page_states_path)

    if not isinstance(page_states, list):
        raise ValueError("page_states.json must contain a list.")

    if assembly_deltas_path.exists():
        _ = load_json(assembly_deltas_path)

    actions = extract_actions(page_states)

    output = {
        "schema_version": "2.1",
        "actions": actions,
        "warnings": []
    }

    if len(actions) == 0:
        output["warnings"].append("No assembly actions extracted.")

    save_json(output, output_path)

    print(f"Saved assembly actions to {output_path}")
    print(f"Assembly actions: {len(actions)}")

    structural_count = sum(
        1 for a in actions if str(a.get("synthetic_reason", "")).strip()
    )

    fastener_count = len(actions) - structural_count
    warnings_count = sum(len(a.get("warnings", [])) for a in actions)

    print(f"Fastener/direct actions: {fastener_count}")
    print(f"Structural inferred actions: {structural_count}")
    print(f"Action warnings: {warnings_count}")

    return output


if __name__ == "__main__":
    build_assembly_actions()