"""Capture the real Rich renderer with isolated synthetic data and system fonts.

These are render previews; tests/test_terminal.py separately drives actual PTYs.
No model calls, Google requests, remote fonts or user data are used.
"""

import argparse
import io
import json
import re
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright
from rich.console import Console
from rich.terminal_theme import TerminalTheme

from clira.agent import Agent
from clira.config import Config
from clira.service import DEMO_CHANNEL, Service
from clira.tui.app import Terminal

DARK = TerminalTheme(
    (23, 26, 24),
    (243, 240, 232),
    [
        (23, 26, 24),
        (220, 137, 132),
        (154, 198, 162),
        (197, 163, 104),
        (130, 160, 190),
        (170, 150, 185),
        (140, 180, 180),
        (243, 240, 232),
    ],
    [
        (90, 96, 89),
        (220, 137, 132),
        (154, 198, 162),
        (197, 163, 104),
        (130, 160, 190),
        (170, 150, 185),
        (140, 180, 180),
        (255, 254, 250),
    ],
)
LIGHT = TerminalTheme(
    (248, 247, 242),
    (37, 43, 36),
    [
        (37, 43, 36),
        (145, 63, 53),
        (66, 108, 78),
        (133, 101, 47),
        (55, 85, 120),
        (110, 65, 110),
        (45, 95, 95),
        (248, 247, 242),
    ],
    [
        (115, 119, 108),
        (145, 63, 53),
        (66, 108, 78),
        (133, 101, 47),
        (55, 85, 120),
        (110, 65, 110),
        (45, 95, 95),
        (255, 254, 250),
    ],
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("work/terminal-visuals/final"))
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=True)
    cases = [
        ("welcome-120", 120, 48, "dark", False),
        ("workspace-120", 120, 48, "dark", True),
        ("conversation-120", 120, 48, "dark", True),
        ("help-120", 120, 48, "dark", True),
        ("light-120", 120, 48, "light", True),
        ("mono-120", 120, 48, "mono", True),
        ("compact-80", 80, 36, "dark", False),
        ("narrow-52", 52, 30, "dark", False),
        ("minimal-40", 40, 24, "dark", False),
        ("short-120", 120, 24, "dark", False),
    ]
    with tempfile.TemporaryDirectory(prefix="clira-visual-") as data:
        service = Service(Config(data_dir=Path(data), mode="demo", model="offline", enable_writes=False))
        for name, width, height, theme, selected in cases:
            terminal = Terminal(service, DEMO_CHANNEL if selected else None)
            terminal.console = Console(
                file=io.StringIO(),
                width=width,
                height=height,
                record=True,
                force_terminal=True,
                color_system="truecolor",
            )
            terminal.theme = theme
            terminal.apply_theme()
            if name.startswith("conversation"):
                terminal.view.composer()
                terminal.print("❯ Show my latest videos")
                result = Agent(service).chat(DEMO_CHANNEL, "Show my latest videos")
                terminal.conversation = result["conversation_id"]
                terminal.view.answer(result["message"], result["receipts"])
                terminal.view.composer()
                terminal.print("❯ ")
            elif name.startswith("help"):
                terminal.view.help()
            else:
                terminal.view.welcome()
                if selected:
                    terminal.view.ready()
                    terminal.view.composer()
                    terminal.print("❯ ")
                else:
                    terminal.print("Choose 1 / 2 / 3 > ")
            (root / (name + ".txt")).write_text(terminal.console.export_text(clear=False))
            svg = terminal.console.export_svg(
                title=f"Clira · synthetic demo · {width} columns",
                theme=LIGHT if theme == "light" else DARK,
            )
            # Rich's stock SVG template references a CDN font. Use installed monospace fonts only.
            svg = re.sub(r"@font-face\s*\{[^}]*\}", "", svg)
            svg = svg.replace("Fira Code, monospace", "'DejaVu Sans Mono', monospace")
            dimensions = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
            svg = svg.replace("<svg ", f'<svg width="{dimensions[1]}" height="{dimensions[2]}" ', 1)
            (root / (name + ".svg")).write_text(svg)
    with sync_playwright() as p:
        import os

        browser = p.chromium.launch(executable_path=os.getenv("CLIRA_BROWSER") or None)
        page = browser.new_page(viewport={"width": 1600, "height": 1200}, device_scale_factor=1)
        page.route(re.compile(r"https?://"), lambda route: route.abort())
        for name, *_ in cases:
            page.goto((root / (name + ".svg")).as_uri())
            page.locator("svg").screenshot(path=str(root / (name + ".png")))
        browser.close()
    report = {
        "synthetic": True,
        "kind": "actual Rich render previews; PTY tested separately",
        "external_requests": False,
        "captures": [case[0] for case in cases],
    }
    (root / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
