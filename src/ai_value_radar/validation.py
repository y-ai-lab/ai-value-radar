from __future__ import annotations

from typing import Any

from .models import OUTCOME_STATUSES, VALIDATION_STATUSES, Opportunity


VALIDATION_LABELS = {
    "unverified": "未検証",
    "signal": "反応あり",
    "validated": "検証済み",
    "rejected": "見送り",
}

OUTCOME_LABELS = {
    "not_measured": "未計測",
    "measuring": "計測中",
    "signal": "反応あり",
    "converted": "成約あり",
    "no_signal": "反応なし",
}

OUTCOME_FIELDS = ("views", "clicks", "signups", "sales", "revenue")


def validation_label(status: str | None) -> str:
    return VALIDATION_LABELS.get(str(status or "unverified"), "未検証")


def outcome_label(status: str | None) -> str:
    return OUTCOME_LABELS.get(str(status or "not_measured"), "未計測")


def build_validation_plan(item: Opportunity) -> str:
    """Return a small, human-checkable route from signal to revenue evidence."""
    if item.category == "affiliate_program" or item.affiliate_rate is not None:
        return (
            "1. 公式Affiliateページで報酬・Cookie・禁止事項を確認。"
            " 2. 読者の悩みに合わせた比較投稿を1本だけ公開。"
            " 3. クリック・登録・成約をTelegramの/resultで記録。"
        )
    if item.category in {"lifetime_deal", "discount", "free_credit", "pricing_change"}:
        return (
            "1. 公式ページで価格・期限・日本利用・商用利用を確認。"
            " 2. 自分の作業で15〜30分だけ試す。"
            " 3. 反応と登録・成約をTelegramの/resultで記録。"
        )
    if item.github_repository:
        return (
            "1. READMEとライセンスを確認。"
            " 2. 自分の作業に使える最小例を1つ試す。"
            " 3. 読者の反応と相談・依頼の有無を記録。"
        )
    return (
        "1. 公式情報と利用条件を確認。"
        " 2. 読者の悩みに対する具体的な使い方を1つ試す。"
        " 3. 投稿後の反応・登録・成約をTelegramの/resultで記録。"
    )


def calculate_revenue_readiness(item: Opportunity) -> int:
    """Score actionability, not proven demand or guaranteed income.

    The value is intentionally separate from ``final_score``. A high value
    means that a candidate has enough concrete information to test; it never
    means that a sale has happened.
    """
    score = 0
    if item.category != "other":
        score += 15
    if any(
        value is not None
        for value in (item.current_price, item.original_price, item.discount, item.affiliate_rate)
    ):
        score += 22
    if item.affiliate_type == "recurring":
        score += 8
    if item.cookie_days is not None:
        score += 4
    if item.deadline:
        score += 8
    if item.summary or item.evidence:
        score += 12
    if item.reader_problem:
        score += 10
    if item.reader_action:
        score += 8
    if item.monetization:
        score += 8
    if item.project_use:
        score += 5
    if item.confidence >= 0.7:
        score += 5
    elif item.confidence >= 0.5:
        score += 3
    if item.validation_status == "signal":
        score += 5
    elif item.validation_status == "validated":
        score += 12
    elif item.validation_status == "rejected":
        score -= 25
    if item.outcome_status == "signal":
        score += 5
    elif item.outcome_status == "converted":
        score += 15
    elif item.outcome_status == "no_signal":
        score -= 5
    return max(0, min(100, score))


def outcome_status_for(value: dict[str, Any]) -> str:
    try:
        revenue = float(value.get("revenue", 0) or 0)
    except (TypeError, ValueError):
        revenue = 0.0
    try:
        sales = int(value.get("sales", 0) or 0)
        signups = int(value.get("signups", 0) or 0)
        clicks = int(value.get("clicks", 0) or 0)
        views = int(value.get("views", 0) or 0)
    except (TypeError, ValueError):
        return "not_measured"
    if sales > 0 or revenue > 0:
        return "converted"
    if signups > 0 or clicks > 0:
        return "signal"
    if views > 0:
        return "measuring"
    return "no_signal"


def update_outcome_metrics(
    entry: dict[str, Any], updates: dict[str, int | float], updated_at: str
) -> dict[str, Any]:
    """Apply bounded, aggregate metrics to a public history entry."""
    for key, value in updates.items():
        if key == "revenue":
            entry[key] = round(float(value), 2)
        else:
            entry[key] = int(value)
    entry["outcome_status"] = outcome_status_for(entry)
    entry["outcome_updated_at"] = updated_at
    return entry


def outcome_totals(entries: list[dict[str, Any]]) -> dict[str, int | float]:
    totals: dict[str, int | float] = {
        "tracked_items": 0,
        "views": 0,
        "clicks": 0,
        "signups": 0,
        "sales": 0,
        "revenue": 0.0,
    }
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if entry.get("outcome_updated_at"):
            totals["tracked_items"] += 1
        for key in OUTCOME_FIELDS:
            try:
                value = float(entry.get(key, 0) or 0)
            except (TypeError, ValueError):
                value = 0.0
            if key == "revenue":
                totals[key] = round(float(totals[key]) + max(0.0, value), 2)
            else:
                totals[key] = int(totals[key]) + max(0, int(value))
    return totals
