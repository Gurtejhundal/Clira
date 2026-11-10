"""Actual browser chat attachment → preview → one owner review → simulated private upload."""

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
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        video = root / "demo.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                "color=c=green:s=320x180:d=3",
                "-c:v",
                "libx264",
                "-y",
                str(video),
            ],
            check=True,
        )
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        env = {
            **os.environ,
            "CLIRA_MODEL": "offline",
            "CLIRA_ALLOW_MODEL_CALLS": "0",
            "CLIRA_ENABLE_WRITES": "0",
        }
        env.pop("GEMINI_API_KEY", None)
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "clira",
                "--mode",
                "demo",
                "--data-dir",
                str(root / "state"),
                "serve",
                "--port",
                str(port),
            ],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        url = f"http://127.0.0.1:{port}"
        try:
            for _ in range(100):
                try:
                    if httpx.get(url + "/api/session", timeout=0.5).status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.1)
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(viewport={"width": 1280, "height": 900})
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(url)
                page.locator("#chatVideo").set_input_files(str(video))
                page.get_by_text("demo.mp4 attached.", exact=False).wait_for()
                page.locator("#sendButton").click()
                page.get_by_role("button", name="Approve & upload privately").wait_for()
                page.wait_for_function(
                    "() => cliraCharacter.state === 'preview' || cliraCharacter.state === 'approval'"
                )
                page.wait_for_function("() => document.querySelector('#messages video')?.readyState >= 2")
                assert page.locator("#messages video").evaluate("v => v.videoWidth") == 320
                assert page.locator("#messages").get_by_label("Title", exact=True).count() == 1
                page.locator("#messages").get_by_label("Title", exact=True).fill("My reviewed chat upload")
                page.locator("#messages").get_by_label("Description", exact=True).fill(
                    "Original synthetic demo for testing."
                )
                page.locator("#messages").get_by_label("Video and audio rights", exact=True).select_option(
                    "original"
                )
                page.locator("#messages").get_by_label(
                    "Rights evidence (including music and fonts)", exact=True
                ).fill("Original silent test fixture.")
                page.locator("#messages").get_by_label(
                    "Made specifically for kids?", exact=True
                ).select_option("false")
                page.locator("#messages").get_by_label(
                    "Realistic altered or synthetic media?", exact=True
                ).select_option("false")
                page.locator("#messages").get_by_label("I watched this exact video", exact=False).check()
                page.get_by_role("button", name="Approve & upload privately").scroll_into_view_if_needed()
                page.screenshot(path=str(output / "chat-review-desktop.png"), full_page=True)
                page.set_viewport_size({"width": 390, "height": 844})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), page.evaluate(
                    "[...document.querySelectorAll('body *')].filter(n=>n.getBoundingClientRect().right>innerWidth+1).map(n=>[n.tagName,n.className,n.id,n.getBoundingClientRect().right]).slice(0,20)"
                )
                page.screenshot(path=str(output / "chat-review-mobile.png"), full_page=True)
                page.get_by_role("button", name="Approve & upload privately").click()
                page.get_by_text("SYNTHETIC DEMO: simulated upload only; no real video exists.").wait_for()
                page.wait_for_function("() => cliraCharacter.state === 'demo'")
                assert page.locator("#characterStatus").inner_text() == "Demo simulation complete"
                assert not errors, errors
                page.screenshot(path=str(output / "chat-upload-result.png"), full_page=True)
                browser.close()
            print(
                "PASS: chat attachment, editable preview, mobile layout, owner review, simulated upload, no browser errors."
            )
        finally:
            process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    main()
