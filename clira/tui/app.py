import difflib
import json
import os
import sys
import time
import webbrowser

import httpx
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.output import ColorDepth
from prompt_toolkit.styles import Style
from rich.console import Console

from ..agent import Agent
from ..config import CliraError
from ..service import DEMO_CHANNEL
from ..text import terminal_text
from ..workspaces import launch
from .presentation import Presentation

COMMANDS = [
    "/help",
    "/status",
    "/channel",
    "/connect",
    "/launch",
    "/back",
    "/new",
    "/sessions",
    "/resume",
    "/title",
    "/ideas",
    "/calendar",
    "/jobs",
    "/approvals",
    "/approve",
    "/model",
    "/mode",
    "/theme",
    "/details",
    "/sources",
    "/clear",
    "/quit",
    "/web",
]


class Terminal:
    def __init__(self, service, channel=None, resume=None, no_logo=False):
        self.service = service
        self.channel = channel
        self.conversation = resume
        self.last = None
        self.no_logo = no_logo
        self.console = Console(no_color="NO_COLOR" in os.environ, highlight=False)
        self.theme = service.store.setting("terminal_theme", "auto")
        self.prompt = None
        self.apply_theme()
        self.view = Presentation(self)

    def apply_theme(self):
        self.console.no_color = "NO_COLOR" in os.environ or self.theme == "mono"
        self.console.style = {"light": "#252b24", "dark": "#f3f0e8"}.get(self.theme)
        if self.prompt:
            self.prompt.color_depth = ColorDepth.DEPTH_1_BIT if self.console.no_color else None
            color = self.view.accent
            self.prompt.style = Style.from_dict({"prompt": "bold " + color, "placeholder": "ansibrightblack"})

    def print(self, text):
        # User/model strings are never Rich markup or terminal control instructions.
        self.console.print(terminal_text(text), markup=False)

    def status(self):
        self.view.status()

    def ask(self, text):
        if text == "❯ ":
            return self.prompt.prompt(
                [("class:prompt", text)],
                placeholder=[("class:placeholder", "Ask about your channel…  /help")],
            ).strip()
        return self.prompt.prompt(text, placeholder="").strip()

    def onboarding(self, show=True):
        previous_channel = self.channel
        if show:
            self.view.onboarding()
        while True:
            try:
                if self.onboarding_choice():
                    break
                self.view.onboarding()
            except CliraError as exc:
                self.print(exc.code + ": " + exc.message)
        if self.channel != previous_channel:
            self.conversation = self.last = None
        self.service.store.set_setting("active_workspace:" + self.service.config.mode, self.channel)

    def onboarding_choice(self):
        choice = self.ask("Choose 1 / 2 / 3 > ")
        if choice.lower() in {"0", "b", "back", "/back"}:
            if self.channel:
                self.print("Back to your workspace.")
                return True
            self.print("You are at the first menu. Choose a path or press Ctrl+D to exit.")
            return False
        if choice == "1":
            questions = [
                ("Your interest > ", "What could you keep making videos about?"),
                ("Your viewer > ", "Who should feel this channel was made for them?"),
                ("Language > ", "Which language will you speak to your viewers?"),
                ("Time per week > ", "Choose a realistic amount of creator time."),
                ("Format > ", "Shorts, longer videos, or another format you enjoy?"),
            ]
            answers = [""] * len(questions)
            step = 0
            while step < len(questions):
                question, hint = questions[step]
                self.view.launch_step(step + 1, hint)
                if answers[step]:
                    self.print("Saved answer: " + answers[step] + " · Enter keeps it.")
                answer = self.ask(question)
                if answer.lower() in {"b", "back", "/back"}:
                    if step == 0:
                        self.print("Back to the start menu. No draft created.")
                        return False
                    step -= 1
                    continue
                if answer.lower() in {"/cancel", "cancel"}:
                    self.print("Setup cancelled. No draft created.")
                    return False
                answers[step] = answer or answers[step]
                step += 1
            result = launch(self.service, *answers)
            self.channel = result["workspace"]["id"]
            self.print(result["plan"]["positioning"])
            self.print("Saved 3 starter ideas and a draft calendar. No YouTube account created.")
        elif choice == "2":
            return self.connect()
        elif choice == "3":
            if self.service.config.mode != "demo":
                self.print("Use clira --mode demo to explore synthetic data.")
                return False
            self.channel = DEMO_CHANNEL
        else:
            self.print("Choose one of the three paths.")
            return False
        return True

    def connect(self):
        if self.service.config.mode != "live":
            self.print(
                "Read-only OAuth: run clira --mode live connect. Configure CLIRA_GOOGLE_CLIENT_FILE privately first."
            )
            return False
        from ..youtube import connect

        result = connect(self.service.config, self.service.store, self.service.secrets, "read", None)
        self.print(json.dumps(result, indent=2))
        self.channel = result["id"]
        self.conversation = None
        self.service.store.set_setting("active_workspace:" + self.service.config.mode, self.channel)
        # OAuth includes explicit immutable-ID confirmation; never guess among returned accounts.
        return True

    def select_session(self, session_id=None):
        rows = self.service.store.sessions(self.channel)
        if not session_id:
            session_id = rows[0]["id"] if rows else None
        if not session_id:
            self.print("No saved sessions. Send a message or use /new.")
            return
        selected = self.service.store.session(self.channel, session_id)
        self.conversation = selected["id"]
        self.print(f"Resumed {selected['title']} · {self.conversation}")
        for message in selected["messages"]:
            if message["role"] == "assistant":
                self.view.answer(message["text"], message.get("receipts"))
            else:
                self.print("\nYOU\n" + message["text"])

    def command(self, line):
        cmd, _, arg = line.partition(" ")
        arg = arg.strip()
        store = self.service.store
        if cmd not in COMMANDS:
            suggestion = difflib.get_close_matches(cmd, COMMANDS, n=1)
            self.print("Unknown command." + (" Try " + suggestion[0] if suggestion else " Use /help."))
            return True
        if cmd == "/quit":
            self.print("Goodbye. No background worker is started by this terminal.")
            return False
        if cmd == "/help":
            self.view.help()
        elif cmd in {"/status", "/model", "/mode"}:
            self.status()
        elif cmd == "/connect":
            self.connect()
        elif cmd in {"/launch", "/back"}:
            self.onboarding()
        elif cmd == "/channel":
            rows = self.service.channels()
            if not arg:
                for c in rows:
                    self.print(f"{c['name']} · {c['mode']} · {c['id']}")
                arg = self.ask("Exact workspace ID (/back or empty cancels) > ")
            if arg.lower() in {"/back", "back", "b", "0"}:
                self.print("Back to your workspace.")
                return True
            if arg:
                self.service.policy.channel(arg)
                self.channel, self.conversation, self.last = arg, None, None
                store.set_setting("active_workspace:" + self.service.config.mode, arg)
                self.status()
        elif cmd == "/new":
            self.conversation = store.new_session(self.channel)["id"]
            self.last = None
            self.print("New session: " + self.conversation)
        elif cmd == "/resume":
            self.select_session(arg or None)
        elif cmd == "/sessions":
            self.view.records("Saved conversations", store.sessions(self.channel, arg), ["updated_at"])
        elif cmd == "/title":
            if not arg or not self.conversation:
                self.print("Use /title NAME in a saved session.")
            else:
                store.title_session(self.channel, self.conversation, arg)
                self.print("Session title saved.")
        elif cmd in {"/ideas", "/calendar"}:
            self.view.records(
                "Ideas" if cmd == "/ideas" else "Editorial calendar",
                store.list(self.channel, "idea" if cmd == "/ideas" else "calendar"),
                ["premise", "at", "status"],
            )
        elif cmd == "/jobs":
            self.view.records(
                "Durable jobs", self.service.tool_list_jobs(self.channel, None)["jobs"], ["state"]
            )
        elif cmd in {"/approvals", "/approve"}:
            rows = store.rows(
                "SELECT * FROM approvals WHERE channel_id=? ORDER BY created_at DESC", (self.channel,)
            )
            if cmd == "/approvals":
                self.view.records("Owner approvals", rows, ["status", "expires_at"])
                if not rows:
                    self.print("No approvals in this workspace.")
            else:
                matches = [a for a in rows if a["id"] == arg]
                if not matches:
                    raise CliraError("NOT_FOUND", "Approval not found in this workspace.")
                c = store.channel(self.channel)
                self.view.owner_review(c, matches[0])
                preview = {**matches[0], "payload": json.loads(matches[0]["payload"])}
                self.print(json.dumps(preview, indent=2, ensure_ascii=False))
                if self.ask("Type APPROVE to approve this exact payload > ") == "APPROVE":
                    self.service.policy.decide(self.channel, arg, True)
                    self.print(
                        "Approved. Execution is separate: clira jobs run JOB_ID --channel " + self.channel
                    )
                else:
                    self.print("No approval granted.")
        elif cmd == "/theme":
            if arg not in {"auto", "light", "dark", "mono"}:
                self.print("Use /theme auto|light|dark|mono")
            else:
                self.theme = arg
                store.set_setting("terminal_theme", arg)
                self.apply_theme()
                self.print("Theme saved: " + arg)
        elif cmd in {"/details", "/sources"}:
            self.print(json.dumps(self.last or {}, indent=2, ensure_ascii=False))
        elif cmd == "/clear":
            self.console.clear()
        elif cmd == "/web":
            url = "http://127.0.0.1:8765"
            try:
                health = httpx.get(url + "/health", timeout=2).json()
                if not health.get("ok") or health.get("store_id") != self.service.store.setting("store_id"):
                    raise ValueError()
                remote = httpx.get(url + "/api/conversations/" + self.channel, timeout=2).json()
                if self.conversation and not any(s["id"] == self.conversation for s in remote):
                    raise ValueError()
            except (httpx.HTTPError, ValueError):
                self.print(
                    "Matching local backend unavailable. Start clira serve with the same data directory and mode."
                )
                return True
            link = (
                url
                + "/?channel="
                + self.channel
                + ("&session=" + self.conversation if self.conversation else "")
            )
            if webbrowser.open(link):
                self.print(link)
            else:
                self.print("Browser unavailable. Open " + link)
        return True

    def run(self):
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            self.print('Interactive chat requires a terminal. Use clira chat --channel ID "question" --json.')
            return 0
        bindings = KeyBindings()

        @bindings.add("enter")
        def send(event):
            event.current_buffer.validate_and_handle()

        @bindings.add("c-j")
        def newline(event):
            event.current_buffer.insert_text("\n")

        @bindings.add("escape", "enter")
        def shift_enter(event):
            event.current_buffer.insert_text("\n")

        self.prompt = PromptSession(
            history=InMemoryHistory(),
            multiline=True,
            key_bindings=bindings,
            completer=WordCompleter(COMMANDS + [c["id"] for c in self.service.channels()], WORD=True),
            enable_history_search=True,
            reserve_space_for_menu=4,
            prompt_continuation="  ",
            color_depth=ColorDepth.DEPTH_1_BIT if self.console.no_color else None,
        )
        self.apply_theme()
        try:
            if self.channel:
                self.service.policy.channel(self.channel)
            else:
                saved = self.service.store.setting("active_workspace:" + self.service.config.mode)
                if saved and any(c["id"] == saved for c in self.service.channels()):
                    self.channel = saved
            self.view.welcome()
            if not self.channel:
                self.onboarding(show=False)
                self.status()
            if self.conversation:
                self.select_session(self.conversation)
            self.view.ready()
            interrupted = False
            while True:
                try:
                    self.view.composer()
                    line = self.ask("❯ ")
                    interrupted = False
                    if not line:
                        continue
                    if line.startswith("/"):
                        if not self.command(line):
                            break
                    else:
                        started = time.perf_counter()
                        with self.console.status(
                            "Clira is working on this request…", spinner_style=self.view.accent
                        ):
                            self.last = Agent(self.service).chat(self.channel, line, self.conversation)
                        self.conversation = self.last["conversation_id"]
                        self.view.answer(
                            self.last["message"], self.last["receipts"], time.perf_counter() - started
                        )
                except CliraError as exc:
                    self.view.error(exc.code, exc.message)
                except KeyboardInterrupt:
                    if interrupted:
                        break
                    interrupted = True
                    self.print(
                        "Input/request interrupted. Completed work may be saved. Ctrl+C again to exit; /jobs to inspect."
                    )
        except (EOFError, KeyboardInterrupt):
            pass
        self.print("Session saved. Goodbye.")
        return 0
