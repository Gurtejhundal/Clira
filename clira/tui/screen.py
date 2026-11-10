"""Persistent terminal shell; existing synchronous workflows run one at a time."""

import asyncio
import io
import queue
import threading
from importlib.resources import files

from prompt_toolkit.application import Application
from prompt_toolkit.completion import CompleteEvent, WordCompleter
from prompt_toolkit.data_structures import Point
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.formatted_text import ANSI, to_formatted_text
from prompt_toolkit.formatted_text.utils import split_lines
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, VSplit, Window
from prompt_toolkit.layout.containers import DynamicContainer, Float, FloatContainer
from prompt_toolkit.layout.controls import FormattedTextControl, UIContent, UIControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.output import ColorDepth
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame, SearchToolbar, TextArea
from rich.console import Console
from rich.text import Text

from .. import __version__
from ..text import terminal_text
from .presentation import WORDMARK


class Transcript(UIControl):
    def __init__(self, shell):
        self.shell = shell

    def create_content(self, width, height):
        lines = self.shell.render_lines(width)
        self.shell.page_height = height
        self.shell.offset = min(self.shell.offset, max(0, len(lines) - 1))
        return UIContent(
            get_line=lambda i: lines[i],
            line_count=len(lines),
            cursor_position=Point(x=0, y=max(0, len(lines) - 1 - self.shell.offset)),
            show_cursor=False,
        )


