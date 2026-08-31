from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from urllib import robotparser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

from .config import Settings
from .normalize import clean_text


class SourceError(RuntimeError):
    """A source failed without making the whole radar fail."""


class RequestBudgetExceeded(SourceError):
    """The run reached its configured HTTP request ceiling."""


@dataclass(frozen=True)
class SourceSpec:
    id: str
    name: str
    kind: str
    url: str
    protocol: str
    official: bool = False
    max_items: int = 24
    notes: str = ""


# These are purpose-built public RSS/API endpoints. The collector does not
# crawl search-result pages or bypass login, paywalls, CAPTCHAs, or robots.
SOURCE_SPECS: tuple[SourceSpec, ...] = (
    SourceSpec(
        "hn_ai_saas",
        "Hacker News: AI SaaS",
        "hn_algolia",
        "https://hn.algolia.com/api/v1/search_by_date?query=AI%20SaaS&tags=story&hitsPerPage=30",
        "public JSON API",
        max_items=24,
        notes="Public search endpoint; titles and excerpts only.",
    ),
    SourceSpec(
        "hn_lifetime_deal",
        "Hacker News: lifetime deal",
        "hn_algolia",
        "https://hn.algolia.com/api/v1/search_by_date?query=lifetime%20deal&tags=story&hitsPerPage=30",
        "public JSON API",
        max_items=24,
        notes="Public search endpoint; titles and excerpts only.",
    ),
    SourceSpec(
        "hn_affiliate_program",
        "Hacker News: affiliate program",
        "hn_algolia",
        "https://hn.algolia.com/api/v1/search_by_date?query=affiliate%20program&tags=story&hitsPerPage=30",
        "public JSON API",
        max_items=24,
        notes="Public search endpoint; titles and excerpts only.",
    ),
    SourceSpec(
        "hn_pricing",
        "Hacker News: pricing",
        "hn_algolia",
        "https://hn.algolia.com/api/v1/search_by_date?query=AI%20pricing&tags=story&hitsPerPage=30",
        "public JSON API",
        max_items=24,
        notes="Public search endpoint; titles and excerpts only.",
    ),
    SourceSpec(
        "github_ai_repositories",
        "GitHub: AI repositories",
        "github_search",
        "https://api.github.com/search/repositories?q=topic%3Aartificial-intelligence%20pushed%3A%3E2026-01-01&sort=updated&order=desc&per_page=30",
        "official public API",
        official=True,
        max_items=24,
        notes="Public repository metadata only; no authenticated API needed.",
    ),
    SourceSpec(
        "github_n8n_releases",
        "GitHub Releases: n8n",
        "github_releases",
        "https://api.github.com/repos/n8n-io/n8n/releases?per_page=20",
        "official public API",
        official=True,
        max_items=20,
        notes="Official release metadata; no source-code download.",
    ),
    SourceSpec(
        "github_flowise_releases",
        "GitHub Releases: Flowise",
        "github_releases",
        "https://api.github.com/repos/FlowiseAI/Flowise/releases?per_page=20",
        "official public API",
        official=True,
        max_items=20,
        notes="Official release metadata; no source-code download.",
    ),
    SourceSpec(
        "github_openwebui_releases",
        "GitHub Releases: Open WebUI",
        "github_releases",
        "https://api.github.com/repos/open-webui/open-webui/releases?per_page=20",
        "official public API",
        official=True,
        max_items=20,
        notes="Official release metadata; no source-code download.",
    ),
    SourceSpec(
        "github_litellm_releases",
        "GitHub Releases: LiteLLM",
        "github_releases",
        "https://api.github.com/repos/BerriAI/litellm/releases?per_page=20",
        "official public API",
        official=True,
        max_items=20,
        notes="Official release metadata; no source-code download.",
    ),
    SourceSpec(
        "cloudflare_blog",
        "Cloudflare Blog",
        "rss",
        "https://blog.cloudflare.com/rss/",
        "official RSS",
        official=True,
        max_items=20,
        notes="RSS feed; no HTML crawling.",
    ),
    SourceSpec(
        "zapier_blog",
        "Zapier Blog",
        "rss",
        "https://zapier.com/blog/feed/",
        "official RSS",
        official=True,
        max_items=20,
        notes="RSS feed; no HTML crawling.",
    ),
    SourceSpec(
        "product_hunt_feed",
        "Product Hunt feed",
        "rss",
        "https://www.producthunt.com/feed",
        "public Atom feed",
        max_items=20,
        notes="Public feed; if unavailable, the source is skipped.",
    ),
    SourceSpec(
        "appsumo_feed",
        "AppSumo feed",
        "rss",
        "https://appsumo.com/rss/",
        "public RSS feed",
        max_items=20,
        notes="Public feed; if unavailable, the source is skipped.",
    ),
    SourceSpec(
        "n8n_pricing_page",
        "n8n official pricing",
        "official_page",
        "https://n8n.io/pricing/",
        "official public page",
        official=True,
        max_items=2,
        notes="One official pricing page request; no site-wide crawl.",
    ),
    SourceSpec(
        "zapier_pricing_page",
        "Zapier official pricing",
        "official_page",
        "https://zapier.com/pricing",
        "official public page",
        official=True,
        max_items=2,
        notes="One official pricing page request; no site-wide crawl.",
    ),
    SourceSpec(
        "make_pricing_page",
        "Make official pricing",
        "official_page",
        "https://www.make.com/en/pricing",
        "official public page",
        official=True,
        max_items=2,
        notes="One official pricing page request; no site-wide crawl.",
    ),
    SourceSpec(
        "cloudflare_workers_ai_pricing",
        "Cloudflare Workers AI official pricing",
        "official_page",
        "https://developers.cloudflare.com/workers-ai/platform/pricing/",
        "official public page",
        official=True,
        max_items=2,
        notes="One official pricing page request; no site-wide crawl.",
    ),
    SourceSpec(
        "n8n_affiliate_page",
        "n8n official affiliate program",
        "official_page",
        "https://n8n.io/affiliates/",
        "official public page",
        official=True,
        max_items=2,
        notes="One official affiliate page request; public program terms only.",
    ),
    SourceSpec(
        "hubspot_affiliate_page",
        "HubSpot official affiliate program",
        "official_page",
        "https://www.hubspot.com/partners/affiliates",
        "official public page",
        official=True,
        max_items=2,
        notes="One official affiliate page request; public program terms only.",
    ),
)


