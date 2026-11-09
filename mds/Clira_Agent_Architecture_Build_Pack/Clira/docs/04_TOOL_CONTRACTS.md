# 04 — Tool Registry and Contracts

## Registry contract
Every tool definition must specify: `name`, `description`, JSON input schema, output schema, OAuth scopes, permission class, idempotency behavior, quota class and timeout.

## Example tool inventory
| Tool | Operation | Permission | Important precondition |
|---|---|---|---|
| `youtube.list_channels` | Authorized channel info | READ | Connected OAuth |
| `youtube.list_videos` | Owned videos and statuses | READ | Channel ID verified |
| `youtube.video_details` | Single video details | READ | Allowed video ID |
| `youtube.upload_private` | New MP4 upload | PRIVATE_WRITE | Exact file + rights + approval |
| `youtube.update_metadata` | Title/description/tags | CHANNEL_WRITE | Approval + preserve fields |
| `youtube.set_thumbnail` | Thumbnail update | CHANNEL_WRITE | Video belongs to channel |
| `youtube.schedule_video` | Set future publishAt | PUBLIC_WRITE | Private never-published video; approval |
| `youtube.publish_now` | Change visibility | PUBLIC_WRITE | Explicit confirmation |
| `analytics.channel_report` | Metrics for date range | READ | OAuth analytics grant |
| `analytics.video_report` | Video performance | READ | Valid video ID; freshness |
| `comments.list` | Get comment threads | READ | OAuth |
| `comments.draft_reply` | Generate suggested reply | DRAFT | No API write |
| `comments.post_reply` | Post comment | PUBLIC_WRITE | Approved exact text |
| `content.suggest_topics` | Topic research | DRAFT | Sources identified |
| `content.write_script` | Script document | DRAFT | Verifiable claims |
| `content.package_video` | Titles/metadata draft | DRAFT | Input video/brief |
| `calendar.add_draft` | Create local plan | DRAFT | Channel ID |
| `production.submit_brief` | Send to external engine | EXTERNAL_JOB | Provider configured, approval for cost |
| `production.import_video` | Register local MP4 | LOCAL_WRITE | Valid file path/provenance |
| `jobs.list`/`jobs.get` | Job status | READ | Owner/channel scope |
| `jobs.pause` | Pause jobs | LOCAL_WRITE | Job ID and allowed state |

## Typed command example
```json
{
  "tool": "youtube.upload_private",
  "arguments": {
    "channel_id": "UC_EXAMPLE_ONLY",
    "asset_id": "asset_001",
    "metadata_draft_id": "draft_002",
    "approval_id": "approval_003",
    "idempotency_key": "upload:UC_EXAMPLE_ONLY:asset_001:v1"
  }
}
```

## Result example
```json
{
  "ok": true,
  "video_id": "EXAMPLE_ONLY",
  "privacy_status": "private",
  "channel_id": "UC_EXAMPLE_ONLY",
  "operation_id": "op_001",
  "verified_remotely": true
}
```

## Contract rules
- Writes require exact target identifiers and approval receipts, not inferred defaults.
- API clients never let the model supply arbitrary URLs, paths or shell commands.
- Video uploads are resumable; persist the Google upload session URI in secret storage as sensitive state.
- If a write times out after a possible success, reconcile remote state before retrying to avoid duplicates.
- `videos.update` requires careful `part` selection and preservation of properties; updating omitted fields can unintentionally clear existing values.
- Tool result metadata includes `source`, `observed_at`, `quota_cost` where known, and `warnings`.
- No model-only `confidence` number should masquerade as a metric.
