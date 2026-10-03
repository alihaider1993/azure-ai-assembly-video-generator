"""
Part Shape Extractor — v2

Fixes vs. the original version:
1. Parts are now keyed by canonical IDs (OBJ0001, FAST0001, ...) from
   universal_assembly_graph.json, instead of page/diagram IDs
   (e.g. "P_PAGE3_D003_001") that never matched anything downstream.
   This was the root cause of proxy geometry never being found by
   blender_builder_v3.py.
2. Shape family comes directly from the graph's already-correct
   "shape_family" field, instead of re-guessing from diagram description
   text (which was misclassifying wooden side rails as cylinders).
3. Hole counts come from the graph's structured "connection_features"
   (count field), instead of a broken "4x" in labels string check that
   never matched the real "x4" label format.
4. Real millimeter dimensions are parsed from diagram_analysis.json
   part-list descriptions (e.g. "(310 x 60mm)") and from fastener names
   (e.g. "M6x50mm Bolt"), instead of using fixed per-shape-type buckets.

Assembly nodes (ASM0001) are intentionally NOT given proxy geometry here;
blender_builder_v3.py already has a sensible built-in fallback box for
node_type == "assembly", and this stage has no reliable size data for
"the whole product" as a single shape.
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from config import (
    UNIVERSAL_GRAPH_JSON,
    DIAGRAM_ANALYSIS_JSON,
    DIAGRAM_ANALYSIS_COPY_JSON,
    PART_SHAPES_JSON,
)


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def norm(value: Any) -> str:
    return str(value or "").strip().lower()


def to_int(value: Any, default: int = 1) -> int:
    """Parse counts that may arrive as 4, "4", "4x" or "x4"."""
    match = re.search(r"\d+", str(value or ""))
    return int(match.group()) if match else default


# ---------------------------------------------------------------------
# Real dimensions from the manual, instead of hardcoded buckets
# ---------------------------------------------------------------------

MM_PAIR_RE = re.compile(r"\((\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*mm\)", re.IGNORECASE)
FASTENER_M_RE = re.compile(r"m(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*mm", re.IGNORECASE)
FASTENER_LEN_RE = re.compile(r"(\d+(?:\.\d+)?)\s*mm", re.IGNORECASE)


def load_diagram_analysis() -> List[Dict[str, Any]]:
    """Prefer the authoritative outputs/json copy; fall back to the
    legacy v2/output/ mirror if that's the only one present."""
    if DIAGRAM_ANALYSIS_JSON.exists():
        return load_json(DIAGRAM_ANALYSIS_JSON)
    if DIAGRAM_ANALYSIS_COPY_JSON.exists():
        return load_json(DIAGRAM_ANALYSIS_COPY_JSON)
    return []


def build_label_dimensions_mm(diagram_analysis: List[Dict[str, Any]]) -> Dict[str, Tuple[float, float]]:
    """Map a manual numeric label (e.g. "1") to (dim1_mm, dim2_mm)
    parsed from part-list diagram descriptions like
    "Left/Right Side Rail (310 x 60mm) x4"."""
    label_dims: Dict[str, Tuple[float, float]] = {}

    for page in diagram_analysis:
        for diagram in page.get("diagrams", []):
            if not diagram.get("contains_parts"):
                continue

            description = diagram.get("description", "")
            match = MM_PAIR_RE.search(description)
            if not match:
                continue

            labels = diagram.get("visible_labels", [])
            numeric_label = next((l for l in labels if str(l).strip().isdigit()), None)
            if not numeric_label:
                continue

            label_dims[str(numeric_label).strip()] = (
                float(match.group(1)),
                float(match.group(2)),
            )

    return label_dims


def parse_fastener_dimensions_m(name: str) -> Tuple[float, float]:
    """Return (diameter_m, length_m) for a fastener, parsed from its name."""
    m = FASTENER_M_RE.search(name)
    if m:
        diameter_mm = float(m.group(1))
        length_mm = float(m.group(2))
        return diameter_mm / 1000.0, length_mm / 1000.0

    m2 = FASTENER_LEN_RE.search(name)
    length_mm = float(m2.group(1)) if m2 else 30.0

    name_l = name.lower()
    if "dowel" in name_l:
        diameter_mm = 8.0
    elif "screw" in name_l:
        diameter_mm = 4.0
    elif "washer" in name_l or "nut" in name_l:
        diameter_mm = 16.0
        length_mm = 3.0  # washers are effectively flat discs
    else:
        diameter_mm = 6.0

    return diameter_mm / 1000.0, length_mm / 1000.0


