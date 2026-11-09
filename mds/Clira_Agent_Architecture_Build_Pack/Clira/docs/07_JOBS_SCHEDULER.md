# 07 — Durable Jobs, Scheduling, Recovery

## Job state machine
`DRAFT -> QUEUED -> RUNNING -> AWAITING_APPROVAL -> RESUMED -> COMPLETED`. Alternatives: `FAILED_RETRYABLE`, `FAILED_TERMINAL`, `CANCELLED`, `PAUSED`.

Use specialized substates for upload: `VALIDATED -> APPROVED -> UPLOADING -> UPLOADED_PRIVATE -> VERIFIED`. No transition to `SCHEDULED/PUBLISHED` without explicit publish approval.

## Worker rules
- Store job and idempotency key **before** executing external side effects.
- Database transaction for claim/lease/heartbeat; after crash, reclaim expired leases safely.
- External writes use a reconciliation step if outcome is unknown. Don't blindly retry a timed-out upload.
- Bounded exponential backoff with jitter for retryable failures, never infinite loops.
- Concurrency limits per channel and resource; avoid simultaneous local rendering on a RAM-constrained laptop.
- Separate `draft`, `private-upload`, `public-publish` capabilities.
- All action receipts record remote IDs and verified status.

## Scheduling
Ubuntu user-level `systemd` timers are preferred for a local-first single-user app. A daily job is a trigger, not a promise that it will complete quickly. The machine must be powered on and able to run the user service; optional lingering behavior must be tested. Persistent timers may execute missed runs after startup; guard against duplicate content creation.

Suggested timers, disabled by default:
- Daily 07:00 Asia/Kolkata: fetch analytics and prepare topic recommendations.
- Mon/Wed/Fri: queue Shorts briefs; **not** public auto-posts.
- Weekly: performance digest + editorial calendar.
- On demand: upload approved private MP4; scheduling after explicit approval.

## System resource policies
- Before render/large import, check free disk and reserve space for final file + temp files.
- Use configured workspace for temporary files; clean only verified disposable data.
- Per-job network/CPU/process time limits; stop instead of corrupting assets.
- Durable logs with rotation; never put token values or full private OAuth URLs in logs.

## Job observability
Show job ID, state, last completed step, generated assets, failure reason, retry count, scheduled next action, and whether waiting for owner input. Distinguish `waiting-for-machine` from `waiting-for-approval`.

## Example status response
```json
{
  "job_id":"job_123", "channel_id":"UC_EXAMPLE_ONLY", "state":"AWAITING_APPROVAL",
  "step":"private_upload", "asset":"video_sha256_here",
  "request":"Approve private upload to channel Inside the Machine",
  "attempt_count":0
}
```
