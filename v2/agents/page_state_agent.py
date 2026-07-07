import sys
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.append(str(Path(__file__).resolve().parents[2]))

from services.foundry import FoundryClient


OUTPUT_PATH = Path("v2/outputs/json/page_states.json")


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


def norm(value: Any) -> str:
    return str(value or "").strip().lower()


def ensure_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def make_aliases(item: Dict[str, Any], keys: List[str]) -> List[str]:
    aliases = []

    for key in keys:
        value = item.get(key)
        if value:
            aliases.append(norm(value))

    return list(set(a for a in aliases if a))


def remap_ref(ref: str, alias_map: Dict[str, str]) -> str:
    ref_n = norm(ref)

    if not ref_n:
        return ""

    return alias_map.get(ref_n, "")


def generate_stable_ids(state: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, int]]:
    page_number = int(state.get("page_number", 0))

    visible_parts = ensure_list(state.get("visible_parts"))
    visible_fasteners = ensure_list(state.get("visible_fasteners"))
    visible_tools = ensure_list(state.get("visible_tools"))
    observed_actions = ensure_list(state.get("observed_actions"))

    part_alias_map: Dict[str, str] = {}
    fastener_alias_map: Dict[str, str] = {}
    tool_alias_map: Dict[str, str] = {}

    for index, part in enumerate(visible_parts, start=1):
        old_uid = part.get("part_uid", "")
        stable_uid = f"P{page_number:03d}_{index:03d}"

        for alias in make_aliases(
            part,
            ["part_uid", "manual_label", "name", "visual_description"]
        ):
            part_alias_map[alias] = stable_uid

        if old_uid:
            part_alias_map[norm(old_uid)] = stable_uid

        part["part_uid"] = stable_uid
        part["quantity_visible"] = int(part.get("quantity_visible", 1) or 1)
        part["connection_features"] = ensure_list(part.get("connection_features"))
        part.setdefault("manual_label", "")
        part.setdefault("name", "")
        part.setdefault("visual_description", "")
        part.setdefault("shape_family", "unknown")
        part.setdefault("material_hint", "unknown")
        part.setdefault("page_position", "unknown")

    for index, fastener in enumerate(visible_fasteners, start=1):
        old_uid = fastener.get("fastener_uid", "")
        stable_uid = f"F{page_number:03d}_{index:03d}"

        for alias in make_aliases(
            fastener,
            ["fastener_uid", "manual_label", "name"]
        ):
            fastener_alias_map[alias] = stable_uid

        if old_uid:
            fastener_alias_map[norm(old_uid)] = stable_uid

        fastener["fastener_uid"] = stable_uid
        fastener["quantity_visible"] = int(fastener.get("quantity_visible", 1) or 1)
        fastener.setdefault("manual_label", "")
        fastener.setdefault("name", "")
        fastener.setdefault("shape_family", "unknown")

    for index, tool in enumerate(visible_tools, start=1):
        old_uid = tool.get("tool_uid", "")
        stable_uid = f"T{page_number:03d}_{index:03d}"

        for alias in make_aliases(tool, ["tool_uid", "name"]):
            tool_alias_map[alias] = stable_uid

        if old_uid:
            tool_alias_map[norm(old_uid)] = stable_uid

        tool["tool_uid"] = stable_uid
        tool.setdefault("name", "")

    unresolved_refs = 0

    for index, action in enumerate(observed_actions, start=1):
        action["action_uid"] = f"A{page_number:03d}_{index:03d}"
        action.setdefault("action_type", "unknown")
        action.setdefault("direction_hint", "unknown")
        action.setdefault("visual_evidence", "")

        moving = action.get("moving_part_ref", "")
        target = action.get("target_part_ref", "")
        fastener = action.get("fastener_ref", "")
        tool = action.get("tool_ref", "")

        action["moving_part_ref"] = remap_ref(moving, part_alias_map)
        action["target_part_ref"] = remap_ref(target, part_alias_map)
        action["fastener_ref"] = remap_ref(fastener, fastener_alias_map)
        action["tool_ref"] = remap_ref(tool, tool_alias_map)

        if moving and not action["moving_part_ref"]:
            unresolved_refs += 1

        if target and not action["target_part_ref"]:
            unresolved_refs += 1

        if fastener and not action["fastener_ref"]:
            unresolved_refs += 1

        if tool and not action["tool_ref"]:
            unresolved_refs += 1

    state["visible_parts"] = visible_parts
    state["visible_fasteners"] = visible_fasteners
    state["visible_tools"] = visible_tools
    state["observed_actions"] = observed_actions

    stats = {
        "unresolved_refs": unresolved_refs
    }

    return state, stats


