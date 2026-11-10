import json
import shutil
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from clira.agent import Agent, ModelTurn
from clira.api import create_app
from clira.config import CliraError
from clira.service import DEMO_CHANNEL
from clira.storage import encode
from clira.upload_flow import UploadFlow, UploadReview, UploadStart


@pytest.fixture
def draft(service, sample_mp4):
    path = service.config.import_dir / "chat-video.mp4"
    shutil.copyfile(sample_mp4, path)
    return UploadFlow(service).start(DEMO_CHANNEL, UploadStart(path=str(path)))


def review(draft, **changes):
    values = {
        "channel_id": DEMO_CHANNEL,
        "preview_hash": draft["preview_hash"],
        "copy": draft["copy"],
        "rights": "original",
        "rights_evidence": "Original test video; no third-party material.",
        "creative_reviewed": True,
        "made_for_kids": False,
        "synthetic_media": False,
        "confirmation": "APPROVE PRIVATE UPLOAD",
    }
    values.update(changes)
    return UploadReview(**values)


def test_one_review_creates_and_executes_only_private_job(service, draft):
    assert not service.store.rows("SELECT * FROM approvals")
    assert not service.store.rows("SELECT * FROM jobs")
    result = UploadFlow(service).approve(draft["id"], review(draft))
    assert result["ok"] and result["data"]["privacy_status"] == "private"
    assert result["data"]["source"] == "mock" and not result["data"]["verified_remotely"]
    job = service.job(DEMO_CHANNEL, result["job_id"])
    assert job["state"] == "COMPLETED"
    assert job["payload"]["body"]["status"]["privacyStatus"] == "private"
    with pytest.raises(CliraError, match="already submitted"):
        UploadFlow(service).approve(draft["id"], review(draft))
    assert len(service.store.rows("SELECT * FROM jobs")) == 1


@pytest.mark.parametrize(
    "changes", [{"preview_hash": "wrong"}, {"creative_reviewed": False}, {"rights_evidence": " "}]
)
def test_incomplete_or_changed_preview_cannot_upload(service, draft, changes):
    with pytest.raises(CliraError):
        UploadFlow(service).approve(draft["id"], review(draft, **changes))
    assert not service.store.rows("SELECT * FROM jobs")


def test_concurrent_approval_starts_at_most_one_job(service, draft):
    def run(_):
        try:
            return UploadFlow(service).approve(draft["id"], review(draft))["ok"]
        except CliraError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(run, range(2))) == [False, True]
    assert len(service.store.rows("SELECT * FROM jobs")) == 1


def test_agent_upload_intent_saves_preview_in_shared_session(service, sample_mp4):
    path = service.config.import_dir / "chat-video.mp4"
    shutil.copyfile(sample_mp4, path)
    result = Agent(service).chat(DEMO_CHANNEL, "/upload " + str(path))
    assert "Private upload preview" in result["message"]
    assert result["receipts"][0]["data"]["state"] == "DRAFT"
    messages = json.loads(service.store.rows("SELECT messages FROM conversations")[0]["messages"])
    assert messages[-1]["receipts"][0]["tool"] == "prepare_video_upload"
    assert not service.store.rows("SELECT * FROM approvals")


def test_sampled_frame_model_generates_copy_without_authority(service, sample_mp4):
    path = service.config.import_dir / "chat-video.mp4"
    shutil.copyfile(sample_mp4, path)

    class Provider:
        def generate(self, messages, tools, limits):
            assert tools == []
            assert sum("inlineData" in p for p in messages[0]["parts"]) == 3
            assert "not a transcript" in limits["system"]
            return ModelTurn(
                {
                    "role": "model",
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "title": "Green test film",
                                    "description": "A green test animation.",
                                    "tags": ["test"],
                                    "script_outline": "Draft outline only.",
                                    "content_summary": "Green frame.",
                                }
                            )
                        }
                    ],
                }
            )

    result = UploadFlow(service).start(DEMO_CHANNEL, UploadStart(path=str(path)), Provider())
    assert result["source"] == "gemini_sampled_frames"
    assert not service.store.rows("SELECT * FROM jobs")


