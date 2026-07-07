import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from services.foundry import FoundryClient


class PageClassifierAgent:
    def __init__(self):
        self.ai = FoundryClient()

    def classify_page(self, image_path: str):
        prompt = """
You are a Page Classifier Agent for an Instruction Manual to Animated Video Generator.

Classify this manual page into ONE page type:

- cover_page
- parts_inventory
- tools_required
- safety_warning
- assembly_step
- final_check
- unknown

Return ONLY valid JSON:

{
  "page_type": "",
  "confidence": 0.0,
  "reason": "",
  "detected_product_type": "",
  "recommended_next_agent": ""
}

For recommended_next_agent, choose one:
- parts_agent
- assembly_agent
- safety_agent
- manual_agent
- ignore
"""
        return self.ai.vision(image_path=image_path, prompt=prompt)


if __name__ == "__main__":
    agent = PageClassifierAgent()

    for page in [
        "temp/pages/page_1.png",
        "temp/pages/page_3.png",
        "temp/pages/page_5.png"
    ]:
        print("\n---", page, "---")
        print(agent.classify_page(page))