# ---------------------------------------------------------------------
# Shape family -> primitive the Blender builder actually understands
# (blender_builder_v3.py only special-cases "cylinder" and
# "rounded_box"/shape_type "rounded_panel"; everything else falls
# through to a plain box, so we target those three deliberately)
# ---------------------------------------------------------------------

def primitive_and_shape_type(shape_family: str, material_hint: str) -> Tuple[str, str]:
    shape = norm(shape_family)
    material = norm(material_hint)

    if shape in {"cylinder", "dowel", "bolt", "screw"}:
        return "cylinder", "cylinder"

    if shape in {"washer", "nut"}:
        return "cylinder", "washer"

    if shape == "panel" and material == "fabric":
        return "rounded_box", "rounded_panel"

    if shape in {"frame", "beam"}:
        return "box", "rectangular_beam"

    if shape == "panel":
        return "box", "thin_plate"

    if shape == "curved":
        return "box", "curved_frame"  # true curve primitive not yet supported by the renderer

    if shape == "bracket":
        return "box", "bracket"

    return "box", "proxy_block"


# Generic furniture vocabulary -> the part's role, which fixes how it sits in
# the finished piece, and a plausible [x, y, z] size in meters (z is up) for
# when the manual gives no measurement.
PART_ROLES = [
    ("top", re.compile(r"\b(table ?top|top panel|worktop|desktop)\b"), [1.2, 0.75, 0.025]),
    # Not "leg frame": on chairs that is a wide U-shaped frame, not a post.
    ("leg", re.compile(r"\blegs?\b(?!\s*frame)"), [0.05, 0.05, 0.72]),
    ("rail", re.compile(r"\b(rails?|aprons?|stretchers?)\b"), [0.9, 0.03, 0.07]),
    ("bracket", re.compile(r"\bbrackets?\b"), [0.08, 0.08, 0.04]),
]


def part_role(name: str) -> str:
    name_n = norm(name)
    for role, pattern, _ in PART_ROLES:
        if pattern.search(name_n):
            return role
    return ""


def role_dimensions(role: str, dims_mm: Optional[Tuple[float, float]]) -> List[float]:
    """[x, y, z] in meters for a part with a known role. A measured pair is
    oriented by role: a top lies flat, a leg stands up, a rail runs
    horizontally along X with its smaller figure as its height."""
    default = next(dims for r, _, dims in PART_ROLES if r == role)
    # A bracket's measured pair doesn't say which faces it covers.
    if not dims_mm or role == "bracket":
        return list(default)

    larger = max(dims_mm) / 1000.0
    smaller = min(dims_mm) / 1000.0

    if role == "top":
        return [larger, smaller, default[2]]
    if role == "leg":
        return [smaller, smaller, larger]
    return [larger, default[1], smaller]


DEFAULT_THICKNESS_M = {
    "thin_plate": 0.018,     # side-rail-style flat panel, typical board thickness
    "rectangular_beam": 0.09,
    "curved_frame": 0.09,
    "bracket": 0.05,
    "rounded_panel": 0.06,
    "proxy_block": 0.08,
}


