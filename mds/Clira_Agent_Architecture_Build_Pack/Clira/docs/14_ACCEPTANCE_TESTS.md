# 14 — Verification and Acceptance Tests

## Test levels
- Unit: policy evaluation, schema validation, timezones, duplicate detector, quota budget, retry state machine.
- Integration with mocks: YouTube Data API, OAuth refresh, Analytics reports, provider adapters.
- E2E local dry run: user intent → model tool selection → state change → operation receipt.
- Real authenticated read: explicitly authorized channel with dated data.
- Real private upload: explicit user approval required; never auto-trigger during tests.

## Acceptance matrix
| Test | Expected |
|---|---|
| Unconnected account | Helpful auth-required result; no guessed data |
| `channels.list(mine=true)` | Actual title/ID shown for selection |
| Wrong channel ID | Request blocked before write |
| Expired/revoked token | Clean auth prompt; no secret leakage |
| Model requests `publish_now` without approval | Policy blocks operation |
| Prompt injection inside comment | Agent does not change permissions or execute text |
| Local MP4 missing | No upload session begun |
| MP4 invalid codec/zero-byte | QC failure with explanation |
| Unlicensed song | Upload gate blocked/pending rights review |
| Double-trigger scheduled upload | Single video ID; no duplicate uploads |
| Upload network interruption | Resume or reconcile remote state |
| Publishing time in past | Refuse unintended immediate publish |
| `videos.update` metadata | Existing fields not accidentally erased |
| Comments reply draft | Creates draft, no public API write |
| Analytics unavailable | Explicit `unavailable`, never invented metrics |
| Production adapter missing | Manual import still works |
| System clock/timezone difference | Correct UTC publishAt and local display |
| Disk full | Safe failure, no destructive cleanup |
| Daily timer during shutdown | Does not claim to have produced a video |

## Test evidence format
```
Test case:
Environment: mock / authenticated live / approved live mutation
Command or endpoint:
Observed result:
Expected result:
Pass or fail:
Artifact path / redacted log:
Known limitations:
```

## Definition of done
- No bypass of owner approvals.
- No wrong-channel writes or duplicate uploads.
- Real YouTube reads and private test upload only after authorization.
- Credentials never committed, printed or logged.
- Tool errors explain the next safe step.
- Reproducible local setup and smoke tests.
