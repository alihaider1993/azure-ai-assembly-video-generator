import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple


GRAPH_PATH = Path("v2/outputs/json/universal_assembly_graph.json")
PAGE_STATES_PATH = Path("v2/outputs/json/page_states.json")

OUTPUT_PATH = Path("v2/outputs/json/object_identity_map.json")


ASSEMBLY_NAME_KEYWORDS = [
    "assembled frame",
    "completed frame",
    "assembled chair",
    "fully assembled",
    "final assembly",
    "assembled structure",
    "frame assembly",
]


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def norm(value: Any) -> str:
    return str(value or "").strip().lower()


def first_label(labels: List[Any]) -> str:
    if not labels:
        return ""
    return str(labels[0]).strip()


def normalize_part_name(name: Any) -> str:
    """Lower-case a part name and drop counts and a plural "s", so
    "Legs", "4x leg" and "leg" all give "leg"."""
    text = norm(name)
    text = re.sub(r"\b\d+\s*x\b|\bx\s*\d+\b", " ", text)
    words = text.split()

    if words and len(words[-1]) > 3 and words[-1].endswith("s") and not words[-1].endswith("ss"):
        words[-1] = words[-1][:-1]

    return " ".join(words)


def identity_keys(label: Any, name: Any) -> List[str]:
    """Keys that identify one kind of part across pages, strongest first.
    A printed label wins; an unlabelled part (most structural parts in
    IKEA-style manuals) is matched by its normalised name."""
    keys = []
    label_text = str(label or "").strip()
    name_text = normalize_part_name(name)

    if label_text:
        keys.append(f"label:{label_text}")
    if name_text:
        keys.append(f"name:{name_text}")

    return keys


def local_part_keys(local_part: Dict[str, Any]) -> List[str]:
    return identity_keys(local_part.get("manual_label"), local_part.get("name"))


def canonical_part_keys(part: Dict[str, Any]) -> List[str]:
    return part.get("identity_keys") or identity_keys(
        first_label(part.get("manual_labels", [])),
        part.get("base_name"),
    )


