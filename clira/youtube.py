import json
import re
from datetime import date, timedelta
from urllib.parse import urlparse

import httpx

from .config import CliraError
from .storage import now

READ_SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]
UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
MANAGE_SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"
DATA_URL = "https://www.googleapis.com/youtube/v3/"


class DemoYouTube:
    source = "mock"

    def __init__(self, channel_id):
        self.channel_id = channel_id

    def verify(self):
        return {
            "id": self.channel_id,
            "snippet": {"title": "Demo creator"},
            "contentDetails": {"relatedPlaylists": {"uploads": "DEMO_UPLOADS"}},
        }

    def list_videos(self, count=5):
        titles = [
            "Why your phone gets slower",
            "What deleting a file really does",
            "Inside a password manager",
            "The hidden cost of notifications",
            "How maps find the fastest route",
        ]
        return [
            {
                "id": f"DEMO_VIDEO_{i}",
                "snippet": {
                    "title": title,
                    "channelId": self.channel_id,
                    "description": "Synthetic demo fixture",
                    "categoryId": "28",
                    "tags": ["technology"],
                    "publishedAt": f"2026-11-0{8 - i}T12:00:00Z",
                },
                "status": {"privacyStatus": "public"},
                "statistics": {"viewCount": str([12400, 8200, 6100, 3800, 2900][i])},
                "contentDetails": {"duration": "PT45S"},
            }
            for i, title in enumerate(titles)
        ][:count]

    def video(self, video_id):
        for video in self.list_videos():
            if video["id"] == video_id:
                return video
        if video_id.startswith("MOCK_"):
            return {
                "id": video_id,
                "snippet": {"channelId": self.channel_id, "title": "Demo private upload", "categoryId": "22"},
                "status": {"privacyStatus": "private", "uploadStatus": "processed"},
            }
        raise CliraError("NOT_FOUND", "Demo video not found.")

    def report(self, days=28, offset_days=0):
        end = date.today() - timedelta(days=2 + offset_days)
        return {
            "range_start": str(end - timedelta(days=days - 1)),
            "range_end": str(end),
            "freshness": "mock",
            "units": {"views": "views", "estimatedMinutesWatched": "minutes"},
            "metrics": {
                "views": 33400,
                "estimatedMinutesWatched": 16300,
                "averageViewDuration": 29,
                "subscribersGained": 142,
            },
            "warnings": ["Entirely synthetic fixtures. These are not your channel's numbers."],
        }

    def comments(self, count=5):
        return [
            {
                "id": "DEMO_COMMENT_1",
                "video_id": "DEMO_VIDEO_0",
                "text": "Could you explain why batteries age?",
                "trust": "untrusted_viewer_content",
            }
        ][:count]

    def research(self, query, count=5):
        return {
            "query": query,
            "examples": [],
            "warnings": [
                "Public research is unavailable in offline demo mode; no trend evidence was invented."
            ],
        }


