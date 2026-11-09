import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from clira.agent import Agent, GeminiProvider, ModelTurn
from clira.config import CliraError
from clira.service import DEMO_CHANNEL
from clira.storage import encode
from clira.youtube import READ_SCOPES, UPLOAD_SCOPE, GoogleYouTube


def google_adapter(service, handler, scopes=None):
    channel = service.store.channel(DEMO_CHANNEL)
    channel["connection"] = {"secret_ref": "oauth_fixture"}
    service.secrets.put(
        "oauth_fixture",
        {
            "client_id": "fake",
            "client_secret": "fake",
            "token": "TEST_TOKEN_NOT_REAL",
            "refresh_token": "TEST_REFRESH_NOT_REAL",
            "token_uri": "https://oauth2.googleapis.com/token",
            "expiry": (datetime.now(UTC) + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
            "scopes": scopes or READ_SCOPES + [UPLOAD_SCOPE],
        },
    )
    return GoogleYouTube(channel, service.secrets, httpx.Client(transport=httpx.MockTransport(handler)))


def test_wrong_google_channel_blocks_before_mutation(service):
    calls = []

    def handler(request):
        calls.append(request.method)
        return httpx.Response(200, json={"items": [{"id": "WRONG_CHANNEL"}]})

    adapter = google_adapter(service, handler)
    with pytest.raises(CliraError, match="identity"):
        adapter.verify()
    assert calls == ["GET"]


def test_scope_required_before_upload(service):
    adapter = google_adapter(service, lambda request: httpx.Response(200, json={}), READ_SCOPES)
    with pytest.raises(CliraError, match="Reconnect"):
        adapter.token(UPLOAD_SCOPE)


def test_upload_explicit_private_and_session_validation(service):
    observed = []

    def handler(request):
        observed.append(request)
        return httpx.Response(
            200,
            headers={
                "Location": "https://www.googleapis.com/upload/youtube/v3/videos?upload_id=PRIVATE_SESSION"
            },
        )

    adapter = google_adapter(service, handler)
    url = adapter.begin_upload({"snippet": {"title": "Test"}, "status": {"privacyStatus": "private"}}, 123)
    assert json.loads(observed[0].content)["status"]["privacyStatus"] == "private"
    assert observed[0].headers["X-Upload-Content-Length"] == "123"
    assert "upload_id=" in url
    with pytest.raises(CliraError):
        adapter.upload_chunk("https://evil.example/upload", b"", "bytes */123")


def test_upload_308_offset_and_expiration(service):
    responses = iter([httpx.Response(308, headers={"Range": "bytes=0-262143"}), httpx.Response(404)])
    adapter = google_adapter(service, lambda request: next(responses))
    url = "https://www.googleapis.com/upload/youtube/v3/videos?upload_id=SECRET"
    assert adapter.upload_chunk(url, b"", "bytes */500000")["offset"] == 262144
    with pytest.raises(CliraError) as exc:
        adapter.upload_chunk(url, b"", "bytes */500000")
    assert exc.value.code == "RECONCILIATION_REQUIRED" and not exc.value.retryable


def test_google_errors_redact_raw_response(service):
    adapter = google_adapter(
        service, lambda request: httpx.Response(403, json={"error": {"message": "LEAK_THIS_TOKEN"}})
    )
    with pytest.raises(CliraError) as exc:
        adapter.verify()
    assert "LEAK_THIS_TOKEN" not in str(exc.value)


def test_owned_videos_use_playlist_and_filter_wrong_channel(service):
    def handler(request):
        path = request.url.path
        if path.endswith("/channels"):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {"id": DEMO_CHANNEL, "contentDetails": {"relatedPlaylists": {"uploads": "UPLOADS"}}}
                    ]
                },
            )
        if path.endswith("/playlistItems"):
            return httpx.Response(
                200,
                json={
                    "items": [{"contentDetails": {"videoId": "one"}}, {"contentDetails": {"videoId": "two"}}]
                },
            )
        return httpx.Response(
            200,
            json={
                "items": [
                    {"id": "two", "snippet": {"channelId": "WRONG"}},
                    {"id": "one", "snippet": {"channelId": DEMO_CHANNEL}},
                ]
            },
        )

    adapter = google_adapter(service, handler)
    assert [v["id"] for v in adapter.list_videos()] == ["one"]


