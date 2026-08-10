from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

from process_action import (
    chroma_fringe_pixels,
    components,
    detect_eye_line,
    detect_face_bbox,
    parse_hex_color,
    subject_edge_spill_pixels,
    subject_and_significant_boxes,
)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a transparent half-body chibi GIF pack.")
    parser.add_argument("--run-dir", required=True, type=Path)
    return parser.parse_args()


def motion_score(first: Image.Image, second: Image.Image) -> float:
    difference = ImageChops.difference(first.convert("RGBA"), second.convert("RGBA"))
    return sum(ImageStat.Stat(difference.convert("RGB")).mean) / 3


def validate_gif(path: Path, job: dict, document: dict) -> dict:
    canvas = document["canvas"]
    framing = job.get("framing", document["framing_defaults"])
    errors: list[str] = []
    warnings: list[str] = []
    frame_metrics = []
    frames = []
    transparent_frames = 0
    loop = None

    try:
        with Image.open(path) as image:
            actual_frames = getattr(image, "n_frames", 1)
            dimensions = list(image.size)
            loop = image.info.get("loop")
            for index in range(actual_frames):
                image.seek(index)
                frame = image.convert("RGBA")
                frames.append(frame.copy())
                alpha = frame.getchannel("A")
                if alpha.getextrema()[0] == 0:
                    transparent_frames += 1
                try:
                    subject_box, _ = subject_and_significant_boxes(frame)
                except SystemExit:
                    errors.append(f"frame {index + 1} is fully transparent")
                    continue
                left, top, right, bottom = subject_box
                margins = [left, top, canvas - right, canvas - bottom]
                subject_ratio = (bottom - top) / canvas
                face_box = detect_face_bbox(frame)
                eye_line = detect_eye_line(frame, face_box)
                face_height = face_box[3] - face_box[1] if face_box else None
                small_components = sum(
                    1
                    for area, _ in components(alpha)
                    if area <= framing["isolated_component_max_pixels"]
                )
                fringe = chroma_fringe_pixels(
                    frame,
                    parse_hex_color(job["chroma_key"]),
                    framing["chroma_fringe_distance"],
                )
                subject_spill = len(subject_edge_spill_pixels(frame, parse_hex_color(job["chroma_key"])))
                frame_metrics.append(
                    {
                        "frame": index + 1,
                        "subject_bbox": list(subject_box),
                        "margins": margins,
                        "subject_height_ratio": round(subject_ratio, 4),
                        "face_bbox": list(face_box) if face_box else None,
                        "face_height": face_height,
                        "eye_line_y": eye_line,
                        "isolated_components": small_components,
                        "chroma_fringe_pixels": fringe,
                        "subject_edge_spill_pixels": subject_spill,
                    }
                )

                if subject_ratio < framing["subject_height_ratio_min"] or subject_ratio > framing["subject_height_ratio_max"]:
                    warnings.append(f"frame {index + 1} subject height ratio {subject_ratio:.3f} is outside 0.85–0.90")
                if subject_ratio < 0.82 or subject_ratio > 0.93:
                    errors.append(f"frame {index + 1} subject height ratio {subject_ratio:.3f} is unreasonable")
                bottom_margin = canvas - bottom
                if abs(bottom_margin - framing["bottom_margin_target_px"]) > framing["bottom_margin_tolerance_px"]:
                    warnings.append(f"frame {index + 1} waist anchor is {bottom_margin}px from bottom")
                if abs(bottom_margin - framing["bottom_margin_target_px"]) > 10:
                    errors.append(f"frame {index + 1} waist anchor differs too much from 12px")
                if top < framing["top_margin_min_px"] or top > framing["top_margin_max_px"]:
                    warnings.append(f"frame {index + 1} top margin is {top}px, expected about 12–24px")
                if top < 4 or top > 36:
                    errors.append(f"frame {index + 1} top margin is incompatible with large half-body framing")
                if not job.get("wide_prop", False):
                    side_margin = min(left, canvas - right)
                    if side_margin < 35 or side_margin > 70:
                        warnings.append(f"frame {index + 1} ordinary side margin is {side_margin}px")
                if not face_box:
                    warnings.append(f"frame {index + 1} face detector could not establish a face-size anchor")
                if small_components:
                    warnings.append(f"frame {index + 1} contains {small_components} tiny isolated opaque component(s)")
                if fringe:
                    errors.append(f"frame {index + 1} contains {fringe} near-chroma fringe pixel(s)")
                if subject_spill > 25:
                    errors.append(f"frame {index + 1} contains {subject_spill} chroma-colored subject-edge pixel(s)")
                elif subject_spill > 5:
                    warnings.append(f"frame {index + 1} contains {subject_spill} quantized color edge pixel(s)")
    except Exception as exc:
        return {"slug": job["slug"], "file": str(path), "errors": [f"cannot read GIF: {exc}"], "warnings": []}

    if dimensions != [canvas, canvas]:
        errors.append(f"dimensions are {dimensions}, expected {[canvas, canvas]}")
    if actual_frames != document["frame_count"]:
        errors.append(f"frame count is {actual_frames}, expected {document['frame_count']}")
    if path.stat().st_size > document["max_kb"] * 1024:
        errors.append(f"file size is {path.stat().st_size} bytes, limit is {document['max_kb'] * 1024}")
    if transparent_frames != actual_frames:
        errors.append(f"only {transparent_frames}/{actual_frames} frames contain transparent pixels")
    if loop != 0:
        errors.append(f"GIF loop value is {loop!r}, expected 0 for continuous looping")

    scores = [round(motion_score(frames[index], frames[index + 1]), 3) for index in range(len(frames) - 1)]
    if scores and max(scores) < 0.45:
        errors.append("frames have almost no detectable motion")
    elif scores and min(scores) < 0.12:
        warnings.append("at least one adjacent frame pair changes very little")

    face_heights = [item["face_height"] for item in frame_metrics if item["face_height"]]
    eye_lines = [item["eye_line_y"] for item in frame_metrics if item["eye_line_y"] is not None]
    waist_lines = [item["subject_bbox"][3] for item in frame_metrics]
    return {
        "slug": job["slug"],
        "file": str(path),
        "size_bytes": path.stat().st_size,
        "dimensions": dimensions,
        "frame_count": actual_frames,
        "loop": loop,
        "transparent_frames": transparent_frames,
        "motion_scores": scores,
        "median_face_height": round(statistics.median(face_heights), 2) if face_heights else None,
        "median_eye_line_y": round(statistics.median(eye_lines), 2) if eye_lines else None,
        "median_waist_line_y": round(statistics.median(waist_lines), 2) if waist_lines else None,
        "frame_metrics": frame_metrics,
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }


