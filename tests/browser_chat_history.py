"""Chat layout and owner history actions against an isolated local demo database."""

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

from clira.config import Config
from clira.service import DEMO_CHANNEL, Service
from clira.storage import encode, now


def main():
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="clira-history-") as temp:
        service = Service(Config(data_dir=Path(temp), mode="demo", model="offline"))
        messages = [
            {"role": "user", "text": "Help me plan a practical video about battery life."},
            {
                "role": "assistant",
                "text": "This is a synthetic planning example.\n\n"
                "### A useful first experiment\n"
                "Compare the same phone with its screen at two brightness levels. "
                "Keep the other settings consistent and record what changes.\n\n"
                "- **Opening:** show the question you will test.\n"
                "- **Experiment:** explain the setup and record the result.\n"
                "- **Takeaway:** describe the limits of this small experiment.\n\n"
                "Would you like to start with the opening or the experiment plan?",
            },
        ]
        with service.store.connect() as db:
            for i in range(112):
                chat_id = f"chat_demo_history_{i:03}"
                db.execute(
                    "INSERT INTO conversations VALUES(?,?,?,?)",
                    (chat_id, DEMO_CHANNEL, encode(messages * (12 if i == 111 else 1)), now()),
                )
                db.execute(
                    "INSERT INTO session_meta VALUES(?,?,?,?,?)",
                    (
                        chat_id,
                        f"Video idea {i:03}: an original engineering experiment",
                        now(),
                        now(),
                        "completed",
                    ),
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
            "CLIRA_DATA_DIR": temp,
        }
        env.pop("GEMINI_API_KEY", None)
        server = subprocess.Popen(
            [sys.executable, "-m", "clira", "serve", "--port", str(port)],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        url = f"http://127.0.0.1:{port}"
        try:
            for _ in range(100):
                try:
                    if httpx.get(url + "/health", timeout=0.3).is_success:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.1)
            else:
                raise RuntimeError("Demo server did not start")
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(viewport={"width": 1440, "height": 950})
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(url + "/?channel=" + DEMO_CHANNEL + "&session=chat_demo_history_111")
                page.wait_for_function("() => !busy && !changingChannel && !!conversationId")
                page.locator("#sidebar-tab-history").click()
                assert page.get_by_text("Tap to say hello", exact=True).count() == 0
                assert page.locator("#sessionList [data-session-id]").count() == 50
                assert page.locator("#messages").evaluate("""n=>[...n.querySelectorAll('.message')].every(
                    m=>getComputedStyle(m).borderBottomWidth==='0px')""")
                assert page.locator("#messages .copy-button").first.inner_text() == ""
                assert page.locator("#messages .user .body").last.bounding_box()["x"] > (
                    page.locator("#messages .assistant .body").last.bounding_box()["x"] + 40
                )
                assert page.evaluate("""() => {
                    const transcript=document.querySelector('#chatTranscript').getBoundingClientRect();
                    const dock=document.querySelector('#chatDock').getBoundingClientRect();
                    return transcript.bottom<=dock.top+1 && dock.bottom<innerHeight;
                }""")
                # Real wheel input reaches each independent scroll region, without moving the other.
                page.locator("#chatTranscript").hover()
                before = page.locator("#chatTranscript").evaluate("n=>n.scrollTop")
                page.mouse.wheel(0, -700)
                page.wait_for_function(
                    "top=>document.querySelector('#chatTranscript').scrollTop<top", arg=before
                )
                chat_top = page.locator("#chatTranscript").evaluate("n=>n.scrollTop")
                page.locator("#sessionList").hover()
                page.mouse.wheel(0, 600)
                page.wait_for_function("() => document.querySelector('#sidebar-history').scrollTop>50")
                assert page.locator("#chatTranscript").evaluate("n=>n.scrollTop") == chat_top
                page.locator("#historyMore").click()
                page.wait_for_function(
                    "() => document.querySelectorAll('#sessionList [data-session-id]').length===100"
                )
                page.locator("#historyMore").click()
                page.wait_for_function(
                    "() => document.querySelectorAll('#sessionList [data-session-id]').length===112"
                )
                assert page.locator("#historyMore").is_hidden()
                page.locator("#sessionSearch").fill("Video idea 005")
                page.wait_for_function(
                    "() => document.querySelectorAll('#sessionList [data-session-id]').length===1"
                )
                target = "chat_demo_history_005"

                def open_menu():
                    page.locator(f'[data-chat-menu="{target}"]').click()
                    page.locator("#chatMenu").wait_for()

                open_menu()
                page.keyboard.press("ArrowDown")
                assert page.evaluate("document.activeElement.textContent==='Pin'")
                page.keyboard.press("Escape")
                page.wait_for_function("() => document.activeElement.hasAttribute('data-chat-menu')")
                page.locator(f'[data-session-id="{target}"]').press("Shift+F10")
                page.locator("#chatMenu").wait_for()
                page.keyboard.press("Escape")
                open_menu()
                page.get_by_role("menuitem", name="Rename", exact=True).click()
                page.locator("#chatTitleInput").fill("Battery lab — first experiment")
                page.locator("#saveChatTitle").click()
                page.locator("#renameChatDialog").wait_for(state="hidden")
                page.locator("#sessionSearch").fill("Battery lab")
                page.locator(f'[data-session-id="{target}"]').wait_for()
                open_menu()
                page.get_by_role("menuitem", name="Pin", exact=True).click()
                page.locator(".history-group", has_text="Pinned").wait_for()
                page.locator("#sessionSearch").fill("")
                page.wait_for_function(
                    "() => document.querySelectorAll('#sessionList [data-session-id]').length===50"
                )
                assert (
                    page.locator("#sessionList [data-session-id]").first.get_attribute("data-session-id")
                    == target
                )
                page.locator(f'[data-session-id="{target}"]').click()
                page.wait_for_function("() => !busy && atChatBottom()")
                page.locator("#toast").wait_for(state="hidden", timeout=10000)
                page.screenshot(path=str(output / "chat-and-history.png"))
                open_menu()
                page.screenshot(path=str(output / "history-actions.png"))
                with page.expect_download() as download:
                    page.get_by_role("menuitem", name="Export chat", exact=True).click()
                exported = Path(download.value.path())
                assert json.loads(exported.read_text())["messages"] == messages

                open_menu()
                page.get_by_role("menuitem", name="Archive", exact=True).click()
                page.wait_for_function("() => !managingChat")
                page.locator("#historyFolder").select_option("archived")
                page.locator(f'[data-session-id="{target}"]').wait_for()
                open_menu()
                page.get_by_role("menuitem", name="Delete", exact=True).click()
                page.locator("#cancelDeleteChat").click()
                assert page.locator(f'[data-session-id="{target}"]').count() == 1
                open_menu()
                page.get_by_role("menuitem", name="Delete", exact=True).click()
                page.locator("#confirmDeleteChat").click()
                page.locator("#deleteChatDialog").wait_for(state="hidden")
                page.locator("#historyFolder").select_option("trash")
                page.locator(f'[data-session-id="{target}"]').wait_for()
                assert page.locator(f'[data-session-id="{target}"]').is_disabled()
                open_menu()
                page.get_by_role("menuitem", name="Restore chat", exact=True).click()
                page.wait_for_function("() => !managingChat")
                restored = httpx.get(url + f"/api/conversations/{DEMO_CHANNEL}/{target}").json()
                assert restored["messages"] == messages and not restored["trashed"]
                page.reload(wait_until="networkidle")
                page.wait_for_function("() => !busy && !changingChannel")
                page.locator("#sidebar-tab-history").click()
                page.locator("#sessionSearch").fill("Battery lab")
                page.locator(f'[data-session-id="{target}"]').wait_for()

                # A URL to an older chat must work even when it is outside the first 50 rows.
                page.goto(url + "/?channel=" + DEMO_CHANNEL + "&session=chat_demo_history_001")
                page.wait_for_function(
                    "() => !busy && !changingChannel && conversationId==='chat_demo_history_001'"
                )
                page.locator("#sidebar-tab-history").click()
                page.locator("#sessionSearch").fill("Battery lab")
                page.locator(f'[data-session-id="{target}"]').wait_for()

                for width, height in [(1440, 600), (1024, 650), (820, 950), (390, 844), (320, 700)]:
                    page.set_viewport_size({"width": width, "height": height})
                    assert not page.evaluate("document.documentElement.scrollWidth>innerWidth")
                    assert page.locator("#sidebar-tab-history").is_visible()
                    if width > 820:
                        assert page.locator("#sidebar-history").evaluate("n=>n.clientHeight>=160")
                        assert page.locator("#channelSelect").bounding_box()["y"] < height
                    page.screenshot(
                        path=str(output / f"history-{width}x{height}.png"), full_page=width <= 820
                    )
                assert not errors, errors
                browser.close()
                report = {
                    "passed": True,
                    "mode": "isolated_synthetic_demo",
                    "chats": 112,
                    "checks": [
                        "compact paginated metadata history and server-side search",
                        "rename, pin, archive, recoverable delete, restore, local JSON export",
                        "menu keyboard navigation, Escape and dialog focus",
                        "independent real-wheel transcript/sidebar scrolling and unobscured composer",
                        "right user bubbles, left Clira replies, no message divider rules or Tap hint",
                        "desktop short-height and 320/390/820px mobile layout",
                    ],
                    "browser_errors": errors,
                }
                (output / "report.json").write_text(json.dumps(report, indent=2))
                print(json.dumps(report, indent=2))
        finally:
            server.terminate()
            server.wait(timeout=10)


if __name__ == "__main__":
    main()
