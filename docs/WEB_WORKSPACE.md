# Terminal identity, browser workspace

The website is Clira's daily workspace. Start it with `./run.sh --mode live serve` and open
`http://127.0.0.1:8765`. Existing CLI/TUI commands remain compatible for scripts and troubleshooting;
using the website does not require running the interactive terminal alongside it. Restart a server
started before this change, then reload the browser to load the new code.

## Visual rules

- Near-black background, warm ivory text, muted secondary text and antique-gold frames.
- The existing CLIRA block wordmark and interactive layered character are centered together. The
  approved original PNG remains the website fallback; the terminal keeps its Braille portrait. The tagline is **Intelligence Behind
  Creation**. No startup version badge. See [LIVE_CHARACTER.md](LIVE_CHARACTER.md).
- Monospace typography throughout, square controls, quiet source/state labels and gold focus rings.
- A four-panel explorer sits under the portrait: **Views, History, Projects and Controls**.
  Views retains all eight navigation controls: chat, videos, ideas, production, approvals, community,
  operations and settings. On narrow screens those controls wrap into two columns.
- History searches and resumes actual channel-scoped conversations, marks the current chat, and
  creates new conversations. It uses single-line titles grouped by Pinned, Today, Yesterday and
  older dates, with 50 metadata-only entries per page and server-side search. Show more loads older
  chats without downloading their message bodies. Projects switches existing channel/local workspaces and opens saved
  video ideas; ideas are labeled as ideas, not a separate new project database. Controls shows the
  selected channel, mode, provider enablement, write policy, jobs, approvals and saved profile values.
- On desktop the transcript and active sidebar panel scroll independently. The composer sits outside
  the transcript's scroll area, so it never covers a reply or its receipts. The portrait and wordmark
  compact into a small identity row while viewing History, leaving room for the list. On mobile the
  document scrolls naturally and long sidebar lists have their own scroll area.
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
Your messages are right-aligned bubbles; Clira replies are left-aligned, with open spacing instead of
repeated horizontal rules. Copy is a small icon below the message with an accessible name. Conversation
details and the channel snapshot are collapsed together, and setup controls disappear during a chat.

Use the **⋯** menu, right-click a history row, or press Shift+F10 on its title to rename, pin/unpin,
archive, export a local JSON file, or delete a conversation. Delete moves the chat to **Trash** after
confirmation. Choose Trash in the folder filter and use Restore chat to recover it. Archived chats
are separate from Recents; continuing an archived chat restores it to Recents. These are local owner
actions and never move data between channel workspaces. Account jobs, uploads and audit records remain
intact when a conversation is moved to Trash. The companion's click/hover reactions remain available;
the repeated “Tap to say hello” caption is removed.

Submitting a message immediately shows **Clira is thinking…** with a small antique-gold spinner in
the conversation and a quiet header status. Video attachment and package preparation have their own
truthful pending labels. No tool progress or percentage is invented. Success and failure both clear
the indicator. The system reduced-motion preference stops rotation while keeping the status visible.

Each submitted message scrolls to the latest content, including the pending indicator. Replies and
late-loading preview content continue following while you remain at the bottom. Scroll up to read
without being pulled away; **Latest message** returns to the bottom. Desktop scrolling stays inside
the conversation frame; mobile uses the document. New/resumed conversations open at their latest content.

Type `/new`, `/sessions`, `/projects`, `/controls`, `/channel` or `/help` for workspace shortcuts. `/chat`, `/videos`, `/ideas`,
`/production`, `/approvals`, `/community`, `/operations` (or `/status`) and `/settings` open the
corresponding view. Other messages, including `/upload PATH`, retain the existing agent path.

| Shortcut | Action |
| --- | --- |
| Alt+1 through Alt+8 | Chat, videos, ideas, production, approvals, community, operations, settings |
| Alt+[ / Alt+] | Previous / next sidebar panel |
| Left / Right on a sidebar tab | Previous / next tab, with focus following |
| Home / End on a sidebar tab | First / last tab |

A two-finger **horizontal** swipe inside the sidebar explorer switches its panels. Trackpads expose
this as horizontal wheel movement; touchscreens use an actual two-touch gesture. One gesture advances
one panel. Vertical scrolling, single-finger movement, pinch zoom, text selection, editable fields and
approval dialogs are excluded. Swipes elsewhere on the page retain browser behavior. Keyboard shortcuts
do not act through an open approval dialog. Discover these controls under **Keyboard shortcuts**.

History actions use the existing owner request token and channel policy. Pin/archive/trash preferences
live in SQLite settings alongside the existing conversation records; there is no new agent or transcript
schema. The regular conversations API retains its existing list shape. A metadata-only paginated index
is available with `?summary=true&folder=active&offset=0&limit=50&search=...`. Restart Clira after updating
this code, then refresh the browser so the new history endpoints and interface load together.

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

`tests/browser_workspace.py OUTPUT_DIRECTORY` holds real demo chat requests at the browser boundary
to test delayed success/failure feedback, automatic scroll and reading-up behavior. It also verifies
history/search/resume, real idea and profile data, all explorer panels at the seven widths in both
themes, keyboard navigation, gesture-event exclusions and reduced motion. Physical trackpad/touchscreen
hardware remains a separate manual check; synthetic browser events verify the handlers.

`tests/browser_chat_history.py OUTPUT_DIRECTORY` verifies 112 saved chats, paging/search, persistent
history actions, keyboard menu/dialog behavior, local export, real mouse-wheel scrolling in both
regions, unobscured chat content and short-height/mobile layouts. The backend history tests also check
owner tokens, cross-channel rejection, running-request protection, restart persistence and recoverable
deletion without provider calls or loss of account records.
