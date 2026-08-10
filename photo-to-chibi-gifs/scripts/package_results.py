from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image, ImageDraw


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a contact sheet and ZIP for a validated GIF pack.")
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--allow-errors", action="store_true")
    return parser.parse_args()


def checkerboard(size: tuple[int, int], cell: int = 12) -> Image.Image:
    image = Image.new("RGBA", size, (245, 245, 245, 255))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill=(222, 222, 222, 255))
    return image


def make_contact_sheet(gifs: list[Path], output: Path, columns: int = 6) -> None:
    tile = 240
    rows = max(1, math.ceil(len(gifs) / columns))
    sheet = checkerboard((columns * tile, rows * tile))
    for index, path in enumerate(gifs):
        with Image.open(path) as image:
            image.seek(0)
            frame = image.convert("RGBA")
        x = (index % columns) * tile
        y = (index // columns) * tile
        sheet.alpha_composite(frame, (x, y))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def make_all_frames_contact_sheet(gifs: list[Path], output: Path) -> None:
    tile = 240
    frame_count = 5
    sheet = checkerboard((frame_count * tile, max(1, len(gifs)) * tile))
    for row, path in enumerate(gifs):
        with Image.open(path) as image:
            if getattr(image, "n_frames", 1) != frame_count:
                raise SystemExit(f"Expected five frames while building contact sheet: {path}")
            for column in range(frame_count):
                image.seek(column)
                frame = image.convert("RGBA")
                sheet.alpha_composite(frame, (column * tile, row * tile))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def main() -> None:
    args = parse_args()
    run_dir = args.run_dir.expanduser().resolve()
    validation_path = run_dir / "qa" / "validation.json"
    if not validation_path.is_file():
        raise SystemExit("Run validate_pack.py before packaging.")
    validation = read_json(validation_path)
    if validation.get("status") != "pass" and not args.allow_errors:
        raise SystemExit("Validation failed. Repair the pack or use --allow-errors for a review-only package.")

    jobs = read_json(run_dir / "jobs.json")
    gifs = [run_dir / "final" / f"{job['index']:02d}-{job['slug']}.gif" for job in jobs["jobs"]]
    missing = [str(path) for path in gifs if not path.is_file()]
    if missing:
        raise SystemExit("Missing GIFs:\n" + "\n".join(missing))

    contact_sheet = run_dir / "qa" / "contact-sheet.png"
    make_contact_sheet(gifs, contact_sheet)
    all_frames_sheet = run_dir / "qa" / "contact-sheet-all-frames.png"
    make_all_frames_contact_sheet(gifs, all_frames_sheet)

    mode = read_json(run_dir / "request.json").get("mode", "standard")
    zip_path = run_dir / "final" / f"chibi-gif-pack-{len(gifs)}-{mode}.zip"
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as archive:
        for gif in gifs:
            archive.write(gif, f"gifs/{gif.name}")
        archive.write(contact_sheet, "qa/contact-sheet.png")
        archive.write(all_frames_sheet, "qa/contact-sheet-all-frames.png")
        archive.write(validation_path, "qa/validation.json")

    progress_path = run_dir / "progress.json"
    progress = read_json(progress_path) if progress_path.is_file() else {}
    progress["package"] = "created"
    progress["zip"] = str(zip_path)
    write_json(progress_path, progress)

    print(f"ZIP\t{zip_path}")
    print(f"CONTACT_SHEET\t{contact_sheet}")
    print(f"ALL_FRAMES_CONTACT_SHEET\t{all_frames_sheet}")
    print(f"GIFS\t{len(gifs)}")


if __name__ == "__main__":
    main()
