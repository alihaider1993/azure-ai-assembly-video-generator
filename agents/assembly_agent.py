import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from services.foundry import FoundryClient


class AssemblyAgent:
    def __init__(self):
        self.ai = FoundryClient()

    def analyze_step(self, image_path: str):
        prompt = """
You are an Assembly Reasoning Agent for a generic Instruction Manual to Animated Video Generator.

Analyze this instruction manual page and identify the assembly step shown.

Return ONLY valid JSON:

{
  "page_type": "assembly_step",
  "step_numbers": [],
  "parts_used": [],
  "fasteners_used": [],
  "tools_required": [],
  "actions": [
    {
      "action": "",
      "motion_for_animation": "",
      "camera_angle": "",
      "highlight_area": "",
      "narration": ""
    }
  ],
  "warnings_or_cautions": [],
  "estimated_scene_duration_seconds": 8
}
"""
        return self.ai.vision(image_path=image_path, prompt=prompt)


if __name__ == "__main__":
    agent = AssemblyAgent()
    print(agent.analyze_step("temp/pages/page_5.png"))