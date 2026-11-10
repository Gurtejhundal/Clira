# Clira character assets

The owner supplied the new monochrome portrait and detailed Braille text on 10 November 2026.

- `clira/web/assets/clira-portrait.png`: original PNG, unchanged; used by the website, browser icon, and GitHub README. This is also the upload-ready GitHub App logo. Changing a GitHub App's account settings is separate from committing its artwork.
- `clira/assets/clira_braille_detailed.txt`: supplied detailed Unicode portrait, preserved exactly.
- `clira/assets/clira_braille_v2_compact.txt`: 42-column by 22-row dot-resampled rendition for the terminal's fixed sidebar.
- `clira/assets/clira_braille_compact.txt`: original contract portrait retained for historical compatibility.

Use the complete PNG with `object-fit: contain`; do not stretch or crop the frame. Keep the Ink/Ivory/Antique Gold interface palette. The terminal background remains the user's own. Small terminals hide decorative artwork while retaining all commands.

The conversation uses a maximum 104-column reading width, padded prompt/answer groups, bold replies and gold question labels. Markdown headings, emphasis and code retain their hierarchy. Empty submissions do not create blank transcript turns. These are display changes; persisted conversations, secrets and permissions are unchanged.
