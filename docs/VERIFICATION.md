> Historical v0.1.0 evidence. For the current candidate, see [v1 RC verification](VERIFICATION_V1_RC.md).

# Verification · 9 November 2026

**Environment:** Ubuntu, Python 3.12.16 managed by uv; SQLite 3.53.1; ffmpeg/ffprobe present.
Dependencies are locked in `uv.lock`. No live Google authorization, live model request, or real
account mutation was performed. All external-service behavior below was simulated or transport-mocked.

## Results

| Check | Command | Observed result |
|---|---|---|
| Backend unit/integration | `uv run --locked --extra dev pytest -q` | **61 passed** in 3.20 s |
| Python lint | `uv run --locked --extra dev ruff check clira tests` | All checks passed |
| Python formatting | `uv run --locked --extra dev ruff format --check clira tests` | 18 files already formatted |
| JavaScript syntax | `node --check clira/web/app.js` | Exit 0 |
| Launcher syntax | `bash -n run.sh` | Exit 0 |
| Locked launcher | `./run.sh doctor` | Database initialized; ffprobe available; no model key/OAuth client; writes disabled |
| Browser workflow | `CLIRA_BROWSER=<installed Chromium path> uv run --locked --extra dev python tests/browser_smoke.py --output <output directory>` | Passed; eight views; 1440px and 390px; no page errors or horizontal page overflow |
| User preview | Local source-tree server at `http://127.0.0.1:8765/` | Loaded in the app browser; synthetic demo/offline labels visible |

One upstream test-only deprecation warning remains: Starlette's current TestClient warns about
its httpx transport. It did not affect the 61 passing assertions. Browser verification used the
already installed Chromium headless shell (revision 1243) through `CLIRA_BROWSER`, rather than
downloading the revision expected by the newly installed Playwright package.

## What was actually exercised

- Chat → validated tool → grounded fixture answer and persisted conversation.
- Five tool calls producing three channel-specific editorial proposals; duplicate rejection.
- Unknown/model-granted tool rejection, strict schemas and channel-override rejection.
- Missing live credentials returning AUTH_REQUIRED without guessed data.
- Cross-channel asset, job, approval, conversation and record isolation.
- Missing/empty/invalid/outside-root/symlink media rejection; real ffmpeg sample and ffprobe QC.
- Managed-copy stability, changed-byte rejection, rights/creative-review gates, model attestation rejection.
- No execution before approval, exact-payload hashing, expiry, rejection, edits invalidating consent.
- Re-preparation of safe requests; renewal retaining the same job and resumable progress;
  renewal rejection for unknown outcomes; completed uploads remaining deduplicated.
- Private-only simulated upload; repeated execution after restart returning the same receipt.
- Concurrent transactional claims with one winner; a blocked second executor leaving the running job intact.
- Pause-all, disabled live writes, past/naive schedule rejection and India-offset-to-UTC conversion.
- Public-release requests requiring separate approval and tracked private-upload history.
- Safe metadata part selection; no accidental status part in metadata updates.
- Local comment drafting with no post; uncertain comment outcomes requiring reconciliation.
- Append-only audit SQL triggers and atomic request caps.
- Mocked OAuth refresh, revoked-token handling, scope rejection, wrong-identity rejection and secret redaction.
- Mocked owned-upload listing via playlist and channel filtering; empty analytics marked unavailable.
- Mocked resumable protocol initialization, explicit private payload, 308 offsets and expired-session refusal.
- Lost-response upload test: server accepted bytes, client reported interruption, next execution queried the
  **same session**, recovered the original video ID, and did not initialize another upload.
- Session URLs stored in owner-only secret files, absent from job payloads/results.
- Mocked Gemini request shape, request cap, opaque thought signature/function ID preservation and bounded tools.
- Local API origin/Host/CSRF rejection, secret export exclusion and validated timezone errors.
- Manual production provider independence, weekly date-window separation, nonfabricated demo research,
  and registry input/output/scope/permission metadata.

## Real-browser scenarios

The reusable test starts an isolated temporary **demo** server with model calls and live writes
explicitly disabled. It checks navigation across all eight views, saves three ideas, generates a
one-second original MP4 fixture, fills the production form, runs real local media QC, reviews the
exact private preview, approves it through the confirmation dialog, runs the simulation, and checks
the completed receipt. It then drafts and simulates a separately approved comment reply and tests
the top-level pause/resume control at 390px width.

Screenshots were captured for desktop chat, mobile chat and completed operations. This verifies
the tested layouts and interactions; it is not a human review of a real production video.

## Unverified / missing

