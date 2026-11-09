# Clira — AI YouTube Manager Build Pack

**Status:** Architecture and implementation specifications, **not executable software**.  
**Prepared:** 2026-11-09  
**Product name:** **Clira**. **Repository folder:** `clira`.  
**Primary builder:** Antigravity on Ubuntu.  
**Hard constraint:** **No Hermes Agent.** Lemo-Opuscar is a **separate optional video-production adapter**, not part of the agent core.

## Mission
Build **one natural-language YouTube channel manager**, not eleven disconnected slash commands. A channel owner asks the agent to research topics, plan a calendar, write scripts, manage channel metadata, review comments, track analytics, prepare videos and — with configured approval — upload privately and schedule publishing.

The agent should work for technology explainers, music channels, gaming, education, and any other niche. Channel identity, permissions and context must never leak across connected channels.

## Reading order for Antigravity
1. `AGENTS.md` — binding implementation instructions.
2. `docs/01_PRODUCT_SPEC.md` — user-facing capabilities and boundaries.
3. `docs/02_ARCHITECTURE.md` — components, major data flows, and separation.
4. `docs/03_AGENT_CORE.md` and `docs/04_TOOL_CONTRACTS.md` — agent runtime and tool permissions.
5. `docs/05_YOUTUBE_OAUTH_APIS.md` and `docs/09_SECURITY_APPROVALS.md` — API and write-safety rules.
6. `docs/06_DATA_MODEL.md`, `docs/07_JOBS_SCHEDULER.md` — persistent state.
7. `docs/08_CONTENT_INTELLIGENCE.md`, `docs/10_PRODUCTION_ADAPTER.md`, `docs/11_ANALYTICS_COMMUNITY.md` — workflows.
8. `docs/12_INTERFACE.md` — dashboard and CLI.
9. `docs/13_IMPLEMENTATION_PLAN.md`, `docs/14_ACCEPTANCE_TESTS.md` — milestones and proof.
10. `docs/15_NAME_RESEARCH.md` — previous name research and collision notes; Clira is selected.
11. `docs/16_ANTIGRAVITY_START_PROMPT.md` — one prompt to initiate implementation.
12. `docs/17_DECISIONS_AND_OPEN_QUESTIONS.md` and `docs/18_SOURCES.md`.
13. `docs/19_CLIRA_BRAND_IDENTITY.md` — selected Clira name, persona, and future mascot direction.

## First release definition
The MVP is **not** a dashboard mockup. It succeeds if the user can: connect one channel using OAuth, ask "How did my latest five uploads perform?", obtain a sourced answer with real numbers, ask for the next three content ideas, create and approve metadata, import a completed MP4, upload it **private** after approval, and retrieve the resulting video ID. Every write is logged.

## Existing environment to inspect; do not assume its health
- `~/youtube-studio` — existing studio/CLI implementation.
- `~/lemo-opuscar` — optional external renderer.
- `~/.gemini/config/plugins/youtube-agent` — existing strategy tools (11 skills, 6 scripts reported).
- `/home/$USER/.local/bin/studio` — existing CLI, if present.

Reuse only well-tested modules behind typed adapters. Do not let a failed or absent optional renderer stop channel management.

## Safety defaults
- Advisor/preview mode first; no live YouTube writes until explicitly enabled.
- Uploads explicitly **private**, never rely on API default privacy.
- Public publishing, scheduled publication, comment posting, moderation, deletion and broad metadata rewrites require owner approval.
- Per-channel OAuth and access boundaries; do not mix up channel IDs.
- Copyright and provenance gate before uploads. Music from a third-party song is **not** assumed licensed.
- No scraping through unauthorized means, no fabricated statistics, no mass repetitive spam.
- Do not claim technical tests prove that visuals look good.

## Suggested repository layout
```
clira/
  app/agent/                # model, planning, policy, tool-calling
  app/tools/                # typed YouTube/channel/content tools
  app/integrations/         # Google OAuth, Data API, Analytics, optional renderer
  app/jobs/                 # queue, scheduler, resume
  app/storage/              # SQLite and migrations
  app/web/                  # local API + minimal dashboard
  app/cli/                  # command-line interface
  tests/
  docs/
```

The structure is a proposal; inspect existing reusable code before finalizing it.
