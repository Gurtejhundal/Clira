import pytest

from clira.config import CliraError
from clira.creator import Creator
from scripts.capture_split_terminal import TerminalProbe


@pytest.mark.parametrize(
    "value,expected",
    [
        ("Asia/Kolkata", "Asia/Kolkata"),
        ("Asia/kolkata", "Asia/Kolkata"),
        ("asia kolkata", "Asia/Kolkata"),
        ("Kolkata", "Asia/Kolkata"),
        ("america new york", "America/New_York"),
        ("utc", "UTC"),
        ("don't know", "UTC"),
        ("skip", "UTC"),
    ],
)
def test_timezone_input_is_normalized_before_saving(service, value, expected):
    creator = Creator(service)
    creator.save_answer("timezone", value, 7)
    assert creator.draft()["answers"]["timezone"] == expected


def test_unknown_timezone_preserves_previous_answers(service):
    creator = Creator(service)
    creator.save_answer("name", "Alex", 1)
    with pytest.raises(CliraError):
        creator.save_answer("timezone", "Mars/Olympus", 7)
    assert creator.draft()["answers"] == {"name": "Alex"}


def test_terminal_resumes_timezone_and_accepts_screenshot_spelling(tmp_path):
    from clira.config import Config
    from clira.service import Service

    service = Service(Config(data_dir=tmp_path, mode="demo", model="offline"))
    service.store.set_setting(
        "creator_setup_draft", {"answers": {"name": "Alex", "passions": "Tech"}, "step": 6}
    )
    probe = TerminalProbe(tmp_path, quickstart=False)
    try:
        probe.wait("Your timezone or city?")
        probe.send("asia kolkata\r")
        probe.wait("How should your channel sound")
        assert service.store.setting("creator_setup_draft")["answers"]["timezone"] == "Asia/Kolkata"
        assert service.store.setting("creator_setup_draft")["answers"]["name"] == "Alex"
    finally:
        probe.close()
