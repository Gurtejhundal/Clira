import json
import os
import subprocess
import sys

import pexpect
import pytest
from fastapi.testclient import TestClient

from clira.api import create_app
from clira.service import DEMO_CHANNEL
from clira.workspaces import launch


def spawn(tmp_path, width=80, *args):
    return pexpect.spawn(
        sys.executable,
        ["-m", "clira", "--data-dir", str(tmp_path), *args],
        env={
            **os.environ,
            "CLIRA_MODEL": "offline",
            "CLIRA_MODE": "demo",
            "NO_COLOR": "1",
            "TERM": "xterm",
            "PROMPT_TOOLKIT_NO_CPR": "1",
        },
        encoding="utf-8",
        timeout=15,
        dimensions=(45, width),
    )


@pytest.mark.parametrize("width", [40, 52, 80, 120])
def test_terminal_start_and_resume(tmp_path, width):
    child = spawn(tmp_path, width)
    child.expect("Choose 1 / 2 / 3")
    child.send("3\r")
    child.expect("DEMO · SYNTHETIC")
    child.expect("❯")
    child.send("/new\r")
    child.expect(r"New session:\s+(chat_[a-f0-9]{32})")
    session_id = child.match.group(1)
    child.expect("❯")
    child.send("/title Owner review\r")
    child.expect("Session title saved")
    child.send("/hep\r")
    child.expect("Unknown command")
    child.expect("/help")
    child.send("/quit\r")
    child.expect(pexpect.EOF)
    child = spawn(tmp_path, width, "--channel", DEMO_CHANNEL, "--resume", session_id, "--no-logo")
    child.expect("Resumed Owner review")
    child.expect("❯")
    child.sendcontrol("d")
    child.expect(pexpect.EOF)


def test_redirected_no_ansi(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "clira", "--data-dir", str(tmp_path)], check=False, capture_output=True
    )
    assert result.returncode == 0
    assert b"\x1b" not in result.stdout
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "clira",
            "--data-dir",
            str(tmp_path),
            "chat",
            "--channel",
            DEMO_CHANNEL,
            "latest videos",
            "--json",
        ],
        check=False,
        capture_output=True,
    )
    assert json.loads(result.stdout)["conversation_id"]


def test_launch_and_shared_sessions(service):
    result = launch(service, "Batteries", "curious beginners", "English", "4 hours", "short")
    workspace = result["workspace"]["id"]
    assert workspace.startswith("workspace_") and not workspace.startswith("UC")
    assert len(service.store.list(workspace, "idea")) == 3
    assert not service.tool(workspace, "channel_report")["ok"]
    with pytest.raises(Exception, match="Local launch workspaces"):
        service.policy.write_gate(workspace)
    from clira.agent import Agent

    conversation = Agent(service).chat(workspace, "Plan my first channel")
    client = TestClient(create_app(service))
    sessions = client.get("/api/conversations/" + workspace).json()
    assert sessions[0]["id"] == conversation["conversation_id"]
    assert sessions[0]["messages"][-1]["text"] == conversation["message"]
    assert (
        client.get("/api/conversations/" + DEMO_CHANNEL + "/" + conversation["conversation_id"]).status_code
        == 400
    )
    token = client.get("/api/session").json()["token"]
    assert (
        client.put(
            "/api/conversations/" + conversation["conversation_id"],
            headers={"x-clira-token": token},
            json={"channel_id": workspace, "title": "Launch review"},
        ).status_code
        == 200
    )
    assert service.store.session(workspace, conversation["conversation_id"])["title"] == "Launch review"


def test_multiline_details_interrupt_and_fake_connection(tmp_path):
    child = spawn(tmp_path, 120, "--no-logo")
    child.expect("Choose 1 / 2 / 3")
    child.send("3\r")
    child.expect("❯")
    child.send("Show my latest")
    child.sendcontrol("j")
    child.send("videos\r")
    child.expect("Latest uploads")
    child.expect(r"session (chat_[a-f0-9]+)")
    session_id = child.match.group(1)
    child.expect("❯")
    child.send("/details\r")
    child.expect("receipts")
    child.send("/connect\r")
    child.expect("Read-only OAuth")
    child.sendcontrol("c")
    child.expect("interrupted")
    child.sendcontrol("c")
    child.expect(pexpect.EOF)
    from clira.storage import Store

    record = Store(tmp_path / "clira.sqlite3").session(DEMO_CHANNEL, session_id)
    assert record["messages"][0]["text"] == "Show my latest\nvideos"
    assert "session_" not in json.dumps(record["messages"][1].get("receipts", []))