def test_chat_attachment_preview_and_channel_isolation(service, sample_mp4):
    client = TestClient(create_app(service))
    headers = {
        "x-clira-token": client.get("/api/session").json()["token"],
        "content-type": "application/octet-stream",
    }
    assert client.post("/api/chat-video/" + DEMO_CHANNEL, content=sample_mp4.read_bytes()).status_code == 403
    attached = client.post(
        "/api/chat-video/" + DEMO_CHANNEL, content=sample_mp4.read_bytes(), headers=headers
    )
    assert attached.status_code == 200
    headers["content-type"] = "application/json"
    result = client.post(
        "/api/chat",
        json={"channel_id": DEMO_CHANNEL, "message": "/upload " + attached.json()["path"]},
        headers=headers,
    )
    assert result.status_code == 200, result.text
    draft = result.json()["receipts"][0]["data"]
    url = "/api/upload-drafts/" + DEMO_CHANNEL + "/" + draft["id"]
    assert client.get(url + "/video").content == sample_mp4.read_bytes()
    service.store.add_channel("OTHER", "Other", "demo")
    assert client.get("/api/upload-drafts/OTHER/" + draft["id"]).status_code == 400
    body = review(draft).model_dump(by_alias=True)
    response = client.post("/api/upload-drafts/" + draft["id"] + "/approve", json=body, headers=headers)
    assert response.status_code == 200 and response.json()["ok"], response.text
    invalid = client.post(
        "/api/chat-video/" + DEMO_CHANNEL,
        content=b"bad",
        headers={**headers, "content-type": "application/octet-stream"},
    )
    assert invalid.status_code == 400


def test_upload_verification_accepts_only_tag_reordering(service, prepared):
    # Exercise the real verification branch using a saved receipt, with no external network.
    job_id = prepared["job_id"]
    payload = service.job(DEMO_CHANNEL, job_id)["payload"]
    payload["body"]["snippet"]["tags"] = ["zeta", "alpha"]
    metadata = service.store.get(DEMO_CHANNEL, payload["metadata_id"], "metadata")
    metadata["tags"] = ["zeta", "alpha"]
    service.store.put(DEMO_CHANNEL, "metadata", metadata, metadata["id"])
    service.store.execute(
        "UPDATE jobs SET result=? WHERE id=?",
        (encode({"stage": "receipt_saved", "video_id": "EXISTING"}), job_id),
    )

    class Remote:
        def video(self, video_id):
            return {
                "id": video_id,
                "status": {"privacyStatus": "private"},
                "snippet": {**payload["body"]["snippet"], "tags": ["alpha", "zeta"]},
            }

    result = service.run_upload(DEMO_CHANNEL, job_id, payload, Remote())
    assert result["video_id"] == "EXISTING" and result["verified_remotely"]
    payload["body"]["snippet"]["title"] = "Changed title"
    metadata["title"] = "Changed title"
    service.store.put(DEMO_CHANNEL, "metadata", metadata, metadata["id"])

    class Changed(Remote):
        def video(self, video_id):
            value = super().video(video_id)
            value["snippet"]["title"] = "Different"
            return value

    with pytest.raises(CliraError, match="metadata differs"):
        service.run_upload(DEMO_CHANNEL, job_id, payload, Changed())


def test_existing_upload_returns_receipt_without_uploading_again(service, draft):
    flow = UploadFlow(service)
    first = flow.approve(draft["id"], review(draft))
    asset = service.store.get(DEMO_CHANNEL, draft["asset_id"], "asset")
    # Start a second review using the original import, not its managed immutable copy.
    path = service.config.import_dir / "chat-video.mp4"
    second = flow.start(DEMO_CHANNEL, UploadStart(path=str(path)))
    result = flow.approve(second["id"], review(second))
    assert result["duplicate"] and result["data"] == first["data"]
    assert len(service.store.rows("SELECT * FROM jobs")) == 1
    assert asset["sha256"] == second["asset_sha256"]


def test_invalid_package_does_not_consume_preview(service, draft):
    body = review(draft)
    body.package.title = "<invalid>"
    with pytest.raises(CliraError, match="angle brackets"):
        UploadFlow(service).approve(draft["id"], body)
    assert service.store.get(DEMO_CHANNEL, draft["id"], "upload_draft")["state"] == "DRAFT"
    assert not service.store.rows("SELECT * FROM jobs")
