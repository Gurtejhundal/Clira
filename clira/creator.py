"""Local owner profile, resumable setup and explicit channel-scoped memory."""

import os
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import CliraError
from .storage import encode, now
from .text import terminal_text

# key, section, question, default. Required fields have no default.
QUESTIONS = [
    ("name", "YOU", "What should Clira call you?", ""),
    ("passions", "YOU", "What are your passions and subjects you love?", ""),
    ("experience", "YOU", "What skills or experience do you bring?", "Learning as I go"),
    ("motivation", "YOU", "Why do you want to create on YouTube?", "Share useful work"),
    ("audience", "YOUR CHANNEL", "Who do you want to help or entertain?", ""),
    ("language", "YOUR CHANNEL", "What language should your content use?", "English"),
    ("timezone", "YOUR CHANNEL", "What is your IANA timezone? e.g. Asia/Kolkata", "UTC"),
    ("voice", "YOUR CHANNEL", "How should your channel sound and feel?", "Clear, warm and practical"),
    ("format", "YOUR CHANNEL", "What formats do you want to make?", "long"),
    ("goal", "YOUR DIRECTION", "What would meaningful progress in 90 days look like?", ""),
    ("cadence", "YOUR DIRECTION", "What publishing pace is realistic?", "One video each week"),
    ("weekly_time", "YOUR RESOURCES", "How much time can you give this each week?", "4 hours"),
    (
        "equipment",
        "YOUR RESOURCES",
        "What equipment and editing tools do you have?",
        "Phone and basic editor",
    ),
    ("budget", "YOUR RESOURCES", "What production budget should plans respect?", "No paid production tools"),
    (
        "boundaries",
        "HOW WE WORK",
        "What topics, claims or personal details should Clira avoid?",
        "No unsupported claims or private details",
    ),
    ("feedback", "HOW WE WORK", "How do you like advice and feedback?", "Direct, kind and concise"),
    ("workflow", "HOW WE WORK", "What should Clira help with first?", "Ideas, scripts and packaging"),
    (
        "approval_preference",
        "HOW WE WORK",
        "Prefer suggestions only, or drafts for your review?",
        "drafts for review",
    ),
    (
        "share_with_model",
        "MEMORY & PRIVACY",
        "May your saved profile and relevant notes be sent to your AI provider? yes/no",
        "no",
    ),
]


def clean_fact(value):
    if not isinstance(value, str) or len(value) > 500 or not value.strip():
        raise CliraError("PROFILE_INPUT", "Use 1–500 characters. No credentials in profile or memory.")
    if re.search(r"AIza[\w-]{15,}|\b\d{6,}:[\w-]{20,}|-----BEGIN .*PRIVATE KEY|\bBearer\s+\S+", value):
        raise CliraError(
            "PROFILE_SECRET", "Use the masked connection step for credentials, not profile or memory."
        )
    cleaned = terminal_text(value).strip()
    if not cleaned:
        raise CliraError("PROFILE_INPUT", "Use a readable answer.")
    return cleaned


class Creator:
    def __init__(self, service):
        self.service, self.store = service, service.store

    def profile(self):
        return self.store.setting("creator_profile")

    def draft(self):
        return self.store.setting("creator_setup_draft", {"answers": {}, "step": 0})

    @staticmethod
    def validate_answer(key, value):
        if key not in {q[0] for q in QUESTIONS}:
            raise CliraError("PROFILE_FIELD", "Unknown creator field.")
        value = clean_fact(value)
        if key == "timezone":
            try:
                ZoneInfo(value)
            except (ZoneInfoNotFoundError, ValueError):
                raise CliraError("PROFILE_TIMEZONE", "Use a timezone such as Asia/Kolkata or UTC.") from None
        if key == "share_with_model" and value.lower() not in {"yes", "no"}:
            raise CliraError("PROFILE_CONSENT", "Choose yes or no for AI context sharing.")
        return value

    def save_answer(self, key, value, step):
        value = self.validate_answer(key, value)
        draft = self.draft()
        draft["answers"][key] = value
        draft.update(step=step, updated_at=now())
        self.store.set_setting("creator_setup_draft", draft)

    def complete(self):
        answers = self.draft()["answers"]
        if any(not answers.get(q[0]) for q in QUESTIONS):
            raise CliraError("PROFILE_INCOMPLETE", "Finish and review the creator questions first.")
        profile = {"answers": answers, "approved_at": now(), "version": 1}
        with self.store.connect() as db:
            db.execute("INSERT OR REPLACE INTO settings VALUES(?,?)", ("creator_profile", encode(profile)))
            db.execute("INSERT OR REPLACE INTO settings VALUES(?,?)", ("creator_connections_done", "false"))
            db.execute("INSERT OR REPLACE INTO settings VALUES(?,?)", ("creator_setup_finished", "false"))
            db.execute("DELETE FROM settings WHERE key='creator_setup_draft'")
        return profile

    def update(self, key, value):
        profile = self.profile()
        if not profile:
            raise CliraError("SETUP_REQUIRED", "Complete /setup first.")
        profile["answers"][key] = self.validate_answer(key, value)
        profile["approved_at"] = now()
        self.store.set_setting("creator_profile", profile)
        return profile

    def forget_profile(self):
        self.store.execute(
            "DELETE FROM settings WHERE key IN ('creator_profile','creator_setup_draft','creator_connections_done','creator_setup_finished')"
        )

    def remember(self, channel_id, text):
        self.service.policy.channel(channel_id)
        return self.store.put(
            channel_id, "memory", {"text": clean_fact(text), "source": "owner", "confirmed_at": now()}
        )

    def forget(self, channel_id, note_id):
        self.store.get(channel_id, note_id, "memory")
        self.store.execute(
            "DELETE FROM records WHERE id=? AND channel_id=? AND kind='memory'", (note_id, channel_id)
        )

    def context(self, channel_id, query):
        profile = self.profile()
        if not profile or profile["answers"].get("share_with_model", "no").lower() != "yes":
            return {}
        terms = set(re.findall(r"\w+", query.lower()))
        notes = self.store.list(channel_id, "memory")
        ranked = sorted(
            notes, key=lambda n: len(terms & set(re.findall(r"\w+", n["text"].lower()))), reverse=True
        )
        return {
            "owner_approved_profile_data": profile["answers"],
            "owner_notes_data": [{"id": n["id"], "text": n["text"]} for n in ranked[:8]],
        }


def model_key(service):
    if os.getenv("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    if service.secrets.path("gemini").is_file():
        return service.secrets.get("gemini").get("api_key")
    return None


def load_runtime(service):
    """CLI opt-in settings; explicit environment always wins, write enablement is never loaded."""
    client_path = service.store.setting("creator_google_client")
    if client_path and not os.getenv("CLIRA_GOOGLE_CLIENT_FILE"):
        os.environ["CLIRA_GOOGLE_CLIENT_FILE"] = client_path
    saved = service.store.setting("creator_runtime", {})
    for field, env in [
        ("model", "CLIRA_MODEL"),
        ("model_id", "CLIRA_MODEL_ID"),
        ("allow_model_calls", "CLIRA_ALLOW_MODEL_CALLS"),
        ("max_model_calls_day", "CLIRA_MAX_MODEL_CALLS_DAY"),
    ]:
        if field in saved and env not in os.environ:
            setattr(service.config, field, saved[field])
