from pathlib import Path
from moviepy import ImageSequenceClip


def frames_to_video(
    frames_dir: str = "outputs/frames",
    output_path: str = "outputs/final_assembly_video.mp4",
    fps: int = 24
):
    frames = sorted(Path(frames_dir).glob("scene_frame_*.png"))

    if not frames:
        frames = sorted(Path(frames_dir).glob("frame_*.png"))

    if not frames:
        raise FileNotFoundError(f"No PNG frames found in {frames_dir}")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    clip = ImageSequenceClip([str(f) for f in frames], fps=fps)
    clip.write_videofile(output_path, codec="libx264", audio=False)

    print(f"Video created: {output_path}")


if __name__ == "__main__":
    frames_to_video()