def test_analytics_empty_is_unavailable_not_zero(service):
    def handler(request):
        if request.url.path.endswith("/channels"):
            return httpx.Response(200, json={"items": [{"id": DEMO_CHANNEL}]})
        assert request.url.params["ids"] == "channel==" + DEMO_CHANNEL
        return httpx.Response(200, json={"columnHeaders": [{"name": "views"}], "rows": []})

    report = google_adapter(service, handler).report()
    assert report["freshness"] == "unavailable" and report["metrics"] == {}


def test_token_refresh_persists_only_to_secret_store(service, monkeypatch):
    adapter = google_adapter(service, lambda request: httpx.Response(200, json={}))
    data = service.secrets.get("oauth_fixture")
    data["expiry"] = "2000-01-01T00:00:00Z"
    service.secrets.put("oauth_fixture", data)
    from google.oauth2.credentials import Credentials

    def refresh(creds, request):
        creds.token = "REFRESHED_SECRET"
        creds.expiry = datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1)

    monkeypatch.setattr(Credentials, "refresh", refresh)
    assert adapter.token() == "REFRESHED_SECRET"
    assert service.secrets.get("oauth_fixture")["token"] == "REFRESHED_SECRET"
    assert "REFRESHED_SECRET" not in json.dumps(service.store.rows("SELECT * FROM channels"))


def test_revoked_token_produces_auth_required(service, monkeypatch):
    from google.auth.exceptions import RefreshError
    from google.oauth2.credentials import Credentials

    adapter = google_adapter(service, lambda request: httpx.Response(200, json={}))
    data = service.secrets.get("oauth_fixture")
    data["expiry"] = "2000-01-01T00:00:00Z"
    service.secrets.put("oauth_fixture", data)

    def refresh(creds, request):
        raise RefreshError("SENSITIVE_PROVIDER_TEXT")

    monkeypatch.setattr(Credentials, "refresh", refresh)
    with pytest.raises(CliraError) as exc:
        adapter.token()
    assert exc.value.code == "AUTH_REQUIRED" and "SENSITIVE" not in str(exc.value)


class ResumableFake:
    source = "youtube_data_api"

    def __init__(self, payload):
        self.payload = payload
        self.started = 0
        self.uploaded = False
        self.fail = True
        self.status_queries = 0

    def verify(self):
        return {"id": DEMO_CHANNEL}

    def begin_upload(self, payload, size):
        self.started += 1
        assert payload["status"]["privacyStatus"] == "private"
        return "https://www.googleapis.com/upload/youtube/v3/videos?upload_id=TEST_SECRET_SESSION"

    def upload_chunk(self, session, content, content_range):
        if not content:
            self.status_queries += 1
            return {"video": self.video("REMOTE_VIDEO")} if self.uploaded else {"offset": 0}
        self.uploaded = True
        if self.fail:
            self.fail = False
            raise CliraError(
                "UPLOAD_INTERRUPTED", "Simulated lost response after server accepted bytes", True
            )
        return {"video": self.video("REMOTE_VIDEO")}

    def video(self, remote_id):
        return {
            "id": remote_id,
            "snippet": {**self.payload["body"]["snippet"], "channelId": DEMO_CHANNEL},
            "status": {"privacyStatus": "private"},
        }


def test_interrupted_upload_reconciles_same_session_and_no_duplicate(service, prepared, monkeypatch):
    service.policy.decide(DEMO_CHANNEL, prepared["approval_id"], True)
    payload = service.job(DEMO_CHANNEL, prepared["job_id"])["payload"]
    adapter = ResumableFake(payload)
    monkeypatch.setattr(service, "adapter", lambda channel_id: adapter)
    first = service.execute_job(DEMO_CHANNEL, prepared["job_id"])
    assert first["error"]["code"] == "UPLOAD_INTERRUPTED"
    assert service.job(DEMO_CHANNEL, prepared["job_id"])["state"] == "FAILED_RETRYABLE"
    service.store.execute("UPDATE jobs SET next_run_at=NULL WHERE id=?", (prepared["job_id"],))
    result = service.execute_job(DEMO_CHANNEL, prepared["job_id"])
    assert result["ok"] and result["data"]["video_id"] == "REMOTE_VIDEO"
    assert adapter.started == 1 and adapter.status_queries == 2
    assert "TEST_SECRET_SESSION" not in encode(service.store.rows("SELECT * FROM jobs"))
    assert service.secrets.get("session_" + prepared["job_id"])["url"].endswith("TEST_SECRET_SESSION")


