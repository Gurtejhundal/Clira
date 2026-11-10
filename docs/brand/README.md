# Clira character assets

The owner supplied the new monochrome portrait and detailed Braille text on 10 November 2026.

- `clira/web/assets/clira-portrait.png`: original PNG, unchanged; used by the website, browser icon, and GitHub README. This is also the upload-ready GitHub App logo. Changing a GitHub App's account settings is separate from committing its artwork.
- `clira/assets/clira_braille_detailed.txt`: supplied detailed Unicode portrait, preserved exactly.
- `clira/assets/clira_braille_v2_compact.txt`: 42-column by 22-row dot-resampled rendition for the terminal's fixed sidebar.
- `clira/assets/clira_braille_compact.txt`: original contract portrait retained for historical compatibility.

Use the complete PNG with `object-fit: contain`; do not stretch or crop the frame. Keep the Ink/Ivory/Antique Gold interface palette. The terminal background remains the user's own. Small terminals hide decorative artwork while retaining all commands.

The conversation uses a maximum 104-column reading width, padded prompt/answer groups, bold replies and gold question labels. Markdown headings, emphasis and code retain their hierarchy. Empty submissions do not create blank transcript turns. These are display changes; persisted conversations, secrets and permissions are unchanged.


## Name and tagline

**Storytelling meets strategic wisdom.**

Clira is an invented name inspired by **Clio**, the Greek Muse of history,
storytelling and preserving knowledge, and **Minerva**, the Roman goddess of
wisdom, intelligence and strategic thinking. This is the owner's naming story,
not a claim that Clira is an ancient word.

## Select and copy terminal answers

Mouse capture is off by default so the terminal emulator can select text normally.
Drag to select, then use the terminal's Copy action (usually Ctrl+Shift+C on Linux).
F2 toggles application mouse scrolling; F2 again restores native selection.
PgUp/PgDn and Ctrl+End work in both modes. Clipboard and selection appearance
are controlled by the terminal emulator; Clira does not write OSC 52 clipboard data.

## Terminal home hierarchy

The terminal tagline is **Intelligence Behind Creation**, directly under the centered
CLIRA wordmark. Startup branding omits the version; `/version` and `clira --version`
expose it on demand. The borderless, unchanged Braille artwork is centered in the
wide layout. Six aligned shortcuts remain below it: `/help`, `/new`, `/sessions`,
`/channel`, `/status`, `/approvals`. Existing commands remain available through help.

At 100 and 120 columns, the fixed sidebar leaves a separate conversation column.
At 80 columns, a compact centered header preserves all six shortcuts and hides
only decorative artwork. Short terminal heights also hide the portrait before
it can crowd the commands. Channel name and mode stay in the secondary header.
The welcome is emitted on interactive startup, outside the message loop.
