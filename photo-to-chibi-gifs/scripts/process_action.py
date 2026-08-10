from __future__ import annotations

import argparse
import colorsys
import json
import statistics
from collections import deque
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert a five-frame strip or frame directory into a transparent GIF.")
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--action", required=True)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--tolerance", type=int, default=70)
    parser.add_argument("--softness", type=int, default=42)
    return parser.parse_args()


def parse_hex_color(value: str) -> tuple[int, int, int]:
    value = value.strip().lstrip("#")
    if len(value) != 6:
        raise ValueError(f"Invalid chroma color: {value}")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


def remove_chroma(image: Image.Image, key: tuple[int, int, int], tolerance: int, softness: int) -> Image.Image:
    rgba = image.convert("RGBA")
    difference = ImageChops.difference(rgba.convert("RGB"), Image.new("RGB", rgba.size, key))
    red, green, blue = difference.split()
    maximum = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    upper = max(tolerance + softness, tolerance + 1)

    def alpha_value(distance: int) -> int:
        if distance <= tolerance:
            return 0
        if distance >= upper:
            return 255
        return round(255 * (distance - tolerance) / (upper - tolerance))

    chroma_alpha = maximum.point(alpha_value).filter(ImageFilter.MinFilter(3))
    rgba.putalpha(ImageChops.multiply(rgba.getchannel("A"), chroma_alpha))
    return rgba


def components(alpha: Image.Image, threshold: int = 16) -> list[tuple[int, tuple[int, int, int, int]]]:
    width, height = alpha.size
    pixels = alpha.load()
    seen = bytearray(width * height)
    found: list[tuple[int, tuple[int, int, int, int]]] = []
    for y in range(height):
        for x in range(width):
            offset = y * width + x
            if seen[offset] or pixels[x, y] < threshold:
                continue
            queue: deque[tuple[int, int]] = deque([(x, y)])
            seen[offset] = 1
            area = 0
            min_x = max_x = x
            min_y = max_y = y
            while queue:
                current_x, current_y = queue.popleft()
                area += 1
                min_x = min(min_x, current_x)
                max_x = max(max_x, current_x)
                min_y = min(min_y, current_y)
                max_y = max(max_y, current_y)
                for next_x, next_y in (
                    (current_x - 1, current_y - 1), (current_x, current_y - 1), (current_x + 1, current_y - 1),
                    (current_x - 1, current_y),                                       (current_x + 1, current_y),
                    (current_x - 1, current_y + 1), (current_x, current_y + 1), (current_x + 1, current_y + 1),
                ):
                    if 0 <= next_x < width and 0 <= next_y < height:
                        next_offset = next_y * width + next_x
                        if not seen[next_offset] and pixels[next_x, next_y] >= threshold:
                            seen[next_offset] = 1
                            queue.append((next_x, next_y))
            found.append((area, (min_x, min_y, max_x + 1, max_y + 1)))
    return found


def union_boxes(boxes: list[tuple[int, int, int, int]]) -> tuple[int, int, int, int]:
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def subject_and_significant_boxes(image: Image.Image) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    found = components(image.getchannel("A"))
    if not found:
        raise SystemExit("A frame became fully transparent. Check the chroma key or source strip.")
    largest_area, subject_box = max(found, key=lambda item: item[0])
    significant = [box for area, box in found if area >= max(40, round(largest_area * 0.015))]
    return subject_box, union_boxes(significant)


def remove_boundary_fragments(panel: Image.Image) -> Image.Image:
    image = panel.copy().convert("RGBA")
    alpha = image.getchannel("A")
    width, height = image.size
    pixels = image.load()
    for area, box in components(alpha):
        left, _, right, _ = box
        touches_side = left == 0 or right == width
        if touches_side and area <= max(500, round(width * height * 0.035)) and right - left <= max(16, round(width * 0.22)):
            crop_alpha = alpha.crop(box)
            crop_pixels = crop_alpha.load()
            for local_y in range(crop_alpha.height):
                for local_x in range(crop_alpha.width):
                    if crop_pixels[local_x, local_y] >= 16:
                        x, y = left + local_x, box[1] + local_y
                        red, green, blue, _ = pixels[x, y]
                        pixels[x, y] = (red, green, blue, 0)
    return image


