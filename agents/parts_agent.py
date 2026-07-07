import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from services.foundry import FoundryClient


class PartsAgent:
    def __init__(self):
        self.ai = FoundryClient()

    def extract_parts(self, image_path: str):
        prompt = """
You are a Parts Extraction Agent for a generic Instruction Manual to Animated Video Generator.

Extract all visible parts, tools, fasteners, labels, codes, and quantities from this page.

Return ONLY valid JSON:

{
  "page_type": "parts_inventory",
  "parts": [
    {
      "label_or_code": "",
      "quantity": "",
      "visual_description": "",
      "likely_purpose": ""
    }
  ],
  "tools": [],
  "notes": []
}
"""
        return self.ai.vision(image_path=image_path, prompt=prompt)


if __name__ == "__main__":
    agent = PartsAgent()
    print(agent.extract_parts("temp/pages/page_3.png"))