def build_inventory(graph: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """identity key -> that part's instances in instance order. A part is
    listed under each of its keys (label and name)."""
    inventory = defaultdict(list)

    parts = sorted(
        graph.get("parts", []),
        key=lambda p: (
            int(p.get("instance_index", 9999)),
            p.get("part_uid", ""),
        ),
    )

    for part in parts:
        if not part.get("part_uid"):
            continue

        for key in canonical_part_keys(part):
            inventory[key].append(part)

    return dict(inventory)


def find_candidates(
    local_part: Dict[str, Any],
    inventory: Dict[str, List[Dict[str, Any]]],
) -> Tuple[str, List[Dict[str, Any]]]:
    """(group key, canonical instances) for a local part, or ("", [])."""
    for key in local_part_keys(local_part):
        candidates = inventory.get(key, [])
        if candidates:
            return canonical_part_keys(candidates[0])[0], candidates

    return "", []


def get_primary_assembly_uid(graph: Dict[str, Any]) -> str:
    assemblies = graph.get("assemblies", [])

    if not assemblies:
        return ""

    # Prefer the assembly with the most members.
    assemblies = sorted(
        assemblies,
        key=lambda a: len(a.get("members", [])),
        reverse=True,
    )

    return assemblies[0].get("assembly_uid", "")


def is_assembly_like_part(local_part: Dict[str, Any]) -> bool:
    text = norm(
        " ".join(
            [
                str(local_part.get("name", "")),
                str(local_part.get("visual_description", "")),
                str(local_part.get("shape_family", "")),
            ]
        )
    )

    return any(keyword in text for keyword in ASSEMBLY_NAME_KEYWORDS)


def similarity_score(local_part: Dict[str, Any], canonical_part: Dict[str, Any]) -> float:
    score = 0.0

    local_label = norm(local_part.get("manual_label"))
    canonical_labels = [norm(x) for x in canonical_part.get("manual_labels", [])]

    if local_label and local_label in canonical_labels:
        score += 5.0

    if norm(local_part.get("shape_family")) == norm(canonical_part.get("shape_family")):
        score += 2.0

    if norm(local_part.get("material_hint")) == norm(canonical_part.get("material_hint")):
        score += 1.0

    local_name = norm(local_part.get("name"))
    canonical_name = norm(canonical_part.get("canonical_name"))

    if local_name and canonical_name:
        local_words = set(local_name.replace("/", " ").split())
        canonical_words = set(canonical_name.replace("/", " ").split())
        overlap = local_words.intersection(canonical_words)
        score += min(len(overlap), 3) * 0.75

    local_features = local_part.get("connection_features", [])
    canonical_features = canonical_part.get("connection_features", [])

    if local_features and canonical_features:
        local_feature_types = {
            norm(f.get("feature_type"))
            for f in local_features
            if f.get("feature_type")
        }
        canonical_feature_types = {
            norm(f.get("feature_type"))
            for f in canonical_features
            if f.get("feature_type")
        }
        score += len(local_feature_types.intersection(canonical_feature_types)) * 0.5

    return score


def choose_new_instance(
    local_part: Dict[str, Any],
    group_key: str,
    candidates: List[Dict[str, Any]],
    used_counts: Dict[str, int],
) -> str:
    if not candidates:
        return ""

    scored: List[Tuple[float, Dict[str, Any]]] = []

    for part in candidates:
        scored.append((similarity_score(local_part, part), part))

    scored.sort(key=lambda x: x[0], reverse=True)

    ordered_candidates = [part for _, part in scored]
    used_index = used_counts[group_key]

    if used_index < len(ordered_candidates):
        chosen = ordered_candidates[used_index]
        used_counts[group_key] += 1
        return chosen.get("part_uid", "")

    return ordered_candidates[0].get("part_uid", "")


def should_track_page(page: Dict[str, Any]) -> bool:
    return norm(page.get("page_type")) in {
        "parts_list",
        "assembly_step",
        "final_check",
    }


def add_history(
    canonical_history: Dict[str, List[Dict[str, Any]]],
    canonical_uid: str,
    page_number: int,
    page_type: str,
    local_part: Dict[str, Any],
    resolution_reason: str,
) -> None:
    canonical_history[canonical_uid].append(
        {
            "page_number": page_number,
            "page_type": page_type,
            "local_uid": local_part.get("part_uid", ""),
            "manual_label": str(local_part.get("manual_label", "")).strip(),
            "local_name": local_part.get("name", ""),
            "shape_family": local_part.get("shape_family", ""),
            "material_hint": local_part.get("material_hint", ""),
            "page_position": local_part.get("page_position", ""),
            "resolution_reason": resolution_reason,
        }
    )


def build_identity_map(
    graph: Dict[str, Any],
    page_states: List[Dict[str, Any]],
) -> Dict[str, Any]:
    inventory = build_inventory(graph)
    primary_assembly_uid = get_primary_assembly_uid(graph)

    local_to_canonical: Dict[str, str] = {}
    canonical_history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    active_instances: Dict[str, str] = {}
    used_counts: Dict[str, int] = defaultdict(int)

    warnings: List[str] = []

    for page in page_states:
        if not should_track_page(page):
            continue

        page_number = int(page.get("page_number", 0))
        page_type = norm(page.get("page_type"))
        # Canonical parts already taken by another local part on this page,
        # so two "leg" entries on one page don't collapse into one leg.
        used_on_page: set = set()

        for local_part in page.get("visible_parts", []):
            local_uid = local_part.get("part_uid", "")

            if not local_uid:
                continue

            # Important MVP rule:
            # If the page calls something "assembled frame", "fully assembled chair",
            # etc., do NOT map it to normal inventory items such as seat pad or chair back.
            # Map it to the main assembly node instead.
            if is_assembly_like_part(local_part):
                if primary_assembly_uid:
                    local_to_canonical[local_uid] = primary_assembly_uid
                    add_history(
                        canonical_history=canonical_history,
                        canonical_uid=primary_assembly_uid,
                        page_number=page_number,
                        page_type=page_type,
                        local_part=local_part,
                        resolution_reason="assembly_like_part_mapped_to_primary_assembly",
                    )
                else:
                    warnings.append(
                        f"Page {page_number}: assembly-like part {local_uid} found but no assembly node exists."
                    )
                continue

            group_key, candidates = find_candidates(local_part, inventory)

            if not candidates:
                warnings.append(
                    f"Page {page_number}: no canonical part matches local part {local_uid} "
                    f"(label={local_part.get('manual_label', '')!r}, name={local_part.get('name', '')!r})."
                )
                continue

            canonical_uid = ""
            resolution_reason = ""

            if page_type == "parts_list":
                canonical_uid = candidates[0].get("part_uid", "")
                resolution_reason = "inventory_reference_first_instance"
            else:
                canonical_uid = active_instances.get(group_key, "")

                if canonical_uid and canonical_uid not in used_on_page:
                    resolution_reason = "reused_active_instance"
                else:
                    canonical_uid = choose_new_instance(
                        local_part=local_part,
                        group_key=group_key,
                        candidates=candidates,
                        used_counts=used_counts,
                    )
                    resolution_reason = "new_instance_selected"

                if canonical_uid:
                    active_instances[group_key] = canonical_uid

            if canonical_uid:
                used_on_page.add(canonical_uid)
                local_to_canonical[local_uid] = canonical_uid

                add_history(
                    canonical_history=canonical_history,
                    canonical_uid=canonical_uid,
                    page_number=page_number,
                    page_type=page_type,
                    local_part=local_part,
                    resolution_reason=resolution_reason,
                )

    return {
        "schema_version": "1.1",
        "description": (
            "Maps local page-level part IDs like P004_001 to stable canonical "
            "object IDs like OBJ0001 or assembly IDs like ASM0001. This helps "
            "downstream agents preserve object identity across pages."
        ),
        "local_to_canonical": local_to_canonical,
        "canonical_history": canonical_history,
        "debug": {
            "primary_assembly_uid": primary_assembly_uid,
            "inventory_keys": {
                key: [p.get("part_uid") for p in parts]
                for key, parts in inventory.items()
            },
            "active_instances": active_instances,
            "used_counts": dict(used_counts),
        },
        "warnings": warnings,
    }


def main():
    graph = load_json(GRAPH_PATH)
    page_states = load_json(PAGE_STATES_PATH)

    output = build_identity_map(graph, page_states)

    save_json(output, OUTPUT_PATH)

    print(f"Saved object identity map to {OUTPUT_PATH}")
    print(f"Primary assembly: {output['debug']['primary_assembly_uid']}")
    print(f"Local mappings : {len(output['local_to_canonical'])}")
    print(f"Canonical objs : {len(output['canonical_history'])}")
    print(f"Warnings       : {len(output['warnings'])}")

    print("\nLocal to canonical:")
    for local, canonical in output["local_to_canonical"].items():
        print(f"  {local} -> {canonical}")

    if output["warnings"]:
        print("\nWarnings:")
        for warning in output["warnings"]:
            print(f"  {warning}")

    if not any(uid.startswith("OBJ") for uid in output["local_to_canonical"].values()):
        sys.exit(
            "ERROR: no part on any page matched a canonical graph part, so there is "
            "nothing to animate. Check visible_parts in page_states.json."
        )


if __name__ == "__main__":
    main()
