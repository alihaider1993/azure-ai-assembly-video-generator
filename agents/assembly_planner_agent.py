import json
from pathlib import Path


def build_assembly_plan(
    product_model_path="outputs/json/product_model.json",
    output_path="outputs/json/assembly_plan.json"
):
    product = json.loads(Path(product_model_path).read_text(encoding="utf-8"))
    product_type = product.get("product_type", "generic_diy").lower()

    if "table" in product_type:
        plan = {
            "product_type": "table",
            "scenes": [
                {
                    "scene_id": 1,
                    "title": "Parts Overview",
                    "active_parts": ["tabletop", "rails", "legs", "screws"],
                    "motion": "show_parts",
                    "narration": "Prepare the tabletop, four rails, four legs, and the required screws."
                },
                {
                    "scene_id": 2,
                    "title": "Attach Frame Rails",
                    "active_parts": ["front_rail", "back_rail", "left_rail", "right_rail"],
                    "motion": "slide_in",
                    "narration": "Slide the frame rails into position underneath the tabletop."
                },
                {
                    "scene_id": 3,
                    "title": "Attach Legs",
                    "active_parts": ["leg_1", "leg_2", "leg_3", "leg_4"],
                    "motion": "rise_into_place",
                    "narration": "Raise each leg into the four corners of the frame."
                },
                {
                    "scene_id": 4,
                    "title": "Tighten Fasteners",
                    "active_parts": ["screws"],
                    "motion": "rotate_insert",
                    "narration": "Insert and tighten the screws to secure the frame and legs."
                },
                {
                    "scene_id": 5,
                    "title": "Assembly Complete",
                    "active_parts": ["assembled_table"],
                    "motion": "final_orbit",
                    "narration": "The table assembly is complete. Check that all screws are secure."
                }
            ]
        }
    else:
        plan = {
            "product_type": product_type,
            "scenes": [
                {
                    "scene_id": 1,
                    "title": "Parts Overview",
                    "active_parts": ["main_parts", "fasteners"],
                    "motion": "show_parts",
                    "narration": "Prepare all parts and fasteners before beginning assembly."
                },
                {
                    "scene_id": 2,
                    "title": "Align Components",
                    "active_parts": ["main_components"],
                    "motion": "slide_in",
                    "narration": "Align the main components according to the instruction manual."
                },
                {
                    "scene_id": 3,
                    "title": "Secure Fasteners",
                    "active_parts": ["fasteners"],
                    "motion": "rotate_insert",
                    "narration": "Secure the components using the supplied fasteners."
                },
                {
                    "scene_id": 4,
                    "title": "Assembly Complete",
                    "active_parts": ["assembled_product"],
                    "motion": "final_orbit",
                    "narration": "The assembly is complete. Check all connections before use."
                }
            ]
        }

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(plan, indent=2), encoding="utf-8")

    print(f"Assembly plan saved to {output_path}")
    return plan


if __name__ == "__main__":
    build_assembly_plan()