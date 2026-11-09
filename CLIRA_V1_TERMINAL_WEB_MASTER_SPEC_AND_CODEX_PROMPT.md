CLIRA v1.0.0 — Terminal + Website Master Experience, Prototype Tests & Codex Build Prompt
Document type: Single-file product, UX, architecture, implementation and release contract
Target repository: https://github.com/Gurtejhundal/Clira
Target version: 1.0.0, only after all stable-release gates pass
Previous published baseline: 0.1.0 according to repository README/release notes reviewed on 2026-11-09
Execution owner: Codex, working in the existing repository
Status: Design/build instructions. This document does not claim the code is implemented, the live YouTube APIs are verified or v1.0.0 is released.
CODEX: This entire file is your implementation brief. Read the repository and all its safety instructions before touching code. Implement the tested prototype first; then close the acceptance gaps; then cut a release candidate. Do not tag v1.0.0 unless the release gates below pass with evidence.

0. The product in one sentence
Clira is one YouTube-specialist AI agent that helps a creator launch a new channel or manage an existing one, through a conversational terminal and a synchronized local website. It researches, plans, writes, packages, coordinates production, manages authorized uploads and community work, and analyzes results. It does not pretend to do work or access data it cannot actually access.
Not this: a generic chatbot, 11 disconnected skills, an AI dashboard with fake metrics, a second Hermes runtime, or a video-rendering engine.
This: one agent runtime; typed tools; persisted memory and jobs; channel identity; transparent receipts; controlled real actions; two polished clients.
Two creator journeys
1. I haven't started YouTube: Start a channel workspace → define niche/audience/language → research channel positioning → choose identity → prepare first ideas, scripts and packaging → guide official YouTube channel creation → connect with OAuth → import video from any creator/renderer → rights/quality review → approved private upload → separate publication approval → learn from results.
2. I already have a channel: Connect YouTube → verify exact account/channel ID → read dated metrics and videos → inspect opportunities → generate ideas/scripts/packages → import assets → approve and execute scoped actions → monitor jobs, comments and performance → iterate.
Both journeys must be usable even if no paid AI provider or video renderer is connected; missing capabilities must be labeled, never simulated as real.
1. Baseline repository audit: preserve what exists
The repo was inspected at public main around 2026-11-09. Codex must re-audit its current checkout; the repository may have changed. The following files existed in the reviewed tree:
Source file	Current role	v1 improvement
clira/cli.py	argparse commands; basic clira chat --channel ID input loop	Bare clira launches accessible interactive experience; preserve all old commands
clira/agent.py	Single bounded agent, offline router, optional Gemini model	Better actionable, evidence-aware responses; proper tool progress and shared sessions
clira/config.py	Environment configuration and safe modes	Add UI/theme preference validation; no secret leakage
clira/contracts.py	Strict typed tool inputs/results	Add narrow types for new packaging/UX actions; never weaken validation
clira/service.py	Tool handlers, job execution, media/YouTube actions	Continue to be the single source of operational truth
clira/policy.py	Exact scoped approval and safe execution	Do not bypass or replace
clira/storage.py	SQLite and owner-only secret store	Migration for onboarding, session metadata/preferences, package assets as needed
clira/youtube.py	Demo and Google YouTube adapters	Add missing API adapters with mocks; verify live only with owner authorization
clira/media.py	ffprobe import/QC, manual production provider	Add optional real thumbnail/captions processing without coupling to Lemo
clira/api.py	FastAPI local server; session/chat/state/conversations; origin/CSRF/Host controls	Extend compatibly, not a new parallel backend
clira/web/index.html, app.js, style.css	Existing responsive eight-view local site	Readability, onboarding, shared sessions, approvals, packaging and responsive polish
docs/VERIFICATION.md	Reports 61 passing mocked/synthetic tests	Rerun and produce fresh, reproducible results
docs/SETUP.md	Live Google OAuth setup	First-run wizard and verified connection guide
mds/Clira_Agent_Architecture_Build_Pack/Clira/	Original 21-file requirements pack	Read as background, reconcile conflicts; this doc controls UX/release scope