def validate_page_state(state: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, int]]:
    required_keys = [
        "page_number",
        "page_type",
        "visible_parts",
        "visible_fasteners",
        "visible_tools",
        "observed_actions",
        "final_visible_structure",
        "uncertainties",
    ]

    for key in required_keys:
        if key not in state:
            if key in [
                "visible_parts",
                "visible_fasteners",
                "visible_tools",
                "observed_actions",
                "uncertainties",
            ]:
                state[key] = []
            elif key == "final_visible_structure":
                state[key] = ""
            else:
                state[key] = "unknown"

    state["visible_parts"] = ensure_list(state.get("visible_parts"))
    state["visible_fasteners"] = ensure_list(state.get("visible_fasteners"))
    state["visible_tools"] = ensure_list(state.get("visible_tools"))
    state["observed_actions"] = ensure_list(state.get("observed_actions"))
    state["uncertainties"] = ensure_list(state.get("uncertainties"))

    page_type = norm(state.get("page_type"))

    if page_type == "cover":
        state["visible_parts"] = []
        state["visible_fasteners"] = []
        state["visible_tools"] = []
        state["observed_actions"] = []

    if page_type == "warning":
        state["visible_parts"] = []
        state["visible_fasteners"] = []
        state["observed_actions"] = []

    if page_type == "parts_list":
        state["observed_actions"] = []

    state, stats = generate_stable_ids(state)

    if page_type == "assembly_step" and len(state.get("observed_actions", [])) == 0:
        state["uncertainties"].append(
            "Assembly step page has no observed_actions. Re-check page analysis."
        )

    if stats["unresolved_refs"] > 0:
        state["uncertainties"].append(
            f"{stats['unresolved_refs']} action reference(s) could not be resolved to visible objects on this page."
        )

    return state, stats


