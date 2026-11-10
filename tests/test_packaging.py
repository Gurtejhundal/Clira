import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from clira.agent import Agent
from clira.api import create_app
from clira.config import CliraError
from clira.packaging import captions, chapters
from clira.service import DEMO_CHANNEL
from clira.youtube import GoogleYouTube


def imported(service, kind="thumbnail", asset_id=None):
    path = service.config.import_dir / ("thumb.png" if kind == "thumbnail" else "speech.srt")
    if kind == "thumbnail":
        Image.new("RGB", (1280, 720), "#252B24").save(path)
    else:
        path.write_text("1\n00:00:00,000 --> 00:00:00,900\nOriginal test caption.\n")
    result = service.tool(
        DEMO_CHANNEL,
        "import_package_asset",
        {
            "path": str(path),
            "type": kind,
            "asset_id": asset_id,
            "rights": "original",
            "rights_evidence": "Original test fixture",
            "creative_reviewed": True,
        },
    )
    assert result["ok"], result
    return result["data"]


def test_actual_thumbnail_and_caption_preview(service, prepared):
    thumbnail = imported(service)
    caption = imported(service, "captions", prepared["asset"]["id"])
    assert caption["cues"][0]["end"] == 0.9 and thumbnail["width"] == 1280
    client = TestClient(create_app(service))
    result = client.get("/api/preview/" + DEMO_CHANNEL + "/" + thumbnail["id"])
    assert result.status_code == 200 and result.headers["content-type"] == "image/png"
    assert result.content.startswith(b"\x89PNG")
    service.store.add_channel("DEMO_OTHER", "Other", "demo")
    assert client.get("/api/preview/DEMO_OTHER/" + thumbnail["id"]).status_code == 400
    assert (
        service.tool(
            "DEMO_OTHER",
            "prepare_attachment",
            {"video_id": "DEMO_VIDEO_0", "package_asset_id": thumbnail["id"]},
        )["error"]["code"]
        == "NOT_FOUND"
    )


def test_template_is_real_but_needs_owner_review(service):
    result = service.tool(DEMO_CHANNEL, "thumbnail_template", {"text": "Original battery guide"})
    image = result["data"]
    with Image.open(image["path"]) as actual:
        assert actual.size == (1280, 720)
    args = {"video_id": "DEMO_VIDEO_0", "package_asset_id": image["id"]}
    assert service.tool(DEMO_CHANNEL, "prepare_attachment", args)["error"]["code"] == "RIGHTS_REVIEW_REQUIRED"
    review = {
        "package_asset_id": image["id"],
        "rights": "original",
        "rights_evidence": "Original owner-selected text",
        "creative_reviewed": True,
    }
    assert (
        service.tool(DEMO_CHANNEL, "review_package_asset", review, actor="agent")["error"]["code"]
        == "OWNER_REVIEW_REQUIRED"
    )
    assert "review_package_asset" not in [d["name"] for d in Agent.declarations()]
    assert service.tool(DEMO_CHANNEL, "review_package_asset", review)["ok"]
    approval = service.tool(DEMO_CHANNEL, "prepare_attachment", args)["data"]
    assert not service.execute_job(DEMO_CHANNEL, approval["job_id"])["ok"]
    service.policy.decide(DEMO_CHANNEL, approval["approval_id"], True)
    assert service.execute_job(DEMO_CHANNEL, approval["job_id"])["data"]["source"] == "mock"


def test_package_binds_bytes_and_captions_edit_requires_review(service, prepared):
    image = imported(service)
    caption = imported(service, "captions", prepared["asset"]["id"])
    metadata = service.tool(
        DEMO_CHANNEL,
        "package_video",
        {
            "title": "Original fixture",
            "description": "A factual owner draft",
            "hashtags": ["#Original"],
            "asset_id": prepared["asset"]["id"],
            "thumbnail_id": image["id"],
            "captions_id": caption["id"],
            "made_for_kids": False,
            "synthetic_media": False,
        },
    )["data"]
    assert "#Original" in metadata["description"] and len(metadata["packaging_manifest"]) == 2
    request = service.tool(
        DEMO_CHANNEL, "prepare_upload", {"asset_id": prepared["asset"]["id"], "metadata_id": metadata["id"]}
    )["data"]
    assert len(request["preview"]["packaging_manifest"]) == 2
    service.policy.decide(DEMO_CHANNEL, request["approval_id"], True)
    path = Path(image["path"])
    path.chmod(0o600)
    path.write_bytes(b"changed")
    assert service.execute_job(DEMO_CHANNEL, request["job_id"])["error"]["code"] == "ASSET_CHANGED"
    edited = service.tool(
        DEMO_CHANNEL,
        "edit_captions",
        {
            "package_asset_id": caption["id"],
            "text": "WEBVTT\n\n00:00.000 --> 00:00.800\nEdited original words.\n",
        },
    )["data"]
    assert edited["id"] != caption["id"] and not edited["creative_reviewed"]
    assert service.store.get(DEMO_CHANNEL, caption["id"])["text"] != edited["text"]


