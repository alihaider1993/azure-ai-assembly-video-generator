import json
from pathlib import Path
from typing import Any, Dict, List, Optional


PAGE_STATES_PATH = Path("v2/outputs/json/page_states.json")
ASSEMBLY_DELTAS_PATH = Path("v2/outputs/json/assembly_deltas.json")
ASSEMBLY_ACTIONS_PATH = Path("v2/outputs/json/assembly_actions.json")
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


def primitive_from_shape(shape: str) -> str:
    shape = norm(shape)
    return {
        "panel": "panel",
        "beam": "beam",
        "frame": "composite",
        "curved": "curved",
        "cylinder": "cylinder",
        "bracket": "bracket",
        "hinge": "hinge",
        "wheel": "wheel",
        "cable": "cable",
        "electronics": "electronics_box",
        "screw": "screw",
        "bolt": "bolt",
        "washer": "washer",
        "nut": "nut",
        "dowel": "cylinder",
        "irregular": "irregular",
    }.get(shape, "unknown")


def is_tool_like(item: Dict[str, Any]) -> bool:
    text = norm(f"{item.get('name')} {item.get('visual_description')} {item.get('manual_label')}")
    return any(x in text for x in ["hex key", "allen key", "screwdriver", "drill", "hammer"])


def is_fastener_like(item: Dict[str, Any]) -> bool:
    text = norm(f"{item.get('name')} {item.get('visual_description')} {item.get('shape_family')}")
    return any(x in text for x in ["screw", "bolt", "nut", "washer", "dowel", "fastener"])


