from __future__ import annotations

import re
from datetime import date, datetime, timezone

from .models import Opportunity


UTILITY_WORDS = (
    "ai",
    "automation",
    "marketing",
    "sales",
    "business",
    "creator",
    "workflow",
    "productivity",
    "画像",
    "動画",
    "文章",
    "自動化",
    "マーケティング",
)

JP_WORDS = ("japan", "japanese", "worldwide", "global", "available in all countries", "日本", "全世界")
SUSPICIOUS_WORDS = ("guaranteed income", "get rich quick", "double your money", "crypto giveaway", "必ず儲かる")


def days_until_deadline(deadline: str | None, today: date | None = None) -> int | None:
    if not deadline:
        return None
    match = re.search(r"\d{4}-\d{1,2}-\d{1,2}", deadline)
    if not match:
        return 3 if "近い" in deadline or "soon" in deadline.lower() else None
    try:
        target = datetime.strptime(match.group(), "%Y-%m-%d").date()
    except ValueError:
        return None
    return (target - (today or datetime.now(timezone.utc).date())).days


def calculate_rule_score(item: Opportunity) -> int:
    text = f"{item.title} {item.summary}".lower()
    score = 0

    if item.category == "lifetime_deal":
        score += 15
    if item.discount is not None:
        if item.discount >= 50:
            score += 15
        elif item.discount >= 30:
            score += 8
    if item.original_price is not None and item.original_price >= 20:
        score += 5
    if item.current_price is not None and item.original_price is not None and item.current_price < item.original_price:
        score += 5
    deadline_days = days_until_deadline(item.deadline)
    if deadline_days is not None and 0 <= deadline_days <= 7:
        score += 5

    if item.category == "affiliate_program":
        if item.affiliate_type == "recurring":
            score += 20
        if item.affiliate_rate is not None:
            if item.affiliate_rate >= 30:
                score += 15
            elif item.affiliate_rate >= 20:
                score += 10
        if item.cookie_days is not None and item.cookie_days >= 30:
            score += 5
        if item.source.startswith("github_") or item.source in {"cloudflare_blog", "zapier_blog"}:
            score += 5

    if any(word in text for word in UTILITY_WORDS):
        score += 10
    if any(word in text for word in JP_WORDS):
        score += 10
    if "free trial" in text or "無料体験" in text:
        score += 5

    if item.source.startswith("hn_") or item.source in {"product_hunt_feed", "appsumo_feed"}:
        score -= 5  # discovery source, not proof from the vendor
    if item.category in {"lifetime_deal", "discount", "affiliate_program", "pricing_change"} and item.current_price is None and item.affiliate_rate is None:
        score -= 10
    if not any(word in text for word in JP_WORDS):
        score -= 5
    if any(word in text for word in SUSPICIOUS_WORDS):
        score -= 20

    return max(0, min(70, score))


def apply_rule_scores(items: list[Opportunity]) -> list[Opportunity]:
    for item in items:
        item.rule_score = calculate_rule_score(item)
        item.final_score = item.rule_score
    return items
