import sys
import json
import re
from pathlib import Path
from typing import Any, Dict, List

sys.path.append(str(Path(__file__).resolve().parents[2]))

from services.foundry import FoundryClient, FoundryConfigError


PAGES_DIR = Path("temp/pages")
OUTPUT_PATH = Path("v2/outputs/json/diagram_analysis.json")


class DiagramAnalysisError(RuntimeError):
    """Every page failed, so the output would be empty."""


def extract_json(text: str) -> Dict[str, Any]:
    text = text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```json", "", text)
        text = re.sub(r"^```", "", text)
        text = re.sub(r"```$", "", text).strip()

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model response.")

    return json.loads(text[start:end + 1])


class DiagramAnalyzerAgent:
    def __init__(self) -> None:
        self.ai = FoundryClient()

    def analyze_page(self, image_path: str, page_number: int) -> Dict[str, Any]:
        prompt = f"""
You are a Diagram Analyzer for a universal assembly manual video generator.

Analyze ONE manual page image.

Your task is NOT to identify the product.
Your task is to detect visual diagrams on the page.

Extract:
- part diagrams
- exploded views
- assembly step diagrams
- close-up diagrams
- warning diagrams
- final product diagrams

Do NOT invent geometry.
Do NOT describe hidden parts.
Only describe visible diagram regions.

Image path:
{image_path}

Return ONLY valid JSON in this exact schema:

{{
  "page_number": {page_number},
  "page_type": "cover | parts_list | assembly_step | warning | final_check | unknown",
  "diagrams": [
    {{
      "diagram_uid": "",
      "diagram_type": "part_inventory | exploded_view | assembly_view | close_up | warning | final_product | unknown",
      "description": "",
      "page_region": {{
        "x_min": 0.0,
        "y_min": 0.0,
        "x_max": 1.0,
        "y_max": 1.0
      }},
      "contains_parts": true,
      "contains_fasteners": false,
      "contains_tools": false,
      "contains_arrows": false,
      "contains_labels": false,
      "visible_labels": [],
      "likely_action": "place | align | insert | slide | rotate | tighten | flip | attach | lower | warning | none | unknown",
      "visual_complexity": "low | medium | high",
      "confidence": 0.0
    }}
  ],
  "primary_assembly_diagram": "",
  "warnings": [],
  "uncertainties": []
}}

Rules:
1. Coordinates must be normalized between 0 and 1.
2. page_region is approximate bounding box of the diagram on the page.
3. If page has multiple step illustrations, return multiple diagrams.
4. If page is parts inventory, identify individual inventory regions if visible.
5. If no diagram is visible, diagrams should be empty.
6. JSON only. No markdown.
"""

        raw = self.ai.vision(image_path=image_path, prompt=prompt)
        data = extract_json(raw)
        # The page number comes from the file name; the model's value is not trusted.
        data["page_number"] = page_number
        return self.validate(data, page_number)

    def validate(self, data: Dict[str, Any], page_number: int) -> Dict[str, Any]:
        data.setdefault("page_number", page_number)
        data.setdefault("page_type", "unknown")
        data.setdefault("diagrams", [])
        data.setdefault("primary_assembly_diagram", "")
        data.setdefault("warnings", [])
        data.setdefault("uncertainties", [])

        validated_diagrams = []
        diagrams = data.get("diagrams")
        diagrams = [d for d in diagrams if isinstance(d, dict)] if isinstance(diagrams, list) else []

        for idx, diagram in enumerate(diagrams, start=1):
            diagram.setdefault("diagram_uid", "")
            diagram["diagram_uid"] = f"D{page_number:03d}_{idx:03d}"

            diagram.setdefault("diagram_type", "unknown")
            diagram.setdefault("description", "")
            diagram.setdefault("page_region", {
                "x_min": 0.0,
                "y_min": 0.0,
                "x_max": 1.0,
                "y_max": 1.0
            })

            region = diagram["page_region"]

            if not isinstance(region, dict):
                region = {}

            for key, default in [("x_min", 0.0), ("y_min", 0.0), ("x_max", 1.0), ("y_max", 1.0)]:
                try:
                    region[key] = max(0.0, min(1.0, float(region.get(key, default))))
                except (TypeError, ValueError):
                    region[key] = default

            diagram["page_region"] = region

            diagram.setdefault("contains_parts", False)
            diagram.setdefault("contains_fasteners", False)
            diagram.setdefault("contains_tools", False)
            diagram.setdefault("contains_arrows", False)
            diagram.setdefault("contains_labels", False)
            if not isinstance(diagram.get("visible_labels"), list):
                diagram["visible_labels"] = []
            diagram.setdefault("likely_action", "unknown")
            diagram.setdefault("visual_complexity", "medium")
            diagram.setdefault("confidence", 0.5)

            validated_diagrams.append(diagram)

        data["diagrams"] = validated_diagrams

        if not data["primary_assembly_diagram"]:
            for diagram in data["diagrams"]:
                if diagram.get("diagram_type") in ["assembly_view", "exploded_view"]:
                    data["primary_assembly_diagram"] = diagram["diagram_uid"]
                    break

        return data


def run_diagram_analysis(
    pages_dir: Path = PAGES_DIR,
    output_path: Path = OUTPUT_PATH
) -> List[Dict[str, Any]]:
    agent = DiagramAnalyzerAgent()

    pages = sorted(
        pages_dir.glob("page_*.png"),
        key=lambda p: int(p.stem.split("_")[1])
    )

    if not pages:
        raise FileNotFoundError(f"No page images found in {pages_dir}")

    results = []
    failed_pages: List[int] = []

    for page in pages:
        page_number = int(page.stem.split("_")[1])
        print(f"Analyzing diagrams on page {page_number}: {page}")

        try:
            result = agent.analyze_page(str(page), page_number)
            results.append(result)
        except FoundryConfigError:
            raise
        except Exception as e:
            print(f"ERROR on page {page_number}: {e}")
            failed_pages.append(page_number)
            results.append({
                "page_number": page_number,
                "page_type": "unknown",
                "diagrams": [],
                "primary_assembly_diagram": "",
                "warnings": [],
                "uncertainties": [str(e)]
            })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    total_diagrams = sum(len(p.get("diagrams", [])) for p in results)
    assembly_diagrams = sum(
        1
        for p in results
        for d in p.get("diagrams", [])
        if d.get("diagram_type") in ["assembly_view", "exploded_view"]
    )

    print()
    print("Diagram Analyzer Summary")
    print("------------------------")
    print(f"Pages analyzed: {len(results)}")
    print(f"Total diagrams: {total_diagrams}")
    print(f"Assembly diagrams: {assembly_diagrams}")
    print(f"Saved to: {output_path}")

    if len(failed_pages) == len(results):
        raise DiagramAnalysisError(
            f"Every page failed diagram analysis (pages {failed_pages}). "
            "See the ERROR lines above."
        )

    return results


if __name__ == "__main__":
    try:
        run_diagram_analysis()
    except (FoundryConfigError, DiagramAnalysisError) as e:
        print("", file=sys.stderr)
        print(f"[FATAL] Diagram analysis stopped: {e}", file=sys.stderr)
        sys.exit(2)