class PageStateAgent:
    def __init__(self):
        self.ai = FoundryClient()

    def analyze_page(self, image_path: str, page_number: int) -> Dict[str, Any]:
        prompt = f"""
You are a Page State Analyzer for a universal assembly manual video generator.

Analyze ONE manual page image and extract only what is visually observable.

Do NOT summarize the product.
Do NOT create a generic chair, table, wardrobe, cabinet, toy, appliance, or gym product.
Do NOT invent hidden parts.
Do NOT infer future steps.
Do NOT use product templates.

Image path:
{image_path}

IMPORTANT ID RULE:
Leave part_uid, fastener_uid, tool_uid, and action_uid as empty strings.
The Python system will generate stable IDs.
Use manual_label only for visible printed part numbers.
Do not use manual_label as identity.

REFERENCE RULE:
For every observed action, moving_part_ref and target_part_ref should refer to visible_parts on this same page.

If a target structure is visible but not labelled, you MUST still add it to visible_parts with:
- manual_label: ""
- name: a simple observable name such as "assembled frame", "seat frame", "side frame", "panel", "beam", "backrest"
- visual_description: what is visible
- shape_family: best observable shape

Then use that generated visible part as target_part_ref.

Do NOT leave target_part_ref empty if the target object is visible on the page.
Only leave it empty if the target object is truly not visible.


COVER PAGE RULE:
If this is a cover page, page_type must be "cover" and visible_parts must be empty.
You may describe the final product only in final_visible_structure.

PARTS LIST RULE:
If this page only shows inventory/hardware, page_type must be "parts_list" and observed_actions must be empty.

ASSEMBLY STEP RULE:
If this page is an assembly_step page, observed_actions MUST NOT be empty.
Look for arrows, hands, tools, screws, bolts, nuts, dowels, parts moving into holes, lowering, rotating, inserting, aligning, or tightening.

Return ONLY valid JSON in this exact schema:

{{
  "page_number": {page_number},
  "page_type": "cover | parts_list | assembly_step | warning | final_check | unknown",
  "visible_parts": [
    {{
      "part_uid": "",
      "manual_label": "",
      "name": "",
      "visual_description": "",
      "shape_family": "panel | beam | frame | curved | cylinder | bracket | hinge | wheel | cable | electronics | irregular | unknown",
      "material_hint": "wood | metal | plastic | fabric | rubber | mixed | unknown",
      "quantity_visible": 1,
      "connection_features": [
        {{
          "feature_type": "hole | slot | peg | hinge_point | screw_point | edge | connector | unknown",
          "count": 1,
          "location_hint": ""
        }}
      ],
      "page_position": "left | right | top | bottom | center | unknown"
    }}
  ],
  "visible_fasteners": [
    {{
      "fastener_uid": "",
      "manual_label": "",
      "name": "",
      "shape_family": "screw | bolt | nut | washer | dowel | bracket | unknown",
      "quantity_visible": 1
    }}
  ],
  "visible_tools": [
    {{
      "tool_uid": "",
      "name": ""
    }}
  ],
  "observed_actions": [
    {{
      "action_uid": "",
      "action_type": "place | align | insert | slide | rotate | tighten | flip | attach | lift | lower | warning | unknown",
      "moving_part_ref": "",
      "target_part_ref": "",
      "fastener_ref": "",
      "tool_ref": "",
      "direction_hint": "down | up | left | right | inward | outward | clockwise | counterclockwise | unknown",
      "visual_evidence": ""
    }}
  ],
  "final_visible_structure": "",
  "uncertainties": []
}}

Rules:
1. Extract only visible objects from this page.
2. Use printed part numbers only in manual_label.
3. If a referenced target is not visible, leave target_part_ref empty and add uncertainty.
4. If a tool is crossed out, include it in visible_tools and mention crossed out in name.
5. JSON only. No markdown.
"""

        raw = self.ai.vision(image_path=image_path, prompt=prompt)
        state = extract_json(raw)
        state, _ = validate_page_state(state)
        return state


def run_page_state_analysis(
    pages_dir: str = "temp/pages",
    output_path: Path = OUTPUT_PATH,
) -> List[Dict[str, Any]]:
    agent = PageStateAgent()

    pages = sorted(
        Path(pages_dir).glob("page_*.png"),
        key=lambda p: int(p.stem.split("_")[1])
    )

    if not pages:
        raise FileNotFoundError(f"No page images found in {pages_dir}")

    results = []
    total_unresolved_refs = 0

    for page in pages:
        page_number = int(page.stem.split("_")[1])
        print(f"V2 analyzing page {page_number}: {page}")

        try:
            result = agent.analyze_page(str(page), page_number)
            result, stats = validate_page_state(result)
            total_unresolved_refs += stats["unresolved_refs"]
            results.append(result)
        except Exception as e:
            print(f"ERROR analyzing page {page_number}: {e}")
            results.append({
                "page_number": page_number,
                "page_type": "unknown",
                "visible_parts": [],
                "visible_fasteners": [],
                "visible_tools": [],
                "observed_actions": [],
                "final_visible_structure": "",
                "uncertainties": [f"Page analysis failed: {str(e)}"]
            })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    assembly_pages = [p for p in results if p.get("page_type") == "assembly_step"]
    empty_action_pages = [
        p.get("page_number")
        for p in assembly_pages
        if len(p.get("observed_actions", [])) == 0
    ]

    print(f"Saved V2 page states to {output_path}")
    print(f"Pages analyzed: {len(results)}")
    print(f"Assembly pages: {len(assembly_pages)}")
    print(f"Assembly pages with empty actions: {empty_action_pages}")
    print(f"Unresolved action references: {total_unresolved_refs}")

    return results


if __name__ == "__main__":
    run_page_state_analysis()