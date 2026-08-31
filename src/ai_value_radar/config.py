from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
REPORT_DIR = DATA_DIR / "reports"


def _int_env(name: str, default: int, minimum: int = 0) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return max(minimum, int(value))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    timezone: str = "Asia/Tokyo"
    request_timeout_seconds: int = 12
    max_http_requests: int = 40
    max_source_items: int = 24
    max_ai_candidates_per_run: int = 3
    max_ai_calls_per_day: int = 8
    max_notifications: int = 3
    max_history_items: int = 1000
    max_run_history_items: int = 120
    max_report_bytes: int = 100_000
    notify_min_score: int = 70
    ai_model: str = "@cf/meta/llama-3.2-3b-instruct"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            timezone=os.getenv("RADAR_TIMEZONE", cls.timezone),
            request_timeout_seconds=_int_env("RADAR_HTTP_TIMEOUT", cls.request_timeout_seconds, 3),
            max_http_requests=_int_env("RADAR_MAX_HTTP_REQUESTS", cls.max_http_requests, 1),
            max_source_items=_int_env("RADAR_MAX_SOURCE_ITEMS", cls.max_source_items, 1),
            max_ai_candidates_per_run=_int_env(
                "RADAR_MAX_AI_CANDIDATES", cls.max_ai_candidates_per_run, 0
            ),
            max_ai_calls_per_day=_int_env("RADAR_MAX_AI_CALLS_PER_DAY", cls.max_ai_calls_per_day, 0),
            max_notifications=_int_env("RADAR_MAX_NOTIFICATIONS", cls.max_notifications, 0),
            max_history_items=_int_env("RADAR_MAX_HISTORY", cls.max_history_items, 100),
            max_run_history_items=_int_env("RADAR_MAX_RUN_HISTORY", cls.max_run_history_items, 7),
            max_report_bytes=_int_env("RADAR_MAX_REPORT_BYTES", cls.max_report_bytes, 10_000),
            notify_min_score=_int_env("RADAR_NOTIFY_MIN_SCORE", cls.notify_min_score, 0),
            ai_model=os.getenv("CLOUDFLARE_AI_MODEL", cls.ai_model),
        )

    @property
    def cloudflare_ai_enabled(self) -> bool:
        return bool(
            os.getenv("CLOUDFLARE_ACCOUNT_ID")
            and os.getenv("CLOUDFLARE_API_TOKEN")
            and os.getenv("CLOUDFLARE_FREE_ONLY_ACK") == "I_UNDERSTAND_FREE_ONLY"
        )

    @property
    def telegram_enabled(self) -> bool:
        return bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
