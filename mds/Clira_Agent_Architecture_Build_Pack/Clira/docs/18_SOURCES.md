# 18 — Sources and Verification Notes

Consulted for the 2026-11-09 specification. Recheck before implementing: these are external systems and may change.

## Official Google / YouTube
- Video upload `videos.insert`: https://developers.google.com/youtube/data/reference/rest/v3/videos/insert
- Video update / scheduled publication: https://developers.google.com/youtube/data/reference/rest/v3/videos/update
- General video status and `publishAt` requirements: https://developers.google.com/youtube/data/reference/rest/v3/videos
- API quota calculator and method limits: https://developers.google.com/youtube/data/determine_quota_cost
- YouTube Analytics reports query: https://developers.google.com/youtube/analytics/reference/reports/query
- OAuth for installed applications: https://developers.google.com/identity/protocols/oauth2/native-app
- Upload guide: https://developers.google.com/youtube/v3/guides/uploading_a_video
- General YouTube policies (check latest): https://support.google.com/youtube/answer/1311392

## YouTube skills
- https://github.com/Jakeschincariol/youtube-agent-skill — original 11 skills / 6 tools; readme confirms they **do not publish**.
- https://github.com/Jakeschincariol/youtube-agent-skill/blob/main/skills/yt-script/SKILL.md
- https://github.com/Jakeschincariol/youtube-agent-skill/blob/main/skills/yt-package/SKILL.md

## Naming collision evidence
Consult `15_NAME_RESEARCH.md` for exact web sources. Search results did **not** establish that any shortlisted brand name, social handle, or domain is legally available. The absence of an exact-match search hit is not legal clearance.

## Key current API observations
- `videos.insert`: explicitly choose `private`; omitted status can default to public.
- `publishAt`: private and never-published requirement; past timestamps can cause immediate publication.
- `videos.update`: beware omitted properties in updated parts being cleared.
- `reports.query`: authenticated metrics with some scope and metric limitations; read current scope documentation.
- YouTube quota model may change; use the current Cloud Console/project allocations, not stale constants.
