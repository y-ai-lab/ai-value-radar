from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .article import render_article_draft
from .config import Settings
from .models import Opportunity
from .publishing import CHANNEL_LABELS, mark_queue_posted, queue_summary, render_content_queue
from .state import load_json, write_json_atomic, write_text_atomic


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


def parse_command(text: str | None) -> tuple[str, list[str]] | None:
    """Parse only the small, documented command set; ignore normal chat text."""
    if not isinstance(text, str):
        return None
    parts = text.strip().split()
    if not parts or not parts[0].startswith("/"):
        return None
    command = parts[0].split("@", 1)[0].lower()
    allowed = {"/help", "/queue", "/good", "/skip", "/trial", "/used", "/published", "/posted"}
    if command not in allowed:
        return None
    return command[1:], parts[1:]


def _get_updates(offset: int, limit: int) -> list[dict[str, Any]]:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        return []
    endpoint = f"https://api.telegram.org/bot{token}/getUpdates"
    body = urlencode(
        {
            "offset": str(max(0, offset)),
            "limit": str(max(1, min(100, limit))),
            "timeout": "0",
            "allowed_updates": json.dumps(["message"], separators=(",", ":")),
        }
    ).encode("utf-8")
    request = Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read(300_000).decode("utf-8", errors="replace"))
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise TelegramError(f"Telegram updates failed: {type(exc).__name__}") from None
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise TelegramError("Telegram updates rejected")
    result = payload.get("result")
    return [value for value in result if isinstance(value, dict)] if isinstance(result, list) else []


def _match_history(history: list[dict[str, Any]], code: str) -> list[dict[str, Any]]:
    clean = code.strip().lower()
    if not clean:
        return []
    return [
        entry
        for entry in history
        if str(entry.get("id", "")).lower() == clean
        or str(entry.get("id", "")).lower().startswith(clean)
    ]


def _help_text() -> str:
    return (
        "AI VALUE RADAR 操作\n\n"
        "/good コード：価値あり\n"
        "/skip コード：今回は不要\n"
        "/trial コード：試用中\n"
        "/used コード：使用済み\n"
        "/published コード：公開済み\n"
        "/posted コード note|x|threads|video：投稿済み\n"
        "/queue：発信キューを確認"
    )


def _ack(text: str, result: dict[str, int]) -> None:
    try:
        _send(text)
    except TelegramError:
        result["ack_errors"] = result.get("ack_errors", 0) + 1


