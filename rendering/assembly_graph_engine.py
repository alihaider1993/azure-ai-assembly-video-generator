import json
from pathlib import Path


def normalize(text):
    return str(text or "").lower().strip()


def component_role(component):
    return normalize(
        component.get("semantic_role")
        or component.get("role")
        or component.get("name")
    )


def get_component_id(component, index=None):
    base = component.get("component_id") or component.get("manual_label") or component.get("name", "component")
    base = str(base).replace(" ", "_")
    if index is not None:
        return f"{base}_{index + 1}"
    return base


def build_nodes(product):
    nodes = []

    for component in product.get("components", []):
        qty = int(component.get("quantity", 1))
        for i in range(qty):
            node_id = get_component_id(component, i if qty > 1 else None)
            nodes.append({
                "node_id": node_id,
                "name": component.get("name", node_id),
                "manual_label": component.get("manual_label", ""),
                "type": "component",
                "semantic_role": component.get("semantic_role", "unknown_part"),
                "geometry_type": component.get("geometry_type", "cuboid"),
                "material": component.get("material", "wood"),
                "dimensions": component.get("dimensions", {}),
                "assembly_motion": component.get("assembly_motion", "move_to_position")
            })

    for fastener in product.get("fasteners", []):
        qty = int(fastener.get("quantity", 1))
        max_visible = min(qty, 12)

        for i in range(max_visible):
            base = fastener.get("fastener_id") or fastener.get("manual_label") or fastener.get("name", "fastener")
            node_id = f"{str(base).replace(' ', '_')}_{i + 1}"
            nodes.append({
                "node_id": node_id,
                "name": fastener.get("name", node_id),
                "manual_label": fastener.get("manual_label", ""),
                "type": "fastener",
                "semantic_role": fastener.get("semantic_role", "fastener"),
                "geometry_type": fastener.get("geometry_type", "screw"),
                "material": "metal",
                "dimensions": {
                    "length": 0.12,
                    "width": 0.12,
                    "height": 0.5,
                    "unit": "generic"
                },
                "assembly_motion": fastener.get("assembly_motion", "rotate_insert")
            })

    return nodes


def find_nodes(nodes, keywords, node_type=None):
    result = []
    for node in nodes:
        if node_type and node.get("type") != node_type:
            continue

        text = normalize(
            f"{node.get('name')} {node.get('semantic_role')} {node.get('manual_label')} {node.get('geometry_type')}"
        )

        if any(k in text for k in keywords):
            result.append(node)

    return result


def add_edge(edges, source, target, relationship, motion, step=None, fastener=None):
    if not source or not target:
        return

    edge = {
        "from": source["node_id"],
        "to": target["node_id"],
        "relationship": relationship,
        "motion": motion,
    }

    if step is not None:
        edge["step"] = step

    if fastener:
        edge["fastener"] = fastener["node_id"]

    if edge not in edges:
        edges.append(edge)


