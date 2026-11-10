"""Render the shipped character textures/masks without model or account calls."""

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
NAMES = ("neutral", "curious", "happy", "surprised", "thinking", "dizzy", "concerned", "celebrating")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    svg = (ROOT / "clira/web/assets/clira-live.svg").read_text().replace("data-src=", "href=")
    css = (ROOT / "clira/web/character.css").read_text()
    shared = """body{margin:0;padding:36px;background:#11130f;color:#eeeae1;font:16px monospace}
    h1{font-size:25px;font-weight:500;margin:0 0 8px}p{color:#aaa99c;margin:0 0 28px}
    .sheet{display:grid;grid-template-columns:repeat(4,1fr);gap:26px 24px}
    .tile{text-align:center}.art{height:310px}.character svg{width:100%;height:100%}
    .name{display:block;color:#c4a466;margin-top:12px}.character .character-gaze{visibility:hidden}
    .comparison{display:grid;grid-template-columns:1fr 1fr;gap:40px}
    .comparison img{width:100%;height:470px;object-fit:contain}
    """
    sheet = "".join(
        f'<div class="tile character" data-motion="off" data-expression="{name}">'
        f'<div class="art">{svg}</div><span class="name">{name.capitalize()}</span></div>'
        for name in NAMES
    )
    comparison = "".join(
        f'<div class="tile"><img src="/static/assets/{path}" alt="{title}">'
        f'<span class="name">{title}</span></div>'
        for path, title in [
            ("clira-portrait.png", "Approved original · unchanged"),
            ("character-v2/neutral.webp", "Faithful neutral · borderless"),
        ]
    )
    pages = {
        "expression-sheet": (
            "Eight expressions",
            "Faithful portrait textures · shared silhouette · monochrome artwork",
            f'<div class="sheet">{sheet}</div>',
            1440,
            950,
        ),
        "identity-comparison": (
            "Identity before animation",
            "Original proportions, linework, hair, glasses, headphones and hoodie retained",
            f'<div class="comparison">{comparison}</div>',
            1100,
            700,
        ),
    }
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, (title, subtitle, content, width, height) in pages.items():
            html = (
                '<!doctype html><html><head><meta charset="utf-8"><style>'
                + css
                + shared
                + f"</style></head><body><h1>CLIRA · {title}</h1><p>{subtitle}</p>{content}</body></html>"
            )
            (output / f"{name}.html").write_text(html)
            page = browser.new_page(viewport={"width": width, "height": height})

            def asset(route):
                relative = route.request.url.split("/static/", 1)[1]
                path = (ROOT / "clira/web" / relative).resolve()
                if not path.is_relative_to(ROOT / "clira/web/assets"):
                    route.abort()
                    return
                route.fulfill(path=str(path))

            page.route("**/static/**", asset)
            page.route(
                "http://clira-art.test/preview",
                lambda route, _request, content=html: route.fulfill(body=content, content_type="text/html"),
            )
            page.goto("http://clira-art.test/preview", wait_until="networkidle")
            page.screenshot(path=str(output / f"{name}.png"), full_page=True)
            page.close()
        browser.close()
    print(output)


if __name__ == "__main__":
    main()