def remove_isolated_components(image: Image.Image, max_pixels: int) -> tuple[Image.Image, int]:
    output = image.copy().convert("RGBA")
    alpha = output.getchannel("A")
    pixels = output.load()
    removed = 0
    for area, box in components(alpha):
        if area > max_pixels:
            continue
        removed += 1
        crop_alpha = alpha.crop(box)
        crop_pixels = crop_alpha.load()
        for local_y in range(crop_alpha.height):
            for local_x in range(crop_alpha.width):
                if crop_pixels[local_x, local_y] >= 16:
                    x, y = box[0] + local_x, box[1] + local_y
                    red, green, blue, _ = pixels[x, y]
                    pixels[x, y] = (red, green, blue, 0)
    return output, removed


def largest_component_pixels(image: Image.Image, threshold: int = 16) -> list[tuple[int, int]]:
    alpha = image.getchannel("A")
    width, height = alpha.size
    pixels = alpha.load()
    seen = bytearray(width * height)
    largest: list[tuple[int, int]] = []
    for y in range(height):
        for x in range(width):
            offset = y * width + x
            if seen[offset] or pixels[x, y] < threshold:
                continue
            queue: deque[tuple[int, int]] = deque([(x, y)])
            seen[offset] = 1
            current: list[tuple[int, int]] = []
            while queue:
                current_x, current_y = queue.popleft()
                current.append((current_x, current_y))
                for next_x, next_y in (
                    (current_x - 1, current_y - 1), (current_x, current_y - 1), (current_x + 1, current_y - 1),
                    (current_x - 1, current_y),                                       (current_x + 1, current_y),
                    (current_x - 1, current_y + 1), (current_x, current_y + 1), (current_x + 1, current_y + 1),
                ):
                    if 0 <= next_x < width and 0 <= next_y < height:
                        next_offset = next_y * width + next_x
                        if not seen[next_offset] and pixels[next_x, next_y] >= threshold:
                            seen[next_offset] = 1
                            queue.append((next_x, next_y))
            if len(current) > len(largest):
                largest = current
    return largest


def subject_edge_spill_pixels(image: Image.Image, key: tuple[int, int, int]) -> list[tuple[int, int]]:
    key_hue = colorsys.rgb_to_hsv(*(channel / 255 for channel in key))[0]
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    spill = []
    subject_pixels = set(largest_component_pixels(rgba))
    for x, y in subject_pixels:
        red, green, blue, alpha = pixels[x, y]
        hue, saturation, value = colorsys.rgb_to_hsv(red / 255, green / 255, blue / 255)
        hue_distance = min(abs(hue - key_hue), 1 - abs(hue - key_hue))
        key_like = hue_distance <= 0.10 and saturation >= 0.55 and value >= 0.20
        boundary = any(
            (x + dx, y + dy) not in subject_pixels
            for dx, dy in ((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1))
        )
        # Preserve normal red/brown hair, skin, and print edges. Neutralize
        # green/cyan/blue/purple/yellow chroma noise only on the outer contour.
        edge_color_noise = boundary and saturation >= 0.35 and value >= 0.06 and 0.14 <= hue <= 0.97
        if alpha >= 16 and (key_like or edge_color_noise):
            spill.append((x, y))
    return spill


def despill_subject_outline(image: Image.Image, key: tuple[int, int, int]) -> tuple[Image.Image, int]:
    output = image.copy().convert("RGBA")
    pixels = output.load()
    spill = subject_edge_spill_pixels(output, key)
    for x, y in spill:
        red, green, blue, alpha = pixels[x, y]
        neutral = min(red, green, blue)
        pixels[x, y] = (neutral, neutral, neutral, alpha)
    return output, len(spill)