Existing limitations reported in README: live OAuth/read/upload unverified; no verified live Gemini call; thumbnail image generation/upload and caption generation/upload not completed; richer retention diagnostics not completed; no active systemd schedule; rendering external/manual. No number of passing mock tests overrides these disclosures.
Before coding
1. Read root AGENTS.md, README.md, pyproject.toml, docs/PRODUCT_ANALYSIS.md, docs/VERIFICATION.md, docs/SETUP.md, all relevant mds/ files, agent/tool/policy/CLI/web code and tests.
2. Run the existing tests, lint, JS syntax and browser smoke checks. Save exact output to a timestamped audit report. A missing tool is NOT RUN, never PASS.
3. Verify repo status/branch. Keep user changes, existing v0.1.0 assets and original release tags untouched. Avoid destructive resets.
4. Write a compact feature matrix: IMPLEMENTED / MOCKED / UNVERIFIED LIVE / MISSING, backed by files/tests.
2. Design identity: one recognizable Clira
Clira's personality: thoughtful, practical, observant, creative, direct. She is a channel operator, not a magical goddess or a chirpy assistant. Her visual character is a monochrome ink/anime illustration: short boy-cut/wavy hair with short bangs, round glasses, headphones, calm pondering expression. No books, ornaments, laurel wreath, rings, captions or text baked into the character.
Brand rule: Two main colors—Ink and Ivory. Antique Gold is one restrained interaction accent; semantic success/warning/error tones are status colors, not extra brand colors. Don't redesign the character. Do not download unapproved mascot images or invent another generic AI logo.
Shared design tokens
Token	Light website	Dark website	Terminal guidance
bg	#F8F7F2	#171A18	Do not override user's terminal background
surface	#FFFEFA	#232723	Use only for a few panels
ink / text	#252B24	#F3F0E8	Auto-select readable ink/ivory
muted	#73776C	#ABB1A5	Muted secondary copy
border	#E4E4D9	#444A42	Thin dividers, not neon boxes
accent	#85652F	#C5A368	Gold: focus, selected items, pending owner review
success	#426C4E	#9AC6A2	Verified positive action only
warning	#8B5E1E	#E7BA71	Needs approval or incomplete
danger	#913F35	#DC8984	Errors, confirmed risky actions


Type: terminal uses user's monospace font; website uses local/system sans for body and restrained editorial serif for large headings. Website body 15–16px, secondary 13–14px (never essential 8px text), comfortable 1.5+ line height. Spacing 4/8/12/16/24/32px; small 8–12px corners; no unnecessary animations. Check WCAG text contrast rather than assuming the palette guarantees it. Honor prefers-reduced-motion, system theme, NO_COLOR, high-contrast preference and narrow screens. Don't distribute font files.
Approved mascot art source
The approved compact terminal Braille text is embedded in Appendix A of this single document. Create clira/assets/clira_braille_compact.txt from it, preserving UTF-8 and spaces. Use it on interactive startup only when the terminal width allows and output is a TTY. For website avatar, use the approved original monochrome portrait only if it is already available or supplied by the owner; if absent, use a simple Clira wordmark until supplied—never use terminal Braille as a fake bitmap.
3. TERMINAL EXPERIENCE — primary interface
3.1 Essential startup
clira launches an interactive session. No mandatory subcommand, OAuth, channel ID or model API key just to explore. Keep clira --help, clira doctor, clira chat --channel …, clira serve, clira connect, clira tool, clira jobs, clira approval and all existing automation/script usage compatible.
Example design target, not actual current output:
$ clira

    [Clira compact black/white Braille portrait — shown only on a roomy TTY]

    clira                                     v1.0.0  ·  local
    Your Creative Intelligence

    Channel   Inside the Machine  ·  UC…ABCD
    Account   LIVE · connected (read)         or   DEMO · synthetic data
    Model     Gemini · enabled               or   Offline · limited
    Policy    Copilot · owner approves channel actions

    Try: “Plan my first channel” · “Analyze my latest five uploads”

    ❯ _
    /help  /channel  /sessions  /status  /approvals
When no channel is attached, onboard rather than error:
    Welcome to Clira.
    1  Start planning a new YouTube channel
    2  Connect an existing channel
    3  Explore with synthetic demo data
    ❯ _
