import json

import pytest
from fastapi.testclient import TestClient

from clira.agent import Agent
from clira.api import create_app
from clira.config import CliraError
from clira.service import DEMO_CHANNEL
from clira.storage import Store, now


def client_for(service):
    client = TestClient(create_app(service))
    return client, {"x-clira-token": client.get("/api/session").json()["token"]}


def test_history_metadata_is_paginated_searchable_and_does_not_return_transcripts(service):
    # Many long chats must not make the sidebar download all message bodies.
    with service.store.connect() as db:
        for number in range(115):
            chat_id = f"chat_history_{number:03}"
            db.execute(
                "INSERT INTO conversations VALUES(?,?,?,?)",
                (chat_id, DEMO_CHANNEL, json.dumps([{"text": "private transcript " * 100}]), now()),
            )
            db.execute(
                "INSERT INTO session_meta VALUES(?,?,?,?,?)",
                (chat_id, f"Video idea {number:03}", now(), now(), "completed"),
            )
    service.store.manage_session(DEMO_CHANNEL, "chat_history_000", "pin")
    client, headers = client_for(service)
    path = f"/api/conversations/{DEMO_CHANNEL}?summary=true"
    first = client.get(path).json()
    assert first["total"] == 115 and len(first["items"]) == 50 and first["has_more"]
    assert first["items"][0]["id"] == "chat_history_000" and first["items"][0]["pinned"]
    assert all("messages" not in row for row in first["items"])
    second = client.get(path + "&offset=50").json()
    third = client.get(path + "&offset=100").json()
    all_ids = [row["id"] for page in [first, second, third] for row in page["items"]]
    assert len(set(all_ids)) == 115 and not third["has_more"]
    assert client.get(path + "&search=Video%20idea%20004").json()["total"] == 1
    # Wildcards are literal characters; pagination is bounded at the API boundary.
    assert client.get(path + "&search=%25").json()["total"] == 0
    assert client.get(path + "&limit=10000").status_code == 422
    assert client.get(path + "&offset=-1").status_code == 422
    assert client.get(path + "&folder=other").status_code == 422
    # Existing terminal/API consumers keep their full-transcript list shape.
    assert "messages" in client.get(f"/api/conversations/{DEMO_CHANNEL}").json()[0]
    assert (
        client.post(
            "/api/conversations/chat_history_000/manage",
            json={"channel_id": DEMO_CHANNEL, "action": "unpin"},
            headers=headers,
        ).status_code
        == 200
    )


def test_history_actions_persist_and_remain_channel_scoped(service):
    chat = service.store.new_session(DEMO_CHANNEL, "An owner chat")
    service.store.add_channel("OTHER_WORKSPACE", "Other", "demo")
    client, headers = client_for(service)
    path = f"/api/conversations/{chat['id']}/manage"
    for action in ["pin", "archive", "trash", "restore"]:
        assert client.post(path, json={"channel_id": DEMO_CHANNEL, "action": action}).status_code == 403
        assert (
            client.post(
                path, json={"channel_id": "OTHER_WORKSPACE", "action": action}, headers=headers
            ).status_code
            == 400
        )
    assert (
        client.post(
            path, json={"channel_id": DEMO_CHANNEL, "action": "grant_write"}, headers=headers
        ).status_code
        == 422
    )
    assert (
        client.post(
            path, json={"channel_id": DEMO_CHANNEL, "action": "pin", "extra": True}, headers=headers
        ).status_code
        == 422
    )
    assert (
        client.post(path, json={"channel_id": DEMO_CHANNEL, "action": "pin"}, headers=headers).status_code
        == 200
    )
    again = Store(service.store.path)
    assert again.session(DEMO_CHANNEL, chat["id"])["pinned"]
    again.manage_session(DEMO_CHANNEL, chat["id"], "archive")
    assert not again.sessions(DEMO_CHANNEL)
    assert again.session_index(DEMO_CHANNEL, folder="archived")["total"] == 1
    again.manage_session(DEMO_CHANNEL, chat["id"], "restore")
    assert len(again.sessions(DEMO_CHANNEL)) == 1
    assert not again.session(DEMO_CHANNEL, chat["id"])["pinned"]


def test_trash_is_recoverable_blocks_agent_calls_and_preserves_other_workspace_state(service):
    result = Agent(service).chat(DEMO_CHANNEL, "Show my latest videos")
    chat_id = result["conversation_id"]
    original = service.store.session(DEMO_CHANNEL, chat_id)["messages"]
    before = service.store.rows("SELECT * FROM audit_events")
    cached = service.store.list(DEMO_CHANNEL, "video_cache")
    service.store.manage_session(DEMO_CHANNEL, chat_id, "trash")
    assert not service.store.sessions(DEMO_CHANNEL)
    assert service.store.session_index(DEMO_CHANNEL, folder="trash")["total"] == 1
    with pytest.raises(CliraError) as error:
        Agent(service).chat(DEMO_CHANNEL, "This must not reach any provider", chat_id)
    assert error.value.code == "SESSION_TRASHED"
    with pytest.raises(CliraError):
        service.store.session(DEMO_CHANNEL, chat_id)
    assert service.store.session(DEMO_CHANNEL, chat_id, include_trashed=True)["messages"] == original
    assert service.store.list(DEMO_CHANNEL, "video_cache") == cached
    assert service.store.rows("SELECT * FROM audit_events")[: len(before)] == before
    service.store.manage_session(DEMO_CHANNEL, chat_id, "restore")
    assert service.store.session(DEMO_CHANNEL, chat_id)["messages"] == original
    assert not service.store.session_index(DEMO_CHANNEL, folder="trash")["total"]
    assert len(service.store.sessions(DEMO_CHANNEL)) == 1


def test_active_request_cannot_be_archived_or_trashed(service):
    chat = service.store.new_session(DEMO_CHANNEL)
    service.store.execute(
        "UPDATE session_meta SET activity='running',accessed_at=? WHERE id=?", (now(), chat["id"])
    )
    for action in ["pin", "unpin", "archive", "trash", "restore"]:
        with pytest.raises(CliraError) as error:
            service.store.manage_session(DEMO_CHANNEL, chat["id"], action)
        assert error.value.code == "SESSION_BUSY"
    assert not service.store.setting("session:" + chat["id"], {})


def test_replying_to_archived_chat_restores_it_and_titles_reject_blank_text(service):
    chat = service.store.new_session(DEMO_CHANNEL, "Original title")
    service.store.manage_session(DEMO_CHANNEL, chat["id"], "archive")
    Agent(service).chat(DEMO_CHANNEL, "Show my latest videos", chat["id"])
    assert service.store.session_index(DEMO_CHANNEL)["items"][0]["id"] == chat["id"]
    assert not service.store.session(DEMO_CHANNEL, chat["id"])["archived"]
    with pytest.raises(CliraError):
        service.store.title_session(DEMO_CHANNEL, chat["id"], "   ")
    assert service.store.title_session(DEMO_CHANNEL, chat["id"], "  Renamed  ")["title"] == "Renamed"
