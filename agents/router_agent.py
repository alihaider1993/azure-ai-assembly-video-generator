import sys
import json
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from agents.page_classifier_agent import PageClassifierAgent
from agents.parts_agent import PartsAgent
from agents.assembly_agent import AssemblyAgent


class RouterAgent:
    def __init__(self):
        self.classifier = PageClassifierAgent()
        self.parts_agent = PartsAgent()
        self.assembly_agent = AssemblyAgent()

    def process_page(self, image_path: str):
        classification_raw = self.classifier.classify_page(image_path)

        result = {
            "image_path": image_path,
            "classification_raw": classification_raw,
            "agent_output": None
        }

        if "parts_agent" in classification_raw:
            result["agent_output"] = self.parts_agent.extract_parts(image_path)

        elif "assembly_agent" in classification_raw:
            result["agent_output"] = self.assembly_agent.analyze_step(image_path)

        else:
            result["agent_output"] = "Page skipped or handled by manual/safety agent later."

        return result

    def process_manual(self, pages_dir: str, max_pages: int = 6):
        pages = sorted(
            Path(pages_dir).glob("page_*.png"),
            key=lambda p: int(p.stem.split("_")[1])
        )[:max_pages]

        outputs = []

        for page in pages:
            print(f"Processing {page}...")
            outputs.append(self.process_page(str(page)))

        return outputs


if __name__ == "__main__":
    router = RouterAgent()
    results = router.process_manual("temp/pages", max_pages=20)

    output_path = Path("outputs/router_results.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nSaved results to {output_path}")