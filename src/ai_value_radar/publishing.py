from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from .models import Opportunity
from .state import write_text_atomic


CHANNELS = ("note", "x", "threads", "video")
CHANNEL_LABELS = {
    "note": "note",
    "x": "X",
    "threads": "Threads",
    "video": "短尺動画",
}

CONTENT_KEYWORDS = (
    "ai",
    "automation",
    "saas",
    "llm",
    "workflow",
    "release",
    "launched",
    "launch",
    "introducing",
    "new feature",
    "update",
    "pricing",
    "price",
    "free",
    "credit",
    "割引",
    "新機能",
    "リリース",
    "アップデート",
    "料金",
    "無料",
)
RELEVANCE_KEYWORDS = (
    "ai",
    "automation",
    "saas",
    "llm",
    "workflow",
    "image",
    "video",
    "文章",
    "自動化",
    "n8n",
    "flowise",
    "openwebui",
    "litellm",
    "zapier",
    "cloudflare",
)


def _one_line(value: str | None, limit: int = 180) -> str:
    text = " ".join((value or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _recent_bonus(published_at: str | None, now: datetime) -> int:
    if not published_at:
        return 0
    try:
        parsed = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return 0
    age = now.astimezone(timezone.utc) - parsed.astimezone(timezone.utc)
    if age < timedelta(days=2):
        return 15
    if age < timedelta(days=14):
        return 10
    if age < timedelta(days=45):
        return 4
    return 0


def calculate_content_score(
    item: Opportunity,
    source_stats: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> int:
    """Score whether a fresh AI/SaaS item is worth turning into content.

    This is deliberately separate from the revenue score. It uses no AI and
    prefers recent, official, concrete changes so a quiet deal cycle does not
    stop the user's publishing pipeline.
    """
    text = f"{item.title} {item.summary} {item.source}".lower()
    if not any(word in text for word in RELEVANCE_KEYWORDS):
        return 0
    source = (source_stats or {}).get(item.source, {})
    score = 0
    if isinstance(source, dict) and source.get("official") is True:
        score += 25
    if isinstance(source, dict) and source.get("kind") in {"rss", "github_releases", "official_page"}:
        score += 10
    if item.status == "new":
        score += 15
    elif item.status == "updated":
        score += 12
    if any(word in text for word in CONTENT_KEYWORDS):
        score += 20
    if item.summary:
        score += 8
    score += _recent_bonus(item.published_at, now or datetime.now(timezone.utc))
    if item.category != "other":
        score += 10
    if item.source.startswith("hn_"):
        score -= 10
    return max(0, min(100, score))


def select_publishing_topics(
    items: Iterable[Opportunity],
    source_stats: dict[str, Any] | None = None,
    excluded_ids: set[str] | None = None,
    limit: int = 2,
    min_score: int = 35,
    now: datetime | None = None,
) -> list[Opportunity]:
    excluded_ids = excluded_ids or set()
    selected: list[Opportunity] = []
    for item in items:
        if item.id in excluded_ids or item.status not in {"new", "updated"}:
            continue
        item.content_score = calculate_content_score(item, source_stats, now)
        if item.content_score >= min_score:
            selected.append(item)
    selected.sort(key=lambda value: (value.content_score, value.confidence, value.title), reverse=True)
    return selected[: max(0, limit)]


def topic_metadata(item: Opportunity, pack: dict[str, Any] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": item.id,
        "code": item.id[:8],
        "title": _one_line(item.ai_title or item.title, 180),
        "url": item.url,
        "source": item.source,
        "content_score": item.content_score,
        "status": item.status,
        "usage_status": item.usage_status,
    }
    if pack:
        result.update({"pack_path": pack.get("path", ""), "pack_url": pack.get("url", "")})
    return result


def _new_channel_state() -> dict[str, dict[str, Any]]:
    return {channel: {"status": "ready"} for channel in CHANNELS}


def _match_queue_code(queue: list[dict[str, Any]], code: str) -> list[dict[str, Any]]:
    clean = code.strip().lower()
    if not clean:
        return []
    return [entry for entry in queue if str(entry.get("id", "")).lower() == clean or str(entry.get("id", "")).lower().startswith(clean)]


def upsert_content_queue(
    existing: Any,
    items: Iterable[Opportunity],
    packs: Iterable[dict[str, Any]],
    now_iso: str,
    max_items: int = 100,
) -> list[dict[str, Any]]:
    queue = [entry for entry in existing if isinstance(entry, dict) and entry.get("id")] if isinstance(existing, list) else []
    by_id = {str(entry["id"]): entry for entry in queue}
    pack_by_id = {str(pack.get("id")): pack for pack in packs if isinstance(pack, dict) and pack.get("id")}
    for item in items:
        pack = pack_by_id.get(item.id)
        if not pack:
            continue
        entry = by_id.get(item.id)
        if entry is None:
            entry = {
                "id": item.id,
                "code": item.id[:8],
                "created_at": now_iso,
                "status": "ready",
                "next_channel": "note",
                "channels": _new_channel_state(),
            }
            queue.append(entry)
            by_id[item.id] = entry
        entry.update(
            {
                "title": _one_line(item.ai_title or item.title, 180),
                "url": item.url,
                "source": item.source,
                "kind": pack.get("kind", "revenue"),
                "pack_path": pack.get("path", ""),
                "pack_url": pack.get("url", ""),
                "usage_status": item.usage_status,
                "content_score": item.content_score,
                "updated_at": now_iso,
            }
        )
        if not isinstance(entry.get("channels"), dict):
            entry["channels"] = _new_channel_state()
        for channel in CHANNELS:
            if not isinstance(entry["channels"].get(channel), dict):
                entry["channels"][channel] = {"status": "ready"}
        if entry.get("status") not in {"ready", "in_progress", "completed"}:
            entry["status"] = "ready"
    queue.sort(key=lambda value: str(value.get("updated_at") or value.get("created_at") or ""), reverse=True)
    return queue[: max(10, max_items)]


def mark_queue_posted(queue: list[dict[str, Any]], code: str, channel: str, now_iso: str) -> tuple[str, str]:
    channel = channel.strip().lower()
    if channel not in CHANNELS:
        return "invalid_channel", "note / x / threads / video のいずれかを指定してください。"
    matches = _match_queue_code(queue, code)
    if not matches:
        return "not_found", "発信キューに該当するコードがありません。"
    if len(matches) > 1:
        return "ambiguous", "コードを8文字より長く指定してください。"
    entry = matches[0]
    channels = entry.setdefault("channels", _new_channel_state())
    channels.setdefault(channel, {})["status"] = "posted"
    channels[channel]["posted_at"] = now_iso
    pending = [name for name in CHANNELS if channels.get(name, {}).get("status") != "posted"]
    entry["next_channel"] = pending[0] if pending else ""
    entry["status"] = "completed" if not pending else "in_progress"
    return "updated", f"{entry.get('code', str(entry.get('id', ''))[:8])} の {CHANNEL_LABELS[channel]} を投稿済みにしました。"


def queue_summary(queue: Any) -> dict[str, int]:
    entries = [entry for entry in queue if isinstance(entry, dict)] if isinstance(queue, list) else []
    ready = sum(1 for entry in entries if entry.get("status") == "ready")
    in_progress = sum(1 for entry in entries if entry.get("status") == "in_progress")
    completed = sum(1 for entry in entries if entry.get("status") == "completed")
    return {"total": len(entries), "ready": ready, "in_progress": in_progress, "completed": completed}


def render_content_queue(queue: Any, checked_at: str, repository_url: str) -> str:
    entries = [entry for entry in queue if isinstance(entry, dict)] if isinstance(queue, list) else []
    base = repository_url.strip().rstrip("/") or "https://github.com/y-ai-lab/ai-value-radar"
    lines = [
        "# AI VALUE RADAR｜発信キュー",
        "",
        f"更新日時：{_one_line(checked_at, 40)}",
        "",
        "次の媒体から順番に使います：note → X → Threads → 短尺動画",
        "Telegramで `/posted コード 媒体` を送ると進捗を更新できます。",
        "",
    ]
    visible = [entry for entry in entries if entry.get("status") != "completed"][:20]
    if not visible:
        lines.append("現在、未投稿の発信用パックはありません。")
    for index, entry in enumerate(visible, start=1):
        title = _one_line(str(entry.get("title", "")), 140).replace("[", "［").replace("]", "］")
        pack_url = str(entry.get("pack_url", ""))
        title_line = f"[{title}]({pack_url})" if pack_url else title
        next_channel = CHANNEL_LABELS.get(str(entry.get("next_channel", "")), "") or "完了"
        lines.extend(
            [
                f"## {index}. {title_line}",
                f"- コード：`{entry.get('code', str(entry.get('id', ''))[:8])}`",
                f"- 状態：{entry.get('status', 'ready')} / 次：{next_channel}",
                f"- note：{entry.get('channels', {}).get('note', {}).get('status', 'ready')}",
                f"- X：{entry.get('channels', {}).get('x', {}).get('status', 'ready')}",
                f"- Threads：{entry.get('channels', {}).get('threads', {}).get('status', 'ready')}",
                f"- 短尺動画：{entry.get('channels', {}).get('video', {}).get('status', 'ready')}",
                f"- 原文：{entry.get('url', '')}",
                "",
            ]
        )
    lines.extend([f"[リポジトリ]({base})", ""])
    return "\n".join(lines)


def write_content_queue(path: Path, queue: list[dict[str, Any]], checked_at: str, repository_url: str) -> None:
    write_text_atomic(path, render_content_queue(queue, checked_at, repository_url))
