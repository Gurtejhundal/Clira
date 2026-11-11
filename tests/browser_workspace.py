"""Thinking feedback, scroll following and explorer navigation in an isolated demo browser.

Delayed requests are held at the browser boundary; no Google or model calls are made.
"""

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
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="clira-workspace-") as temp:
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
                    if httpx.get(url + "/health", timeout=0.3).status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.1)
            else:
                raise RuntimeError("Demo server did not start")
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(viewport={"width": 1440, "height": 1000})
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(url, wait_until="networkidle")
                page.wait_for_function("() => !!channelId && !busy && !changingChannel")
                pending = []
                page.route("**/api/chat", lambda route: pending.append(route))

                def send_held(text):
                    page.locator("#message").fill(text)
                    page.locator("#message").press("Enter")
                    page.locator("#chatActivity").wait_for()
                    page.wait_for_function("() => busy && atChatBottom()")
                    assert len(pending) == 1
                    assert page.locator("#messages").get_attribute("aria-busy") == "true"
                    assert page.locator("#newChat").is_disabled()
                    assert page.locator("#channelSelect").is_disabled()
                    assert page.locator("#sidebarNewChat").is_disabled()

                def finish_held():
                    route = pending.pop()
                    response = route.fetch()
                    route.fulfill(response=response)
                    page.wait_for_function("() => !busy")
                    assert page.locator("#chatActivity").is_hidden()
                    assert page.locator("#messages").get_attribute("aria-busy") == "false"
                    assert page.locator("#newChat").is_enabled()

                # A long conversation, not just the empty welcome screen.
                page.evaluate("""() => {
                    for(let i=0;i<12;i++)addMessage('assistant',
                        'Synthetic scroll fixture '+(i+1)+'\\n\\n'+
                        'A saved conversation should remain readable while a request is pending. '.repeat(4));
                }""")
                send_held("Suggest three new topic ideas for this channel.")
                assert page.locator("#chatActivityLabel").inner_text() == "Clira is thinking…"
                assert (
                    page.locator(".activity-spinner").evaluate("n=>getComputedStyle(n).animationName")
                    == "activity-spin"
                )
                assert page.locator("#chatActivity").evaluate(
                    "n=>{let r=n.getBoundingClientRect();return r.top>=0&&r.bottom<innerHeight;}"
                )
                page.screenshot(path=str(output / "thinking-desktop.png"))
                page.locator("#message").fill("A draft to keep while waiting")
                finish_held()
                assert page.locator("#message").input_value() == "A draft to keep while waiting"
                page.wait_for_function("() => atChatBottom()")

                # Reading up during a delayed reply must not be interrupted by completion/focus.
                send_held("Show my latest videos")
                page.wait_for_function("() => !scrollingChat && !chatScrollFrame")
                page.locator("#main").evaluate("n=>n.scrollTop=0")
                page.wait_for_function("() => !followChat")
                finish_held()
                assert page.locator("#main").evaluate("n=>n.scrollTop") < 10
                page.locator("#jumpToLatest").click()
                page.wait_for_function("() => atChatBottom()")

                # A failed request clears its status, even after changing to another view.
                send_held("Synthetic failure check")
                page.keyboard.press("Alt+Digit3")
                assert page.locator("#view-ideas").is_visible()
                assert page.locator("#requestState").is_visible()
                pending.pop().fulfill(
                    status=400,
                    json={"error": {"code": "FIXTURE_ERROR", "message": "Synthetic test failure"}},
                )
                page.wait_for_function("() => !busy")
                assert page.locator("#requestState").is_hidden()
                page.keyboard.press("Alt+Digit1")
                assert "FIXTURE_ERROR" in page.locator("#messages").inner_text()
                assert page.locator("#chatActivity").is_hidden()
                page.locator("#toast").wait_for(state="hidden", timeout=15000)

                # Sidebar tabs, live history, search, resume and new conversations.
                page.locator("#sidebar-tab-history").click()
                history_id = page.evaluate("conversationId")
                assert page.locator("#sessionList button[aria-current=true]").count() == 1
                page.locator("#sessionSearch").fill("no such conversation")
                assert page.locator("#sessionList button").count() == 0
                page.locator("#sessionSearch").fill("")
                page.locator("#sidebarNewChat").click()
                page.wait_for_function("() => !busy && !document.querySelector('#chatWelcome').hidden")
                assert page.locator("#messages .message").count() == 0
                page.locator(f'#sessionList button[data-session-id="{history_id}"]').click()
                page.wait_for_function("() => !busy")
                assert page.evaluate("conversationId") == history_id
                assert "Three editorial hypotheses saved" in page.locator("#messages").inner_text()

                # Real saved ideas and profile parameters, not invented projects or settings.
                page.locator("#sidebar-tab-projects").click()
                assert page.locator("#projectList button").count() == 3
                page.locator("#projectList button").first.click()
                assert page.locator("#view-ideas").is_visible()
                assert page.evaluate("document.activeElement.id.startsWith('idea-')")
                page.locator("#sidebar-tab-controls").click()
                assert "Offline router" in page.locator("#workspaceParameters").inner_text()
                assert "Asia/Kolkata" in page.locator("#workspaceParameters").inner_text()
                page.screenshot(path=str(output / "controls-desktop.png"))
                page.locator("#sidebar-tab-controls").press("Home")
                assert page.locator("#sidebar-tab-views").get_attribute("aria-selected") == "true"
                page.keyboard.press("Alt+BracketRight")
                assert page.locator("#sidebar-history").is_visible()
                page.keyboard.press("Alt+BracketLeft")
                assert page.locator("#sidebar-views").is_visible()

                # Horizontal trackpad wheel events: one switch per gesture, no vertical/pinch capture.
                explorer = page.locator("#sidebarWorkspace")
                explorer.dispatch_event("wheel", {"deltaX": 100, "deltaY": 2})
                assert page.locator("#sidebar-history").is_visible()
                explorer.dispatch_event("wheel", {"deltaX": 120, "deltaY": 1})
                assert page.locator("#sidebar-history").is_visible()
                explorer.dispatch_event("wheel", {"deltaX": 5, "deltaY": 150})
                assert page.locator("#sidebar-history").is_visible()
                explorer.dispatch_event("wheel", {"deltaX": 130, "deltaY": 0, "ctrlKey": True})
                assert page.locator("#sidebar-history").is_visible()
                assert page.evaluate("""() => {
                    const explorer=document.querySelector('#sidebarWorkspace');
                    const search=document.querySelector('#sessionSearch');
                    return explorer.dispatchEvent(new WheelEvent('wheel',{
                        deltaY:150,bubbles:true,cancelable:true})) &&
                        search.dispatchEvent(new WheelEvent('wheel',{
                        deltaX:150,bubbles:true,cancelable:true}));
                }""")
                for digit in range(1, 9):
                    page.keyboard.press(f"Alt+Digit{digit}")
                    assert page.locator(".view:visible").count() == 1
                # Approval dialogs must retain keyboard authority.
                page.locator("#approvalDialog").evaluate("n=>n.showModal()")
                page.keyboard.press("Alt+Digit1")
                assert page.locator("#view-settings").is_visible()
                page.keyboard.press("Escape")

                # Every explorer pane fits at all existing breakpoints, in both themes.
                for width in [1440, 1280, 1024, 820, 768, 390, 320]:
                    page.set_viewport_size({"width": width, "height": 950})
                    for theme in ["dark", "light"]:
                        page.keyboard.press("Alt+Digit8")
                        page.locator("#themeSelect").select_option(theme)
                        page.keyboard.press("Alt+Digit1")
                        for panel in ["views", "history", "projects", "controls"]:
                            page.locator("#sidebar-tab-" + panel).click()
                            assert page.locator("#sidebar-" + panel).is_visible()
                            assert not page.evaluate("document.documentElement.scrollWidth>innerWidth")
                            if theme == "dark" and width in [1440, 390, 320]:
                                page.screenshot(path=str(output / f"{panel}-{width}.png"), full_page=True)

                # Create and switch real local workspaces through Projects, keeping history isolated.
                page.locator("#sidebar-tab-projects").click()
                page.locator("#sidebarNewWorkspace").click()
                for answer in ["Battery experiments", "beginners", "English", "4 hours", "short"]:
                    page.locator("#launchAnswer").fill(answer)
                    page.locator("#launchNext").click()
                page.wait_for_function("() => !changingChannel && channelId.startsWith('workspace_')")
                assert page.locator("#sessionList button").count() == 0
                assert page.locator("#workspaceList button").count() == 2
                assert page.locator("#projectList button").count() == 3
                assert "Battery experiments" in page.locator("#workspaceParameters").inner_text()
                page.locator('#workspaceList button[data-workspace-id="DEMO_CHANNEL_TECH"]').click()
                page.wait_for_function("() => !changingChannel && channelId==='DEMO_CHANNEL_TECH'")
                assert page.locator(f'#sessionList button[data-session-id="{history_id}"]').count() == 1
                assert "Battery experiments" not in page.locator("#workspaceParameters").inner_text()

                # Touchscreen two-finger swipes, vertical scroll, single finger and pinch.
                touch = browser.new_context(
                    viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
                )
                mobile = touch.new_page()
                mobile.on("pageerror", lambda e: errors.append(str(e)))
                mobile.goto(url, wait_until="networkidle")
                mobile.wait_for_function("() => !!channelId && !busy && !changingChannel")
                mobile.locator("#sidebar-tab-views").click()
                assert mobile.evaluate("""() => {
                    const target=document.querySelector('.sidebar-tabs');
                    const points=(x,y,gap=60)=>[0,1].map(i=>new Touch({identifier:i,target,
                        clientX:x+i*gap,clientY:y,pageX:x+i*gap,pageY:y}));
                    function gesture(start,end){
                        target.dispatchEvent(new TouchEvent('touchstart',{touches:start,bubbles:true}));
                        target.dispatchEvent(new TouchEvent('touchmove',{touches:end,bubbles:true,cancelable:true}));
                        target.dispatchEvent(new TouchEvent('touchend',{touches:[],bubbles:true}));
                    }
                    gesture(points(200,200),points(110,202));
                    if(activeSidebar!=='history')return false;
                    gesture(points(100,200),points(102,300));
                    gesture(points(100,200),points(60,200,150));
                    gesture(points(200,200).slice(0,1),points(100,200).slice(0,1));
                    return activeSidebar==='history';
                }""")
                mobile.locator("#sidebar-tab-views").click()
                mobile_pending = []
                mobile.route("**/api/chat", lambda route: mobile_pending.append(route))
                mobile.locator("#message").fill("Show my latest videos")
                mobile.locator("#message").press("Enter")
                mobile.locator("#chatActivity").wait_for()
                mobile.wait_for_function("() => atChatBottom()")
                mobile.screenshot(path=str(output / "thinking-mobile.png"))
                mobile.emulate_media(reduced_motion="reduce")
                assert (
                    mobile.locator(".activity-spinner").evaluate("n=>getComputedStyle(n).animationName")
                    == "none"
                )
                assert mobile.locator("#chatActivityLabel").is_visible()
                route = mobile_pending.pop()
                route.fulfill(response=route.fetch())
                mobile.wait_for_function("() => !busy && atChatBottom()")
                assert not errors, errors
                browser.close()
                report = {
                    "passed": True,
                    "mode": "isolated_offline_demo",
                    "checks": [
                        "delayed success/failure feedback and disabled context changes",
                        "desktop and mobile autoscroll; respect reading up; latest button",
                        "history search, new, resume; real saved ideas and profile parameters",
                        "create and switch local workspaces; channel-isolated history and parameters",
                        "eight view shortcuts; tab keyboard navigation; modal shortcut exclusion",
                        "horizontal trackpad wheel and two-touch event navigation",
                        "vertical, single-finger, pinch and momentum exclusions",
                        "four panels at seven widths and two themes; no horizontal overflow",
                        "reduced motion preserves readable thinking status",
                    ],
                    "physical_gesture_hardware": "not tested; browser event behavior tested",
                    "browser_errors": errors,
                }
                (output / "report.json").write_text(json.dumps(report, indent=2))
                print(json.dumps(report, indent=2))
        finally:
            server.terminate()
            server.wait(timeout=10)


if __name__ == "__main__":
    main()
