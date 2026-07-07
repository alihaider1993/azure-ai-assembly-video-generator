import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from config import (
    FRAMES_V2_DIR,
    FRAMES_V3_DIR,
    VIDEO_V2_PATH,
    VIDEO_V3_PATH,
    BLENDER_V2_SCRIPT,
    BLENDER_V3_SCRIPT,
    ensure_project_dirs,
)


PATHS_TO_CLEAR = [
    FRAMES_V2_DIR,
    FRAMES_V3_DIR,
]

FILES_TO_DELETE = [
    VIDEO_V2_PATH,
    VIDEO_V3_PATH,
    BLENDER_V2_SCRIPT,
    BLENDER_V3_SCRIPT,
]


def clear_folder(folder: Path):
    folder.mkdir(parents=True, exist_ok=True)

    deleted = 0

    for item in folder.glob("*"):
        if item.is_file():
            item.unlink()
            deleted += 1

    print(f"Cleared {deleted} files from {folder}")


def delete_file(path: Path):
    if path.exists():
        path.unlink()
        print(f"Deleted: {path}")
    else:
        print(f"Skip missing file: {path}")


def main():
    ensure_project_dirs()

    print("=" * 80)
    print("Cleaning project render outputs")
    print("=" * 80)

    print(f"Project root : {PROJECT_ROOT}")
    print(f"Frames V2    : {FRAMES_V2_DIR}")
    print(f"Frames V3    : {FRAMES_V3_DIR}")
    print(f"Video V2     : {VIDEO_V2_PATH}")
    print(f"Video V3     : {VIDEO_V3_PATH}")
    print("=" * 80)

    for folder in PATHS_TO_CLEAR:
        clear_folder(folder)

    for file in FILES_TO_DELETE:
        delete_file(file)

    print("=" * 80)
    print("✅ Clean complete")
    print("=" * 80)


if __name__ == "__main__":
    main()