@pytest.mark.parametrize(
    "text",
    [
        "Untimed transcript only",
        "1\n00:00:01,000 --> 00:00:00,500\nBackwards",
        "1\n00:60:00,000 --> 00:61:00,000\nInvalid",
        "1\n00:00:00,000 --> 00:00:02,000\nToo long",
        "1\n00:00:00,000 --> 00:00:00,500\n<script>injection</script>",
        "1\n00:00:00,000 --> 00:00:00,700\nOne\n\n2\n00:00:00,600 --> 00:00:00,900\nOverlap",
    ],
)
def test_bad_captions(text):
    with pytest.raises(CliraError):
        captions(text, 1)


def test_chapters_and_metadata_rules(service):
    data = [
        {"seconds": 0, "title": "Start"},
        {"seconds": 10, "title": "Middle"},
        {"seconds": 20, "title": "End"},
    ]
    assert chapters(data, 30) == "00:00 Start\n00:10 Middle\n00:20 End"
    with pytest.raises(CliraError):
        chapters(data, 8)
    with pytest.raises(CliraError):
        chapters(data[1:], 40)
    base = {"title": "A title", "made_for_kids": False, "synthetic_media": False}
    for extra in [
        {"hashtags": ["#bad space"]},
        {"description": "é" * 3000},
        {"chapters": data},
        {"title": "<bad>"},
    ]:
        assert not service.tool(DEMO_CHANNEL, "package_video", {**base, **extra})["ok"]


@pytest.mark.parametrize("target_format", ["srt", "vtt"])
def test_caption_format_edit_preview_has_correct_mime(service, target_format):
    original = imported(service, "captions")
    vtt = "WEBVTT\n\n00:00.000 --> 00:00.800\nAn edited original line.\n"
    srt = "1\n00:00:00,000 --> 00:00:00,800\nAn edited original line.\n"

    def edit(record, text):
        result = service.tool(DEMO_CHANNEL, "edit_captions", {"package_asset_id": record["id"], "text": text})
        assert result["ok"], result
        return result["data"]

    # Exercise both SRT -> VTT and VTT -> SRT, preserving the original asset.
    previous = original if target_format == "vtt" else edit(original, vtt)
    edited = edit(previous, vtt if target_format == "vtt" else srt)
    mime = "text/vtt" if target_format == "vtt" else "application/x-subrip"
    assert edited["format"] == target_format and edited["mime"] == mime
    assert Path(edited["path"]).suffix == "." + target_format
    assert not edited["creative_reviewed"] and edited["id"] != previous["id"]
    client = TestClient(create_app(service))
    response = client.get(f"/api/preview/{DEMO_CHANNEL}/{edited['id']}")
    assert response.status_code == 200
    assert response.headers["content-type"].split(";")[0] == mime
    assert response.text == edited["text"]
    assert Path(original["path"]).read_text() == original["text"]


def test_tag_limit_counts_youtube_quotes_and_separators(service):
    base = {"title": "A factual title", "made_for_kids": False, "synthetic_media": False}
    # Old accounting accepted these 400 characters, but YouTube counts 499 with quotes.
    rejected = service.tool(DEMO_CHANNEL, "package_video", {**base, "tags": ["foo bar"] * 50})
    assert not rejected["ok"]
    assert service.tool(DEMO_CHANNEL, "package_video", {**base, "tags": ["foo bar"] * 45})["ok"]
    assert not service.tool(DEMO_CHANNEL, "package_video", {**base, "tags": [" "]})["ok"]