def detect_face_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    rgba = image.convert("RGBA")
    mask = Image.new("L", rgba.size, 0)
    source = rgba.load()
    target = mask.load()
    try:
        subject_box, _ = subject_and_significant_boxes(rgba)
    except SystemExit:
        return None
    subject_left, subject_top, subject_right, subject_bottom = subject_box
    subject_width = subject_right - subject_left
    subject_height = subject_bottom - subject_top
    center_x = (subject_left + subject_right) / 2
    roi_left = max(0, round(center_x - subject_width * 0.34))
    roi_right = min(rgba.width, round(center_x + subject_width * 0.34))
    roi_top = max(0, round(subject_top + subject_height * 0.05))
    roi_bottom = min(rgba.height, round(subject_top + subject_height * 0.58))
    for y in range(roi_top, roi_bottom):
        for x in range(roi_left, roi_right):
            red, green, blue, alpha = source[x, y]
            is_skin = (
                alpha >= 96
                and red >= 135
                and green >= 75
                and blue >= 55
                and red >= green + 6
                and green >= blue - 8
                and red - blue >= 22
                and not (red > 246 and green > 242 and blue > 238)
            )
            if is_skin:
                target[x, y] = 255
    candidates = []
    for area, box in components(mask, threshold=128):
        left, top, right, bottom = box
        width = right - left
        height = bottom - top
        center_x = (left + right) / 2
        if area >= 80 and width >= 18 and height >= 18 and top < roi_bottom and roi_left < center_x < roi_right:
            aspect = width / max(1, height)
            if 0.55 <= aspect <= 1.8:
                candidates.append((area * (1.2 if top < rgba.height * 0.45 else 1.0), box))
    return max(candidates, default=(0, None), key=lambda item: item[0])[1]


def detect_eye_line(image: Image.Image, face_box: tuple[int, int, int, int] | None) -> int | None:
    if not face_box:
        return None
    left, top, right, bottom = face_box
    width = right - left
    height = bottom - top
    x0 = left + round(width * 0.14)
    x1 = right - round(width * 0.14)
    y0 = top + round(height * 0.28)
    y1 = top + round(height * 0.66)
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    best_y = None
    best_count = -1
    for y in range(max(0, y0), min(rgba.height, y1)):
        count = 0
        for x in range(max(0, x0), min(rgba.width, x1)):
            red, green, blue, alpha = pixels[x, y]
            if alpha >= 128 and (red + green + blue) / 3 < 105:
                count += 1
        if count > best_count:
            best_count = count
            best_y = y
    return best_y if best_count >= 2 else None


def split_or_load_frames(source: Path, frame_count: int) -> list[Image.Image]:
    if source.is_dir():
        paths = sorted(path for path in source.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)
        if len(paths) != frame_count:
            raise SystemExit(f"Expected exactly {frame_count} frame images in {source}; found {len(paths)}.")
        return [Image.open(path).convert("RGBA") for path in paths]
    if not source.is_file():
        raise SystemExit(f"Source does not exist: {source}")
    strip = Image.open(source).convert("RGBA")
    return [
        strip.crop((round(index * strip.width / frame_count), 0, round((index + 1) * strip.width / frame_count), strip.height))
        for index in range(frame_count)
    ]


