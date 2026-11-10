import json
import sqlite3
import subprocess
import sys
import time

from fastapi.testclient import TestClient

from clira.agent import Agent
from clira.api import create_app
from clira.config import Config
from clira.service import DEMO_CHANNEL, Service
from clira.storage import SCHEMA, Store


def test_v01_additive_migration_backup_and_rollback(tmp_path):
    path = tmp_path / "v01.sqlite3"
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA)
        db.execute("INSERT INTO migrations VALUES(1,'2026-11-01')")
        db.execute(
            "INSERT INTO channels VALUES(?,?,?,?,?,?)",
            (DEMO_CHANNEL, "Original", "demo", "{}", "{}", "2026-11-01"),
        )
        db.execute(
            "INSERT INTO conversations VALUES(?,?,?,?)",
            (
                "chat_old",
                DEMO_CHANNEL,
                json.dumps([{"role": "user", "text": "Saved before migration"}]),
                "2026-11-01",
            ),
        )
        db.commit()
        with sqlite3.connect(tmp_path / "before.sqlite3") as backup:
            db.backup(backup)
    store = Store(path)
    assert store.session(DEMO_CHANNEL, "chat_old")["messages"][0]["text"] == "Saved before migration"
    assert store.session(DEMO_CHANNEL, "chat_old")["title"] == "Untitled conversation"
    Store(path)
    assert len(store.rows("SELECT * FROM migrations")) == 2
    # Undo means use the untouched pre-migration copy, never destructively down-migrate in place.
    with sqlite3.connect(tmp_path / "before.sqlite3") as old:
        assert old.execute("SELECT MAX(version) FROM migrations").fetchone()[0] == 1
        assert not old.execute("SELECT name FROM sqlite_master WHERE name='session_meta'").fetchone()


