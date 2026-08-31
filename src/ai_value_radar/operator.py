from __future__ import annotations

from typing import Any

from .filtering import compare_item, find_match
from .models import Opportunity


def reconcile(items: list[Opportunity], history: list[dict[str, Any]], now_iso: str) -> tuple[list[Opportunity], list[dict[str, Any]], dict[str, int]]:
    current: list[Opportunity] = []
    counts = {"new": 0, "updated": 0, "duplicate": 0, "ended": 0}
    for item in items:
        old = find_match(item, history)
        status, changed = compare_item(item, old)
        item.status = status
        item.updated_fields = changed
        if old:
            item.discovered_at = str(old.get("discovered_at") or item.discovered_at)
            item.last_notified_at = old.get("last_notified_at")
        if any(word in f"{item.title} {item.summary}".lower() for word in ("expired", "ended", "終了しました", "販売終了")):
            item.status = "ended"
        counts[item.status] = counts.get(item.status, 0) + 1
        current.append(item)

    by_id: dict[str, dict[str, Any]] = {}
    for old in history:
        if isinstance(old, dict) and old.get("id"):
            by_id[str(old["id"])] = old
    for item in current:
        stored = item.to_dict()
        if item.status == "duplicate":
            stored["status"] = "seen"
        stored["last_seen_at"] = now_iso
        by_id[item.id] = stored
    merged = sorted(by_id.values(), key=lambda value: str(value.get("last_seen_at", "")), reverse=True)
    return current, merged, counts
