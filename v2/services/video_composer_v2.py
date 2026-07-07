import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from moviepy.video.io.ImageSequenceClip import ImageSequenceClip

from config import FRAMES_V2_DIR, VIDEO_V2_PATH, ensure_project_dirs


FPS = 24
FRAMES_DIR = FRAMES_V2_DIR
OUTPUT_VIDEO = VIDEO_V2_PATH


def build_video():
    ensure_project_dirs()

    if not FRAMES_DIR.exists():
        raise FileNotFoundError(f"Frames folder not found: {FRAMES_DIR}")

    frames = sorted(FRAMES_DIR.glob("*.png"))

    if not frames:
        raise RuntimeError(f"No PNG frames found in: {FRAMES_DIR}")

    OUTPUT_VIDEO.parent.mkdir(parents=True, exist_ok=True)

    print(f"Frames folder : {FRAMES_DIR.resolve()}")
    print(f"Frames found  : {len(frames)}")
    print(f"FPS           : {FPS}")
    print(f"Output video  : {OUTPUT_VIDEO.resolve()}")
    print("Creating video...\n")

    start = time.time()

    clip = ImageSequenceClip(
        [str(f) for f in frames],
        fps=FPS
    )

    clip.write_videofile(
        str(OUTPUT_VIDEO),
        codec="libx264",
        audio=False,
        fps=FPS,
        preset="medium",
        threads=4
    )

    elapsed = time.time() - start

    print("\n----------------------------")
    print("✅ Video successfully created")
    print("----------------------------")
    print(f"Output : {OUTPUT_VIDEO.resolve()}")
    print(f"Frames : {len(frames)}")
    print(f"Length : {len(frames) / FPS:.1f} seconds")
    print(f"Time   : {elapsed:.1f} seconds")


if __name__ == "__main__":
    build_video()