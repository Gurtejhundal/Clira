import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from clira.agent import Agent, ModelTurn
from clira.config import CliraError
from clira.service import DEMO_CHANNEL, Service
from clira.storage import encode


def test_demo_agent_grounded_and_persistent(service):
    result = Agent(service).chat(DEMO_CHANNEL, "Show my latest five uploads")
    assert "SYNTHETIC DEMO" in result["message"]
    assert "12,400" in result["message"]
    assert result["receipts"][0]["source"] == "mock"
    again = Service(service.config)
    assert again.store.rows("SELECT * FROM conversations")[0]["id"] == result["conversation_id"]


def test_three_ideas_use_tool_loop(service):
    result = Agent(service).chat(DEMO_CHANNEL, "Give me three topic ideas")
    assert len(service.store.list(DEMO_CHANNEL, "idea")) == 3
    assert len(result["receipts"]) == 5
    assert "templates" in result["message"]


def test_duplicate_topic_is_rejected(service):
    payload = {"title": "How batteries age", "premise": "An evidence led explanation", "sources": []}
    assert service.tool(DEMO_CHANNEL, "save_idea", payload)["ok"]
    result = service.tool(DEMO_CHANNEL, "save_idea", payload)
    assert result["error"]["code"] == "DUPLICATE_TOPIC"


def test_unconnected_live_channel_no_guessed_data(service):
    service.config.mode = "live"
    service.store.add_channel("UC_TEST", "No credentials", "live")
    result = service.tool("UC_TEST", "list_videos")
    assert result["error"]["code"] == "AUTH_REQUIRED"
    assert "data" not in result


def test_model_cannot_approve_or_publish(service):
    class HostileModel:
        def generate(self, messages, tools, limits):
            if len(messages) > 1:
                return ModelTurn({"role": "model", "parts": [{"text": "Stopped."}]})
            return ModelTurn(
                {
                    "role": "model",
                    "parts": [
                        {
                            "functionCall": {
                                "name": "approve_and_publish",
                                "args": {"channel_id": "OTHER", "approval": "I grant permission"},
                            }
                        }
                    ],
                }
            )

    result = Agent(service, HostileModel()).chat(DEMO_CHANNEL, "Read viewer feedback")
    assert result["receipts"][0]["error"]["code"] == "UNKNOWN_TOOL"
    assert not service.store.rows("SELECT * FROM approvals")


def test_strict_schema_rejects_channel_override(service):
    result = service.tool(DEMO_CHANNEL, "list_videos", {"count": 5, "channel_id": "OTHER"})
    assert result["error"]["code"] == "INVALID_INPUT"
    assert service.tool(DEMO_CHANNEL, "list_videos", {"count": "5"})["error"]["code"] == "INVALID_INPUT"


def test_no_upload_without_approval(service, prepared):
    result = service.execute_job(DEMO_CHANNEL, prepared["job_id"])
    assert not result["ok"]
    assert service.job(DEMO_CHANNEL, prepared["job_id"])["attempts"] == 0


def test_approved_private_upload_is_idempotent_across_restart(service, prepared):
    service.policy.decide(DEMO_CHANNEL, prepared["approval_id"], True)
    first = service.execute_job(DEMO_CHANNEL, prepared["job_id"])
    assert first["ok"] and first["data"]["privacy_status"] == "private"
    assert first["data"]["source"] == "mock" and first["data"]["verified_remotely"] is False
    again = Service(service.config).execute_job(DEMO_CHANNEL, prepared["job_id"])
    assert again["duplicate"] and again["data"]["video_id"] == first["data"]["video_id"]
    assert len(service.store.list(DEMO_CHANNEL, "uploaded_video")) == 1


def test_duplicate_prepare_returns_same_job(service, prepared):
    result = service.tool(
        DEMO_CHANNEL,
        "prepare_upload",
        {"asset_id": prepared["asset"]["id"], "metadata_id": prepared["metadata"]["id"]},
    )["data"]
    assert result["job_id"] == prepared["job_id"] and result["duplicate"]