class UniversalGraphBuilder:
    def __init__(self) -> None:
        self.parts: List[Dict[str, Any]] = []
        self.assemblies: List[Dict[str, Any]] = []
        self.fasteners: List[Dict[str, Any]] = []
        self.tools: List[Dict[str, Any]] = []
        self.connections: List[Dict[str, Any]] = []

        self.local_to_global_node: Dict[str, str] = {}
        self.local_to_fastener: Dict[str, str] = {}
        self.local_to_tool: Dict[str, str] = {}

        # label -> list of physical part UIDs created from inventory quantity
        self.inventory_label_to_parts: Dict[str, List[str]] = {}
        self.inventory_name_to_parts: Dict[str, List[str]] = {}
        self.inventory_claim_index: Dict[str, int] = {}

        self.part_counter = 1
        self.assembly_counter = 1
        self.fastener_counter = 1
        self.tool_counter = 1
        self.connection_counter = 1

        self.current_assembly_uid: Optional[str] = None
        self.warnings: List[str] = []

    def local_key(self, page: int, local_uid: str) -> str:
        return f"p{page}:{local_uid}"

    def new_part_uid(self) -> str:
        uid = f"OBJ{self.part_counter:04d}"
        self.part_counter += 1
        return uid

    def new_assembly_uid(self) -> str:
        uid = f"ASM{self.assembly_counter:04d}"
        self.assembly_counter += 1
        return uid

    def new_fastener_uid(self) -> str:
        uid = f"FAST{self.fastener_counter:04d}"
        self.fastener_counter += 1
        return uid

    def new_tool_uid(self) -> str:
        uid = f"TOOL{self.tool_counter:04d}"
        self.tool_counter += 1
        return uid

    def new_connection_uid(self) -> str:
        uid = f"CONN{self.connection_counter:04d}"
        self.connection_counter += 1
        return uid

    def is_assembly_observation(self, part: Dict[str, Any]) -> bool:
        text = norm(f"{part.get('name')} {part.get('visual_description')}")
        shape = norm(part.get("shape_family"))
        return (
            "assembled frame" in text
            or "partially assembled" in text
            or "frame with" in text
            or "chair frame" in text
            or "assembled structure" in text
            or (shape == "frame" and "assembled" in text)
        )

    def make_part_record(self, observed: Dict[str, Any], page: int, instance_index: int = 1, total_instances: int = 1) -> Dict[str, Any]:
        uid = self.new_part_uid()
        label = observed.get("manual_label", "")
        base_name = observed.get("name") or observed.get("visual_description") or "unknown part"

        name = base_name
        if total_instances > 1:
            name = f"{base_name} {instance_index}/{total_instances}"

        return {
            "part_uid": uid,
            "manual_labels": [label] if label else [],
            "canonical_name": name,
            "base_name": base_name,
            "instance_index": instance_index,
            "instance_count": total_instances,
            "shape_family": observed.get("shape_family", "unknown"),
            "material_hint": observed.get("material_hint", "unknown"),
            "quantity_total": 1,
            "inventory_quantity_total": total_instances,
            "geometry_intent": {
                "primitive": primitive_from_shape(observed.get("shape_family", "unknown")),
                "is_composite": norm(observed.get("shape_family")) == "frame",
                "subparts": []
            },
            "connection_features": observed.get("connection_features", []),
            "first_seen_page": page,
            "last_seen_page": page,
            "confidence": 0.75,
            "observations": [
                {
                    "page_number": page,
                    "local_part_uid": observed.get("part_uid", ""),
                    "visual_description": observed.get("visual_description", ""),
                    "page_position": observed.get("page_position", "unknown")
                }
            ]
        }

    def create_inventory_parts(self, observed: Dict[str, Any], page: int) -> List[str]:
        qty = max(1, int(observed.get("quantity_visible", 1) or 1))
        label = norm(observed.get("manual_label"))
        name_key = norm(observed.get("name") or observed.get("visual_description"))

        if label and label in self.inventory_label_to_parts:
            return self.inventory_label_to_parts[label]

        if not label and name_key in self.inventory_name_to_parts:
            return self.inventory_name_to_parts[name_key]

        uids = []
        for i in range(1, qty + 1):
            part = self.make_part_record(observed, page, i, qty)
            self.parts.append(part)
            uids.append(part["part_uid"])

        if label:
            self.inventory_label_to_parts[label] = uids
        if name_key:
            self.inventory_name_to_parts[name_key] = uids

        return uids

    def claim_inventory_part(self, observed: Dict[str, Any], page: int) -> Optional[str]:
        label = norm(observed.get("manual_label"))
        name_key = norm(observed.get("name") or observed.get("visual_description"))

        candidates = []
        claim_key = ""

        if label and label in self.inventory_label_to_parts:
            candidates = self.inventory_label_to_parts[label]
            claim_key = f"label:{label}"
        elif name_key and name_key in self.inventory_name_to_parts:
            candidates = self.inventory_name_to_parts[name_key]
            claim_key = f"name:{name_key}"

        if not candidates:
            return None

        idx = self.inventory_claim_index.get(claim_key, 0)
        uid = candidates[min(idx, len(candidates) - 1)]
        self.inventory_claim_index[claim_key] = idx + 1

        part = self.get_part(uid)
        self.update_part(part, observed, page)
        return uid

    def get_part(self, uid: str) -> Dict[str, Any]:
        for part in self.parts:
            if part["part_uid"] == uid:
                return part
        raise KeyError(uid)

    def create_assembly(self, observed: Dict[str, Any], page: int) -> Dict[str, Any]:
        uid = self.new_assembly_uid()
        assembly = {
            "assembly_uid": uid,
            "canonical_name": observed.get("name") or "assembled frame",
            "shape_family": observed.get("shape_family", "frame"),
            "material_hint": observed.get("material_hint", "unknown"),
            "geometry_intent": {
                "primitive": "composite",
                "is_composite": True,
                "subparts": []
            },
            "members": [],
            "first_seen_page": page,
            "last_seen_page": page,
            "observations": [],
            "confidence": 0.75
        }
        self.assemblies.append(assembly)
        return assembly

    def update_assembly(self, assembly: Dict[str, Any], observed: Dict[str, Any], page: int) -> None:
        assembly["last_seen_page"] = max(int(assembly.get("last_seen_page", page)), page)
        if assembly.get("material_hint") in ["", "unknown"]:
            assembly["material_hint"] = observed.get("material_hint", "unknown")
        assembly["observations"].append({
            "page_number": page,
            "local_part_uid": observed.get("part_uid", ""),
            "visual_description": observed.get("visual_description", ""),
            "page_position": observed.get("page_position", "unknown")
        })

    def register_assembly_observation(self, observed: Dict[str, Any], page: int) -> str:
        local_uid = observed.get("part_uid", "")
        key = self.local_key(page, local_uid)
        if key in self.local_to_global_node:
            return self.local_to_global_node[key]

        if self.current_assembly_uid:
            assembly = self.get_assembly(self.current_assembly_uid)
        else:
            assembly = self.create_assembly(observed, page)
            self.current_assembly_uid = assembly["assembly_uid"]

        self.update_assembly(assembly, observed, page)
        self.local_to_global_node[key] = assembly["assembly_uid"]
        return assembly["assembly_uid"]

    def update_part(self, part: Dict[str, Any], observed: Dict[str, Any], page: int) -> None:
        label = observed.get("manual_label")
        if label and label not in part["manual_labels"]:
            part["manual_labels"].append(label)
        part["last_seen_page"] = max(int(part.get("last_seen_page", page)), page)
        part["observations"].append({
            "page_number": page,
            "local_part_uid": observed.get("part_uid", ""),
            "visual_description": observed.get("visual_description", ""),
            "page_position": observed.get("page_position", "unknown")
        })

    def register_part(self, observed: Dict[str, Any], page: int, page_type: str) -> Optional[str]:
        local_uid = observed.get("part_uid", "")
        key = self.local_key(page, local_uid)
        if key in self.local_to_global_node:
            return self.local_to_global_node[key]

        if is_tool_like(observed) or is_fastener_like(observed):
            return None

        # Preserve real inventory quantities as physical objects.
        if page_type == "parts_list":
            uids = self.create_inventory_parts(observed, page)
            if uids:
                self.local_to_global_node[key] = uids[0]
                return uids[0]

        if self.is_assembly_observation(observed):
            return self.register_assembly_observation(observed, page)

        claimed = self.claim_inventory_part(observed, page)
        if claimed:
            self.local_to_global_node[key] = claimed
            return claimed

        part = self.make_part_record(observed, page, 1, 1)
        self.parts.append(part)
        self.local_to_global_node[key] = part["part_uid"]
        return part["part_uid"]

    def register_fastener(self, observed: Dict[str, Any], page: int) -> str:
        local_uid = observed.get("fastener_uid", "")
        key = self.local_key(page, local_uid)
        if key in self.local_to_fastener:
            return self.local_to_fastener[key]

        label = norm(observed.get("manual_label"))
        name = norm(observed.get("name"))
        shape = norm(observed.get("shape_family"))

        for fastener in self.fasteners:
            labels = [norm(x) for x in fastener.get("manual_labels", [])]
            if label and label in labels:
                fastener["last_seen_page"] = page
                self.local_to_fastener[key] = fastener["fastener_uid"]
                return fastener["fastener_uid"]
            if name and name == norm(fastener.get("name")) and shape == norm(fastener.get("shape_family")):
                fastener["last_seen_page"] = page
                self.local_to_fastener[key] = fastener["fastener_uid"]
                return fastener["fastener_uid"]

        uid = self.new_fastener_uid()
        self.fasteners.append({
            "fastener_uid": uid,
            "manual_labels": [observed.get("manual_label", "")] if observed.get("manual_label") else [],
            "name": observed.get("name") or observed.get("shape_family", "fastener"),
            "shape_family": observed.get("shape_family", "unknown"),
            "quantity_total": int(observed.get("quantity_visible", 1) or 1),
            "geometry_intent": {"primitive": primitive_from_shape(observed.get("shape_family", "unknown"))},
            "first_seen_page": page,
            "last_seen_page": page,
            "observations": [{"page_number": page, "local_fastener_uid": local_uid}]
        })
        self.local_to_fastener[key] = uid
        return uid

    def register_tool(self, observed: Dict[str, Any], page: int) -> str:
        local_uid = observed.get("tool_uid", "")
        key = self.local_key(page, local_uid)
        if key in self.local_to_tool:
            return self.local_to_tool[key]

        tool_name = norm(observed.get("name"))
        for tool in self.tools:
            existing = norm(tool.get("name"))
            if tool_name == existing:
                tool["last_seen_page"] = page
                self.local_to_tool[key] = tool["tool_uid"]
                return tool["tool_uid"]
            if ("hex key" in tool_name and "allen key" in existing) or ("allen key" in tool_name and "hex key" in existing):
                tool["last_seen_page"] = page
                self.local_to_tool[key] = tool["tool_uid"]
                return tool["tool_uid"]

        uid = self.new_tool_uid()
        self.tools.append({"tool_uid": uid, "name": observed.get("name", "tool"), "first_seen_page": page, "last_seen_page": page})
        self.local_to_tool[key] = uid
        return uid

    def get_assembly(self, uid: str) -> Dict[str, Any]:
        for assembly in self.assemblies:
            if assembly["assembly_uid"] == uid:
                return assembly
        raise KeyError(uid)

    def resolve_node(self, local_ref: str, page: int) -> str:
        if not local_ref:
            return ""
        return self.local_to_global_node.get(self.local_key(page, local_ref), "")

    def resolve_fastener(self, local_ref: str, page: int) -> str:
        if not local_ref:
            return ""
        return self.local_to_fastener.get(self.local_key(page, local_ref), "")

    def resolve_tool(self, local_ref: str, page: int) -> str:
        if not local_ref:
            return ""
        return self.local_to_tool.get(self.local_key(page, local_ref), "")

    def add_member_to_assembly(self, assembly_uid: str, member_uid: str, page: int) -> None:
        if not assembly_uid.startswith("ASM"):
            return
        assembly = self.get_assembly(assembly_uid)
        if member_uid and member_uid != assembly_uid and member_uid not in assembly["members"]:
            assembly["members"].append(member_uid)
            assembly["geometry_intent"]["subparts"].append(member_uid)
            assembly["last_seen_page"] = max(int(assembly.get("last_seen_page", page)), page)

    def create_connection(self, from_node: str, to_node: str, connection_type: str, page: int, action_uid: str, fastener: str, tool: str, confidence: float, evidence: str) -> None:
        if not from_node or not to_node:
            self.warnings.append(f"{action_uid}: unresolved endpoint on page {page}")
            return
        if from_node == to_node:
            self.warnings.append(f"{action_uid}: skipped self-connection {from_node}")
            return

        for existing in self.connections:
            if existing["from_node_ref"] == from_node and existing["to_node_ref"] == to_node and existing["connection_type"] == connection_type:
                return

        conn_uid = self.new_connection_uid()
        self.connections.append({
            "connection_uid": conn_uid,
            "from_node_ref": from_node,
            "to_node_ref": to_node,
            "connection_type": connection_type,
            "fasteners": [fastener] if fastener else [],
            "tool_ref": tool,
            "created_on_page": page,
            "created_by_action": action_uid,
            "confidence": confidence,
            "visual_evidence": evidence
        })

        if to_node.startswith("ASM"):
            self.add_member_to_assembly(to_node, from_node, page)
        if from_node.startswith("ASM"):
            self.add_member_to_assembly(from_node, to_node, page)

    def register_action_connection(self, action: Dict[str, Any]) -> None:
        page = int(action.get("source_page", 0))
        moving_ref = action.get("moving_ref", "")
        target_ref = action.get("target_ref", "")
        fastener_ref = action.get("fastener_ref", "")
        tool_ref = action.get("tool_ref", "")

        moving_node = self.resolve_node(moving_ref, page)
        target_node = self.resolve_node(target_ref, page)
        moving_fastener = self.resolve_fastener(moving_ref, page)
        fastener = self.resolve_fastener(fastener_ref, page) or moving_fastener
        tool = self.resolve_tool(tool_ref, page)

        connection_type = action.get("connection_type", "unknown")
        action_uid = action.get("action_uid", "")
        confidence = float(action.get("confidence", 0.75))
        evidence = action.get("visual_evidence", "")

        if moving_fastener and target_node:
            self.create_connection(moving_fastener, target_node, connection_type, page, action_uid, fastener, tool, confidence, evidence)
            return

        self.create_connection(moving_node, target_node, connection_type, page, action_uid, fastener, tool, confidence, evidence)

    def collect_uncertainties(self, page_states: List[Dict[str, Any]], deltas: List[Dict[str, Any]]) -> List[str]:
        items = []
        for page in page_states:
            for uncertainty in page.get("uncertainties", []):
                items.append(f"Page {page.get('page_number')}: {uncertainty}")
        for delta in deltas:
            for warning in delta.get("warnings", []):
                items.append(f"{delta.get('delta_id')}: {warning}")
        items.extend(self.warnings)
        return items

    def validate_graph(self) -> List[str]:
        warnings = []
        node_ids = ({p["part_uid"] for p in self.parts} | {a["assembly_uid"] for a in self.assemblies} | {f["fastener_uid"] for f in self.fasteners})
        for conn in self.connections:
            if conn["from_node_ref"] not in node_ids:
                warnings.append(f"{conn['connection_uid']}: from_node_ref missing: {conn['from_node_ref']}")
            if conn["to_node_ref"] not in node_ids:
                warnings.append(f"{conn['connection_uid']}: to_node_ref missing: {conn['to_node_ref']}")
            if conn["from_node_ref"] == conn["to_node_ref"]:
                warnings.append(f"{conn['connection_uid']}: self connection detected")
        for assembly in self.assemblies:
            for member in assembly.get("members", []):
                if member not in node_ids:
                    warnings.append(f"{assembly['assembly_uid']}: member not found: {member}")
        return warnings

    def build(self, page_states: List[Dict[str, Any]], deltas: List[Dict[str, Any]], actions_data: Dict[str, Any]) -> Dict[str, Any]:
        page_states = sorted(page_states, key=lambda p: int(p.get("page_number", 0)))

        for page_state in page_states:
            page = int(page_state.get("page_number", 0))
            page_type = page_state.get("page_type", "")
            for part in page_state.get("visible_parts", []):
                self.register_part(part, page, page_type)
            for fastener in page_state.get("visible_fasteners", []):
                self.register_fastener(fastener, page)
            for tool in page_state.get("visible_tools", []):
                self.register_tool(tool, page)

        for action in actions_data.get("actions", []):
            self.register_action_connection(action)

        product_hint = {"name": "unknown", "category": "unknown", "confidence": 0.0}
        for page_state in page_states:
            if page_state.get("page_type") == "cover" and page_state.get("final_visible_structure"):
                product_hint = {"name": page_state.get("final_visible_structure"), "category": "unknown", "confidence": 0.6}
                break

        validation_warnings = self.validate_graph()

        return {
            "graph_id": "assembly_graph_v2_001",
            "schema_version": "2.3",
            "product_hint": product_hint,
            "parts": self.parts,
            "assemblies": self.assemblies,
            "connections": self.connections,
            "fasteners": self.fasteners,
            "tools": self.tools,
            "assembly_order": [c["connection_uid"] for c in self.connections],
            "debug": {
                "inventory_label_to_parts": self.inventory_label_to_parts,
                "inventory_name_to_parts": self.inventory_name_to_parts
            },
            "uncertainties": self.collect_uncertainties(page_states, deltas) + validation_warnings
        }


def build_universal_graph(page_states_path: Path = PAGE_STATES_PATH, assembly_deltas_path: Path = ASSEMBLY_DELTAS_PATH, assembly_actions_path: Path = ASSEMBLY_ACTIONS_PATH, output_path: Path = OUTPUT_PATH) -> Dict[str, Any]:
    page_states = load_json(page_states_path)
    deltas = load_json(assembly_deltas_path)
    actions_data = load_json(assembly_actions_path)

    builder = UniversalGraphBuilder()
    graph = builder.build(page_states, deltas, actions_data)

    save_json(graph, output_path)

    print(f"Saved universal assembly graph to {output_path}")
    print(f"Parts: {len(graph.get('parts', []))}")
    print(f"Assemblies: {len(graph.get('assemblies', []))}")
    print(f"Fasteners: {len(graph.get('fasteners', []))}")
    print(f"Tools: {len(graph.get('tools', []))}")
    print(f"Connections: {len(graph.get('connections', []))}")
    print(f"Assembly order steps: {len(graph.get('assembly_order', []))}")
    print(f"Uncertainties: {len(graph.get('uncertainties', []))}")

    return graph


if __name__ == "__main__":
    build_universal_graph()
