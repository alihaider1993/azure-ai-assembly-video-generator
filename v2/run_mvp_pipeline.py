import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config import (
    FRAMES_V3_DIR,
    VIDEO_V3_PATH,
    BLENDER_V3_SCRIPT,
    ensure_project_dirs,
)


BLENDER_EXE = r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe"

COMMANDS = [
    [sys.executable, "v2/agents/page_state_agent.py"],
    [sys.executable, "v2/rendering/state_difference_engine.py"],
    [sys.executable, "v2/rendering/assembly_action_extractor.py"],
    [sys.executable, "v2/rendering/universal_graph_engine.py"],
    [sys.executable, "v2/rendering/motion_planner.py"],
    [sys.executable, "v2/rendering/scene_layout_engine.py"],

    [sys.executable, "v2/agents/diagram_analyzer_agent.py"],

    ["powershell", "-Command", "copy v2\\outputs\\json\\diagram_analysis.json v2\\output\\diagram_analysis.json"],
    ["powershell", "-Command", "copy v2\\outputs\\json\\scene_layout.json v2\\output\\scene_layout.json"],

    [sys.executable, "v2/agents/part_shape_extractor_agent.py"],
    [sys.executable, "v2/builders/proxy_geometry_builder.py"],

    [sys.executable, "v2/rendering/blender_builder_v3.py"],

    [BLENDER_EXE, "--background", "--python", str(BLENDER_V3_SCRIPT)],

    [sys.executable, "v2/rendering/render_video.py"],
]


def run_command(cmd):
    print("\n" + "=" * 80)
    print("RUNNING:", " ".join(cmd))
    print("=" * 80)

    result = subprocess.run(cmd, shell=False)

    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")


def clear_old_outputs():
    ensure_project_dirs()

    for item in FRAMES_V3_DIR.glob("*.png"):
        item.unlink()

    if VIDEO_V3_PATH.exists():
        VIDEO_V3_PATH.unlink()


def main():
    ensure_project_dirs()

    print("Starting MVP pipeline...")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Frames output: {FRAMES_V3_DIR}")
    print(f"Video output: {VIDEO_V3_PATH}")

    clear_old_outputs()

    for cmd in COMMANDS:
        run_command(cmd)

    print("\n[SUCCESS] MVP pipeline complete")
    print("Video should be here:")
    print(VIDEO_V3_PATH.resolve())


if __name__ == "__main__":
    main()