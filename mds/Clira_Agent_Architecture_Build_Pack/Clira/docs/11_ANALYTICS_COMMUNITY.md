# 11 — Analytics and Community Operations

## Data sources
- Own channel videos: official YouTube Data API.
- Own channel performance: authorized YouTube Analytics API.
- Public niche examples: permitted YouTube Data API/public information; don't scrape protected Studio pages.
- Retention export supplied by user or accessible official endpoints when available. No universal assumption that every Studio graph can be queried by API.

## Metrics and interpretation
Report date range, data freshness, channel scope and units for every chart. Separate Shorts from long-form. Key measures: views, watch time, average view duration, impressions/CTR where available, audience retention when available, subscriptions attributable where available. Use RPM/revenue only when actually accessible and authorized.

## Sample report questions
- Did impressions change, or did conversion from impressions change?
- Were views driven by Shorts feed or long-form discovery?
- Where did viewers leave, if retention data exists?
- Did topics with similar length perform differently over enough samples?
- Was there an upload frequency or seasonality confound?

Never imply correlation proves causation; show confidence qualitatively with sample size and missing data.

## Daily workflow
Refresh owned videos and recent analytics → compare with prior snapshots → identify one notable observation → suggest a next action and content topic. Respect API reporting delays.

## Weekly workflow
Output a concise digest: week vs prior week, 3 lessons, 3 content experiments, 1 likely bottleneck, channel-specific editorial calendar.

## Community
Comment review types:
- Genuine question: draft concise helpful response.
- Feedback: surface in creator insight digest.
- Moderation concern: flag for manual review.
- Spam/abuse: categorize; do not automatically delete in MVP.

Posting replies requires approved exact text + comment ID + channel ID. Do not produce repetitive generic responses across many comments.

## Data freshness
Every metric is either `fresh`, `delayed`, `stale`, `unavailable` or `mock`. The UI must make these distinctions obvious.
