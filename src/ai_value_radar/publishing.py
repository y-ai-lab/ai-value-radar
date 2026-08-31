from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from .models import Opportunity
from .state import write_text_atomic
from .validation import outcome_label, validation_label
from .writer import display_name


CHANNELS = ("note", "x", "threads", "video")
CHANNEL_LABELS = {
    "note": "note",
    "x": "X",
    "threads": "Threads",
    "video": "短尺動画",
}

CONTENT_KEYWORDS = (
    "ai",
    "automation",
    "saas",
    "llm",
    "workflow",
    "release",
    "launched",
    "launch",
    "introducing",
    "new feature",
    "update",
    "pricing",
    "price",
    "free",
    "credit",
    "割引",
    "新機能",
    "リリース",
    "アップデート",
    "料金",
    "無料",
)
RELEVANCE_KEYWORDS = (
    "ai",
    "automation",
    "saas",
    "llm",
    "workflow",
    "image",
    "video",
    "文章",
    "自動化",
    "n8n",
    "flowise",
    "openwebui",
    "litellm",
    "zapier",
    "cloudflare",
    "dify",
    "langflow",
    "ollama",
    "anythingllm",
    "comfyui",
)
CONCRETE_CHANGE_KEYWORDS = (
    "release",
    "launched",
    "launch",
    "introducing",
    "new feature",
    "feature",
    "update",
    "pricing",
    "price",
    "free",
    "credit",
    "discount",
    "sale",
    "料金",
    "値上げ",
    "無料",
    "割引",
    "新機能",
    "リリース",
    "アップデート",
    "追加",
    "変更",
)
READER_IMPACT_KEYWORDS = (
    "price",
    "pricing",
    "free",
    "credit",
    "discount",
    "limit",
    "plan",
    "affiliate",
    "partner",
    "integration",
    "api",
    "workflow",
    "automation",
    "security",
    "docker",
    "performance",
    "speed",
    "support",
    "料金",
    "無料",
    "制限",
    "連携",
    "自動化",
    "安全",
    "高速",
)
GITHUB_SEARCH_NOISE_KEYWORDS = (
    "news",
    "satire",
    "satirical",
    "awesome",
    "guide",
    "list",
    "collection",
    "template",
    "course",
    "paper",
    "blog",
    "newsletter",
    "ニュース",
    "まとめ",
    "ガイド",
    "solver",
    "scheduling",
    "routing",
    "rostering",
    "optimization",
    "assignment",
)
GITHUB_SEARCH_TOOL_KEYWORDS = (
    "tool",
    "platform",
    "framework",
    "library",
    "assistant",
    "chatbot",
    "agent",
    "automation",
    "workflow",
    "llm",
    "model",
    "inference",
    "api",
    "integration",
    "developer",
    "自動化",
    "チャット",
)
PROJECT_CONTENT_ANGLES = {
    "n8n": "面倒な定型作業を一つ選び、n8nで自動化できるか試す。",
    "Flowise": "Flowiseで簡単なFAQチャットを作れるか、初心者目線で試す。",
    "Open WebUI": "自分用のAIチャット環境を作ると、何が便利になるか確認する。",
    "LiteLLM": "複数のAIを使い分けると、料金や機能の選択をどう整理できるか確認する。",
    "Dify": "Difyで小さなAIチャットボットを作り、仕事に使える範囲を試す。",
    "Langflow": "LangflowでAIエージェントの流れを組み、何が自動化できるか試す。",
    "Ollama": "自分のPCでAIを動かすと、何ができて何が難しいのか試す。",
    "AnythingLLM": "自分の資料を読ませたAIが、FAQや検索の代わりになるか試す。",
    "ComfyUI": "画像生成の手順を組み替えると、制作時間を減らせるか試す。",
}
PROJECT_READER_PROBLEMS = {
    "n8n": "毎回同じ入力・転記・通知をしていて、時間を取られている。",
    "Flowise": "AIチャットを作りたいが、コードを書かずに試す方法が分からない。",
    "Open WebUI": "AIを使いたいが、自分の用途に合う環境の作り方が分からない。",
    "LiteLLM": "ChatGPTやClaudeなどを使い分けたいが、管理方法が分からない。",
    "Dify": "AIを仕事に組み込みたいが、最初に何を作ればよいか分からない。",
    "Langflow": "AIエージェントの仕組みが見えにくく、試す手順が分からない。",
    "Ollama": "自分のPCでAIを動かせるか、難しさや必要な性能が分からない。",
    "AnythingLLM": "自分の資料をAIに読ませたいが、どのツールが合うか分からない。",
    "ComfyUI": "画像生成を細かく調整したいが、設定が複雑で始めにくい。",
}
PROJECT_READER_ACTIONS = {
    "n8n": "自分の転記・通知作業を一つ選び、公式ドキュメントを見ながら小さく試す。",
    "Flowise": "自分のよくある質問を3つ用意し、簡単なFAQチャットを試す。",
    "Open WebUI": "手元の環境と対応モデルを確認し、1つの質問だけで動作を試す。",
    "LiteLLM": "使いたいAIを2つ選び、同じ入力で結果と料金の違いを比べる。",
    "Dify": "自分の作業に関係する質問応答を1つだけ作り、動作を確認する。",
    "Langflow": "入力・AI処理・出力の3段階だけをつないで、流れを確認する。",
    "Ollama": "PCの性能と対応モデルを確認し、短い質問を一つだけ試す。",
    "AnythingLLM": "公開して問題ない資料を一つだけ読み込ませ、回答を確認する。",
    "ComfyUI": "画像生成の基本ワークフローを一つ動かし、変更点を一つだけ試す。",
}


