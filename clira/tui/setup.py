"""Owner-driven creator setup; no network calls until a connection is explicitly chosen."""

import re
from pathlib import Path

from ..config import CliraError
from ..creator import QUESTIONS, Creator, valid_model_key
from ..storage import encode
from ..workspaces import launch
from .presentation import literal


class CreatorSetup:
    def __init__(self, terminal):
        self.t = terminal
        self.creator = Creator(terminal.service)

    def choice(self, question, options, default):
        while True:
            answer = self.t.ask(question + " > ").lower() or default
            if answer in {"/cancel", "/back"}:
                return None
            if answer in options:
                return answer
            self.t.print("Choose " + " / ".join(options) + ". /cancel saves progress for later.")

    def profile(self):
        t = self.t
        t.print("LET'S MAKE CLIRA YOURS")
        t.print(
            "Your creator setup is saved on this device after each answer. /back revisits; /cancel pauses."
        )
        t.print("Review before saving. Only share personal details you want Clira to remember. No keys here.")
        draft = self.creator.draft()
        step = min(draft["step"], len(QUESTIONS) - 1)
        while True:
            while step < len(QUESTIONS):
                key, section, question, default = QUESTIONS[step]
                existing = self.creator.draft()["answers"].get(key, default)
                t.view.emit(t.view.heading(f"{section} · {step + 1} OF {len(QUESTIONS)}"))
                t.view.emit(literal(question))
                if existing:
                    t.print("Enter keeps: " + existing)
                answer = t.ask(question + " > ")
                if answer.lower() in {"/cancel", "cancel"}:
                    t.print("Setup paused. Your answers stay on this device. /setup resumes.")
                    return False
                if answer.lower() in {"/back", "back"}:
                    step = max(0, step - 1)
                    continue
                try:
                    self.creator.save_answer(key, answer or existing, step + 1)
                except CliraError as exc:
                    t.view.error(exc.code, exc.message)
                    continue
                step += 1
            t.print("REVIEW YOUR CREATOR MEMORY")
            for i, (key, _, question, _) in enumerate(QUESTIONS, 1):
                t.print(f"{i}. {question}\n   {self.creator.draft()['answers'][key]}")
            t.print("These preferences never authorize uploads, spending or channel changes.")
            decision = t.ask("SAVE profile / question number to edit / /back / /cancel > ")
            if decision.lower() == "save":
                self.creator.complete()
                t.print("Creator profile saved locally. You can inspect /profile and manage /memory.")
                return True
            if decision == "/cancel":
                return False
            if decision == "/back":
                step = len(QUESTIONS) - 1
            elif decision.isdigit() and 1 <= int(decision) <= len(QUESTIONS):
                step = int(decision) - 1

    def connections(self):
        while True:
            try:
                return self._connections()
            except CliraError as exc:
                self.t.view.error(exc.code, exc.message)
                self.t.print(
                    "Your saved profile is safe. Retry connections, or /cancel to leave them for later."
                )

    def _connections(self):
        t, service = self.t, self.t.service
        t.print("CONNECTIONS · Set up now or leave any connection for later.")
        t.print(
            f"AI: {service.config.model}; Google channels: {sum(c['connected'] for c in service.channels())}; Telegram: {'paired' if service.store.setting('telegram_owner') else 'not paired'}."
        )
        ai = self.choice("AI: 1 configure Gemini / 2 keep current setup", {"1", "2"}, "2")
        if ai is None:
            return False
        if ai == "1":
            key = t.ask_secret("Gemini API key (hidden; Enter keeps existing) > ")
            if key in {"/cancel", "/back"}:
                return False
            if key:
                if not valid_model_key(key):
                    raise CliraError("KEY_FORMAT", "Key format is invalid. Nothing was saved.")
                service.secrets.put("gemini", {"api_key": key})
            import os

            from ..creator import model_key

            if key and os.getenv("GEMINI_API_KEY") and key != os.environ["GEMINI_API_KEY"]:
                t.print(
                    "GEMINI_API_KEY in your environment overrides the saved key. Unset it to use the new saved key."
                )

            if not model_key(service):
                raise CliraError("MODEL_KEY_REQUIRED", "A Gemini key is needed. You can continue offline.")
            model = t.ask("Model ID from AI Studio > ")
            if not re.fullmatch(r"[a-zA-Z0-9._-]{1,100}", model):
                raise CliraError("MODEL_ID", "Use the exact model ID from AI Studio.")
            consent = self.choice(
                "Enable provider requests with your account's quota/billing? yes/no", {"yes", "no"}, "no"
            )
            if consent is None:
                return False
            runtime = {
                "model": "gemini",
                "model_id": model,
                "allow_model_calls": consent == "yes",
                "max_model_calls_day": 50,
            }
            service.store.set_setting("creator_runtime", runtime)
            for field, value in runtime.items():
                setattr(service.config, field, value)
            t.print(
                "Gemini configured locally; no test request was made. Daily cap: 50 requests, not a currency budget."
            )
        else:
            t.print("Keeping your current model configuration: " + service.config.model)
        youtube = self.choice("YouTube: 1 connect read-only now / 2 later", {"1", "2"}, "2")
        if youtube is None:
            return False
        if youtube == "1":
            if service.config.mode != "live":
                t.print(
                    "For real Google sign-in, restart clira --mode live; then /connections. Your profile stays saved."
                )
            else:
                existing_path = service.store.setting("creator_google_client", "")
                if existing_path:
                    t.print("Saved Desktop OAuth client path is available. Enter keeps it.")
                path = t.ask("Path to Desktop OAuth client JSON (not the file contents) > ") or existing_path
                if path in {"/back", "/cancel"}:
                    return False
                if not Path(path).is_file():
                    raise CliraError("CLIENT_REQUIRED", "That client file does not exist.")
                import os

                os.environ["CLIRA_GOOGLE_CLIENT_FILE"] = str(Path(path).resolve())
                service.store.set_setting("creator_google_client", str(Path(path).resolve()))
                t.connect()
        telegram = self.choice("Telegram: 1 configure your personal bot / 2 later", {"1", "2"}, "2")
        if telegram is None:
            return False
        if telegram == "1":
            t.print("Create your bot with @BotFather /newbot. Bot conversations pass through Telegram.")
            token = t.ask_secret("Telegram bot token (hidden) > ")
            if token in {"/cancel", "/back"}:
                return False
            if not re.fullmatch(r"\d{5,}:[A-Za-z0-9_-]{20,}", token):
                raise CliraError("BOT_TOKEN", "Token format is invalid. Nothing was saved.")
            service.secrets.put("telegram", {"token": token})
            service.store.set_setting("telegram_owner", {})
            service.store.set_setting("telegram_offset", 0)
            from ..telegram import pairing_code

            code = pairing_code(service)
            t.print(
                "Bot token saved locally. Start clira telegram run, then privately send /pair "
                + code
                + " to your bot (10 minute expiry)."
            )
        service.store.set_setting("creator_connections_done", True)
        return True

    def project(self):
        t = self.t
        choice = self.choice("START: 1 first project / 2 keep or choose a channel", {"1", "2"}, "1")
        if choice is None:
            return None
        if choice != "1":
            return False
        profile = self.creator.profile()["answers"]
        title = t.ask("Name your first project (Enter: My YouTube channel) > ") or "My YouTube channel"
        if title in {"/back", "/cancel"}:
            t.print("Project setup paused. No project was created.")
            return None
        from ..creator import clean_fact

        title = clean_fact(title)
        result = launch(
            t.service,
            profile["passions"],
            profile["audience"],
            profile["language"],
            profile["weekly_time"],
            profile["format"],
        )
        channel = result["workspace"]["id"]
        identity = {
            **result["workspace"]["profile"],
            "voice": profile["voice"],
            "timezone": profile["timezone"],
            "rules": profile["boundaries"],
        }
        t.service.store.execute(
            "UPDATE channels SET name=?,profile=? WHERE id=?", (title, encode(identity), channel)
        )
        t.service.store.put(
            channel,
            "project",
            {
                "title": title,
                "goal": profile["goal"],
                "cadence": profile["cadence"],
                "status": "planning",
                "source": "owner_setup",
            },
        )
        t.channel, t.conversation, t.last = channel, None, None
        t.service.store.set_setting("active_workspace:" + t.service.config.mode, channel)
        t.print(
            f"Your project {title} is ready: three starter ideas and a draft calendar, based on your creator profile."
        )
        t.print("These are local starting templates, not audience research or a connected YouTube account.")
        return True

    def run(self, edit=False):
        if edit and not self.creator.store.setting("creator_setup_draft"):
            existing = self.creator.profile()
            if existing:
                self.creator.store.set_setting(
                    "creator_setup_draft", {"answers": existing["answers"], "step": 0}
                )
        if (edit or not self.creator.profile()) and not self.profile():
            return False
        if not self.creator.store.setting("creator_connections_done", False) and not self.connections():
            return False
        result = self.project()
        if result is not None:
            self.creator.store.set_setting("creator_setup_finished", True)
        return result