def _iso_datetime(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        return parsed.isoformat()
    except (TypeError, ValueError, OverflowError):
        return value[:80]


class HttpClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.request_count = 0
        self.retry_count = 0
        self._robots: dict[str, bool] = {}

    def robots_allowed(self, url: str) -> bool:
        """Respect an explicit robots Disallow before reading a source."""
        parts = urlsplit(url)
        origin_key = urlunsplit((parts.scheme, parts.netloc, "", "", ""))
        if origin_key in self._robots:
            return self._robots[origin_key]
        robots_url = f"{origin_key}/robots.txt"
        try:
            payload, status = self.get(robots_url, "text/plain, text/*;q=0.5")
            if status == "404":
                self._robots[origin_key] = True
                return True
            parser = robotparser.RobotFileParser()
            parser.set_url(robots_url)
            parser.parse(payload.splitlines())
            allowed = parser.can_fetch("AI-Value-Radar/0.1", url)
        except SourceError:
            # An unavailable robots file is not evidence of permission to
            # crawl, so the source is skipped conservatively.
            allowed = False
        self._robots[origin_key] = allowed
        return allowed

    def get(self, url: str, accept: str) -> tuple[str, str]:
        last_error: Exception | None = None
        attempts = 1 + min(1, 1)  # one retry maximum, intentionally explicit
        for attempt in range(attempts):
            if self.request_count >= self.settings.max_http_requests:
                raise RequestBudgetExceeded("HTTP request budget reached")
            self.request_count += 1
            request = Request(
                url,
                headers={
                    "Accept": accept,
                    "User-Agent": "AI-Value-Radar/0.1 (+public-feed-reader)",
                },
                method="GET",
            )
            try:
                with urlopen(request, timeout=self.settings.request_timeout_seconds) as response:
                    payload = response.read(1_500_000)
                    charset = response.headers.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace"), str(response.status)
            except HTTPError as exc:
                last_error = exc
                if url.endswith("/robots.txt") and exc.code == 404:
                    return "", "404"
                if exc.code not in {408, 425, 429, 500, 502, 503, 504} or attempt + 1 >= attempts:
                    raise SourceError(f"HTTP {exc.code}") from None
            except (URLError, TimeoutError, OSError) as exc:
                last_error = exc
                if attempt + 1 >= attempts:
                    raise SourceError(f"network error: {type(exc).__name__}") from None
            self.retry_count += 1
            time.sleep(0.2)
        raise SourceError(f"request failed: {type(last_error).__name__ if last_error else 'unknown'}")


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _child_text(element: ET.Element, *names: str) -> str:
    wanted = {name.lower() for name in names}
    for child in element:
        if _local_name(child.tag) in wanted and child.text:
            return child.text.strip()
    return ""


def _child_link(element: ET.Element) -> str:
    for child in element:
        if _local_name(child.tag) == "link":
            href = child.attrib.get("href")
            if href:
                return href.strip()
            if child.text:
                return child.text.strip()
    return ""


def parse_feed(payload: str, source_id: str) -> list[dict[str, str | None]]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise SourceError("invalid RSS/Atom XML") from exc
    entries = [element for element in root.iter() if _local_name(element.tag) in {"item", "entry"}]
    results: list[dict[str, str | None]] = []
    for entry in entries:
        title = _child_text(entry, "title")
        link = _child_link(entry)
        summary = _child_text(entry, "description", "summary", "content", "encoded")
        published = _child_text(entry, "pubdate", "published", "updated", "date")
        if title and link:
            results.append(
                {
                    "title": title,
                    "url": link,
                    "summary": summary,
                    "published_at": _iso_datetime(published),
                    "source": source_id,
                    "evidence": summary or title,
                }
            )
    return results


def fetch_source(client: HttpClient, spec: SourceSpec) -> list[dict[str, str | None]]:
    if spec.kind == "rss":
        payload, _ = client.get(spec.url, "application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.8")
        return parse_feed(payload, spec.id)[: spec.max_items]

    if spec.kind == "official_page":
        payload, _ = client.get(spec.url, "text/html, application/xhtml+xml;q=0.9")
        title_match = re.search(r"<title[^>]*>(.*?)</title>", payload, flags=re.IGNORECASE | re.DOTALL)
        meta_match = re.search(
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
            payload,
            flags=re.IGNORECASE | re.DOTALL,
        )
        title = clean_text(title_match.group(1) if title_match else spec.name, 300)
        meta_summary = clean_text(meta_match.group(1) if meta_match else "", 800)
        visible_summary = clean_text(payload, 1400)
        summary = clean_text(f"{meta_summary} {visible_summary}", 1600)
        if not summary:
            summary = title
        return [
            {
                "title": title,
                "url": spec.url,
                "summary": summary,
                "published_at": None,
                "source": spec.id,
                "evidence": summary,
            }
        ]

    payload, _ = client.get(spec.url, "application/json")
    try:
        data: Any = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise SourceError("invalid JSON") from exc

    if spec.kind == "hn_algolia":
        results = []
        for item in data.get("hits", []) if isinstance(data, dict) else []:
            title = item.get("title") or item.get("story_title") or ""
            url = item.get("url") or item.get("story_url") or ""
            summary = item.get("story_text") or item.get("comment_text") or ""
            if title and url:
                results.append(
                    {
                        "title": str(title),
                        "url": str(url),
                        "summary": str(summary),
                        "published_at": str(item.get("created_at") or "") or None,
                        "source": spec.id,
                        "evidence": str(summary) or str(title),
                    }
                )
        return results[: spec.max_items]

    if spec.kind == "github_search":
        results = []
        for item in data.get("items", []) if isinstance(data, dict) else []:
            title = item.get("full_name") or item.get("name") or ""
            url = item.get("html_url") or ""
            summary = item.get("description") or ""
            if title and url:
                results.append(
                    {
                        "title": str(title),
                        "url": str(url),
                        "summary": str(summary),
                        "published_at": str(item.get("pushed_at") or "") or None,
                        "source": spec.id,
                        "evidence": str(summary) or str(title),
                    }
                )
        return results[: spec.max_items]

    if spec.kind == "github_releases":
        results = []
        for item in data if isinstance(data, list) else []:
            title = item.get("name") or item.get("tag_name") or ""
            url = item.get("html_url") or ""
            summary = item.get("body") or ""
            if title and url:
                results.append(
                    {
                        "title": str(title),
                        "url": str(url),
                        "summary": str(summary),
                        "published_at": str(item.get("published_at") or "") or None,
                        "source": spec.id,
                        "evidence": str(summary) or str(title),
                    }
                )
        return results[: spec.max_items]

    raise SourceError(f"unsupported source kind: {spec.kind}")


def collect_candidates(settings: Settings) -> tuple[list[dict[str, str | None]], dict[str, Any], list[dict[str, str]]]:
    client = HttpClient(settings)
    raw: list[dict[str, str | None]] = []
    source_stats: dict[str, Any] = {}
    errors: list[dict[str, str]] = []
    for spec in SOURCE_SPECS:
        started = time.monotonic()
        try:
            if not client.robots_allowed(spec.url):
                raise SourceError("robots.txt disallows or is unavailable")
            items = fetch_source(client, spec)
            raw.extend(items)
            source_stats[spec.id] = {
                "name": spec.name,
                "kind": spec.kind,
                "protocol": spec.protocol,
                "official": spec.official,
                "status": "ok",
                "items": len(items),
                "seconds": round(time.monotonic() - started, 2),
            }
        except Exception as exc:
            message = str(exc)[:160]
            source_stats[spec.id] = {
                "name": spec.name,
                "kind": spec.kind,
                "protocol": spec.protocol,
                "official": spec.official,
                "status": "error",
                "items": 0,
                "seconds": round(time.monotonic() - started, 2),
            }
            errors.append({"source": spec.id, "message": message})
    source_stats["_meta"] = {
        "registered": len(SOURCE_SPECS),
        "succeeded": sum(1 for value in source_stats.values() if isinstance(value, dict) and value.get("status") == "ok"),
        "failed": len(errors),
        "http_requests": client.request_count,
        "http_retries": client.retry_count,
    }
    return raw, source_stats, errors
