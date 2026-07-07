import sys
import json
import re
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from services.foundry import FoundryClient


def extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```json", "", text)
        text = re.sub(r"^```", "", text)
        text = re.sub(r"```$", "", text).strip()
    return json.loads(text)


class ProductBuilderAgent:
    def __init__(self):
        self.ai = FoundryClient()

    def build_product_model(self):
        router_path = Path("outputs/router_results.json")

        if not router_path.exists():
            raise FileNotFoundError("outputs/router_results.json not found. Run router_agent.py first.")

        router_results = router_path.read_text(encoding="utf-8")

        prompt = f"""

You are a Product Builder Agent for a universal DIY Assembly Video Generator.

Your job is to extract a renderable product model from the manual analysis.

You must extract BOTH:
1. Hardware/parts list items
2. Final assembled product structure visible in later instruction diagrams

Do not rely only on the parts page.
If later pages show legs, seat panel, backrest, cross braces, shelves, doors, handles, wheels, cables, motors, or covers, include them as components even if they are not listed separately on the parts page.

Infer all major renderable physical components visible across the whole manual, including final assembled structure.

This system must support:
- chairs
- tables
- wardrobes
- cabinets
- shelves
- beds
- gym equipment
- toys
- electronics
- appliances
- general household DIY products

Do NOT create a generic table.
Do NOT create a generic chair.
Do NOT invent a template.
Extract physical component instances from the manual.

Use these universal component roles where possible:
- panel
- side_panel
- back_panel
- top_panel
- bottom_panel
- shelf
- door
- drawer
- leg
- frame
- rail
- beam
- bracket
- hinge
- wheel
- handle
- rod
- tube
- cable
- motor
- electronic_board
- cover
- fastener
- screw
- bolt
- nut
- washer
- dowel
- unknown_part

Router analysis:
{router_results}

Return ONLY valid JSON in this exact structure:

{{
  "product_type": "",
  "product_name": "",
  "confidence": 0.0,
  "components": [
    {{
      "component_id": "",
      "manual_label": "",
      "name": "",
      "semantic_role": "",
      "geometry_type": "",
      "quantity": 1,
      "material": "",
      "dimensions": {{
        "length": 1.0,
        "width": 1.0,
        "height": 1.0,
        "unit": "generic"
      }},
      "visual_notes": "",
      "assembly_motion": ""
    }}
  ],
  "fasteners": [
    {{
      "fastener_id": "",
      "manual_label": "",
      "name": "",
      "semantic_role": "",
      "geometry_type": "",
      "quantity": 1,
      "assembly_motion": ""
    }}
  ],
  "tools": [],
  "summary": ""
}}

Geometry type must be one of:
- cuboid
- thin_panel
- long_beam
- cylinder
- tube
- curved_part
- bracket
- hinge
- wheel
- screw
- bolt
- nut
- washer
- cable
- electronics_box
- irregular

Rules:
1. Prefer specific physical parts over broad descriptions.
2. If the manual shows a frame, split it into meaningful renderable parts if possible.
3. Use manual part numbers where available.
4. Use generic dimensions only when real dimensions are not visible.
5. Make the output useful for procedural Blender rendering.
6. JSON only.
"""

        raw = self.ai.chat(prompt)
        return extract_json(raw)


if __name__ == "__main__":
    agent = ProductBuilderAgent()
    product = agent.build_product_model()

    output_path = Path("outputs/json/product_model.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(product, indent=2), encoding="utf-8")

    print(json.dumps(product, indent=2))
    print(f"Saved to {output_path}")