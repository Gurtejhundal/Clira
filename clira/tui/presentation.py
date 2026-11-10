"""Terminal presentation only. Operational state stays in the existing service."""

import json
import os
from importlib.resources import files

from rich import box
from rich.console import Group
from rich.markdown import Markdown
from rich.padding import Padding
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from ..contracts import TOOLS
from ..creator import model_key
from ..text import terminal_text

WORDMARK = (
    " ██████╗██╗     ██╗██████╗  █████╗ ",
    "██╔════╝██║     ██║██╔══██╗██╔══██╗",
    "██║     ██║     ██║██████╔╝███████║",
    "██║     ██║     ██║██╔══██╗██╔══██║",
    "╚██████╗███████╗██║██║  ██║██║  ██║",
    " ╚═════╝╚══════╝╚═╝╚═╝  ╚═╝╚═╝  ╚═╝",
)

HELP = [
    ("YOUR CLIRA", "/setup · /profile · /project", "Your creator profile and next project"),
    ("", "/memory · /remember TEXT", "Review or explicitly save a local note"),
    ("", "/forget ID · /connections", "Remove a note or configure connections"),
    ("WORKSPACE", "/channel [ID]", "Choose a channel or local workspace"),
    ("", "/launch · /connect", "Plan locally or start read-only OAuth"),
    ("", "/back", "Return to the start menu; keep saved work"),
    ("CONVERSATIONS", "/new · /sessions [search]", "Start or find saved conversations"),
    ("", "/resume [ID] · /title NAME", "Resume or name a conversation"),
    ("CREATOR WORK", "/ideas · /calendar", "Saved ideas and draft plans"),
    ("", "/jobs · /approvals", "Durable work and owner review"),
    ("", "/approve ID", "Review exact payload; never executes"),
    ("INSPECT", "/status · /model · /mode · /version", "Current account, runtime and policy"),
    ("", "/details · /sources", "Complete last receipt and evidence"),
    ("PREFERENCES", "/theme auto|light|dark|mono", "Appearance; NO_COLOR takes priority"),
    ("", "/web · /clear · /quit", "Open matching website, clear, exit"),
]


def literal(value, style=None):
    return Text(terminal_text(value), style=style or "", overflow="fold")


