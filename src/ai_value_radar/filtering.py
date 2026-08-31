from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from .models import Opportunity
from .normalize import normalize_title, normalize_url


IMPORTANT_FIELDS = (
    "category",
    "original_price",
    "current_price",
    "discount",
    "affiliate_rate",
    "affiliate_type",
    "cookie_days",
    "deadline",
    "content_hash",
)


def _similar(a: str, b: str) -> bool:
    if not a or not b:
        return False
    return SequenceMatcher(None, a, b).ratio() >= 0.92


def find_match(item: Opportunity, history: list[dict[str, Any]]) -> dict[str, Any] | None:
    item_url = normalize_url(item.canonical_url or item.url)
    item_title = normalize_title(item.title)
    for old in history:
        if normalize_url(str(old.get("canonical_url") or old.get("url") or "")) == item_url:
            return old
    for old in history:
        if old.get("content_hash") and old.get("content_hash") == item.content_hash:
            return old
    for old in history:
        if old.get("category") == item.category and _similar(item_title, normalize_title(str(old.get("title") or ""))):
            return old
    return None


def compare_item(item: Opportunity, old: dict[str, Any] | None) -> tuple[str, list[str]]:
    if old is None:
        return "new", []
    changed = [field for field in IMPORTANT_FIELDS if old.get(field) != getattr(item, field)]
    if changed:
        return "updated", changed
    return "duplicate", []


def deduplicate_current(items: list[Opportunity]) -> tuple[list[Opportunity], int]:
    unique: list[Opportunity] = []
    urls: set[str] = set()
    hashes: set[str] = set()
    titles: list[str] = []
    duplicates = 0
    for item in items:
        url = normalize_url(item.canonical_url or item.url)
        title = normalize_title(item.title)
        if url in urls or (item.content_hash and item.content_hash in hashes) or any(
            item.category == existing.category and _similar(title, old_title)
            for existing, old_title in zip(unique, titles)
        ):
            duplicates += 1
            continue
        unique.append(item)
        urls.add(url)
        if item.content_hash:
            hashes.add(item.content_hash)
        titles.append(title)
    return unique, duplicates
