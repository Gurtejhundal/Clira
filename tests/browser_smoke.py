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
                "color=c=green:s=160x90:d=8",
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
                terminal_result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "clira",
                        "chat",
                        "--channel",
                        "DEMO_CHANNEL_TECH",
                        "Show my latest videos",
                        "--json",
                    ],
                    env=env,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                shared_id = json.loads(terminal_result.stdout)["conversation_id"]
                page.goto(url + "/?channel=DEMO_CHANNEL_TECH&session=" + shared_id, wait_until="networkidle")
                page.locator("#terminalResume", has_text=shared_id).wait_for(state="attached")
                page.locator("#characterArtwork svg").wait_for()
                assert "Latest uploads" in page.locator("#messages").inner_text()
                assert not page.locator("#chatWelcome").is_visible()
                assert "Mono" in page.locator("body").evaluate("n=>getComputedStyle(n).fontFamily")
                assert (
                    page.locator("#characterFallback img").get_attribute("src")
                    == "/static/assets/clira-portrait.png"
                )
                page.context.grant_permissions(["clipboard-read", "clipboard-write"])
                page.locator("#messages .assistant .message-actions button").first.click()
                assert "Latest uploads" in page.evaluate("navigator.clipboard.readText()")
                assert page.evaluate(r"""() => {
                    const body=document.createElement('div');
                    renderAnswer(body, '### Heading\n\n**Bold** and `code` <img src=x onerror=alert(1)>\n\n- One\n- Two\n\n| A | B |\n| --- | --- |\n| 1 | 2 |');
                    return body.querySelectorAll('strong').length===1 &&
                        body.querySelectorAll('li').length===2 &&
                        body.querySelectorAll('table').length===1 &&
                        !body.querySelector('img') && body.textContent.includes('<img');
                }""")
                page.locator("#message").fill("First line")
                page.locator("#message").press("Shift+Enter")
                page.locator("#message").type("Second line")
                assert page.locator("#message").input_value() == "First line\nSecond line"
                page.locator("#message").press("Insert")
                assert page.locator("#cursorToggle").get_attribute("aria-pressed") == "false"
                page.locator("#message").press("Insert")
                assert page.locator("#cursorToggle").get_attribute("aria-pressed") == "true"
                page.locator("#message").evaluate(
                    "n=>{n.setSelectionRange(0,5);n.dispatchEvent(new Event('select'));}"
                )
                page.wait_for_function(
                    "() => !document.querySelector('.input-surface').classList.contains('block-cursor')"
                )
                page.locator("#message").fill("/settings")
                page.locator("#message").press("Enter")
                assert page.locator("#view-settings").is_visible()
                page.locator("nav button[data-view=chat]").click()
                page.locator(".snapshot summary").click()
                page.get_by_text("33,400", exact=True).wait_for()
                assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
                page.screenshot(path=str(args.output / "clira-desktop.png"), full_page=True)
                page.locator("#message").fill("Suggest three new topic ideas for this channel.")
                page.locator("#message").press("Enter")
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
                approval_state = httpx.get(url + "/api/state/DEMO_CHANNEL_TECH").json()
                pending = next(a for a in approval_state["approvals"] if a["status"] == "PENDING")
                cli_approval = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "clira",
                        "approval",
                        "show",
                        pending["id"],
                        "--channel",
                        "DEMO_CHANNEL_TECH",
                    ],
                    env=env,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                assert json.loads(cli_approval.stdout)["id"] == pending["id"]
                page.keyboard.press("Tab")
                assert page.locator("#approvalDialog").evaluate(
                    "dialog=>dialog.contains(document.activeElement)"
                )
                page.keyboard.press("Escape")
                page.locator("#approvalDialog").wait_for(state="hidden")
                page.wait_for_function(
                    "() => document.activeElement.textContent.includes('Review & approve exact action')"
                )
                assert (
                    next(
                        a
                        for a in httpx.get(url + "/api/state/DEMO_CHANNEL_TECH").json()["approvals"]
                        if a["id"] == pending["id"]
                    )["status"]
                    == "PENDING"
                )
                page.get_by_role("button", name="Review & approve exact action").click()
                page.locator("#confirmApproval").check()
                page.locator("#approvalText").fill("APPROVE")
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
                approval_state = httpx.get(url + "/api/state/DEMO_CHANNEL_TECH").json()
                pending = next(a for a in approval_state["approvals"] if a["status"] == "PENDING")
                cli_approval = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "clira",
                        "approval",
                        "show",
                        pending["id"],
                        "--channel",
                        "DEMO_CHANNEL_TECH",
                    ],
                    env=env,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                assert json.loads(cli_approval.stdout)["id"] == pending["id"]
                page.keyboard.press("Tab")
                assert page.locator("#approvalDialog").evaluate(
                    "dialog=>dialog.contains(document.activeElement)"
                )
                page.keyboard.press("Escape")
                page.locator("#approvalDialog").wait_for(state="hidden")
                page.wait_for_function(
                    "() => document.activeElement.textContent.includes('Review & approve exact action')"
                )
                assert (
                    next(
                        a
                        for a in httpx.get(url + "/api/state/DEMO_CHANNEL_TECH").json()["approvals"]
                        if a["id"] == pending["id"]
                    )["status"]
                    == "PENDING"
                )
                page.get_by_role("button", name="Review & approve exact action").click()
                page.locator("#confirmApproval").check()
                page.locator("#approvalText").fill("APPROVE")
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
                # Shared session search/resume and cross-surface content survive a browser reload.
                page.locator("#sidebar-tab-history").click()
                page.locator(f'#sessionList button[data-session-id="{shared_id}"]').click()
                page.wait_for_function("() => !busy")
                page.locator("#message").fill("Show my latest videos again")
                page.locator("#message").press("Enter")
                page.locator("#sendButton", has_text="Send message").wait_for()
                page.wait_for_function("() => document.querySelectorAll('#messages .assistant').length >= 3")
                page.wait_for_function("() => !busy")
                page.reload(wait_until="networkidle")
                page.locator("#terminalResume", has_text=shared_id).wait_for(state="attached")
                assert shared_id in page.locator("#terminalResume").text_content()
                page.locator("#sidebar-tab-views").click()
                shared = httpx.get(url + "/api/conversations/DEMO_CHANNEL_TECH/" + shared_id).json()
                assert any(m["text"] == "Show my latest videos again" for m in shared["messages"])
                (args.output / "shared-session.json").write_text(json.dumps(shared, indent=2))
                # Actual packaging UI, not a concept masquerading as an image.
                page.locator("nav button[data-view=production]").click()
                page.locator("#templateForm [name=text]").fill("An original fixture")
                page.locator("#templateForm button").click()
                page.locator("#packageAssets img").wait_for()
                assert page.locator("#packageAssets img").evaluate(
                    "img=>img.complete && img.naturalWidth===1280"
                )
                caption_path = imports / "original.srt"
                caption_path.write_text("1\n00:00:00,000 --> 00:00:07,500\nOriginal silent test fixture.\n")
                form = page.locator("#packageAssetForm")
                form.locator("[name=type]").select_option("captions")
                form.locator("[name=path]").fill(str(caption_path))
                video_assets = httpx.get(url + "/api/state/DEMO_CHANNEL_TECH").json()["records"]["asset"]
                form.locator("[name=asset_id]").select_option(video_assets[0]["id"])
                form.locator("[name=rights]").select_option("original")
                form.locator("[name=rights_evidence]").fill("Original typed test words")
                form.locator("[name=creative_reviewed]").check()
                form.locator("button").click()
                page.locator("#packageAssets pre", has_text="Original silent test fixture").first.wait_for()
                # All eight views at every required width, both palettes, keyboard focus.
                for width in [1440, 1280, 1024, 820, 768, 390, 320]:
                    page.set_viewport_size({"width": width, "height": 950})
                    for view in [
                        "chat",
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
                        assert page.locator("nav button:visible").count() == 8
                        assert page.locator("#characterInteract").evaluate(
                            "n=>{const p=n.getBoundingClientRect(),s=document.querySelector('#sidebar').getBoundingClientRect();return p.left>=s.left && p.right<=s.right;}"
                        )
                        if width == 1440:
                            page.screenshot(path=str(args.output / f"terminal-{view}.png"))
                        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth"), (
                            width,
                            view,
                        )
                    page.locator("#themeSelect").select_option("dark")
                    assert page.locator("html").get_attribute("data-theme") == "dark"
                    page.locator("nav button[data-view=chat]").click()
                    page.screenshot(path=str(args.output / f"clira-dark-{width}.png"))
                    page.locator("nav button[data-view=settings]").click()
                    page.locator("#themeSelect").select_option("light")
                    page.locator("nav button[data-view=chat]").click()
                    page.locator("#toast").wait_for(state="hidden", timeout=10000)
                    page.locator("#message").focus()
                    page.evaluate("window.scrollTo(0,0)")
                    page.screenshot(path=str(args.output / f"clira-chat-{width}.png"), full_page=True)
                page.keyboard.press("Tab")
                assert page.evaluate("document.activeElement !== document.body")
                # Welcome belongs to a new conversation, never to each reply.
                page.locator("#newChat").click()
                page.wait_for_function("() => document.querySelector('#messages').children.length===0")
                assert page.locator("#chatWelcome").is_visible()
                # Five-step launch path without Google account creation.
                page.locator("#onboarding").evaluate("n=>n.open=true")
                page.locator("#startLaunch").click()
                for answer in ["Batteries", "curious beginners", "English", "4 hours", "short"]:
                    page.locator("#launchAnswer").fill(answer)
                    page.locator("#launchNext").click()
                page.locator("#modeBadge", has_text="LOCAL DRAFT").wait_for()
                assert page.locator("#channelSelect").input_value().startswith("workspace_")
                page.locator("nav button[data-view=ideas]").click()
                assert page.locator("#ideas .card").count() == 3
                assert page.locator("#messages").inner_text() == ""
                page.locator("nav button[data-view=chat]").click()
                page.locator("#message").fill("Plan my first channel")
                page.locator("#message").press("Enter")
                page.locator("#messages", has_text="LOCAL DRAFT").wait_for()
                page.screenshot(path=str(args.output / "clira-launch-320.png"), full_page=True)
                assert not errors, errors
                browser.close()
                print(
                    json.dumps(
                        {
                            "passed": True,
                            "mode": "isolated_synthetic_demo",
                            "views": 8,
                            "viewport_widths": [1440, 1280, 1024, 820, 768, 390, 320],
                            "flows": [
                                "ideas",
                                "MP4 QC",
                                "upload preview",
                                "approval",
                                "private upload simulation",
                                "comment draft and simulation",
                                "mobile pause/resume",
                                "CLI/web shared session and approval IDs",
                                "actual PNG and timed SRT UI",
                                "five-step local launch",
                                "eight views at seven widths; light/dark; keyboard",
                                "clipboard copy; safe Markdown; multiline; Insert cursor; slash navigation",
                                "faithful portrait with approved PNG fallback; welcome per new conversation",
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
