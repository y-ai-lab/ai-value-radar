from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class TelegramError(RuntimeError):
    pass


def _send(text: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise TelegramError("Telegram secrets are not configured")
    endpoint = f"https://api.telegram.org/bot{token}/sendMessage"
    body = urlencode(
        {
            "chat_id": chat_id,
            "text": text[:4096],
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    request = Request(endpoint, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read(20_000).decode("utf-8", errors="replace"))
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise TelegramError(f"Telegram request failed: {type(exc).__name__}") from None
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise TelegramError("Telegram rejected the message")


def send_report(text: str) -> str:
    if not os.getenv("TELEGRAM_BOT_TOKEN") or not os.getenv("TELEGRAM_CHAT_ID"):
        return "skipped_missing_secrets"
    _send(text)
    return "sent"


def send_test() -> str:
    _send("AI VALUE RADAR\n\nTelegramテスト通知に成功しました。")
    return "sent"