def dimensions_for_part(
    shape_family: str,
    material_hint: str,
    dims_mm: Optional[Tuple[float, float]],
) -> List[float]:
    """
    Returns [x, y, z] in meters. Axis assignment is a heuristic:
    manuals mix side-view, front-view, and top-view dimension pairs
    with no explicit axis labels, so this maps the larger figure to
    "height" for upright parts (frames/curved/panels) and to "width"
    for flat parts (fabric panels), and uses a shape-based default
    thickness for the un-stated third axis. This is a proxy, not a
    CAD-accurate reconstruction — flagged as a known limitation.
    """
    _, shape_type = primitive_and_shape_type(shape_family, material_hint)
    thickness = DEFAULT_THICKNESS_M.get(shape_type, 0.08)

    if not dims_mm:
        # No manual measurement found — reasonable generic fallback per type
        fallback = {
            "thin_plate": [0.31, thickness, 0.06],
            "rectangular_beam": [0.42, thickness, 0.43],
            "curved_frame": [0.40, thickness, 0.90],
            "bracket": [0.05, 0.03, 0.04],
            "rounded_panel": [0.45, thickness, 0.36],
            "cylinder": [0.02, 0.02, 0.10],
            "washer": [0.02, 0.02, 0.004],
            "proxy_block": [0.5, thickness, 0.3],
        }
        return fallback.get(shape_type, [0.5, thickness, 0.3])

    a_m, b_m = dims_mm[0] / 1000.0, dims_mm[1] / 1000.0
    larger, smaller = max(a_m, b_m), min(a_m, b_m)

    if shape_type == "rounded_panel":
        # Flat cushion/seat: larger figure is width, smaller is depth
        return [larger, thickness, smaller]

    # Upright structural parts: larger figure is height
    return [smaller, thickness, larger]


# Four holes described as being at the corners sit just in from each corner.
CORNER_HOLE_POSITIONS = [(0.06, 0.08), (0.94, 0.08), (0.06, 0.92), (0.94, 0.92)]


def edge_position(i: int, count: int) -> List[float]:
    """i-th of `count` points spread evenly around the corner-hole inset
    rectangle, so a top's holes follow its edges where the frame sits."""
    (x0, y0), (x1, y1) = CORNER_HOLE_POSITIONS[0], CORNER_HOLE_POSITIONS[3]
    w, h = x1 - x0, y1 - y0
    d = (i + 0.5) / count * 2 * (w + h)
    if d < w:
        return [round(x0 + d, 4), y0]
    d -= w
    if d < h:
        return [x1, round(y0 + d, 4)]
    d -= h
    if d < w:
        return [round(x1 - d, 4), y1]
    return [x0, round(y1 - (d - w), 4)]


def build_holes_from_features(
    connection_features: List[Dict[str, Any]],
    around_edge: bool = False,
) -> List[Dict[str, Any]]:
    """Use the graph's already-correct structured hole/slot counts,
    instead of re-deriving (incorrectly) from label text."""
    holes = []
    hole_index = 1

    for feature in connection_features or []:
        if not isinstance(feature, dict) or norm(feature.get("feature_type")) != "hole":
            continue

        count = to_int(feature.get("count"))
        at_corners = count == 4 and "corner" in norm(feature.get("location_hint"))

        for i in range(count):
            if at_corners:
                position = [CORNER_HOLE_POSITIONS[i][0], CORNER_HOLE_POSITIONS[i][1]]
            elif around_edge:
                position = edge_position(i, count)
            else:
                # Spread evenly along the part so positions stay inside 0..1
                # for any count (the old 2-column grid overflowed past 4 holes).
                position = [round((i + 0.5) / count, 4), 0.5]
            holes.append({
                "hole_uid": f"H{hole_index}",
                "type": "round",
                "relative_position": position,
                "radius_hint": 0.006,
                "location_hint": feature.get("location_hint", ""),
            })
            hole_index += 1

    return holes


def aspect_ratio(dimensions: List[float]) -> float:
    """Longest side over shortest side of the proxy box."""
    shortest = min(dimensions)
    return round(max(dimensions) / shortest, 3) if shortest > 0 else 1.0


# ---------------------------------------------------------------------
# Main extraction
# ---------------------------------------------------------------------

