# 05 — Google OAuth and YouTube API Integration

**Important:** Check the current official documentation again during implementation. This spec reflects documentation consulted **2026-11-09**; Google changes scopes, quota rules and API behavior.

## Required Google APIs
- YouTube Data API v3 — channel data, video listing, uploads, metadata, thumbnails, comments and scheduling.
- YouTube Analytics API — channel/video metrics available to authorized owners.

## OAuth installation flow (desktop/local app)
1. User creates or selects Google Cloud project.
2. Enables both APIs and configures Google Auth Platform consent screen.
3. Creates a Desktop OAuth client.
4. Downloads client JSON **outside the repository**.
5. App launches authorization code + PKCE flow, with browser and loopback callback where supported.
6. User selects Google identity/YouTube account and grants minimum requested scopes.
7. App calls `channels.list(mine=true)` and displays the actual channel title/ID for user confirmation.
8. Bind verified `channel_id` to local profile and token record.
9. Store tokens with restrictive OS permissions or system keyring; provide disconnect/revoke path.

Do not ask users to paste OAuth refresh tokens into chat. Google app verification/testing mode and test-user restrictions must be handled explicitly.

## Suggested scope separation
- Read-only channel operations: `youtube.readonly` where supported.
- Basic analytics: `yt-analytics.readonly` plus any additional currently documented requirements for `reports.query` (verify at implementation; official page notes `youtube.readonly`).
- Upload: `youtube.upload` when sufficient.
- Metadata/comments/scheduling: scoped account-management permissions as necessary, requested only when enabled.
- Monetization analytics: separate sensitive scope only on opt-in, never MVP default.

Scopes must be chosen from current Google API reference, not guessed.

## API-specific safety notes
### Upload
Call `videos.insert` with an **explicit** `status.privacyStatus = "private"`. Current API documentation says omitted privacy may default to `public`; **do not rely on platform defaults**. Resumable upload, checkpoint state, server receipt, verify `videos.list` status.

### Scheduling
`status.publishAt` requires the video to be **private and never previously published**. When setting it via `videos.update`, include `privacyStatus=private`. A publishAt value in the past can cause immediate publication, so timezone conversion and future validation are mandatory. Re-read the target video's current status before writing.

### Metadata updates
`videos.update` may clear existing properties omitted from the request within updated parts. Fetch current state, construct the minimal safe update with fields preserved, validate preview, then verify after the call.

### AI/synthetic disclosure
API video status supports `containsSyntheticMedia`; collect accurate disclosure from user/source provenance and apply current platform guidance. Not all animation requires the same disclosure.

### Analytics
`reports.query` requires OAuth authorization, channel ID, date range, and metric/dimensions. No guarantee all YouTube Studio metrics are available by API; display unavailable metrics explicitly. Note reporting delays/timezones and keep timestamps.

### Comments
Comment retrieval and posting use relevant endpoints and scopes. Drafts are local until approved; moderation or deletion requires separately confirmed privileges.

### Quotas
Current developer quota documentation describes separate default daily buckets for `search.list` and `videos.insert`, and other endpoints pooled by units. Do **not** embed outdated assumptions such as every upload costing a fixed legacy value; build a configured quota tracker based on current Google Cloud quota display and official method costs.

## Failures to handle
- OAuth token expired/revoked.
- Wrong YouTube channel selected / brand account mismatch.
- Consent screen misconfiguration or unverified app warnings.
- Insufficient scope, quota exhausted or rate limits.
- Upload session interrupted.
- Processing rejected; copyright/duplicate problems.
- Scheduled publish time is in the past.
- Video ID stored remotely but local response lost.

## Official references
- https://developers.google.com/youtube/data/reference/rest/v3/videos/insert
- https://developers.google.com/youtube/data/reference/rest/v3/videos/update
- https://developers.google.com/youtube/data/determine_quota_cost
- https://developers.google.com/youtube/analytics/reference/reports/query
- https://developers.google.com/youtube/v3/guides/uploading_a_video
- https://developers.google.com/identity/protocols/oauth2
