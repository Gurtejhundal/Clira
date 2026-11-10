"""Real-browser companion interactions, lifecycle and API hooks; isolated offline demo only."""

import json
import math
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
    with tempfile.TemporaryDirectory(prefix="clira-character-") as temp:
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
        server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "clira",
                "--mode",
                "demo",
                "--data-dir",
                temp,
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
                    if httpx.get(url + "/health", timeout=0.3).status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.1)
            else:
                raise RuntimeError("Demo server did not start")
            with sync_playwright() as p:
                browser = p.chromium.launch()
                context = browser.new_context(
                    viewport={"width": 1440, "height": 1000}, reduced_motion="no-preference"
                )
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                asset_requests = []
                page.on(
                    "request",
                    lambda request: (
                        asset_requests.append(request.url) if "/character-v2/" in request.url else None
                    ),
                )
                page.goto(url)
                page.wait_for_function(
                    "() => document.querySelector('#cliraCharacter').dataset.ready==='true'"
                )
                assert {url.rsplit("/", 1)[-1] for url in asset_requests} == {"neutral.webp"}
                assert page.evaluate("cliraCharacter.expression") == "neutral"
                page.screenshot(path=str(output / "neutral.png"))
                page.wait_for_function("() => !busy && !!channelId")
                assert page.locator("#characterFallback").is_hidden()
                assert page.evaluate("cliraCharacter.motion") == "full"
                character = page.locator("#characterInteract")
                character.hover()
                assert page.evaluate("cliraCharacter.state") == "hover"
                page.wait_for_function("() => cliraCharacter.expression==='curious'")
                page.screenshot(path=str(output / "curious.png"))
                box = character.bounding_box()
                cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
                for i in range(24):
                    page.mouse.move(cx - 35 + i * 3, cy + 15)
                assert page.evaluate("cliraCharacter.state") != "dizzy"
                assert (
                    page.locator("#cliraCharacter").evaluate("n=>n.style.getPropertyValue('--look-x')")
                    != "0px"
                )
                page.evaluate(
                    "window.transitions=[];window.testObserver=new MutationObserver(()=>transitions.push(cliraCharacter.state));testObserver.observe(document.querySelector('#cliraCharacter'),{attributes:true,attributeFilter:['data-state']});"
                )
                character.click()
                page.wait_for_timeout(180)
                assert page.evaluate("cliraCharacter.state") == "hover"
                page.wait_for_function("() => cliraCharacter.state==='happy'")
                page.wait_for_function("() => cliraCharacter.expression==='happy'")
                page.screenshot(path=str(output / "single-click.png"))
                page.wait_for_timeout(1400)
                page.evaluate("transitions.length=0")
                character.dblclick(delay=70)
                page.wait_for_function("() => cliraCharacter.state==='delighted'")
                page.wait_for_timeout(400)
                assert "happy" not in page.evaluate("transitions")
                page.wait_for_function("() => cliraCharacter.expression==='celebrating'")
                page.screenshot(path=str(output / "double-click.png"))
                page.wait_for_timeout(1400)
                box = character.bounding_box()
                cx, cy, radius = (
                    box["x"] + box["width"] / 2,
                    box["y"] + box["height"] / 2,
                    box["height"] * 0.36,
                )
                for i in range(49):
                    angle = i * 2 * math.pi / 48
                    page.mouse.move(cx + radius * math.cos(angle), cy + radius * math.sin(angle))
                page.wait_for_function("() => cliraCharacter.state==='dizzy'")
                page.wait_for_function("() => cliraCharacter.expression==='dizzy'")
                page.screenshot(path=str(output / "circle.png"))
                # Reverse travel must be recognized too, after the existing cooldown.
                page.wait_for_timeout(6100)
                for i in range(49):
                    angle = -i * 2 * math.pi / 48
                    page.mouse.move(cx + radius * math.cos(angle), cy + radius * math.sin(angle))
                page.wait_for_function("() => cliraCharacter.state==='dizzy'")
                page.wait_for_timeout(1900)
                page.mouse.move(1100, 150)
                character.evaluate("n=>n.blur()")
                page.wait_for_function("() => cliraCharacter.state==='idle'")
                character.focus()
                character.press("Space")
                page.wait_for_function("() => cliraCharacter.state==='happy'")
                page.wait_for_timeout(1400)
                page.evaluate("cliraCharacter.emit('attached')")
                page.wait_for_function("() => cliraCharacter.expression==='surprised'")
                page.screenshot(path=str(output / "surprised.png"))
                page.wait_for_timeout(1900)
                page.locator("#message").fill("Show my latest videos")
                assert page.evaluate("cliraCharacter.state") == "typing"
                held = []
                page.route("**/api/chat", lambda route: held.append(route))
                page.locator("#message").press("Enter")
                page.wait_for_function("() => cliraCharacter.state==='thinking'")
                character.dblclick(delay=50)
                assert page.evaluate("cliraCharacter.state") == "thinking"
                assert page.evaluate("cliraCharacter.diagnostics.pending") == 1
                page.wait_for_function("() => cliraCharacter.expression==='thinking'")
                page.screenshot(path=str(output / "thinking.png"))
                held.pop().continue_()
                page.wait_for_function("() => !busy && cliraCharacter.diagnostics.pending===0")
                page.unroute("**/api/chat")
                assert "Latest uploads" in page.locator("#messages").inner_text()
                page.screenshot(path=str(output / "chat-reply.png"))
                page.wait_for_timeout(1500)
                page.route(
                    "**/api/chat",
                    lambda route: route.fulfill(
                        status=504,
                        json={"error": {"code": "MODEL_TIMEOUT", "message": "Offline test timeout"}},
                    ),
                )
                page.locator("#message").fill("Timeout fixture")
                page.locator("#message").press("Enter")
                page.wait_for_function("() => !busy && cliraCharacter.state==='error'")
                assert page.evaluate("cliraCharacter.diagnostics.pending") == 0
                page.wait_for_function("() => cliraCharacter.expression==='concerned'")
                page.screenshot(path=str(output / "error.png"))
                page.unroute("**/api/chat")
                # These mocked result envelopes exercise the real API-to-character adapter only.
                for verified, expected in [(False, "demo"), (True, "celebrate")]:
                    page.route(
                        "**/api/jobs/CHARACTER_FIXTURE/run",
                        lambda route, _request, v=verified: route.fulfill(
                            json={
                                "ok": True,
                                "data": {"verified_remotely": v, "source": "google" if v else "mock"},
                            }
                        ),
                    )
                    page.evaluate("api('/api/jobs/CHARACTER_FIXTURE/run',{})")
                    page.wait_for_function("expected => cliraCharacter.state===expected", arg=expected)
                    page.unroute("**/api/jobs/CHARACTER_FIXTURE/run")
                assert not httpx.get(url + "/api/state/DEMO_CHANNEL_TECH").json()["jobs"]
                page.locator("nav button[data-view=settings]").click()
                page.locator("#characterMotion").select_option("reduced")
                assert page.evaluate("cliraCharacter.motion") == "reduced"
                assert page.evaluate("cliraCharacter.diagnostics.timers") == 0
                page.locator("#characterMotion").select_option("off")
                character.click()
                page.wait_for_timeout(450)
                assert page.locator("#cliraCharacter").get_attribute("data-state") == "idle"
                page.reload()
                page.wait_for_function(
                    "() => document.querySelector('#cliraCharacter').dataset.ready==='true'"
                )
                assert page.evaluate("cliraCharacter.motion") == "off"
                page.locator("nav button[data-view=settings]").click()
                page.locator("#characterMotion").select_option("full")
                page.emulate_media(reduced_motion="reduce")
                page.wait_for_function(
                    "() => document.querySelector('#cliraCharacter').dataset.motion==='reduced'"
                )
                assert page.evaluate("cliraCharacter.motion") == "reduced"
                assert page.evaluate("cliraCharacter.diagnostics.timers") == 0
                page.emulate_media(reduced_motion="no-preference")
                # Visibility/BFCache lifecycle fixtures use the browser's actual event handlers.
                page.evaluate(
                    "Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'))"
                )
                assert page.evaluate("cliraCharacter.diagnostics.timers") == 0
                assert page.locator("#cliraCharacter").get_attribute("data-paused") == "true"
                page.evaluate("window.originalDateNow=Date.now;Date.now=()=>originalDateNow()+31000")
                page.evaluate(
                    "Object.defineProperty(document,'hidden',{configurable:true,get:()=>false});document.dispatchEvent(new Event('visibilitychange'))"
                )
                page.wait_for_function("() => cliraCharacter.state==='greeting'")
                page.evaluate("Date.now=originalDateNow;delete window.originalDateNow")
                page.evaluate("window.dispatchEvent(new PageTransitionEvent('pagehide',{persisted:true}))")
                assert page.evaluate("cliraCharacter.diagnostics.timers") == 0
                assert not page.evaluate("cliraCharacter.diagnostics.destroyed")
                page.evaluate("window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true}))")
                assert page.locator("#cliraCharacter").get_attribute("data-paused") == "false"
                for width in [1440, 1024, 820, 390, 320]:
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
                        page.locator(f"nav button[data-view={view}]").click()
                        assert page.locator("nav button:visible").count() == 8
                        assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
                    assert character.evaluate(
                        "n=>{const r=n.getBoundingClientRect(),p=document.querySelector('#sidebar').getBoundingClientRect();return r.left>=p.left && r.right<=p.right;}"
                    )
                page.screenshot(path=str(output / "mobile.png"), full_page=True)
                page.evaluate("window.dispatchEvent(new PageTransitionEvent('pagehide',{persisted:false}))")
                page.evaluate("cliraCharacter.emit('request:start',{id:'late-callback'})")
                assert page.evaluate("cliraCharacter.diagnostics") == {
                    "pending": 0,
                    "timers": 0,
                    "points": 0,
                    "destroyed": True,
                }
                assert not errors, errors
                context.close()
                # Touch gestures and a graceful fallback when the vector asset is unavailable.
                touch = browser.new_context(
                    viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
                )
                mobile = touch.new_page()
                mobile.goto(url)
                mobile.wait_for_function(
                    "() => document.querySelector('#cliraCharacter').dataset.ready==='true'"
                )
                mobile.locator("#characterInteract").tap()
                mobile.wait_for_function("() => cliraCharacter.state==='happy'")
                mobile.wait_for_timeout(1400)
                mobile.locator("#characterInteract").tap()
                mobile.locator("#characterInteract").tap()
                mobile.wait_for_function("() => cliraCharacter.state==='delighted'")
                touch.close()
                fallback = browser.new_context()
                fallback.route("**/static/assets/clira-live.svg", lambda route: route.abort())
                fallback_page = fallback.new_page()
                fallback_page.goto(url)
                fallback_page.wait_for_function(
                    "() => document.querySelector('#cliraCharacter').dataset.ready==='false'"
                )
                assert fallback_page.locator("#characterFallback").is_visible()
                assert fallback_page.evaluate("cliraCharacter.diagnostics.timers") == 0
                fallback.close()
                # Optional texture failure keeps the canonical face, while real status still updates.
                degraded = browser.new_context()
                degraded.route("**/character-v2/happy.webp", lambda route: route.abort())
                degraded_page = degraded.new_page()
                degraded_page.goto(url)
                degraded_page.wait_for_function(
                    "() => document.querySelector('#cliraCharacter').dataset.ready==='true'"
                )
                degraded_page.locator("#characterInteract").click()
                degraded_page.wait_for_function("() => cliraCharacter.state==='happy'")
                degraded_page.wait_for_function("() => cliraCharacter.expression==='neutral'")
                assert degraded_page.locator("#characterFallback").is_hidden()
                degraded.close()
                # A late texture must never replace a newer, higher-priority facial reaction.
                delayed = browser.new_context()
                delayed_page = delayed.new_page()
                held_texture = []
                delayed_page.route("**/character-v2/happy.webp", lambda route: held_texture.append(route))
                delayed_page.goto(url)
                delayed_page.wait_for_function(
                    "() => document.querySelector('#cliraCharacter').dataset.ready==='true'"
                )
                delayed_page.evaluate("cliraCharacter.emit('reply')")
                delayed_page.wait_for_timeout(100)
                assert len(held_texture) == 1
                delayed_page.evaluate("cliraCharacter.emit('error')")
                delayed_page.wait_for_function("() => cliraCharacter.expression==='concerned'")
                held_texture.pop().continue_()
                delayed_page.wait_for_function(
                    "() => document.querySelector('[data-face=happy]').getAttribute('href')!==null"
                )
                assert delayed_page.evaluate("cliraCharacter.expression") == "concerned"
                assert delayed_page.evaluate("cliraCharacter.state") == "error"
                delayed.close()
                # Missing critical texture uses the approved PNG, never a blank character.
                missing = browser.new_context()
                missing.route("**/character-v2/neutral.webp", lambda route: route.abort())
                missing_page = missing.new_page()
                missing_page.goto(url)
                missing_page.wait_for_function(
                    "() => document.querySelector('#cliraCharacter').dataset.ready==='false'"
                )
                assert missing_page.locator("#characterFallback img").evaluate(
                    "n=>n.complete && n.naturalWidth===1254"
                )
                assert missing_page.evaluate("cliraCharacter.motion") == "off"
                missing.close()
                # Short recording of the actual application, using its real offline chat backend.
                recording = browser.new_context(
                    viewport={"width": 1280, "height": 900},
                    record_video_dir=str(output / "video"),
                    record_video_size={"width": 1280, "height": 900},
                )
                demo = recording.new_page()
                demo.goto(url)
                demo.wait_for_function(
                    "() => document.querySelector('#cliraCharacter').dataset.ready==='true'"
                )
                demo.locator("#characterInteract").hover()
                demo.wait_for_timeout(700)
                demo.locator("#characterInteract").click()
                demo.wait_for_timeout(1600)
                demo.locator("#characterInteract").dblclick(delay=70)
                demo.wait_for_timeout(1900)
                rect = demo.locator("#characterInteract").bounding_box()
                for i in range(49):
                    a = i * 2 * math.pi / 48
                    demo.mouse.move(
                        rect["x"] + rect["width"] / 2 + 70 * math.cos(a),
                        rect["y"] + rect["height"] / 2 + 70 * math.sin(a),
                    )
                demo.wait_for_timeout(1600)
                demo.locator("#message").fill("Show my latest videos")
                demo.wait_for_timeout(600)
                demo.locator("#message").press("Enter")
                demo.wait_for_function(
                    "() => !busy && document.querySelectorAll('#messages .assistant').length>0"
                )
                demo.wait_for_timeout(1800)
                video = demo.video
                recording.close()
                video.save_as(str(output / "clira-character.webm"))
                browser.close()
            print(
                json.dumps(
                    {
                        "passed": True,
                        "mode": "isolated_offline_demo",
                        "browser_errors": errors,
                        "output": str(output),
                    },
                    indent=2,
                )
            )
        finally:
            server.terminate()
            server.wait(timeout=10)


if __name__ == "__main__":
    main()
