# Clira terminal visuals

The owner-approved composition keeps the large CLIRA lettering, fine rounded workspace border,
and the supplied Braille portrait beside actual channel status or first-run choices. The latest
owner clarification applies the design Markdown to the **color palette**, preserving this layout.
The [master specification](../CLIRA_V1_TERMINAL_WEB_MASTER_SPEC_AND_CODEX_PROMPT.md) supplies the
Ink/Ivory and Antique Gold tokens and the exact approved character.

![Clira first-run render](media/terminal/welcome-120.png)

[Returning workspace](media/terminal/workspace-120.png). These are previews of the actual Rich
renderer with synthetic data and installed system fonts. They are not native-window screenshots
or live-channel verification. The capture script exports emitted ANSI, including actual mono output.

## Palette and hierarchy

| Role | Light | Dark |
|---|---|---|
| Main text | Ink `#252B24` | Ivory `#F3F0E8` |
| CLIRA lettering, frame, headings and prompt | Antique Gold `#85652F` | Antique Gold `#C5A368` |
| Secondary text | `#62675C` | `#ABB1A5` |
| Preview background | Ivory `#F8F7F2` | Ink `#171A18` |

The runtime inherits the user's terminal background. Auto keeps the native main foreground,
uses the light gold when COLORFGBG reports a conventional white background (7 or 15), and otherwise
uses dark-theme gold. `/theme light` or `/theme dark` explicitly selects the palette when the
terminal supplies no background hint. The prompt uses the same gold as the lettering and borders.
Secondary light text is slightly darker than the suggested muted token to pass 4.5:1 contrast on
Ivory. NO_COLOR and mono remove color while preserving hierarchy and labels. The exact approved
22-line portrait remains monochrome. No fonts are downloaded or distributed.

## Responsive composition

| Available space | Behavior |
|---|---|
| 100+ columns and 36+ rows | Large wordmark, portrait and status/choices side by side inside a rounded frame |
| 80–99 columns | Large wordmark and tagline; framed content without portrait |
| 52–79 columns | Large lettering with tagline below; single-column framed content |
| Under 52 columns | Small text identity and unframed content |
| Short windows | Compact identity, no portrait, condensed choices |
| `--no-logo` | Small identity and content, without large lettering or portrait |

The canvas is bounded to 124 columns and reflows on resize. Channel name, complete immutable ID,
actual model, policy, approvals and job counts remain visible. Toolkit summaries describe existing
tools and disclose the OAuth requirement. Five launch steps, grouped help and saved-session records
retain their existing behavior. Markdown replies preserve line breaks and Unicode bullets; receipts
show actual sources and `/details` exposes complete results. Elapsed time measures actual work.

Enter sends, Ctrl+J adds a newline, Ctrl+R searches history, Tab completes slash commands and Ctrl+D
exits empty input. Owner review retains the exact channel, target, operation, expiry, privacy,
rights, file hash and complete payload. Approval and execution remain separate.

## Verification

**134 local tests pass**, including terminal PTY, security, shared-session, packaging and API suites.
Presentation tests cover 40/52/80/99/100/120/160 columns, short windows, mono/no-logo, real status,
copyable IDs, literal untrusted text, reply bullets, readable secondary contrast and the restored
large lettering/frame. Auto-mode tests verify actual gold in rendered output, background hints and
absence of background painting. Colored PTY tests exercise startup, help, completion and resize.

```bash
uv run --locked --extra dev pytest -q
uv run --locked --extra dev ruff check clira tests scripts
uv run --locked --extra dev ruff format --check clira tests scripts
node --check clira/web/app.js
bash -n run.sh
uv run --locked --extra dev python scripts/capture_terminal.py --output work/terminal-palette/previews
uv run --locked --extra dev python tests/browser_smoke.py --output work/terminal-palette/browser
```

The capture gallery includes welcome, workspace, replies, help, light, mono and narrow/short views.
Browser regression covers all eight website views at 1440/1280/768/390/320px. Packaging verification
checks fresh wheel, source ZIP and sdist installations and their terminal/runtime behavior.

Exit an existing process with Ctrl+D, then run `uv run --locked clira` to load this revision.
