# Changelog

## 1.0.0rc1 · unreleased local candidate

- Replace the simplified live-character drawing with faithful portrait textures, eight restrained
  expressions and a dedicated blink. Clip facial changes over a shared silhouette, with subtle head,
  breathing and iris motion. Keep the existing event controller, motion controls and agent backend.
  Load expressions on demand; retain the approved PNG on artwork failure and the terminal's Braille.
  Add reproducible identity/expression previews, prompt provenance and texture-failure browser checks.

- Make timezone setup accept case/spacing variants and unambiguous city names. Support skip/unknown
  with an explicit UTC fallback, show the saved timezone, and preserve progress after invalid input.

- Review follow-up: accept dotted Gemini auth keys, recover connection setup after errors,
  atomically claim Telegram updates and pairing codes, and reject malformed model responses with
  redacted domain errors. Preserve the existing visual layout and account-write policy.

- Personal creator setup with 19 resumable questions, explicit profile review, local memory,
  editable preferences, optional masked Gemini/YouTube/Telegram connection setup and a personalized
  first project. Add inspect/remember/forget commands and opt-in saved-memory context. Telegram
  polling shares the existing agent and saved sessions after expiring single-use private pairing;
  account approvals/execution remain local. No live provider verification is implied.
- Restrict source distributions to product/source folders and reject generated/private entries;
  prevent recursive inclusion of prior builds and local runtime data.

- Center and lower the sidebar wordmark with top padding; left-align composer question labels
  with the answer field. Add a transcript scrollbar and mouse-wheel scrolling. Recognize reported
  Shift+Enter and Shift+Backspace via CSI-u/xterm encodings, preserving Ctrl+J, `/back` and ordinary
  Backspace editing.

- Persistent split terminal: fixed Clira lettering, portrait and help sidebar; independently
  scrollable conversation; fixed multiline composer. Page Up/Down browse history and Ctrl+End
  follows the latest message. Responsive compact header, retained input across resize, working
  completion/history search, light/dark/mono themes and legacy inline fallback. Existing typed
  tools, SQLite sessions, exact owner approvals and execution policy remain in use.

- Add terminal `/back`, previous-question navigation and `/cancel` during setup. Retain answers
  when revisiting questions, and preserve the current session when returning from the start menu.
  `0` returns to the active workspace; the channel picker also accepts `/back`.

- Restore the owner-preferred large CLIRA wordmark, rounded frame and portrait/status composition.
  Apply the supplied Ink/Ivory and Antique Gold palette, including matching prompt colors, readable
  secondary text and light/dark/mono fallbacks. Keep responsive status composition, guided
  onboarding, readable help/records/owner review, Markdown replies and real source receipts.
  Remove the accidentally copied spec footer from the portrait and fix slash-command Tab completion.
- Terminal-first prompt_toolkit client with approved Braille asset, width/no-color fallbacks,
  local launch planning, slash commands, titled saved sessions and owner confirmation.
- Additive migration 2 preserves v0.1 conversations; terminal and website share session IDs.
- Five-step website launch, session search/resume, light/dark themes and readable mobile layouts.
- Actual local thumbnail template/import/preview and manual timed captions import/edit/preview.
- Hashtags, validated chapter timestamps, title alternatives and hashed packaging manifests.
- Separate approved official thumbnail/caption upload adapters; uncertain outcomes stop for review.
- Owner-initiated read-only website OAuth with exact immutable channel review, reusing existing flow.
- CI no longer creates tags or GitHub releases. No stable v1 release or live success claim.
- Follow-up audit: persisted monochrome terminal theme, recoverable first-run input/OAuth errors,
  correct MIME after SRT/VTT conversion, and tag limits including YouTube quote/separator accounting.


## 0.1.0 — 2026-11-09

First public MVP preview: single-agent runtime, channel-scoped state, Google/Gemini adapters,
content and analytics tools, media validation, exact approvals, durable private-upload jobs,
publication/community request paths, dashboard and CLI.

Includes captured demo media, setup and architecture documentation, 61 backend checks, and an
isolated desktop/mobile browser workflow. Live-channel verification remains pending account setup.
