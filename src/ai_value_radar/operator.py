from __future__ import annotations

from typing import Any

from .filtering import compare_item, find_match
from .models import Opportunity
from .validation import OUTCOME_STATUSES, VALIDATION_STATUSES


def _safe_non_negative_int(value: Any, default: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, parsed)


def _safe_non_negative_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, parsed)


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
            item.usage_status = str(old.get("usage_status") or item.usage_status)
            item.usage_status_at = old.get("usage_status_at")
            item.value_feedback = str(old.get("value_feedback") or item.value_feedback)
            item.value_feedback_at = old.get("value_feedback_at")
            validation_status = str(old.get("validation_status") or item.validation_status)
            item.validation_status = validation_status if validation_status in VALIDATION_STATUSES else "unverified"
            item.demand_evidence = str(old.get("demand_evidence") or item.demand_evidence)
            item.validation_plan = str(old.get("validation_plan") or item.validation_plan)
            item.validation_updated_at = old.get("validation_updated_at")
            item.post_url = str(old.get("post_url") or item.post_url)
            for field in ("views", "clicks", "signups", "sales"):
                setattr(item, field, _safe_non_negative_int(old.get(field), getattr(item, field)))
            item.revenue = _safe_non_negative_float(old.get("revenue"), item.revenue)
            outcome_status = str(old.get("outcome_status") or item.outcome_status)
            item.outcome_status = outcome_status if outcome_status in OUTCOME_STATUSES else "not_measured"
            item.outcome_updated_at = old.get("outcome_updated_at")
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