def build_universal_relationships(nodes, product_type):
    edges = []

    panels = find_nodes(nodes, ["panel", "surface", "board"], "component")
    side_panels = find_nodes(nodes, ["side_panel", "side panel", "side"], "component")
    back_panels = find_nodes(nodes, ["back_panel", "back panel", "backrest", "back"], "component")
    top_panels = find_nodes(nodes, ["top_panel", "top panel", "top"], "component")
    bottom_panels = find_nodes(nodes, ["bottom_panel", "bottom panel", "base", "bottom"], "component")
    shelves = find_nodes(nodes, ["shelf", "shelves"], "component")
    doors = find_nodes(nodes, ["door"], "component")
    drawers = find_nodes(nodes, ["drawer"], "component")
    legs = find_nodes(nodes, ["leg"], "component")
    frames = find_nodes(nodes, ["frame"], "component")
    rails = find_nodes(nodes, ["rail"], "component")
    beams = find_nodes(nodes, ["beam", "support"], "component")
    brackets = find_nodes(nodes, ["bracket"], "component")
    hinges = find_nodes(nodes, ["hinge"], "component")
    wheels = find_nodes(nodes, ["wheel", "caster"], "component")
    tubes = find_nodes(nodes, ["tube", "rod", "bar"], "component")
    electronics = find_nodes(nodes, ["motor", "board", "electronic", "cable", "cover"], "component")
    fasteners = find_nodes(nodes, ["screw", "bolt", "nut", "washer", "dowel", "fastener"], "fastener")

    primary_base = (
        bottom_panels[0] if bottom_panels else
        frames[0] if frames else
        panels[0] if panels else
        rails[0] if rails else
        beams[0] if beams else
        nodes[0] if nodes else None
    )

    # Chair/table/bench style support logic
    for leg in legs:
        target = primary_base
        add_edge(edges, leg, target, "supports", "rise_into_position")

    for rail in rails:
        target = frames[0] if frames else primary_base
        add_edge(edges, rail, target, "connects_to", "slide_into_position")

    for beam in beams:
        target = frames[0] if frames else primary_base
        add_edge(edges, beam, target, "reinforces", "slide_into_position")

    for back in back_panels:
        target = frames[0] if frames else primary_base
        add_edge(edges, back, target, "attaches_to", "lower_down")

    # Cabinet / wardrobe / shelf logic
    for side in side_panels:
        target = bottom_panels[0] if bottom_panels else primary_base
        add_edge(edges, side, target, "attaches_to", "vertical_insert")

    for top in top_panels:
        target = side_panels[0] if side_panels else primary_base
        add_edge(edges, top, target, "caps_structure", "lower_down")

    for shelf in shelves:
        target = side_panels[0] if side_panels else primary_base
        add_edge(edges, shelf, target, "slots_into", "slide_into_position")

    for door in doors:
        target = side_panels[0] if side_panels else primary_base
        add_edge(edges, door, target, "hinges_to", "rotate_into_position")

    for drawer in drawers:
        target = side_panels[0] if side_panels else primary_base
        add_edge(edges, drawer, target, "slides_into", "slide_into_position")

    for hinge in hinges:
        target = doors[0] if doors else side_panels[0] if side_panels else primary_base
        add_edge(edges, hinge, target, "mounts_to", "place_and_fasten")

    for bracket in brackets:
        target = primary_base
        add_edge(edges, bracket, target, "brackets_to", "place_and_fasten")

    # Gym equipment / toys / electronics
    for tube in tubes:
        target = frames[0] if frames else primary_base
        add_edge(edges, tube, target, "connects_to", "insert")

    for wheel in wheels:
        target = primary_base
        add_edge(edges, wheel, target, "mounts_to", "push_fit")

    for part in electronics:
        target = primary_base
        add_edge(edges, part, target, "installs_into", "place_inside")

    # Fasteners secure existing component relationships
    connection_edges = [e for e in edges if e["relationship"] != "secures_connection"]

    for i, fastener in enumerate(fasteners):
        if not connection_edges:
            break

        target_edge = connection_edges[i % len(connection_edges)]

        edges.append({
            "from": fastener["node_id"],
            "to": target_edge["from"],
            "relationship": "secures_connection",
            "target_connection": {
                "from": target_edge["from"],
                "to": target_edge["to"]
            },
            "motion": "rotate_insert",
            "step": i + 1
        })

    return edges


def build_assembly_graph(
    product_model_path="outputs/json/product_model.json",
    output_path="outputs/json/assembly_graph.json"
):
    product = json.loads(Path(product_model_path).read_text(encoding="utf-8"))

    product_type = product.get("product_type", "generic_diy")
    nodes = build_nodes(product)
    edges = build_universal_relationships(nodes, product_type)

    graph = {
        "product_type": product_type,
        "product_name": product.get("product_name", "DIY Product"),
        "nodes": nodes,
        "edges": edges,
        "summary": product.get("summary", "")
    }

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(graph, indent=2), encoding="utf-8")

    print(f"Assembly graph saved to {output_path}")
    print(f"Nodes: {len(nodes)}")
    print(f"Edges: {len(edges)}")

    if len(edges) == 0:
        print("WARNING: Assembly graph has zero edges. Product model may be too vague.")

    return graph


if __name__ == "__main__":
    build_assembly_graph()