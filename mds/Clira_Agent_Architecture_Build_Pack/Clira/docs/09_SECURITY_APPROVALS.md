# 09 — Permissions, Consent, Rights, Threat Model

## Permission classes
| Class | Examples | Default |
|---|---|---|
| `READ` | list videos, fetch analytics | allowed after OAuth |
| `DRAFT` | scripts, titles, local plans | allowed |
| `LOCAL_WRITE` | edit own draft, import MP4 | allowed with workspace rules |
| `PRIVATE_ACCOUNT_WRITE` | upload private, update non-public metadata | owner confirmation initially |
| `PUBLIC_WRITE` | schedule, publish, post reply, change public metadata | explicit per-action approval |
| `DESTRUCTIVE` | delete video/comment, ban user | explicit strong confirmation / not MVP |
| `PAID_EXTERNAL` | paid LLM/renderer requests | explicit budget/policy |

## Approval receipt
Approved action is bound to **channel ID, exact operation, target ID/hash, target visibility, payload hash, approver, expiration, and single-use nonce**. The AI cannot substitute another video or metadata after approval. Invalidate approval on edits.

## Attack surface and mitigations
- Prompt injection in comments/webpages: treat as untrusted data, never execute retrieved instructions.
- OAuth token theft: OS keyring or owner-only filesystem, redact logs, restrict scope, revoke flow.
- Wrong channel upload: verify channel ID before each mutation; UI displays channel name/ID.
- Duplicate upload: idempotency plus remote reconciliation.
- Silent public publishing: hard default private; separate publish approval.
- Copyright complaints: provenance manifest, music clearance gate, no automatic rights assertion.
- PII disclosure in analytics/comments: scoped storage, redacted debug output, retention policy.
- Local file access: allowlist workspace, canonicalize paths, reject symlink traversal and arbitrary shell commands.
- Cost runaway: per-day LLM quota/budget, max tool steps, timeout and circuit breaker.

## Platform compliance
- No unauthorized scraping or circumventing rate limits.
- No automated comment spam, follow-for-follow tactics or misleading engagement manipulation.
- Automated uploads can be legitimate, but mass-produced repetitive/inauthentic output risks platform enforcement/monetization issues.
- Properly disclose realistic altered/synthetic content when required by platform rules.
- No assumption that uploading a song is licensed merely because it was used in an editing demo.

## Audit trail
Append immutable record of every attempted mutation (allowed or blocked), actor, channel, approval ID, payload hash, timestamp, outcome and verified YouTube video/comment IDs.

## Owner escape hatches
- One-click pause all schedules and disable writes.
- Disconnect OAuth, revoke credentials, clear local remembered context.
- Dry-run mode must never call mutating APIs.
- Public publishing disabled by default, no hidden config fallback.
