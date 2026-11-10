# Borderless logo and animated README

The logo retains Clira's approved character identity: short irregular hair, fine round glasses,
large headphones and a hoodie. No enclosing border, badge or decorative circle is added.

| Asset | Format and dimensions | Use |
| --- | --- | --- |
| `clira/web/assets/clira-logo.png` | 512 × 512 RGBA PNG | Optional transparent logo download |
| `clira/web/assets/clira-logo-black.png` | 512 × 512 RGB PNG | Default borderless logo on solid black; README and touch icon |
| `clira/web/assets/clira-icon.png` | 96 × 96 RGB PNG | Small browser favicon |
| `docs/media/clira-banner.svg` | 1200 × 230 SVG | Borderless gold wordmark and current tagline |
| `docs/media/character/clira-character.gif` | 360 × 437, 133 frames, ~16.6 seconds | Character reactions, ~2.84 MB |
| `docs/media/character/clira-workspace.gif` | 960 × 675, 104 frames, 10.4 seconds | Actual offline website recording, ~2.70 MB |
| `docs/media/character/character-poster.png` | 420 × 510 PNG | Static alternative to the character GIF |

The transparent alternative is a high-quality Lanczos export of the canonical V2 neutral texture.
The default black-background logo was made with built-in image generation, inspected, then exported
at 512 px. The small browser icon is a 96 px export of that black-background logo. The original approved portrait and character textures
are unchanged. PNG masters remain in the task workspace under `outputs/Clira-readme/logo/`.

## Black-background variant prompt

Use case: identity-preserve / logo-brand. Edit target: the supplied Clira neutral portrait.
Create a square production-ready Clira logo variant. Change ONLY the transparent background to
perfectly flat solid black (#000000), and remove any stray background edge pixels. Preserve the
character EXACTLY: same face, pose, proportions, detailed black and white linework, naturally irregular
short wavy hair, fine round glasses, large headphones, freckles, hoodie and silhouette. Center the
existing entire portrait with generous safe margin on all sides, so hair and shoulders do not clip.
No rounded-square frame, no border, no circles, no badge, no text, no new ornament, no gold/neon,
no stylistic redesign. It must look like the existing Clira character on pure black, not a new character.
Sharp monochrome anime brand mark, suitable for GitHub and web application icon.

## Animation provenance

The character GIF records the **shipped** `character.js`, `character.css` and image-backed SVG in a
small isolated presentation page. Hover, clicks, double-clicks and circular-pointer movement are real
browser inputs. Attachment/thinking/error samples feed the existing local presentation event API;
they do not claim a model response, upload or verified account outcome. The caption says so.
The cursor overlay only makes those real pointer inputs visible in the capture.

The workspace GIF is converted from the continuous real-browser recording made by
`tests/browser_character.py`, using Clira's actual offline demo backend. It shows synthetic channel
content and local character reactions. No real Google model request or YouTube mutation was made.

GIFs use finite 48/128-color palettes, rectangle differencing and 8/10 fps rather than embedding
multi-megabyte video frames at full desktop resolution. An initial 6.3 MB character export was reduced
to ~2.84 MB while retaining all expressions, linework and captions. A static alternative is linked
beside the animation. GIF playback is independent of the website's motion setting; Full/Reduced/Off
controls apply to the application character.

## Rebuild

```bash
uv run --locked --extra dev python scripts/make_character_readme_media.py --output /absolute/output
```

This requires Playwright Chromium and ffmpeg, and never starts an agent or calls a provider API.
The script routes every browser request to local project files; missing routes fail closed.
Generate the workspace recording with `tests/browser_character.py`, then encode its WebM with
ffmpeg at 10 fps / 960 px and a 128-color palette. New clips should retain the explicit demo label.
