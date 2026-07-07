import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from services.foundry import FoundryClient


if __name__ == "__main__":
    ai = FoundryClient()

    result = ai.vision(
        image_path="temp/pages/page_3.png",
        prompt="""
You are an AI Vision agent for an Instruction Manual to Animated Video Generator.

The uploaded document may be for:
- Furniture
- Electronics
- Appliances
- Toys
- Exercise equipment
- Industrial machinery
- Tools
- Consumer products

Your job is to understand the page exactly as a human assembly expert would.

Identify:
1. What type of page this is.
2. Every visible part, component, fastener or tool.
3. Any quantities shown.
4. Any assembly actions shown.
5. Camera movements suitable for animation.
6. Narration suitable for a professional assembly video.
7. Any warnings or notes.

Return ONLY valid JSON.

{
  "page_type": "",
  "manual_category": "",
  "parts": [
    {
      "label": "",
      "quantity": "",
      "description": "",
      "purpose": ""
    }
  ],
  "assembly_actions": [
    {
      "action": "",
      "parts": [],
      "tool": "",
      "camera": "",
      "animation": "",
      "narration": ""
    }
  ],
  "warnings": []
}
"""
    )

    print(result)