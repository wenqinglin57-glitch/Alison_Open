# Identity prompting

## Reference authority

Assign a role to every photo:

- `primary-face`: highest authority for face shape, eye spacing, jaw, midface, and age presentation.
- `hair-profile`: authority for hair length, parting, volume, and side silhouette.
- `outfit-primary`: sole visual authority for the chosen clothing construction and color blocks.
- `identity-only`: use for the person; ignore clothing, headwear, pose, and background.

Explicit user instructions override photographs. Never average conflicting outfits or copy clothing from a face-only reference.

## Identity lock

Record visible, stable traits without guessing sensitive attributes. Complete:

- `age_presentation`: describe the visible adult or youthful presentation; explicitly block a toddler-like face when the person is an adult.
- face shape, jaw, midface, eyes, brows, nose, mouth, and distinctive features;
- hair color, length, parting, volume, and must-preserve strands;
- exact layered outfit, print placement, color blocks, opacity, and construction;
- `permanent_accessories` and `action_only_accessories`;
- `framing`, `target_subject_height_ratio`, and `waist_anchor`;
- `reference_priority` for identity, outfit, and composition.

For LanKu only, load `assets/identity-presets/lanku.json`: preserve an approximately 25-year-old presentation, mature oval face, defined jaw, normal midface, long black hair, transparent round prescription glasses, white printed T-shirt, open black sleeveless vest, and black watch. For any other person, derive these fields from that user's instructions and photos instead.

## Eyewear rules

- Keep permanent prescription glasses in every ordinary action.
- Add sunglasses only when an action explicitly requires them.
- When sunglasses are required, replace prescription glasses for that action; never stack two pairs.
- Do not inherit glasses from an identity-only photo unless the user confirms they are permanent.

## Canonical half-body prompt

Generate one neutral chibi portrait from headwear or hair top to the waist:

- subject occupies 85–90% of the 240 px height after processing;
- top margin 12–24 px and bottom margin about 12 px;
- ordinary side margins about 50–60 px;
- waist meets a stable bottom anchor and is naturally cut by the canvas;
- face size, eye height, shoulder width, and waist line match the approved framing reference;
- hair, headwear, visible arms, both hands, and required upper-body clothing remain complete;
- fabric stays fully opaque with no chroma showing through;
- use clean dark sticker linework and restrained cel shading;
- use the exact solid chroma background from the identity lock;
- exclude scenery, cast shadow, words, watermark, label, or border.

Use `assets/approved-samples/framing-reference.png` only for size and waist crop. Its red-panda hat, face, and outfit are forbidden identity sources.

## Choosing chroma

Default to `#FF00FF`. If the selected clothing or props contain strong magenta, use `#00FF00`. If both conflict, use `#0066FF`. Record the color before generating the base and never change it during a run.
