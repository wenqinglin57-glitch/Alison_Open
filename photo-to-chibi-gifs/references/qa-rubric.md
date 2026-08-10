# QA rubric

## Automated requirements

- Exactly the requested GIFs and order; standard mode contains nine.
- Exactly `240×240`, five frames, looping, true transparency, and no more than `500 KB` per GIF.
- Main subject height is approximately 85–90% of the canvas.
- Main subject top is normally 12–24 px and its waist anchor is about 12 px from the bottom.
- Ordinary actions normally leave about 50–60 px on each side; wide props may use more width without a large face-size change.
- Face height and eye-line position stay within configured cross-action tolerances.
- No near-chroma fringe and no tiny isolated opaque color components.
- Adjacent frames contain detectable motion.

The natural waist cutoff is correct composition, not an error.

## Required frame-by-frame review

Inspect `qa/contact-sheet-all-frames.png` and the original GIFs after automated validation:

- exactly two hands; no missing hand, third hand, disconnected arm, fused palm, or incorrect gesture fingers;
- props are single, stable, connected where appropriate, and never floating, duplicated, or deformed;
- adult age presentation, face shape, jaw, midface, hair, eyewear, clothing layers, print, and watch do not drift;
- face size, eye height, shoulder width, waist line, and crop stay consistent across frames and actions;
- computer and wide effects do not shrink the person noticeably;
- animation communicates the named action and loops naturally from frame 5 to frame 1.

Regenerate artwork for anatomy, identity, age, outfit, prop, or semantic failures. Reprocess locally for transparency, chroma fringe, isolated pixels, scale, waist anchor, timing, palette, or file-size failures.
