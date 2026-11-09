# 01 — Product Requirements

## Product thesis
A channel operator should be able to manage one or more YouTube channels by **talking to one AI assistant**, while retaining control over actions that affect their public reputation. The assistant handles research, planning, analytics, packaging, operational tasks and approved uploads. Video creation is delegated to a separate renderer or a human.

## Who uses it
- Independent creator — wants low-friction planning and publishing.
- Multi-channel owner — needs strict channel isolation and schedules.
- Small creator team — needs approval and audit history.
- Music creator — needs extra rights controls for audio assets.

## Primary jobs to be done
1. "Explain what worked this week, with numbers and sources."
2. "Find three topics that suit *this channel*; don't repeat last month's uploads."
3. "Write a 40-second script and a complete production brief."
4. "Import the finished video and check if it's ready."
5. "Upload privately to the correct channel and show me the link." (after approval)
6. "Schedule that approved video for Friday at 6 PM India time."
7. "Which comments need a reply? Draft, don't post."
8. "Make a weekly content and analytics digest."

## MVP scope (P0)
- Local-first single-user app with multi-channel support in the data model.
- Configurable Gemini-first LLM provider; vendor-neutral interface for future models.
- Chat with tool calls, clear confirmation messages and action history.
- Google OAuth channel connection; channel ID verification.
- Authenticated read-only video list, channel details and basic analytics.
- Content ideas, scripts, titles, description drafts and an editorial calendar.
- Local MP4 import; ffprobe validation; upload approval + private resumable upload.
- Stable job IDs, audit entries, retry handling and duplicate prevention.

## Next (P1)
- Real weekly analytics diagnostics with cohort/format segmentation.
- Comment queue, reply drafts, comment posting only after approval.
- Thumbnail uploads, metadata modifications, scheduled-publication workflow.
- Scheduled reports and topic-plan preparation via systemd timers.
- Production-provider adapter with optional Lemo and generic manual-video provider.

## Later (P2)
- Team roles, hosted access, subscription billing, cloud workers, smart notifications, team approval chains, more integrations. Not for initial build.

## Explicit non-goals
- Producing video animation within the agent core.
- Becoming a generic social-media scheduling platform.
- Predicting views/revenue from title scores.
- Bypassing YouTube upload quotas, Content ID or copyright.
- Automatic deletion or mass comments.
- Public autoposting without preapproved, auditable policy.

## Quality attributes
- Correct channel selection every time (never cross-account publish).
- Owner can inspect what will change before confirming.
- Long-running jobs resume after interruption with stable IDs.
- All stored channel data has timestamp, source and freshness status.
- Adapter failures do not corrupt the job database.
- Clear, minimal UI; prioritize useful workflows over animation.

## Product metrics
- % successful authenticated read requests; upload success after resume.
- Rate of operations needing manual repair.
- Duplicate uploads = zero.
- Wrong-channel writes = zero.
- Approval bypass = zero.
- Creator minutes saved per recurring workflow.
- User-rated quality of recommendations, not invented "virality scores".
