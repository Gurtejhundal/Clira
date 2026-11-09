"""Build versioned source/install packages and checksums from tracked files only."""

import argparse
import hashlib
import json
import shutil
import subprocess
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    from clira import __version__

    if version != __version__:
        raise RuntimeError("Package and runtime versions must match")
    tracked = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    files = [Path(p) for p in tracked.decode().split("\0") if p]
    if not files:
        raise RuntimeError("Stage the source files before building a release")
    forbidden = {".clira", ".venv", "work", "__pycache__", ".git", ".env"}
    for path in files:
        if any(part in forbidden for part in path.parts) or path.suffix in {".sqlite3", ".pyc"}:
            raise RuntimeError(f"Runtime/private file must not be tracked: {path}")
        if path.name.startswith(("client_secret", "credentials", "token")) and path.suffix == ".json":
            raise RuntimeError(f"Credential-like file must not be tracked: {path}")
    archive = output / f"Clira-{version}-source.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for path in files:
            z.write(ROOT / path, Path(f"Clira-{version}") / path)
    subprocess.run(["uv", "build", "--out-dir", str(output)], cwd=ROOT, check=True)
    for name in ["Clira-tour.mp4", "Clira-cli.mp4"]:
        shutil.copyfile(ROOT / "docs/media" / name, output / name)
    assets = [
        archive,
        output / f"clira-{version}-py3-none-any.whl",
        output / f"clira-{version}.tar.gz",
        output / "Clira-tour.mp4",
        output / "Clira-cli.mp4",
    ]
    with zipfile.ZipFile(assets[1]) as wheel:
        for name in ["clira/web/index.html", "clira/web/app.js", "clira/web/style.css"]:
            if name not in wheel.namelist():
                raise RuntimeError(f"Wheel is missing a runtime asset: {name}")
    checksums = "".join(hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n" for p in assets)
    (output / "SHA256SUMS.txt").write_text(checksums)
    print(
        json.dumps(
            {"version": version, "files": [p.name for p in assets], "source_files": len(files)}, indent=2
        )
    )


if __name__ == "__main__":
    main()