class GoogleYouTube:
    source = "youtube_data_api"

    def __init__(self, channel, secrets, client=None):
        self.channel, self.secrets = channel, secrets
        self.ref = channel["connection"].get("secret_ref")
        if not self.ref:
            raise CliraError("AUTH_REQUIRED", "Connect this channel with clira connect.")
        self.client = client or httpx.Client(timeout=60, follow_redirects=False)

    def token(self, scope=None):
        from google.auth.exceptions import RefreshError
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        data = self.secrets.get(self.ref)
        if scope and scope not in data.get("scopes", []):
            raise CliraError("SCOPE_REQUIRED", "Reconnect with the required capability using clira connect.")
        creds = Credentials.from_authorized_user_info(data)
        if not creds.valid:
            try:
                creds.refresh(Request())
            except RefreshError:
                raise CliraError(
                    "AUTH_REQUIRED", "Google access expired or was revoked. Reconnect this channel."
                ) from None
            self.secrets.put(self.ref, json.loads(creds.to_json()))
        return creds.token

    def request(self, method, resource, *, params=None, body=None, scope=None):
        try:
            response = self.client.request(
                method,
                DATA_URL + resource,
                params=params,
                json=body,
                headers={"Authorization": "Bearer " + self.token(scope)},
            )
        except httpx.HTTPError:
            raise CliraError("NETWORK", "Google request interrupted. Try again later.", True) from None
        self.check(response)
        return response.json()

    @staticmethod
    def check(response):
        if response.status_code < 400:
            return
        code = {
            401: "AUTH_REQUIRED",
            403: "GOOGLE_PERMISSION_OR_QUOTA",
            404: "NOT_FOUND",
            429: "RATE_LIMIT",
        }.get(response.status_code, "GOOGLE_API_ERROR")
        # Do not surface raw server response text: it can contain request credentials/URLs.
        raise CliraError(
            code,
            f"Google returned HTTP {response.status_code}. Check consent, scopes and Cloud quotas.",
            response.status_code in {429, 500, 502, 503, 504},
        )

    def set_thumbnail(self, video_id, content, mime):
        self.video(video_id)
        response = self.client.post(
            "https://www.googleapis.com/upload/youtube/v3/thumbnails/set",
            params={"videoId": video_id, "uploadType": "media"},
            content=content,
            headers={"Authorization": "Bearer " + self.token(MANAGE_SCOPE), "Content-Type": mime},
        )
        self.check(response)
        return response.json()

    def insert_captions(self, video_id, content, language, name, is_draft):
        self.video(video_id)
        import secrets

        boundary = "clira_" + secrets.token_hex(16)
        metadata = json.dumps(
            {"snippet": {"videoId": video_id, "language": language, "name": name, "isDraft": is_draft}}
        ).encode()
        body = (
            b"--"
            + boundary.encode()
            + b"\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
            + metadata
            + b"\r\n--"
            + boundary.encode()
            + b"\r\nContent-Type: application/octet-stream\r\n\r\n"
            + content
            + b"\r\n--"
            + boundary.encode()
            + b"--\r\n"
        )
        response = self.client.post(
            "https://www.googleapis.com/upload/youtube/v3/captions",
            params={"part": "snippet", "uploadType": "multipart"},
            content=body,
            headers={
                "Authorization": "Bearer " + self.token(MANAGE_SCOPE),
                "Content-Type": "multipart/related; boundary=" + boundary,
            },
        )
        self.check(response)
        return response.json()

    def verify(self):
        result = self.request("GET", "channels", params={"part": "snippet,contentDetails", "mine": "true"})
        items = result.get("items", [])
        if len(items) != 1 or items[0]["id"] != self.channel["id"]:
            raise CliraError(
                "CHANNEL_MISMATCH", "OAuth identity does not resolve to exactly this channel. Reconnect."
            )
        return items[0]

    def list_videos(self, count=5):
        identity = self.verify()
        playlist = identity["contentDetails"]["relatedPlaylists"]["uploads"]
        result = self.request(
            "GET",
            "playlistItems",
            params={"part": "contentDetails", "playlistId": playlist, "maxResults": count},
        )
        ids = [r["contentDetails"]["videoId"] for r in result.get("items", [])]
        if not ids:
            return []
        result = self.request(
            "GET", "videos", params={"part": "snippet,statistics,status,contentDetails", "id": ",".join(ids)}
        )
        by_id = {
            v["id"]: v for v in result.get("items", []) if v["snippet"]["channelId"] == self.channel["id"]
        }
        return [by_id[i] for i in ids if i in by_id]

    def video(self, video_id):
        result = self.request(
            "GET", "videos", params={"id": video_id, "part": "snippet,status,contentDetails"}
        )
        items = result.get("items", [])
        if not items or items[0]["snippet"]["channelId"] != self.channel["id"]:
            raise CliraError("CHANNEL_MISMATCH", "Video is not owned by this channel.")
        return items[0]

    def report(self, days=28, offset_days=0):
        self.verify()
        self.token(READ_SCOPES[1])
        end = date.today() - timedelta(days=2 + offset_days)
        start = end - timedelta(days=days - 1)
        try:
            response = self.client.get(
                "https://youtubeanalytics.googleapis.com/v2/reports",
                params={
                    "ids": "channel==" + self.channel["id"],
                    "startDate": str(start),
                    "endDate": str(end),
                    "metrics": "views,estimatedMinutesWatched,averageViewDuration,subscribersGained",
                },
                headers={"Authorization": "Bearer " + self.token(READ_SCOPES[0])},
            )
        except httpx.HTTPError:
            raise CliraError("NETWORK", "Analytics request interrupted.", True) from None
        self.check(response)
        report = response.json()
        headers, rows = report.get("columnHeaders", []), report.get("rows", [])
        return {
            "range_start": str(start),
            "range_end": str(end),
            "freshness": "delayed" if rows else "unavailable",
            "metrics": dict(zip([h["name"] for h in headers], rows[0])) if rows else {},
            "units": {
                "views": "views",
                "estimatedMinutesWatched": "minutes",
                "averageViewDuration": "seconds",
            },
            "warnings": [
                "YouTube reporting can lag; the requested end date is not a guarantee of completeness."
            ],
        }

    def comments(self, count=5):
        self.verify()
        data = self.request(
            "GET",
            "commentThreads",
            params={
                "part": "snippet",
                "allThreadsRelatedToChannelId": self.channel["id"],
                "maxResults": count,
                "textFormat": "plainText",
                "order": "time",
            },
        )
        return [
            {
                "id": r["snippet"]["topLevelComment"]["id"],
                "video_id": r["snippet"].get("videoId"),
                "text": r["snippet"]["topLevelComment"]["snippet"]["textDisplay"],
                "trust": "untrusted_viewer_content",
            }
            for r in data.get("items", [])
        ]

    def research(self, query, count=5):
        self.verify()
        result = self.request(
            "GET",
            "search",
            params={
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": count,
                "order": "relevance",
            },
        )
        examples = [
            {
                "video_id": row["id"]["videoId"],
                "title": row["snippet"]["title"],
                "channel_id": row["snippet"]["channelId"],
                "published_at": row["snippet"]["publishedAt"],
                "source_url": "https://www.youtube.com/watch?v=" + row["id"]["videoId"],
                "trust": "untrusted_public_content",
            }
            for row in result.get("items", [])
        ]
        return {
            "query": query,
            "examples": examples,
            "warnings": [
                "Search examples are not evidence of a trend, audience retention, or asset reuse rights."
            ],
        }

    def validate_comment(self, comment_id):
        data = self.request("GET", "comments", params={"part": "snippet", "id": comment_id})
        items = data.get("items", [])
        if not items or items[0]["snippet"].get("channelId") != self.channel["id"]:
            raise CliraError("CHANNEL_MISMATCH", "Comment is not on the selected channel.")

    def begin_upload(self, payload, size):
        response = self.client.post(
            "https://www.googleapis.com/upload/youtube/v3/videos",
            params={"uploadType": "resumable", "part": "snippet,status"},
            json=payload,
            headers={
                "Authorization": "Bearer " + self.token(UPLOAD_SCOPE),
                "X-Upload-Content-Length": str(size),
                "X-Upload-Content-Type": "video/mp4",
            },
        )
        self.check(response)
        location = response.headers.get("Location", "")
        self.validate_session(location)
        return location

    @staticmethod
    def validate_session(url):
        parsed = urlparse(url)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "www.googleapis.com"
            or parsed.path != "/upload/youtube/v3/videos"
        ):
            raise CliraError(
                "INVALID_UPLOAD_SESSION", "Unexpected upload endpoint. Stopped before sending content."
            )

    def upload_chunk(self, session, content, content_range):
        self.validate_session(session)
        try:
            response = self.client.put(
                session,
                content=content,
                headers={
                    "Authorization": "Bearer " + self.token(UPLOAD_SCOPE),
                    "Content-Length": str(len(content)),
                    "Content-Type": "video/mp4",
                    "Content-Range": content_range,
                },
            )
        except httpx.HTTPError:
            raise CliraError(
                "UPLOAD_INTERRUPTED", "Upload interrupted. Resume the same job to query its session.", True
            ) from None
        if response.status_code == 308:
            match = re.fullmatch(r"bytes=0-(\d+)", response.headers.get("Range", ""))
            return {"offset": int(match.group(1)) + 1 if match else 0}
        if response.status_code in {404, 410}:
            raise CliraError(
                "RECONCILIATION_REQUIRED", "Upload session expired. Inspect YouTube before any new upload."
            )
        self.check(response)
        return {"video": response.json()}

    def update(self, body, part):
        return self.request("PUT", "videos", params={"part": part}, body=body, scope=MANAGE_SCOPE)

    def post_reply(self, comment_id, text):
        self.validate_comment(comment_id)
        posted = self.request(
            "POST",
            "comments",
            params={"part": "snippet"},
            scope=MANAGE_SCOPE,
            body={"snippet": {"parentId": comment_id, "textOriginal": text}},
        )
        verified = self.request("GET", "comments", params={"part": "snippet", "id": posted["id"]})
        items = verified.get("items", [])
        if (
            not items
            or items[0]["snippet"].get("parentId") != comment_id
            or items[0]["snippet"].get("textOriginal") != text
        ):
            raise CliraError(
                "RECONCILIATION_REQUIRED", "Reply exists but its exact target/text could not be verified."
            )
        return items[0]


