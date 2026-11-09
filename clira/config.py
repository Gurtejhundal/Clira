import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("CLIRA_DATA_DIR", ".clira")).resolve())
    mode: str = field(default_factory=lambda: os.getenv("CLIRA_MODE", "demo"))
    display_name: str = field(default_factory=lambda: os.getenv("APP_DISPLAY_NAME", "Clira"))
    enable_writes: bool = field(default_factory=lambda: os.getenv("CLIRA_ENABLE_WRITES", "0") == "1")
    model: str = field(default_factory=lambda: os.getenv("CLIRA_MODEL", "offline"))
    model_id: str = field(default_factory=lambda: os.getenv("CLIRA_MODEL_ID", "gemini-2.5-flash"))
    allow_model_calls: bool = field(default_factory=lambda: os.getenv("CLIRA_ALLOW_MODEL_CALLS", "0") == "1")
    max_model_calls_day: int = field(
        default_factory=lambda: int(os.getenv("CLIRA_MAX_MODEL_CALLS_DAY", "50"))
    )
    max_steps: int = 8
    import_dir: Path | None = None

    def __post_init__(self):
        if self.mode not in {"demo", "live"} or self.model not in {"offline", "gemini"}:
            raise ValueError("mode must be demo/live; model must be offline/gemini")
        self.data_dir = self.data_dir.resolve()
        self.import_dir = (
            self.import_dir or Path(os.getenv("CLIRA_IMPORT_DIR", str(self.data_dir / "imports")))
        ).resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.import_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.data_dir.chmod(0o700)


class CliraError(Exception):
    def __init__(self, code: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.code, self.message, self.retryable = code, message, retryable

    def envelope(self):
        return {
            "ok": False,
            "error": {"code": self.code, "message": self.message, "retryable": self.retryable},
        }