class SplitScreen:
    def __init__(self, terminal):
        from .app import COMMANDS

        self.terminal = terminal
        self.blocks = []
        self.lock = threading.Lock()
        self.answers = queue.Queue()
        self.waiting = False
        self.busy = False
        self.prompt_label = "Starting Clira…"
        self.offset = 0
        self.page_height = 20
        self.size = (120, 45)
        self.loop = None
        self.worker = None
        self.failure = None
        self.cache_key = None
        self.cache_count = 0
        self.lines = []
        self.history = InMemoryHistory()
        self.search = SearchToolbar()
        self.input = TextArea(
            height=Dimension(min=1, preferred=2, max=5),
            dont_extend_height=True,
            multiline=True,
            wrap_lines=True,
            history=self.history,
            search_field=self.search,
            completer=WordCompleter(COMMANDS + [c["id"] for c in terminal.service.channels()], WORD=True),
            complete_while_typing=False,
            read_only=Condition(lambda: not self.waiting),
            style="class:input",
        )
        self.log = Window(Transcript(self), wrap_lines=False, always_hide_cursor=True)
        self.sidebar = Window(
            FormattedTextControl(self.sidebar_text), width=44, dont_extend_width=True, style="class:body"
        )
        self.right = HSplit(
            [
                Window(FormattedTextControl(self.title), height=1, style="class:heading"),
                self.log,
                Window(FormattedTextControl(self.scroll_hint), height=1, style="class:muted"),
                FloatContainer(
                    Frame(self.input, title=lambda: self.prompt_label, style="class:composer"),
                    floats=[Float(xcursor=True, ycursor=True, content=CompletionsMenu(max_height=6))],
                ),
                self.search,
            ]
        )
        self.wide = VSplit(
            [
                Frame(self.sidebar, title=" CLIRA ", style="class:frame"),
                Window(width=1, char=" "),
                self.right,
            ]
        )
        self.compact = HSplit(
            [
                Window(FormattedTextControl(self.compact_title), height=2, style="class:heading"),
                self.right,
            ]
        )
        self.application = Application(
            layout=Layout(
                DynamicContainer(lambda: self.wide if self.is_wide else self.compact),
                focused_element=self.input,
            ),
            key_bindings=self.bindings(),
            full_screen=True,
            color_depth=lambda: (
                ColorDepth.DEPTH_1_BIT if terminal.console.no_color else ColorDepth.DEPTH_24_BIT
            ),
            mouse_support=False,
            refresh_interval=0.15,
            before_render=self.before_render,
        )
        self.refresh_style()

    @property
    def is_wide(self):
        return self.size[0] >= 110 and self.size[1] >= 24

    @property
    def content_width(self):
        return max(12, self.size[0] - (47 if self.is_wide else 0))

    def before_render(self, app):
        size = app.output.get_size()
        self.size = (size.columns, size.rows)
        self.terminal.console.width = self.content_width
        self.terminal.console.height = size.rows

    def refresh_style(self):
        t = self.terminal
        base = {"light": "#252b24", "dark": "#f3f0e8"}.get(t.theme, "fg:default")
        muted = t.view.muted
        self.application.style = Style.from_dict(
            {
                "": base,
                "frame": t.view.accent,
                "frame.label": "bold " + t.view.accent,
                "heading": "bold " + t.view.accent,
                "muted": muted,
                "composer": t.view.accent,
                "input": base,
                "body": base,
            }
        )
        self.invalidate()

    def invalidate(self):
        if self.loop:
            self.application.invalidate()

    def emit(self, renderable):
        with self.lock:
            self.blocks.append(renderable)
        self.invalidate()

    def clear(self):
        with self.lock:
            self.blocks.clear()
            self.cache_key = None
        self.offset = 0
        self.invalidate()

    def render_lines(self, width):
        t = self.terminal
        key = (width, t.theme, t.console.no_color)
        with self.lock:
            if key != self.cache_key:
                self.lines = []
                self.cache_count = 0
                self.cache_key = key
            previous_count = len(self.lines)
            for block in self.blocks[self.cache_count :]:
                output = io.StringIO()
                console = Console(
                    file=output,
                    width=width,
                    force_terminal=True,
                    color_system="truecolor",
                    no_color=t.console.no_color,
                    style=t.console.style,
                    highlight=False,
                )
                console.print(block)
                self.lines.extend(list(split_lines(to_formatted_text(ANSI(output.getvalue()))))[:-1])
            if self.offset and self.cache_count:
                self.offset += len(self.lines) - previous_count
            self.cache_count = len(self.blocks)
            return self.lines or [[("", "")]]

    def sidebar_text(self):
        t = self.terminal
        height = self.size[1] - 2
        text = []

        def add(value, style=""):
            text.append((style, value + "\n"))

        gold = "class:heading"
        if height >= 40 and not t.no_logo:
            add("\n".join(WORDMARK), gold)
        else:
            add("CLIRA", gold)
        add("Your Creative Intelligence", "class:muted")
        add("v" + __version__, "class:muted")
        if height >= 32 and not t.no_logo:
            add("")
            add(files("clira").joinpath("assets/clira_braille_compact.txt").read_text().rstrip())
        add("")
        add("YOUR CREATOR WORKSPACE", gold)
        add("/help     Commands")
        add("/back     Start menu")
        add("/sessions Saved conversations")
        add("PgUp/PgDn Conversation history")
        if height >= 40:
            add("Ctrl+End  Latest message")
            add("Ctrl+J    New line")
            add("Ctrl+D    Exit")
        return text

    def compact_title(self):
        return [
            ("class:heading", "CLIRA  ·  Your Creative Intelligence\n"),
            ("class:muted", "/help commands · /back menu · PgUp/PgDn history"),
        ]

    def title(self):
        label = "CONVERSATION"
        if self.terminal.channel:
            label += "  /  " + self.terminal.channel
        return terminal_text(label)

    def scroll_hint(self):
        if self.busy:
            return "Clira is working…"
        if self.offset:
            return "History · PgUp/PgDn scroll · Ctrl+End returns to latest"
        return "Latest · PgUp history · Enter send · Ctrl+J newline"

    def scroll(self, amount):
        self.offset = max(0, min(len(self.lines) - 1, self.offset + amount))
        self.invalidate()

    def bindings(self):
        keys = KeyBindings()

        @keys.add("enter", filter=has_focus(self.input))
        def submit(event):
            if not self.waiting:
                return
            value = self.input.text
            self.waiting = False
            self.input.buffer.reset(append_to_history=True)
            self.offset = 0
            self.emit(Text(self.prompt_label + " " + terminal_text(value)))
            self.answers.put(value)

        @keys.add("tab", filter=has_focus(self.input))
        def complete(event):
            if not self.waiting:
                return
            buffer = self.input.buffer
            if buffer.complete_state:
                buffer.complete_next()
                return
            matches = list(
                self.input.completer.get_completions(
                    buffer.document, CompleteEvent(completion_requested=True)
                )
            )
            if len(matches) == 1:
                buffer.apply_completion(matches[0])
            elif matches:
                buffer.start_completion(select_first=True)

        @keys.add("c-j", filter=has_focus(self.input))
        @keys.add("escape", "enter", filter=has_focus(self.input))
        def newline(event):
            if self.waiting:
                event.current_buffer.insert_text("\n")

        @keys.add("pageup")
        def previous(event):
            self.scroll(max(1, self.page_height - 2))

        @keys.add("pagedown")
        def following(event):
            self.scroll(-max(1, self.page_height - 2))

        @keys.add("c-end")
        def latest(event):
            self.offset = 0

        @keys.add("c-c", filter=has_focus(self.input))
        def interrupt(event):
            if self.waiting:
                self.waiting = False
                self.input.text = ""
                self.answers.put(KeyboardInterrupt())
            else:
                # Never kill a running write or claim it was cancelled.
                self.emit(Text("Request in progress. Wait for its receipt; /jobs inspects saved work."))

        @keys.add("c-d", filter=has_focus(self.input))
        def exit_or_delete(event):
            if self.waiting and not self.input.text:
                self.waiting = False
                self.answers.put(EOFError())
            elif self.waiting:
                event.current_buffer.delete()

        return keys

    def prompt(self, label, **kwargs):
        if not isinstance(label, str):
            label = "".join(part[1] for part in label)

        def prepare():
            self.prompt_label = terminal_text(label).strip()
            self.input.buffer.reset()
            self.waiting = True
            self.application.layout.focus(self.input)
            self.invalidate()

        self.loop.call_soon_threadsafe(prepare)
        result = self.answers.get()
        if isinstance(result, BaseException):
            raise result
        return result

    async def start(self):
        self.loop = asyncio.get_running_loop()

        def work():
            try:
                self.terminal.interact()
            except Exception as exc:  # noqa: BLE001 -- propagate worker failures on the UI thread
                self.failure = exc
            finally:
                self.loop.call_soon_threadsafe(self.application.exit)

        self.worker = threading.Thread(target=work, name="clira-workflow", daemon=True)
        self.worker.start()

    def run(self):
        # Rich is used only to format content; prompt_toolkit owns the terminal.
        self.terminal.console = Console(file=io.StringIO(), width=self.content_width, highlight=False)
        self.terminal.prompt = self
        self.terminal.apply_theme()
        self.application.run(pre_run=lambda: self.application.create_background_task(self.start()))
        self.worker.join(timeout=1)
        if self.failure:
            raise self.failure
        print("Session saved. Goodbye.")
        return 0
