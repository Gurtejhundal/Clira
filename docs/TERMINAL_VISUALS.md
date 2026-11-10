# Clira terminal design language

The design authority is the supplied
[terminal/web master specification](../CLIRA_V1_TERMINAL_WEB_MASTER_SPEC_AND_CODEX_PROMPT.md),
particularly section 2 (identity and tokens) and section 3 (terminal experience), together with the
original [interface goals](../mds/Clira_Agent_Architecture_Build_Pack/Clira/docs/12_INTERFACE.md).
The newer master specification controls the approved character and supersedes the older pack's
exploratory mascot direction. No new brand asset or character is introduced.

The previous visual pass overemphasized the Hermes reference with a large block-letter banner,
gold outer frame, a tool-catalogue panel and added slogans. This revision follows Clira's own
restrained Ink/Ivory language: normal-case wordmark, native monospace typography, approved monochrome
portrait, deliberate spacing, neutral hierarchy and gold reserved for interaction/owner review.

![Clira first-run render](media/terminal/welcome-120.png)

[Returning workspace](media/terminal/workspace-120.png). These are previews of the actual Rich output
using synthetic demo data and installed system fonts, not native-window screenshots or live-channel
proof. The exporter uses the actual emitted ANSI, so mono previews retain no runtime color.

## Contract to implementation

| Supplied design rule | Terminal behavior |
|---|---|
| One recognizable Clira | Small `Clira` wordmark and exact “Your Creative Intelligence” tagline |
| Preserve the approved character | Exact 22-line Braille portrait; no ornaments or replacement mascot |
| Ink and Ivory as the main colors | Native foreground/background in auto/mono; manual light/dark text palettes |
| Restrained Antique Gold | Prompt, numbered choices, command shortcut and explicit owner-review emphasis |
| Calm operations cockpit | Channel ID, actual mode, model, policy and work counts precede next actions |
| Thin dividers, few panels | Neutral input divider; status/review panels only when useful; no outer dashboard frame |
| Lightweight conversational terminal | Ordinary scrolling REPL; no fullscreen takeover, large banner or tool wall |
| Clear, practical voice | Short guidance tied to working commands and real state; no added promotional slogans |

Manual light uses Ink `#252B24`, gold `#85652F` and secondary text `#62675C`. The secondary value is
slightly darker than the suggested muted token so small text passes 4.5:1 contrast on Ivory `#F8F7F2`.
Manual dark uses Ivory `#F3F0E8`, gold `#C5A368` and secondary `#ABB1A5`. Preview backgrounds use the
specified Ivory/Ink tokens; the running application never changes the user's terminal background.
Auto uses the terminal's normal foreground and ANSI accent palette. NO_COLOR and mono remove color
while retaining bold hierarchy and complete labels. No fonts are downloaded or distributed.

## Responsive behavior and controls

| Terminal | Composition |
|---|---|
| 100+ columns, 36+ rows | Approved portrait beside the small identity block and status/onboarding |
| 80–99 columns | Identity and readable content in one column; no portrait |
| 52–79 columns | Compact identity, status/choices and prompt |
| Under 52 columns or short windows | Minimal text; no large art or decorative frame |
| `--no-logo` | Small identity text; portrait hidden |

The canvas is bounded to 124 columns and reflows on resize. Enter sends, Ctrl+J adds a newline,
Ctrl+R searches history, Tab completes slash commands and Ctrl+D exits empty input. The five launch
questions use a small step label and practical guidance. Help is grouped by task, and saved records
retain complete IDs. Markdown replies preserve plain line breaks and Unicode bullets. Receipts show
actual tool sources; `/details` retains the full result. Measured elapsed time reflects actual work.

Owner approval still shows channel, immutable ID, target, operation, expiry, privacy, rights, file
hash and complete exact payload. Gold marks this deliberate review point. Typing APPROVE grants
consent only; execution is separate. Rendering cannot alter any policy, scope or stored conversation.

## Verification

After the design-language correction, **131 tests passed**, including the existing terminal PTY,
security, shared-session, packaging and API suites. Presentation checks cover 40/52/80/99/100/120/160
columns, short windows, mono/no-logo, actual status values, literal untrusted text, copyable IDs,
preserved reply bullets and secondary-text contrast. A regression checks that the invented block
banner, decorative outer frame and catalogue slogans do not return. Colored PTY tests exercise
startup, grouped help, completion and resizing. The approved portrait bytes are unchanged.

```bash
uv run --locked --extra dev pytest -q
uv run --locked --extra dev ruff check clira tests scripts
uv run --locked --extra dev ruff format --check clira tests scripts
node --check clira/web/app.js
bash -n run.sh
uv run --locked --extra dev python tests/browser_smoke.py --output work/design-language/browser
uv run --locked --extra dev python scripts/capture_terminal.py --output work/design-language/previews
```

The capture script produces welcome, workspace, conversation, help, light, mono and narrow/short
previews without external requests. Browser regression exercises all eight existing views at
1440/1280/768/390/320px. Package checks ensure the presentation module and portrait ship in the wheel;
clean wheel, source ZIP and sdist installation/runtime checks remain part of verification.

Exit an existing Clira process with Ctrl+D and run `uv run --locked clira` again to load this revision.
The same SQLite state, sessions, tools and account policies remain in use.
