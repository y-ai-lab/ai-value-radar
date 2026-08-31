from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .models import Opportunity


TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "referrer",
    "source",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_source",
    "utm_term",
}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(data)


def clean_text(value: str | None, limit: int = 1800) -> str:
    if not value:
        return ""
    parser = _TextExtractor()
    try:
        parser.feed(value)
        value = " ".join(parser.parts)
    except Exception:
        value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:limit]


def normalize_url(value: str | None) -> str:
    if not value:
        return ""
    try:
        parts = urlsplit(value.strip())
    except ValueError:
        return ""
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        return ""
    hostname = (parts.hostname or "").lower()
    if not hostname:
        return ""
    try:
        port = parts.port
    except ValueError:
        return ""
    netloc = hostname
    if parts.username or parts.password:
        return ""
    if port and not ((parts.scheme.lower() == "http" and port == 80) or (parts.scheme.lower() == "https" and port == 443)):
        netloc = f"{netloc}:{port}"
    query = [
        (key, val)
        for key, val in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMS and not key.lower().startswith("utm_")
    ]
    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), netloc, path, urlencode(sorted(query)), ""))


def normalize_title(value: str | None) -> str:
    value = clean_text(value, 300).lower()
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def content_hash(title: str, summary: str, url: str = "") -> str:
    basis = "|".join((normalize_title(title), clean_text(summary, 1200).lower(), normalize_url(url)))
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]


def _number(value: str) -> float | None:
    try:
        return float(value.replace(",", ""))
    except ValueError:
        return None


def extract_discount(text: str) -> float | None:
    patterns = [
        r"(?:save|discount|割引)[^0-9]{0,20}(\d{1,3}(?:\.\d+)?)\s*%",
        r"(\d{1,3}(?:\.\d+)?)\s*%\s*(?:off|discount|割引)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            value = float(match.group(1))
            if 0 <= value <= 100:
                return value
    return None


def extract_prices(text: str) -> tuple[float | None, float | None, str | None]:
    patterns = [
        (r"\$\s*([0-9]+(?:,[0-9]{3})*(?:\.\d+)?)", "USD"),
        (r"(?:USD|US\$)\s*([0-9]+(?:,[0-9]{3})*(?:\.\d+)?)", "USD"),
        (r"€\s*([0-9]+(?:,[0-9]{3})*(?:\.\d+)?)", "EUR"),
        (r"£\s*([0-9]+(?:,[0-9]{3})*(?:\.\d+)?)", "GBP"),
        (r"(?:JPY|円)\s*([0-9]+(?:,[0-9]{3})*)", "JPY"),
    ]
    values: list[tuple[float, str]] = []
    for pattern, currency in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            parsed = _number(match.group(1))
            if parsed is not None:
                values.append((parsed, currency))
    if not values:
        return None, None, None
    currency = values[0][1]
    # When a source states both old and new prices, the larger value is treated
    # as original and the smaller as current. A single price is current.
    numbers = [value for value, item_currency in values if item_currency == currency]
    if len(numbers) >= 2 and max(numbers) != min(numbers):
        return max(numbers), min(numbers), currency
    return None, numbers[0], currency


def extract_affiliate(text: str) -> tuple[float | None, str | None, int | None]:
    lower = text.lower()
    if not any(word in lower for word in ("affiliate", "partner program", "referral")):
        return None, None, None
    rate: float | None = None
    match = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%", text)
    if match:
        parsed = float(match.group(1))
        if 0 <= parsed <= 100:
            rate = parsed
    affiliate_type = "recurring" if any(word in lower for word in ("recurring", "recurr", "monthly commission")) else "one_time"
    cookie_days: int | None = None
    cookie = re.search(r"(?:cookie|クッキー)[^\d]{0,15}(\d{1,3})\s*(?:day|days|日)", lower)
    if cookie:
        cookie_days = int(cookie.group(1))
    return rate, affiliate_type, cookie_days


def extract_deadline(text: str, now: datetime | None = None) -> str | None:
    now = now or datetime.now(timezone.utc)
    lower = text.lower()
    if any(term in lower for term in ("limited time", "ends soon", "ending soon", "期間限定", "まもなく終了")):
        return "期限が近い可能性あり"
    match = re.search(r"(?:until|ends?|expires?|through|終了)[^\d]{0,10}(\d{4}[-/]\d{1,2}[-/]\d{1,2})", lower)
    if match:
        raw = match.group(1).replace("/", "-")
        try:
            parsed = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return parsed.date().isoformat()
        except ValueError:
            return raw
    if re.search(r"\b(?:this week|今週)\b", lower):
        return (now + timedelta(days=7)).date().isoformat()
    return None


def infer_category(title: str, summary: str) -> str:
    text = f"{title} {summary}".lower()
    if any(word in text for word in ("lifetime deal", "lifetime access", "買い切り", "生涯")):
        return "lifetime_deal"
    if any(word in text for word in ("affiliate", "partner program", "referral program", "アフィリエイト")):
        return "affiliate_program"
    if any(word in text for word in ("discount", "% off", "sale", "black friday", "cyber monday", "割引", "セール")):
        return "discount"
    if any(word in text for word in ("free credit", "free credits", "free plan", "free tier", "無料枠", "無料クレジット", "free trial")):
        return "free_credit"
    if any(word in text for word in ("pricing", "price change", "price increase", "plan change", "料金", "値上げ", "プラン変更")):
        return "pricing_change"
    return "other"


def make_opportunity(raw: dict[str, str | None], now_iso: str) -> Opportunity | None:
    title = clean_text(raw.get("title"), 300)
    url = normalize_url(raw.get("url"))
    if not title or not url:
        return None
    summary = clean_text(raw.get("summary"), 1600)
    source = clean_text(raw.get("source"), 120) or "unknown"
    category = infer_category(title, summary)
    text = f"{title}. {summary}"
    original_price, current_price, currency = extract_prices(text)
    discount = extract_discount(text)
    affiliate_rate, affiliate_type, cookie_days = extract_affiliate(text)
    deadline = extract_deadline(text)
    identifier = hashlib.sha256(f"{source}|{normalize_title(title)}|{url}".encode("utf-8")).hexdigest()[:20]
    return Opportunity(
        id=identifier,
        title=title,
        url=url,
        source=source,
        discovered_at=now_iso,
        last_seen_at=now_iso,
        category=category,
        original_price=original_price,
        current_price=current_price,
        currency=currency,
        discount=discount,
        affiliate_rate=affiliate_rate,
        affiliate_type=affiliate_type,
        cookie_days=cookie_days,
        deadline=deadline,
        content_hash=content_hash(title, summary, url),
        canonical_url=url,
        published_at=raw.get("published_at"),
        summary=summary,
        evidence=clean_text(raw.get("evidence") or summary, 500),
    )
