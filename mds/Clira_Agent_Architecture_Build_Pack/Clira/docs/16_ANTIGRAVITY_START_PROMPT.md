# 16 — Paste This Into Antigravity

You are implementing a **general-purpose single-agent YouTube channel manager** for my Ubuntu computer. I have provided a ZIP containing `AGENTS.md`, `README.md`, and detailed specs in `docs/`.

**Read `AGENTS.md` and all essential specs before coding.** The documentation is the product contract, not an excuse to write more documents instead of working software.

Goals:
1. One conversational AI manager for authorized YouTube channels (analytics, research, scripts, metadata, approvals, uploads, community, scheduling).
2. Reuse my existing `~/.gemini/config/plugins/youtube-agent` scripts as internal functions where appropriate; its repository does **not** implement YouTube publishing.
3. Google OAuth and official YouTube Data/Analytics APIs for authenticated operations.
4. Per-channel memory and strict channel separation.
5. Reliable SQLite jobs, retries, audit history and private-first uploads.
6. Minimal local UI and a useful CLI.
7. Lemo-Opuscar remains **external and optional**, connected via provider adapter later.
8. **Do not install Hermes or build a multi-agent framework.**

Inspect `~/youtube-studio`, `~/lemo-opuscar` and the installed skill folders without deleting anything. Verify available dependencies instead of trusting previous 100% claims.

Start with **M0–M1** in `docs/13_IMPLEMENTATION_PLAN.md`: actual repository layout, migrations, mock tools, tool-calling agent loop, permission checks and CLI. Test locally and show commands/results. Continue to Google OAuth and read-only YouTube API integration if account credentials are available; if not, stop that specific step and proceed with independent code.

Never upload, publish, delete, post comments, or spend money before approval. Explicitly default all YouTube uploads to private, and ensure public publishing is a separate approval step. Keep secrets out of git and logs.

For every milestone report: files changed, tests executed, pass/fail, real vs mocked integrations, exact next command, blockers. Avoid fake progress and huge markdown-only deliverables.

Use **Clira** as the product name and `clira` as the application package/repository name. Keep `APP_DISPLAY_NAME=Clira` configurable. Brand rules are in `docs/19_CLIRA_BRAND_IDENTITY.md`.