def normalize_half_body_frames(
    frames: list[Image.Image], canvas: int, framing: dict
) -> tuple[list[Image.Image], dict]:
    measurements = [subject_and_significant_boxes(frame) for frame in frames]
    subject_boxes = [item[0] for item in measurements]
    significant_boxes = [item[1] for item in measurements]
    median_subject_height = statistics.median(box[3] - box[1] for box in subject_boxes)
    target_subject_height = round(canvas * framing["target_subject_height_ratio"])
    subject_scale = target_subject_height / max(1, median_subject_height)

    face_boxes = [detect_face_bbox(frame) for frame in frames]
    face_heights = [box[3] - box[1] for box in face_boxes if box]
    face_scale = None
    if face_heights:
        face_scale = framing["target_face_height_px"] / statistics.median(face_heights)

    safe_margin = 4
    width_fit_scales = []
    height_fit_scales = []
    for subject_box, significant_box in zip(subject_boxes, significant_boxes):
        subject_center_x = (subject_box[0] + subject_box[2]) / 2
        horizontal_span = 2 * max(subject_center_x - significant_box[0], significant_box[2] - subject_center_x)
        width_fit_scales.append((canvas - 2 * safe_margin) / max(1, horizontal_span))
        vertical_span = subject_box[3] - significant_box[1]
        height_fit_scales.append((canvas - framing["bottom_margin_target_px"] - safe_margin) / max(1, vertical_span))
    fit_scale = min([subject_scale, *width_fit_scales, *height_fit_scales])
    applied_scale = fit_scale

    output = []
    per_frame = []
    for frame, subject_box in zip(frames, subject_boxes):
        # Resize in premultiplied-alpha mode so hidden chroma RGB values in
        # transparent pixels cannot bleed back into the character outline.
        scaled = frame.convert("RGBa").resize(
            (max(1, round(frame.width * applied_scale)), max(1, round(frame.height * applied_scale))),
            Image.Resampling.LANCZOS,
        ).convert("RGBA")
        subject_center_x = (subject_box[0] + subject_box[2]) * applied_scale / 2
        subject_bottom = subject_box[3] * applied_scale
        offset_x = round(canvas / 2 - subject_center_x)
        offset_y = round(canvas - framing["bottom_margin_target_px"] - subject_bottom)
        target = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
        target.alpha_composite(scaled, (offset_x, offset_y))
        output.append(target)
        normalized_subject, _ = subject_and_significant_boxes(target)
        normalized_face = detect_face_bbox(target)
        per_frame.append(
            {
                "subject_bbox": list(normalized_subject),
                "face_bbox": list(normalized_face) if normalized_face else None,
                "eye_line_y": detect_eye_line(target, normalized_face),
            }
        )
    cleaned_output = []
    normalized_isolated_removed = []
    for frame in output:
        cleaned_frame, removed = remove_isolated_components(frame, framing["isolated_component_max_pixels"])
        cleaned_output.append(cleaned_frame)
        normalized_isolated_removed.append(removed)
    return cleaned_output, {
        "requested_subject_scale": round(subject_scale, 6),
        "applied_scale": round(applied_scale, 6),
        "scale_retention_ratio": round(applied_scale / max(subject_scale, 1e-9), 4),
        "target_subject_height_px": target_subject_height,
        "target_face_height_px": framing["target_face_height_px"],
        "face_reference_scale": round(face_scale, 6) if face_scale is not None else None,
        "normalized_isolated_components_removed": normalized_isolated_removed,
        "frames": per_frame,
    }


