from __future__ import annotations

from datetime import datetime
from typing import Any

from .models import Opportunity
from .writer import CATEGORY_LABELS, _short, price_line


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
            f"発信候補 {report.get('publishable_count', 0)}件"
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
            "今回は新規または重要更新の発信候補はありませんでした。",
            "同じ案件の重複通知は抑止しています。次回の巡回を待ちます。",
        ])
    else:
        for index, raw in enumerate(top[:3], start=1):
            item = Opportunity(**raw) if isinstance(raw, dict) else raw
            draft = drafts.get(item.id, {})
            title = _markdown_label(item.ai_title or item.title)
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
                lines.append(f"記事下書き：[Markdownを開く]({draft_url})")
            lines.append("")

    lines.extend([
        "## 次にすること",
        "",
        "1. 記事下書きを開く",
        "2. 公式ページで価格・期限・日本利用・商用利用を確認する",
        "3. 実際に使った結果を追記してから公開判断する",
        "",
        "## 7日間の集計",
        "",
    ])
    metrics = report.get("metrics_7d", {})
    lines.extend([
        f"- 実行回数：{metrics.get('runs', 0)}回",
        f"- 記事下書き：{metrics.get('draft_count', 0)}件",
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
    lines.extend([
        "",
        "このページは公開情報だけで生成されています。自動公開は行いません。",
        "",
    ])
    return "\n".join(lines)
