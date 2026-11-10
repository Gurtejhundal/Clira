"""Capture actual first-run creator setup with fictional data; no providers are contacted."""

import argparse
import json
import os
import re
import tempfile
from pathlib import Path

from capture_split_terminal import TerminalProbe
from playwright.sync_api import sync_playwright

from clira.creator import QUESTIONS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("work/creator-setup/previews"))
    root = parser.parse_args().output.resolve()
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="clira-creator-preview-") as data:
        probe = TerminalProbe(data, color=True, quickstart=False)
        try:
            required = {
                "name": "Asha",
                "passions": "Repairing everyday electronics",
                "audience": "Curious beginners",
                "goal": "Publish four helpful repair tutorials in 90 days",
            }
            for key, _, question, default in QUESTIONS:
                probe.wait(question[:32])
                if key == "name":
                    probe.capture(root, "creator-identity")
                if key == "goal":
                    probe.capture(root, "creator-direction")
                probe.send(required.get(key, default) + "\r")
            probe.wait("REVIEW YOUR CREATOR MEMORY")
            probe.capture(root, "creator-review")
            probe.send("SAVE\r")
            probe.wait("AI: 1 configure Gemini")
            probe.capture(root, "creator-connections")
            probe.send("2\r")
            probe.wait("YouTube: 1 connect")
            probe.send("2\r")
            probe.wait("Telegram: 1 configure")
            probe.send("2\r")
            probe.wait("START: 1 first project")
            probe.send("1\r")
            probe.wait("Name your first project")
            probe.send("Everyday repair lab\r")
            probe.wait("Your project Everyday repair lab is ready")
            probe.capture(root, "creator-project")
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
    report = {
        "kind": "actual PTY visible cells",
        "fictional_creator": True,
        "external_requests": False,
        "captures": [p.stem for p in root.glob("*.png")],
    }
    (root / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
