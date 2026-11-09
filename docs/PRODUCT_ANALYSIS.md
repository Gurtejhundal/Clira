# Clira: product analysis and implementation decisions

Reviewed all 21 Markdown files (1,019 lines) in the supplied build pack on 9 November 2026.
The initial project contained specifications only. This analysis explains the product, the important
gaps in the specification, the resulting implementation, and the proof still required.

## What we are building

Clira is a channel owner's operating partner. The creator should describe an outcome in ordinary
language and get the connected work done: understand performance, choose a topic, develop the story,
prepare its package, coordinate production, review the result, and manage its release and audience.

The useful promise is **less coordination work for the creator**. A creator should not need to
move the same context between an analyst, planner, writer, uploader and community assistant.
One central agent shares the channel's voice, editorial history and operating state across those jobs.

“Like Hermes, specific to YouTube” describes the interaction: a resourceful conversational operator
with memory and tools. The actual pack explicitly chooses one Python orchestrator and excludes
Hermes itself and autonomous subagents. Those choices have been preserved.

The main product object is a **work item with evidence and state**, rather than a chat answer.
An idea becomes a script and brief, then an imported asset and reviewed package, then an approval,
then a private video receipt, and only then a separately approved public action. Each step must
remain inspectable after the conversation or process ends.

## The complete creator loop

| Stage | Creator question | Durable output | Proof required |
|---|---|---|---|
| Understand | What worked, and for whom? | Dated analytics and recent uploads | Correct channel, source, period, units and freshness |
| Choose | What should I make next? | Distinct ideas and experiments | Channel fit; previous topics; honest evidence limits |
| Develop | What is the story? | Script, evidence list, production brief | Factual claims checked by owner; clear audience promise |
| Produce | How do we get a finished video? | External/manual handoff and asset | Actual file; provenance; technical and human review |
| Package | How do we present it? | Title, description, tags, thumbnail concept and disclosures | Exact metadata preview; no invented CTR promises |
| Release | Put it on my channel | Private receipt, separate public request | Exact owner consent; remote channel and visibility verification |
| Respond | What needs my attention? | Comment review and exact reply drafts | Reply target and text approval; no unattended spam |
| Learn | What should change next week? | Comparable weekly digest and hypotheses | Reporting limitations; no causal claims from small samples |

This loop is the reason a dashboard mockup or a collection of independent writing prompts would
not satisfy the brief. The application now has the persistent backend, policies, tools and UI for it.
Live account and model verification remain explicit gates.

## What the specifications got right

The strongest decisions were the single-agent boundary, immutable channel identity, private-first
uploads, separate publishing consent, local durable state, and an optional renderer. These prevent
the most expensive errors: sending content to the wrong account, treating a render as publication,
losing an upload after a timeout, or letting retrieved viewer text authorize public changes.

The brand direction is restrained and useful: warm ivory, charcoal, muted gold, clear language,
and a calm creator workspace. A simple temporary wordmark/emblem implements this direction.
The custom character/mascot and commercial brand clearance are future work, not fabricated assets.

## Gaps and decisions resolved during implementation

**1. “Handle everything” needs an operational boundary.** Clira handles channel operations and
creative coordination. Finished-video generation remains external. In the inspected environment,
`~/youtube-studio` and the `studio` CLI were broken symlinks. Lemo was present, but no stable
integration was assumed or invoked. The independent manual-provider path works without either.

**2. Agent authority must be narrower than owner authority.** The model can read, draft, import
unreviewed files, and prepare exact account-action requests. Owner-only endpoints/CLI commands
approve and execute them. The model's registry contains no approval or execution tool. It also
cannot attest rights ownership or human creative review. Prompt instructions alone would be
insufficient for these boundaries.

**3. Approval is a content contract.** Channel, mode, operation, file hash, visibility and payload
are hashed together. Consent expires, is single-use, and is invalidated when a never-started request
changes. A completed upload cannot become another upload when the same bytes get new metadata.
Expired resumable jobs can obtain fresh consent while retaining their original session/job.

**4. A timeout is not evidence of failure.** Upload intent is saved before initialization; the
session URI is saved separately as a secret; completion IDs are checkpointed before verification.
After a lost response, the same session is queried. If initialization or a non-resumable mutation
has an uncertain outcome, the job stops for reconciliation. An unavailable upload session never
silently triggers a new upload. This trades convenience for avoiding duplicate account changes.

**5. “Never published” is not fully inferable from a current private status.** Scheduling is limited
to videos uploaded and tracked by Clira and rechecks current status. External changes can still
invalidate local history; the Google API remains the final authority. A scheduled video is marked
as having a public-release workflow, conservatively preventing reuse of the initial-private flow.

**6. Research is not verified fact or a trend forecast.** The official search adapter stores public
examples and source links. Script claim lists and model-supplied citations remain unverified until
reviewed. The reused title/hook scripts produce editorial heuristics. No score becomes a promise
of virality, revenue or audience retention.

**7. Analytics windows matter.** Recent-video counts are explicitly lifetime counts. Channel
reports have requested start/end dates, units and observation timestamps. Reporting is labeled
delayed, and missing rows mean unavailable. Weekly digests compare nonoverlapping periods and
compute descriptive changes without claiming their causes. These are not complete Studio analytics.

