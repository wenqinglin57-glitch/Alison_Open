# Animation prompting

## Five-frame strip contract

Generate one horizontal strip with five equal panels and no gaps. In every panel:

- show the same large head-to-waist character with the waist naturally meeting the bottom crop;
- keep face size, eye height, hair silhouette, shoulder width, waist line, outfit, eyewear, outline, and palette stable;
- keep hair, headwear, both visible arms, exactly two hands, and the action prop complete;
- use the exact solid chroma background;
- exclude words, labels, numbers, borders, scenery, cast shadows, and watermark;
- place motion accents inside the safe area without using them to determine character scale.

The approved action strip is a style, scale, composition, and timing reference only. Current-user photos and the identity lock always override its identity and clothing.

## Motion construction

Use anticipation, action, peak, release, and settle:

1. neutral or anticipation;
2. action begins;
3. clearest peak pose;
4. release or opposite pose;
5. settle toward frame 1.

Use meaningful changes in hands, arms, face, shoulders, and props. Do not move an unchanged cutout across the frame. Anchor the face and waist unless the action specifically needs a small bounce.

For `busy-typing`, show a laptop below the face, keep the screen from blocking the face, and alternate the left and right hand on the keyboard. Exactly two hands must remain connected to their arms in every panel. Use focused eyes and a subtle upper-body rise and fall. The laptop may widen the composition but must not make the face visibly smaller than other actions.

## Repair prompts

- Extra hand: “Exactly two hands in every panel. Change the pose of the existing hand; do not add another hand.”
- Disconnected arm: “Connect each visible hand to its forearm with a continuous, anatomically readable silhouette.”
- Wrong fingers: “Redraw the gesture with a clear, intentional finger count and no fused or duplicate digits.”
- Prop failure: “Keep one consistent prop, attached to the hands where appropriate; no duplicate, floating, or deformed prop.”
- Outfit drift: “Use identical opaque garment construction and color blocks in all five panels.”
- Scale drift: “Match the approved sample's head-to-waist size; keep face height and eye line constant.”
- Chroma leak: “Use fully opaque hair and clothing; the solid chroma color must appear only in the background.”
