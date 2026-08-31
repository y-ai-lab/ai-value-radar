from __future__ import annotations

from datetime import datetime

from .models import Opportunity


CATEGORY_LABELS = {
    "lifetime_deal": "Lifetime Deal",
    "discount": "値引き",
    "free_credit": "無料枠・クレジット",
    "affiliate_program": "Affiliate",
    "pricing_change": "Pricing変更",
    "other": "AI/SaaS情報",
}
USAGE_LABELS = {
    "not_used": "未使用",
    "trial": "試用中",
    "used": "使用済み",
    "published": "公開済み",
}


def _short(value: str, limit: int) -> str:
    value = " ".join((value or "").split())
    return value if len(value) <= limit else value[: limit - 1] + "…"


def enrich_fallback(item: Opportunity) -> Opportunity:
    text = f"{item.title} {item.evidence or item.summary}".lower()
    if not item.summary:
        item.summary = _short(f"{CATEGORY_LABELS.get(item.category, 'AI/SaaS情報')}。{item.evidence or item.title}", 220)
    if not item.why_now:
        item.why_now = (
            f"期限候補: {item.deadline}。"
            if item.deadline
            else "今回の巡回で新規または重要な変化として検出。"
        )
    if not item.best_for:
        item.best_for = "AI・自動化・マーケティングを試す人。"
        if "affiliate" in text or item.category == "affiliate_program":
            item.best_for = "AI/SaaSを紹介できる発信者・運用者。"
    if not item.skip_if:
        item.skip_if = "日本利用、商用利用、解約条件を確認できない場合。"
    if not item.monetization:
        if item.affiliate_rate is not None:
            rate = f"{item.affiliate_rate:g}%"
            kind = " recurring" if item.affiliate_type == "recurring" else ""
            item.monetization = f"Affiliate {rate}{kind}の可能性。公式条件の確認が必要。"
        elif item.category in {"lifetime_deal", "discount", "free_credit"}:
            item.monetization = "自分の作業コストを下げ、制作・発信・受託へ転用できる可能性。"
        else:
            item.monetization = "収益化に直結するかは、利用価値と公式条件の確認後に判断。"
    if not item.risk:
        item.risk = "公式ページで価格、期限、日本利用、商用利用、自動更新を確認。"
    if item.confidence <= 0:
        item.confidence = round(min(0.95, 0.45 + item.rule_score / 200), 2)
    return item


def price_line(item: Opportunity) -> str:
    currency = item.currency or ""
    if item.original_price is not None and item.current_price is not None:
        return f"{currency} {item.current_price:g}（通常 {currency} {item.original_price:g}）"
    if item.current_price is not None:
        return f"{currency} {item.current_price:g}"
    if item.discount is not None:
        return f"{item.discount:g}% OFF候補"
    if item.affiliate_rate is not None:
        suffix = " recurring" if item.affiliate_type == "recurring" else ""
        return f"報酬 {item.affiliate_rate:g}%{suffix}"
    return "条件はリンク先で確認"


def format_telegram_report(report: dict) -> str:
    run_at = report.get("run_at", "")
    try:
        display_time = datetime.fromisoformat(run_at).strftime("%Y/%m/%d %H:%M")
    except (TypeError, ValueError):
        display_time = str(run_at)[:16]
    lines = [
        "AI VALUE RADAR",
        display_time,
        "",
        (
            f"監視：{report.get('fetched_count', 0)}件　"
            f"新規：{report.get('new_count', 0)}件　"
            f"有望：{report.get('promising_count', 0)}件　"
            f"発信候補：{report.get('publishable_count', 0)}件　"
            f"発信ネタ：{report.get('topic_count', 0)}件"
        ),
    ]
    top = report.get("top3", [])
    drafts = {
        str(value.get("id")): value
        for value in report.get("drafts", [])
        if isinstance(value, dict) and value.get("id")
    }
    if top:
        medals = ["🥇", "🥈", "🥉"]
        for index, raw in enumerate(top[:3]):
            item = Opportunity(**raw) if isinstance(raw, dict) else raw
            enrich_fallback(item)
            draft = drafts.get(item.id)
            title = _short(item.ai_title or item.title, 80)
            label = "有望" if item.final_score >= 70 else "発信候補・要確認"
            usage = USAGE_LABELS.get(getattr(item, "usage_status", "not_used"), "未使用")
            lines.extend(
                [
                    "",
                    f"{medals[index]} {item.final_score}点｜{label}｜{title}",
                    f"コード：{item.id[:8]}　実利用：{usage}",
                    f"{CATEGORY_LABELS.get(item.ai_category or item.category, item.ai_category or item.category)}｜{price_line(item)}",
                    f"注目：{_short(item.why_now, 100)}",
                    f"向く人：{_short(item.best_for, 90)}",
                    f"見送り：{_short(item.skip_if, 90)}",
                    f"収益化：{_short(item.monetization, 110)}",
                    f"URL：{item.url}",
                ]
            )
            if draft and draft.get("url"):
                lines.append(f"発信用パック：{draft['url']}")
    else:
        lines.extend(["", "収益候補：今回はなし"])

    topics = report.get("publishing_topics", [])
    if isinstance(topics, list) and topics:
        lines.extend(["", "発信ネタ（収益候補とは別枠）"])
        for topic in topics[:3]:
            if not isinstance(topic, dict):
                continue
            title = _short(str(topic.get("title", "")), 90)
            code = str(topic.get("code") or str(topic.get("id", ""))[:8])
            lines.extend(
                [
                    "",
                    f"📝 {topic.get('content_score', 0)}点｜{title}",
                    f"コード：{code}　実利用：{USAGE_LABELS.get(str(topic.get('usage_status', 'not_used')), '未使用')}",
                    f"原文：{topic.get('url', '')}",
                ]
            )
            if topic.get("pack_url"):
                lines.append(f"発信用パック：{topic['pack_url']}")
    elif not top:
        lines.append("発信ネタも今回はありません。次回もAI / SaaSを巡回します。")
    lines.extend([
        "",
        "次にすること：発信用パック → 公式条件確認 → 実体験を追記",
    ])
    queue_link = report.get("queue_link")
    if queue_link:
        lines.append(f"発信キュー：{queue_link}")
    latest = report.get("latest", {})
    if isinstance(latest, dict) and latest.get("url"):
        lines.append(f"詳細レポート：{latest['url']}")
    lines.extend(
        [
            "",
            "Telegram操作：/good コード（価値あり） /skip コード（不要）",
            "/trial コード /used コード /posted コード note|x|threads|video",
        ]
    )
    return "\n".join(lines)[:3900]