Starting a new channel creates a local draft workspace, not an invented YouTube account or fake immutable UC… ID. The first conversation can begin immediately. Guidance for Google account/channel creation must not claim an unsupported YouTube API action.
3.2 Interaction mechanics
Use a lightweight REPL, not a giant full-screen dashboard. Prefer prompt_toolkit for multiline editing, history and completion; rich for readable panels, Markdown, progress and concise receipts if they provide measurable value. No arbitrary shell execution shortcut and no new autonomous subagents.
- Enter: send. Ctrl+J: newline; Shift+Enter when supported. Tab: command/channel autocomplete. Up/down: prompt history. Ctrl+R: search history. Ctrl+D: exit with empty input. Ctrl+C: cancel active request; while idle clear text, repeat to exit. Esc dismisses picker.
- Terminal widths: ≥100 show compact portrait + full status; 80–99 hide large portrait; 52–79 compact status; <52 minimal prompt and simple text; no character truncation or broken wrap. Width detection must be tested, not assumed.
- Non-TTY/CI/redirected stdout: no splash, no spinners, no interactive prompts and no ANSI garbage. Support one-shot clira chat --channel ID "question", clira chat --json, plus input from stdin if implemented. NO_COLOR=1 and --no-logo must work.
- Use structured, source-labeled progress only for actual observable steps; do not expose invented chain-of-thought or pretend API calls succeeded. If backend is synchronous, show a truthful busy indicator, not fake live tool streaming.
- Save every conversation with its real channel_id or local workspace ID and conversation_id so the website can reopen it.
- A Clira reply defaults to clean prose and small actionable receipts, not raw JSON. Expand with /details or existing tool --json.
3.3 Command catalog
Interactive slash commands should work in addition to normal chat:
Command	Behavior
/help	Discover shortcuts, status and supported tools
/status	Mode, active channel/workspace, model, OAuth scope, pending approvals, job counts
/channel	Verified channel selector; never guess a brand-channel identity
/connect	Launch the explicit Google OAuth setup flow when user requests it
/new	Begin new persisted conversation
/sessions	Search/select old conversations
/resume [id]	Resume latest or specified conversation in the active channel
/title <name>	Set a session title
/ideas, /calendar, /jobs	View records belonging to current channel
/approvals	List pending exact owner actions
/approve <id>	Show immutable payload, then require explicit typed owner confirmation
/model, /mode	Inspect configured provider and permission policy; not bypass security
`/theme auto	light
/details, /sources	Inspect last tool receipt with source, timestamp, warnings
/clear	Clear terminal display, not SQLite history
/quit	Exit cleanly; explain worker tasks continue only if actually configured


Unknown slash command → suggest similar commands; don't silently pass it to an LLM. Commands that claim to open a site or change settings must do it or explicitly say unavailable.
3.4 Approval presentation
Every account write stays behind existing policy.py authorization. Show a dedicated confirmation view with target channel name and immutable ID, operation, exact video/comment target, exact metadata, privacy status, expiry, disclosure, rights evidence and upload file hash when relevant. Require an explicit APPROVE entry and revalidate the same hash immediately before execution. Never expose tokens or upload session URLs. Model-issued approval is forbidden.
3.5 CLI prototype tests
Test actual pseudo-terminal sessions (pexpect or scripted PTY) for: bare startup; zero-channel onboarding; demo labeling; --help and old commands; new/resume across process restart; multi-line editor; color/monochrome; width 52/80/120; Ctrl+C and Ctrl+D; malformed commands; lack of API keys; a fake OAuth attempt; proposal → owner approval separation; raw tool receipts on demand; no secret echo.
4. WEBSITE EXPERIENCE — same agent, visual workspace
Keep existing FastAPI, vanilla JS and CSS unless strong evidence requires a change. Do not rewrite Clira into a separate React agent or build an unauthenticated public SaaS. The website remains local-only by default: http://127.0.0.1:8765/.
4.1 Visual concept
A warm, quiet editorial workspace built for channel owners. Website defaults to warm ivory while the terminal inherits the user's theme. Use the same ink/ivory/gold semantic tokens, evidence labels, channel selector and Clira portrait. No stock dashboards, giant decorative rings, glossy cards or unreadable 9px labels.
Desktop wireframe (design target):
┌───────────────────────┬───────────────────────────────────────────────────┐
│  [Clira] Clira        │ Inside the Machine · LIVE / read · 2 approvals    │
│                       ├───────────────────────────────────────────────────┤
│  Switch channel ▾     │ What should we work on?                           │
│                       │                                                   │
│  Chat                 │ [Clira conversation + receipts]                   │
│  Overview             │                                                   │
│  Ideas & Calendar     │ Sources · observed time · task progress          │
│  Production           │                                                   │
│  Approvals       (2)  │                                                   │
│  Community            │ [ Ask Clira about your channel…             ➜ ]   │
│  Jobs                 ├───────────────────────────────────────────────────┤
│  Settings             │ Next: review video package / check pending job   │
└───────────────────────┴───────────────────────────────────────────────────┘
4.2 Preserve eight functional views
Map existing data-view values instead of breaking app.js handlers:
1. Chat — primary conversation, session drawer, provider/source receipts and contextual next actions.
2. Overview / Video library — dated metrics, true video privacy status, clear lifetime-vs-period labeling, owner uploads.
3. Ideas & Calendar — launch plans, topic research, drafts, scripts, packaging state, planned vs actual publication dates.
4. Production — external production handoffs, manual MP4 import, QA, asset previews and complete packaging readiness.
5. Approvals — exact unambiguous private upload, metadata, schedule, publish and reply approvals.
6. Community — comments, creator-voice draft replies, exact target, approved writes only.
7. Operations / Jobs — queued/running/needs-review/recovery-required/failed; safe retry controls and audit history.
8. Settings — Google channel scopes, model config and limits, appearance, data/export, safety toggles.
Avoid fake metrics and generic demo green checkmarks. Show DEMO · SYNTHETIC visibly throughout synthetic workflows. Surface Model offline, Not connected, Metric unavailable, Approval required, Upload not yet tested as real states.
4.3 Website onboarding
If no real channel exists, show three clear paths: Launch a channel, Connect existing, Explore demo.
Launch flow: 3–5 conversational steps max (interest, viewer, language, available time, format), then drafts of positioning, channel name and description, initial creative brand direction, first 3 ideas and first publishing calendar. The user can change decisions later. Guide actual YouTube channel creation manually in a browser and connect through OAuth. A draft workspace remains available without Google sign-in.
Connect flow: direct Google OAuth with exact immutable ID review, scope explanation and read-only initial grant. No browser chat requests for client secrets. Permit no writes until explicitly upgraded, enabled and approved.
4.4 Website chat and sessions
- Current session, saved session list/search, New conversation, Resume, truthful timestamps and channel identity.
- Persist channel/workspace ID and conversation ID server-side. Browser URL may contain a non-secret conversation ID, but never refresh token, credential or upload session URL.
- Existing GET /api/conversations/{channel_id} and /api/chat are starting points; adapt APIs only with tests and compatibility. Do not infer a global viewer identity from an arbitrary client-supplied channel ID in a hosted environment.
- Use readable line lengths (~70–85 chars) and accessible font sizes. Chat composer: Enter send, Shift+Enter newline, autoheight, focus restore, clearly disabled while busy.
- Source/call receipts expandable. Busy state reflects actual request; SSE/streaming only once implemented in backend—no simulated streaming text.
- Resume in terminal: show copyable clira --channel ID --resume SESSION or an actually implemented equivalent; Open in web in terminal opens a local link only after verifying backend is available.
- Channel switching must not mix histories, ideas, thumbnails, approvals or API grants.
4.5 Content packaging: release-critical, not fake UI
User requires actual support for titles, descriptions, tags/hashtags, thumbnails, captions and chapters. Build a capability-aware packaging area:
Asset	v1 behavior	Honest fallback
Titles	Suggest alternatives with factual/title-length checks; owner selects	Manual title
Descriptions	Descriptive text, source references where appropriate, timestamps	Manual edit
Hashtags / metadata tags	Relevant small set, no hashtag spam; API-compatible tags	Manual edit
Thumbnail image file	Generate local preview using real provider or approved deterministic template; correct size; enable owner selection and image upload through official endpoint	Mark Provider not configured and allow user's own file (not concept text as completed thumbnail)
Speech captions	Generate real timed SRT/VTT from a connected transcription provider or manual captions; allow preview/edit; upload through supported authorized caption endpoint	Upload manual SRT; Transcription not configured
Chapters	Validate first timestamp and interval rules against current YouTube requirements; produce description timestamps	Manual chapters
Disclosures / copyright / kids	Explicit owner checklist and metadata state	Block account write when required choices absent
Playlists / pinned comments	Only expose where official API/actions and owner permission are implemented and tested	Coming later, no fake buttons


Do not represent an image concept, model hallucination or mock screenshot as a real thumbnail. Do not burn captions into the MP4 unless an actual editing integration is available. Do not auto-post copyrighted music; rights clearance remains owner's responsibility.
Important: a release candidate can demonstrate with fixture videos and stubbed external APIs; a stable live channel-management claim needs owner-approved real integration evidence. If image generation or transcription providers are unavailable, implement manual import + preview/upload paths, and label automated generation as optional/unavailable. Don't silently downgrade a promised feature.
4.6 Approvals and analytics
- An approval panel must include immutable account name + channel ID, operation, exact target, privacy, schedule/timezone, upload hash, licensing attestation, expiry, owner confirmation and audit receipt.
- Approval and execution remain separate actions as in current service. Never make an approval button automatically publish; clearly show the following execution step.
- Metrics show units, date range, observed/freshness/source; missing rows show Unavailable rather than zero. No correlation-as-causation or virality promises.
4.7 Responsive and accessible acceptance
Test screenshots and interactions at 1440, 1280, 768, 390 and 320px. No horizontal overflow. 44×44px mobile actions where feasible. Keyboard traversal, visible focus, dialog escape and proper trapping/return to trigger, reduced-motion support, WCAG AA readable contrast, and no offscreen approval action. Make portrait decorative; it must not block tools, status or onboarding.
5. Shared runtime and data contract
Terminal (Rich + prompt_toolkit)       Local Website (FastAPI + JS)
             │                                  │
             └───────────┬──────────────────────┘
                         ▼
                  Single Clira Agent
                  + typed tool registry
                         │
                 Existing Service / Policy
                  ┌──────┼────────────┐
                  ▼      ▼            ▼
              SQLite   Media QC   YouTube adapters
             + secrets  / import     + OAuth
                         │
                   Optional production
                     adapter (Lemo)
- One durable SQLite store, one agent/tool implementation, one approval/publishing policy, one set of YouTube integrations.
- Authoritative IDs: channel_id (verified for live; special local draft identity for launch mode), conversation_id, idea_id, asset_id, approval_id, job_id, remote youtube_video_id.
- Typed sources: mock / local / youtube_data_api / youtube_analytics_api; include observed timestamp and warnings.
- Add session title, last accessed, channel/workspace ownership, settings and activity metadata with safe migrations; don't break v0.1.0 data.
- Request activity states: queued, running, completed, needs_approval, failed, unavailable, recovery_required. A terminal spinner must represent a real running operation.
- No code path should allow the model to approve, execute, publish, post_reply, delete, or attest licensing/creative review. Owner-only routes/CLI stay outside the model tool registry.
- API route security: loopback/Host/Origin/CSRF restrictions, safe text DOM (textContent), strict content types/limits, audit logs. Do not expose this localhost server on public network or cloud without a separate auth, tenancy and threat model.
- If moving slow work out of synchronous requests, persist jobs with stable IDs and observe them from both surfaces. Do not create independent site-only fake job timelines.
- Isolation: switching channel/launch-workspace must not leak conversations, approvals, job receipts, data or tokens. No global channel fallback for real writes.
Launch path compatibility
For users without a YouTube channel, create a safe local draft workspace and keep content plans there. When the user later connects an actual channel, require explicit choice to associate/copy draft content; do not remap ownership invisibly or use fabricated UC IDs in real APIs.
6. Release scope and roadmap
v1.0.0 should be a trustworthy local creator agent, not a claim that it can secretly run an entire channel autonomously. This list is the required scope for a stable release; any unverified live critical operation should block the stable tag and leave the product at v1.0.0-rc.N / preview with clear notes.
P0 — Stable release blockers
- [ ] Bare clira opens functional, attractive terminal chat with first-run onboarding, sessions, compact Braille art and graceful no-color/no-logo/narrow behavior.
- [ ] Existing CLI commands remain backward-compatible and documented.
- [ ] Website chat uses same conversations, channel/workspace context, jobs, approvals and saved results as terminal.
- [ ] Zero-channel launch workspace works without fake account creation and can be linked to a real channel only with owner confirmation.
- [ ] All eight existing website views remain usable at desktop and mobile sizes; readable and keyboard-accessible.
- [ ] Real YouTube OAuth and channel read tested under the owner's explicit consent, with immutable ID verified and credential isolation validated. If owner cannot provide credentials, do not claim live integration passed.
- [ ] Optional live configured model tested with owner permission and budget controls; offline/demo mode clearly limited and synthetic.
- [ ] Finished-video manual import, ffprobe QC, asset hashing, rights/declaration controls remain correct.
- [ ] Real or manually imported thumbnail image preview and official upload route implemented (with mocks + live owner test when authorized); do not mark text concept as an image.
- [ ] Captions SRT/VTT import/edit/validation and authorized caption-track upload implemented, plus optional real transcription provider integration with honest capability states.
- [ ] Titles, descriptions, metadata tags, hashtags and valid chapter timestamps can be prepared, previewed and included in the approved publish package.
- [ ] Exact approved private upload to intended channel is live-verified with a real remote video ID, or stable release is blocked; no automatic public publication.
- [ ] One explicit, separate owner approval flow for schedule/publication, and for comment reply, verified with safe test evidence or marked unsupported if not part of advertised stable functionality.
- [ ] No way for the model/website/CLI to bypass owner scopes, approvals, rights gates or safe resumable-upload state.
- [ ] Durable jobs and safe recovery do not silently duplicate uploads. Background scheduler is disabled by default and documented truthfully.
- [ ] Clean installation from the built wheel and source archive; fresh data directory, migration from v0.1.0, backup, restart and undo tests.
- [ ] Fresh backend, browser, terminal, security and artifact tests pass and are documented with reproducible commands.
P1 — After v1.0.0 (don't falsely advertise at launch)
- Full in-terminal streaming and cancellable concurrent tool calls if warranted.
- Multiple external video-render providers with real job dispatch and collection.
- Full retention/cohort diagnostics and data-history pagination.
- Actual visual thumbnail generation via connected image model beyond deterministic templates.
- Smart content experimentation/A-B processes, playlist/pinned-comment workflows where supported and authorized.
- Hosted multi-user SaaS, remote OAuth, team roles, mobile native apps.
- Auto-publishing from explicitly preapproved policies after real operational safety testing.
Versioning: Do not update public README badges, version strings or tags ahead of the demonstrated reality. A failed gate produces a preview/RC release or a blockers report, not an invented v1.0.0 success claim.
7. Prototype and release test plan
Phase A — Baseline and interfaces (no credentials, no live writes)
1. Snapshot repo baseline. Run tests/lint; inventory current API and IDs.
2. Implement terminal startup, theme, help, channel picker, history and session restore.
3. Implement shared web session picker and launch onboarding with backend persistence.
4. Add real character text asset and website approved asset only if supplied.
5. Run terminal PTY tests, CLI compatibility tests and demo browser smoke at sizes above.
6. Record prototype demo in two directions:
   - Terminal → ideas/session → website resumes same session, same record IDs.
   - Website → approval request → terminal lists exact same approval, without executing it.
Phase B — Packaging and safety (mocked YouTube; real local media files)
1. Create a 5–10-second rights-cleared MP4 fixture using FFmpeg.
2. Import it through production UI; inspect ffprobe streams and persisted hash.
3. Prepare package with title, description, relevant hashtags/tags, optional chapters, manual thumbnail PNG/JPEG and real timed SRT/VTT.
4. Validate dimensions/file type/size against current official YouTube requirements (research at implementation time), and test file parsing/preview.
5. Mock official thumbnail/caption endpoints and simulate authenticated action failures, quota limits, wrong channel, expired tokens and failed retries.
6. Prepare private upload approval → reject/approve on CLI or site → execute only through owner-only path → inspect receipt and audit.
7. Restart during a resumable upload simulation; ensure the same session is resumed without duplicate video creation.
8. Regression: prompt-injection in comments/metadata cannot cause publish, scope changes, or secret exposure.
Phase C — Live integration (ONLY with user authorization)
1. Configure Google Cloud Desktop OAuth client outside Git; connect one exact channel read-only; validate channel ID, scopes and a sourced recent-video read.
2. Enable configured LLM using owner's own key/budget; run a real small content-research/script tool request; verify source claims are clearly marked unverified until fact-checked.
3. Enable upload grant and writes only after owner confirmation; perform one private rights-cleared test upload. Validate remote ID, privacy and metadata; reconcile any uncertain outcome before retry.
4. Test thumbnail and caption upload against that private test video with separate appropriate OAuth capability/approval gates.
5. If publication testing is desired, require a new explicit owner approval and current policy/API check. Never public-post by default.
6. Verify scheduler status and clearly document whether timers are enabled; leave off unless owner authorizes recurring work.
Phase D — Release candidate and stable release
1. Build wheel + sdist; install into clean venv and from source; validate clira, clira --version, clira serve, clira doctor.
2. Run all old tests + new PTY/Playwright/security tests; zero new regressions; no debug secrets or synthetic screenshots presented as real.
3. Generate screenshots at 1440px/390px and terminal transcript in wide/narrow/no-color modes; label demo data visibly.
4. Update pyproject.toml, package __version__, CHANGELOG.md, README, docs/SETUP.md, docs/VERIFICATION.md, release workflow and migration notes only when gate evidence exists.
5. Test scripts/build_release.py and .github/workflows/release.yml using a safe dry run or candidate tag; verify artifact contents and checksums.
6. Prepare v1.0.0-rc.1 if any live/account block remains. Only propose/perform final v1.0.0 tag and GitHub release after all mandatory checks and explicit owner approval to publish the release.
7. Post-release: smoke test clean install from actual assets, verify links/checksums, and maintain a rollback route (prior release tags + DB backup/migration plan).
Exact baseline commands (run against current checkout)
uv run --locked --extra dev pytest -q
uv run --locked --extra dev ruff check clira tests
uv run --locked --extra dev ruff format --check clira tests
node --check clira/web/app.js
bash -n run.sh
./run.sh doctor
uv run --locked --extra dev python tests/browser_smoke.py
The existing browser test may require a Chromium installation or CLIRA_BROWSER=.... Report not-run status and reason if unavailable. Existing repo contains pyproject.toml with [project.scripts] clira = "clira.cli:main"; preserve it and verify packaged console entry points.
Test matrix and pass condition
Scenario	Required evidence
clira no args	Interactive first-run or safe resumed session; no parse error
No-channel user	Local draft workspace created without fake YouTube ID
Offline/model missing	Honest limited state; no invented live actions
CLI ↔ Website sessions	Identical conversation ID and messages across restart and both clients
CLI ↔ Website account switch	No cross-channel data, approval or credential leak
Braille, 52/80/120 cols, NO_COLOR	No corrupted output, runaway wrapping, ANSI escape leak
320/390/768/1280/1440px web	No overflow, accessible controls, legible text, working approvals
Missing image provider	Manual thumbnail import works; generation explicitly unavailable
Missing transcription provider	Manual caption import works; automatic transcript not falsely claimed
Package validation	Correct title/description/tag/hashtag/chapter and file facts
Approval / write boundaries	Exact scoped payload, separate owner consent, no model self-approval
Resumable upload failure	Remote status reconciled; no duplicate upload on retry
Google API outage / quota	Clear error state, safe backoff, persisted retry metadata
Browser/CLI prompt injection	Untrusted data remains data, never authorizes tools
Package/install/release	Clean install succeeds; versions and assets consistent; checksums valid
Live feature claim	Actual owner-authorized API receipt or explicitly labeled unverified


Do not count screenshot beauty, mock tests or a demo YouTube ID as proof of live channel management.
8. CODEX MASTER EXECUTION PROMPT
Copy this section to Codex, or point Codex to this entire Markdown file.
You are working on Clira, one autonomous YouTube-specialist agent with a terminal-first interface and a synchronized website. The repository is https://github.com/Gurtejhundal/Clira.
Objective: Take the current v0.1.0-style foundation to a tested, usable terminal-and-website prototype, then prepare a credible v1.0.0 release only if all release gates pass.
Read first: root AGENTS.md, README.md, pyproject.toml, all original mds/ specifications, docs/PRODUCT_ANALYSIS.md, docs/VERIFICATION.md, docs/SETUP.md, agent/tool/CLI/API/storage/policy/YouTube code and existing tests. Read this whole document, which is the current consolidated UX/release contract. Reinspect the code; do not assume the documentation is current.
Do not rebuild from scratch. Preserve the single Clira agent, typed Python tools, SQLite, OAuth, private-first uploads, idempotent jobs, exact approval hashes and all original routes and commands. Lemo-Opuscar is optional and external. No Hermes runtime. No autonomous subagent swarm. Do not weaken API security or open localhost to the network.
Work sequence:
1. Run and document baseline tests. Create a short list of gaps with code paths.
2. Implement bare clira as an interactive, accessible prompt_toolkit/Rich terminal. Add true mode/status, the approved embedded Braille asset, narrow-width fallback, NO_COLOR, multiline input, slash commands, safe cancellation and readable structured receipts. Keep argparse compatibility.
3. Add new-creator launch workspaces and connected-owner flows without fake Google channel creation. Persist workspaces, user decisions and channel-linked sessions in SQLite with tested migrations.
4. Make the website's existing eight views use the shared design language, readable type and session picker. CLI and web must resume the same conversations/jobs/approvals with the same IDs. No duplicated agent or fake streaming UI.
5. Complete content packaging: useful titles/descriptions/tags/hashtags/chapters; real thumbnail preview/import + optional generator and official upload; real caption SRT/VTT import/validation + optional transcription and authorized upload. Show provider/feature availability truthfully. Keep rights/disclosure review and human approval.
6. Write PTY, CLI, API, media, security and Playwright tests. Test first-run/no-channel, offline/demo, cross-surface session resume, narrow layout, component reuse, permissions, mock upload faults and source labels. Fix actual failures.
7. With owner approval only, perform Google OAuth live channel read, optional live model test and one private test upload with a rights-cleared video. Verify remote receipt, thumbnail/caption operations where authorized. If unverified, stop short of stable v1.0.0.
8. Build v1.0.0-rc.1, install artifacts cleanly, run release workflow tests and update docs with actual evidence. For v1.0.0, require every P0 gate plus explicit owner confirmation to tag/publish. Otherwise report blockers and ship an honestly labeled RC.
Focus: Ship working code, not another pile of Markdown. Make small, reviewable changes. Do not invent tests, tool output, completed API actions, live channel data, performance claims or rights clearance. Do not expose OAuth tokens or API keys. Do not automatically publish videos, replies, GitHub releases or public website deployments.
When reporting: Give the code files changed, feature status (DONE / TESTED-MOCK / UNVERIFIED-LIVE / MISSING), exact commands and result counts, screenshots/transcripts of the prototype, current version, artifact locations, and blockers with the next safe action. State explicitly whether v1.0.0 has actually been released or is only prepared.

9. Codex deliverables checklist
Codex should produce, in the repository (not merely in a chat response):
- Updated terminal modules under clira/tui/ plus backward-compatible entrypoint in clira/cli.py.
- A tracked UTF-8 Clira Braille text asset and optional approved website portrait asset.
- Responsive, accessible improvements in clira/web/ with preserved endpoints and CSRF protections.
- Persisted onboarding/workspace and session metadata with safe migration.
- Actual, capability-aware video packaging surfaces and backend tools for thumbnail/captions/metadata, or explicitly gated providers.
- End-to-end demo prototype with no credentials and no external writes.
- New tests for TUI, browser sync, UX states, secure operations and packaging.
- Fresh verification report, screenshots and short terminal capture.
- Candidate release artifacts, checksum manifest, release notes and clean install result.
- Owner-approved v1.0.0 GitHub tag/release only when gates are satisfied and approval is explicit.
The success metric is simple: A beginner can start in Clira, a creator can use Clira to manage a real channel, and the same trustworthy work is visible in terminal and website.
References to review at implementation time
- Clira repository: https://github.com/Gurtejhundal/Clira
- Hermes terminal reference: https://hermes-agent.nousresearch.com/docs/user-guide/cli/
- Claude Code CLI docs: https://code.claude.com/docs/en/interactive-mode
- Codex CLI: https://developers.openai.com/codex/cli
- Rich: https://rich.readthedocs.io/
- prompt_toolkit: https://python-prompt-toolkit.readthedocs.io/
- YouTube video insert: https://developers.google.com/youtube/v3/docs/videos/insert
- YouTube thumbnail set: https://developers.google.com/youtube/v3/docs/thumbnails/set
- YouTube caption insert: https://developers.google.com/youtube/v3/docs/captions/insert
- YouTube video updates and scheduling: https://developers.google.com/youtube/v3/docs/videos/update
- Google OAuth installed apps: https://developers.google.com/identity/protocols/oauth2/native-app
- YouTube API policies: https://developers.google.com/youtube/terms/api-services-terms-of-service
Always check official docs for current quotas, OAuth scopes, caption/thumbnail limits and video scheduling rules rather than encoding guessed constants.
Appendix A — Approved compact Clira Braille portrait
Source: the prior approved Clira monochrome portrait converted to Unicode Braille. Copy these exact UTF-8 lines, including spaces, into clira/assets/clira_braille_compact.txt. Keep text-only; display only when terminal dimensions permit. The portrait is decorative, not required for successful CLI operation.
                 ⢀⠠⡠⢄⣀⡀⣤⣤⣐⡠⠠⢄
             ⡀⣠⠄⠈⣠⣴⣾⣿⣿⣿⣿⣿⢿⣿⣷⣾⣷⡲⡆⠢⡀
          ⣀⠔⣲⡾⠊ ⣴⠿⠟⢻⠿⡿⣻⡟⣡⣿⣿⣯⡛⠿⣿⣿⣧⡙⠄
        ⢀⣔⢅⣰⣾⠁ ⣼⣵⣦⣴⣥⣴⣿⣿⡮⣿⣿⡎⢿⡱ ⠈⢟⣿⣻⣿⣦⢄
        ⣿⢈⣾⣿⡇ ⡰⣿⣿⣟⣿⣿⣿⡟⣿⣿⡿⡽⠃⢸⠏  ⢅⡟⣿⣿⣿⣧⠙⢄
      ⣀⣬⢶⣿⣿⣿⣚⢉⣿⣟⣷⣿⡻⢋⢁⣴⣿⣿⠼⠛⠛⠛⠛⢀⠈⠈⡉⣉⣿⣽⢻⡂⠈⠱
   ⢀⡴⠊⠁⣰⣿⣿⣿⣿⣿⠐⣿⣿⢿⣿⣫⣷⣿⣿⠋⡼⣰⣰⠶⡳⠄⢀⠎⠉⠏⠻⢿⣿⡷⣆⠊⢀⠁
   ⠎ ⣴⣽⠿⢛⢏⣾⣿⣿⢀⡛⣉⠙⠺⢿⣿⣯⣗⠹⠁⠈⠄⡀  ⢀⠁ ⡄⢰⠈⢿⣻⣟⢿⡄
   ⠐⡼⢹⢁⣀⣴⣵⣿⣿⣱⣷⣷⣶⡕⢄⠈⢚⣿⣾⣦⡀   ⠁⠈  ⠁ ⣀⡀⠸⣿⣿⡠⠃
   ⠐⢁⣦⣿⣾⣿⣟⣾⣿⣺⣿⣿⣿⣿⡎⢆⣤⡿⣿⣿⢮⠂⠂    ⠠⠐⠉⡈⠑⢘⣿⣿⣧⡐⡀
  ⠐⢔⡷⣿⢿⣿⣿⣿⣿⣿⣷⣻⣿⣿⣿⢇⢯⣿⢯⣿⣿⠩⢃⠡         ⢸⣿⠇⣻⢷⠈
   ⡿⠁⠺⠳⡽⡟⣿⣿⣿⣿⣿⣾⣽⣽⣮⣿⣫⣿⣿⠾⢰⣯⣀⣀⣀⣀⣀⣀⣀⣠⣠⣤⣾⡯⠄⠁⡈
       ⣠⡵⣿⣽⣽⣿⣿⣿⣿⣿⣿⣿⣿⣻⡝⠐⠋⠃⠈⠙⠛⠿⣿⣿⣿⣟⡿⢻⢟⠂ ⠈
      ⠂⠋ ⠈⠋⡙⠿⣝⠛⠿⡿⣿⣿⡿⣟⠣⠄      ⢈⣿⠧⡈ ⠃
         ⣀⣤⡠⠄⠐⠐⠐⠐⠛⠿⡁⡊⠁       ⡈⠉
       ⣀⠜⢋⣡⣤⣶⣿⣿⠾⠂   ⠈⠒⠦⣀    ⠠⠂
     ⠠⡈⢀⡴⢫⣾⠿⠛⠉ ⢀⣠⡴⡶⣾⣶⣶⣦⣌⠻⢦⡄ ⣾⣦⣦⣄⢀
      ⣷⠟⡱⠋  ⢀⣀⣤⣥⣦⣶⣦⣦⣤⣍⣛⣿⣟⠮⠹⣧⣿⣿⣿⠟ ⢣
     ⡔⣩⣾⠁⣀⣶⣿⡿⣿⠟⠋⠁   ⠈⠙⢿⣿⣿⣿⣦⢬⣹⠟⠁⢀⣀⠆⢑⠄
    ⢨⣶⣿⣷⣼⣿⡟⡡⠊⢀        ⢤⠘⢿⣿⣿⡌⣿⣷⢘⣹⣥⣶⣯⣄⡀
    ⢸⣿⣿⣿⡿⠋ ⠁⢠⡃         ⠹⣄⠙⢿⣇⢻⣿⣿⣿⣇⢽⣿⣿⢿⣦
     ⠉⢿⠟   ⢠⡿           ⠘⣧⠈⢻⠸⣿⣿⣿⣿⡈⡿⠁⠊⢻⣧⡀
End of single-file Clira v1.0.0 design and implementation contract.