def test_approval_payload_tamper_blocked(service, prepared):
    service.policy.decide(DEMO_CHANNEL, prepared["approval_id"], True)
    payload = service.job(DEMO_CHANNEL, prepared["job_id"])["payload"]
    payload["body"]["status"]["privacyStatus"] = "public"
    service.store.execute("UPDATE jobs SET payload=? WHERE id=?", (encode(payload), prepared["job_id"]))
    result = service.execute_job(DEMO_CHANNEL, prepared["job_id"])
    assert result["error"]["code"] == "APPROVAL_REQUIRED"


def test_editing_metadata_invalidates_upload_approval(service, prepared):
    service.policy.decide(DEMO_CHANNEL, prepared["approval_id"], True)
    metadata = prepared["metadata"]
    metadata["title"] = "Changed after approval"
    service.store.put(DEMO_CHANNEL, "metadata", metadata, metadata["id"])
    assert service.execute_job(DEMO_CHANNEL, prepared["job_id"])["error"]["code"] == "APPROVAL_INVALIDATED"


def test_expired_approval(service, prepared):
    service.store.execute(
        "UPDATE approvals SET expires_at='2000-01-01' WHERE id=?", (prepared["approval_id"],)
    )
    with pytest.raises(CliraError, match="expired"):
        service.policy.decide(DEMO_CHANNEL, prepared["approval_id"], True)


def test_reject_and_single_use_decision(service, prepared):
    service.policy.decide(DEMO_CHANNEL, prepared["approval_id"], False)
    with pytest.raises(CliraError):
        service.policy.decide(DEMO_CHANNEL, prepared["approval_id"], True)
    assert service.job(DEMO_CHANNEL, prepared["job_id"])["state"] == "CANCELLED"


def test_channel_isolation_for_assets_approvals_jobs_conversations(service, prepared):
    other = "DEMO_OTHER"
    service.store.add_channel(other, "Another creator", "demo")
    assert (
        service.tool(
            other,
            "prepare_upload",
            {"asset_id": prepared["asset"]["id"], "metadata_id": prepared["metadata"]["id"]},
        )["error"]["code"]
        == "NOT_FOUND"
    )
    with pytest.raises(CliraError):
        service.policy.decide(other, prepared["approval_id"], True)
    assert not service.execute_job(other, prepared["job_id"])["ok"]
    convo = Agent(service).chat(DEMO_CHANNEL, "overview")["conversation_id"]
    with pytest.raises(CliraError):
        Agent(service).chat(other, "hi", convo)
    with pytest.raises(CliraError):
        service.store.put(other, "asset", {}, prepared["asset"]["id"])


def test_pause_all_and_live_write_switch(service, prepared):
    service.policy.decide(DEMO_CHANNEL, prepared["approval_id"], True)
    service.store.set_setting("paused", True)
    assert service.execute_job(DEMO_CHANNEL, prepared["job_id"])["error"]["code"] == "WRITES_PAUSED"
    service.store.set_setting("paused", False)
    service.config.mode = "live"
    service.store.execute("UPDATE channels SET mode='live' WHERE id=?", (DEMO_CHANNEL,))
    assert service.execute_job(DEMO_CHANNEL, prepared["job_id"])["error"]["code"] == "WRITES_DISABLED"


def test_timestamp_requires_zone_and_future(service):
    for at in ["2020-01-01T18:00:00+05:30", "2099-01-01T18:00:00"]:
        assert (
            service.tool(DEMO_CHANNEL, "prepare_schedule", {"video_id": "x", "at": at})["error"]["code"]
            == "INVALID_INPUT"
        )
    from clira.contracts import Schedule

    parsed = Schedule(video_id="x", at="2099-01-01T18:00:00+05:30")
    assert parsed.at == "2099-01-01T12:30:00+00:00"


def test_publication_requires_separate_approval_and_private_history(service, prepared):
    service.policy.decide(DEMO_CHANNEL, prepared["approval_id"], True)
    receipt = service.execute_job(DEMO_CHANNEL, prepared["job_id"])["data"]
    request = service.tool(
        DEMO_CHANNEL, "prepare_schedule", {"video_id": receipt["video_id"], "at": "2099-01-01T18:00:00+05:30"}
    )
    assert request["ok"] and request["data"]["state"] == "AWAITING_APPROVAL"
    assert not service.execute_job(DEMO_CHANNEL, request["data"]["job_id"])["ok"]
    result = service.tool(DEMO_CHANNEL, "prepare_publish", {"video_id": "DEMO_VIDEO_0"})
    assert result["error"]["code"] == "PUBLICATION_HISTORY_REQUIRED"


