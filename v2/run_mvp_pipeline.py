"""Run the full v2 MVP pipeline: manual pages -> JSON stages -> Blender -> MP4.

Usage (from the repo root):
    python v2/run_mvp_pipeline.py
    python v2/run_mvp_pipeline.py --vision-fixture [DIR]

--vision-fixture skips the two Azure OpenAI vision stages and copies
page_states.json and diagram_analysis.json from DIR instead (default:
v2/tests/fixtures/vision, the hand-authored IKEA MELLTORP fixture). Use it
to exercise every downstream stage without Azure access.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Union

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config import (
    FRAMES_V3_DIR,
    VIDEO_V3_PATH,
    BLENDER_V3_SCRIPT,
    V2_JSON_DIR,
    V2_OUTPUT_DIR,
    PAGE_STATES_JSON,
    DIAGRAM_ANALYSIS_JSON,
    DIAGRAM_ANALYSIS_COPY_JSON,
    SCENE_LAYOUT_JSON,
    SCENE_LAYOUT_COPY_JSON,
    ensure_project_dirs,
)

load_dotenv(PROJECT_ROOT / ".env")

BLENDER_EXE = os.environ.get(
    "BLENDER_EXE",
    r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe",
)

DEFAULT_VISION_FIXTURE_DIR = PROJECT_ROOT / "v2" / "tests" / "fixtures" / "vision"

PAGE_STATE_COMMAND = [sys.executable, "v2/agents/page_state_agent.py"]
DIAGRAM_ANALYZER_COMMAND = [sys.executable, "v2/agents/diagram_analyzer_agent.py"]


class CopyStep:
    """In-process file copy, so the pipeline does not need PowerShell."""

    def __init__(self, source: Path, destination: Path):
        self.source = source
        self.destination = destination

    def __str__(self) -> str:
        return f"copy {self.source} -> {self.destination}"


Step = Union[List[str], CopyStep]


COMMANDS: List[Step] = [
    PAGE_STATE_COMMAND,
    [sys.executable, "v2/rendering/state_difference_engine.py"],
    [sys.executable, "v2/rendering/assembly_action_extractor.py"],

    # --- PASS 1: initial graph from raw page/action data. ---
    [sys.executable, "v2/rendering/universal_graph_engine.py"],

    [sys.executable, "v2/agents/object_identity_tracker.py"],

    [sys.executable, "v2/rendering/canonical_resolver.py"],

    # Expand resolved actions across sibling instances (4 rails, 2 legs,
    # 2 seat pads, 2 backs) BEFORE the graph is rebuilt, so the graph's
    # connections — and everything downstream of it, including
    # motion_planner.py — actually reflect the full part count instead
    # of just one representative instance per part.
    [sys.executable, "v2/rendering/action_replicator.py"],

    # --- PASS 2: rebuild the graph now using the REPLICATED actions. ---
    [sys.executable, "v2/rendering/universal_graph_engine.py"],

    [sys.executable, "v2/rendering/motion_planner.py"],

    [sys.executable, "v2/rendering/geometry_synthesizer.py"],

    DIAGRAM_ANALYZER_COMMAND,

    CopyStep(DIAGRAM_ANALYSIS_JSON, DIAGRAM_ANALYSIS_COPY_JSON),

    # Part shapes come before the scene layout, which uses their sizes and
    # roles (top/leg/rail) to place parts where they actually attach.
    [sys.executable, "v2/agents/part_shape_extractor_agent.py"],

    [sys.executable, "v2/rendering/scene_layout_engine.py"],

    CopyStep(SCENE_LAYOUT_JSON, SCENE_LAYOUT_COPY_JSON),

    [sys.executable, "v2/builders/proxy_geometry_builder.py"],

    [sys.executable, "v2/rendering/blender_builder_v3.py"],

    # --python-exit-code makes an exception in the generated script fail
    # the stage instead of exiting 0.
    [BLENDER_EXE, "--background", "--python-exit-code", "1", "--python", str(BLENDER_V3_SCRIPT)],

    [sys.executable, "v2/rendering/render_video.py"],
]


class PipelineStepError(RuntimeError):
    pass


def build_steps(vision_fixture_dir: Optional[Path]) -> List[Step]:
    if vision_fixture_dir is None:
        return list(COMMANDS)

    steps: List[Step] = []

    for step in COMMANDS:
        if step is PAGE_STATE_COMMAND:
            steps.append(CopyStep(vision_fixture_dir / "page_states.json", PAGE_STATES_JSON))
        elif step is DIAGRAM_ANALYZER_COMMAND:
            steps.append(CopyStep(vision_fixture_dir / "diagram_analysis.json", DIAGRAM_ANALYSIS_JSON))
        else:
            steps.append(step)

    return steps


def run_command(step: Step) -> None:
    print("\n" + "=" * 80)
    print("RUNNING:", step if isinstance(step, CopyStep) else " ".join(step))
    print("=" * 80, flush=True)

    if isinstance(step, CopyStep):
        if not step.source.exists():
            raise PipelineStepError(f"{step} failed: {step.source} does not exist.")
        step.destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(step.source, step.destination)
        return

    if step[0] == BLENDER_EXE and not Path(BLENDER_EXE).exists():
        raise PipelineStepError(
            f"Blender not found at {BLENDER_EXE}. Install Blender or set BLENDER_EXE "
            "in .env to the full path of blender.exe."
        )

    result = subprocess.run(step, shell=False)

    if result.returncode != 0:
        raise PipelineStepError(
            f"Stage exited with code {result.returncode}: {' '.join(step)}. "
            "Its error is shown above; later stages were not run."
        )


def clear_old_outputs():
    ensure_project_dirs()

    for item in FRAMES_V3_DIR.glob("*.png"):
        item.unlink()

    if VIDEO_V3_PATH.exists():
        VIDEO_V3_PATH.unlink()

    for json_dir in (V2_JSON_DIR, V2_OUTPUT_DIR):
        if json_dir.exists():
            for item in json_dir.glob("*.json"):
                item.unlink()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--vision-fixture",
        nargs="?",
        const=DEFAULT_VISION_FIXTURE_DIR,
        type=Path,
        metavar="DIR",
        help=(
            "Skip the Azure vision stages and use page_states.json and "
            "diagram_analysis.json from DIR (default: %(const)s)."
        ),
    )
    return parser.parse_args()


def main():
    args = parse_args()
    ensure_project_dirs()

    print("Starting MVP pipeline...")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Frames output: {FRAMES_V3_DIR}")
    print(f"Video output: {VIDEO_V3_PATH}")

    if args.vision_fixture is not None:
        print(f"Vision fixture: {args.vision_fixture} (Azure vision stages skipped)")

    clear_old_outputs()

    try:
        for step in build_steps(args.vision_fixture):
            run_command(step)
    except PipelineStepError as e:
        print(f"\n[PIPELINE FAILED] {e}", file=sys.stderr)
        sys.exit(1)

    print("\n[SUCCESS] MVP pipeline complete")
    print("Video should be here:")
    print(VIDEO_V3_PATH.resolve())


if __name__ == "__main__":
    main()
