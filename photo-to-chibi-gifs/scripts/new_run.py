from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
ASSETS = SKILL_DIR / "assets"
IDENTITY_PRESETS = ASSETS / "identity-presets"
SUPPORTED = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def deep_merge(base: dict, override: dict) -> dict:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a portrait-to-chibi GIF run.")
    parser.add_argument("--reference", nargs="+", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--character-name", default="Character")
    parser.add_argument("--mode", choices=("standard", "quick"), default="standard")
    parser.add_argument("--actions", nargs="+", help="Explicit action slugs; overrides the mode defaults.")
    parser.add_argument("--identity-preset", help="Optional named preset from assets/identity-presets, for example lanku.")
    parser.add_argument("--outfit-notes", default="")
    parser.add_argument("--style-notes", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 2 <= len(args.reference) <= 3:
        raise SystemExit("Provide exactly 2 or 3 portrait references.")

    source_paths = [path.expanduser().resolve() for path in args.reference]
    for path in source_paths:
        if not path.is_file():
            raise SystemExit(f"Reference does not exist: {path}")
        if path.suffix.lower() not in SUPPORTED:
            raise SystemExit(f"Unsupported reference type: {path.suffix}")

    run_dir = args.output_dir.expanduser().resolve()
    if run_dir.exists() and any(run_dir.iterdir()):
        raise SystemExit(f"Output directory is not empty: {run_dir}")

    for relative in (
        "references",
        "prompts/actions",
        "generated",
        "processed",
        "final",
        "qa",
    ):
        (run_dir / relative).mkdir(parents=True, exist_ok=True)

    copied = []
    for index, source in enumerate(source_paths, start=1):
        destination = run_dir / "references" / f"photo-{index}{source.suffix.lower()}"
        shutil.copy2(source, destination)
        copied.append(str(destination))

    presets = read_json(ASSETS / "action-presets.json")
    actions = args.actions or (presets["quick_test"] if args.mode == "quick" else presets["default_order"])
    unknown_actions = [slug for slug in actions if slug not in presets["actions"]]
    if unknown_actions:
        raise SystemExit(f"Unknown action presets: {', '.join(unknown_actions)}")
    if len(actions) != len(set(actions)):
        raise SystemExit("Action slugs must not contain duplicates.")
    request = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "character_name": args.character_name,
        "mode": args.mode,
        "references": copied,
        "outfit_notes": args.outfit_notes,
        "style_notes": args.style_notes,
        "actions": actions,
        "identity_preset": args.identity_preset,
        "framing": presets["framing_defaults"],
        "approved_sample_manifest": str(ASSETS / "approved-samples" / "manifest.json"),
        "output": {
            "width": presets["canvas"],
            "height": presets["canvas"],
            "frames": presets["frame_count"],
            "max_kb": presets["max_kb"],
            "transparent": True,
        },
    }
    write_json(run_dir / "request.json", request)

    identity = read_json(ASSETS / "identity-lock-template.json")
    if args.identity_preset:
        if not args.identity_preset.replace("-", "").isalnum():
            raise SystemExit("Identity preset names may contain only letters, digits, and hyphens.")
        preset_path = IDENTITY_PRESETS / f"{args.identity_preset}.json"
        if not preset_path.is_file():
            raise SystemExit(f"Unknown identity preset: {args.identity_preset}")
        identity = deep_merge(identity, read_json(preset_path))
    identity["character_name"] = args.character_name
    identity["reference_roles"] = [
        {"path": path, "role": "unassigned", "notes": ""} for path in copied
    ]
    if args.outfit_notes:
        identity["outfit"]["user_notes"] = args.outfit_notes
    if args.style_notes:
        identity["style"]["user_notes"] = args.style_notes
    write_json(run_dir / "identity-lock.json", identity)

    progress = {
        "identity_lock": "draft",
        "canonical_base": "missing",
        "jobs": "not_created",
        "processed_actions": [],
        "validation": "not_run",
        "package": "not_created",
    }
    write_json(run_dir / "progress.json", progress)

    print(f"RUN_DIR\t{run_dir}")
    print(f"MODE\t{args.mode}")
    print(f"ACTIONS\t{len(actions)}")
    print(f"IDENTITY_LOCK\t{run_dir / 'identity-lock.json'}")
    print("NEXT\tInspect the references, complete identity-lock.json, and set status to approved.")


if __name__ == "__main__":
    main()
