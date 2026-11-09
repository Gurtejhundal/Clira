# 12 — Local UX and CLI

## Design goals
A calm operations cockpit, not a flashy sci-fi dashboard. Keep the most important information visible: active channel, agent reasoning summary, approval requests, recent analytics and jobs waiting for review.

## Screen map
1. **Agent Chat** — ask natural language questions; see actions and sources.
2. **Channel Switcher** — channel title, immutable YouTube ID, permissions and connection health.
3. **Overview** — recent uploads and high-level performance with date ranges.
4. **Ideas & Calendar** — topic cards, briefs, statuses and duplicate warnings.
5. **Video Library** — owned uploads, privacy, thumbnails, metadata drafts.
6. **Production Inbox** — external briefs/jobs, MP4 imports, creative QA.
7. **Approvals** — show exact payload/destination/visibility before confirm.
8. **Community** — filter comments and approve suggested responses.
9. **Automations** — pause/resume schedule, last runs and failures.
10. **Settings** — OAuth, model provider, costs, rights and data controls.

## Approval UX
Show "You are about to upload [file] to [channel name + ID] as PRIVATE" with file hash, intended metadata, licensing status and a visible confirmation. For public publishing, show schedule and timezone; no easy-to-miss toggle.

## CLI (proposed interfaces, not preexisting)
```bash
yt-agent doctor
yt-agent connect youtube
yt-agent channels list
yt-agent chat
yt-agent analytics --channel <id> --days 28
yt-agent ideas --channel <id> --count 3
yt-agent videos import /path/to/video.mp4
yt-agent uploads prepare --asset <id>
yt-agent uploads approve --request <id>
yt-agent jobs list
yt-agent jobs pause <id>
yt-agent schedule list
```

`doctor` should validate config, Python version, OAuth scopes, SQLite migrations, disk space and optional renderer availability. Display actual check results, not fabricated status.

## Frontend build approach
Build CLI + API/backend first; add minimal localhost dashboard once core functions work. A lightweight Python API (e.g., FastAPI) plus minimal frontend is sufficient. Do not introduce major frontend dependencies for looks alone.
