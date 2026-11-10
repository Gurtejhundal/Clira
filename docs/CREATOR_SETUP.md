# Your personal Clira

Run `uv run --locked clira`. First run now starts a creator setup before the channel menu or agent.
Existing installations without a creator profile are invited through this setup once; existing
projects, channels, approvals and conversation IDs are preserved. `--quickstart` explicitly skips
personal onboarding for a temporary demo. It does not grant account permissions.

## The sequence

1. **You:** preferred name, passions, skills, experience and motivation.
2. **Your channel:** audience, language, timezone, voice and video format.
3. **Your direction:** a concrete 90-day goal and a realistic publishing cadence.
4. **Your resources:** weekly time, equipment, editing tools and production budget.
5. **How we work:** boundaries, feedback style, first tasks and review preferences.
6. **Memory and privacy:** choose whether your profile and relevant saved notes may be sent to your AI provider. Default: no.
Timezone entry accepts a city such as `Kolkata`, a timezone such as `Asia/Kolkata`, and
case/spacing variants such as `asia kolkata`. `skip`, `don't know`, or keeping the initial
default uses UTC, which is displayed before continuing. Unknown places are never guessed.

7. **Review:** inspect all 19 answers; enter a question number to edit, or type SAVE to approve the profile.
8. **Connections:** configure Gemini, connect a YouTube channel and/or configure a personal Telegram bot. Every connection can wait.
9. **First project:** choose a name. Clira reuses the saved interests, audience, language, schedule and format to create a local workspace, three starter ideas and a draft calendar. Voice, timezone, boundaries, goal and cadence are retained too.

The starter plan is an offline template, not completed audience research. The project is a local
workspace, not a newly created YouTube account. You can choose the channel menu instead, or use
`/project` later. An approved profile never enables account writes or approves jobs.

## Progress and memory

Each valid answer is saved immediately. `/back` or supported Shift+Backspace revisits a question;
Enter keeps the saved answer. `/cancel` pauses setup. Starting Clira again resumes unfinished setup,
including the connection/project checkpoint. Reopening a finished installation goes straight to the
workspace, using the saved identity and sessions.

All data belongs to the selected data directory (`.clira` by default, or `--data-dir` /
`CLIRA_DATA_DIR`). The SQLite store contains the approved profile, setup progress, projects, explicit
notes and conversation history. No hosted Clira database is involved. Use the same absolute data
directory from every terminal/website process. A separate directory creates a separate creator.

- `/profile`: inspect the approved profile.
- `/profile set name Asha`: change one field. Other field names appear in `/profile`.
- `/profile set share_with_model no`: stop including saved profile/notes in model context.
- `/profile forget`: requires typing FORGET PROFILE; removes the profile and setup draft. Projects, explicit notes, credentials and existing conversation history remain separate.
- `/setup`: review/edit the full creator setup again.
- `/remember Prefer practical repair videos under eight minutes`: explicitly save a note in the active workspace.
- `/memory`: inspect active-workspace notes and their IDs.
- `/forget memory_ID`: remove that note. Prior conversation messages are not rewritten.
- `/connections`: configure or revisit connection choices.
- `/project`: create another local project using your saved preferences.

Memory is inspectable owner-provided data, not hidden model training. With context sharing enabled,
the agent receives the approved profile and up to eight relevant active-workspace notes, alongside
recent conversation context. Notes from another channel are excluded. Profile and note contents are
untrusted context; they cannot authorize tools or override backend policy. Clira does not silently
infer and save new personal facts from every model reply. Use `/remember` for durable additions.
Disabling saved-memory sharing does not stop the current chat and tool context from reaching an
explicitly enabled cloud model.

## Credentials and connections

Both dotted Gemini authorization keys and legacy key syntax are accepted. A connection typo offers
retry/cancel while preserving your profile. Environment credentials take precedence over saved keys;
setup discloses an override without printing either credential.

Keys are entered in a masked field, excluded from terminal input history and transcript, and saved
in owner-only `secrets/` files (0600, directory 0700). Credentials never enter the creator profile,
notes or model prompt. Do not paste credentials into ordinary chat. Common key/token formats are
rejected in profile and note fields; this is not a comprehensive secret scanner.

**Gemini:** create a key in [Google AI Studio](https://aistudio.google.com/apikey), enter it in the
masked connection step, enter your exact available model ID, and explicitly choose whether to
allow provider requests. Setup makes no generation/test request. The current daily cap is 50
requests, not a currency spending limit. Saved runtime settings load on future CLI starts; explicit
environment variables take precedence. `/model` and `clira doctor` show configuration without keys.

**YouTube:** use a Desktop OAuth client from your Google project, enable YouTube Data API v3 and
YouTube Analytics API, and configure consent/test users. Start `clira --mode live` to authorize an
actual channel; demo mode never opens Google sign-in. The setup asks for the client JSON path and
uses the existing browser sign-in plus immutable channel-ID confirmation. The saved grant is
read-only. Model configuration, saved preferences and a Telegram pairing do not enable uploads.
See [Google setup](SETUP.md) for provider prerequisites.

**Telegram:** use [@BotFather](https://t.me/BotFather) `/newbot` to create your own bot and enter its
token in the masked connection step. Setup stores the token locally and shows a single-use pairing
code valid for ten minutes. It does not contact Telegram during setup. Bot messages pass through
Telegram's service; they are not device-only transport.

```bash
uv run --locked clira telegram run
# In a private chat with your bot, send: /pair CODE_SHOWN_LOCALLY
```

If the code expires, generate another locally with `clira telegram pair`. After pairing, only the
exact paired user in the exact private chat can use the bot. Groups, other users and duplicate
updates are ignored. The bot uses the active workspace; pin one explicitly with
`clira --channel WORKSPACE_ID telegram run`. It shares the same agent, profile, notes and persisted
sessions as the terminal. `/new` starts a bot conversation; `/status`, `/memory`, `/remember TEXT`
and `/forget ID` are available. Ordinary text uses the configured agent.

Exact approvals, execution, channel switching and connection setup stay in the local terminal.
Use `/sessions` there to open the Telegram session. Keep the device and `telegram run` process online;
no daemon, webhook, scheduler or hosted service is installed. Stop with Ctrl+C. A pre-existing bot
webhook conflicts with polling; use a dedicated bot or remove its webhook yourself before running.
Uncertain/failed updates are not automatically replayed. A failed outgoing response can leave a
completed local conversation: inspect saved sessions before resubmitting a task.

`clira telegram disconnect` removes the local bot credential and pairing. Revoking a bot token is
separate and happens through BotFather. Existing Telegram messages and local conversation history
are not deleted by disconnect.

The adapter follows the official [Telegram Bot API](https://core.telegram.org/bots/api) and
[BotFather setup](https://core.telegram.org/bots/features). Local tests mock Telegram/Gemini and
exercise actual terminal setup; live provider calls, Google OAuth and bot pairing still require
owner participation. No real messages or paid model calls were sent during development.
