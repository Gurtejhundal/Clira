import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Protocol

from .config import CliraError
from .storage import uid


def file_hash(path):
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def inside(path, root):
    candidate = Path(path).absolute()
    if candidate.is_symlink() or any(parent.is_symlink() for parent in candidate.parents):
        raise CliraError("PATH_NOT_ALLOWED", "Symlink paths cannot be imported.")
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise CliraError("PATH_NOT_ALLOWED", f"Copy the file into the configured imports folder: {root}")
    return resolved


def inspect_video(path):
    if not path.is_file() or not path.stat().st_size or path.suffix.lower() != ".mp4":
        raise CliraError("INVALID_MEDIA", "Expected a nonempty .mp4 file.")
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-protocol_whitelist",
                "file,crypto,data",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            timeout=30,
            check=False,
        )
        probe = json.loads(result.stdout) if result.returncode == 0 else {}
    except FileNotFoundError:
        raise CliraError("FFPROBE_REQUIRED", "Install ffmpeg/ffprobe to validate video imports.") from None
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        raise CliraError("INVALID_MEDIA", "ffprobe could not inspect this file within 30 seconds.") from None
    videos = [s for s in probe.get("streams", []) if s.get("codec_type") == "video"]
    if not videos or videos[0].get("codec_name") not in {"h264", "hevc", "av1", "vp9", "mpeg4"}:
        raise CliraError("INVALID_MEDIA", "No supported video stream found (H.264, HEVC, AV1, VP9, MPEG-4).")
    duration = float(probe.get("format", {}).get("duration", 0))
    if duration <= 0:
        raise CliraError("INVALID_MEDIA", "Video duration must be greater than zero.")
    audio = any(s.get("codec_type") == "audio" for s in probe.get("streams", []))
    return {
        "duration_seconds": duration,
        "width": videos[0].get("width"),
        "height": videos[0].get("height"),
        "codec": videos[0]["codec_name"],
        "has_audio": audio,
        "warnings": ([] if audio else ["No audio stream. Confirm this is intentional."])
        + ["Technical QC does not establish creative quality or music rights."],
    }


def import_video(config, store, channel_id, args):
    path = inside(args.path, config.import_dir)
    qc = inspect_video(path)
    if args.rights in {"licensed", "original"} and not args.rights_evidence.strip():
        raise CliraError(
            "RIGHTS_EVIDENCE", "Describe the ownership or license evidence for the video and audio."
        )
    size = path.stat().st_size
    if shutil.disk_usage(config.data_dir).free < size * 2 + 100 * 1024 * 1024:
        raise CliraError("DISK_SPACE", "Not enough disk space to safely copy and process this asset.")
    target_dir = config.data_dir / "assets" / channel_id
    target_dir.mkdir(parents=True, exist_ok=True)
    temporary = target_dir / (uid("import") + ".mp4")
    try:
        shutil.copyfile(path, temporary)
        sha = file_hash(temporary)
        # Inspect the copied bytes as well; the user's original may have changed during copying.
        qc = inspect_video(temporary)
        final = target_dir / (sha + ".mp4")
        temporary.replace(final)
        final.chmod(0o400)
    finally:
        temporary.unlink(missing_ok=True)
    existing = [a for a in store.list(channel_id, "asset") if a["sha256"] == sha]
    asset = {
        "path": str(final),
        "filename": path.name,
        "sha256": sha,
        "size": final.stat().st_size,
        "rights": args.rights,
        "rights_evidence": args.rights_evidence,
        "creative_reviewed": args.creative_reviewed,
        "qc": qc,
    }
    return store.put(channel_id, "asset", asset, existing[0]["id"] if existing else None)


def editorial_lint(kind, text, thumbnail=""):
    root = Path.home() / ".gemini/config/plugins/youtube-agent/skills"
    script = root / ("yt-package/title.py" if kind == "title" else "yt-script/hookscore.py")
    if not script.is_file():
        return {"available": False, "warning": "Optional editorial utility is not installed."}
    args = [sys.executable, str(script), "--json", "--title" if kind == "title" else "--hook", text]
    if kind == "title" and thumbnail:
        args += ["--thumb", thumbnail]
    try:
        result = subprocess.run(args, capture_output=True, timeout=10, check=True)
        return {
            "available": True,
            "heuristic_only": True,
            "results": json.loads(result.stdout),
            "warning": "Editorial heuristic, not a prediction of views, CTR, or virality.",
        }
    except (subprocess.SubprocessError, json.JSONDecodeError):
        return {"available": False, "warning": "Optional editorial utility failed; draft remains usable."}


class ProductionProvider(Protocol):
    def submit(self, brief: dict) -> dict: ...
    def status(self, external_job_id: str) -> dict: ...
    def collect(self, external_job_id: str) -> dict: ...
    def cancel(self, external_job_id: str) -> dict: ...


class ManualProductionProvider:
    """Human handoff; never starts a renderer or assumes a video was made."""

    def __init__(self, store, channel_id):
        self.store, self.channel_id = store, channel_id

    def submit(self, brief):
        result = self.store.put(
            self.channel_id, "production", {"brief": brief, "status": "awaiting_manual_video"}
        )
        return {"external_job_id": result["id"], "status": result["status"]}

    def status(self, external_job_id):
        return self.store.get(self.channel_id, external_job_id, "production")

    def collect(self, external_job_id):
        record = self.status(external_job_id)
        if record["status"] != "completed":
            raise CliraError("VIDEO_REQUIRED", "Import a finished MP4. No external renderer is configured.")
        return record

    def cancel(self, external_job_id):
        record = self.status(external_job_id)
        return self.store.put(
            self.channel_id, "production", {**record, "status": "cancelled"}, external_job_id
        )