def test_ambiguous_session_init_never_retried_blindly(service, prepared, monkeypatch):
    service.policy.decide(DEMO_CHANNEL, prepared["approval_id"], True)
    adapter = ResumableFake(service.job(DEMO_CHANNEL, prepared["job_id"])["payload"])

    def fail(*args):
        raise httpx.ReadTimeout("SESSION_URL_MUST_NOT_LEAK")

    adapter.begin_upload = fail
    monkeypatch.setattr(service, "adapter", lambda channel_id: adapter)
    result = service.execute_job(DEMO_CHANNEL, prepared["job_id"])
    assert result["error"]["code"] == "RECONCILIATION_REQUIRED"
    assert service.job(DEMO_CHANNEL, prepared["job_id"])["state"] == "RECOVERY_REQUIRED"
    assert not service.execute_job(DEMO_CHANNEL, prepared["job_id"])["ok"]


def test_comment_timeout_requires_reconciliation(service, monkeypatch):
    request = service.policy.prepare(
        DEMO_CHANNEL, "post_reply", {"comment_id": "comment", "text": "Exact reply"}
    )
    service.policy.decide(DEMO_CHANNEL, request["approval_id"], True)

    class Fake:
        source = "youtube_data_api"

        def verify(self):
            return {"id": DEMO_CHANNEL}

        def post_reply(self, *args):
            raise CliraError("GOOGLE_API_ERROR", "HTTP 503", True)

    monkeypatch.setattr(service, "adapter", lambda channel_id: Fake())
    result = service.execute_job(DEMO_CHANNEL, request["job_id"])
    assert not result["ok"] and service.job(DEMO_CHANNEL, request["job_id"])["state"] == "RECOVERY_REQUIRED"


def test_gemini_mock_transport_and_budget(service, monkeypatch):
    service.config.allow_model_calls = True
    service.config.max_model_calls_day = 1
    monkeypatch.setenv("GEMINI_API_KEY", "FAKE_TEST_KEY")

    def handler(request):
        body = json.loads(request.content)
        assert request.headers["x-goog-api-key"] == "FAKE_TEST_KEY"
        assert body["tools"][0]["functionDeclarations"][0]["parametersJsonSchema"]
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"role": "model", "parts": [{"text": "Model fixture response"}]}}]
            },
        )

    provider = GeminiProvider(
        service.config, service.store, httpx.Client(transport=httpx.MockTransport(handler))
    )
    assert "Model fixture" in Agent(service, provider).chat(DEMO_CHANNEL, "hello")["message"]
    with pytest.raises(CliraError, match="cap"):
        Agent(service, provider).chat(DEMO_CHANNEL, "again")


def test_gemini_thought_signatures_and_function_ids_preserved(service):
    class Provider:
        def generate(self, messages, tools, limits):
            if len(messages) == 1:
                return ModelTurn(
                    {
                        "role": "model",
                        "parts": [
                            {
                                "thoughtSignature": "OPAQUE_SIGNATURE",
                                "functionCall": {"name": "channel_overview", "args": {}, "id": "call_123"},
                            }
                        ],
                    }
                )
            assert messages[1]["parts"][0]["thoughtSignature"] == "OPAQUE_SIGNATURE"
            assert messages[2]["parts"][0]["functionResponse"]["id"] == "call_123"
            return ModelTurn({"role": "model", "parts": [{"text": "Verified fixture answer"}]})

    assert Agent(service, Provider()).chat(DEMO_CHANNEL, "overview")["receipts"][0]["ok"]


def test_agent_bounds_many_tool_calls(service):
    class Provider:
        def generate(self, messages, tools, limits):
            return ModelTurn(
                {"role": "model", "parts": [{"functionCall": {"name": "channel_overview", "args": {}}}] * 20}
            )

    result = Agent(service, Provider()).chat(DEMO_CHANNEL, "overview")
    assert sum(1 for r in result["receipts"] if r.get("ok")) == service.config.max_steps
    assert "step limit" in result["message"].lower()