def test_terminal_five_step_launch_without_channel(tmp_path):
    child = spawn(tmp_path, 80, "--no-logo")
    child.expect("Choose 1 / 2 / 3")
    child.send("1\r")
    for prompt, answer in [
        ("Your interest", "Batteries"),
        ("Your viewer", "Beginners"),
        ("Language", "English"),
        ("Time per week", "4 hours"),
        ("Format", "short"),
    ]:
        child.expect(prompt)
        child.send(answer + "\r")
    child.expect("No YouTube account created")
    child.expect("LOCAL DRAFT")
    child.expect("❯")
    child.send("Plan my first channel\r")
    child.expect("Offline planning workspace")
    child.expect("❯")
    child.send("/approvals\r")
    child.expect("No approvals")
    child.send("/quit\r")
    child.expect(pexpect.EOF)
    from clira.storage import Store

    store = Store(tmp_path / "clira.sqlite3")
    workspace = store.rows("SELECT id FROM channels WHERE mode='draft'")[0]["id"]
    assert workspace.startswith("workspace_") and len(store.list(workspace, "idea")) == 3


def test_approval_in_terminal_does_not_execute(service, prepared):
    from clira.tui.app import Terminal

    terminal = Terminal(service, DEMO_CHANNEL, no_logo=True)
    output = []
    terminal.print = output.append
    terminal.ask = lambda question: "APPROVE"
    assert terminal.command("/approve " + prepared["approval_id"])
    assert service.job(DEMO_CHANNEL, prepared["job_id"])["state"] == "QUEUED"
    assert not service.store.list(DEMO_CHANNEL, "uploaded_video")
    assert any(prepared["asset"]["sha256"] in str(item) for item in output)
    assert any("Execution is separate" in str(item) for item in output)


def test_asset_exactly_matches_approved_portrait():
    from importlib.resources import files
    from pathlib import Path

    spec = Path("CLIRA_V1_TERMINAL_WEB_MASTER_SPEC_AND_CODEX_PROMPT.md").read_text()
    lines = spec.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("                 ⢀"))
    assert (
        files("clira").joinpath("assets/clira_braille_compact.txt").read_text()
        == "\n".join(lines[start:]) + "\n"
    )


def test_untrusted_terminal_escape_sequences_are_inert():
    from clira.text import terminal_text

    dangerous = "Viewer\x1b]52;c;Y2xpcGJvYXJk\x07\x1b[31m red\x1b[0m\x9b2J\u202esecret"
    safe = terminal_text(dangerous)
    assert "\x1b" not in safe and "\x9b" not in safe and "\u202e" not in safe
    assert "Y2xpcGJvYXJk" not in safe and "Viewer" in safe


def test_terminal_mono_is_persisted_and_no_color_overrides_theme(service, monkeypatch):
    from types import SimpleNamespace

    from prompt_toolkit.output import ColorDepth

    from clira.tui.app import Terminal

    monkeypatch.delenv("NO_COLOR", raising=False)
    terminal = Terminal(service, DEMO_CHANNEL, no_logo=True)
    terminal.print = lambda text: None
    terminal.prompt = SimpleNamespace(color_depth=None)
    terminal.command("/theme mono")
    assert terminal.console.no_color and terminal.console.style is None
    assert terminal.prompt.color_depth == ColorDepth.DEPTH_1_BIT
    assert Terminal(service).theme == "mono" and Terminal(service).console.no_color
    terminal.command("/theme dark")
    assert not terminal.console.no_color and terminal.prompt.color_depth is None
    monkeypatch.setenv("NO_COLOR", "1")
    terminal.command("/theme light")
    assert terminal.console.no_color and terminal.prompt.color_depth == ColorDepth.DEPTH_1_BIT


def test_first_run_invalid_launch_recovers_in_same_terminal(tmp_path):
    child = spawn(tmp_path, 80, "--no-logo")
    child.expect("Choose 1 / 2 / 3")
    child.send("1\r")
    for prompt in ["Your interest", "Your viewer", "Language", "Time per week", "Format"]:
        child.expect(prompt)
        child.send("\r")
    child.expect("LAUNCH_INPUT")
    child.expect("Choose 1 / 2 / 3")
    child.send("3\r")
    child.expect("❯")
    child.send("/theme mono\r")
    child.expect("Theme saved: mono")
    child.expect("❯")
    child.sendcontrol("d")
    child.expect(pexpect.EOF)
    child.close()
    assert child.exitstatus == 0


def test_invalid_onboarding_does_not_recurse(service):
    from clira.tui.app import Terminal

    terminal = Terminal(service)
    answers = iter(["invalid"] * 1100 + ["3"])
    terminal.ask = lambda question: next(answers)
    terminal.print = lambda text: None
    terminal.onboarding()
    assert terminal.channel == DEMO_CHANNEL


def test_first_run_missing_live_client_returns_to_choices(tmp_path, monkeypatch):
    monkeypatch.delenv("CLIRA_GOOGLE_CLIENT_FILE", raising=False)
    child = spawn(tmp_path, 80, "--mode", "live", "--no-logo")
    child.expect("Choose 1 / 2 / 3")
    child.send("2\r")
    child.expect("CLIENT_REQUIRED")
    child.expect("Choose 1 / 2 / 3")
    child.sendcontrol("d")
    child.expect(pexpect.EOF)
    child.close()
    assert child.exitstatus == 0
    assert not list((tmp_path / "secrets").glob("*.json"))
