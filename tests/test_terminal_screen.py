"""Assertions use visible VT screen cells, not accidental matches in redraw escape sequences."""

import re

import pytest

from clira.service import DEMO_CHANNEL
from clira.storage import Store
from scripts.capture_split_terminal import TerminalProbe


@pytest.mark.parametrize("width,height", [(40, 24), (80, 32), (140, 48)])
def test_full_screen_startup_multiline_and_clean_exit(tmp_path, width, height):
    probe = TerminalProbe(tmp_path, width, height)
    try:
        probe.wait("Choose 1 / 2 / 3")
        assert "CLIRA" in probe.text
        probe.send("3\r")
        probe.wait("❯")
        probe.send("Show latest\x0avideos\r")
        probe.wait("list_videos")
        assert "mock" in probe.text
        probe.send("/quit\r")
        probe.process.expect(__import__("pexpect").EOF)
        probe.process.close()
        assert probe.process.exitstatus == 0
        assert "\x1b[?1049h" in probe.raw  # Application owns an alternate screen.
        assert not re.search(r"\x1b\[(?:38|48);", probe.raw)  # NO_COLOR respected.
        sessions = Store(tmp_path / "clira.sqlite3").sessions(DEMO_CHANNEL)
        assert sessions[0]["messages"][0]["text"] == "Show latest\nvideos"
    finally:
        probe.close()


def test_long_conversation_sidebar_scroll_resize_and_input_are_independent(tmp_path):
    probe = TerminalProbe(tmp_path, color=True)
    try:
        probe.wait("Choose 1 / 2 / 3")
        portrait = probe.left
        assert "█" in portrait and re.search(r"[\u2800-\u28ff]", portrait)
        probe.send("3\r")
        probe.wait("❯")
        for i in range(10):
            probe.send(f"/title history-{i}\r")
            probe.send("/help\r")
        probe.send("Show latest videos\r")
        probe.wait("Latest uploads")
        assert probe.left == portrait
        latest = probe.text
        probe.send("unfinished message")
        probe.send("\x1b[5~")  # Page Up
        probe.wait("History ·")
        assert probe.left == portrait and probe.text != latest
        assert "unfinished message" in probe.text
        probe.send("\x1b[1;5F")  # Ctrl+End
        probe.wait("Latest uploads")
        assert probe.left == portrait
        probe.resize(80, 32)
        assert "Your Creative Intelligence" in probe.text and "█" not in probe.text
        assert "unfinished message" in probe.text
        probe.resize(140, 48)
        assert probe.left == portrait and "unfinished message" in probe.text
        probe.send("\x15")  # clear input, then ensure channel/session still usable
        probe.send("/status\r")
        probe.wait("Workspace status")
        assert "DEMO_CHANNEL_TECH" in probe.text
        probe.send("/clear\r")
        assert probe.left == portrait
        probe.send("/sessions\r")
        probe.wait("Saved conversations")
        assert "chat_" in probe.text
    finally:
        probe.close()


def test_full_screen_setup_back_cancel_and_workspace_return(tmp_path):
    probe = TerminalProbe(tmp_path)
    try:
        probe.wait("Choose 1 / 2 / 3")
        portrait = probe.left
        probe.send("1\r")
        probe.wait("Your interest >")
        probe.send("Batteries\r")
        probe.wait("Your viewer >")
        probe.send("/back\r")
        probe.wait("Saved answer: Batteries")
        assert probe.left == portrait
        probe.send("/cancel\r")
        probe.wait("Choose 1 / 2 / 3")
        assert not Store(tmp_path / "clira.sqlite3").rows("SELECT id FROM channels WHERE mode='draft'")
        probe.send("3\r")
        probe.wait("❯")
        probe.send("/new\r")
        probe.wait("New session:")
        probe.send("/back\r")
        probe.wait("0  Back to your workspace")
        probe.send("0\r")
        probe.wait("Back to your workspace.")
        probe.send("/sessions\r")
        probe.wait("Saved conversations")
        assert "chat_" in probe.text
    finally:
        probe.close()


def test_full_screen_owner_review_never_executes(service, prepared):
    probe = TerminalProbe(service.config.data_dir)
    try:
        probe.wait("Choose 1 / 2 / 3")
        probe.send("3\r")
        probe.wait("❯")
        probe.send("/approve " + prepared["approval_id"] + "\r")
        probe.wait("Type APPROVE")
        assert "asset_sha256" in probe.text or prepared["asset"]["sha256"] in probe.text
        probe.send("APPROVE\r")
        probe.wait("Execution is separate")
        assert service.job(DEMO_CHANNEL, prepared["job_id"])["state"] == "QUEUED"
        assert not service.store.list(DEMO_CHANNEL, "uploaded_video")
    finally:
        probe.close()


def test_full_screen_completion_history_search_and_theme_changes(tmp_path):
    probe = TerminalProbe(tmp_path, color=True)
    try:
        probe.wait("Choose 1 / 2 / 3")
        assert any(cell.fg == "c5a368" for row in probe.screen.buffer.values() for cell in row.values())
        probe.send("3\r")
        probe.wait("❯")
        probe.send("Show latest videos\r")
        probe.wait("Latest uploads")
        probe.send("/clear\r")
        probe.send("/sta\t\r")
        probe.wait("Workspace status")
        assert "Unknown command" not in probe.text
        probe.send("\x12Show latest")
        probe.wait("I-search backward")
        probe.send("\r")
        assert any("Show latest videos" in line for line in probe.screen.display[-5:])
        probe.send("\x01\x0b/theme light\r")
        probe.wait("Theme saved: light")
        assert any(cell.fg == "85652f" for row in probe.screen.buffer.values() for cell in row.values())
        probe.send("/theme mono\r")
        probe.wait("Theme saved: mono")
        assert all(cell.fg == "default" for row in probe.screen.buffer.values() for cell in row.values())
    finally:
        probe.close()
