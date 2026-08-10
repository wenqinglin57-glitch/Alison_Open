---
name: photo-to-chibi-gifs
description: Turn 2–3 real-person portrait photos into a consistent large half-body chibi/Q-version transparent animated GIF expression pack. Use when a user uploads human photos and asks for Q版表情包, animated stickers, transparent reaction GIFs, the default nine-action pack, or a small test pack based on that person's likeness. Preserve identity, adult age presentation, hair, eyewear, outfit, waist framing, hand anatomy, props, transparency, 240×240 dimensions, five-frame motion, and a 500 KB per-file limit.
---

# Photo to Chibi GIFs

Create a reusable chibi identity from 2–3 portrait photos, generate action keyframes with `$imagegen`, and turn them into validated transparent GIFs. Use a large, stable head-to-waist composition by default.

## Dependencies

- Use `$imagegen` for all character and animation artwork. Do not draw or synthesize the character with local code.
- Use `view_image` to inspect every supplied reference, the canonical base, the approved action sample, and every generated frame.
- Use the bundled Codex Python runtime with Pillow for the scripts in `scripts/` when the system Python lacks Pillow.

## Defaults

- Generate these nine standard actions in this exact order: `eating`, `happy`, `busy-typing`, `angry`, `peace`, `wave`, `crying`, `thumbs-up`, `embarrassed`.
- Generate `eating`, `happy`, and `busy-typing` when the user explicitly requests a quick test.
- Keep every other preset in `assets/action-presets.json` available only when the user explicitly asks for it.
- Output five-frame looping GIFs at `240×240`, transparent background, no words, no watermark, and no more than `500 KB` each.
- Use a large half-body composition from headwear or hair top to the waist. Do not show legs or shoes by default.
- Keep hair, headwear, both hands, visible arms, and action props complete. A natural cutoff at the waist is correct and must not be treated as a crop defect.
- Target 85–90% subject height, 12–24 px top margin, about 12 px bottom margin, and about 50–60 px side margins for ordinary actions.
- Allow a modestly wider composition for a laptop or horizontal prop, but keep face size, eye height, and waist anchor close to the other actions.
- Use sunglasses only for an explicitly requested `cool` action. If prescription glasses are permanent, sunglasses replace them instead of stacking on top.
- Package the GIFs, a first-frame contact sheet, an all-five-frames contact sheet, and a validation report.

Read `assets/action-presets.json` for action semantics, framing defaults, timing, required elements, and forbidden errors.

## Workflow

### 1. Prepare a run

Choose an output directory inside the user's workspace. Run:

```powershell
<PYTHON> scripts/new_run.py --reference <photo1> <photo2> [<photo3>] --output-dir <run-dir> --character-name <name>
```

Use `--mode quick` only for a requested trial. Use `--actions <slug...>` for an explicitly requested custom subset. Use `--identity-preset lanku` only when the user is creating LanKu; never apply that preset to other people.

The helper copies references into the run, creates output folders, and writes a draft `identity-lock.json`.

### 2. Build the identity lock

Inspect all reference photos. Read `references/identity-prompting.md`, complete `identity-lock.json`, and change `status` to `approved`.

- Let the clearest face photo control facial identity and age presentation.
- Let explicit outfit instructions and the designated outfit photo control clothing.
- Treat transparent prescription glasses, watches, hats, and jewelry as permanent only when the user or identity evidence supports that decision.
- Never mix clothing from face-only photos into the selected outfit.
- Record framing, target subject height, waist anchor, permanent accessories, action-only accessories, and reference priority.

Ask only when photos show different people, the face is unusable, or outfit instructions conflict materially. Otherwise make conservative choices and continue.

### 3. Generate the canonical base

Read `references/identity-prompting.md`. Use `$imagegen` with every portrait reference and `assets/approved-samples/framing-reference.png` as a composition-only reference.

Require one centered, large head-to-waist chibi character on the solid chroma color recorded in `identity-lock.json`. Preserve the locked adult age presentation, face, hair, outfit, eyewear, accessories, and waist anchor. Keep clothing opaque. Exclude scenery, cast shadows, words, watermark, borders, and unrelated objects.

The red-panda hat in the framing reference is not a default accessory. Copy only its subject size and waist crop, never its identity, clothing, or hat.

Inspect and approve the base before generating actions. Save the original as `<run-dir>/references/canonical-base.png`.

### 4. Create action jobs

Run:

```powershell
<PYTHON> scripts/create_action_jobs.py --run-dir <run-dir> --canonical-base <approved-base.png>
```

This writes `jobs.json` and one prompt under `prompts/actions/` for each requested action. Each of the nine standard jobs includes its matching approved five-frame strip from `assets/approved-samples/`.

Apply reference priority strictly:

1. Current user photos and `identity-lock.json` decide identity, face, hair, eyewear, and outfit.
2. The approved action strip decides drawing style, half-body scale, framing, spacing, and motion rhythm.
3. The action preset text supplies the remaining action details.

Never transfer the sample character's identity, face, glasses, hair, clothing, or accessories to another user.

### 5. Generate action artwork

Read `references/animation-prompting.md`. For every job:

1. Attach every path listed in the job's `inputs`, including its approved sample when present.
2. Follow the generated prompt exactly.
3. Generate one horizontal five-panel strip on the exact solid chroma background.
4. Keep face size, eye height, waist line, clothing, and overall proportions stable across all panels and actions.
5. Save the original result under `<run-dir>/generated/<action-slug>/strip.png`.

Inspect the strip before processing. Regenerate only the broken action when it contains extra or missing hands, disconnected arms, wrong fingers, malformed or duplicated props, identity drift, age drift, outfit drift, panel leakage, or inconsistent scale.

### 6. Process each action

```powershell
<PYTHON> scripts/process_action.py --run-dir <run-dir> --action <slug> --source <strip.png>
```

The helper removes chroma, clears isolated color specks, splits the strip, anchors the largest subject component to a common waist line, scales from the subject rather than detached effects, preserves a stable face size, and reduces the GIF below the size limit.

### 7. Validate and package

```powershell
<PYTHON> scripts/validate_pack.py --run-dir <run-dir>
<PYTHON> scripts/package_results.py --run-dir <run-dir>
```

Open both `qa/contact-sheet.png` and `qa/contact-sheet-all-frames.png`. Read `qa/validation.json`. Automated validation is necessary but not sufficient: inspect every frame against `references/qa-rubric.md` before delivery.

## Repair Rules

- Repair only failed actions.
- Regenerate the canonical base first when multiple actions share age, face, hair, eyewear, clothing, or proportion drift.
- Regenerate artwork for anatomy, hand, prop, identity, or semantic failures.
- Reprocess locally for chroma fringe, isolated pixels, waist anchoring, timing, palette, transparency, or file-size failures.
- Do not shrink the character merely because an effect, laptop, bowl, heart, or motion symbol expands the overall bounding box.

## Delivery

Return links to the ZIP, both contact sheets, and the validation report. State how many GIFs passed automated validation and list the manual checks that were completed or remain outstanding.
