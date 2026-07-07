import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from agents.scene_graph_agent import SceneGraphAgent
from agents.blender_agent import BlenderAgent
from services.video_composer import frames_to_video


BLENDER_PATH = r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe"


SCENE_GRAPH_PATH = PROJECT_ROOT / "outputs" / "json" / "scene_graph.json"
BLENDER_SCRIPT_PATH = PROJECT_ROOT / "blender" / "generated" / "generated_blender_scene.py"
FRAMES_DIR = PROJECT_ROOT / "outputs" / "frames"
FINAL_VIDEO_PATH = PROJECT_ROOT / "outputs" / "videos" / "final_assembly_video.mp4"


def ensure_folders():
    SCENE_GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
    BLENDER_SCRIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    FINAL_VIDEO_PATH.parent.mkdir(parents=True, exist_ok=True)


def clean_frames():
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)

    for frame in FRAMES_DIR.glob("*.png"):
        frame.unlink()


def run_blender(script_path: Path):
    command = [
        BLENDER_PATH,
        "--background",
        "--python",
        str(script_path)
    ]

    subprocess.run(command, check=True)


def main():
    print("Starting MVP pipeline...")

    ensure_folders()
    clean_frames()

    print("1. Generating Scene Graph...")

    sample_assembly_output = """
{
  "page_type": "assembly_step",
  "step_numbers": [1],
  "parts_used": ["panel", "8 fasteners"],
  "fasteners_used": ["8 fasteners"],
  "tools_required": ["screwdriver"],
  "actions": [
    {
      "action": "Insert and secure 8 fasteners into the designated holes on the panel.",
      "motion_for_animation": "Fasteners being rotated and tightened into the panel.",
      "camera_angle": "Top-down view focusing on the panel and fasteners.",
      "highlight_area": "Holes on the panel where fasteners are inserted.",
      "narration": "Insert 8 fasteners into the marked holes on the panel and tighten them using a screwdriver."
    }
  ],
  "warnings_or_cautions": ["Do not overtighten."]
}
"""

    scene_agent = SceneGraphAgent()
    scene = scene_agent.generate_scene_graph(sample_assembly_output)

    SCENE_GRAPH_PATH.write_text(
        scene.model_dump_json(indent=2),
        encoding="utf-8"
    )

    print(f"Scene graph saved to: {SCENE_GRAPH_PATH}")

    print("2. Generating Blender script...")

    blender_agent = BlenderAgent()
    blender_agent.generate_blender_script(
        scene_graph_path=str(SCENE_GRAPH_PATH),
        output_script_path=str(BLENDER_SCRIPT_PATH)
    )

    print(f"Blender script saved to: {BLENDER_SCRIPT_PATH}")

    print("3. Rendering Blender frames...")

    run_blender(BLENDER_SCRIPT_PATH)

    print("4. Creating MP4 video...")

    frames_to_video(
        frames_dir=str(FRAMES_DIR),
        output_path=str(FINAL_VIDEO_PATH),
        fps=24
    )

    print("MVP video complete:")
    print(FINAL_VIDEO_PATH)


if __name__ == "__main__":
    main()