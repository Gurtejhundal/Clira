"""Build a captioned product tour from captured demo screens and actual CLI output.

Authoring dependency: Pillow. Requires ffmpeg. No model or Google calls.
This is a guided visual tour, not a claim of a live account recording.
"""

import argparse
import json
import os
import shutil
import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
PAPER = "#f8f7f2"
INK = "#252b24"
GOLD = "#c9b780"
MUTED = "#abb49e"
FONTS = Path("/usr/share/fonts/truetype/dejavu")


def font(size, serif=False):
    return ImageFont.truetype(str(FONTS / ("DejaVuSerif.ttf" if serif else "DejaVuSans.ttf")), size)


def write(draw, xy, value, size=28, fill=INK, serif=False):
    draw.text(xy, value, font=font(size, serif), fill=fill)


def base(title, subtitle, chapter):
    canvas = Image.new("RGB", (1600, 1100), PAPER)
    draw = ImageDraw.Draw(canvas)
    write(draw, (65, 32), "CLIRA  /  YOUR CREATIVE INTELLIGENCE", 16, "#8a773d")
    write(draw, (65, 75), title, 42, serif=True)
    write(draw, (65, 135), subtitle, 20, "#737b68")
    draw.line((65, 183, 1535, 183), fill="#dddccd", width=1)
    write(draw, (65, 1050), "v0.1.0  ·  SYNTHETIC DEMO  ·  NO REAL CHANNEL ACTIONS", 16, "#7a826f")
    write(draw, (1420, 1050), chapter, 16, "#7a826f")
    return canvas