def test_backup_command_and_restart(service, tmp_path):
    result = Agent(service).chat(DEMO_CHANNEL, "latest videos")
    target = tmp_path / "backup.sqlite3"
    command = subprocess.run(
        [sys.executable, "-m", "clira", "--data-dir", str(service.config.data_dir), "backup", str(target)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(command.stdout)["includes_secrets"] is False
    assert target.stat().st_mode & 0o077 == 0
    assert Store(target).session(DEMO_CHANNEL, result["conversation_id"])["messages"]
    again = Service(service.config)
    assert again.store.session(DEMO_CHANNEL, result["conversation_id"])["id"] == result["conversation_id"]


def test_web_oauth_missing_or_demo_never_starts(service, tmp_path, monkeypatch):
    import pytest

    from clira.config import CliraError
    from clira.connections import Connections

    with pytest.raises(CliraError, match="Demo never"):
        Connections(service).start()
    live = Service(Config(data_dir=tmp_path / "live", mode="live", model="offline"))
    monkeypatch.delenv("CLIRA_GOOGLE_CLIENT_FILE", raising=False)
    with pytest.raises(CliraError, match="privately"):
        Connections(live).start()


def test_web_oauth_read_only_exact_confirmation(tmp_path, monkeypatch):
    live = Service(Config(data_dir=tmp_path / "live", mode="live", model="offline"))
    client_path = tmp_path / "desktop.json"
    client_path.write_text("{}")
    monkeypatch.setenv("CLIRA_GOOGLE_CLIENT_FILE", str(client_path))

    def fake_connect(config, store, secrets, capability, client_file, choose):
        assert capability == "read"
        actual = {"id": "UC_OWNER_TEST", "snippet": {"title": "Owner channel"}}
        selected = choose(actual)
        assert selected == "UC_OWNER_TEST"
        store.add_channel(
            actual["id"],
            actual["snippet"]["title"],
            "live",
            connection={"secret_ref": "private-reference", "scopes": ["readonly"]},
        )
        return {"id": actual["id"], "name": actual["snippet"]["title"]}

    monkeypatch.setattr("clira.connections.connect", fake_connect)
    client = TestClient(create_app(live))
    token = client.get("/api/session").json()["token"]
    headers = {"x-clira-token": token}
    assert client.post("/api/connect/start", json={}).status_code == 403
    result = client.post("/api/connect/start", json={}, headers=headers).json()
    for _ in range(100):
        state = client.get("/api/connect/status").json()
        if state["state"] == "awaiting_confirmation":
            break
        time.sleep(0.01)
    assert state["channel_id"] == "UC_OWNER_TEST"
    assert not live.channels()
    endpoint = "/api/connect/" + result["id"] + "/confirm"
    assert client.post(endpoint, headers=headers, json={"channel_id": "WRONG"}).status_code == 400
    assert not live.channels()
    assert client.post(endpoint, headers=headers, json={"channel_id": "UC_OWNER_TEST"}).status_code == 200
    for _ in range(100):
        state = client.get("/api/connect/status").json()
        if state["state"] == "connected":
            break
        time.sleep(0.01)
    assert state["state"] == "connected"
    assert "secret" not in json.dumps(state)


def test_new_endpoints_keep_csrf_type_and_ownership(service):
    client = TestClient(create_app(service))
    token = client.get("/api/session").json()["token"]
    headers = {"x-clira-token": token}
    assert client.post("/api/conversations", json={"channel_id": DEMO_CHANNEL}).status_code == 403
    assert (
        client.post(
            "/api/conversations", content="{}", headers={**headers, "content-type": "text/plain"}
        ).status_code
        == 415
    )
    created = client.post(
        "/api/conversations", json={"channel_id": DEMO_CHANNEL, "title": "A saved title"}, headers=headers
    ).json()
    assert created["title"] == "A saved title"
    service.store.add_channel("OTHER", "Other", "demo")
    assert (
        client.put(
            "/api/conversations/" + created["id"],
            headers=headers,
            json={"channel_id": "OTHER", "title": "wrong"},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/chat",
            headers=headers,
            json={"channel_id": DEMO_CHANNEL, "conversation_id": "arbitrary_missing", "message": "hello"},
        ).status_code
        == 400
    )
    assert "arbitrary_missing" not in [s["id"] for s in service.store.sessions(DEMO_CHANNEL)]
    assert (
        client.post(
            "/api/workspaces", content="x" * 1048577, headers={**headers, "content-type": "application/json"}
        ).status_code
        == 413
    )


def test_same_session_cannot_overwrite_concurrent_request(service):
    import threading

    import pytest

    from clira.agent import ModelTurn
    from clira.config import CliraError

    entered, finish = threading.Event(), threading.Event()
    session = service.store.new_session(DEMO_CHANNEL)["id"]

    class SlowProvider:
        def generate(self, *args):
            entered.set()
            finish.wait(5)
            return ModelTurn({"role": "model", "parts": [{"text": "Completed one actual request."}]})

    error = []

    def run():
        try:
            Agent(service, SlowProvider()).chat(DEMO_CHANNEL, "First message", session)
        except (CliraError, ValueError, OSError) as exc:
            error.append(exc)

    thread = threading.Thread(target=run)
    thread.start()
    assert entered.wait(5)
    assert service.store.session(DEMO_CHANNEL, session)["activity"] == "running"
    with pytest.raises(CliraError, match="running request"):
        Agent(service).chat(DEMO_CHANNEL, "Racing message", session)
    finish.set()
    thread.join(5)
    assert not error
    record = service.store.session(DEMO_CHANNEL, session)
    assert len(record["messages"]) == 2 and record["activity"] == "completed"


def test_draft_copy_requires_live_owner_confirmation_and_preserves_source(tmp_path):
    import pytest

    from clira.config import CliraError
    from clira.workspaces import copy_drafts, launch

    service = Service(Config(data_dir=tmp_path, mode="live", model="offline"))
    source = launch(service, "Batteries", "Beginners", "English", "4 hours", "short")["workspace"]["id"]
    service.store.add_channel("UC_OWNER", "Owner", "live", connection={"secret_ref": "private"})
    with pytest.raises(CliraError):
        copy_drafts(service, source, "UC_OWNER", "WRONG")
    assert not service.store.list("UC_OWNER", "idea")
    copied = copy_drafts(service, source, "UC_OWNER", "UC_OWNER")
    assert len(copied["copied"]) == 3 and len(service.store.list(source, "idea")) == 3
    assert len(service.store.list("UC_OWNER", "idea")) == 3
    assert not service.store.sessions("UC_OWNER") and not service.store.list("UC_OWNER", "asset")
