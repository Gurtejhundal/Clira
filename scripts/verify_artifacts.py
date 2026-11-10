"""Clean install/runtime checks for local candidate artifacts; never publish anything."""

import argparse
import hashlib
import json
import os
import socket
import subprocess
import tempfile
import time
import tomllib
import urllib.request
import zipfile
from pathlib import Path

import pexpect
from capture_split_terminal import TerminalProbe


def run(args, cwd, env):
    result = subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True, check=True, timeout=120)
    return result.stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", type=Path, default=Path("dist"))
    parser.add_argument("--report", type=Path, default=Path("work/artifact-verification.json"))
    parser.add_argument(
        "--version",
        default=tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text())[
            "project"
        ]["version"],
    )
    args = parser.parse_args()
    artifacts = args.artifacts.resolve()
    report = args.report.resolve()
    version = args.version
    wheel = artifacts / f"clira-{version}-py3-none-any.whl"
    source = artifacts / f"Clira-{version}-source.zip"
    sdist = artifacts / f"clira-{version}.tar.gz"
    if not all(path.is_file() for path in [wheel, source, sdist]):
        raise RuntimeError(
            "Expected versioned wheel/source ZIP/sdist missing; build the requested candidate first."
        )
    checksums = dict(
        reversed(line.split("  ", 1)) for line in (artifacts / "SHA256SUMS.txt").read_text().splitlines()
    )
    for path in [wheel, source, sdist]:
        if checksums.get(path.name) != hashlib.sha256(path.read_bytes()).hexdigest():
            raise RuntimeError(f"Artifact checksum mismatch: {path.name}")
    results = []
    with tempfile.TemporaryDirectory(prefix="clira-clean-install-") as directory:
        root = Path(directory)
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in {"PYTHONPATH", "GEMINI_API_KEY", "CLIRA_GOOGLE_CLIENT_FILE", "CLIRA_IMPORT_DIR"}
        }
        env.update(
            CLIRA_TERMINAL_LAYOUT="inline",
            CLIRA_MODE="demo",
            CLIRA_MODEL="offline",
            CLIRA_ALLOW_MODEL_CALLS="0",
            CLIRA_ENABLE_WRITES="0",
            NO_COLOR="1",
            UV_LINK_MODE="copy",
        )
        for kind, install in [("wheel", wheel), ("source", source), ("sdist", sdist)]:
            case = root / kind
            case.mkdir()
            venv = case / "venv"
            run(["uv", "venv", "--python", "3.12", str(venv)], case, env)
            if kind == "source":
                with zipfile.ZipFile(source) as archive:
                    if any(
                        not (case / name).resolve().is_relative_to(case.resolve())
                        for name in archive.namelist()
                    ):
                        raise RuntimeError("Unsafe archive path")
                    archive.extractall(case)
                install = next(case.glob("Clira-*"))
            run(["uv", "pip", "install", "--python", str(venv / "bin/python"), str(install)], case, env)
            binary = str(venv / "bin/clira")
            env["CLIRA_DATA_DIR"] = str(case / "data")
            assert run([binary, "--version"], case, env).strip() == version
            assert "Interactive chat requires a terminal" in run([binary], case, env)
            doctor = json.loads(run([binary, "doctor"], case, env))
            assert doctor["migration_version"] == 2 and not doctor["writes_enabled"]
            chat = json.loads(
                run(
                    [binary, "chat", "--channel", "DEMO_CHANNEL_TECH", "--json", "Show latest videos"],
                    case,
                    env,
                )
            )
            assert chat["conversation_id"] and chat["receipts"][0]["source"] == "mock"
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            process = subprocess.Popen(
                [binary, "serve", "--port", str(port)],
                cwd=case,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                url = f"http://127.0.0.1:{port}"
                for _ in range(100):
                    try:
                        with urllib.request.urlopen(url + "/health", timeout=0.3) as response:
                            if json.load(response)["ok"]:
                                break
                    except OSError:
                        pass
                    time.sleep(0.1)
                else:
                    raise RuntimeError("Installed server failed to start")
                for path in [
                    "/",
                    "/static/app.js",
                    "/static/style.css",
                    "/api/conversations/DEMO_CHANNEL_TECH",
                ]:
                    with urllib.request.urlopen(url + path, timeout=2) as response:
                        assert response.status == 200
            finally:
                process.terminate()
                process.wait(timeout=10)
            # Actual installed console entrypoint under a pseudo-terminal.
            interactive = pexpect.spawn(
                binary,
                ["--no-logo"],
                cwd=str(case),
                env={**env, "TERM": "xterm", "PROMPT_TOOLKIT_NO_CPR": "1"},
                encoding="utf-8",
                timeout=15,
                dimensions=(40, 80),
            )
            interactive.expect("Choose 1 / 2 / 3")
            interactive.send("3\r")
            interactive.expect("DEMO · SYNTHETIC")
            interactive.expect("❯")
            interactive.sendcontrol("d")
            interactive.expect(pexpect.EOF)
            interactive.close()
            assert interactive.exitstatus == 0

            split = TerminalProbe(case / "split-state", python=str(venv / "bin/python"), cwd=case)
            try:
                split.wait("Choose 1 / 2 / 3")
                assert "█" in split.left
                split.send("3\r")
                split.wait("❯")
                split.send("Show latest videos\r")
                split.wait("list_videos")
                assert "SYNTHETIC DEMO" in split.text
            finally:
                split.close()
            assert split.process.exitstatus == 0

            capture = run(
                [
                    str(venv / "bin/python"),
                    "-c",
                    "from importlib.resources import files; assert files('clira').joinpath('assets/clira_braille_compact.txt').read_text().strip(); import clira.tui.app; print('packaged terminal and portrait present')",
                ],
                case,
                env,
            )
            results.append(
                {
                    "kind": kind,
                    "version": version,
                    "checks": [
                        "artifact checksum",
                        "console version",
                        "installed interactive PTY",
                        "installed persistent split screen and offline receipt",
                        "safe non-TTY startup",
                        "doctor migration",
                        "offline chat",
                        "loopback server",
                        "static assets",
                        "shared session route",
                        capture.strip(),
                    ],
                    "passed": True,
                }
            )
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(results, indent=2) + "\n")
    print(report.read_text())


if __name__ == "__main__":
    main()
