"""Drive the real full-screen terminal, emulate VT output and capture its visible cells."""

import argparse
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

import pexpect
import pyte
from playwright.sync_api import sync_playwright
from rich.console import Console
from rich.terminal_theme import TerminalTheme
from rich.text import Text


class TerminalProbe:
    def __init__(self, data, width=140, height=48, color=False, python=None, cwd=None):
        self.width, self.height = width, height
        self.screen = pyte.Screen(width, height)
        self.stream = pyte.Stream(self.screen)
        env = {
            **os.environ,
            "CLIRA_MODE": "demo",
            "CLIRA_MODEL": "offline",
            "CLIRA_ALLOW_MODEL_CALLS": "0",
            "CLIRA_ENABLE_WRITES": "0",
            "CLIRA_TERMINAL_LAYOUT": "split",
            "TERM": "xterm-256color",
            "PROMPT_TOOLKIT_NO_CPR": "1",
        }
        env.pop("PYTHONPATH", None)
        env.pop("GEMINI_API_KEY", None)
        env.pop("CLIRA_GOOGLE_CLIENT_FILE", None)
        if color:
            env.pop("NO_COLOR", None)
        else:
            env["NO_COLOR"] = "1"
        self.process = pexpect.spawn(
            python or sys.executable,
            ["-m", "clira", "--data-dir", str(data)],
            env=env,
            cwd=str(cwd) if cwd else None,
            encoding="utf-8",
            dimensions=(height, width),
            timeout=10,
        )
        self.raw = ""

    @property
    def text(self):
        return "\n".join(self.screen.display)

    @property
    def left(self):
        return "\n".join(line[:46] for line in self.screen.display)

    def pump(self, seconds=0.2):
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            try:
                raw = self.process.read_nonblocking(
                    65536, timeout=min(0.05, max(0.001, until - time.monotonic()))
                )
            except pexpect.TIMEOUT:
                continue
            except pexpect.EOF:
                return
            self.raw += raw
            self.stream.feed(raw)

    def wait(self, text, timeout=10):
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            self.pump(0.1)
            if text in self.text:
                self.pump(0.1)
                return
        raise AssertionError(f"Missing {text!r} in visible terminal:\n{self.text}")

    def send(self, text):
        self.process.send(text)
        self.pump(0.25)

    def resize(self, width, height):
        self.width, self.height = width, height
        self.screen.resize(lines=height, columns=width)
        self.process.setwinsize(height, width)
        self.pump(0.5)

    def close(self):
        if self.process.isalive():
            self.process.sendcontrol("d")
            self.pump(0.4)
        if self.process.isalive():
            self.process.terminate(force=True)
        self.process.close()

    def capture(self, root, name, light=False):
        (root / (name + ".txt")).write_text(self.text + "\n")
        (root / (name + ".ansi")).write_text(self.raw)
        foreground = "#252b24" if light else "#f3f0e8"
        background = "#f8f7f2" if light else "#171a18"
        rendered = Text()
        for row in range(self.height):
            for column in range(self.width):
                cell = self.screen.buffer[row][column]

                def color(value, default):
                    return (
                        default
                        if value == "default"
                        else "#" + value
                        if re.fullmatch(r"[a-fA-F0-9]{6}", value)
                        else value
                    )

                style = color(cell.fg, foreground) + " on " + color(cell.bg, background)
                if cell.bold:
                    style += " bold"
                rendered.append(cell.data, style=style)
            rendered.append("\n")
        console = Console(width=self.width, record=True, file=__import__("io").StringIO())
        console.print(rendered, end="")
        rgb = lambda color: tuple(int(color[i : i + 2], 16) for i in (1, 3, 5))
        theme = TerminalTheme(rgb(background), rgb(foreground), [rgb(background)] * 8, [rgb(foreground)] * 8)
        svg = console.export_svg(title=f"Clira · real PTY · {self.width}×{self.height}", theme=theme)
        svg = re.sub(r"@font-face\s*\{[^}]*\}", "", svg).replace(
            "Fira Code, monospace", "'DejaVu Sans Mono', monospace"
        )
        dimensions = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
        svg = svg.replace("<svg ", f'<svg width="{dimensions[1]}" height="{dimensions[2]}" ', 1)
        (root / (name + ".svg")).write_text(svg)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("work/split-terminal/previews"))
    root = parser.parse_args().output.resolve()
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="clira-split-capture-") as data:
        probe = TerminalProbe(data, color=True)
        try:
            probe.wait("Choose 1 / 2 / 3")
            probe.capture(root, "welcome-split")
            probe.send("1\r")
            probe.wait("Your interest >")
            probe.capture(root, "setup-split")
            probe.send("/back\r")
            probe.wait("Choose 1 / 2 / 3")
            probe.send("3\r")
            probe.wait("❯")
            for _ in range(6):
                probe.send("Show latest videos\r")
                probe.wait("list_videos")
            probe.send("Show latest videos\r")
            probe.wait("Latest uploads")
            probe.capture(root, "conversation-split")
            probe.send("\x1b[5~")
            probe.capture(root, "history-split")
            probe.send("\x1b[1;5F")
            probe.resize(80, 32)
            probe.capture(root, "compact-split")
            probe.resize(140, 48)
            probe.send("/theme light\r")
            probe.wait("Theme saved: light")
            probe.capture(root, "light-split", light=True)
            probe.send("/theme mono\r")
            probe.wait("Theme saved: mono")
            probe.capture(root, "mono-split")
        finally:
            probe.close()
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.getenv("CLIRA_BROWSER") or None)
        page = browser.new_page()
        page.route(re.compile(r"https?://"), lambda route: route.abort())
        for svg in root.glob("*.svg"):
            page.goto(svg.as_uri())
            page.locator("svg").screenshot(path=str(svg.with_suffix(".png")))
        browser.close()
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "kind": "actual PTY output, visible cells decoded by pyte",
                "synthetic": True,
                "external_requests": False,
                "captures": [p.stem for p in root.glob("*.png")],
            },
            indent=2,
        )
        + "\n"
    )
    print((root / "manifest.json").read_text())


if __name__ == "__main__":
    main()
