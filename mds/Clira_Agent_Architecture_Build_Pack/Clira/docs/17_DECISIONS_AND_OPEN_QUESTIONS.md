# 17 — Decision Register and Open Questions

## Decisions already made
- One general YouTube channel-management agent; no Hermes.
- Single Python orchestrator; no unnecessary multi-agent framework.
- Video rendering is a separate responsibility via optional adapter.
- Reuse compatible internal tools from already-installed YouTube Agent Skill.
- Official Google OAuth + YouTube APIs, not browser automation where API suffices.
- SQLite initially; multi-channel separation from day one.
- First launch local/Ubuntu, not paid hosted SaaS.
- Private upload by default; public posting requires explicit approval.
- Music content requires verified rights.
- Branding deferred until clearance; no product name hardcoded into database.

## Safe defaults (can be changed later)
| Setting | Default | Reason |
|---|---|---|
| Model provider | Gemini configurable | Existing Antigravity ecosystem; not mandatory |
| Default mode | Advisor | No unintended writes |
| Upload behavior | Disabled until connection + approval | Safety |
| Privacy on upload | Private | Reputation safety |
| Public publishing | Per-video approval | Avoid unwanted posts |
| Comment replies | Draft only | Avoid spam/brand damage |
| Scheduled jobs | Disabled until tests | Prevent surprises |
| Rendering | Manual import first | Independent product design |
| Data store | SQLite | Simple local-first |

## Decisions to ask user only when required
1. Which Google identity and YouTube channel(s) should be connected?
2. Which Gemini/model API account is available, with what monthly cost cap?
3. Does the user want approval for every private upload, or a preauthorized private-only queue?
4. Preferred target platform: desktop-only local web app or future hosted deployment?
5. Which brand name passes actual domain/trademark clearance?

Implement everything else with reversible defaults. Do not block engineering over cosmetics.