class Presentation:
    def __init__(self, terminal):
        self.terminal = terminal

    @property
    def console(self):
        return self.terminal.console

    @property
    def width(self):
        return min(self.console.width, 124)

    @property
    def palette(self):
        if self.terminal.theme == "auto":
            # Respect the conventional terminal background hint when available.
            background = os.getenv("COLORFGBG", "").rsplit(";", 1)[-1]
            return "light" if background in {"7", "15"} else "dark"
        return self.terminal.theme

    @property
    def accent(self):
        if self.palette == "light":
            return "#85652f"
        return "#c5a368"

    @property
    def muted(self):
        # Dimming halves contrast on light terminals. Explicit themes use readable
        # secondary colors; mono inherits the owner's normal foreground.
        if self.console.no_color:
            return ""
        return {"light": "#62675c", "dark": "#abb1a5"}.get(self.palette, "")

    def emit(self, renderable):
        if self.terminal.screen:
            self.terminal.screen.emit(renderable)
        else:
            self.console.print(renderable, width=self.width)

    def heading(self, label):
        return literal(label, "bold " + self.accent)

    def notice(self, text):
        text = terminal_text(text)
        heading, separator, body = text.partition(" · ")
        if separator and heading in {"CONNECTIONS", "YOUR CHANNEL", "YOUR CREATOR MEMORY"}:
            self.emit(Padding(Group(self.heading(heading), Text(""), literal(body)), (1, 2)))
        else:
            self.emit(Padding(literal(text), (0, 2)))

    def runtime(self):
        terminal = self.terminal
        config = terminal.service.config
        if config.model == "offline":
            model = "Offline · limited templates"
        elif config.allow_model_calls and model_key(terminal.service):
            model = config.model_id + " · enabled"
        else:
            model = "Gemini · unavailable"
        policy = (
            "PAUSED"
            if terminal.service.store.setting("paused", False)
            else "owner approval required"
            if config.enable_writes
            else "live writes disabled"
        )
        return model, policy

    def facts(self):
        terminal = self.terminal
        channel = terminal.service.policy.channel(terminal.channel) if terminal.channel else None
        model, policy = self.runtime()
        mode = {
            "demo": "DEMO · SYNTHETIC",
            "draft": "LOCAL DRAFT · Not connected",
            "live": "LIVE · " + ("connected" if channel and channel["connection"] else "Not connected"),
        }.get(channel["mode"] if channel else terminal.service.config.mode, "LOCAL")
        rows = [("Mode", mode), ("Model", model), ("Policy", policy)]
        if channel:
            rows[:0] = [("Channel", channel["name"]), ("ID", channel["id"])]
            pending = terminal.service.store.rows(
                "SELECT COUNT(*) AS count FROM approvals WHERE channel_id=? AND status='PENDING'",
                (terminal.channel,),
            )[0]["count"]
            jobs = terminal.service.store.rows(
                "SELECT state,COUNT(*) AS count FROM jobs WHERE channel_id=? GROUP BY state",
                (terminal.channel,),
            )
            rows.append(("Review", f"{pending} pending approvals"))
            rows.append(("Jobs", ", ".join(f"{r['state']} {r['count']}" for r in jobs) or "none"))
        return rows

    def fact_table(self, rows):
        table = Table.grid(padding=(0, 2), expand=True)
        table.add_column(width=7, style=self.muted, no_wrap=True)
        table.add_column(overflow="fold", ratio=1)
        for label, value in rows:
            table.add_row(literal(label), literal(value, "bold" if label in {"Channel", "Mode"} else ""))
        return table

    def choices(self):
        entries = [self.heading("Welcome to Clira."), Text("")]
        compact = self.width < 52 or self.console.height < 30
        choices = [
            ("1", "Start planning a new YouTube channel", "Identity, first ideas and a draft calendar"),
            ("2", "Connect an existing channel", "Read-only Google OAuth · exact channel review"),
            ("3", "Explore synthetic demo data", "No account, API key or real channel actions"),
        ]
        for number, title, description in choices:
            entry = Text.assemble((number + "  ", "bold " + self.accent), (title, "bold"))
            entries.append(entry)
            if not compact:
                entries.extend([literal("   " + description, self.muted), Text("")])
        model, policy = self.runtime()
        entries.extend(
            [
                self.heading("LOCAL BY DEFAULT"),
                literal("Local workspace · saved on this computer.", self.muted),
                Text(""),
                literal("Model   " + model),
                literal("Policy  " + policy),
                literal("Human approval for channel changes.", self.muted),
                *(
                    [literal("0  Back to your workspace", "bold " + self.accent)]
                    if self.terminal.channel
                    else []
                ),
            ]
        )
        return Group(*entries)

    def welcome(self):
        terminal = self.terminal
        roomy = self.width >= 100 and self.console.height >= 36
        logo = not terminal.no_logo
        self.emit(Text(""))
        if logo and self.width >= 52 and self.console.height >= 30:
            mark = Text("\n".join(WORDMARK), style="bold " + self.accent)
            header = Table.grid(padding=(0, 3), expand=True)
            header.add_column(width=43)
            header.add_column(vertical="bottom", ratio=1)
            header.add_row(
                mark,
                Group(
                    self.heading("INTELLIGENCE BEHIND CREATION"),
                    literal("The work behind your YouTube channel.", self.muted),
                    literal("Local workspace", self.muted),
                ),
            )
            # A narrow terminal gets the tagline underneath instead of a crushed column.
            if self.width < 80:
                self.emit(mark)
                self.emit(literal("Intelligence Behind Creation", self.muted))
            else:
                self.emit(Padding(header, (0, 2)))
            self.emit(Text(""))
        else:
            self.emit(self.heading("CLIRA"))
            self.emit(literal("Intelligence Behind Creation", self.muted))
            self.emit(Text(""))

        if terminal.channel:
            right = Group(
                self.heading("YOUR WORKSPACE"),
                Text(""),
                self.fact_table(self.facts()),
                Text(""),
                self.heading("CREATOR TOOLKIT"),
                literal("Plan      ideas · scripts · calendar"),
                literal("Package   titles · thumbnails · timed captions"),
                literal("Account   reads · uploads · community"),
                literal("Account tools require OAuth and owner policy.", self.muted),
                Text(""),
                literal(f"{len(TOOLS)} typed tools · /help to explore", self.muted),
                Text(""),
                self.heading("What should we work on?"),
                literal("Try: Show my latest videos", self.muted),
            )
        else:
            right = self.choices()

        if logo and roomy:
            portrait = Text(
                files("clira").joinpath("assets/clira_braille_v2_compact.txt").read_text().rstrip("\n"),
                no_wrap=True,
                overflow="fold",
            )
            layout = Table.grid(padding=(0, 3), expand=True)
            layout.add_column(width=43)
            layout.add_column(ratio=1)
            layout.add_row(portrait, right)
            body = layout
        else:
            body = right
        if self.width >= 52:
            self.emit(
                Panel(
                    body,
                    title=literal(" YOUTUBE WORKSPACE ", self.accent),
                    subtitle=literal(" ONE AGENT · YOUR CHANNEL · YOUR CALL ", self.muted),
                    title_align="left",
                    subtitle_align="left",
                    border_style=self.accent,
                    box=box.ROUNDED,
                    padding=(1, 2),
                )
            )
        else:
            self.emit(body)
        self.emit(Text(""))

    def onboarding(self):
        if self.terminal.screen:
            self.emit(Padding(self.choices(), (1, 2)))
        elif self.width >= 52:
            self.emit(Panel(self.choices(), border_style=self.accent, padding=(1, 2), box=box.ROUNDED))
        else:
            self.emit(self.choices())

    def launch_step(self, number, hint):
        self.emit(Text(""))
        self.emit(self.heading(f"CHANNEL LAUNCH  /  {number} OF 5"))
        self.emit(literal(hint, self.muted))
        self.emit(literal("/back previous step · /cancel start menu", self.muted))

    def status(self):
        terminal = self.terminal
        rows = self.facts()
        if terminal.channel:
            channel = terminal.service.store.channel(terminal.channel)
            scopes = channel["connection"].get("scopes", [])
            rows.append(("Scopes", ", ".join(scopes) or "none"))
        if terminal.conversation:
            rows.append(("Session", terminal.conversation))
        content = self.fact_table(rows)
        if self.width >= 52:
            self.emit(Panel(content, title=self.heading("Workspace status"), box=box.ROUNDED, padding=(1, 2)))
        else:
            self.emit(content)

    def ready(self):
        if self.terminal.screen:
            return
        self.emit(
            Text.assemble(
                ("  /help", "bold " + self.accent),
                (" commands   /back start menu   /sessions saved work   /web website", self.muted),
            )
        )
        self.emit(literal("  Enter sends · Ctrl+J newline · Ctrl+R history · Ctrl+D exits", self.muted))
        self.emit(Text(""))

    def composer(self):
        label = "YOU"
        if self.terminal.channel:
            name = self.terminal.service.store.channel(self.terminal.channel)["name"]
            label += "  /  " + name
        if self.width >= 52:
            self.emit(Text(""))
            self.emit(Rule(self.heading(label), align="left", style=self.muted))

    def answer(self, text, receipts=None, elapsed=None):
        self.emit(Text(""))
        self.emit(Rule(self.heading("CLIRA"), align="left", style=self.accent))
        self.emit(Text(""))
        # Markdown is presentation only; hyperlinks cannot inject OSC terminal links.
        content = Markdown(terminal_text(text), hyperlinks=False, code_theme="ansi_dark")
        # Tool/offline replies also use plain newlines and Unicode bullets. Preserve their
        # line boundaries instead of merging them into a Markdown paragraph.
        tokens = list(content.parsed)
        while tokens:
            token = tokens.pop()
            if token.type == "softbreak":
                token.type = "hardbreak"
            tokens.extend(token.children or [])
        self.emit(Padding(content, (0, 2)) if self.width >= 52 else content)
        self.emit(Text(""))
        if receipts:
            table = Table(box=None, padding=(0, 2), show_header=False, expand=False)
            table.add_column(style=self.muted, overflow="fold")
            table.add_column(style=self.muted, overflow="fold")
            for receipt in receipts[:4]:
                ok = receipt.get("ok", False)
                label = receipt.get("tool", receipt.get("error", {}).get("code", "tool"))
                table.add_row(
                    literal(("✓ " if ok else "! ") + label), literal(receipt.get("source", "unavailable"))
                )
            self.emit(Padding(table, (0, 2)))
        if elapsed is not None:
            total = len(receipts or [])
            self.emit(literal(f"  {total} tool receipts · {elapsed:.1f}s · /details", self.muted))
        if self.terminal.conversation:
            self.emit(literal("  session " + self.terminal.conversation, self.muted))
        self.emit(Text(""))

    def help(self):
        self.emit(self.heading("A little clarity. A lot of possibility."))
        table = Table(box=None, padding=(0, 2), show_header=False, expand=True)
        if self.width >= 80:
            table.add_column(style="bold " + self.accent, width=14)
            table.add_column(width=28)
            table.add_column(overflow="fold")
            for section, command, description in HELP:
                table.add_row(section, command, description)
            self.emit(table)
        else:
            for section, command, description in HELP:
                if section:
                    self.emit(self.heading("\n" + section))
                self.emit(literal(command, "bold"))
                self.emit(literal(description, self.muted))
        self.emit(
            literal(
                "\n/help shows this guide. /clear clears display only. /approve never executes.", self.muted
            )
        )
        self.ready()

    def records(self, title, records, fields):
        self.emit(self.heading(title))
        if not records:
            self.emit(literal("Nothing saved here yet.", self.muted))
            return
        for record in records:
            self.emit(literal(record.get("title") or record.get("operation") or record.get("id"), "bold"))
            self.emit(literal(record["id"], self.muted))
            for field in fields:
                if record.get(field):
                    self.emit(literal(f"{field.replace('_', ' ')}  {record[field]}"))
            self.emit(Text(""))

    def owner_review(self, channel, approval):
        self.emit(Rule(self.heading("OWNER REVIEW · execution is separate"), style=self.accent))
        rows = [
            ("Channel", channel["name"]),
            ("ID", channel["id"]),
            ("Action", approval["operation"]),
            ("Expires", approval["expires_at"]),
        ]
        payload = json.loads(approval["payload"])
        for key, label in [
            ("video_id", "Video"),
            ("comment_id", "Comment"),
            ("privacy", "Privacy"),
            ("visibility", "Privacy"),
            ("filename", "File"),
            ("rights", "Rights"),
            ("asset_sha256", "SHA-256"),
            ("sha256", "SHA-256"),
        ]:
            if key in payload:
                rows.append((label, payload[key]))
        self.emit(self.fact_table(rows))
        self.emit(literal("Review the complete exact payload below before typing APPROVE.", self.muted))

    def error(self, code, message):
        content = Text.assemble((terminal_text(code) + "\n", "bold"), terminal_text(message))
        if self.width >= 52:
            self.emit(
                Panel(
                    content,
                    title="Request needs attention",
                    border_style="#dc8984",
                    box=box.ROUNDED,
                    padding=(1, 2),
                    title_align="left",
                )
            )
        else:
            self.emit(content)
