from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
PRESETS_PATH = SKILL_DIR / "assets" / "action-presets.json"
SAMPLES_DIR = SKILL_DIR / "assets" / "approved-samples"
SAMPLES_MANIFEST_PATH = SAMPLES_DIR / "manifest.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create ImageGen action jobs from an approved identity lock.")
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--canonical-base", required=True, type=Path)
    parser.add_argument("--allow-draft", action="store_true", help="Only for deterministic script tests.")
    return parser.parse_args()


def identity_summary(identity: dict) -> str:
    fields = {
        "age_presentation": identity.get("age_presentation", {}),
        "reference_priority": identity.get("reference_priority", {}),
        "face": identity.get("face", {}),
        "hair": identity.get("hair", {}),
        "outfit": identity.get("outfit", {}),
        "framing": identity.get("framing", ""),
        "target_subject_height_ratio": identity.get("target_subject_height_ratio", {}),
        "waist_anchor": identity.get("waist_anchor", {}),
        "permanent_accessories": identity.get("permanent_accessories", []),
        "action_only_accessories": identity.get("action_only_accessories", {}),
        "accessory_rules": identity.get("accessory_rules", {}),
        "proportions": identity.get("proportions", {}),
        "style": identity.get("style", {}),
        "forbidden_drift": identity.get("forbidden_drift", []),
    }
    return json.dumps(fields, ensure_ascii=False, indent=2)


def build_prompt(identity: dict, action: dict, slug: str, has_approved_sample: bool) -> str:
    chroma = identity.get("chroma_key", "#FF00FF")
    required = "; ".join(action["required"])
    forbidden = "; ".join(action["forbidden"])
    return f"""Create one horizontal five-panel animation strip for the chibi character in the attached canonical base and portrait references.

ACTION: {action['name_zh']} ({slug})
MOTION: {action['motion']}
REQUIRED: {required}
FORBIDDEN: {forbidden}

REFERENCE PRIORITY:
1. The current user's portrait photos and identity lock control identity, age presentation, face, hair, eyewear, clothing, and accessories.
2. {"The attached approved five-frame action strip" if has_approved_sample else "The attached framing reference"} controls drawing style, large half-body scale, subject size, waist crop, spacing, and motion rhythm only.
3. This action preset supplies remaining motion details.

Never copy the sample character's identity, face, glasses, hair, clothing, print, watch, or headwear to the current user.

IDENTITY LOCK:
{identity_summary(identity)}

STRIP CONTRACT:
- exactly five equal panels in one horizontal row, read left to right;
- the same single large head-to-waist character in every panel; legs and shoes are outside the default composition;
- identical adult age presentation, face size, eye height, hair, eyewear, outfit construction, opaque fabric, waist line, proportions, outline, and palette;
- target 85–90% subject height, 12–24 px top margin after processing, about 12 px below the waist crop, and about 50–60 px ordinary side margins;
- the natural cutoff at the waist is correct and must remain stable;
- meaningful pose changes with a natural loop from frame 5 back to frame 1;
- exactly two connected visible arms and exactly two hands, with intentional fingers for the gesture;
- complete hair, headwear, hands, props, and expression accents inside a safe area;
- a laptop or wide prop may use more width, but it must not noticeably reduce the face size or cover the face;
- pure solid {chroma} background in every panel;
- no words, labels, numbers, watermark, borders, scenery, or cast shadow.

Only an explicitly requested cool action may replace permanent prescription glasses with sunglasses. Never stack two pairs of glasses.
"""


def main() -> None:
    args = parse_args()
    run_dir = args.run_dir.expanduser().resolve()
    request_path = run_dir / "request.json"
    identity_path = run_dir / "identity-lock.json"
    if not request_path.is_file() or not identity_path.is_file():
        raise SystemExit("Run is missing request.json or identity-lock.json.")

    request = read_json(request_path)
    identity = read_json(identity_path)
    if identity.get("status") != "approved" and not args.allow_draft:
        raise SystemExit("identity-lock.json must have status=approved before creating action jobs.")

    canonical_source = args.canonical_base.expanduser().resolve()
    if not canonical_source.is_file():
        raise SystemExit(f"Canonical base does not exist: {canonical_source}")
    canonical_destination = run_dir / "references" / "canonical-base.png"
    if canonical_source != canonical_destination:
        shutil.copy2(canonical_source, canonical_destination)

    presets = read_json(PRESETS_PATH)
    manifest = read_json(SAMPLES_MANIFEST_PATH)
    framing_reference = (SAMPLES_DIR / manifest["framing_reference"]["path"]).resolve()
    jobs = []
    prompts_dir = run_dir / "prompts" / "actions"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    for index, slug in enumerate(request["actions"], start=1):
        if slug not in presets["actions"]:
            raise SystemExit(f"Unknown action preset: {slug}")
        action = presets["actions"][slug]
        sample_entry = manifest.get("actions", {}).get(slug)
        approved_sample = (SAMPLES_DIR / sample_entry["path"]).resolve() if sample_entry else None
        style_reference = approved_sample or framing_reference
        if not style_reference.is_file():
            raise SystemExit(f"Missing approved sample or framing reference for {slug}: {style_reference}")
        prompt = build_prompt(identity, action, slug, approved_sample is not None)
        prompt_path = prompts_dir / f"{index:02d}-{slug}.md"
        prompt_path.write_text(prompt, encoding="utf-8")
        jobs.append(
            {
                "index": index,
                "slug": slug,
                "name_zh": action["name_zh"],
                "prompt": str(prompt_path),
                "inputs": [str(canonical_destination), *request["references"], str(style_reference)],
                "approved_sample": str(approved_sample) if approved_sample else None,
                "sample_role": "style, half-body scale, composition, and motion rhythm only",
                "output_dir": str(run_dir / "generated" / slug),
                "alignment": action["alignment"],
                "wide_prop": action.get("wide_prop", False),
                "framing": presets["framing_defaults"],
                "durations_ms": action["durations_ms"],
                "chroma_key": identity.get("chroma_key", "#FF00FF"),
                "status": "pending",
            }
        )

    write_json(
        run_dir / "jobs.json",
        {
            "schema_version": 1,
            "frame_count": presets["frame_count"],
            "canvas": presets["canvas"],
            "max_kb": presets["max_kb"],
            "framing_defaults": presets["framing_defaults"],
            "approved_sample_manifest": str(SAMPLES_MANIFEST_PATH),
            "jobs": jobs,
        },
    )
    progress_path = run_dir / "progress.json"
    progress = read_json(progress_path) if progress_path.is_file() else {}
    progress.update({"identity_lock": "approved", "canonical_base": "approved", "jobs": "created"})
    write_json(progress_path, progress)

    print(f"JOBS\t{len(jobs)}")
    print(f"JOBS_FILE\t{run_dir / 'jobs.json'}")
    print(f"FIRST_PROMPT\t{jobs[0]['prompt'] if jobs else ''}")


if __name__ == "__main__":
    main()