**8. Local-first does not mean unauthenticated web writes are acceptable.** The app binds to
loopback, restricts Host/Origin, uses a per-process request token and a restrictive content policy,
and renders viewer/model text as text. It is not a hosted authentication system. The local OS
account is the owner trust boundary; team roles and remote access need a different deployment design.

**9. Money needs explicit enablement and bounded work.** Gemini calls are disabled until configured
and enabled. Each turn is bounded by tool steps and output tokens, with an atomic daily request cap.
The cap is not a financial guarantee: per-request token usage and provider pricing vary. Public
research has a separate application cap of ten search requests per UTC day. Actual Google quotas
remain controlled by the user's Cloud project; legacy quota constants were not copied into policy.

**10. Database detail should follow access boundaries.** The initial schema uses relational tables
for channels, conversations, approvals, jobs, settings and audit, plus indexed channel-owned JSON
records for evolving content types. This is a deliberate simplification of the proposed many-table
content schema. Ownership checks remain mandatory on every get/put, and structured inputs/results
are validated at the tool boundary. Future reporting may justify normalizing additional record types.

## Architecture and change-risk map

```text
Browser / CLI
    ├── Owner controls: profile, approval, execution, pause
    └── Agent: offline router OR configured Gemini provider
             └── Validated, bounded tool registry
                       ├── Channel / analytics / research / community reads
                       ├── Content / calendar / production drafts
                       └── Exact approval requests

Owner-approved jobs → transactional claim + lease + permission check
                   → verify Google channel ID
                   → execute/resume official API operation
                   → verify/store receipt + append audit

SQLite: state and opaque credential references
Owner-only files: OAuth credentials and upload session URLs
Managed media: per-channel immutable-byte copies and QC
External production: provider protocol; manual import works independently
```

| Area | Main modules | Risk when changing |
|---|---|---|
| Model behavior and memory | `agent.py` | Invalid function history, unbounded calls, unsupported action claims |
| Permission and consent | `policy.py` | Approval substitution/replay or bypass |
| External action execution | `service.py`, `youtube.py` | Duplicate writes, field loss, incorrect visibility |
| Media and rights | `media.py` | Path traversal, mutable assets, false rights assumptions |
| Durable state | `storage.py` | Cross-channel reads, corrupt job transitions, lost receipts |
| Local interface | `api.py`, `web/` | Cross-origin writes, unsafe HTML, misleading source labels |

The central executor is intentionally explicit. If the operation set grows, split its upload and
publication handlers into modules while retaining one deterministic policy/execution path.

## Milestone evidence and remaining gates

| Pack milestone | Current state |
|---|---|
| M0 environment | Inspected; dependencies tested; broken legacy links documented |
| M1 offline agent | Implemented and tested end-to-end |
| M2 OAuth and reads | Adapters implemented; mock refresh/identity/read tests pass; live grant still required |
| M3 content intelligence | Ideas, scripts, packaging lint, research and calendar implemented; quality needs actual model/channel review |
| M4 private upload | Actual local media QC and approval simulation pass; interrupted-upload transport tests pass; real upload not performed |
| M5 publication/community | Approved metadata/schedule/publish/reply paths implemented; thumbnail upload remains future work; live mutations unverified |
| M6 durable jobs | Transactional claims, backoff, recovery and pause tested; timer examples remain disabled/uninstalled |
| M7 production | Manual provider and interface implemented; external Lemo execution intentionally unconfigured |
| M8 interface | Eight views checked in browser at desktop/mobile sizes; full account gate still outstanding |

The product is useful as a local tested foundation. The supplied README's live-channel MVP definition
is not complete until a real connected channel produces a sourced read and an explicitly authorized,
verified private test upload. No completion percentage replaces that proof.

## Priorities after account connection

1. Verify OAuth account/brand-channel selection and a recent-video read on the actual channel.
2. Enable the chosen model under a budget policy; review tool selection and scripts in that niche.
3. Review one original, rights-cleared MP4 and authorize exactly one private test upload.
4. Verify its remote metadata, visibility, disclosures, interrupted recovery and audit receipt.
5. Validate separately approved scheduling/comment changes only if the owner requests them.
6. Add thumbnail upload, richer retention/cohort reporting, source verification and complete-history
   pagination when the real workflow demonstrates their requirements.

## Official integration references rechecked

- [Google desktop OAuth and PKCE](https://developers.google.com/identity/protocols/oauth2/native-app)
- [YouTube resumable upload protocol](https://developers.google.com/youtube/v3/guides/using_resumable_upload_protocol)
- [Video insert fields and project restrictions](https://developers.google.com/youtube/data/reference/rest/v3/videos/insert)
- [Video updates, preserved fields and publishAt requirements](https://developers.google.com/youtube/data/reference/rest/v3/videos/update)
- [YouTube Analytics reports, scopes and reporting availability](https://developers.google.com/youtube/analytics/reference/reports/query)
- [Gemini function calling and function response history](https://ai.google.dev/gemini-api/docs/generate-content/function-calling)
