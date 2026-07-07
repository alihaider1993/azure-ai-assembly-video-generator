import sys
import json
import re
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from services.foundry import FoundryClient
from models.scene_graph import SceneGraph


def extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```json", "", text)
        text = re.sub(r"^```", "", text)
        text = re.sub(r"```$", "", text).strip()
    return json.loads(text)


class SceneGraphAgent:
    def __init__(self):
        self.ai = FoundryClient()

    def generate_scene_graph(self, assembly_agent_output: str) -> SceneGraph:
        prompt = f"""
You are a Scene Graph Agent for a GENERIC DIY Instruction Manual to Animated Video Generator.

The uploaded manual may be for:
- table
- chair
- sofa
- shelf
- cabinet
- bed
- desk
- drawer unit
- TV stand
- appliance
- toy
- gym equipment
- electronics
- generic DIY product

Your job:
1. Infer the product type from the assembly analysis.
2. Create a simplified but relevant 3D animation scene.
3. Use generic geometry that visually matches the product.
4. Do NOT hardcode only table geometry.
5. The scene must look relevant to the detected product.

Use these product templates:

TABLE:
- tabletop = large flat cuboid
- 4 legs = tall cuboids
- rails/aprons = long thin cuboids
- screws/bolts = cylinders

CHAIR:
- seat = flat cuboid
- backrest = vertical cuboid
- 4 legs = tall cuboids
- side supports = thin cuboids
- screws/bolts = cylinders

SOFA:
- base frame = wide cuboid
- arms = two side cuboids
- back panel = vertical cuboid
- cushions = soft rounded cuboid approximation
- legs = short cuboids/cylinders

SHELF / BOOKCASE:
- two side panels = vertical cuboids
- shelves = horizontal flat cuboids
- back panel = thin vertical cuboid
- dowels/screws = cylinders

CABINET / DRAWER:
- side panels, top, bottom = cuboids
- doors/drawers = front cuboids
- hinges/handles = small cuboids/cylinders
- screws = cylinders

BED:
- headboard = large vertical cuboid
- footboard = vertical cuboid
- side rails = long cuboids
- slats = repeated thin cuboids
- legs = cuboids/cylinders

APPLIANCE / ELECTRONICS:
- main body = cuboid
- panel/door/tray = smaller cuboid
- buttons/ports = small cuboids/cylinders
- screws/clips = cylinders

GENERIC DIY:
- panels = cuboids
- rods/tubes = cylinders
- brackets = small cuboids
- fasteners = cylinders

Geometry rules:
- panel/board/base/seat/backrest/shelf/door = cuboid
- rod/tube/screw/bolt/dowel = cylinder
- cushion/pad = cuboid with larger soft-looking proportions
- bracket/hinge/plate = small cuboid
- wheel/knob = cylinder

Animation rules:
- Moving parts must start away from the final product and move into place.
- Screws/bolts/dowels should rotate 360 degrees while moving into position.
- Legs/posts should slide or rise into their connection points.
- Panels should slide into alignment.
- Backrests/doors should rotate or slide into place where relevant.
- Use at least 5 objects where possible so the animation is visually meaningful.
- Keep dimensions visually proportional, not exact.
- Use simple coordinates.

Assembly analysis:
{assembly_agent_output}

Return ONLY valid JSON matching this schema:

{{
  "scene_number": 1,
  "title": "",
  "manual_category": "",
  "duration_seconds": 8,
  "objects": [
    {{
      "object_id": "",
      "name": "",
      "shape": "cuboid",
      "dimensions": {{
        "length": 1,
        "width": 1,
        "height": 1,
        "unit": "generic"
      }},
      "start_position": {{
        "x": 0,
        "y": 0,
        "z": 0
      }},
      "end_position": {{
        "x": 0,
        "y": 0,
        "z": 0
      }},
      "rotation": {{
        "axis": "z",
        "degrees": 0
      }}
    }}
  ],
  "camera": {{
    "angle": "isometric",
    "zoom": 1.2,
    "focus_object": ""
  }},
  "narration": "",
  "warnings": []
}}

Return valid JSON only. Do not include markdown.
"""
        raw = self.ai.chat(prompt)
        data = extract_json(raw)
        return SceneGraph(**data)


if __name__ == "__main__":
    router_results_path = Path("outputs/router_results.json")

    if router_results_path.exists():
        router_results = json.loads(router_results_path.read_text(encoding="utf-8"))

        assembly_outputs = [
            item["agent_output"]
            for item in router_results
            if item.get("agent_output") and "assembly_step" in item["agent_output"]
        ]

        if not assembly_outputs:
            raise ValueError("No assembly step found in outputs/router_results.json")

        assembly_input = assembly_outputs[0]
    else:
        assembly_input = """
{
  "page_type": "assembly_step",
  "step_numbers": [1],
  "parts_used": ["panel", "legs", "screws"],
  "fasteners_used": ["screws"],
  "tools_required": ["screwdriver"],
  "actions": [
    {
      "action": "Attach structural parts together using screws.",
      "motion_for_animation": "Main parts slide into alignment and screws rotate into place.",
      "camera_angle": "Isometric view",
      "highlight_area": "Connection points",
      "narration": "Align the parts and secure them using the supplied screws."
    }
  ],
  "warnings_or_cautions": ["Do not overtighten."]
}
"""

    agent = SceneGraphAgent()
    scene = agent.generate_scene_graph(assembly_input)

    output_path = Path("outputs/json/scene_graph.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(scene.model_dump_json(indent=2), encoding="utf-8")

    print(scene.model_dump_json(indent=2))
    print(f"Saved to {output_path}")