def screen(image, title, subtitle, chapter, progress=0, phone=False):
    canvas = base(title, subtitle, chapter)
    source = Image.open(image).convert("RGB")
    if phone:
        width = 430
        source = source.resize((width, round(source.height * width / source.width)), Image.Resampling.LANCZOS)
        top = round(max(0, source.height - 815) * progress)
        crop = source.crop((0, top, width, min(source.height, top + 815)))
        canvas.paste(crop, (80, 210))
        draw = ImageDraw.Draw(canvas)
        write(draw, (590, 350), "The same channel context.", 39, serif=True)
        write(draw, (590, 425), "At your desk. On your phone.", 30, "#758265", True)
        for y, text in [
            (550, "Channel-specific memory"),
            (615, "Ideas, scripts and editorial plans"),
            (680, "Visible sources and action receipts"),
            (745, "Pause account writes from any screen"),
        ]:
            draw.ellipse((590, y + 9, 600, y + 19), fill="#a18b4e")
            write(draw, (622, y), text, 23)
    else:
        scale = min(1470 / source.width, 815 / min(source.height, 1053))
        source = source.resize(
            (round(source.width * scale), round(source.height * scale)), Image.Resampling.LANCZOS
        )
        top = round(max(0, source.height - 815) * progress)
        crop = source.crop((0, top, source.width, min(source.height, top + 815)))
        canvas.paste(crop, ((1600 - crop.width) // 2, 210))
    return canvas


def title_card(title, subtitle, lines):
    image = Image.new("RGB", (1600, 1100), "#222820")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((95, 95, 250, 285), radius=70, outline=GOLD, width=2)
    write(draw, (125, 95), "c", 150, GOLD, True)
    write(draw, (255, 55), "✦", 36, GOLD)
    write(draw, (95, 350), title, 78, "#f5f4e7", True)
    write(draw, (95, 475), subtitle, 30, MUTED)
    for index, line in enumerate(lines):
        write(draw, (98, 620 + index * 72), line, 27, "#d9ddcd")
    write(draw, (98, 1000), "CLIRA v0.1.0  /  LOCAL MVP PREVIEW", 19, GOLD)
    return image


def encode_video(frames, destination, fps):
    process = subprocess.Popen(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            "1600x1100",
            "-r",
            str(fps),
            "-i",
            "-",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "24",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(destination),
        ],
        stdin=subprocess.PIPE,
    )
    try:
        for frame in frames:
            process.stdin.write(frame.tobytes())
        process.stdin.close()
        if process.wait() != 0:
            raise RuntimeError("ffmpeg video export failed")
    finally:
        if process.poll() is None:
            process.kill()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--screenshots", type=Path, required=True)
    args = parser.parse_args()
    media = ROOT / "docs/media"
    work = ROOT / "work/release-media"
    media.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    for name in ["clira-desktop.png", "clira-mobile.png", "clira-operations.png"]:
        shutil.copyfile(args.screenshots / name, media / name)

    intro = title_card(
        "Your channel. One creative partner.",
        "A calmer way to manage the work behind your videos.",
        [
            "Understand → Plan → Create → Review → Release",
            "One agent. Channel memory. Your final say.",
            "Guided tour using real captured synthetic-demo screens.",
        ],
    )
    outro = title_card(
        "Start local. Connect when ready.",
        "github.com/Gurtejhundal/Clira",
        [
            "./run.sh",
            "Google OAuth + Gemini unlock live account and AI workflows.",
            "Live channel verification is pending. Rendering stays external.",
        ],
    )
    intro.save(media / "tour-poster.jpg", quality=88, optimize=True)
    home = lambda p: screen(
        media / "clira-desktop.png",
        "Understand your channel, with context.",
        "Dated metrics, clear sources, and a conversation that remembers the channel.",
        "01 / 03",
        p,
    )
    mobile = lambda p: screen(
        media / "clira-mobile.png",
        "Keep your ideas and operations together.",
        "Responsive creator workspace · The offline router uses templates; Gemini enables open-ended AI.",
        "02 / 03",
        p,
        True,
    )
    ops = lambda p: screen(
        media / "clira-operations.png",
        "Review the action. Approve the exact payload.",
        "Tested flow: MP4 QC → preview → owner approval → private-upload simulation → durable receipt.",
        "03 / 03",
        p,
    )
    fps = 10

    def tour():
        for frame, seconds in [(intro, 4)]:
            for _ in range(seconds * fps):
                yield frame
        for scene, seconds in [(home, 9), (mobile, 10), (ops, 11)]:
            for n in range(seconds * fps):
                yield scene(n / (seconds * fps - 1))
        for _ in range(5 * fps):
            yield outro

    encode_video(tour(), media / "Clira-tour.mp4", fps)

    # A compact, silent looping preview for GitHub's Markdown image renderer.
    preview = []
    for scene in [home, mobile, ops]:
        for n in range(8):
            frame = scene(n / 7).resize((800, 550), Image.Resampling.LANCZOS)
            preview.append(frame.quantize(colors=96, method=Image.Quantize.MEDIANCUT))
    preview[0].save(
        media / "clira-preview.gif",
        save_all=True,
        append_images=preview[1:],
        duration=360,
        loop=0,
        optimize=True,
    )

    state = work / "cli-state"
    env = {
        **os.environ,
        "CLIRA_MODE": "demo",
        "CLIRA_MODEL": "offline",
        "CLIRA_DATA_DIR": str(state),
        "CLIRA_ALLOW_MODEL_CALLS": "0",
        "CLIRA_ENABLE_WRITES": "0",
    }
    commands = [
        ("./run.sh doctor", ["./run.sh", "doctor"]),
        (
            "./run.sh chat --channel DEMO_CHANNEL_TECH 'Show my latest five uploads'",
            ["./run.sh", "chat", "--channel", "DEMO_CHANNEL_TECH", "Show my latest five uploads"],
        ),
        (
            "./run.sh ideas --channel DEMO_CHANNEL_TECH",
            ["./run.sh", "ideas", "--channel", "DEMO_CHANNEL_TECH"],
        ),
    ]
    captures = []
    for command, argv in commands:
        result = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True, check=True)
        payload = json.loads(result.stdout)
        if "message" in payload:
            output = payload["message"]
        else:
            output = json.dumps(
                {
                    k: payload[k]
                    for k in [
                        "python",
                        "mode",
                        "migration_version",
                        "ffprobe",
                        "model",
                        "model_key_present",
                        "oauth_client_configured",
                        "writes_enabled",
                    ]
                },
                indent=2,
            )
        captures.append({"command": command, "stdout_excerpt": output})
    (media / "cli-capture.json").write_text(json.dumps(captures, indent=2) + "\n")

    def terminal_frame(capture, progress):
        image = Image.new("RGB", (1600, 1100), "#171e19")
        d = ImageDraw.Draw(image)
        d.rounded_rectangle((55, 55, 1545, 1045), radius=15, fill="#202a22", outline="#46523e", width=2)
        for x, c in [(90, "#c78368"), (120, "#cfb870"), (150, "#8ca37b")]:
            d.ellipse((x, 88, x + 13, 101), fill=c)
        write(d, (195, 78), "clira — local creator workspace", 19, MUTED)
        write(d, (90, 148), "SYNTHETIC DEMO · ACTUAL CLI OUTPUT EXCERPTS", 18, GOLD)
        lines = textwrap.wrap("$ " + capture["command"], 88)
        for i, line in enumerate(lines):
            write(d, (90, 205 + i * 34), line, 24, "#e7ebda")
        body = []
        for line in capture["stdout_excerpt"].splitlines():
            body.extend(textwrap.wrap(line, 94) or [""])
        reveal = max(1, round(len(body) * min(1, progress * 2)))
        for i, line in enumerate(body[:reveal]):
            write(d, (90, 305 + i * 33), line, 23, "#c2cfb5")
        write(
            d,
            (90, 987),
            "Output shortened for readability · No paid model calls or Google account actions",
            17,
            "#8e9b83",
        )
        return image

    def cli_frames():
        for capture in captures:
            for n in range(8 * fps):
                yield terminal_frame(capture, n / (8 * fps - 1))

    encode_video(cli_frames(), media / "Clira-cli.mp4", fps)
    terminal_frame(captures[1], 1).save(media / "cli-poster.jpg", quality=88, optimize=True)
    banner = """<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="440" viewBox="0 0 1600 440"><rect width="1600" height="440" rx="20" fill="#222820"/><g fill="none" stroke="#aab58e"><circle cx="1320" cy="220" r="150" opacity=".35"/><circle cx="1320" cy="220" r="120" stroke="#c9b780" opacity=".5"/><path d="M110 95h0a50 50 0 0 1 50 50v100H60V145a50 50 0 0 1 50-50z"/></g><g fill="#c9b780"><text x="80" y="220" font-family="Georgia,serif" font-style="italic" font-size="110">c</text><path d="m1465 100 7 20 20 7-20 7-7 20-7-20-20-7 20-7z"/></g><text x="205" y="198" fill="#f6f4e8" font-family="Georgia,serif" font-size="105">Clira</text><text x="210" y="250" fill="#c9b780" font-family="sans-serif" font-size="20" letter-spacing="5">YOUR CREATIVE INTELLIGENCE</text><text x="65" y="340" fill="#bcc5ad" font-family="sans-serif" font-size="28">One YouTube agent. Channel memory. Your final say.</text><text x="1253" y="265" fill="#9ba985" font-family="Georgia,serif" font-size="150" font-style="italic">c</text></svg>"""
    (media / "clira-banner.svg").write_text(banner)
    print(json.dumps({p.name: p.stat().st_size for p in media.iterdir() if p.is_file()}, indent=2))


if __name__ == "__main__":
    main()
