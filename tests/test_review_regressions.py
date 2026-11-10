import threading
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from clira.agent import GeminiProvider
from clira.config import CliraError
from clira.creator import Creator, valid_model_key
from clira.service import DEMO_CHANNEL
from clira.telegram import Telegram, pairing_code
from clira.tui.app import Terminal
from clira.tui.setup import CreatorSetup


@pytest.mark.parametrize("key", ["AQ." + "Z" * 50, "AIza" + "z" * 35])
def test_supported_key_formats_are_never_saved_as_creator_memory(service, key):
    assert valid_model_key(key)
    with pytest.raises(CliraError, match="masked"):
        Creator(service).remember(DEMO_CHANNEL, key)
    assert not service.store.list(DEMO_CHANNEL, "memory")


@pytest.mark.parametrize(
    "key", ["short", "AQ." + "z" * 30 + "\nmore", "x" * 513, "key with whitespace" + "x" * 40]
)
def test_credential_validation_rejects_broken_header_values(key):
    assert not valid_model_key(key)


def test_connection_typo_retries_and_accepts_auth_key_without_network(service, monkeypatch):
    terminal = Terminal(service)
    answers = iter(["1", "1", "test-model", "no", "2", "2"])
    credentials = iter(["invalid", "AQ." + "Z" * 50])
    monkeypatch.setattr(terminal, "ask", lambda q: next(answers))
    monkeypatch.setattr(terminal, "ask_secret", lambda q: next(credentials))
    assert CreatorSetup(terminal).connections()
    assert service.secrets.get("gemini")["api_key"].startswith("AQ.")
    assert not service.config.allow_model_calls


def test_parallel_update_claims_execute_at_most_once(service):
    # Claim methods do not require a running bot or external requests.
    first, second = Telegram.__new__(Telegram), Telegram.__new__(Telegram)
    first.service = second.service = service
    barrier = threading.Barrier(2)

    def run(transport):
        barrier.wait()
        return transport.claim_update(123)

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(run, [first, second])) == [False, True]
    assert service.store.setting("telegram_offset") == 124


def test_pairing_code_is_consumed_atomically_across_pollers(service):
    code = pairing_code(service)
    first, second = Telegram.__new__(Telegram), Telegram.__new__(Telegram)
    first.service = second.service = service
    barrier = threading.Barrier(2)

    def run(item):
        transport, owner = item
        barrier.wait()
        return transport.claim_pair(owner, owner, code)

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(run, [(first, 42), (second, 99)])) == [False, True]
    assert service.store.setting("telegram_owner")["user_id"] in {42, 99}
    assert service.store.setting("telegram_pair") == {}


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="not json"),
        httpx.Response(200, json={"candidates": ["bad"]}),
        httpx.Response(200, json={"candidates": [{"content": None}]}),
        httpx.Response(200, json={"candidates": [{"content": {"parts": [42]}}]}),
    ],
)
def test_invalid_model_response_is_a_recoverable_redacted_error(service, response, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    service.config.allow_model_calls = True
    provider = GeminiProvider(
        service.config,
        service.store,
        client=httpx.Client(transport=httpx.MockTransport(lambda r: response)),
        key="AQ." + "Z" * 50,
    )
    with pytest.raises(CliraError) as exc:
        provider.generate([], [], {"system": "test"})
    assert exc.value.code == "MODEL_SCHEMA"
    assert "AQ." not in str(exc.value)


@pytest.mark.parametrize("part", [{"functionCall": None}, {"text": 42}])
def test_invalid_model_turn_releases_session_lease_without_running_tools(service, part):
    from clira.agent import Agent, ModelTurn

    class BrokenProvider:
        def generate(self, messages, tools, limits):
            return ModelTurn({"role": "model", "parts": [part]})

    with pytest.raises(CliraError) as exc:
        Agent(service, BrokenProvider()).chat(DEMO_CHANNEL, "A test message")
    assert exc.value.code == "MODEL_SCHEMA"
    assert service.store.rows("SELECT activity FROM session_meta")[0]["activity"] == "failed"
    assert not service.store.rows("SELECT * FROM jobs")
