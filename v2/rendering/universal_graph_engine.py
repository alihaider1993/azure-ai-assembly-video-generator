import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from v2.agents.object_identity_tracker import identity_keys, is_assembly_like_part


PAGE_STATES_PATH = Path("v2/outputs/json/page_states.json")
RAW_ACTIONS_PATH = Path("v2/outputs/json/assembly_actions.json")
RESOLVED_ACTIONS_PATH = Path("v2/outputs/json/resolved_assembly_actions.json")
IDENTITY_MAP_PATH = Path("v2/outputs/json/object_identity_map.json")
OUTPUT_PATH = Path("v2/outputs/json/universal_assembly_graph.json")


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def norm(value: Any) -> str:
    return str(value or "").strip().lower()


def first_non_empty(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def infer_category(text: str) -> str:
    t = norm(text)
    if "chair" in t:
        return "chair"
    if "table" in t:
        return "table"
    if "bed" in t:
        return "bed"
    if "bike" in t or "bicycle" in t:
        return "bicycle"
    return "unknown"


def infer_part_primitive(part: Dict[str, Any]) -> str:
    text = norm(
        f"{part.get('manual_label', '')} "
        f"{part.get('name', '')} "
        f"{part.get('shape_family', '')} "
        f"{part.get('visual_description', '')}"
    )

    if "seat" in text or "pad" in text or "cushion" in text:
        return "rounded_panel"
    if "chair back" in text or "backrest" in text or "slat" in text:
        return "chair_back_frame"
    if "front leg" in text or "leg" in text:
        return "leg_frame"
    if "side rail" in text or "rail" in text:
        return "rail"
    if "panel" in text:
        return "panel"
    if "beam" in text:
        return "beam"
    if "frame" in text:
        return "composite"

    return part.get("shape_family", "box") or "box"


def is_composite_primitive(primitive: str) -> bool:
    return primitive in {"chair_back_frame", "leg_frame", "composite"}


def infer_fastener_primitive(fastener: Dict[str, Any]) -> str:
    text = norm(f"{fastener.get('name', '')} {fastener.get('shape_family', '')}")

    if "washer" in text:
        return "washer"
    if "bolt" in text:
        return "bolt"
    if "screw" in text:
        return "screw"
    if "dowel" in text or "cylinder" in text:
        return "cylinder"
    if "key" in text:
        return "tool"

    return fastener.get("shape_family", "cylinder") or "cylinder"


def load_identity_lookup() -> Dict[str, str]:
    if not IDENTITY_MAP_PATH.exists():
        return {}
    data = load_json(IDENTITY_MAP_PATH)
    return data.get("local_to_canonical", {})


def load_best_actions() -> Dict[str, Any]:
    if RESOLVED_ACTIONS_PATH.exists():
        return load_json(RESOLVED_ACTIONS_PATH)
    return load_json(RAW_ACTIONS_PATH)


def part_kinds_from_pages(page_states: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One entry per distinct kind of part, in first-seen order.

    Parts-list pages come first and are authoritative for quantity. Parts
    that only appear on assembly pages (e.g. an unlabelled tabletop, rails
    and legs, which IKEA parts lists often omit) are added too, keyed by
    label or normalised name, with the largest quantity seen on any page.
    Assembly-like parts ("assembled frame") are left out; they map to the
    primary assembly instead.
    """
    kinds: List[Dict[str, Any]] = []
    kind_by_key: Dict[str, Dict[str, Any]] = {}

    def add_or_merge(local_part: Dict[str, Any], page_number: int, from_parts_list: bool) -> None:
        keys = identity_keys(local_part.get("manual_label"), local_part.get("name"))
        if not keys:
            return

        quantity = int(local_part.get("quantity_visible") or 1)
        existing = next((kind_by_key[k] for k in keys if k in kind_by_key), None)

        if existing:
            if not existing["from_parts_list"]:
                existing["quantity"] = max(existing["quantity"], quantity)
            for key in keys:
                kind_by_key.setdefault(key, existing)
            return

        kind = {
            "local_part": local_part,
            "page_number": page_number,
            "quantity": quantity,
            "keys": keys,
            "from_parts_list": from_parts_list,
        }
        kinds.append(kind)
        for key in keys:
            kind_by_key[key] = kind

    for page in page_states:
        if norm(page.get("page_type")) == "parts_list":
            for local_part in page.get("visible_parts", []):
                add_or_merge(local_part, int(page.get("page_number", 0)), True)

    for page in page_states:
        if norm(page.get("page_type")) not in {"assembly_step", "final_check"}:
            continue
        for local_part in page.get("visible_parts", []):
            if not is_assembly_like_part(local_part):
                add_or_merge(local_part, int(page.get("page_number", 0)), False)

    return kinds


def collect_inventory_parts(page_states: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    parts: List[Dict[str, Any]] = []
    counter = 1

    for kind in part_kinds_from_pages(page_states):
        local_part = kind["local_part"]
        page_number = kind["page_number"]
        quantity = kind["quantity"]

        label = str(local_part.get("manual_label", "")).strip()
        name = first_non_empty(local_part.get("name"), f"Part {label}")
        primitive = infer_part_primitive(local_part)

        for idx in range(1, quantity + 1):
            uid = f"OBJ{counter:04d}"

            parts.append({
                "part_uid": uid,
                "manual_labels": [label] if label else [],
                "canonical_name": f"{name} {idx}/{quantity}" if quantity > 1 else name,
                "base_name": name,
                "identity_keys": kind["keys"],
                "instance_index": idx,
                "instance_count": quantity,
                "shape_family": local_part.get("shape_family", "unknown"),
                "material_hint": local_part.get("material_hint", "unknown"),
                "quantity_total": 1,
                "inventory_quantity_total": quantity,
                "inventory_source": "parts_list" if kind["from_parts_list"] else "assembly_pages",
                "geometry_intent": {
                    "primitive": primitive,
                    "is_composite": is_composite_primitive(primitive),
                    "subparts": [],
                },
                "connection_features": local_part.get("connection_features", []),
                "first_seen_page": page_number,
                "last_seen_page": page_number,
                "confidence": 0.78 if kind["from_parts_list"] else 0.68,
                "observations": [{
                    "page_number": page_number,
                    "local_part_uid": local_part.get("part_uid", ""),
                    "visual_description": local_part.get("visual_description", ""),
                    "page_position": local_part.get("page_position", ""),
                }],
            })

            counter += 1

    return parts


def add_page_observations(
    parts: List[Dict[str, Any]],
    page_states: List[Dict[str, Any]],
    identity_lookup: Dict[str, str],
) -> None:
    by_uid = {part["part_uid"]: part for part in parts}

    for page in page_states:
        if norm(page.get("page_type")) not in {"assembly_step", "final_check"}:
            continue

        page_number = int(page.get("page_number", 0))

        for local_part in page.get("visible_parts", []):
            local_uid = local_part.get("part_uid", "")
            canonical_uid = identity_lookup.get(local_uid, "")

            if canonical_uid not in by_uid:
                continue

            part = by_uid[canonical_uid]

            if any(obs.get("local_part_uid") == local_uid for obs in part.get("observations", [])):
                continue

            part["last_seen_page"] = max(int(part.get("last_seen_page", 0)), page_number)
            part.setdefault("observations", []).append({
                "page_number": page_number,
                "local_part_uid": local_uid,
                "visual_description": local_part.get("visual_description", ""),
                "page_position": local_part.get("page_position", ""),
            })


def collect_fasteners_and_tools(page_states: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    fasteners_by_key: Dict[str, Dict[str, Any]] = {}
    tools_by_key: Dict[str, Dict[str, Any]] = {}
    fastener_counter = 1
    tool_counter = 1

    for page in page_states:
        page_number = int(page.get("page_number", 0))

        for fastener in page.get("visible_fasteners", []):
            label = str(fastener.get("manual_label", "")).strip()
            name = first_non_empty(fastener.get("name"), f"Fastener {label}")
            key = label or norm(name)

            if key not in fasteners_by_key:
                uid = f"FAST{fastener_counter:04d}"
                fastener_counter += 1
                fasteners_by_key[key] = {
                    "fastener_uid": uid,
                    "manual_labels": [label] if label else [],
                    "name": name,
                    "shape_family": fastener.get("shape_family", "unknown"),
                    "quantity_total": int(fastener.get("quantity_visible") or 1),
                    "geometry_intent": {
                        "primitive": infer_fastener_primitive(fastener)
                    },
                    "first_seen_page": page_number,
                    "last_seen_page": page_number,
                    "observations": [],
                }

            fasteners_by_key[key]["last_seen_page"] = max(
                fasteners_by_key[key]["last_seen_page"],
                page_number,
            )
            fasteners_by_key[key]["observations"].append({
                "page_number": page_number,
                "local_fastener_uid": fastener.get("fastener_uid", ""),
            })

        for tool in page.get("visible_tools", []):
            name = first_non_empty(tool.get("name"), "Tool")
            key = norm(name)

            if key not in tools_by_key:
                uid = f"TOOL{tool_counter:04d}"
                tool_counter += 1
                tools_by_key[key] = {
                    "tool_uid": uid,
                    "name": name,
                    "first_seen_page": page_number,
                    "last_seen_page": page_number,
                }

            tools_by_key[key]["last_seen_page"] = max(
                tools_by_key[key]["last_seen_page"],
                page_number,
            )

    return list(fasteners_by_key.values()), list(tools_by_key.values())


def build_connections_from_actions(actions: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], List[str], List[str]]:
    connections: List[Dict[str, Any]] = []
    assembly_order: List[str] = []
    uncertainties: List[str] = []
    seen: Set[tuple[str, str, str]] = set()
    connected_pairs: Set[frozenset] = set()
    counter = 1

    for action in actions:
        action_uid = action.get("action_uid", "")
        moving = action.get("moving_ref", "")
        target = action.get("target_ref", "")
        fastener = action.get("fastener_ref", "")
        connection_type = action.get("connection_type", "attached")

        if not moving or not target:
            uncertainties.append(f"{action_uid}: skipped missing moving/target")
            continue

        if moving == target:
            uncertainties.append(f"{action_uid}: skipped self-connection {moving}")
            continue

        key = (moving, target, connection_type)
        if key in seen and not fastener:
            uncertainties.append(f"{action_uid}: duplicate connection skipped {moving}->{target}")
            continue

        # Inferred (synthetic) actions only add links the manual didn't
        # already state, in either direction.
        pair = frozenset((moving, target))
        if action.get("synthetic_reason") and pair in connected_pairs:
            uncertainties.append(f"{action_uid}: inferred connection already known {moving}<->{target}")
            continue

        seen.add(key)
        connected_pairs.add(pair)

        conn_uid = f"CONN{counter:04d}"
        counter += 1

        fasteners: List[str] = []
        if fastener:
            fasteners.append(fastener)
        elif moving.startswith("FAST"):
            fasteners.append(moving)

        connections.append({
            "connection_uid": conn_uid,
            "from_node_ref": moving,
            "to_node_ref": target,
            "connection_type": connection_type,
            "fasteners": fasteners,
            "tool_ref": action.get("tool_ref", ""),
            "created_on_page": action.get("source_page"),
            "created_by_action": action_uid,
            "confidence": action.get("confidence", 0.65),
            "visual_evidence": action.get("visual_evidence", ""),
        })
        assembly_order.append(conn_uid)

    return connections, assembly_order, uncertainties


def build_primary_assembly(
    page_states: List[Dict[str, Any]],
    connections: List[Dict[str, Any]],
) -> Dict[str, Any]:
    product_hint = "Primary Assembly"

    for page in page_states:
        if page.get("final_visible_structure"):
            product_hint = page.get("final_visible_structure")
            break

    members: List[str] = []

    for conn in connections:
        for key in ["from_node_ref", "to_node_ref"]:
            ref = conn.get(key, "")
            if ref.startswith(("OBJ", "FAST")) and ref not in members:
                members.append(ref)

        for fastener in conn.get("fasteners", []):
            if fastener and fastener not in members:
                members.append(fastener)

    category = infer_category(product_hint)

    return {
        "assembly_uid": "ASM0001",
        "canonical_name": f"{category.title()} Assembly" if category != "unknown" else "Primary Assembly",
        "shape_family": "assembly",
        "material_hint": "mixed",
        "geometry_intent": {
            "primitive": "composite",
            "is_composite": True,
            "subparts": members,
        },
        "members": members,
        "first_seen_page": min([c.get("created_on_page", 9999) or 9999 for c in connections] or [1]),
        "last_seen_page": max([c.get("created_on_page", 1) or 1 for c in connections] or [1]),
        "observations": [],
        "confidence": 0.72,
    }


def build_graph(
    page_states_path: Path = PAGE_STATES_PATH,
    output_path: Path = OUTPUT_PATH,
) -> Dict[str, Any]:
    page_states = load_json(page_states_path)
    identity_lookup = load_identity_lookup()

    actions_json = load_best_actions()
    actions = actions_json.get("actions", [])

    parts = collect_inventory_parts(page_states)
    add_page_observations(parts, page_states, identity_lookup)

    fasteners, tools = collect_fasteners_and_tools(page_states)
    connections, assembly_order, uncertainties = build_connections_from_actions(actions)
    primary_assembly = build_primary_assembly(page_states, connections)

    product_name = "unknown"
    for page in page_states:
        if page.get("final_visible_structure"):
            product_name = page.get("final_visible_structure")
            break

    graph = {
        "graph_id": "assembly_graph_v2_001",
        "schema_version": "2.4",
        "product_hint": {
            "name": product_name,
            "category": infer_category(product_name),
            "confidence": 0.65 if product_name != "unknown" else 0.3,
        },
        "parts": parts,
        "assemblies": [primary_assembly],
        "connections": connections,
        "fasteners": fasteners,
        "tools": tools,
        "assembly_order": assembly_order,
        "debug": {
            "actions_source": str(RESOLVED_ACTIONS_PATH if RESOLVED_ACTIONS_PATH.exists() else RAW_ACTIONS_PATH),
            "identity_map_used": IDENTITY_MAP_PATH.exists(),
            "parts_count": len(parts),
            "fasteners_count": len(fasteners),
            "tools_count": len(tools),
            "connections_count": len(connections),
            "resolved_actions_count": len(actions),
            "identity_lookup": identity_lookup,
        },
        "uncertainties": actions_json.get("warnings", []) + uncertainties,
    }

    save_json(graph, output_path)

    print()
    print("Universal Graph Summary")
    print("-----------------------")
    print(f"Parts: {len(parts)}")
    print(f"Assemblies: {len(graph['assemblies'])}")
    print(f"Connections: {len(connections)}")
    print(f"Assembly order: {len(assembly_order)}")
    print(f"Fasteners: {len(fasteners)}")
    print(f"Tools: {len(tools)}")
    print(f"Actions source: {graph['debug']['actions_source']}")
    print(f"Identity map used: {graph['debug']['identity_map_used']}")
    print(f"Uncertainties: {len(graph['uncertainties'])}")
    print()

    return graph


if __name__ == "__main__":
    result = build_graph()

    if not result["connections"]:
        sys.exit(
            f"ERROR: the assembly graph has no connections "
            f"({result['debug']['resolved_actions_count']} actions read), so there is "
            "nothing to animate. Check the earlier stages' output."
        )
