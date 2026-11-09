from clira.service import DEMO_CHANNEL


def test_expired_never_started_upload_can_be_reprepared(service, prepared):
    service.store.execute(
        "UPDATE approvals SET expires_at='2000-01-01' WHERE id=?", (prepared["approval_id"],)
    )
    new = service.tool(
        DEMO_CHANNEL,
        "prepare_upload",
        {"asset_id": prepared["asset"]["id"], "metadata_id": prepared["metadata"]["id"]},
    )["data"]
    assert new["job_id"] == prepared["job_id"] and new["approval_id"] != prepared["approval_id"]
    assert (
        service.store.rows("SELECT status FROM approvals WHERE id=?", (prepared["approval_id"],))[0]["status"]
        == "SUPERSEDED"
    )
    assert service.job(DEMO_CHANNEL, new["job_id"])["state"] == "AWAITING_APPROVAL"


def test_edit_never_reuses_existing_consent(service, prepared):
    service.policy.decide(DEMO_CHANNEL, prepared["approval_id"], True)
    metadata = prepared["metadata"]
    metadata["title"] = "An entirely new package"
    service.store.put(DEMO_CHANNEL, "metadata", metadata, metadata["id"])
    new = service.tool(
        DEMO_CHANNEL, "prepare_upload", {"asset_id": prepared["asset"]["id"], "metadata_id": metadata["id"]}
    )["data"]
    assert new["job_id"] == prepared["job_id"] and new["approval_id"] != prepared["approval_id"]
    assert service.job(DEMO_CHANNEL, new["job_id"])["state"] == "AWAITING_APPROVAL"
    assert not service.execute_job(DEMO_CHANNEL, new["job_id"])["ok"]


def test_completed_upload_never_reprepared_into_another_upload(service, prepared):
    service.policy.decide(DEMO_CHANNEL, prepared["approval_id"], True)
    service.execute_job(DEMO_CHANNEL, prepared["job_id"])
    metadata = prepared["metadata"]
    metadata["title"] = "Different metadata"
    service.store.put(DEMO_CHANNEL, "metadata", metadata, metadata["id"])
    result = service.tool(
        DEMO_CHANNEL, "prepare_upload", {"asset_id": prepared["asset"]["id"], "metadata_id": metadata["id"]}
    )["data"]
    assert result["duplicate"] and result["state"] == "COMPLETED"


def test_weekly_digest_has_disjoint_ranges_and_units(service):
    result = service.tool(DEMO_CHANNEL, "weekly_digest")["data"]
    assert result["previous"]["range_end"] < result["current"]["range_start"]
    assert "estimatedMinutesWatched" in result["changes"]
    assert result["current"]["freshness"] == "mock"


def test_public_research_demo_does_not_invent_sources(service):
    result = service.tool(DEMO_CHANNEL, "research_videos", {"query": "battery aging"})
    assert result["ok"] and result["data"]["examples"] == []


def test_tool_contracts_include_input_output_scope_and_permission():
    from clira.contracts import tool_contracts

    for contract in tool_contracts():
        assert {
            "input_schema",
            "output_schema",
            "oauth_scopes",
            "permission",
            "idempotency",
            "quota_class",
            "timeout_seconds",
        } <= contract.keys()


def test_owner_renewal_preserves_upload_session_and_job(service, prepared):
    from clira.storage import encode

    service.policy.decide(DEMO_CHANNEL, prepared["approval_id"], True)
    service.policy.claim(DEMO_CHANNEL, prepared["job_id"])
    progress = {"stage": "session_saved"}
    service.store.execute(
        "UPDATE jobs SET state='FAILED_RETRYABLE',result=? WHERE id=?", (encode(progress), prepared["job_id"])
    )
    fresh = service.policy.renew(DEMO_CHANNEL, prepared["approval_id"])
    assert fresh["approval_id"] != prepared["approval_id"]
    assert fresh["job_id"] == prepared["job_id"]
    assert service.job(DEMO_CHANNEL, prepared["job_id"])["result"] == progress
    assert service.job(DEMO_CHANNEL, prepared["job_id"])["state"] == "AWAITING_APPROVAL"


def test_owner_cannot_renew_unknown_outcome(service, prepared):
    import pytest

    from clira.config import CliraError

    service.store.execute("UPDATE jobs SET state='RECOVERY_REQUIRED' WHERE id=?", (prepared["job_id"],))
    with pytest.raises(CliraError):
        service.policy.renew(DEMO_CHANNEL, prepared["approval_id"])
