# Setup and runtime review follow-up

Reviewed the local personal-setup commit together with the existing terminal, agent, channel-policy,
API, session, media-packaging and release paths. Kept the existing one-agent architecture and visual
layout. This is a functional/code review with local regressions, not proof of live provider success.

## Corrections

- **Gemini auth keys:** setup previously rejected dots, so newer `AQ.` authorization keys could not
  be entered. Treat credentials as opaque bounded values, allow dots, and reject control characters
  and whitespace. Recognize the new prefix in profile/memory credential rejection too. Keys stay
  in masked input and owner-only secret storage. Native REST continues using `x-goog-api-key`,
  consistent with [Google's key documentation](https://ai.google.dev/gemini-api/docs/api-key).
- **Recoverable setup errors:** connection validation/provider errors now show a redacted explanation
  and offer retry or cancel, preserving the creator profile. They no longer terminate first-run
  setup. Skipping connections keeps existing configuration. Environment key overrides are disclosed
  without displaying either key. Final project choice clarifies that a connected channel may be kept.
- **Atomic Telegram state:** duplicate-update claims and pairing-code consumption now use SQLite
  immediate transactions. Two local pollers cannot process the same update or claim one pairing code
  for two different users. Unknown write outcomes remain conservative: no automatic replay.
- **Malformed model responses:** invalid JSON, content shapes and non-object parts produce a
  recoverable domain error instead of escaping the chat loop as a Python traceback. No raw provider
  response or credential is put in that error.

## Preserved and checked

Setup progress and review, profile edits/deletion, channel-scoped notes and model-context consent,
masked credential entry, local project creation, legacy quickstart, persistent terminal layout,
keyboard/mouse controls, resizing, shared sessions, website flows, asset/caption packaging, exact
approvals, private-first account writes and unknown-outcome recovery retain their existing paths.
The tests include actual terminal processes and VT screen assertions, concurrent SQLite claims,
HTTP mocks, API/policy isolation and browser workflows.

Source distributions use an explicit source-folder allowlist. The builder rejects generated/private
paths and credential-like JSON files. Clean installs exercise wheel, source ZIP and sdist, including
first-run setup and both terminal layouts. User credentials and local `.clira` state are excluded.

No real Gemini generation, Telegram messages or Google account mutations were performed for this
review. Live Gemini/model availability, Google OAuth/channel reads, private-upload approval and
Telegram pairing still need owner participation. The screenshot credential is not copied into code,
tests, documentation or preview artifacts. Stable v1.0.0 remains untagged pending its live gates and
explicit release approval.
