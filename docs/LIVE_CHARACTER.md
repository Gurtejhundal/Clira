# Clira's local companion

The website uses a faithful **image-backed SVG rig**, replacing the earlier simplified vector face.
The approved 1254 × 1254 PNG remains untouched. A borderless neutral edit preserves its proportions,
linework, messy hair, round glasses, headphones, freckles and hoodie. Eight consistent expression
textures supply neutral, curious, happy, surprised, thinking, dizzy, concerned and celebrating faces.

`clira/web/assets/clira-live.svg` separates the canonical torso, head/neck, facial-feature patches,
iris texture and blink overlay. Expression textures are clipped to eyebrows, eyes and mouth; hair,
outer face, glasses silhouette, headphones and clothing always come from the canonical neutral.
This is a raster texture rig with SVG masks, **not independently redrawn vector hair or a skeletal rig**.
The head/neck masks overlap slightly to avoid an antialiased seam. No hearts, blush, spiral eyes,
colored character accents or portrait frame are added. Gold stays in the interface.

Neutral loads first. Other lossless WebP textures load only when requested and are browser-cached.
A requested expression becomes visible after its texture loads; stale loads cannot override newer
states. A missing expression falls back to neutral without altering the real operational status.
The approved original PNG is visible before JavaScript loads and remains the fallback if the SVG or
critical neutral texture fails. The terminal retains its exact Braille artwork and text interactions.

See [art provenance, prompts and limitations](brand/CHARACTER_V2_ART.md). Rebuild the identity comparison
and expression contact sheet with `uv run --extra dev python scripts/preview_character.py OUTPUT_DIR`.

## Interaction

- Idle breathing is a less than one screen pixel over six seconds; blinking occurs every 3.5–6.3 seconds.
  A head tilt below one degree is scheduled independently every 14–23 seconds.
- Nearby mouse/pen movement shifts clipped iris textures by less than one screen pixel. Hover or keyboard focus gives attention.
- A single pointer click waits 360ms to distinguish a second tap. A second click/tap within that
  window replaces the pending single reaction with delight. Keyboard Enter/Space greets immediately.
- A circular gesture needs at least 18 local samples within 1.8 seconds, over 333 degrees of signed
  travel, consistent direction and radius, and no large pointer jumps. History is capped at 80
  samples and discarded on exit from the ring. Circular reactions have a six-second cooldown.
- Typing gets attention; submitted chat requests show thinking; replies get a brief smile.
  Video attachment, preview, owner review, timeout and error events have separate expressions.
- A verified API result permits celebration. A mock result says **Demo simulation complete** and
  uses a quieter smile. The character never infers success from a click or an HTTP 200 alone.
- Returning after 30 seconds of inactivity gets a greeting unless a more important state is active.

No sentiment model, microphone, audio playback, telemetry, account tool or model call is added.
Pointer coordinates exist only in short-lived local memory. Ordinary text selection and copy work.
The character is a labeled native button, supports touch and keyboard, and never submits a form.

## State and event contract

`character.js` owns presentation and exposes `window.cliraCharacter.emit(event, detail)`. App handlers
supply events; the controller cannot invoke agent or account actions.

| Event | Detail | Effect |
| --- | --- | --- |
| `request:start` | `{id, kind: 'thinking' or 'uploading'}` | Tracks a real pending request by ID |
| `request:end` | `{id}` | Releases only that request, including failed calls |
| `typing` | `{active}` | Short attention lease; no message content is provided |
| `attached`, `reply`, `preview`, `error` | none | Bounded temporary expression |
| `approval` | `{source, required}` | Maintains separate queue and preview review reasons |
| `outcome` | `{verified, simulated}` | Verified celebration or explicitly simulated result |
| `conversation` | none | Clears chat-specific reactions/review, preserves queue and pending work |
| `context` | none | Clears state on channel changes |

Request IDs are released in the existing API wrapper's `finally` block. Errors override pending
work temporarily, then return to the remaining pending state. New work clears a previous temporary
reaction. Queue/preview review overrides idle gestures; playful clicks cannot replace typing,
review or pending requests. Repeated events do not restart the same expression.

`state`, `expression`, `motion` and `diagnostics` are read-only observations for tests. Diagnostics expose counts,
not pointer coordinates or chat content. `destroy()` aborts listeners/fetch, clears timers/history,
cancels the one-shot animation frame and leaves the artwork static. Visibility/BFCache suspension
pauses animations and clears ephemeral timers; pending requests survive suspension. Closing the
page destroys the controller.

## Motion settings

Settings → Appearance → **Character motion** offers Full, Reduced and Off. The preference is stored
locally. Full always honors the OS reduced-motion preference. Reduced uses static expressions with
no idle loops or pointer following; Off keeps neutral static artwork while the status text can still
report actual work. Native browser focus rings remain visible. There is no sound or flashing.

## Verification

`tests/browser_character.py` runs against a fresh offline demo server. It covers single/double clicks,
clockwise/anticlockwise circular gestures, all eight rendered expressions, lazy texture loading, hover,
keyboard, typing, held actual chat requests, timeout cleanup, distinct
mock/verified result fixtures, motion preferences, visibility/teardown, mobile tabs, touch and failed
SVG, neutral-texture and optional-expression failure recovery. It records a short real-app WebM using the existing offline chat backend.

The verified-success fixture mocks the API response; it is not evidence of another real upload.
`tests/browser_upload_flow.py` additionally checks preview/review and simulated-upload reactions.
The existing eight-view browser regression still covers clipboard copying, safe Markdown, shared
sessions, dialogs, image/caption tools, light/dark palettes and seven responsive widths.

## Deliberate fidelity limits

Facial expressions switch textures; they are not mouth/eyelid morphs or lip-sync. Blinks use a dedicated
closed-eyelid texture rather than vertically squashing open eyes. Head tilt, breathing and iris motion
are deliberately tiny. There is no hand/glasses-adjustment animation: the approved image contains no
hand rig, and inventing one would weaken identity fidelity. No model decides moods and no new agent
framework is involved. Full / Reduced / Off and the existing real-event priorities remain intact.
