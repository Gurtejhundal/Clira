import difflib
import json
import os
import sys
import webbrowser
from importlib.resources import files

import httpx
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.output import ColorDepth
from rich.console import Console

from .. import __version__
from ..agent import Agent
from ..config import CliraError
from ..service import DEMO_CHANNEL
from ..text import terminal_text
from ..workspaces import launch

COMMANDS = [
    "/help",
    "/status",
    "/channel",
    "/connect",
    "/launch",
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

    def apply_theme(self):
        self.console.no_color = "NO_COLOR" in os.environ or self.theme == "mono"
        self.console.style = {"light": "#252b24", "dark": "#f3f0e8"}.get(self.theme)
        if self.prompt:
            self.prompt.color_depth = ColorDepth.DEPTH_1_BIT if self.console.no_color else None

    def print(self, text):
        # User/model strings are never Rich markup or terminal control instructions.
        self.console.print(terminal_text(text), markup=False)

    def status(self):
        c = self.service.policy.channel(self.channel) if self.channel else None
        label = {"demo": "DEMO · SYNTHETIC", "draft": "LOCAL DRAFT · Not connected", "live": "LIVE"}
        self.print(f"Clira {__version__} · {label.get(c['mode'], '') if c else 'No channel selected'}")
        if c:
            self.print(f"{c['name']}\n{c['id']}")
        config = self.service.config
        model = (
            "Offline · limited templates"
            if config.model == "offline"
            else (
                "Gemini · enabled"
                if config.allow_model_calls and os.getenv("GEMINI_API_KEY")
                else "Gemini · unavailable (enable calls and configure key privately)"
            )
        )
        self.print(f"Model: {model}")
        paused = self.service.store.setting("paused", False)
        writes = (
            "PAUSED"
            if paused
            else "owner approval required"
            if config.enable_writes
            else "live writes disabled"
        )
        self.print("Policy: " + writes)
        if c:
            pending = self.service.store.rows(
                "SELECT COUNT(*) AS count FROM approvals WHERE channel_id=? AND status='PENDING'",
                (self.channel,),
            )[0]["count"]
            jobs = self.service.store.rows(
                "SELECT state,COUNT(*) AS count FROM jobs WHERE channel_id=? GROUP BY state", (self.channel,)
            )
            self.print(
                f"Pending approvals: {pending} · Jobs: "
                + (", ".join(f"{j['state']} {j['count']}" for j in jobs) or "none")
            )
            if c["mode"] == "live":
                self.print("Account: " + ("connected" if c["connection"] else "Not connected"))
        if c and self.console.width >= 80:
            self.print(f"Scopes: {', '.join(c['connection'].get('scopes', [])) or 'none'}")
        if self.conversation:
            self.print(f"Session: {self.conversation}")

    def ask(self, text):
        return self.prompt.prompt(text).strip()

    def onboarding(self):
        while True:
            try:
                if self.onboarding_choice():
                    break
            except CliraError as exc:
                self.print(exc.code + ": " + exc.message)
        self.service.store.set_setting("active_workspace:" + self.service.config.mode, self.channel)

    def onboarding_choice(self):
        self.print(
            "Welcome to Clira.\n1  Start planning a new YouTube channel\n2  Connect an existing channel\n3  Explore synthetic demo data"
        )
        choice = self.ask("Choose 1 / 2 / 3 > ")
        if choice == "1":
            answers = [
                self.ask(q)
                for q in [
                    "Your interest > ",
                    "Your viewer > ",
                    "Language > ",
                    "Time per week > ",
                    "Format > ",
                ]
            ]
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
            self.print(message["role"] + ": " + message["text"])

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
            self.print(
                " ".join(COMMANDS)
                + "\nEnter sends · Ctrl+J newline · Ctrl+R history · Ctrl+D exits\n/clear clears display only. /approve never executes an action."
            )
        elif cmd in {"/status", "/model", "/mode"}:
            self.status()
        elif cmd == "/connect":
            self.connect()
        elif cmd == "/launch":
            self.onboarding()
        elif cmd == "/channel":
            rows = self.service.channels()
            if not arg:
                for c in rows:
                    self.print(f"{c['name']} · {c['mode']} · {c['id']}")
                arg = self.ask("Exact workspace ID (empty cancels) > ")
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
            for s in store.sessions(self.channel, arg):
                self.print(f"{s['id']} · {s['title']} · {s['updated_at']}")
        elif cmd == "/title":
            if not arg or not self.conversation:
                self.print("Use /title NAME in a saved session.")
            else:
                store.title_session(self.channel, self.conversation, arg)
                self.print("Session title saved.")
        elif cmd in {"/ideas", "/calendar"}:
            for r in store.list(self.channel, "idea" if cmd == "/ideas" else "calendar"):
                self.print(f"{r['id']} · {r.get('title', '')} · {r.get('at', r.get('premise', ''))}")
        elif cmd == "/jobs":
            for j in self.service.tool_list_jobs(self.channel, None)["jobs"]:
                self.print(f"{j['id']} · {j['operation']} · {j['state']}")
        elif cmd in {"/approvals", "/approve"}:
            rows = store.rows(
                "SELECT * FROM approvals WHERE channel_id=? ORDER BY created_at DESC", (self.channel,)
            )
            if cmd == "/approvals":
                for a in rows:
                    self.print(f"{a['id']} · {a['operation']} · {a['status']} · {a['expires_at']}")
                if not rows:
                    self.print("No approvals in this workspace.")
            else:
                matches = [a for a in rows if a["id"] == arg]
                if not matches:
                    raise CliraError("NOT_FOUND", "Approval not found in this workspace.")
                c = store.channel(self.channel)
                self.print(f"{c['name']} · {self.channel}")
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
            completer=WordCompleter(COMMANDS + [c["id"] for c in self.service.channels()]),
            enable_history_search=True,
            color_depth=ColorDepth.DEPTH_1_BIT if self.console.no_color else None,
        )
        if not self.no_logo and self.console.width >= 100:
            self.print(files("clira").joinpath("assets/clira_braille_compact.txt").read_text())
        try:
            if self.channel:
                self.service.policy.channel(self.channel)
            else:
                saved = self.service.store.setting("active_workspace:" + self.service.config.mode)
                if saved and any(c["id"] == saved for c in self.service.channels()):
                    self.channel = saved
                else:
                    self.onboarding()
            self.status()
            if self.conversation:
                self.select_session(self.conversation)
            interrupted = False
            while True:
                try:
                    line = self.ask("❯ ")
                    interrupted = False
                    if not line:
                        continue
                    if line.startswith("/"):
                        if not self.command(line):
                            break
                    else:
                        with self.console.status("Working on this request…"):
                            self.last = Agent(self.service).chat(self.channel, line, self.conversation)
                        self.conversation = self.last["conversation_id"]
                        self.print(self.last["message"])
                        if self.last["receipts"]:
                            self.print(
                                "Sources: "
                                + "; ".join(
                                    r.get("tool", "tool") + " · " + r.get("source", "unavailable")
                                    for r in self.last["receipts"]
                                )
                            )
                        self.print(
                            f"{len(self.last['receipts'])} tool receipts · /details · session {self.conversation}"
                        )
                except CliraError as exc:
                    self.print(exc.code + ": " + exc.message)
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
