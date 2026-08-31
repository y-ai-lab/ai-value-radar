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
    service_name: str = ""


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
        "hn_ai_agents",
        "Hacker News: AI agents",
        "hn_algolia",
        "https://hn.algolia.com/api/v1/search_by_date?query=AI%20agents&tags=story&hitsPerPage=30",
        "public JSON API",
        max_items=24,
        notes="Public search endpoint; discovery only, not proof of vendor terms.",
    ),
    SourceSpec(
        "hn_open_source_ai",
        "Hacker News: open source AI",
        "hn_algolia",
        "https://hn.algolia.com/api/v1/search_by_date?query=open%20source%20AI&tags=story&hitsPerPage=30",
        "public JSON API",
        max_items=24,
        notes="Public search endpoint; discovery only, not proof of vendor terms.",
    ),
    SourceSpec(
        "hn_ai_automation",
        "Hacker News: AI automation",
        "hn_algolia",
        "https://hn.algolia.com/api/v1/search_by_date?query=AI%20automation&tags=story&hitsPerPage=30",
        "public JSON API",
        max_items=24,
        notes="Public search endpoint; discovery only, not proof of vendor terms.",
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
        service_name="n8n",
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
        service_name="Flowise",
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
        service_name="Open WebUI",
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
        service_name="LiteLLM",
    ),
    SourceSpec(
        "github_dify_releases",
        "GitHub Releases: Dify",
        "github_releases",
        "https://api.github.com/repos/langgenius/dify/releases?per_page=20",
        "official public API",
        official=True,
        max_items=20,
        notes="Official release metadata; no source-code download.",
        service_name="Dify",
    ),
    SourceSpec(
        "github_langflow_releases",
        "GitHub Releases: Langflow",
        "github_releases",
        "https://api.github.com/repos/langflow-ai/langflow/releases?per_page=20",
        "official public API",
        official=True,
        max_items=20,
        notes="Official release metadata; no source-code download.",
        service_name="Langflow",
    ),
    SourceSpec(
        "github_ollama_releases",
        "GitHub Releases: Ollama",
        "github_releases",
        "https://api.github.com/repos/ollama/ollama/releases?per_page=20",
        "official public API",
        official=True,
        max_items=20,
        notes="Official release metadata; no source-code download.",
        service_name="Ollama",
    ),
    SourceSpec(
        "github_anythingllm_releases",
        "GitHub Releases: AnythingLLM",
        "github_releases",
        "https://api.github.com/repos/Mintplex-Labs/anything-llm/releases?per_page=20",
        "official public API",
        official=True,
        max_items=20,
        notes="Official release metadata; no source-code download.",
        service_name="AnythingLLM",
    ),
    SourceSpec(
        "github_comfyui_releases",
        "GitHub Releases: ComfyUI",
        "github_releases",
        "https://api.github.com/repos/comfyanonymous/ComfyUI/releases?per_page=20",
        "official public API",
        official=True,
        max_items=20,
        notes="Official release metadata; no source-code download.",
        service_name="ComfyUI",
    ),
    SourceSpec(
        "github_vllm_releases",
        "GitHub Releases: vLLM",
        "github_releases",
        "https://api.github.com/repos/vllm-project/vllm/releases?per_page=20",
        "official public API",
        official=True,
        max_items=20,
        notes="Official release metadata; no source-code download.",
        service_name="vLLM",
    ),
    SourceSpec(
        "github_llamacpp_releases",
        "GitHub Releases: llama.cpp",
        "github_releases",
        "https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=20",
        "official public API",
        official=True,
        max_items=20,
        notes="Official release metadata; no source-code download.",
        service_name="llama.cpp",
    ),
    SourceSpec(
        "github_continue_releases",
        "GitHub Releases: Continue",
        "github_releases",
        "https://api.github.com/repos/continuedev/continue/releases?per_page=20",
        "official public API",
        official=True,
        max_items=20,
        notes="Official release metadata; no source-code download.",
        service_name="Continue",
    ),
    SourceSpec(
        "github_librechat_releases",
        "GitHub Releases: LibreChat",
        "github_releases",
        "https://api.github.com/repos/danny-avila/LibreChat/releases?per_page=20",
        "official public API",
        official=True,
        max_items=20,
        notes="Official release metadata; no source-code download.",
        service_name="LibreChat",
    ),
    SourceSpec(
        "github_ragflow_releases",
        "GitHub Releases: RAGFlow",
        "github_releases",
        "https://api.github.com/repos/infiniflow/ragflow/releases?per_page=20",
        "official public API",
        official=True,
        max_items=20,
        notes="Official release metadata; no source-code download.",
        service_name="RAGFlow",
    ),
    SourceSpec(
        "github_autogen_releases",
        "GitHub Releases: AutoGen",
        "github_releases",
        "https://api.github.com/repos/microsoft/autogen/releases?per_page=20",
        "official public API",
        official=True,
        max_items=20,
        notes="Official release metadata; no source-code download.",
        service_name="AutoGen",
    ),
    SourceSpec(
        "github_crewai_releases",
        "GitHub Releases: CrewAI",
        "github_releases",
        "https://api.github.com/repos/crewAIInc/crewAI/releases?per_page=20",
        "official public API",
        official=True,
        max_items=20,
        notes="Official release metadata; no source-code download.",
        service_name="CrewAI",
    ),
    SourceSpec(
        "github_langchain_releases",
        "GitHub Releases: LangChain",
        "github_releases",
        "https://api.github.com/repos/langchain-ai/langchain/releases?per_page=20",
        "official public API",
        official=True,
        max_items=20,
        notes="Official release metadata; no source-code download.",
        service_name="LangChain",
    ),
    SourceSpec(
        "github_llamaindex_releases",
        "GitHub Releases: LlamaIndex",
        "github_releases",
        "https://api.github.com/repos/run-llama/llama_index/releases?per_page=20",
        "official public API",
        official=True,
        max_items=20,
        notes="Official release metadata; no source-code download.",
        service_name="LlamaIndex",
    ),
    SourceSpec(
        "github_browseruse_releases",
        "GitHub Releases: Browser Use",
        "github_releases",
        "https://api.github.com/repos/browser-use/browser-use/releases?per_page=20",
        "official public API",
        official=True,
        max_items=20,
        notes="Official release metadata; no source-code download.",
        service_name="Browser Use",
    ),
    SourceSpec(
        "github_aider_releases",
        "GitHub Releases: Aider",
        "github_releases",
        "https://api.github.com/repos/Aider-AI/aider/releases?per_page=20",
        "official public API",
        official=True,
        max_items=20,
        notes="Official release metadata; no source-code download.",
        service_name="Aider",
    ),
    SourceSpec(
        "github_gradio_releases",
        "GitHub Releases: Gradio",
        "github_releases",
        "https://api.github.com/repos/gradio-app/gradio/releases?per_page=20",
        "official public API",
        official=True,
        max_items=20,
        notes="Official release metadata; no source-code download.",
        service_name="Gradio",
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
        service_name="Cloudflare",
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
        service_name="Zapier",
    ),
    SourceSpec(
        "openai_news",
        "OpenAI News",
        "rss",
        "https://openai.com/news/rss.xml",
        "official RSS",
        official=True,
        max_items=20,
        notes="Official news feed; RSS only, no HTML crawling.",
        service_name="OpenAI",
    ),
    SourceSpec(
        "google_ai_blog",
        "Google AI Blog",
        "rss",
        "https://blog.google/technology/ai/rss/",
        "official RSS",
        official=True,
        max_items=20,
        notes="Official technology feed; RSS only, no HTML crawling.",
        service_name="Google AI",
    ),
    SourceSpec(
        "aws_machine_learning_blog",
        "AWS Machine Learning Blog",
        "rss",
        "https://aws.amazon.com/blogs/machine-learning/feed/",
        "official RSS",
        official=True,
        max_items=20,
        notes="Official AWS feed; RSS only, no HTML crawling.",
        service_name="AWS Machine Learning",
    ),
    SourceSpec(
        "huggingface_blog",
        "Hugging Face Blog",
        "rss",
        "https://huggingface.co/blog/feed.xml",
        "official RSS",
        official=True,
        max_items=20,
        notes="Official blog feed; RSS only, no HTML crawling.",
        service_name="Hugging Face",
    ),
    SourceSpec(
        "google_deepmind_blog",
        "Google DeepMind Blog",
        "rss",
        "https://deepmind.google/blog/rss.xml",
        "official RSS",
        official=True,
        max_items=20,
        notes="Official blog feed; RSS only, no HTML crawling.",
        service_name="Google DeepMind",
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


GITHUB_SERVICE_NAMES = {
    "n8n-io/n8n": "n8n",
    "flowiseai/flowise": "Flowise",
    "open-webui/open-webui": "Open WebUI",
    "berriai/litellm": "LiteLLM",
    "langgenius/dify": "Dify",
    "langflow-ai/langflow": "Langflow",
    "ollama/ollama": "Ollama",
    "mintplex-labs/anything-llm": "AnythingLLM",
    "comfyanonymous/comfyui": "ComfyUI",
    "vllm-project/vllm": "vLLM",
    "ggml-org/llama.cpp": "llama.cpp",
    "continuedev/continue": "Continue",
    "danny-avila/librechat": "LibreChat",
    "infiniflow/ragflow": "RAGFlow",
    "microsoft/autogen": "AutoGen",
    "crewaiinc/crewai": "CrewAI",
    "langchain-ai/langchain": "LangChain",
    "run-llama/llama_index": "LlamaIndex",
    "browser-use/browser-use": "Browser Use",
    "aider-ai/aider": "Aider",
    "gradio-app/gradio": "Gradio",
}
GITHUB_PROJECT_SUMMARIES = {
    "n8n": "Gmailやスプレッドシートなどをつなぎ、繰り返し作業を自動化するツール。",
    "Flowise": "AIチャットボットの処理を、ブロックをつなぐように組み立てるツール。",
    "Open WebUI": "自分で用意したAIを、ChatGPTのような画面から使えるようにするツール。",
    "LiteLLM": "ChatGPTやClaudeなど複数のAIを、同じ形式で扱いやすくする中継ツール。",
    "Dify": "AIチャットボットや小さなAIアプリを作り、動かすための土台。",
    "Langflow": "AIエージェントの処理を、画面上で部品をつないで組み立てるツール。",
    "Ollama": "自分のPC上でAIモデルを動かし、管理するためのツール。",
    "AnythingLLM": "手元の文書を読み込ませ、資料について質問できるAIを作るツール。",
    "ComfyUI": "画像生成の手順を部品ごとにつなぎ、細かく調整する制作ツール。",
    "vLLM": "大規模言語モデルを効率よく動かし、APIとして提供するための基盤。",
    "llama.cpp": "PCや比較的小さな環境でもAIモデルを動かしやすくする実装。",
    "Continue": "エディタの中でAIにコードの説明や修正を頼める開発支援ツール。",
    "LibreChat": "複数のAIモデルを一つの画面で使えるオープンソースのチャット環境。",
    "RAGFlow": "資料を読み込ませ、検索と生成を組み合わせたAIアプリを作る基盤。",
    "AutoGen": "複数のAIエージェントを組み合わせて処理を組み立てる開発フレームワーク。",
    "CrewAI": "役割の違うAIエージェントをチームのように動かすためのフレームワーク。",
    "LangChain": "LLM、データ、外部ツールを組み合わせてAIアプリを作る開発基盤。",
    "LlamaIndex": "自分の文書やデータをAIから扱いやすくする連携・検索基盤。",
    "Browser Use": "AIエージェントからブラウザ操作を扱いやすくする開発ツール。",
    "Aider": "ターミナル上でAIと相談しながらコードを編集する開発ツール。",
    "Gradio": "AIモデルのデモや小さなWebアプリを素早く公開するためのライブラリ。",
}
GITHUB_PROJECT_USE_HINTS = {
    "n8n": "定型業務の自動化や、複数サービスの連携を試したい人向け。",
    "Flowise": "社内FAQや問い合わせ対応のAIチャットを試したい人向け。",
    "Open WebUI": "自分用・チーム用のAIチャット環境を試したい人向け。",
    "LiteLLM": "複数のAIを使い分ける仕組みや、AIアプリの裏側を試したい人向け。",
    "Dify": "AIチャットボットや小さなAIサービスを作って試したい人向け。",
    "Langflow": "AIエージェントの流れを見える形で組み立てたい人向け。",
    "Ollama": "PC上でAIを試したい人や、外部サービスにデータを送らず検証したい人向け。",
    "AnythingLLM": "自分の資料を使ったFAQやナレッジ検索を試したい人向け。",
    "ComfyUI": "画像生成の手順を細かく調整したい人や、制作を自動化したい人向け。",
    "vLLM": "自分のAIモデルをAPI化したい開発者や、推論速度を検証したい人向け。",
    "llama.cpp": "PC上でローカルAIを試したい人や、外部送信なしで検証したい人向け。",
    "Continue": "AIを使ったコーディングや、エディタ作業の効率化を試したい人向け。",
    "LibreChat": "複数のAIを一つの画面で比較したい人や、自分用環境を作りたい人向け。",
    "RAGFlow": "自分の資料を使った検索・FAQ・社内ナレッジ活用を試したい人向け。",
    "AutoGen": "AIエージェント同士の連携や自動処理を開発したい人向け。",
    "CrewAI": "役割分担するAIエージェントの仕組みを試したい人向け。",
    "LangChain": "AIアプリの連携や、外部ツールを呼ぶ処理を作りたい人向け。",
    "LlamaIndex": "自分の文書やデータをAIに読ませる仕組みを試したい人向け。",
    "Browser Use": "ブラウザ操作をAIに任せる仕組みを検証したい人向け。",
    "Aider": "AIと相談しながらコードを書いたり直したりしたい人向け。",
    "Gradio": "AIの試作品を簡単な画面にして、人に試してもらいたい人向け。",
}


def _humanize_repo_name(value: str) -> str:
    value = re.sub(r"[-_]+", " ", value).strip()
    return value.title() if value else "GitHubプロジェクト"


def _github_use_hint(text: str) -> str:
    lower = text.lower()
    if any(word in lower for word in ("workflow", "automation", "zapier", "n8n", "flowise")):
        return "業務自動化や複数サービスの連携を試したい人向け。"
    if any(word in lower for word in ("chat", "chatbot", "llm", "language model", "rag")):
        return "AIチャット、LLM、社内ナレッジ活用を試したい人向け。"
    if any(word in lower for word in ("image", "video", "diffusion", "comfyui")):
        return "画像・動画生成やクリエイティブ制作を試したい人向け。"
    if any(word in lower for word in ("agent", "machine learning", "artificial intelligence", "ai")):
        return "AI開発や新しいAI活用を試したい人向け。"
    return "GitHub上の公開プロジェクトを試したい開発者・検証者向け。"


def _github_release_summary(service_name: str, release_title: str, tag_name: str, body: str) -> str:
    """Turn a raw Markdown release body into a short reader-facing summary."""
    service = service_name or "GitHub公開プロジェクト"
    release_label = tag_name or release_title or "新しいリリース"
    plain = clean_text(body, 900)
    plain = re.sub(r"#{1,6}\s*", "", plain)
    plain = re.sub(r"\s[*-]\s+", " ", plain)
    plain = re.sub(r"\s+", " ", plain).strip()
    if plain:
        # Keep the reader-facing line compact. The full public excerpt remains
        # in evidence and can be checked from the official release URL.
        plain = plain[:220].rstrip()
        if len(plain) == 220:
            plain += "…"
        return f"{service}の公式GitHubリリース（{release_label}）です。主な変更：{plain}"
    return f"{service}の公式GitHubリリース（{release_label}）です。詳しい変更点は公式リリースページで確認できます。"


def _github_details(
    full_name: str,
    name: str,
    description: str,
    language: str,
    topics: list[str],
    stars: Any = None,
    homepage: str = "",
    release: bool = False,
    service_name: str = "",
) -> dict[str, Any]:
    key = full_name.strip().lower()
    display_name = service_name or GITHUB_SERVICE_NAMES.get(key) or _humanize_repo_name(name or full_name.rsplit("/", 1)[-1])
    project_type = "公式GitHubリリース" if release else "GitHub公開AIプロジェクト"
    description = clean_text(description, 800)
    base_summary = GITHUB_PROJECT_SUMMARIES.get(display_name) or f"{display_name}の公開プロジェクト。GitHub上で更新履歴と利用方法を確認できます。"
    if release:
        project_summary = base_summary
    else:
        project_summary = description or base_summary
    context = f"{display_name} {description} {' '.join(topics)}"
    try:
        star_count = int(stars) if stars is not None else None
    except (TypeError, ValueError):
        star_count = None
    return {
        "service_name": display_name,
        "project_type": project_type,
        "project_summary": project_summary,
        "project_use": GITHUB_PROJECT_USE_HINTS.get(display_name) or _github_use_hint(context),
        "github_owner": full_name.split("/", 1)[0] if "/" in full_name else "",
        "github_repository": full_name,
        "github_language": language or "",
        "github_stars": star_count,
        "github_topics": topics[:12],
        "github_homepage": homepage,
    }


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


def parse_feed(payload: str, source_id: str) -> list[dict[str, Any]]:
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


def fetch_source(client: HttpClient, spec: SourceSpec) -> list[dict[str, Any]]:
    if spec.kind == "rss":
        payload, _ = client.get(spec.url, "application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.8")
        items = parse_feed(payload, spec.id)[: spec.max_items]
        if spec.service_name:
            for item in items:
                item.setdefault("service_name", spec.service_name)
        return items

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
                "service_name": spec.service_name or spec.name,
                "project_type": "公式価格・Affiliate情報",
                "project_summary": meta_summary or title,
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
                full_name = str(item.get("full_name") or title)
                details = _github_details(
                    full_name,
                    str(item.get("name") or title),
                    str(summary),
                    str(item.get("language") or ""),
                    [str(topic) for topic in item.get("topics", []) if topic],
                    item.get("stargazers_count"),
                    str(item.get("homepage") or ""),
                )
                results.append({
                        "title": str(title),
                        "url": str(url),
                        "summary": str(summary),
                        "published_at": str(item.get("pushed_at") or "") or None,
                        "source": spec.id,
                        "evidence": str(summary) or str(title),
                        **details,
                    })
        return results[: spec.max_items]

    if spec.kind == "github_releases":
        results = []
        repo_match = re.search(r"/repos/([^/]+/[^/]+)/releases", spec.url)
        repository = repo_match.group(1) if repo_match else ""
        repository_name = repository.rsplit("/", 1)[-1] if repository else spec.service_name
        for item in data if isinstance(data, list) else []:
            title = item.get("name") or item.get("tag_name") or ""
            url = item.get("html_url") or ""
            release_body = item.get("body") or ""
            tag_name = item.get("tag_name") or ""
            if title and url:
                service_name = spec.service_name or repository_name
                summary = _github_release_summary(
                    service_name,
                    str(title),
                    str(tag_name),
                    str(release_body),
                )
                details = _github_details(
                    repository,
                    repository_name,
                    str(release_body),
                    "",
                    [],
                    None,
                    "",
                    release=True,
                    service_name=spec.service_name,
                )
                results.append({
                        "title": str(title),
                        "url": str(url),
                        "summary": str(summary),
                        "published_at": str(item.get("published_at") or "") or None,
                        "source": spec.id,
                        "evidence": str(release_body) or str(summary) or str(title),
                        **details,
                    })
        return results[: spec.max_items]

    raise SourceError(f"unsupported source kind: {spec.kind}")


def collect_candidates(settings: Settings) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, str]]]:
    client = HttpClient(settings)
    raw: list[dict[str, Any]] = []
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
