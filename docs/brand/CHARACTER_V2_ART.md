# Clira character V2 artwork

## Reference and generation

Primary reference: `clira/web/assets/clira-portrait.png`, 1254 × 1254 RGBA. It is unchanged.
Artwork was edited with the built-in image-generation tool on 2026-11-10, using that image as an
explicit identity reference. No external image API, Google provider call or YouTube write was used.
The first edit removed the frame; every expression then used that borderless neutral as its reference.
All nine generated source images are 1254 × 1254 RGBA: eight expressions plus a blink.

Delivery: `clira/web/assets/character-v2/*.webp`. Conversion used ffmpeg libwebp lossless mode at
compression level 6. Alpha and every visible RGBA pixel were checked against the PNG masters.
Per-file dimensions, delivery byte sizes and SHA-256 checksums are in `manifest.json` alongside them.
The neutral is 647,642 bytes; remaining textures are approximately 650–687 kB each. Only neutral is
critical at startup. Expressions are requested on demand, not all preloaded.

The source PNG masters and generated contact sheets are development deliverables under
`outputs/Clira-character-v2/` in the task workspace. The application packages the WebP textures,
editable SVG masks, controller and CSS; it does not need the source PNG duplicates.

## Prompt set

**Neutral identity extraction** (reference: approved portrait; transparent background):

> Preserve EXACTLY the original illustrated woman, detailed monochrome anime linework, original
> realistic facial proportions, small eyes, upward/right three-quarter angle, irregular short wavy
> silhouette and bangs, fine-wire round glasses, large left headphones, freckles, hoodie and shoulders.
> Change ONLY the rounded-square frame and stray border pixels: remove them. Use genuine transparent
> alpha around the character. Keep opaque black-and-white hair and hoodie intact. No redesign, text,
> props, new shading, chibi proportions, neon or hearts.

**Shared expression instruction** (reference: generated neutral; transparent background):

> Change ONLY eyes, eyelids, eyebrows and mouth. Keep the exact 1254 × 1254 canvas, pixel-aligned head,
> body, pose, silhouette, glasses, hair, headphones, neck, hoodie and transparency. No redrawing or
> recomposition and no head turn. Monochrome only. No symbols, blush, frame, chibi proportions or large eyes.

Append one expression instruction:

| Texture | Instruction |
| --- | --- |
| Curious | Raise just one eyebrow a little; a small attentive widening of the eyes, lips nearly neutral. Quietly observant, not cartoon surprise. |
| Happy | Very small closed-lip smile, subtly softened eyes, reserved and slightly awkward warmth. No wide grin or blush. |
| Surprised | Restrained mild surprise; brows slightly lifted, eyes only slightly wider, lips softly parted. No giant eyes or big O mouth. |
| Thinking | Thoughtful narrowed eyes, one eyebrow subtly engaged, tiny inward press of the lips. No hands, props or symbols. |
| Dizzy | Eyes gently closed, puzzled brows, small uncertain lip line. No spiral/X eyes or symbols. Head pose stays exact; code provides motion. |
| Concerned | Inner brows slightly raised and drawn together, sympathetic eyes, tiny closed-lip downturn. No tears or exaggerated emotion. |
| Celebrating | Eyes gently closed into a contented expression, restrained closed-lip smile. Quiet satisfaction; no cheering, hearts, sparkles, blush or pose changes. |
| Blink | Both eyelids fully and naturally closed mid-blink. Neutral brows and mouth unchanged. No smile. |

## Implementation boundary

The generated edits are consistent expression sprites, not mathematically identical complete images.
The rig deliberately ignores their outer pixels: only facial patches are composited over the same
canonical silhouette. It does not claim independently articulated hair, glasses, hands or headphones.
Neutral is faithful to the approved reference; expression changes remain restrained. An original-PNG
fallback is retained rather than replacing failed art with the old simplified cartoon.
