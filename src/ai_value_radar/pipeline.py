from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from .ai import apply_ai_analysis
from .article import generate_article_drafts
from .config import DATA_DIR, REPORT_DIR, Settings, ensure_data_dirs
from .filtering import deduplicate_current
from .latest import render_latest_report
from .models import Opportunity, validate_opportunity
from .normalize import make_opportunity
from .operator import reconcile
from .publishing import (
    queue_summary,
    select_publishing_topics,
    topic_metadata,
    upsert_content_queue,
    write_content_queue,
)
from .scoring import apply_rule_scores
from .sources import collect_candidates
from .state import append_jsonl, load_json, write_json_atomic, write_text_atomic
from .telegram import process_telegram_updates, send_report
from .validation import calculate_revenue_readiness, outcome_totals
from .writer import enrich_fallback, format_telegram_report


TARGET_CATEGORIES = {
    "lifetime_deal",
    "discount",
    "free_credit",
    "affiliate_program",
    "pricing_change",
}


def _now(settings: Settings) -> datetime:
    try:
        return datetime.now(ZoneInfo(settings.timezone))
    except Exception:
        return datetime.now(timezone.utc)


def _bounded_errors(errors: list[dict[str, str]]) -> list[dict[str, str]]:
    return [{str(key): str(value)[:180] for key, value in error.items()} for error in errors[:100]]


