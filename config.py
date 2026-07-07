from pathlib import Path

# ==========================================================
# PROJECT ROOT
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parent

# ==========================================================
# INPUTS
# ==========================================================

UPLOADS_DIR = PROJECT_ROOT / "uploads"
DEFAULT_MANUAL_PDF = UPLOADS_DIR / "manual.pdf"

# ==========================================================
# TEMP
# ==========================================================

TEMP_DIR = PROJECT_ROOT / "temp"
PAGE_IMAGES_DIR = TEMP_DIR / "pages"

# ==========================================================
# OUTPUTS
# ==========================================================

OUTPUTS_DIR = PROJECT_ROOT / "outputs"

FRAMES_V2_DIR = OUTPUTS_DIR / "frames_v2"
FRAMES_V3_DIR = OUTPUTS_DIR / "frames_v3"

VIDEO_V2_PATH = OUTPUTS_DIR / "assembly_animation_v2.mp4"
VIDEO_V3_PATH = OUTPUTS_DIR / "assembly_animation_v3.mp4"

# ==========================================================
# BLENDER
# ==========================================================

BLENDER_DIR = PROJECT_ROOT / "blender"

BLENDER_GENERATED_DIR = BLENDER_DIR / "generated"

BLENDER_V2_SCRIPT = BLENDER_GENERATED_DIR / "v2_generated_blender_scene.py"
BLENDER_V3_SCRIPT = BLENDER_GENERATED_DIR / "v3_generated_blender_scene.py"

# ==========================================================
# V2 OUTPUTS
# ==========================================================

V2_DIR = PROJECT_ROOT / "v2"

V2_JSON_DIR = V2_DIR / "outputs" / "json"

V2_OUTPUT_DIR = V2_DIR / "output"

# JSON Files

PAGE_STATES_JSON = V2_JSON_DIR / "page_states.json"

ASSEMBLY_DELTAS_JSON = V2_JSON_DIR / "assembly_deltas.json"

ASSEMBLY_ACTIONS_JSON = V2_JSON_DIR / "assembly_actions.json"

UNIVERSAL_GRAPH_JSON = V2_JSON_DIR / "universal_assembly_graph.json"

MOTION_PLAN_JSON = V2_JSON_DIR / "motion_plan.json"

SCENE_LAYOUT_JSON = V2_JSON_DIR / "scene_layout.json"

DIAGRAM_ANALYSIS_JSON = V2_JSON_DIR / "diagram_analysis.json"

GEOMETRY_SPEC_JSON = V2_JSON_DIR / "geometry_spec.json"

# Intermediate Files

PART_SHAPES_JSON = V2_OUTPUT_DIR / "part_shapes.json"

PROXY_GEOMETRY_JSON = V2_OUTPUT_DIR / "proxy_geometry.json"

DIAGRAM_ANALYSIS_COPY_JSON = V2_OUTPUT_DIR / "diagram_analysis.json"

SCENE_LAYOUT_COPY_JSON = V2_OUTPUT_DIR / "scene_layout.json"

# ==========================================================
# CREATE DIRECTORIES
# ==========================================================

def ensure_project_dirs():

    directories = [

        UPLOADS_DIR,

        TEMP_DIR,

        PAGE_IMAGES_DIR,

        OUTPUTS_DIR,

        FRAMES_V2_DIR,

        FRAMES_V3_DIR,

        BLENDER_GENERATED_DIR,

        V2_JSON_DIR,

        V2_OUTPUT_DIR,

    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)