def indexed_frame(frame: Image.Image, colors: int) -> Image.Image:
    rgba = frame.convert("RGBA")
    alpha = rgba.getchannel("A")
    quantized = rgba.convert("RGB").quantize(colors=colors - 1, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette()[: (colors - 1) * 3]
    source = quantized.tobytes()
    alpha_bytes = alpha.tobytes()
    shifted = bytearray(len(source))
    for index, color_index in enumerate(source):
        shifted[index] = 0 if alpha_bytes[index] < 128 else color_index + 1
    indexed = Image.new("P", rgba.size, 0)
    indexed.frombytes(bytes(shifted))
    indexed.putpalette(([0, 0, 0] + palette + [0] * 768)[:768])
    indexed.info["transparency"] = 0
    indexed.info["disposal"] = 2
    return indexed


def save_gif_under_limit(
    frames: list[Image.Image], output: Path, durations: list[int], max_bytes: int
) -> tuple[int, int]:
    output.parent.mkdir(parents=True, exist_ok=True)
    for colors in (256, 192, 128, 96, 64, 48, 32):
        indexed = [indexed_frame(frame, colors) for frame in frames]
        indexed[0].save(
            output,
            save_all=True,
            append_images=indexed[1:],
            duration=durations,
            loop=0,
            disposal=2,
            transparency=0,
            optimize=False,
        )
        if output.stat().st_size <= max_bytes:
            return output.stat().st_size, colors
    raise SystemExit(f"Could not reduce GIF below {max_bytes / 1024:.0f} KB: {output}")


def chroma_fringe_pixels(image: Image.Image, key: tuple[int, int, int], distance: int) -> int:
    count = 0
    rgba = image.convert("RGBA")
    pixel_values = rgba.get_flattened_data() if hasattr(rgba, "get_flattened_data") else rgba.getdata()
    for red, green, blue, alpha in pixel_values:
        if alpha >= 32 and max(abs(red - key[0]), abs(green - key[1]), abs(blue - key[2])) <= distance:
            count += 1
    return count


def main() -> None:
    args = parse_args()
    run_dir = args.run_dir.expanduser().resolve()
    jobs_path = run_dir / "jobs.json"
    if not jobs_path.is_file():
        raise SystemExit("Run jobs.json is missing. Run create_action_jobs.py first.")
    jobs_document = read_json(jobs_path)
    matching = [job for job in jobs_document["jobs"] if job["slug"] == args.action]
    if len(matching) != 1:
        raise SystemExit(f"Action is not uniquely present in jobs.json: {args.action}")
    job = matching[0]
    framing = job.get("framing", jobs_document["framing_defaults"])

    source = args.source.expanduser().resolve()
    frames = split_or_load_frames(source, jobs_document["frame_count"])
    chroma = parse_hex_color(job["chroma_key"])
    frames = [remove_chroma(frame, chroma, args.tolerance, args.softness) for frame in frames]
    frames = [remove_boundary_fragments(frame) for frame in frames]
    cleaned = [remove_isolated_components(frame, framing["isolated_component_max_pixels"]) for frame in frames]
    frames = [item[0] for item in cleaned]
    isolated_removed = [item[1] for item in cleaned]
    frames, normalization = normalize_half_body_frames(frames, jobs_document["canvas"], framing)
    despilled = [despill_subject_outline(frame, chroma) for frame in frames]
    frames = [item[0] for item in despilled]
    subject_spill_removed = [item[1] for item in despilled]

    processed_dir = run_dir / "processed" / args.action
    frames_dir = processed_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for index, frame in enumerate(frames, start=1):
        frame.save(frames_dir / f"frame-{index:02d}.png")

    gif_path = run_dir / "final" / f"{job['index']:02d}-{args.action}.gif"
    size, colors = save_gif_under_limit(frames, gif_path, job["durations_ms"], jobs_document["max_kb"] * 1024)
    fringe_counts = [chroma_fringe_pixels(frame, chroma, framing["chroma_fringe_distance"]) for frame in frames]

    job.update(
        {
            "status": "processed",
            "source": str(source),
            "gif": str(gif_path),
            "size_bytes": size,
            "palette_colors": colors,
            "normalization": normalization,
        }
    )
    write_json(jobs_path, jobs_document)

    progress_path = run_dir / "progress.json"
    progress = read_json(progress_path) if progress_path.is_file() else {}
    processed = set(progress.get("processed_actions", []))
    processed.add(args.action)
    progress["processed_actions"] = sorted(processed)
    write_json(progress_path, progress)

    report = {
        "action": args.action,
        "gif": str(gif_path),
        "size_bytes": size,
        "size_kb": round(size / 1024, 1),
        "palette_colors": colors,
        "dimensions": [jobs_document["canvas"], jobs_document["canvas"]],
        "frames": jobs_document["frame_count"],
        "wide_prop": job.get("wide_prop", False),
        "isolated_components_removed": isolated_removed,
        "subject_edge_spill_pixels_neutralized": subject_spill_removed,
        "chroma_fringe_pixels": fringe_counts,
        "normalization": normalization,
    }
    write_json(processed_dir / "report.json", report)
    print(f"GIF\t{gif_path}")
    print(f"SIZE_KB\t{size / 1024:.1f}")
    print(f"PALETTE\t{colors}")
    print(f"SCALE_RETENTION\t{normalization['scale_retention_ratio']:.3f}")


if __name__ == "__main__":
    main()
