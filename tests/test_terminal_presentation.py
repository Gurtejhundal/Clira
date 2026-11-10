"""Layout invariants for the actual Rich renderer, alongside the PTY workflow tests."""

import io
import re

import pytest
from rich.cells import cell_len
from rich.console import Console

from clira.agent import Agent
from clira.service import DEMO_CHANNEL
from clira.tui.app import Terminal


def terminal(service, width=120, height=48, channel=None, no_logo=False):
    result = Terminal(service, channel, no_logo=no_logo)
    result.console = Console(file=io.StringIO(), width=width, height=height, record=True, no_color=True)
    return result


@pytest.mark.parametrize("width", [40, 52, 80, 99, 100, 120, 160])
@pytest.mark.parametrize("channel", [None, DEMO_CHANNEL])
def test_welcome_reflows_without_truncation_or_contract_leak(service, width, channel):
    app = terminal(service, width, channel=channel)
    app.view.welcome()
    output = app.console.export_text()
    assert all(cell_len(line) <= min(width, 124) for line in output.splitlines())
    assert "End of single-file" not in output
    assert "v1.0.0rc1" in output and "\x1b" not in output
    assert bool(re.search(r"[\u2800-\u28ff]", output)) == (width >= 100)
    if channel:
        assert DEMO_CHANNEL in output and "SYNTHETIC" in output
        assert "live writes disabled" in output and "Offline" in output
    else:
        assert "Welcome to Clira." in output
        assert "Start planning" in output and "Connect an existing" in output
        assert "Explore synthetic demo data" in output


@pytest.mark.parametrize("width", [40, 52, 80, 120])
def test_short_terminal_keeps_onboarding_visible(service, width):
    app = terminal(service, width, height=24)
    app.view.welcome()
    output = app.console.export_text()
    assert len(output.splitlines()) <= 22
    assert not re.search(r"[\u2800-\u28ff]", output)
    assert "Start planning" in output and "Explore synthetic demo data" in output


def test_no_logo_suppresses_wordmark_and_portrait(service):
    app = terminal(service, no_logo=True)
    app.view.welcome()
    output = app.console.export_text()
    assert "█" not in output and not re.search(r"[\u2800-\u28ff]", output)
    assert "Clira" in output and "Welcome to Clira." in output


def test_status_is_real_and_all_channel_ids_remain_copyable(service):
    service.store.set_setting("paused", True)
    app = terminal(service, channel=DEMO_CHANNEL)
    session = service.store.new_session(DEMO_CHANNEL, "An owner review")
    app.conversation = session["id"]
    app.view.status()
    output = app.console.export_text()
    assert "PAUSED" in output and session["id"] in output
    assert DEMO_CHANNEL in output and "Scopes" in output and "none" in output


def test_answer_renders_real_receipts_and_inert_untrusted_content(service):
    app = terminal(service, channel=DEMO_CHANNEL)
    result = Agent(service).chat(DEMO_CHANNEL, "Show latest videos")
    app.conversation = result["conversation_id"]
    unsafe = "\n[owner](https://example.com)\x1b]52;c;clipboard-payload\x07\u202e"
    app.view.answer(result["message"] + unsafe, result["receipts"], elapsed=0.2)
    output = app.console.export_text()
    assert "CLIRA" in output and "SYNTHETIC DEMO" in output
    assert "list_videos" in output and "mock" in output
    assert result["conversation_id"] in output and "1 tool receipts" in output
    assert "clipboard-payload" not in output and "\u202e" not in output and "\x1b" not in output
    assert len([line for line in output.splitlines() if "• " in line]) == 5


def test_mono_render_uses_no_color_or_hyperlink_escape(service, monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    app = terminal(service)
    buffer = io.StringIO()
    app.console = Console(file=buffer, width=120, height=48, force_terminal=True, color_system="truecolor")
    app.theme = "mono"
    app.apply_theme()
    app.view.welcome()
    app.view.answer("[A source](https://example.com)")
    output = buffer.getvalue()
    # Bold/dim cursor-independent styling is allowed; foreground/background color and OSC links aren't.
    assert not re.search(r"\x1b\[[0-9;]*(?:3[0-9]|4[0-9]|9[0-7])(?:;[0-9;]*)?m", output)
    assert "\x1b]8;" not in output


def test_workspace_names_are_literal_text_in_frame(service):
    service.store.add_channel("DEMO_OTHER", "[red]Viewer\x1b]52;c;hidden\x07", "demo")
    app = terminal(service, channel="DEMO_OTHER")
    app.view.welcome()
    output = app.console.export_text()
    assert "[red]Viewer" in output and "hidden" not in output


@pytest.mark.parametrize("theme,background", [("light", "#f8f7f2"), ("dark", "#171a18")])
def test_rendered_secondary_text_has_readable_contrast(service, theme, background):
    app = terminal(service)
    app.theme = theme
    app.console.no_color = False
    app.view.welcome()
    html = app.console.export_html(inline_styles=True)
    assert "color: " + app.view.muted in html

    def luminance(color):
        channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return sum(c * weight for c, weight in zip(linear, [0.2126, 0.7152, 0.0722]))

    high, low = sorted([luminance(background), luminance(app.view.muted)], reverse=True)
    assert (high + 0.05) / (low + 0.05) >= 4.5


def test_startup_preserves_approved_bold_layout(service):
    app = terminal(service, channel=DEMO_CHANNEL)
    app.view.welcome()
    output = app.console.export_text()
    assert "█" in output and "YOUR CREATIVE INTELLIGENCE" in output
    assert "YOUTUBE WORKSPACE" in output and "CREATOR TOOLKIT" in output
    assert all(char in output for char in "╭╮╰╯")
    assert DEMO_CHANNEL in output and "live writes disabled" in output


@pytest.mark.parametrize("background,accent", [("0;15", "#85652f"), ("15;0", "#c5a368"), ("", "#c5a368")])
def test_auto_uses_clira_gold_and_respects_background_hint(service, monkeypatch, background, accent):
    monkeypatch.setenv("COLORFGBG", background)
    app = terminal(service)
    app.theme = "auto"
    assert app.view.accent == accent
    app.console.no_color = False
    app.view.welcome()
    html = app.console.export_html(inline_styles=True)
    assert "color: " + accent in html
    # The app must never paint over the owner's terminal background.
    assert "background-color:" not in html.split("<code", 1)[1].split("</code>", 1)[0]
