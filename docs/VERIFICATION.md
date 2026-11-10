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
