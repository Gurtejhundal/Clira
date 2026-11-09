# 06 — SQLite Data Model

Use SQLite with migrations, foreign keys, unique constraints and transactional writes. Never store raw OAuth tokens or API keys inside the analytics/content database.

## Proposed entities
| Entity | Main fields | Constraints |
|---|---|---|
| `channels` | `id`, `youtube_channel_id`, `display_name`, `niche`, `status`, `created_at` | `youtube_channel_id` unique |
| `oauth_connections` | `id`, `channel_id`, `secret_ref`, `scope_set`, `last_verified_at`, `status` | token is referenced, not stored in DB |
| `channel_profiles` | `channel_id`, `language`, `voice`, `content_rules_json`, `timezone`, `updated_at` | one profile/channel |
| `conversations` | `id`, `channel_id`, `owner_id`, `summary`, `created_at` | scoped |
| `content_ideas` | `id`, `channel_id`, `title`, `premise`, `sources_json`, `status` | keep rejected too |
| `content_briefs` | `id`, `idea_id`, `format`, `script`, `storyboard_uri`, `version`, `status` | versioned |
| `assets` | `id`, `channel_id`, `path`, `sha256`, `mime`, `rights_status`, `provenance_json` | dedupe on hash+channel where useful |
| `videos` | `id`, `channel_id`, `asset_id`, `youtube_video_id`, `privacy`, `status`, `metadata_json` | unique remote ID |
| `jobs` | `id`, `channel_id`, `type`, `state`, `attempts`, `input_json`, `result_json`, `next_run_at`, `last_error` | transactional state |
| `approvals` | `id`, `channel_id`, `operation_type`, `target_hash`, `approved_by`, `expires_at`, `used_at`, `status` | scoped and expiring |
| `tool_executions` | `id`, `job_id`, `tool_name`, `request_hash`, `outcome`, `source_ref`, `at` | redacted |
| `analytics_snapshots` | `id`, `channel_id`, `video_id`, `range_start`, `range_end`, `metrics_json`, `observed_at` | freshness |
| `comments` | `id`, `channel_id`, `youtube_comment_id`, `video_id`, `text`, `status`, `fetched_at` | respect privacy/retention |
| `reply_drafts` | `id`, `comment_id`, `text`, `status`, `approved_at` | never silently post |
| `schedule_rules` | `id`, `channel_id`, `job_type`, `timezone`, `rule`, `enabled` | opt-in |
| `audit_events` | `id`, `channel_id`, `actor`, `action`, `object_id`, `decision`, `at`, `metadata_json` | append-only |

## Example operational SQL (illustrative; revise in migrations)
```sql
CREATE TABLE IF NOT EXISTS channels (
  id TEXT PRIMARY KEY,
  youtube_channel_id TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  channel_id TEXT NOT NULL REFERENCES channels(id),
  job_type TEXT NOT NULL,
  state TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  attempt_count INTEGER NOT NULL DEFAULT 0,
  payload_json TEXT NOT NULL,
  next_run_at TEXT,
  updated_at TEXT NOT NULL
);
```

## Multi-channel invariants
- Every channel-owned row carries `channel_id`; queries check it.
- Do not identify channels by display name or handle. A human can rename those.
- Before external writes, prove OAuth connection resolves to intended immutable YouTube channel ID.
- Separate metrics, editorial memory and upload queue across channels.

## Data retention and export
- User can inspect/edit/delete locally stored channel profiles and ideas.
- Logs redact tokens and comment personal data where possible.
- Store analytics snapshots only as long as useful for trend analysis.
- Support backup/export; protect OAuth/keyring items separately.
