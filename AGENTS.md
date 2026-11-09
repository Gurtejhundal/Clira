# Clira implementation

Read the original product contract in `mds/Clira_Agent_Architecture_Build_Pack/Clira/AGENTS.md`
and `docs/PRODUCT_ANALYSIS.md`. It remains the design authority; originals are preserved.

- One Python agent with deterministic typed tools. No Hermes or autonomous subagents.
- Rendering is external and optional. Do not modify Lemo internals.
- All real account writes require a channel verification, explicit enablement, exact owner approval,
  and an audit event. Upload private; publishing is a separate request.
- Never run authenticated mutations or paid model calls during development without owner authorization.
- Keep tokens and upload session URLs in owner-only secret files, outside SQLite, frontend and logs.
- Demo mode is synthetic and must never use Google credentials.
- Run `uv run --extra dev pytest -q`, `uv run --extra dev ruff check clira tests`,
  and `node --check clira/web/app.js` after relevant changes.
- Browser checks: `uv run --extra dev python tests/browser_smoke.py` (requires Playwright Chromium).
- Report live verification separately from mock tests. Do not claim the real-channel MVP gate passed
  until the owner completes OAuth, authenticated reads, and an explicitly approved private upload.
