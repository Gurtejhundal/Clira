"""Explicitly started personal Telegram transport; paired private chat only."""

import hashlib
import hmac
import secrets
import time

import httpx

from .agent import Agent
from .config import CliraError
from .creator import Creator


def pairing_code(service):
    code = secrets.token_urlsafe(18)
    service.store.set_setting(
        "telegram_pair", {"digest": hashlib.sha256(code.encode()).hexdigest(), "expires": time.time() + 600}
    )
    return code


class Telegram:
    def __init__(self, service, channel_id, client=None):
        self.service, self.channel = service, channel_id
        service.policy.channel(channel_id)
        if not Creator(service).profile():
            raise CliraError("SETUP_REQUIRED", "Run clira and complete your creator setup first.")
        self.token = service.secrets.get("telegram")["token"]
        self.client = client or httpx.Client(timeout=40)

    def api(self, method, payload):
        try:
            response = self.client.post(f"https://api.telegram.org/bot{self.token}/{method}", json=payload)
            if response.status_code >= 400:
                raise ValueError()
            result = response.json()
            if not result.get("ok"):
                raise ValueError()
            return result["result"]
        except (httpx.HTTPError, ValueError, KeyError):
            raise CliraError(
                "TELEGRAM_API",
                "Telegram request failed. Check your bot connection; no automatic replay was attempted.",
            ) from None

    def handle(self, update):
        store = self.service.store
        update_id = update.get("update_id")
        if not isinstance(update_id, int) or update_id < store.setting("telegram_offset", 0):
            return None
        # Mark before work: uncertain/failed work must not be repeated silently after restart.
        store.set_setting("telegram_offset", update_id + 1)
        message = update.get("message", {})
        chat, sender = message.get("chat", {}), message.get("from", {})
        text = message.get("text", "")
        if chat.get("type") != "private" or not isinstance(text, str) or sender.get("is_bot"):
            return None
        owner = store.setting("telegram_owner")
        chat_id, user_id = chat.get("id"), sender.get("id")
        if not isinstance(chat_id, int) or not isinstance(user_id, int):
            return None
        if text.startswith("/pair ") and not owner:
            pairing = store.setting("telegram_pair", {})
            given = hashlib.sha256(text[6:].strip().encode()).hexdigest()
            if time.time() > pairing.get("expires", 0) or not hmac.compare_digest(
                given, pairing.get("digest", "")
            ):
                return None
            store.set_setting("telegram_owner", {"chat_id": chat_id, "user_id": user_id})
            store.set_setting("telegram_pair", {})
            return (
                chat_id,
                "Paired with your local Clira. /help for commands. Channel writes still need local owner review.",
            )
        if owner != {"chat_id": chat_id, "user_id": user_id}:
            return None
        if len(text) > 12000:
            return chat_id, "Keep messages under 12000 characters."
        creator = Creator(self.service)
        if text in {"/start", "/help"}:
            answer = "Clira · /new /status /memory /remember TEXT /forget ID. Send a message to talk about your active project. Use the local terminal for setup, channel switching and exact approvals."
        elif text == "/status":
            answer = f"Channel: {self.channel}\nModel: {self.service.config.model}\nSession: {store.setting('telegram_session:' + self.channel, 'none')}"
        elif text == "/new":
            session = store.new_session(self.channel, "Telegram conversation")
            store.set_setting("telegram_session:" + self.channel, session["id"])
            answer = "New conversation: " + session["id"]
        elif text == "/memory":
            answer = (
                "\n".join(n["id"] + ": " + n["text"] for n in store.list(self.channel, "memory"))
                or "No saved notes. /remember TEXT saves an explicit note."
            )
        elif text.startswith("/remember "):
            note = creator.remember(self.channel, text[10:])
            answer = "Remembered locally: " + note["id"]
        elif text.startswith("/forget "):
            creator.forget(self.channel, text[8:].strip())
            answer = "Note removed. Existing conversation history is unchanged."
        elif text.startswith("/"):
            answer = "Use /help. Setup, channel changes, approvals and execution stay in the local terminal."
        else:
            result = Agent(self.service).chat(
                self.channel, text, store.setting("telegram_session:" + self.channel)
            )
            store.set_setting("telegram_session:" + self.channel, result["conversation_id"])
            answer = result["message"] + "\n\nSession: " + result["conversation_id"]
        return chat_id, answer

    def poll_once(self):
        updates = self.api(
            "getUpdates",
            {
                "offset": self.service.store.setting("telegram_offset", 0),
                "timeout": 25,
                "allowed_updates": ["message"],
            },
        )
        for update in updates:
            try:
                reply = self.handle(update)
            except CliraError as exc:
                message = update.get("message", {})
                owner = self.service.store.setting("telegram_owner", {})
                if message.get("chat", {}).get("id") != owner.get("chat_id") or message.get("from", {}).get(
                    "id"
                ) != owner.get("user_id"):
                    continue
                reply = owner["chat_id"], exc.code + ": " + exc.message
            if reply:
                chat_id, answer = reply
                for start in range(0, len(answer), 3500):
                    self.api("sendMessage", {"chat_id": chat_id, "text": answer[start : start + 3500]})

    def run(self):
        try:
            while True:
                self.poll_once()
        except KeyboardInterrupt:
            return
