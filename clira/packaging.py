"""Real local packaging assets; external writes remain ordinary approved jobs."""

import io
import itertools
import re
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

from .config import CliraError
from .media import file_hash, inside
from .storage import uid

# Deliberately conservative app limits, below current API maxima (50 MB / 100 MB).
THUMBNAIL_LIMIT = 2 * 1024 * 1024
CAPTION_LIMIT = 4 * 1024 * 1024


def caption_time(value):
    value = value.replace(",", ".")
    if not re.fullmatch(r"(?:\d{2,}:)?\d{2}:\d{2}\.\d{3}", value):
        raise CliraError("CAPTION_TIME", "Use HH:MM:SS,mmm (SRT) or HH:MM:SS.mmm (VTT).")
    parts = value.split(":")
    hours, minutes, seconds = ([0] + parts) if len(parts) == 2 else parts
    if int(minutes) > 59 or float(seconds) >= 60:
        raise CliraError("CAPTION_TIME", "Caption minutes and seconds must be below 60.")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def captions(text, duration=None):
    text = text.lstrip("\ufeff").replace("\r\n", "\n").strip()
    is_vtt = text.startswith("WEBVTT\n") or text == "WEBVTT"
    blocks = re.split(r"\n\s*\n", text)
    if is_vtt:
        blocks = blocks[1:]
    cues = []
    for block in blocks:
        lines = block.splitlines()
        if not lines:
            continue
        timing = 0 if "-->" in lines[0] else 1
        if timing >= len(lines) or "-->" not in lines[timing]:
            raise CliraError("CAPTION_FORMAT", "Every caption block needs a timed cue and text.")
        match = re.fullmatch(r"(\S+)\s+-->\s+(\S+)", lines[timing])
        if not match or not lines[timing + 1 :]:
            raise CliraError(
                "CAPTION_FORMAT",
                "Basic SRT/VTT cues require start, end and visible text; cue settings unsupported.",
            )
        start, end = map(caption_time, match.groups())
        if end <= start or (cues and start < cues[-1]["end"]) or (duration and end > duration + 0.1):
            raise CliraError(
                "CAPTION_RANGE", "Cues must be ordered, nonoverlapping and within the video duration."
            )
        body = "\n".join(lines[timing + 1 :])
        if "<" in body or ">" in body or any(ord(c) < 32 and c not in "\n\t" for c in body):
            raise CliraError(
                "CAPTION_TEXT", "Only plain caption text is supported; remove markup/control characters."
            )
        cues.append({"start": start, "end": end, "text": body})
    if not cues or len(cues) > 20000:
        raise CliraError("CAPTION_FORMAT", "Expected 1–20000 timed cues.")
    return {"format": "vtt" if is_vtt else "srt", "cues": cues, "text": text + "\n"}


def chapters(items, duration):
    if not items:
        return ""
    times = [c["seconds"] for c in items]
    if (
        len(items) < 3
        or times[0] != 0
        or any(b - a < 10 for a, b in itertools.pairwise(times))
        or duration - times[-1] < 10
    ):
        raise CliraError(
            "CHAPTERS",
            "Use at least three chapters, starting at 00:00; every chapter must last at least 10 seconds within the actual video.",
        )

    def stamp(seconds):
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        return f"{h}:{m:02}:{s:02}" if h else f"{m:02}:{s:02}"

    return "\n".join(stamp(c["seconds"]) + " " + c["title"] for c in items)


def save_asset(service, channel_id, content, suffix, facts, rights, evidence, reviewed):
    directory = service.config.data_dir / "assets" / channel_id
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (uid("package") + suffix)
    target.write_bytes(content)
    target.chmod(0o400)
    return service.store.put(
        channel_id,
        "package_asset",
        {
            "path": str(target),
            "filename": target.name,
            "sha256": file_hash(target),
            "size": len(content),
            "rights": rights,
            "rights_evidence": evidence,
            "creative_reviewed": reviewed,
            **facts,
        },
    )


def import_asset(service, channel_id, args):
    source = inside(args.path, service.config.import_dir)
    limit = THUMBNAIL_LIMIT if args.type == "thumbnail" else CAPTION_LIMIT
    if not source.is_file() or not 0 < source.stat().st_size <= limit:
        raise CliraError("PACKAGE_SIZE", f"Expected a nonempty file under {limit} bytes.")
    content = source.read_bytes()
    if len(content) > limit:
        raise CliraError("PACKAGE_SIZE", "File changed during import.")
    if args.type == "thumbnail":
        try:
            with Image.open(io.BytesIO(content)) as image:
                if image.format not in {"JPEG", "PNG"} or not (
                    640 <= image.width <= 7680 and 360 <= image.height <= 4320
                ):
                    raise CliraError(
                        "THUMBNAIL_FORMAT",
                        "Use JPEG/PNG, at least 640×360; recommended 1280×720 for long form.",
                    )
                image.verify()
            with Image.open(io.BytesIO(content)) as image:
                facts = {
                    "type": "thumbnail",
                    "width": image.width,
                    "height": image.height,
                    "mime": "image/png" if image.format == "PNG" else "image/jpeg",
                }
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            raise CliraError("THUMBNAIL_FORMAT", "Cannot decode this image safely.") from None
        suffix = ".png" if facts["mime"] == "image/png" else ".jpg"
    else:
        asset = service.store.get(channel_id, args.asset_id, "asset") if args.asset_id else None
        try:
            facts = {
                "type": "captions",
                **captions(content.decode("utf-8-sig"), asset["qc"]["duration_seconds"] if asset else None),
            }
        except UnicodeError:
            raise CliraError("CAPTION_ENCODING", "Use UTF-8 SRT or VTT.") from None
        facts.update(
            {
                "language": args.language,
                "mime": "text/vtt" if facts["format"] == "vtt" else "application/x-subrip",
                "video_asset_id": args.asset_id,
            }
        )
        suffix = "." + facts["format"]
    return save_asset(
        service, channel_id, content, suffix, facts, args.rights, args.rights_evidence, args.creative_reviewed
    )


def template(service, channel_id, args):
    # A real deterministic PNG, explicitly selected by the owner; no image-model claim.
    image = Image.new("RGB", (1280, 720), "#F8F7F2")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=64)
    draw.rectangle((48, 48, 64, 672), fill="#85652F")
    draw.multiline_text(
        (112, 160), "\n".join(textwrap.wrap(args.text, width=24)), font=font, fill="#252B24", spacing=24
    )
    output = io.BytesIO()
    image.save(output, format="PNG")
    return save_asset(
        service,
        channel_id,
        output.getvalue(),
        ".png",
        {
            "type": "thumbnail",
            "mime": "image/png",
            "width": 1280,
            "height": 720,
            "provider": "deterministic local template",
            "text": args.text,
        },
        "unreviewed",
        "",
        False,
    )


def verify_package_asset(service, channel_id, record, reviewed=True):
    path = Path(record["path"])
    root = service.config.data_dir / "assets" / channel_id
    if (
        path.is_symlink()
        or not path.resolve().is_relative_to(root.resolve())
        or not path.is_file()
        or file_hash(path) != record["sha256"]
    ):
        raise CliraError("ASSET_CHANGED", "Packaging file missing or changed; import and approve again.")
    if reviewed and (
        record["rights"] not in {"original", "licensed"}
        or not record["rights_evidence"].strip()
        or not record["creative_reviewed"]
    ):
        raise CliraError(
            "RIGHTS_REVIEW_REQUIRED",
            "Review packaging rights, evidence and creative quality before account writes.",
        )
    return path