def _trim_history(history: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return history[:limit]


def _metrics_7d(
    run_history: list[dict[str, Any]],
    now: datetime,
    outcomes: dict[str, int | float] | None = None,
) -> dict[str, Any]:
    cutoff = (now - timedelta(days=7)).isoformat()
    recent = [entry for entry in run_history if str(entry.get("run_at", "")) >= cutoff]
    keys = (
        "fetched_count",
        "new_count",
        "promising_count",
        "top3_count",
        "affiliate_count",
        "publishable_count",
        "ai_calls",
        "duplicate_count",
        "error_count",
        "draft_count",
        "draft_error_count",
        "topic_count",
        "topic_pack_count",
        "content_pack_count",
        "feedback_valuable",
        "feedback_not_valuable",
        "usage_updated",
        "posted_count",
        "post_url_updated",
        "validation_updated",
        "outcome_updated",
    )
    totals = {key: sum(int(entry.get(key, 0) or 0) for entry in recent) for key in keys}
    if outcomes is not None:
        totals["outcomes"] = outcomes
    totals.update({"runs": len(recent), "window": "7d", "calculated_at": now.isoformat()})
    return totals


def run_scan(
    settings: Settings | None = None,
    collector: Callable[[Settings], tuple[list[dict[str, str | None]], dict[str, Any], list[dict[str, str]]]] = collect_candidates,
    notifier: Callable[[str], str] = send_report,
    now: datetime | None = None,
    data_dir: Path | None = None,
) -> dict[str, Any]:
    settings = settings or Settings.from_env()
    data_dir = data_dir or DATA_DIR
    report_dir = data_dir / "reports"
    data_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    now = now or _now(settings)
    now_iso = now.isoformat(timespec="seconds")
    history_path = data_dir / "opportunities.json"
    runtime_path = data_dir / "runtime_state.json"
    run_history_path = data_dir / "run_history.json"
    feedback = process_telegram_updates(settings, data_dir, now_iso)
    raw, source_stats, source_errors = collector(settings)

    normalized: list[Opportunity] = []
    for raw_item in raw[: settings.max_source_items * len(source_stats)]:
        item = make_opportunity(raw_item, now_iso)
        if item:
            normalized.append(item)
    unique, current_duplicates = deduplicate_current(normalized)
    apply_rule_scores(unique)

    history = load_json(history_path, [])
    if not isinstance(history, list):
        history = []
    runtime_state = load_json(runtime_path, {})
    if not isinstance(runtime_state, dict):
        runtime_state = {}
    current, merged_history, state_counts = reconcile(unique, history, now_iso)
    eligible = [
        item
        for item in current
        if item.status in {"new", "updated"}
        and item.status != "ended"
        and item.category in TARGET_CATEGORIES
    ]
    ai_calls, ai_errors = apply_ai_analysis(eligible, settings, runtime_state)
    for item in current:
        enrich_fallback(item)
        item.revenue_readiness = calculate_revenue_readiness(item)
    promising = [item for item in eligible if item.final_score >= settings.notify_min_score]
    promising.sort(key=lambda item: (item.final_score, item.confidence, item.title), reverse=True)
    publishable = [item for item in eligible if item.final_score >= settings.publish_min_score]
    publishable.sort(key=lambda item: (item.final_score, item.confidence, item.title), reverse=True)
    top3 = publishable[: settings.max_notifications]
    for item in top3:
        item.last_notified_at = now_iso
        for stored in merged_history:
            if stored.get("id") == item.id:
                stored["last_notified_at"] = now_iso
                stored["status"] = item.status
                break

    drafts, draft_errors = generate_article_drafts(
        top3,
        data_dir=data_dir,
        repository_url=settings.repository_url,
        checked_at=now_iso,
        limit=settings.max_article_drafts_per_run,
        max_bytes=settings.max_article_draft_bytes,
        mode="revenue",
    )
    topic_items = select_publishing_topics(
        current,
        source_stats=source_stats,
        excluded_ids={item.id for item in top3},
        limit=settings.max_publishing_topics_per_run,
        min_score=settings.publishing_topic_min_score,
        now=now,
    )
    topic_pack_limit = min(
        settings.max_publishing_topics_per_run,
        max(0, settings.max_total_content_packs_per_run - len(drafts)),
    )
    topic_packs, topic_pack_errors = generate_article_drafts(
        topic_items,
        data_dir=data_dir,
        repository_url=settings.repository_url,
        checked_at=now_iso,
        limit=topic_pack_limit,
        max_bytes=settings.max_article_draft_bytes,
        mode="publishing",
    )
    all_packs = drafts + topic_packs
    queue_path = data_dir / "content_queue.json"
    queue = load_json(queue_path, [])
    queue_errors: list[dict[str, str]] = []
    try:
        queue = upsert_content_queue(
            queue,
            [*top3, *topic_items],
            all_packs,
            now_iso,
            max_items=settings.max_queue_items,
        )
        write_json_atomic(queue_path, queue)
        write_content_queue(data_dir / "content_queue.md", queue, now_iso, settings.repository_url)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        queue_errors.append({"stage": "content_queue", "message": type(exc).__name__})

    # Reconcile again after the optional AI pass so the public history contains
    # the same score and Japanese analysis that was included in the report.
    for item in current:
        for stored in merged_history:
            if stored.get("id") == item.id:
                previous_notification = stored.get("last_notified_at")
                stored.update(item.to_dict())
                if previous_notification and not stored.get("last_notified_at"):
                    stored["last_notified_at"] = previous_notification
                break

    report: dict[str, Any] = {
        "run_at": now_iso,
        "fetched_count": len(raw),
        "normalized_count": len(normalized),
        "unique_count": len(unique),
        "new_count": sum(1 for item in current if item.status == "new"),
        "updated_count": sum(1 for item in current if item.status == "updated"),
        "duplicate_count": current_duplicates + state_counts.get("duplicate", 0),
        "promising_count": len(promising),
        "publishable_count": len(publishable),
        "top3_count": len(top3),
        "draft_count": len(drafts),
        "draft_error_count": len(draft_errors) + len(topic_pack_errors),
        "topic_count": len(topic_items),
        "topic_pack_count": len(topic_packs),
        "content_pack_count": len(all_packs),
        "affiliate_count": sum(1 for item in current if item.category == "affiliate_program"),
        "validation": {
            "unverified": sum(1 for item in current if item.validation_status == "unverified"),
            "signal": sum(1 for item in current if item.validation_status == "signal"),
            "validated": sum(1 for item in current if item.validation_status == "validated"),
            "rejected": sum(1 for item in current if item.validation_status == "rejected"),
        },
        "outcomes": outcome_totals(merged_history),
        "source_stats": source_stats,
        "ai": {
            "enabled": settings.cloudflare_ai_enabled,
            "calls": ai_calls,
            "max_per_run": settings.max_ai_candidates_per_run,
            "errors": len(ai_errors),
        },
        "drafts": all_packs,
        "publishing_topics": [
            topic_metadata(item, next((pack for pack in topic_packs if pack.get("id") == item.id), None))
            for item in topic_items
        ],
        "queue": queue_summary(queue),
        "queue_link": f"{settings.repository_url.strip().rstrip('/') or 'https://github.com/y-ai-lab/ai-value-radar'}/blob/main/data/content_queue.md",
        "feedback": {key: value for key, value in feedback.items() if key != "errors"},
        "latest": {
            "path": "data/latest.md",
            "url": f"{settings.repository_url.strip().rstrip('/') or 'https://github.com/y-ai-lab/ai-value-radar'}/blob/main/data/latest.md",
        },
        "top3": [item.to_dict() for item in top3],
        "errors": _bounded_errors(
            source_errors
            + ai_errors
            + draft_errors
            + topic_pack_errors
            + queue_errors
            + ([{"stage": "telegram_feedback", "message": "poll failed"}] if feedback.get("errors") else [])
        ),
        "notification": {"status": "pending"},
    }

    # Persist public state before trying Telegram. A notification outage must
    # not erase the observation or stop future runs.
    safe_history = []
    for entry in _trim_history(merged_history, settings.max_history_items):
        if validate_opportunity(entry) == []:
            safe_history.append(entry)
    write_json_atomic(history_path, safe_history)
    write_json_atomic(runtime_path, runtime_state)
    run_history = load_json(run_history_path, [])
    if not isinstance(run_history, list):
        run_history = []
    run_entry = {
        "run_at": now_iso,
        "fetched_count": report["fetched_count"],
        "new_count": report["new_count"],
        "updated_count": report["updated_count"],
        "promising_count": report["promising_count"],
        "publishable_count": report["publishable_count"],
        "top3_count": report["top3_count"],
        "draft_count": report["draft_count"],
        "draft_error_count": report["draft_error_count"],
        "topic_count": report["topic_count"],
        "topic_pack_count": report["topic_pack_count"],
        "content_pack_count": report["content_pack_count"],
        "affiliate_count": report["affiliate_count"],
        "ai_calls": ai_calls,
        "feedback_valuable": int(feedback.get("feedback_valuable", 0) or 0),
        "feedback_not_valuable": int(feedback.get("feedback_not_valuable", 0) or 0),
        "usage_updated": int(feedback.get("usage_updated", 0) or 0),
        "posted_count": int(feedback.get("posted_count", 0) or 0),
        "post_url_updated": int(feedback.get("post_url_updated", 0) or 0),
        "validation_updated": int(feedback.get("validation_updated", 0) or 0),
        "outcome_updated": int(feedback.get("outcome_updated", 0) or 0),
        "duplicate_count": report["duplicate_count"],
        "error_count": len(report["errors"]),
        "seconds": round(time.monotonic() - started, 2),
        "telegram_configured": settings.telegram_enabled,
    }
    run_history.append(run_entry)
    run_history = run_history[-settings.max_run_history_items :]
    write_json_atomic(run_history_path, run_history)
    report["seconds"] = run_entry["seconds"]
    report["metrics_7d"] = _metrics_7d(run_history, now, report["outcomes"])
    try:
        write_text_atomic(data_dir / "latest.md", render_latest_report(report))
    except (OSError, UnicodeError) as exc:
        report["errors"].append({"stage": "latest_report", "message": type(exc).__name__})
        report["errors"] = _bounded_errors(report["errors"])
        report["draft_error_count"] = report.get("draft_error_count", 0)
    write_json_atomic(data_dir / "metrics_7d.json", report["metrics_7d"])
    write_json_atomic(data_dir / "last_report.json", report)
    report_path = report_dir / f"{now.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}.json"
    write_json_atomic(report_path, report)

    for error in report["errors"]:
        append_jsonl(data_dir / "errors.jsonl", {"run_at": now_iso, **error})

    try:
        report["notification"]["status"] = notifier(format_telegram_report(report))
    except Exception as exc:
        report["notification"]["status"] = "error"
        report["notification"]["error"] = type(exc).__name__
        append_jsonl(data_dir / "errors.jsonl", {"run_at": now_iso, "stage": "telegram", "message": type(exc).__name__})
    write_json_atomic(data_dir / "last_report.json", report)
    write_json_atomic(report_path, report)
    report_files = sorted(report_dir.glob("*.json"), key=lambda path: path.name)
    for old_report in report_files[:-120]:
        try:
            old_report.unlink()
        except OSError:
            pass
    return report
