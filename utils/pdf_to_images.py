import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import fitz

from config import DEFAULT_MANUAL_PDF, PAGE_IMAGES_DIR, ensure_project_dirs


def clear_old_pages(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    for old_file in output_dir.glob("page_*.png"):
        old_file.unlink()


def pdf_to_images(pdf_path: str, output_dir: str, zoom: int = 2):
    pdf = Path(pdf_path)
    output = Path(output_dir)

    if not pdf.exists():
        raise FileNotFoundError(f"Manual PDF not found: {pdf}")

    clear_old_pages(output)

    doc = fitz.open(pdf)
    image_paths = []

    for page_index in range(len(doc)):
        page = doc[page_index]
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))

        image_path = output / f"page_{page_index + 1}.png"
        pix.save(image_path)

        image_paths.append(str(image_path))

    doc.close()
    return image_paths


def main():
    ensure_project_dirs()

    if len(sys.argv) > 1:
        pdf_path = Path(sys.argv[1])
    else:
        pdf_path = DEFAULT_MANUAL_PDF

    print("=" * 80)
    print("Processing instructional manual:")
    print(pdf_path.resolve())
    print("=" * 80)

    paths = pdf_to_images(str(pdf_path), str(PAGE_IMAGES_DIR))

    print(f"Extracted {len(paths)} pages")
    print("First pages:")
    print(paths[:3])


if __name__ == "__main__":
    main()