import sys
import json
import re
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from services.foundry import FoundryClient


def extract_json(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```json", "", text)
        text = re.sub(r"^```", "", text)
        text = re.sub(r"```$", "", text).strip()
    return json.loads(text)


class ManualScenePlannerAgent:
    def __init__(self):
        self.ai = FoundryClient()

    def build_scene_plan(self):
        router_path = Path("outputs/router_results.json")
        product_path = Path("outputs/json/product_model.json")
        graph_path = Path("outputs/json/assembly_graph.json")

        if not router_path.exists():
            raise FileNotFoundError("outputs/router_results.json not found")

        if not product_path.exists():
            raise FileNotFoundError("outputs/json/product_model.json not found")

        if not graph_path.exists():
            raise FileNotFoundError("outputs/json/assembly_graph.json not found")

        router_results = router_path.read_text(encoding="utf-8")
        product_model = product_path.read_text(encoding="utf-8")
        assembly_graph = graph_path.read_text(encoding="utf-8")

        prompt = f"""
You are a Manual Scene Planner Agent.

Your job is to create a manual-specific animation plan from the uploaded DIY instruction manual.

Do NOT create a generic table or chair animation.
Use the actual manual analysis, product model, and assembly graph.

Input 1: Router/page analysis:
{router_results}

Input 2: Product model:
{product_model}

Input 3: Assembly graph:
{assembly_graph}

Return ONLY valid JSON:

{{
  "product_type": "",
  "product_name": "",
  "scenes": [
    {{
      "scene_number": 1,
      "manual_page": "",
      "title": "",
      "active_parts": [],
      "active_fasteners": [],
      "action": "",
      "motion": "",
      "camera": "isometric",
      "narration": "",
      "notes": []
    }}
  ]
}}

Rules:
- Follow the actual page/order of the manual.
- Each scene should represent one real instruction step.
- Use part names from the product model or router analysis.
- Use fasteners from the product model when relevant.
- Keep 4 to 8 scenes maximum.
- Make the plan suitable for Blender animation.
- Return JSON only.
"""

        raw = self.ai.chat(prompt)
        return extract_json(raw)


if __name__ == "__main__":
    agent = ManualScenePlannerAgent()
    plan = agent.build_scene_plan()

    output_path = Path("outputs/json/manual_scene_plan.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")

    print(json.dumps(plan, indent=2))
    print(f"Saved to {output_path}")