def connect(config, store, secrets, capability="read", client_file=None, choose=None):
    if config.mode != "live":
        raise CliraError("LIVE_MODE_REQUIRED", "Demo never accesses Google credentials.")
    if capability not in {"read", "upload", "manage"}:
        raise CliraError("CAPABILITY", "Choose read, upload or manage explicitly.")
    try:
        return _connect(config, store, secrets, capability, client_file, choose)
    except CliraError:
        raise
    except Exception:  # noqa: BLE001 -- provider exceptions can contain secrets and callback URLs
        raise CliraError(
            "OAUTH_NOT_COMPLETED",
            "Google sign-in did not complete. Check your Desktop client, consent and network; retry without sharing credentials.",
        ) from None


def _connect(config, store, secrets, capability="read", client_file=None, choose=None):
    """Owner CLI only: browser participation + exact immutable channel confirmation."""
    import os

    from google_auth_oauthlib.flow import InstalledAppFlow

    path = client_file or os.getenv("CLIRA_GOOGLE_CLIENT_FILE")
    if not path:
        raise CliraError(
            "CLIENT_REQUIRED", "Set CLIRA_GOOGLE_CLIENT_FILE to an external Desktop OAuth client JSON."
        )
    scopes = READ_SCOPES + (
        [UPLOAD_SCOPE]
        if capability == "upload"
        else [UPLOAD_SCOPE, MANAGE_SCOPE]
        if capability == "manage"
        else []
    )
    flow = InstalledAppFlow.from_client_secrets_file(path, scopes=scopes, autogenerate_code_verifier=True)
    creds = flow.run_local_server(
        host="127.0.0.1",
        port=0,
        authorization_prompt_message="",
        success_message="Authorization received. Return to the Clira terminal to confirm the channel.",
        access_type="offline",
        timeout_seconds=300,
        prompt="consent",
    )
    response = httpx.get(
        DATA_URL + "channels",
        params={"part": "snippet", "mine": "true"},
        headers={"Authorization": "Bearer " + creds.token},
        timeout=30,
    )
    GoogleYouTube.check(response)
    items = response.json().get("items", [])
    if len(items) != 1:
        raise CliraError(
            "CHANNEL_SELECTION",
            "Google did not return one channel. Choose the intended YouTube account and reconnect.",
        )
    actual = items[0]
    selected = (
        choose(actual)
        if choose
        else input(f"Connect {actual['snippet']['title']}? Type {actual['id']}: ").strip()
    )
    if selected != actual["id"]:
        raise CliraError("CHANNEL_UNCONFIRMED", "Channel was not confirmed. No credentials were saved.")
    ref = "oauth_" + actual["id"]
    secrets.put(ref, json.loads(creds.to_json()))
    channel = store.add_channel(
        actual["id"],
        actual["snippet"]["title"],
        "live",
        connection={"secret_ref": ref, "scopes": list(creds.scopes or scopes), "verified_at": now()},
    )
    store.audit(channel["id"], "oauth.connect", "confirmed")
    return {"id": channel["id"], "name": channel["name"], "scopes": channel["connection"]["scopes"]}
