from __future__ import annotations

from datetime import datetime
from typing import Any

from .models import Opportunity
from .writer import CATEGORY_LABELS, _short, display_name, price_line


def _markdown_label(value: str) -> str:
    return _short(value, 180).replace("[", "［").replace("]", "］")


def _display_time(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%Y/%m/%d %H:%M")
    except (TypeError, ValueError):
        return str(value)[:16]


def _file_url(repository_url: str, path: str) -> str:
    return f"{repository_url.strip().rstrip('/') or 'https://github.com/y-ai-lab/ai-value-radar'}/blob/main/{path}"


def render_latest_report(report: dict[str, Any]) -> str:
    """Render one public, phone-readable run summary without secrets."""
    run_at = str(report.get("run_at", ""))
    lines = [
        "# AI VALUE RADAR｜今回の監視結果",
        "",
        f"確認日時：{_display_time(run_at)}",
        "",
        (
            f"監視 {report.get('fetched_count', 0)}件 / "
            f"新規 {report.get('new_count', 0)}件 / "
            f"有望 {report.get('promising_count', 0)}件 / "
            f"発信候補 {report.get('publishable_count', 0)}件 / "
            f"発信ネタ {report.get('topic_count', 0)}件"
        ),
        "",
        "## 結論",
        "",
    ]
    top = report.get("top3", [])
    drafts = {
        str(value.get("id")): value
        for value in report.get("drafts", [])
        if isinstance(value, dict) and value.get("id")
    }
    if not top:
        lines.extend([
            "今回は新規または重要更新の収益候補はありませんでした。",
            "同じ案件の重複通知は抑止しています。次回の巡回を待ちます。",
        ])
    else:
        for index, raw in enumerate(top[:3], start=1):
            item = Opportunity(**raw) if isinstance(raw, dict) else raw
            draft = drafts.get(item.id, {})
            title = _markdown_label(display_name(item))
            draft_url = str(draft.get("url") or "")
            title_link = f"[{title}]({draft_url})" if draft_url else title
            label = "有望" if item.final_score >= 70 else "発信候補・要確認"
            lines.extend([
                f"### {index}. {item.final_score}点｜{label}",
                f"{title_link}",
                f"カテゴリ：{CATEGORY_LABELS.get(item.ai_category or item.category, item.category)}",
                f"条件：{price_line(item)}",
                f"注目理由：{_short(item.why_now, 240)}",
                f"原文：[{item.source}]({item.url})",
            ])
            if draft_url:
                lines.append(f"発信用パック：[Markdownを開く]({draft_url})")
            lines.append("")

    topics = report.get("publishing_topics", [])
    if isinstance(topics, list) and topics:
        lines.extend(["## 発信ネタ", ""])
        for index, topic in enumerate(topics[:3], start=1):
            if not isinstance(topic, dict):
                continue
            title = _markdown_label(str(topic.get("service_name") or topic.get("title", "")))
            pack_url = str(topic.get("pack_url") or "")
            title_link = f"[{title}]({pack_url})" if pack_url else title
            lines.extend([
                f"### {index}. {topic.get('content_grade', '発信候補')}｜発信価値 {topic.get('content_score', 0)}点",
                title_link,
                f"コード：`{topic.get('code') or str(topic.get('id', ''))[:8]}`",
                f"切り口：{_short(str(topic.get('content_angle') or ''), 240)}" if topic.get("content_angle") else "",
                f"読者の悩み：{_short(str(topic.get('reader_problem') or ''), 220)}" if topic.get("reader_problem") else "",
                f"何をするものか：{_short(str(topic.get('project_summary') or ''), 220)}" if topic.get("project_summary") else "",
                f"用途の目安：{_short(str(topic.get('project_use') or ''), 160)}" if topic.get("project_use") else "",
                f"次にすること：{_short(str(topic.get('reader_action') or ''), 220)}" if topic.get("reader_action") else "",
                f"収益化の仮説：{_short(str(topic.get('monetization') or ''), 220)}" if topic.get("monetization") else "",
                f"原文：[{topic.get('source', 'source')}]({topic.get('url', '')})",
                "",
            ])

    lines.extend([
        "## 次にすること",
        "",
        "1. 発信用パックを開く（note・X・Threads案を確認）",
        "2. 公式ページで価格・期限・日本利用・商用利用を確認する",
        "3. 実際に使った結果を追記してから公開判断する",
        "",
        "## 7日間の集計",
        "",
    ])
    metrics = report.get("metrics_7d", {})
    lines.extend([
        f"- 実行回数：{metrics.get('runs', 0)}回",
        f"- 発信用パック：{metrics.get('content_pack_count', metrics.get('draft_count', 0))}件",
        f"- 発信ネタ：{metrics.get('topic_count', 0)}件",
        f"- 価値あり判定：{metrics.get('feedback_valuable', 0)}件",
        f"- 今回は不要判定：{metrics.get('feedback_not_valuable', 0)}件",
        f"- Affiliate候補：{metrics.get('affiliate_count', 0)}件",
        f"- AI呼び出し：{metrics.get('ai_calls', 0)}回",
        f"- エラー：{metrics.get('error_count', 0)}件",
        "",
        "## エラー・取得できなかったソース",
        "",
    ])
    errors = report.get("errors", [])
    if errors:
        lines.extend(f"- {error.get('source') or error.get('stage', 'system')}：{error.get('message', 'error')}" for error in errors[:20])
    else:
        lines.append("- なし")
    queue_link = report.get("queue_link")
    if queue_link:
        lines.extend(["", f"発信キュー：[未投稿を確認]({queue_link})"])
    lines.extend([
        "",
        "このページは公開情報だけで生成されています。自動公開は行いません。",
        "",
    ])
    return "\n".join(lines)
