# 13 — Implementation Plan and Milestone Gates

## Overall priorities
**Working agent and tools first; dashboard last.** Do not spend days polishing UI when authenticated tool calls are unimplemented.

### M0 — Environment audit
Inspect `~/youtube-studio`, installed skills, available Python, existing CLI, storage. Produce a concise report with confirmed commands and what can be reused. No destructive changes.
**Gate:** inventory with tested/unverified/blocked statuses.

### M1 — Agent skeleton (offline)
Repository, config, SQLite migrations, tool registry, mock model and mock YouTube tools, tool-call loop, permission engine, operation log, CLI. Test "show channel overview" via fixture data.
**Gate:** end-to-end simulated chat → tool → grounded response; forbidden writes blocked.

### M2 — OAuth and owned-channel read
Google OAuth, credential storage, `channels.list(mine=true)`, channel ID confirmation, owned video list, minimal analytics.
**Gate:** real authenticated read with channel ID, timestamps and correct data; no writes.

### M3 — Content intelligence
Topic proposals, duplication guard, evidence-backed scripts, title/thumbnail lint using existing YouTube Agent scripts, calendar and memory.
**Gate:** produce 3 distinct proposals for an actual channel, cite evidence where used; title scores labeled heuristics.

### M4 — Controlled private upload
Import MP4, ffprobe QC, asset hashing, approval receipts, resumable uploader, remote private-status verification, duplicate detection.
**Gate:** user-authorized private test upload verified remotely and logged (do not run automatically).

### M5 — Publishing and community
Metadata update safely, thumbnail, approved schedule, comments listing, suggested replies, separately approved posting.
**Gate:** no public/reply write without verified approval; automated tests cover rejection.

### M6 — Jobs/automation
Durable queue, state machine, retry, systemd timers disabled by default, recovery, weekly report jobs, storage preflight.
**Gate:** test missed run/restart, duplicate triggers, quota failures and pause.

### M7 — Optional production adapter
Generic provider interface, manual import, optional Lemo integration using actual supported CLI/contract, provenance/QC gate.
**Gate:** create a brief, import provider result and prepare private-upload request; renderer failure does not break channel management.

### M8 — Practical interface + hardening
Minimal local UI, approval pages, docs, migration/backup, secrets scan, real-world dry runs.
**Gate:** acceptance suite in `14_ACCEPTANCE_TESTS.md`.

## Engineering habits
- Test one feature before beginning the next; no 100% claims without execution evidence.
- No browser automation required if API supports needed action.
- Fail safely when OAuth or approvals missing.
- Keep all external writes behind audit and approval controls.
- User can stop or revoke any automation.

## MVP demo script
1. Connect account with OAuth.
2. Ask for latest five videos and views, including freshness.
3. Request three topic ideas based on recent performance.
4. Approve one content brief.
5. Import manually rendered video and QC it.
6. Review and approve private upload.
7. Verify private video ID and accurate metadata on YouTube.
8. Show pending publishing approval (do not actually publish).
