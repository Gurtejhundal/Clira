"""Run a real browser against an isolated demo server. No OAuth or paid model calls.

uv run --extra dev python tests/browser_smoke.py --output /absolute/path/to/qa
"""

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(".clira/qa"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="clira-browser-") as temp:
        root = Path(temp)
        imports = root / "imports"
        imports.mkdir()
        video = imports / "original-demo.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                "color=c=green:s=160x90:d=1",
                "-c:v",
                "mpeg4",
                "-y",
                str(video),
            ],
            check=True,
            timeout=30,
        )
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        env = {
            **os.environ,
            "CLIRA_MODE": "demo",
            "CLIRA_MODEL": "offline",
            "CLIRA_ALLOW_MODEL_CALLS": "0",
            "CLIRA_ENABLE_WRITES": "0",
            "CLIRA_DATA_DIR": str(root),
            "CLIRA_IMPORT_DIR": str(imports),
        }
        process = subprocess.Popen(
            [sys.executable, "-m", "clira", "serve", "--port", str(port)],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            url = f"http://127.0.0.1:{port}"
            for _ in range(100):
                try:
                    if httpx.get(url + "/health", timeout=0.3).status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.1)
            else:
                raise RuntimeError("Demo server did not start")
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path=os.getenv("CLIRA_BROWSER") or None)
                page = browser.new_page(viewport={"width": 1440, "height": 1050}, reduced_motion="reduce")
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(url, wait_until="networkidle")
                page.get_by_text("33,400", exact=True).wait_for()
                assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
                page.screenshot(path=str(args.output / "clira-desktop.png"), full_page=True)
                page.get_by_role("button", name="Find my next three ideas").click()
                page.get_by_text("Three editorial hypotheses saved", exact=False).wait_for()
                for view in [
                    "library",
                    "ideas",
                    "production",
                    "approvals",
                    "community",
                    "operations",
                    "settings",
                ]:
                    page.locator("nav button[data-view=" + view + "]").click()
                    assert page.locator("#view-" + view).is_visible()
                page.locator("nav button[data-view=production]").click()
                form = page.locator("#productionForm")
                form.locator("[name=path]").fill(str(video))
                form.locator("[name=title]").fill("An original browser test")
                form.locator("[name=description]").fill(
                    "Silent synthetic test fixture. No real YouTube upload."
                )
                form.locator("[name=rights]").select_option("original")
                form.locator("[name=rights_evidence]").fill(
                    "Generated original green frame; no third-party audio or assets."
                )
                form.locator("[name=made_for_kids]").select_option("false")
                form.locator("[name=synthetic_media]").select_option("false")
                form.locator("[name=creative_reviewed]").check()
                page.get_by_role("button", name="Validate & prepare private upload").click()
                page.get_by_role("button", name="Review & approve exact action").wait_for()
                assert "private" in page.locator("#approvals").inner_text()
                page.get_by_role("button", name="Review & approve exact action").click()
                assert "DEMO_CHANNEL_TECH" in page.locator("#dialogChannel").inner_text()
                page.locator("#confirmApproval").check()
                page.get_by_role("button", name="Approve exact action", exact=True).click()
                page.get_by_role("button", name="Run simulation", exact=True).click()
                page.get_by_text(
                    "Simulation complete. No real YouTube action occurred.", exact=True
                ).wait_for()
                page.locator("nav button[data-view=operations]").click()
                assert page.locator("#jobs .badge", has_text="COMPLETED").count() == 1
                page.screenshot(path=str(args.output / "clira-operations.png"), full_page=True)
                page.locator("nav button[data-view=community]").click()
                page.get_by_role("button", name="Read recent comments").click()
                page.get_by_role("textbox", name="Reply to DEMO_COMMENT_1").fill(
                    "Thanks for asking. I will research that."
                )
                page.get_by_role("button", name="Save reply & request approval").click()
                page.get_by_text("Reply saved locally. Posting requires approval.", exact=True).wait_for()
                page.locator("nav button[data-view=approvals]").click()
                page.get_by_role("button", name="Review & approve exact action").click()
                page.locator("#confirmApproval").check()
                page.get_by_role("button", name="Approve exact action", exact=True).click()
                page.get_by_role("button", name="Run simulation", exact=True).click()
                page.get_by_text(
                    "Simulation complete. No real YouTube action occurred.", exact=True
                ).wait_for()
                page.locator("nav button[data-view=chat]").click()
                page.set_viewport_size({"width": 390, "height": 844})
                page.get_by_role("button", name="Pause writes", exact=True).click()
                page.get_by_role("button", name="Resume writes", exact=True).wait_for()
                page.get_by_role("button", name="Resume writes", exact=True).click()
                page.get_by_role("button", name="Pause writes", exact=True).wait_for()
                page.locator("#toast").wait_for(state="hidden", timeout=10000)
                assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
                page.screenshot(path=str(args.output / "clira-mobile.png"), full_page=True)
                assert not errors, errors
                browser.close()
                print(
                    json.dumps(
                        {
                            "passed": True,
                            "mode": "isolated_synthetic_demo",
                            "views": 8,
                            "viewport_widths": [1440, 390],
                            "flows": [
                                "ideas",
                                "MP4 QC",
                                "upload preview",
                                "approval",
                                "private upload simulation",
                                "comment draft and simulation",
                                "mobile pause/resume",
                            ],
                            "browser_errors": errors,
                            "screenshots": str(args.output.resolve()),
                        },
                        indent=2,
                    )
                )
        finally:
            process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    main()