def test_import_rejects_untrusted_paths_bytes_and_attestation(service, tmp_path):
    outside = tmp_path / "outside.png"
    Image.new("RGB", (1280, 720)).save(outside)
    assert not service.tool(
        DEMO_CHANNEL, "import_package_asset", {"type": "thumbnail", "path": str(outside)}
    )["ok"]
    local = service.config.import_dir / "bad.png"
    local.write_bytes(b"bad")
    assert not service.tool(DEMO_CHANNEL, "import_package_asset", {"type": "thumbnail", "path": str(local)})[
        "ok"
    ]
    result = service.tool(
        DEMO_CHANNEL,
        "import_package_asset",
        {"type": "thumbnail", "path": str(local), "rights": "original"},
        actor="agent",
    )
    assert result["error"]["code"] == "OWNER_REVIEW_REQUIRED"


def adapter(service, handler):
    channel = service.store.channel(DEMO_CHANNEL)
    channel["connection"] = {"secret_ref": "fixture"}
    result = GoogleYouTube(channel, service.secrets, httpx.Client(transport=httpx.MockTransport(handler)))
    result.token = lambda scope=None: "fixture-secret"
    return result


@pytest.mark.parametrize("operation", ["thumbnail", "captions"])
def test_official_attachment_wire_format(service, operation):
    requests = []

    def handler(request):
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "owned",
                            "snippet": {"channelId": DEMO_CHANNEL},
                            "status": {"privacyStatus": "private"},
                        }
                    ]
                },
            )
        if operation == "thumbnail":
            assert str(request.url).startswith("https://www.googleapis.com/upload/youtube/v3/thumbnails/set")
            assert request.headers["content-type"] == "image/png" and request.content == b"png-data"
            return httpx.Response(200, json={"items": [{"default": {"url": "https://i.ytimg.com/example"}}]})
        assert request.url.params["uploadType"] == "multipart"
        assert request.headers["content-type"].startswith("multipart/related; boundary=")
        assert b'"videoId": "owned"' in request.content and b'"isDraft": true' in request.content
        assert b"00:00:00,000" in request.content
        return httpx.Response(200, json={"id": "track", "snippet": {"status": "syncing"}})

    client = adapter(service, handler)
    if operation == "thumbnail":
        client.set_thumbnail("owned", b"png-data", "image/png")
    else:
        client.insert_captions("owned", b"1\n00:00:00,000 --> 00:00:00,900\nTest", "en", "Manual", True)
    assert len(requests) == 2


@pytest.mark.parametrize("status", [401, 403, 429, 503])
def test_attachment_api_errors_sanitized(service, status):
    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json={"items": [{"snippet": {"channelId": DEMO_CHANNEL}}]})
        return httpx.Response(status, text="fixture-secret-sensitive")

    client = adapter(service, handler)
    with pytest.raises(CliraError) as exc:
        client.set_thumbnail("owned", b"data", "image/png")
    assert "sensitive" not in str(exc.value)
    assert exc.value.retryable == (status in {429, 503})


def test_unknown_caption_outcome_never_blindly_replayed(service, monkeypatch):
    caption = imported(service, "captions")
    request = service.tool(
        DEMO_CHANNEL, "prepare_attachment", {"video_id": "DEMO_VIDEO_0", "package_asset_id": caption["id"]}
    )["data"]
    service.policy.decide(DEMO_CHANNEL, request["approval_id"], True)

    class Interrupted:
        def verify(self):
            return {"id": DEMO_CHANNEL}

        def video(self, video_id):
            return {"status": {"privacyStatus": "private"}}

        def insert_captions(self, *args):
            raise httpx.ReadTimeout("sensitive transport")

    monkeypatch.setattr(service, "adapter", lambda channel: Interrupted())
    result = service.execute_job(DEMO_CHANNEL, request["job_id"])
    assert result["error"]["code"] == "RECONCILIATION_REQUIRED"
    assert service.job(DEMO_CHANNEL, request["job_id"])["state"] == "RECOVERY_REQUIRED"
    assert not service.execute_job(DEMO_CHANNEL, request["job_id"])["ok"]
    assert "sensitive" not in json.dumps(service.store.rows("SELECT * FROM jobs"))
