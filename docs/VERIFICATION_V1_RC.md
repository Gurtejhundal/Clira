# v1.0.0-rc.1 verification · 9 November 2026

**Local candidate only. Stable v1.0.0 is not tagged or published.** Package version: `1.0.0rc1`.
Working branch: `codex/v1-terminal-web-rc`; published baseline remains v0.1.0.

## Baseline and scope

Before implementation, the exact requested baseline passed: 61 pytest tests, ruff lint/format,
JavaScript and shell syntax, doctor and the original eight-view browser smoke. Timestamped raw
baseline/final logs are retained under ignored `work/v1-audit/` and copied to the delivered report bundle.
The existing agent, SQLite tables, service/policy, official adapters, endpoints and CLI commands were
extended. No renderer, Hermes runtime, React frontend or autonomous subagents were introduced.

| Area | Before | Candidate status and evidence |
|---|---|---|
| Bare interactive terminal | MISSING | DONE; `clira/tui/app.py`, real pexpect tests at 52/80/120 columns |
| Approved portrait | MISSING | DONE; exact UTF-8 appendix asset; test checks byte-equivalent text |
| Zero-channel planning | MISSING | DONE; five decisions, local `workspace_` ID, positioning/name/description/brand, three ideas/calendar |
| Titled shared sessions | Basic history only | DONE; additive migration 2, shared API/CLI IDs, search/resume/rename, concurrent-request lease |
| Eight-view readable website | Existing MVP | DONE; light/dark, five viewport widths, keyboard focus and exact typed approval |
| Thumbnail image | MISSING | DONE local PNG template/manual import/preview; TESTED-MOCK official upload; UNVERIFIED-LIVE |
| Timed captions | MISSING | DONE basic SRT/VTT import/preview/edit; TESTED-MOCK official upload; UNVERIFIED-LIVE |
| Metadata/hashtags/chapters | Metadata drafts | DONE local validation and exact package manifest; owner checks factual claims |
| OAuth/read/private upload | Adapter and simulations | TESTED-MOCK; website exact-ID confirmation added; UNVERIFIED-LIVE |
| Gemini | Adapter and mocks | TESTED-MOCK; no paid call performed; UNVERIFIED-LIVE quality |
| Publication/comment replies | Separate approval paths | Existing regression tests retained; UNVERIFIED-LIVE; no account mutations performed |
| Image model/transcription/render | Optional/unconfigured | MISSING providers explicitly labelled; deterministic/manual paths work |
| Background schedule | Disabled | Still disabled; no timer/service installed or started |
| Release automation | Auto-published from main | DONE; automatic tag/release job removed; workflow only verifies |

## Reproducible commands

```bash
uv run --locked --extra dev pytest -q
uv run --locked --extra dev ruff check clira tests scripts
uv run --locked --extra dev ruff format --check clira tests scripts
node --check clira/web/app.js
bash -n run.sh
./run.sh doctor
uv run --locked clira --version
CLIRA_BROWSER=/absolute/path/to/chromium uv run --locked --extra dev python tests/browser_smoke.py --output work/v1-audit/browser-final
uv run --locked --extra dev python scripts/build_release.py --output dist/v1.0.0-rc.1
uv run --locked --extra dev python scripts/verify_artifacts.py --artifacts dist/v1.0.0-rc.1 --report work/v1-audit/artifacts.json
```

Fresh Python suite: **96 passed** (61 baseline tests preserved + 35 new tests). Python lint and
formatting pass; JavaScript and shell syntax pass. One upstream Starlette/httpx TestClient deprecation
warning remains. Python 3.12.16, SQLite 3.53.1, ffmpeg/ffprobe, uv 0.13.6, Chromium headless
shell revisions 1243 and 1248 were used. The final local run uses 1248, matching CI. Browser executable can be overridden through CLIRA_BROWSER; CI installs
its matching Chromium revision.

Browser checks exercise all eight views at **1440/1280/768/390/320px**, without horizontal page
overflow or JavaScript errors. They verify light/dark selection, actual keyboard focus, native-dialog
Tab/Escape/cancel/return focus, typed APPROVE, separate execution, MP4 ffprobe QC, mock private upload,
comment simulation, pause/resume, actual PNG preview, real timed SRT import, five-step local launch and
cross-channel message clearing. A CLI-created conversation is resumed in the website with identical ID
and saved text; website messages survive reload. CLI approval inspection returns the same exact approval
ID before the browser approves it. `shared-session.json` retains synthetic shared-session evidence.

Actual PTY checks cover first-run/demo and launch paths, 52/80/120 columns, approved portrait/no-logo,
NO_COLOR, multiline Ctrl+J, title/new/resume across restart, malformed command suggestions, /details,
missing connection prerequisites, Ctrl+C/Ctrl+D and approval without execution. Non-TTY startup and
one-shot JSON use no interactive prompts or ANSI escapes. Terminal escape/clipboard/bidi instructions in
untrusted content are stripped. Source receipts remain labelled mock/local/API as appropriate.

New backend tests validate additive v0.1-schema migration, backup/restart/rollback-copy integrity,
concurrent session isolation, exact workspace-copy confirmation, CSRF/content type/size/ownership,
read-only mocked website OAuth, package hash/right changes, real image decoding, strict timed cue
parsing/edit invalidation, chapters and UTF-8 description limits, official multipart caption and raw
thumbnail requests, sanitized auth/quota/rate/server errors and unknown-outcome recovery. The existing
lost-upload-response/same-session/no-duplicate tests still pass.

The first GitHub CI attempt exposed a Chromium 1248 dialog-close timing difference after Escape.
The owner dialog now explicitly restores focus to its trigger; the test waits for that observable
focus result instead of assuming the hidden state and close-event handler finish simultaneously.
The newer browser also enforces CSP for string-evaluating test predicates, so waits now use function
predicates. CSP was kept strict. Local checks were repeated with matching Chromium 1248 before
updating the RC branch.

## Artifact gate

The builder creates wheel, sdist, tracked-source ZIP, actual terminal capture and SHA256SUMS. It rejects
tracked private/runtime files and verifies packaged web assets, terminal module and approved portrait.
`verify_artifacts.py` installs **wheel and source ZIP independently in fresh venvs**, outside the checkout,
then checks actual console version, non-TTY startup, installed PTY onboarding, doctor/migration, offline
chat, loopback server, static assets and shared session endpoint. Candidate package/install evidence is
saved with the delivered artifacts; this is local verification, not a claim that GitHub CI has run the
unpublished branch. Source history keeps old preview videos labelled v0.1; they are not relabelled as RC
recordings. [Migration and rollback](MIGRATIONS.md), [packaging limits](PACKAGING.md).

## Stable release remains BLOCKED

No Google Desktop client or Gemini key is configured. Doctor reports both absent, model calls disabled
and live writes disabled. Therefore none of the following has passed:

1. Owner-authorized real OAuth, immutable channel verification and sourced live read.
2. Owner-authorized live configured-model request and content-quality/budget review.
3. One approved original/private upload verified against the intended real channel, privacy and remote ID.
4. Separately approved live thumbnail/caption upload and image/timed-playback review.
5. Any desired live publication/schedule/reply test, each with its own explicit approval.
6. Explicit final owner approval to tag and publish stable v1.0.0 after all mandatory gates.

No real upload, publication, reply, paid model call, timer installation, GitHub release or public site
deployment was performed. The next safe step is private local credential configuration, followed by
owner-authorized read-only testing. Never paste keys/tokens into chat. The app is loopback-only and
single-owner; hosted/team operation remains unsupported. No streaming/transcription/image-model/render
capability or performance/growth outcome is claimed.