- **Authenticated live read:** no Google Desktop OAuth client or channel grant was supplied/configured.
- **Live AI behavior:** no Gemini API key was configured; no paid model call was made.
- **Actual private upload:** intentionally not run; requires account setup, rights-cleared media and exact owner approval.
- **Live public/metadata/reply mutation:** intentionally not run; requires separate grants and approval.
- **Systemd operation:** example files exist; no timer/service was installed or enabled.
- **External rendering:** optional Lemo is not executed or integrated; manual handoff works independently.
- **Future features:** thumbnail upload, complete-history pagination, retention/cohort diagnostics,
  semantic topic matching, automatic factual-source validation and hosted/team access.

The original live-channel MVP gate is still pending. Passing mock and local-browser tests does
not establish that the Google project is verified, that its quotas/scopes permit an operation,
or that the model's creative output meets the creator's needs.

## 10 November 2026 — chat upload workflow

This newer entry supersedes the historical missing-prerequisite statements above for this local checkout.
The owner completed an upload-capable Google grant and uploaded the Clira concept demo privately.
A direct authenticated read verified video `rycD06XeyGY` was private on the intended channel; the only
verification mismatch was the order of identical tags. The comparison now ignores tag order while
retaining all other metadata checks. The existing recovery job was not restarted or replaced.

The new workflow adds MP4 chat attachments (256 MiB cap), three-frame Gemini analysis under existing
provider enablement/budgets, an editable persistent chat preview, owner rights/disclosure review,
and one owner action that prepares, approves and executes the existing private-upload job.
Terminal commands `/upload` and `/upload-approve` share the same workflow. No model approval tool
was added. Captions and thumbnails still use separate exact approvals; frame samples do not
constitute audio transcription or complete video understanding.

Validation: full suite 205 passed before two additional regression cases; the final focused upload
suite is 11 passed, including duplicate/concurrent submissions, channel isolation, CSRF, invalid
media, preview/video bytes, stored conversations, sampled-frame provider mocks, tag-order handling,
and invalid-package recovery. Existing browser smoke passed eight views at 1440/1280/768/390/320.
`tests/browser_upload_flow.py` passed actual attachment → chat preview → edits → owner confirmation
→ simulated upload, with a mobile overflow check and no JavaScript errors. Ruff, formatting and
JavaScript syntax checks passed. Wheel build succeeded. New workflow tests used isolated demo data,
mock model output and simulated writes, not another authenticated upload or paid model call.


## 10 November 2026 — terminal-style web workspace

The web application now uses Clira's antique-gold frames, monochrome palette, block wordmark,
complete borderless Braille portrait and monospace controls across all eight views. The browser
remains the main daily workspace; CLI/TUI compatibility is retained. New-conversation welcome,
native text selection and Copy buttons, safe Markdown formatting, slash navigation, Shift+Enter,
and a selectable block/line cursor are implemented without a framework or backend replacement.

Validation after these changes: **207 Python tests passed**, with one upstream Starlette/httpx
deprecation warning. The final focused upload suite passed 11 tests. Ruff check/format,
JavaScript syntax, shell syntax and whitespace checks passed. Wheel build succeeded.
The expanded browser smoke test passed all eight views at **320, 390, 768, 820, 1024, 1280 and
1440 pixels**, both light/dark palettes, exact portrait bounds, clipboard copying, safe Markdown,
multiline input, Insert cursor switching, slash navigation, welcome lifecycle and shared sessions.
The separate chat-upload browser test passed actual H.264 playback, editable preview, mobile layout,
owner review and simulated private upload. Browser errors: **zero**. Screenshots were inspected.

All new model/upload execution tests used isolated demo state, mock model output and simulated
account writes. No new real upload, paid model call, stable tag or stable release was made.
See [WEB_WORKSPACE.md](WEB_WORKSPACE.md) and [CHAT_UPLOAD.md](CHAT_UPLOAD.md) for behavior and limits.


## 10 November 2026 — interactive web companion

Added an original layered SVG adaptation, a local presentation state machine and scoped app-event
hooks. Tested single versus double click, gaze/hover, circular gestures, keyboard and touch, actual
pending offline chat, timeout cleanup, preview/approval and simulated-result reactions. Verified
success is exercised with an explicitly mocked API receipt; no new real account write was made.
Full/Reduced/Off preferences, OS reduced motion, visibility, return-from-inactivity, BFCache,
teardown/late callbacks, fallback artwork and responsive navigation are covered by the dedicated
browser test. A short WebM records the actual offline application.

Final Python run: **207 passed**, one upstream Starlette/httpx warning. An initial timing-sensitive
terminal resize assertion failed while parallel browser tests ran; its isolated recheck and the
complete rerun both passed without changing terminal code or weakening that test. Existing browser
smoke passed eight views at seven widths; the chat-upload simulation and dedicated character browser
suite passed with zero JavaScript errors. Ruff check/format and both JavaScript syntax checks passed.
The original PNG and terminal Braille files are unchanged. No paid model request or live upload was
performed. The SVG is a simplified new interpretation, not independent facial layers recovered from
the original PNG. See [LIVE_CHARACTER.md](LIVE_CHARACTER.md) for implementation and behavior limits.
