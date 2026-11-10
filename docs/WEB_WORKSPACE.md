# Terminal identity, browser workspace

The website is Clira's daily workspace. Start it with `./run.sh --mode live serve` and open
`http://127.0.0.1:8765`. Existing CLI/TUI commands remain compatible for scripts and troubleshooting;
using the website does not require running the interactive terminal alongside it. Restart a server
started before this change, then reload the browser to load the new code.

## Visual rules

- Near-black background, warm ivory text, muted secondary text and antique-gold frames.
- The existing CLIRA block wordmark and complete, borderless Unicode Braille character are centered
  together. The tagline is **Intelligence Behind Creation**. No startup version badge.
- Monospace typography throughout, square controls, quiet source/state labels and gold focus rings.
- All eight navigation controls sit directly under the portrait: chat, videos, ideas, production,
  approvals, community, operations and settings. On narrow screens the navigation wraps into two
  columns rather than hiding controls in a horizontally scrolling strip.
- Desktop conversation scrolls inside its frame. On mobile the document scrolls naturally, with no
  input overlay covering the upload review. Portrait sizes change without cropping its characters.
- The welcome and starter prompts appear for an empty conversation. Replies and resumed conversations
  do not reprint them. Channel snapshot, setup and session details remain available as disclosures.
- Dark is the first-use theme; explicit light/system preferences remain available in Settings.
  Reduced-motion preferences stop cursor blinking. No CRT noise, fake typing or simulated progress.

## Input, reading and navigation

Enter sends and Shift+Enter inserts a newline. Insert, or the visible cursor button, toggles between
block and line carets. This changes appearance only; ordinary text insertion, selection, IME input,
keyboard shortcuts and paste retain browser behavior. The block caret follows wrapping and hides
while text is selected. Cursor preference is saved locally.

Replies support headings, bold text, inline/fenced code, lists, tables and HTTP(S) Markdown links.
The renderer builds text nodes and allowlisted elements; model HTML is displayed as text.
Every message has a Copy button. Native drag selection and the browser's copy shortcut also work.

Type `/new`, `/sessions`, `/channel` or `/help` for workspace shortcuts. `/chat`, `/videos`, `/ideas`,
`/production`, `/approvals`, `/community`, `/operations` (or `/status`) and `/settings` open the
corresponding view. Other messages, including `/upload PATH`, retain the existing agent path.

## Upload from the conversation

Attach an MP4, send “upload”, review the actual video and editable package, complete the owner
rights/disclosure review, then click **Approve & upload privately**. Preparation and final execution
use the existing channel-bound policy, immutable media hash, durable job and receipt verification.
See [CHAT_UPLOAD.md](CHAT_UPLOAD.md) for supported analysis and current limits. This interface does
not claim audio transcription, automatic video rendering, or automatic thumbnail/caption uploads.

## Verification

`tests/browser_smoke.py` exercises all eight views at 320, 390, 768, 820, 1024, 1280 and 1440 pixels,
light/dark settings, exact portrait bounds, shared sessions, native clipboard copying, safe Markdown,
Shift+Enter, Insert and slash navigation. `tests/browser_upload_flow.py` plays the actual H.264 test
attachment, edits its preview and completes a private-upload simulation. Both use isolated demo data
with model calls and live writes disabled. A simulated upload does not prove the new flow against a
real Google account.
