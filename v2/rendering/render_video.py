import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from moviepy.video.io.ImageSequenceClip import ImageSequenceClip

from config import FRAMES_V3_DIR, VIDEO_V3_PATH, ensure_project_dirs


FRAME_DIR = FRAMES_V3_DIR
OUTPUT_VIDEO = VIDEO_V3_PATH
FPS = 24


def main():
    ensure_project_dirs()

    frames = sorted(FRAME_DIR.glob("*.png"))

    if not frames:
        raise FileNotFoundError(f"No PNG frames found in {FRAME_DIR}")

    print(f"Frames found: {len(frames)}")
    print(f"Input folder: {FRAME_DIR.resolve()}")
    print(f"Output video: {OUTPUT_VIDEO.resolve()}")

    clip = ImageSequenceClip([str(f) for f in frames], fps=FPS)

    OUTPUT_VIDEO.parent.mkdir(parents=True, exist_ok=True)

    clip.write_videofile(
        str(OUTPUT_VIDEO),
        codec="libx264",
        audio=False
    )

    print(f" Video created: {OUTPUT_VIDEO.resolve()}")


if __name__ == "__main__":
    main()