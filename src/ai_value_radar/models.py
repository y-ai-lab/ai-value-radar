from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


CATEGORIES = {
    "lifetime_deal",
    "discount",
    "free_credit",
    "affiliate_program",
    "pricing_change",
    "other",
}

STATUSES = {"new", "updated", "duplicate", "seen", "ended"}
USAGE_STATUSES = {"not_used", "trial", "used", "published"}
FEEDBACK_VALUES = {"valuable", "not_valuable"}
CONTENT_KINDS = {"revenue", "publishing"}


@dataclass
class Opportunity:
    id: str
    title: str
    url: str
    source: str
    discovered_at: str
    last_seen_at: str
    category: str = "other"
    original_price: Optional[float] = None
    current_price: Optional[float] = None
    currency: Optional[str] = None
    discount: Optional[float] = None
    affiliate_rate: Optional[float] = None
    affiliate_type: Optional[str] = None
    cookie_days: Optional[int] = None
    deadline: Optional[str] = None
    rule_score: int = 0
    ai_score: Optional[int] = None
    final_score: int = 0
    status: str = "new"
    content_hash: str = ""
    canonical_url: str = ""
    published_at: Optional[str] = None
    summary: str = ""
    service_name: str = ""
    project_type: str = ""
    project_summary: str = ""
    project_use: str = ""
    content_angle: str = ""
    reader_problem: str = ""
    reader_action: str = ""
    github_owner: str = ""
    github_repository: str = ""
    github_language: str = ""
    github_stars: Optional[int] = None
    github_topics: list[str] = field(default_factory=list)
    github_homepage: str = ""
    why_now: str = ""
    best_for: str = ""
    skip_if: str = ""
    monetization: str = ""
    risk: str = ""
    confidence: float = 0.0
    evidence: str = ""
    ai_title: Optional[str] = None
    ai_category: Optional[str] = None
    updated_fields: list[str] = field(default_factory=list)
    last_notified_at: Optional[str] = None
    draft_path: Optional[str] = None
    draft_status: str = ""
    content_kind: str = "revenue"
    content_score: int = 0
    usage_status: str = "not_used"
    usage_status_at: Optional[str] = None
    value_feedback: str = ""
    value_feedback_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_opportunity(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = ("id", "title", "url", "source", "discovered_at", "last_seen_at", "content_hash")
    for key in required:
        if not isinstance(value.get(key), str) or not value[key].strip():
            errors.append(f"missing_or_invalid:{key}")
    if value.get("category") not in CATEGORIES:
        errors.append("invalid:category")
    if value.get("status") not in STATUSES:
        errors.append("invalid:status")
    usage_status = value.get("usage_status", "not_used")
    if usage_status not in USAGE_STATUSES:
        errors.append("invalid:usage_status")
    value_feedback = value.get("value_feedback", "")
    if value_feedback and value_feedback not in FEEDBACK_VALUES:
        errors.append("invalid:value_feedback")
    content_kind = value.get("content_kind", "revenue")
    if content_kind not in CONTENT_KINDS:
        errors.append("invalid:content_kind")
    for key in ("rule_score", "final_score"):
        if not isinstance(value.get(key), int) or not 0 <= value[key] <= 100:
            errors.append(f"invalid:{key}")
    content_score = value.get("content_score", 0)
    if not isinstance(content_score, int) or not 0 <= content_score <= 100:
        errors.append("invalid:content_score")
    ai_score = value.get("ai_score")
    if ai_score is not None and (not isinstance(ai_score, int) or not 0 <= ai_score <= 100):
        errors.append("invalid:ai_score")
    confidence = value.get("confidence", 0.0)
    if not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
        errors.append("invalid:confidence")
    return errors