def process_telegram_updates(settings: Settings, data_dir: Path, now_iso: str) -> dict[str, Any]:
    """Consume bounded Telegram commands and update only public, aggregate state.

    The bot accepts commands only from the configured chat. Message text, chat
    identifiers, and usernames are never persisted in the repository.
    """
    result: dict[str, Any] = {
        "received": 0,
        "recognized": 0,
        "feedback_valuable": 0,
        "feedback_not_valuable": 0,
        "usage_updated": 0,
        "posted_count": 0,
        "errors": 0,
        "ack_errors": 0,
    }
    if not settings.telegram_enabled or settings.max_telegram_updates_per_run <= 0:
        return result
    state_path = data_dir / "telegram_state.json"
    state = load_json(state_path, {})
    if not isinstance(state, dict):
        state = {}
    try:
        offset = max(0, int(state.get("update_offset", 0) or 0))
    except (TypeError, ValueError):
        offset = 0
    try:
        updates = _get_updates(offset, settings.max_telegram_updates_per_run)
    except TelegramError:
        result["errors"] = 1
        return result
    if not updates:
        return result

    history_path = data_dir / "opportunities.json"
    queue_path = data_dir / "content_queue.json"
    history = load_json(history_path, [])
    history = [entry for entry in history if isinstance(entry, dict)] if isinstance(history, list) else []
    queue = load_json(queue_path, [])
    queue = [entry for entry in queue if isinstance(entry, dict)] if isinstance(queue, list) else []
    history_changed = False
    queue_changed = False
    latest_update = offset
    configured_chat = str(os.getenv("TELEGRAM_CHAT_ID", ""))
    labels = {"not_used": "未使用", "trial": "試用中", "used": "使用済み", "published": "公開済み"}

    for update in updates[: settings.max_telegram_updates_per_run]:
        try:
            update_id = int(update.get("update_id", -1))
            latest_update = max(latest_update, update_id + 1)
        except (TypeError, ValueError):
            continue
        result["received"] += 1
        message = update.get("message")
        if not isinstance(message, dict):
            continue
        chat = message.get("chat")
        if not isinstance(chat, dict) or str(chat.get("id", "")) != configured_chat:
            continue
        parsed = parse_command(message.get("text"))
        if parsed is None:
            continue
        command, args = parsed
        result["recognized"] += 1
        if command == "help":
            _ack(_help_text(), result)
            continue
        if command == "queue":
            summary = queue_summary(queue)
            queue_url = f"{settings.repository_url.strip().rstrip('/') or 'https://github.com/y-ai-lab/ai-value-radar'}/blob/main/data/content_queue.md"
            _ack(
                f"発信キュー\n未着手：{summary['ready']}件 / 進行中：{summary['in_progress']}件 / 完了：{summary['completed']}件\n{queue_url}",
                result,
            )
            continue
        if command == "posted":
            if len(args) < 2:
                _ack("形式：/posted コード note|x|threads|video", result)
                continue
            status, message_text = mark_queue_posted(queue, args[0], args[1], now_iso)
            if status == "updated":
                result["posted_count"] += 1
                queue_changed = True
            _ack(message_text, result)
            continue
        if command in {"good", "skip", "trial", "used", "published"}:
            if not args:
                _ack(f"形式：/{command} コード", result)
                continue
            matches = _match_history(history, args[0])
            if not matches:
                _ack("該当するコードがありません。通知のコードを確認してください。", result)
                continue
            if len(matches) > 1:
                _ack("コードを8文字より長く指定してください。", result)
                continue
            entry = matches[0]
            code = str(entry.get("id", ""))[:8]
            if command in {"good", "skip"}:
                value = "valuable" if command == "good" else "not_valuable"
                entry["value_feedback"] = value
                entry["value_feedback_at"] = now_iso
                result[f"feedback_{value}"] += 1
                history_changed = True
                _ack(f"{code}：{'価値あり' if value == 'valuable' else '今回は不要'}として記録しました。", result)
                continue
            usage = {
                "trial": "trial",
                "used": "used",
                "published": "published",
            }[command]
            entry["usage_status"] = usage
            entry["usage_status_at"] = now_iso
            for queued in queue:
                if str(queued.get("id", "")) == str(entry.get("id", "")):
                    queued["usage_status"] = usage
                    queue_changed = True
                    break
            result["usage_updated"] += 1
            history_changed = True
            draft_path = str(entry.get("draft_path") or f"data/drafts/{entry.get('id', '')}.md")
            relative_path = Path(draft_path)
            if relative_path.parts and relative_path.parts[0] == "data":
                relative_path = Path(*relative_path.parts[1:])
            local_path = data_dir / relative_path
            try:
                item = Opportunity(**entry)
                mode = entry.get("content_kind", "revenue")
                write_text_atomic(local_path, render_article_draft(item, now_iso, mode=mode))
            except (TypeError, OSError, UnicodeError, ValueError):
                result["errors"] += 1
            _ack(f"{code}：実利用ステータスを{labels[usage]}に更新しました。", result)

    if latest_update > offset:
        write_json_atomic(state_path, {"update_offset": latest_update})
    if history_changed:
        write_json_atomic(history_path, history)
    if queue_changed:
        write_json_atomic(queue_path, queue)
        write_text_atomic(
            data_dir / "content_queue.md",
            render_content_queue(queue, now_iso, settings.repository_url),
        )
    return result
