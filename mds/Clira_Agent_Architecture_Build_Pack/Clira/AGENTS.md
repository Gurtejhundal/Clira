> Project identity: **Clira**, your creative intelligence. See `docs/19_CLIRA_BRAND_IDENTITY.md`.

# Antigravity Instructions — General YouTube Agent

Read `README.md` and `docs/13_IMPLEMENTATION_PLAN.md` before coding.

## Non-negotiable principles
- One **general-purpose AI agent**, with explicit typed tools, **not** multiple autonomous agents.
- **Never add Hermes** or a multi-agent runtime as an unnecessary dependency.
- **Video generation is external.** Implement a generic `ProductionProvider` adapter. Lemo-Opuscar can be one optional adapter; do not modify Lemo by default.
- **Inspect existing code** in `~/youtube-studio` and installed YouTube Agent skills before reusing pieces; don't blindly shell out to unknown scripts.
- The source repository https://github.com/Jakeschincariol/youtube-agent-skill is a writing/analysis toolkit; it explicitly **does not publish**. Its heuristics are not reliable predictors of virality.
- Use official YouTube Data API and YouTube Analytics API for authenticated account operations; Google OAuth 2.0 for identity.
- Keep per-channel identity, permissions, task state and audit records; every external write checks them.
- Only perform Google account sign-in with user participation, never ask for tokens in chat, never print secrets in logs.
- Do not upload or publish real content during development without express user authorization. Use mocks first.
- All videos must start with explicit `privacyStatus=private`. Publishing requires explicit approval.
- Error reports must distinguish a mock test, a dry run, an authenticated read, and a real mutation.
- Respect copyrights, disclosure rules, community guidelines and platform automation policies.

## Sequence
1. Audit current environment and create a short dependency inventory (paths + tests).
2. Implement database/migrations + permission engine + mock tools.
3. Implement model adapter and tool-calling chat loop with strict output schemas, bounded steps and human approvals.
4. Add YouTube OAuth, read-only channel details and analytics; test authenticated reads.
5. Add private upload with resumability/idempotency; demonstrate only after authorization.
6. Add topic research, scripts, packaging, comments, scheduling.
7. Add generic production handoff and optional Lemo adapter last.
8. Add practical dashboard and CLI; verify end-to-end on one channel, then multi-channel isolation.

## Definition of done for every milestone
- Tests exist and were run.
- An exact supported command or API endpoint works.
- Real / mocked results are clearly labeled.
- Failure modes, permissions and rollback are documented.
- No imaginary completion percentages.

## How to proceed if blocked
When OAuth credentials, a channel grant, an LLM key, or owner approval is needed: stop the affected action, name the missing prerequisite, and keep implementing independent functionality. No credential fabrication or bypass.
