"""Owner-initiated local OAuth using the existing terminal connection implementation."""

import os
import threading
from pathlib import Path

from .config import CliraError
from .storage import uid
from .youtube import READ_SCOPES, connect


class Connections:
    def __init__(self, service):
        self.service = service
        self.lock = threading.Lock()
        self.current = None
        self.confirmed = None
        self.event = threading.Event()

    def start(self):
        if self.service.config.mode != "live":
            raise CliraError(
                "LIVE_MODE_REQUIRED",
                "Start clira --mode live serve for Google OAuth. Demo never uses credentials.",
            )
        client = os.getenv("CLIRA_GOOGLE_CLIENT_FILE")
        if not client or not Path(client).is_file():
            raise CliraError(
                "CLIENT_REQUIRED",
                "Configure CLIRA_GOOGLE_CLIENT_FILE privately, then restart. Do not paste credentials here.",
            )
        with self.lock:
            if self.current and self.current["state"] in {"authorizing", "awaiting_confirmation", "saving"}:
                return dict(self.current)
            self.event = threading.Event()
            self.confirmed = None
            self.current = {
                "id": uid("connection"),
                "state": "authorizing",
                "scopes": READ_SCOPES,
                "notice": "Google sign-in runs in your browser. Read-only grant; no channel writes.",
            }
        threading.Thread(target=self.run, daemon=True).start()
        return self.status()

    def run(self):
        def choose(actual):
            with self.lock:
                self.current.update(
                    state="awaiting_confirmation", channel_id=actual["id"], name=actual["snippet"]["title"]
                )
            self.event.wait(300)
            return self.confirmed or ""

        try:
            result = connect(
                self.service.config, self.service.store, self.service.secrets, "read", None, choose
            )
            with self.lock:
                self.current.update(state="connected", channel_id=result["id"], name=result["name"])
        except Exception:  # noqa: BLE001 -- redact every provider exception at the OAuth trust boundary
            # Provider/transport exceptions can contain tokens and callback URLs.
            with self.lock:
                self.current.update(
                    state="failed",
                    notice="Connection not completed. Check Google consent/client setup and retry. No unconfirmed credentials are saved.",
                )

    def status(self):
        with self.lock:
            return dict(self.current) if self.current else {"state": "idle", "scopes": READ_SCOPES}

    def confirm(self, connection_id, channel_id):
        with self.lock:
            if (
                not self.current
                or self.current["id"] != connection_id
                or self.current["state"] != "awaiting_confirmation"
                or self.current["channel_id"] != channel_id
            ):
                raise CliraError(
                    "CHANNEL_UNCONFIRMED", "Confirm exactly the immutable channel ID currently displayed."
                )
            self.confirmed = channel_id
            self.current["state"] = "saving"
            self.event.set()
        return self.status()
