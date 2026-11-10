# Clira implementation

Read the original product contract in `mds/Clira_Agent_Architecture_Build_Pack/Clira/AGENTS.md`
and `docs/PRODUCT_ANALYSIS.md`. Originals are preserved. For the v1 candidate, read
`CLIRA_V1_TERMINAL_WEB_MASTER_SPEC_AND_CODEX_PROMPT.md` completely; it controls UX and release scope.
Do not tag/publish stable v1.0.0 until every mandatory gate passes and the owner explicitly approves.

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