def add_cross_action_checks(results: list[dict], framing: dict) -> None:
    face_values = [result["median_face_height"] for result in results if result.get("median_face_height")]
    eye_values = [result["median_eye_line_y"] for result in results if result.get("median_eye_line_y") is not None]
    waist_values = [result["median_waist_line_y"] for result in results if result.get("median_waist_line_y") is not None]
    global_face = statistics.median(face_values) if face_values else None
    global_eye = statistics.median(eye_values) if eye_values else None
    global_waist = statistics.median(waist_values) if waist_values else None

    for result in results:
        face = result.get("median_face_height")
        if global_face and face:
            difference_ratio = abs(face - global_face) / global_face
            if difference_ratio > framing["face_height_error_ratio"]:
                result["errors"].append(f"face height differs {difference_ratio:.1%} from the pack median")
            elif difference_ratio > framing["face_height_warning_ratio"]:
                result["warnings"].append(f"face height differs {difference_ratio:.1%} from the pack median")
            if result["slug"] == "busy-typing" and face < global_face * framing["wide_prop_max_face_shrink_ratio"]:
                result["errors"].append("laptop composition shrinks the face more than allowed")
        eye = result.get("median_eye_line_y")
        if global_eye is not None and eye is not None:
            difference = abs(eye - global_eye)
            if difference > framing["eye_line_error_px"]:
                result["errors"].append(f"eye line differs {difference:.1f}px from the pack median")
            elif difference > framing["eye_line_warning_px"]:
                result["warnings"].append(f"eye line differs {difference:.1f}px from the pack median")
        waist = result.get("median_waist_line_y")
        if global_waist is not None and waist is not None:
            difference = abs(waist - global_waist)
            if difference > 8:
                result["errors"].append(f"waist line differs {difference:.1f}px from the pack median")
            elif difference > 4:
                result["warnings"].append(f"waist line differs {difference:.1f}px from the pack median")
        result["errors"] = sorted(set(result["errors"]))
        result["warnings"] = sorted(set(result["warnings"]))


def main() -> None:
    args = parse_args()
    run_dir = args.run_dir.expanduser().resolve()
    jobs_path = run_dir / "jobs.json"
    if not jobs_path.is_file():
        raise SystemExit("jobs.json is missing.")
    document = read_json(jobs_path)
    expected_paths = {
        f"{job['index']:02d}-{job['slug']}.gif": job
        for job in document["jobs"]
    }
    gif_paths = sorted((run_dir / "final").glob("*.gif"))
    found = {path.name for path in gif_paths}
    expected = set(expected_paths)

    pack_errors = []
    if expected - found:
        pack_errors.append(f"missing GIFs: {', '.join(sorted(expected - found))}")
    if found - expected:
        pack_errors.append(f"unexpected GIFs: {', '.join(sorted(found - expected))}")

    results = [
        validate_gif(path, expected_paths[path.name], document)
        for path in gif_paths
        if path.name in expected_paths
    ]
    add_cross_action_checks(results, document["framing_defaults"])
    error_count = len(pack_errors) + sum(len(result["errors"]) for result in results)
    warning_count = sum(len(result["warnings"]) for result in results)
    report = {
        "status": "pass" if error_count == 0 else "fail",
        "job_order": [job["slug"] for job in document["jobs"]],
        "expected_gifs": len(expected),
        "found_gifs": len(found & expected),
        "error_count": error_count,
        "warning_count": warning_count,
        "pack_errors": pack_errors,
        "files": results,
        "manual_review_required": True,
        "manual_checks": [
            "inspect all five frames of every action in qa/contact-sheet-all-frames.png",
            "check extra or missing hands, disconnected arms, and incorrect fingers",
            "check duplicated, floating, disconnected, or deformed props",
            "check age presentation, face shape, jaw, midface, hair, eyewear, clothing, print, and watch drift",
            "check face size, eye height, waist anchor, overall proportion, and natural waist crop consistency",
            "check that the laptop or effects do not noticeably shrink the person",
            "check that frame 5 loops naturally to frame 1",
        ],
    }
    report_path = run_dir / "qa" / "validation.json"
    write_json(report_path, report)

    progress_path = run_dir / "progress.json"
    progress = read_json(progress_path) if progress_path.is_file() else {}
    progress["validation"] = report["status"]
    progress["manual_review"] = "required"
    write_json(progress_path, progress)

    print(f"STATUS\t{report['status']}")
    print(f"GIFS\t{report['found_gifs']}/{report['expected_gifs']}")
    print(f"ERRORS\t{error_count}")
    print(f"WARNINGS\t{warning_count}")
    print(f"REPORT\t{report_path}")
    if error_count:
        sys.exit(1)


if __name__ == "__main__":
    main()
