# Clira's local companion

The web sidebar now has an original layered SVG interpretation of Clira: wavy hair, round glasses,
headphones, freckles and a hoodie. Eyes, pupils, brows, mouth shapes, hair, headphones and body are
separate groups. It is a simplified vector adaptation, not a rig extracted from the flattened PNG.
`clira/web/assets/clira-live.svg` contains the editable artwork; `character.css` provides the motion.
The original PNG remains unchanged and the exact Braille portrait is the no-JavaScript/failed-asset
fallback. Terminal artwork is unchanged.

## Interaction

- Idle breathing is a one-pixel movement over 5.5 seconds; blinking occurs every 3.5–6.3 seconds.
  An occasional head tilt is scheduled independently every 14–23 seconds.
- Nearby mouse/pen movement shifts pupils slightly. Hover or keyboard focus gives attention.
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

`state`, `motion` and `diagnostics` are read-only observations for tests. Diagnostics expose counts,
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
circular gestures, hover, keyboard, typing, held actual chat requests, timeout cleanup, distinct
mock/verified result fixtures, motion preferences, visibility/teardown, mobile tabs, touch and failed
asset fallback. It records a short real-app WebM using the existing offline chat backend.

The verified-success fixture mocks the API response; it is not evidence of another real upload.
`tests/browser_upload_flow.py` additionally checks preview/review and simulated-upload reactions.
The existing eight-view browser regression still covers clipboard copying, safe Markdown, shared
sessions, dialogs, image/caption tools, light/dark palettes and seven responsive widths.
