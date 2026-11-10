"""Capture the shipped local character controller and encode a compact README GIF."""

import argparse
import math
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/media/character")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    html = """<!doctype html><html><head><meta charset="utf-8">
    <link rel="stylesheet" href="/static/character.css"><style>
    :root{--gold:#c4a466;--muted:#b4b1a8;color-scheme:dark}
    *{box-sizing:border-box}body{margin:0;background:#000;color:#eeeae1;font:12px monospace;
    width:420px;height:510px;padding:25px 24px 15px;text-align:center;overflow:hidden}
    h1{font-size:22px;font-weight:600;letter-spacing:8px;margin:0 0 9px;padding-left:8px;color:var(--gold)}
    .tagline{font-size:10px;color:var(--muted);margin:0 0 16px}
    #characterInteract{height:350px;max-width:350px;border:0;cursor:pointer}
    #characterInteract:focus-visible{outline:0}.character-caption{margin:8px 0 0;min-height:18px}
    #characterStatus{font-size:11px}#gesture{height:18px;color:var(--gold);margin:12px 0 6px;font-size:11px}
    .foot{color:#817e76;font-size:9px;margin:0}#cursor{pointer-events:none;position:fixed;top:0;left:0;
    width:9px;height:12px;background:#c4a466;clip-path:polygon(0 0,0 100%,32% 70%,65% 100%,85% 86%,52% 56%,100% 50%);
    z-index:4;transform:translate(-30px,-30px)}#cursor.down{background:white}
    </style><script defer src="/static/character.js"></script></head><body>
    <h1>CLIRA</h1><p class="tagline">Intelligence Behind Creation</p>
    <div id="cliraCharacter" class="character" data-motion="off" data-state="idle">
    <button id="characterInteract" type="button" aria-label="Say hello to Clira" aria-describedby="characterStatus">
    <span id="characterArtwork" aria-hidden="true"></span>
    <span id="characterFallback"><img src="/static/assets/character-v2/neutral.webp" alt=""></span></button>
    <div class="character-caption"><span id="characterStatus">Clira is here</span></div></div>
    <p id="gesture">A quiet creative companion</p><p class="foot">Character preview · local presentation events</p>
    <select id="characterMotion" hidden><option value="full">Full</option></select><span id="cursor"></span>
    <script>document.addEventListener('pointermove',e=>{document.querySelector('#cursor').style.transform=
    `translate(${e.clientX}px,${e.clientY}px)`});document.addEventListener('pointerdown',()=>document.querySelector('#cursor').classList.add('down'));
    document.addEventListener('pointerup',()=>document.querySelector('#cursor').classList.remove('down'));</script>
    </body></html>"""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport={"width": 420, "height": 510},
            reduced_motion="no-preference",
            record_video_dir=str(output / "capture"),
            record_video_size={"width": 420, "height": 510},
        )
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def route_local(route):
            path = urlsplit(route.request.url).path
            if path == "/":
                route.fulfill(body=html, content_type="text/html")
                return
            if not path.startswith("/static/"):
                route.abort()
                return
            source = (ROOT / "clira/web" / path.removeprefix("/static/")).resolve()
            if not source.is_relative_to(ROOT / "clira/web") or not source.is_file():
                route.abort()
                return
            route.fulfill(path=str(source))

        page.route("**/*", route_local)
        page.goto("http://clira-media.test/")
        page.wait_for_function("document.querySelector('#cliraCharacter').dataset.ready==='true'")
        button = page.locator("#characterInteract")

        def caption(text):
            page.locator("#gesture").evaluate("(n,text)=>n.textContent=text", text)

        page.wait_for_timeout(900)
        caption("Hover → quietly curious")
        button.hover()
        page.wait_for_function("cliraCharacter.expression==='curious'")
        page.wait_for_timeout(1000)
        caption("One click → a little smile")
        button.click()
        page.wait_for_function("cliraCharacter.expression==='happy'")
        page.wait_for_timeout(1500)
        caption("Double click → quiet delight")
        button.dblclick(delay=75)
        page.wait_for_function("cliraCharacter.expression==='celebrating'")
        page.wait_for_timeout(1850)
        caption("Circle the pointer → a little dizzy")
        rect = button.bounding_box()
        for i in range(49):
            angle = i * 2 * math.pi / 48
            page.mouse.move(
                rect["x"] + rect["width"] / 2 + 114 * math.cos(angle),
                rect["y"] + rect["height"] / 2 + 114 * math.sin(angle),
            )
        page.wait_for_function("cliraCharacter.expression==='dizzy'")
        page.wait_for_timeout(1850)
        page.mouse.move(415, 508)
        caption("A video attached → interest")
        page.evaluate("cliraCharacter.emit('attached')")
        page.wait_for_function("cliraCharacter.expression==='surprised'")
        page.wait_for_timeout(1700)
        caption("A chat request → thinking")
        page.evaluate("cliraCharacter.emit('request:start',{id:'readme-preview',kind:'thinking'})")
        page.wait_for_function("cliraCharacter.expression==='thinking'")
        page.wait_for_timeout(2100)
        caption("An error → concern, not false success")
        page.evaluate("cliraCharacter.emit('request:end',{id:'readme-preview'});cliraCharacter.emit('error')")
        page.wait_for_function("cliraCharacter.expression==='concerned'")
        page.wait_for_timeout(1700)
        caption("Back to her calm self")
        page.evaluate("cliraCharacter.emit('context')")
        page.wait_for_function("cliraCharacter.expression==='neutral'")
        page.wait_for_timeout(1200)
        page.screenshot(path=str(output / "character-poster.png"))
        assert not errors, errors
        video = page.video
        context.close()
        video.save_as(str(output / "clira-character.webm"))
        browser.close()
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(output / "clira-character.webm"),
            "-filter_complex",
            "fps=8,scale=360:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=48:stats_mode=full[p];[b][p]paletteuse=dither=none:diff_mode=rectangle",
            "-loop",
            "0",
            "-y",
            str(output / "clira-character.gif"),
        ],
        check=True,
    )
    print(output / "clira-character.gif")


if __name__ == "__main__":
    main()