def extract_part_shapes():
    graph = load_json(UNIVERSAL_GRAPH_JSON)
    diagram_analysis = load_diagram_analysis()

    label_dims_mm = build_label_dimensions_mm(diagram_analysis)

    part_shapes = {
        "metadata": {
            "created_at": datetime.utcnow().isoformat(),
            "source": "universal_assembly_graph.json + diagram_analysis.json",
            "note": "Canonical-ID-keyed proxy shape extraction for MVP rendering",
        },
        "parts": [],
    }

    # --- Real parts (OBJ*) ---
    for part in graph.get("parts", []):
        part_uid = part.get("part_uid")
        if not part_uid:
            continue

        shape_family = part.get("shape_family", "unknown")
        material_hint = part.get("material_hint", "unknown")

        manual_label = ""
        labels = part.get("manual_labels", [])
        if labels:
            manual_label = str(labels[0]).strip()

        dims_mm = label_dims_mm.get(manual_label)
        primitive, shape_type = primitive_and_shape_type(shape_family, material_hint)
        role = part_role(part.get("base_name") or part.get("canonical_name", ""))
        if role:
            dimensions = role_dimensions(role, dims_mm)
        else:
            dimensions = dimensions_for_part(shape_family, material_hint, dims_mm)

        if dims_mm:
            dims_source = "manual_measurement"
        elif role:
            dims_source = "name_hint_default"
        else:
            dims_source = "fallback_default"

        part_shapes["parts"].append({
            "part_uid": part_uid,  # canonical: OBJ0001, etc.
            "canonical_name": part.get("canonical_name", part_uid),
            "shape_family": shape_family,
            "material_hint": material_hint,
            "shape_type": shape_type,
            "primitive": primitive,
            "role": role,
            "dimensions": dimensions,
            "dims_source": dims_source,
            "aspect_ratio": aspect_ratio(dimensions),
            "source_page": part.get("first_seen_page"),
            "source_diagram_uid": "",
            "has_rounded_corners": shape_type == "rounded_panel",
            "holes": build_holes_from_features(part.get("connection_features", []), around_edge=role == "top"),
            "anchor_points": [
                {"anchor_uid": "A_TOP", "relative_position": [0.5, 0.0]},
                {"anchor_uid": "A_CENTER", "relative_position": [0.5, 0.5]},
                {"anchor_uid": "A_BOTTOM", "relative_position": [0.5, 1.0]},
            ],
            "labels": labels,
            "confidence": part.get("confidence", 0.7),
        })

    # --- Fasteners (FAST*) ---
    for fastener in graph.get("fasteners", []):
        fastener_uid = fastener.get("fastener_uid")
        if not fastener_uid:
            continue

        name = fastener.get("name", "")
        shape_family = fastener.get("shape_family", "cylinder")

        if shape_family in {"irregular"}:
            # e.g. Allen key — small tool, not a fastener geometry
            dimensions = [0.01, 0.01, 0.15]
            primitive, shape_type = "cylinder", "cylinder"
            dims_source = "fallback_default"
        else:
            primitive, shape_type = primitive_and_shape_type(shape_family, "metal")

            if primitive == "cylinder":
                diameter_m, length_m = parse_fastener_dimensions_m(name)
                dimensions = [diameter_m, diameter_m, length_m]
                dims_source = "parsed_from_name"
            else:
                # e.g. a bracket listed with the hardware: a thin rod is wrong.
                dimensions = dimensions_for_part(shape_family, "metal", None)
                dims_source = "fallback_default"

        part_shapes["parts"].append({
            "part_uid": fastener_uid,  # canonical: FAST0001, etc.
            "canonical_name": name,
            "shape_family": shape_family,
            "material_hint": "metal",
            "shape_type": shape_type,
            "primitive": primitive,
            "dimensions": dimensions,
            "dims_source": dims_source,
            "aspect_ratio": aspect_ratio(dimensions),
            "source_page": fastener.get("first_seen_page"),
            "source_diagram_uid": "",
            "has_rounded_corners": False,
            "holes": [],
            "anchor_points": [],
            "labels": fastener.get("manual_labels", []),
            "confidence": 0.8,
        })

    PART_SHAPES_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(PART_SHAPES_JSON, "w", encoding="utf-8") as f:
        json.dump(part_shapes, f, indent=2)

    if not part_shapes["parts"]:
        print(
            f"[FATAL] No parts or fasteners in {UNIVERSAL_GRAPH_JSON}; "
            "nothing to build shapes for. Check the earlier stages' output.",
            file=sys.stderr,
        )
        sys.exit(2)

    print("[SUCCESS] Part Shape Extractor complete")
    print(f"Parts extracted: {len(part_shapes['parts'])}")
    print(f"Output: {PART_SHAPES_JSON}")


if __name__ == "__main__":
    extract_part_shapes()