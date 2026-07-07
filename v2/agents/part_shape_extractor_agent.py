import json
from pathlib import Path
from datetime import datetime


INPUT_DIAGRAM_ANALYSIS = Path("v2/output/diagram_analysis.json")
INPUT_PRODUCT_MODEL = Path("v2/output/product_model.json")
OUTPUT_PART_SHAPES = Path("v2/output/part_shapes.json")


def load_json(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def infer_shape_from_text(text: str):
    text = text.lower()

    if any(w in text for w in ["screw", "bolt", "fastener"]):
        return "cylinder"

    if any(w in text for w in ["bar", "rod", "rail", "tube"]):
        return "long_cylinder"

    if any(w in text for w in ["bracket", "plate", "panel"]):
        return "thin_plate"

    if any(w in text for w in ["seat", "base", "top"]):
        return "rounded_panel"

    if any(w in text for w in ["frame", "leg", "support"]):
        return "rectangular_beam"

    return "proxy_block"


def infer_holes(labels, contains_fasteners):
    holes = []

    if contains_fasteners:
        count = 2
        if "4x" in labels:
            count = 4
        elif "2x" in labels:
            count = 2

        for i in range(count):
            holes.append({
                "hole_uid": f"H{i+1}",
                "type": "round",
                "relative_position": [
                    0.2 + (i % 2) * 0.6,
                    0.25 + (i // 2) * 0.5
                ],
                "radius_hint": 0.04
            })

    return holes


def extract_part_shapes():
    diagram_analysis = load_json(INPUT_DIAGRAM_ANALYSIS)

    product_model = {}
    if INPUT_PRODUCT_MODEL.exists():
        product_model = load_json(INPUT_PRODUCT_MODEL)

    part_shapes = {
        "metadata": {
            "created_at": datetime.utcnow().isoformat(),
            "source": "diagram_analysis.json",
            "mvp_note": "Heuristic visual proxy extraction for MVP rendering"
        },
        "parts": []
    }

    seen = set()

    for page in diagram_analysis:
        page_number = page.get("page_number")

        for diagram in page.get("diagrams", []):
            diagram_uid = diagram.get("diagram_uid")
            diagram_type = diagram.get("diagram_type")
            description = diagram.get("description", "")
            labels = diagram.get("visible_labels", [])
            contains_parts = diagram.get("contains_parts", False)
            contains_fasteners = diagram.get("contains_fasteners", False)
            contains_tools = diagram.get("contains_tools", False)
            likely_action = diagram.get("likely_action", "none")
            region = diagram.get("page_region", {})

            if not contains_parts and not contains_fasteners:
                continue

            shape_type = infer_shape_from_text(description)

            base_uid = f"P_PAGE{page_number}_{diagram_uid}"

            if base_uid in seen:
                continue

            seen.add(base_uid)

            width = abs(region.get("x_max", 1.0) - region.get("x_min", 0.0))
            height = abs(region.get("y_max", 1.0) - region.get("y_min", 0.0))

            aspect_ratio = round(width / height, 2) if height else 1.0

            part_shape = {
                "part_uid": base_uid,
                "source_page": page_number,
                "source_diagram_uid": diagram_uid,
                "diagram_type": diagram_type,
                "description": description,
                "likely_action": likely_action,
                "shape_type": shape_type,
                "visual_bbox": region,
                "aspect_ratio": aspect_ratio,
                "has_rounded_corners": shape_type in ["rounded_panel"],
                "has_slots": "slot" in description.lower(),
                "holes": infer_holes(labels, contains_fasteners),
                "anchor_points": [
                    {"anchor_uid": "A_TOP", "relative_position": [0.5, 0.0]},
                    {"anchor_uid": "A_CENTER", "relative_position": [0.5, 0.5]},
                    {"anchor_uid": "A_BOTTOM", "relative_position": [0.5, 1.0]}
                ],
                "extrusion_hint": {
                    "thickness": 0.12 if shape_type in ["thin_plate", "rounded_panel"] else 0.25,
                    "depth": 1.0
                },
                "labels": labels,
                "contains_fasteners": contains_fasteners,
                "contains_tools": contains_tools,
                "confidence": diagram.get("confidence", 0.7)
            }

            part_shapes["parts"].append(part_shape)

    OUTPUT_PART_SHAPES.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PART_SHAPES, "w", encoding="utf-8") as f:
        json.dump(part_shapes, f, indent=2)

    print("[SUCCESS] Part Shape Extractor complete")
    print(f"Parts extracted: {len(part_shapes['parts'])}")
    print(f"Output: {OUTPUT_PART_SHAPES}")


if __name__ == "__main__":
    extract_part_shapes()