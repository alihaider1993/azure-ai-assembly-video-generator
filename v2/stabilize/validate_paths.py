import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


IGNORE_FOLDERS = {
    ".venv",
    "__pycache__",
    ".git",
    ".pytest_cache",
}

BAD_DRIVE = "C:"
BAD_FOLDER = "outputs"


def should_ignore(path: Path) -> bool:
    return any(part in IGNORE_FOLDERS for part in path.parts)


def has_bad_output_path(text: str) -> bool:
    normalized = text.replace("\\", "/").lower()
    return f"{BAD_DRIVE.lower()}/{BAD_FOLDER}" in normalized


def main():
    print("=" * 80)
    print("Validating project paths")
    print("=" * 80)
    print(f"Project root: {PROJECT_ROOT}")
    print("=" * 80)

    hits = []

    for path in PROJECT_ROOT.rglob("*.py"):
        if should_ignore(path):
            continue

        text = path.read_text(encoding="utf-8", errors="ignore")

        if has_bad_output_path(text):
            hits.append(path)

    if hits:
        print("❌ Hardcoded external output paths found:\n")

        for path in hits:
            print(path.relative_to(PROJECT_ROOT))

        raise SystemExit(1)

    print("✅ No hardcoded external output paths found")
    print("✅ Path validation passed")


if __name__ == "__main__":
    main()