def _one_line(value: str | None, limit: int = 180) -> str:
    text = " ".join((value or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _recent_bonus(published_at: str | None, now: datetime) -> int:
    if not published_at:
        return 0
    try:
        parsed = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return 0
    age = now.astimezone(timezone.utc) - parsed.astimezone(timezone.utc)
    if age < timedelta(days=2):
        return 15
    if age < timedelta(days=14):
        return 10
    if age < timedelta(days=45):
        return 4
    return 0


def _content_text(item: Opportunity) -> str:
    return " ".join(
        (
            item.title,
            item.summary,
            item.evidence,
            item.project_summary,
            item.source,
        )
    ).lower()


def _content_angle(item: Opportunity) -> str:
    name = _one_line(display_name(item), 80)
    text = _content_text(item)
    if item.category == "affiliate_program" or "affiliate" in text or "partner program" in text:
        return f"{name}を紹介する前に、報酬条件・Cookie期間・規約を確認する。"
    if item.category in {"lifetime_deal", "discount", "free_credit", "pricing_change"}:
        return f"{name}の料金・無料条件が、自分の用途で本当に得になるかを確認する。"
    if item.github_repository:
        if name in PROJECT_CONTENT_ANGLES:
            return PROJECT_CONTENT_ANGLES[name]
        summary = _one_line(item.project_summary or "AI向けの公開プロジェクト", 110).rstrip("。")
        return f"{name}は{summary}。自分の作業に使えるか、具体的な一例で確認する。"
    if any(word in text for word in ("new feature", "feature", "新機能", "update", "アップデート")):
        return f"{name}の新機能が、日々の作業をどれだけ減らせるかを実例で確認する。"
    return f"{name}が、どんな人のどんな作業に役立つのかを具体例で確認する。"


def _reader_problem(item: Opportunity) -> str:
    text = _content_text(item)
    if item.category == "affiliate_program" or "affiliate" in text or "partner program" in text:
        return "AIツールを紹介したいが、報酬条件や広告表記の確認方法が分からない。"
    if item.category in {"lifetime_deal", "discount", "free_credit", "pricing_change"}:
        return "AIツールの料金や無料枠が複雑で、自分に合う選び方が分からない。"
    if item.github_repository:
        return PROJECT_READER_PROBLEMS.get(
            _one_line(display_name(item), 80),
            "AIツールの名前は見つかるが、結局どの作業に使えるのか分からない。",
        )
    return "AIの情報は多いのに、自分の作業で試す方法まで落とし込めない。"


def _reader_action(item: Opportunity) -> str:
    if item.category == "affiliate_program" or item.affiliate_rate is not None:
        return "公式Affiliateページで報酬・Cookie・禁止事項を確認し、紹介できる条件だけメモする。"
    if item.github_repository:
        return PROJECT_READER_ACTIONS.get(
            _one_line(display_name(item), 80),
            "公式リポジトリの概要を確認し、自分の用途に合うかを一つだけ試す。",
        )
    return "公式ページで条件を確認し、自分の用途で一つだけ試して結果を記録する。"


def _content_grade(score: int) -> str:
    if score >= 65:
        return "発信候補"
    if score >= 45:
        return "要検証"
    return "参考ニュース"


def calculate_content_score(
    item: Opportunity,
    source_stats: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> int:
    """Score whether a fresh AI/SaaS item is worth turning into content.

    This is deliberately separate from the revenue score. It uses no AI and
    prefers recent, official, concrete changes so a quiet deal cycle does not
    stop the user's publishing pipeline.
    """
    text = _content_text(item)
    if not any(word in text for word in RELEVANCE_KEYWORDS):
        return 0
    if item.source == "github_ai_repositories":
        if not any(word in text for word in GITHUB_SEARCH_TOOL_KEYWORDS):
            return 0
        if any(word in text for word in GITHUB_SEARCH_NOISE_KEYWORDS):
            return 0
    source = (source_stats or {}).get(item.source, {})
    score = 0
    if isinstance(source, dict) and source.get("official") is True:
        score += 2 if source.get("kind") == "github_search" else 10
    if isinstance(source, dict) and source.get("kind") in {"rss", "github_releases", "official_page"}:
        score += 5
    if item.status == "new":
        score += 12
    elif item.status == "updated":
        score += 10
    has_concrete_change = any(word in text for word in CONCRETE_CHANGE_KEYWORDS)
    has_reader_impact = any(word in text for word in READER_IMPACT_KEYWORDS)
    if has_concrete_change:
        score += 18
    if has_reader_impact:
        score += 18
    if item.summary:
        score += 6
    if item.project_summary:
        score += 6
    if item.project_use:
        score += 5
    score += min(10, _recent_bonus(item.published_at, now or datetime.now(timezone.utc)))
    if item.category != "other":
        score += 6
    if item.github_repository and not has_reader_impact:
        score -= 12
    if item.source.startswith("hn_"):
        score -= 8
    if item.source == "github_ai_repositories":
        # Repository search is useful for discovery, but its results are not
        # automatically an official product announcement. Keep noisy or tiny
        # projects out of the main publishing lane while retaining them in
        # the collected history.
        score -= 15
        if item.github_stars is None or item.github_stars < 100:
            score -= 20
        elif item.github_stars >= 1000:
            score += 10
        else:
            score += 5
        if any(word in text for word in GITHUB_SEARCH_NOISE_KEYWORDS):
            score -= 30
    return max(0, min(100, score))


def select_publishing_topics(
    items: Iterable[Opportunity],
    source_stats: dict[str, Any] | None = None,
    excluded_ids: set[str] | None = None,
    limit: int = 2,
    min_score: int = 35,
    now: datetime | None = None,
) -> list[Opportunity]:
    excluded_ids = excluded_ids or set()
    selected: list[Opportunity] = []
    for item in items:
        if item.id in excluded_ids or item.status not in {"new", "updated"}:
            continue
        item.content_score = calculate_content_score(item, source_stats, now)
        item.content_angle = item.content_angle or _content_angle(item)
        item.reader_problem = item.reader_problem or _reader_problem(item)
        item.reader_action = item.reader_action or _reader_action(item)
        if item.content_score >= min_score:
            selected.append(item)
    selected.sort(key=lambda value: (value.content_score, value.confidence, value.title), reverse=True)
    limit = max(0, limit)
    if limit <= 1:
        return selected[:limit]
    # Prefer different services/sources so two consecutive releases from one
    # project do not occupy the whole publishing preview.
    diverse: list[Opportunity] = []
    seen_keys: set[str] = set()
    for item in selected:
        key = (item.service_name or item.source or display_name(item)).strip().lower()
        if key in seen_keys:
            continue
        seen_keys.add(key)
        diverse.append(item)
        if len(diverse) >= limit:
            return diverse
    for item in selected:
        if item not in diverse:
            diverse.append(item)
        if len(diverse) >= limit:
            break
    return diverse


def topic_metadata(item: Opportunity, pack: dict[str, Any] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": item.id,
        "code": item.id[:8],
        "title": _one_line(display_name(item), 180),
        "service_name": _one_line(item.service_name, 180),
        "project_type": _one_line(item.project_type, 180),
        "project_summary": _one_line(item.project_summary, 500),
        "project_use": _one_line(item.project_use, 260),
        "content_grade": _content_grade(item.content_score),
        "content_angle": _one_line(item.content_angle, 500),
        "reader_problem": _one_line(item.reader_problem, 400),
        "reader_action": _one_line(item.reader_action, 400),
        "monetization": _one_line(item.monetization, 500),
        "github_language": _one_line(item.github_language, 80),
        "github_stars": item.github_stars,
        "github_topics": item.github_topics[:12],
        "github_homepage": item.github_homepage,
        "url": item.url,
        "source": item.source,
        "content_score": item.content_score,
        "status": item.status,
        "usage_status": item.usage_status,
        "revenue_readiness": item.revenue_readiness,
        "validation_status": item.validation_status,
        "validation_updated_at": item.validation_updated_at,
        "outcome_status": item.outcome_status,
        "outcome_updated_at": item.outcome_updated_at,
        "post_url": item.post_url,
        "post_url_updated_at": item.post_url_updated_at,
        "views": item.views,
        "clicks": item.clicks,
        "signups": item.signups,
        "sales": item.sales,
        "revenue": item.revenue,
    }
    if pack:
        result.update({"pack_path": pack.get("path", ""), "pack_url": pack.get("url", "")})
    return result


def _new_channel_state() -> dict[str, dict[str, Any]]:
    return {channel: {"status": "ready"} for channel in CHANNELS}


def _match_queue_code(queue: list[dict[str, Any]], code: str) -> list[dict[str, Any]]:
    clean = code.strip().lower()
    if not clean:
        return []
    return [entry for entry in queue if str(entry.get("id", "")).lower() == clean or str(entry.get("id", "")).lower().startswith(clean)]


def upsert_content_queue(
    existing: Any,
    items: Iterable[Opportunity],
    packs: Iterable[dict[str, Any]],
    now_iso: str,
    max_items: int = 100,
) -> list[dict[str, Any]]:
    queue = [entry for entry in existing if isinstance(entry, dict) and entry.get("id")] if isinstance(existing, list) else []
    by_id = {str(entry["id"]): entry for entry in queue}
    pack_by_id = {str(pack.get("id")): pack for pack in packs if isinstance(pack, dict) and pack.get("id")}
    for item in items:
        pack = pack_by_id.get(item.id)
        if not pack:
            continue
        entry = by_id.get(item.id)
        if entry is None:
            entry = {
                "id": item.id,
                "code": item.id[:8],
                "created_at": now_iso,
                "status": "ready",
                "next_channel": "note",
                "channels": _new_channel_state(),
            }
            queue.append(entry)
            by_id[item.id] = entry
        entry.update(
            {
                "title": _one_line(display_name(item), 180),
                "service_name": _one_line(item.service_name, 180),
                "project_type": _one_line(item.project_type, 180),
                "project_summary": _one_line(item.project_summary, 500),
                "project_use": _one_line(item.project_use, 260),
                "content_grade": _content_grade(item.content_score),
                "content_angle": _one_line(item.content_angle, 500),
                "reader_problem": _one_line(item.reader_problem, 400),
                "reader_action": _one_line(item.reader_action, 400),
                "monetization": _one_line(item.monetization, 500),
                "github_language": _one_line(item.github_language, 80),
                "github_stars": item.github_stars,
                "github_topics": item.github_topics[:12],
                "github_homepage": item.github_homepage,
                "url": item.url,
                "source": item.source,
                "kind": pack.get("kind", "revenue"),
                "pack_path": pack.get("path", ""),
                "pack_url": pack.get("url", ""),
                "usage_status": item.usage_status,
                "content_score": item.content_score,
                "revenue_readiness": item.revenue_readiness,
                "validation_status": item.validation_status,
                "validation_updated_at": item.validation_updated_at,
                "outcome_status": item.outcome_status,
                "outcome_updated_at": item.outcome_updated_at,
                "post_url": item.post_url,
                "post_url_updated_at": item.post_url_updated_at,
                "views": item.views,
                "clicks": item.clicks,
                "signups": item.signups,
                "sales": item.sales,
                "revenue": item.revenue,
                "updated_at": now_iso,
            }
        )
        if not isinstance(entry.get("channels"), dict):
            entry["channels"] = _new_channel_state()
        for channel in CHANNELS:
            if not isinstance(entry["channels"].get(channel), dict):
                entry["channels"][channel] = {"status": "ready"}
        if entry.get("status") not in {"ready", "in_progress", "completed"}:
            entry["status"] = "ready"
    queue.sort(key=lambda value: str(value.get("updated_at") or value.get("created_at") or ""), reverse=True)
    return queue[: max(10, max_items)]


def mark_queue_posted(queue: list[dict[str, Any]], code: str, channel: str, now_iso: str) -> tuple[str, str]:
    channel = channel.strip().lower()
    if channel not in CHANNELS:
        return "invalid_channel", "note / x / threads / video のいずれかを指定してください。"
    matches = _match_queue_code(queue, code)
    if not matches:
        return "not_found", "発信キューに該当するコードがありません。"
    if len(matches) > 1:
        return "ambiguous", "コードを8文字より長く指定してください。"
    entry = matches[0]
    channels = entry.setdefault("channels", _new_channel_state())
    channels.setdefault(channel, {})["status"] = "posted"
    channels[channel]["posted_at"] = now_iso
    pending = [name for name in CHANNELS if channels.get(name, {}).get("status") != "posted"]
    entry["next_channel"] = pending[0] if pending else ""
    entry["status"] = "completed" if not pending else "in_progress"
    return "updated", f"{entry.get('code', str(entry.get('id', ''))[:8])} の {CHANNEL_LABELS[channel]} を投稿済みにしました。"


def queue_summary(queue: Any) -> dict[str, int]:
    entries = [entry for entry in queue if isinstance(entry, dict)] if isinstance(queue, list) else []
    ready = sum(1 for entry in entries if entry.get("status") == "ready")
    in_progress = sum(1 for entry in entries if entry.get("status") == "in_progress")
    completed = sum(1 for entry in entries if entry.get("status") == "completed")
    return {"total": len(entries), "ready": ready, "in_progress": in_progress, "completed": completed}


def render_content_queue(queue: Any, checked_at: str, repository_url: str) -> str:
    entries = [entry for entry in queue if isinstance(entry, dict)] if isinstance(queue, list) else []
    base = repository_url.strip().rstrip("/") or "https://github.com/y-ai-lab/ai-value-radar"
    lines = [
        "# AI VALUE RADAR｜発信キュー",
        "",
        f"更新日時：{_one_line(checked_at, 40)}",
        "",
        "次の媒体から順番に使います：note → X → Threads → 短尺動画",
        "Telegramで `/posted コード 媒体` を送ると進捗を更新できます。",
        "投稿後は `/result コード views=100 clicks=5 signups=1 sales=0 revenue=0` で反応を記録します。",
        "",
    ]
    visible = [entry for entry in entries if entry.get("status") != "completed"][:20]
    if not visible:
        lines.append("現在、未投稿の発信用パックはありません。")
    for index, entry in enumerate(visible, start=1):
        title = _one_line(str(entry.get("title", "")), 140).replace("[", "［").replace("]", "］")
        pack_url = str(entry.get("pack_url", ""))
        title_line = f"[{title}]({pack_url})" if pack_url else title
        next_channel = CHANNEL_LABELS.get(str(entry.get("next_channel", "")), "") or "完了"
        lines.extend(
            [
                f"## {index}. {title_line}",
                f"- コード：`{entry.get('code', str(entry.get('id', ''))[:8])}`",
                f"- 状態：{entry.get('status', 'ready')} / 次：{next_channel}",
                f"- 判定：{entry.get('content_grade', '発信候補')}",
                f"- 収益準備度：{entry.get('revenue_readiness', 0)}点 / 需要：{validation_label(str(entry.get('validation_status', 'unverified')))} / 結果：{outcome_label(str(entry.get('outcome_status', 'not_measured')))}",
                f"- 計測：閲覧 {entry.get('views', 0)} / クリック {entry.get('clicks', 0)} / 登録 {entry.get('signups', 0)} / 成約 {entry.get('sales', 0)} / 売上 {entry.get('revenue', 0)}円",
                f"- 切り口：{entry.get('content_angle', '')}",
                f"- 読者の悩み：{entry.get('reader_problem', '')}",
                f"- note：{entry.get('channels', {}).get('note', {}).get('status', 'ready')}",
                f"- X：{entry.get('channels', {}).get('x', {}).get('status', 'ready')}",
                f"- Threads：{entry.get('channels', {}).get('threads', {}).get('status', 'ready')}",
                f"- 短尺動画：{entry.get('channels', {}).get('video', {}).get('status', 'ready')}",
                f"- 原文：{entry.get('url', '')}",
                "",
            ]
        )
    lines.extend([f"[リポジトリ]({base})", ""])
    return "\n".join(lines)


def write_content_queue(path: Path, queue: list[dict[str, Any]], checked_at: str, repository_url: str) -> None:
    write_text_atomic(path, render_content_queue(queue, checked_at, repository_url))