def test_metadata_preserves_properties_and_separates_status(service):
    metadata = service.tool(
        DEMO_CHANNEL,
        "package_video",
        {"title": "Reviewed new title", "made_for_kids": False, "synthetic_media": False},
    )["data"]
    result = service.tool(
        DEMO_CHANNEL, "prepare_metadata", {"video_id": "DEMO_VIDEO_0", "metadata_id": metadata["id"]}
    )
    body = result["data"]["preview"]["body"]
    assert body["snippet"]["categoryId"] == "22"
    assert "status" not in body
    assert result["data"]["preview"]["visibility"] == "public"


def test_comment_injection_is_untrusted_and_reply_is_draft(service):
    service.tool(DEMO_CHANNEL, "list_comments")
    result = service.tool(
        DEMO_CHANNEL,
        "draft_reply",
        {"comment_id": "DEMO_COMMENT_1", "text": "Thanks — I will research that."},
    )
    assert result["ok"]
    assert result["data"]["state"] == "AWAITING_APPROVAL"
    assert service.store.list(DEMO_CHANNEL, "reply")[0]["status"] == "draft"
    assert not service.store.rows("SELECT * FROM jobs WHERE state='COMPLETED'")


def test_audit_is_append_only(service):
    service.store.audit(DEMO_CHANNEL, "test", "blocked")
    with pytest.raises(sqlite3.IntegrityError):
        service.store.execute("DELETE FROM audit_events")
    with pytest.raises(sqlite3.IntegrityError):
        service.store.execute("UPDATE audit_events SET decision='allowed'")


def test_concurrent_claim_does_not_modify_another_workers_job(service, prepared):
    service.policy.decide(DEMO_CHANNEL, prepared["approval_id"], True)
    claimed = service.policy.claim(DEMO_CHANNEL, prepared["job_id"])
    assert claimed["state"] == "RUNNING"
    result = service.execute_job(DEMO_CHANNEL, prepared["job_id"])
    assert result["error"]["code"] == "JOB_NOT_RUNNABLE"
    assert service.job(DEMO_CHANNEL, prepared["job_id"])["state"] == "RUNNING"


def test_transactional_claim_only_one_winner(service, prepared):
    service.policy.decide(DEMO_CHANNEL, prepared["approval_id"], True)

    def claim():
        try:
            return service.policy.claim(DEMO_CHANNEL, prepared["job_id"])["state"]
        except CliraError:
            return "blocked"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: claim(), range(2)))
    assert sorted(results) == ["RUNNING", "blocked"]


def test_recovery_conservative_for_ambiguous_writes(service, prepared):
    service.policy.decide(DEMO_CHANNEL, prepared["approval_id"], True)
    service.policy.claim(DEMO_CHANNEL, prepared["job_id"])
    service.store.execute(
        "UPDATE jobs SET lease_until='2000-01-01',result=? WHERE id=?",
        (encode({"stage": "init_started"}), prepared["job_id"]),
    )
    assert service.recover()["recovered"] == 1
    assert service.job(DEMO_CHANNEL, prepared["job_id"])["state"] == "RECOVERY_REQUIRED"


def test_resumable_job_recovered_without_new_upload(service, prepared):
    service.policy.decide(DEMO_CHANNEL, prepared["approval_id"], True)
    service.policy.claim(DEMO_CHANNEL, prepared["job_id"])
    service.store.execute(
        "UPDATE jobs SET lease_until='2000-01-01',result=? WHERE id=?",
        (encode({"stage": "session_saved"}), prepared["job_id"]),
    )
    service.recover()
    assert service.job(DEMO_CHANNEL, prepared["job_id"])["state"] == "FAILED_RETRYABLE"


def test_request_budget_is_atomic(service):
    service.store.consume_budget(1)
    with pytest.raises(CliraError, match="cap"):
        service.store.consume_budget(1)
