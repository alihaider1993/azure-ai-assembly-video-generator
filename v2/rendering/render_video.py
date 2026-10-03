import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
from moviepy import VideoClip
from PIL import Image, ImageDraw, ImageFont

from config import (
    BLENDER_V3_SCRIPT,
    FRAMES_V3_DIR,
    RENDER_TIMELINE_JSON,
    VIDEO_V3_PATH,
    ensure_project_dirs,
)


FRAME_DIR = FRAMES_V3_DIR
OUTPUT_VIDEO = VIDEO_V3_PATH
FPS = 24
# Fewer frames than this means the render stage produced (almost) nothing;
# encoding it would just hide that failure behind a valid-looking MP4.
MIN_FRAMES = FPS
FRAME_NUMBER_RE = re.compile(r"(\d+)\.png$")

# Caption panel, as fractions of the frame height.
CAPTION_MARGIN = 0.035
CAPTION_PADDING = 0.022
LABEL_SIZE = 0.028
TEXT_SIZE = 0.042
CAPTION_FADE_FRAMES = 6
PANEL_COLOR = (20, 24, 30)
PANEL_OPACITY = 0.78
LABEL_COLOR = (255, 140, 60)
TEXT_COLOR = (245, 246, 248)


def load_font(names, size):
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def frame_number(path: Path) -> int:
    match = FRAME_NUMBER_RE.search(path.name)
    return int(match.group(1)) if match else 0


def caption_at(captions, frame):
    """(caption, opacity 0..1) showing at `frame`, or (None, 0)."""
    for caption in captions:
        start, end = caption["start_frame"], caption["end_frame"]
        if start <= frame <= end:
            fade = min(frame - start, end - frame) / CAPTION_FADE_FRAMES
            return caption, max(0.0, min(1.0, fade))
    return None, 0.0


def draw_caption(image: Image.Image, caption, opacity: float, fonts) -> Image.Image:
    label_font, text_font = fonts
    height = image.height
    margin = int(height * CAPTION_MARGIN)
    padding = int(height * CAPTION_PADDING)

    label_box = label_font.getbbox(caption["label"])
    text_box = text_font.getbbox(caption["text"])
    gap = padding // 2
    panel_w = max(label_box[2], text_box[2]) + 2 * padding
    panel_h = label_box[3] + gap + text_box[3] + 2 * padding
    left = margin
    top = height - margin - panel_h

    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle(
        (left, top, left + panel_w, top + panel_h),
        radius=padding,
        fill=PANEL_COLOR + (int(255 * PANEL_OPACITY * opacity),),
    )
    alpha = int(255 * opacity)
    draw.text((left + padding, top + padding), caption["label"], font=label_font, fill=LABEL_COLOR + (alpha,))
    draw.text(
        (left + padding, top + padding + label_box[3] + gap),
        caption["text"],
        font=text_font,
        fill=TEXT_COLOR + (alpha,),
    )
    return Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")


def main():
    ensure_project_dirs()

    frames = sorted(FRAME_DIR.glob("*.png"), key=frame_number)

    if not frames:
        raise FileNotFoundError(f"No PNG frames found in {FRAME_DIR}")

    # A failed or interrupted render can leave the previous run's frames
    # behind; never encode those.
    if BLENDER_V3_SCRIPT.exists():
        script_time = BLENDER_V3_SCRIPT.stat().st_mtime
        stale = [f for f in frames if f.stat().st_mtime < script_time]
        if stale:
            raise RuntimeError(
                f"{len(stale)} frame(s) in {FRAME_DIR} are older than {BLENDER_V3_SCRIPT.name}; "
                "the latest Blender render did not complete."
            )

    if len(frames) < MIN_FRAMES:
        raise RuntimeError(
            f"Only {len(frames)} frame(s) in {FRAME_DIR}; need at least {MIN_FRAMES}. "
            "The Blender render stage produced too little to make a video."
        )

    captions = []
    if RENDER_TIMELINE_JSON.exists():
        captions = json.loads(RENDER_TIMELINE_JSON.read_text(encoding="utf-8")).get("captions", [])
    else:
        print(f"No {RENDER_TIMELINE_JSON.name}; encoding without captions")

    height = Image.open(frames[0]).height
    fonts = (
        load_font(["segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"], int(height * LABEL_SIZE)),
        load_font(["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"], int(height * TEXT_SIZE)),
    )

    def make_frame(t):
        index = min(int(round(t * FPS)), len(frames) - 1)
        path = frames[index]
        image = Image.open(path).convert("RGB")
        caption, opacity = caption_at(captions, frame_number(path))
        if caption and opacity > 0:
            image = draw_caption(image, caption, opacity, fonts)
        return np.asarray(image)

    print(f"Frames found: {len(frames)}")
    print(f"Captions: {len(captions)}")
    print(f"Input folder: {FRAME_DIR.resolve()}")
    print(f"Output video: {OUTPUT_VIDEO.resolve()}")

    clip = VideoClip(make_frame, duration=len(frames) / FPS)

    OUTPUT_VIDEO.parent.mkdir(parents=True, exist_ok=True)

    clip.write_videofile(
        str(OUTPUT_VIDEO),
        fps=FPS,
        codec="libx264",
        audio=False,
        # Standard players and browsers need yuv420p, which needs even
        # dimensions; moviepy only requests it when the size is already even.
        ffmpeg_params=["-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-pix_fmt", "yuv420p"],
    )

    print(f" Video created: {OUTPUT_VIDEO.resolve()}")


if __name__ == "__main__":
    main()
