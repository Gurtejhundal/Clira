import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from clira.api import create_app
from clira.config import CliraError
from clira.media import ManualProductionProvider
from clira.service import DEMO_CHANNEL


@pytest.mark.parametrize("kind", ["missing", "empty", "garbage", "outside", "symlink"])
def test_invalid_import_never_starts_upload(service, tmp_path, kind):
    path = service.config.import_dir / "invalid.mp4"
    if kind == "empty":
        path.write_bytes(b"")
    if kind == "garbage":
        path.write_bytes(b"not a video")
    if kind == "outside":
        path = tmp_path / "outside.mp4"
        path.write_bytes(b"bad")
    if kind == "symlink":
        target = tmp_path / "target.mp4"
        target.write_bytes(b"bad")
        path.symlink_to(target)
    result = service.tool(DEMO_CHANNEL, "import_video", {"path": str(path)})
    assert not result["ok"]
    assert not service.store.rows("SELECT * FROM jobs")


def test_rights_and_creative_gate(service, sample_mp4):
    target = service.config.import_dir / "sample.mp4"
    shutil.copyfile(sample_mp4, target)
    asset = service.tool(DEMO_CHANNEL, "import_video", {"path": str(target), "rights": "unlicensed"})["data"]
    metadata = service.tool(
        DEMO_CHANNEL, "package_video", {"title": "A sample", "made_for_kids": False, "synthetic_media": False}
    )["data"]
    result = service.tool(
        DEMO_CHANNEL, "prepare_upload", {"asset_id": asset["id"], "metadata_id": metadata["id"]}
    )
    assert result["error"]["code"] == "RIGHTS_REVIEW_REQUIRED"


def test_model_cannot_attest_rights(service):
    result = service.tool(
        DEMO_CHANNEL,
        "import_video",
        {"path": "/some.mp4", "rights": "original", "rights_evidence": "I own it", "creative_reviewed": True},
        actor="agent",
    )
    assert result["error"]["code"] == "OWNER_REVIEW_REQUIRED"


def test_managed_copy_and_tampering(service, prepared):
    original = service.config.import_dir / "sample.mp4"
    original.write_bytes(b"changed original")
    assert Path(prepared["asset"]["path"]).stat().st_size == prepared["asset"]["size"]
    path = Path(prepared["asset"]["path"])
    path.chmod(0o600)
    path.write_bytes(b"changed managed copy")
    service.policy.decide(DEMO_CHANNEL, prepared["approval_id"], True)
    assert service.execute_job(DEMO_CHANNEL, prepared["job_id"])["error"]["code"] == "ASSET_CHANGED"


def test_missing_renderer_does_not_block_manual_import(service, prepared):
    provider = ManualProductionProvider(service.store, DEMO_CHANNEL)
    brief = provider.submit({"script": "A script", "channel_id": DEMO_CHANNEL})
    assert provider.status(brief["external_job_id"])["status"] == "awaiting_manual_video"
    with pytest.raises(CliraError):
        provider.collect(brief["external_job_id"])
    assert prepared["asset"]["qc"]["duration_seconds"] > 0


def test_api_origin_csrf_host_and_no_secret_export(service):
    client = TestClient(create_app(service))
    session = client.get("/api/session").json()
    payload = {"channel_id": DEMO_CHANNEL, "tool": "list_videos", "arguments": {}}
    assert client.post("/api/tool", json=payload).status_code == 403
    headers = {"X-Clira-Token": session["token"]}
    assert (
        client.post(
            "/api/tool", json=payload, headers={**headers, "Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert client.get("/api/session", headers={"Host": "evil.example"}).status_code == 400
    assert client.post("/api/tool", json=payload, headers=headers).json()["ok"]
    service.secrets.put("test", {"refresh_token": "NEVER_EXPORT_THIS"})
    output = client.get("/api/state/" + DEMO_CHANNEL).text
    assert "NEVER_EXPORT_THIS" not in output and "secret_ref" not in output
    assert "frame-ancestors 'none'" in client.get("/").headers["Content-Security-Policy"]


def test_api_full_approved_simulation(service, prepared):
    client = TestClient(create_app(service))
    headers = {"X-Clira-Token": client.get("/api/session").json()["token"]}
    result = client.post(
        "/api/approvals/" + prepared["approval_id"],
        headers=headers,
        json={"channel_id": DEMO_CHANNEL, "approve": True},
    )
    assert result.status_code == 200
    result = client.post(
        "/api/jobs/" + prepared["job_id"] + "/run", headers=headers, json={"channel_id": DEMO_CHANNEL}
    )
    assert result.json()["data"]["source"] == "mock"


def test_api_validates_profile_timezone(service):
    client = TestClient(create_app(service))
    headers = {"X-Clira-Token": client.get("/api/session").json()["token"]}
    response = client.put(
        "/api/profile/" + DEMO_CHANNEL, headers=headers, json={"niche": "tech", "timezone": "Not/AZone"}
    )
    assert response.status_code == 422


def test_secret_refs_and_permissions(service):
    with pytest.raises(CliraError):
        service.secrets.get("../../outside")
    service.secrets.put("oauth_test", {"token": "private"})
    assert service.secrets.path("oauth_test").stat().st_mode & 0o077 == 0
    assert service.secrets.get("oauth_test")["token"] == "private"
