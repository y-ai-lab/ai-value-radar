from __future__ import annotations

import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .models import Opportunity
from .writer import CATEGORY_LABELS


def _one_line(value: str | None, limit: int = 700) -> str:
    value = " ".join((value or "").split())
    return value if len(value) <= limit else value[: limit - 1] + "…"


def _display_number(value: float | None) -> str:
    if value is None:
        return "未抽出"
    return f"{value:g}"


def _price_summary(item: Opportunity) -> str:
    currency = item.currency or ""
    if item.original_price is not None and item.current_price is not None:
        return (
            f"{currency} {_display_number(item.current_price)}（通常 "
            f"{currency} {_display_number(item.original_price)}）"
        ).strip()
    if item.current_price is not None:
        return f"{currency} {_display_number(item.current_price)}".strip()
    if item.discount is not None:
        return f"{_display_number(item.discount)}% OFF候補"
    return "公開情報から価格は抽出できませんでした"


def _discount_summary(item: Opportunity) -> str:
    if item.discount is not None:
        return f"{item.discount:g}%"
    if item.original_price and item.current_price is not None and item.current_price < item.original_price:
        value = (1 - item.current_price / item.original_price) * 100
        return f"約{value:.1f}%（価格から計算）"
    return "未抽出"


def _affiliate_summary(item: Opportunity) -> str:
    parts: list[str] = []
    if item.affiliate_rate is not None:
        parts.append(f"報酬率 {item.affiliate_rate:g}%")
    if item.affiliate_type:
        parts.append("継続報酬の可能性あり" if item.affiliate_type == "recurring" else "単発報酬の可能性")
    if item.cookie_days is not None:
        parts.append(f"Cookie {item.cookie_days}日")
    return "、".join(parts) if parts else "公開情報からは報酬条件を抽出できませんでした"


def _deadline_summary(item: Opportunity) -> str:
    return item.deadline or "公開情報から期限は抽出できませんでした"


def _quote(value: str) -> str:
    text = _one_line(value, 500)
    return "> " + (text or "公開情報の短い抜粋はありません。")


def _disclosure(item: Opportunity) -> str:
    if item.category == "affiliate_program" or item.affiliate_rate is not None:
        return (
            "> アフィリエイト関連の調査下書きです。紹介リンクを掲載する場合は、記事冒頭で広告・"
            "アフィリエイトであることを明示し、各プログラムの規約に従ってください。"
        )
    return (
        "> この下書きに紹介リンクを掲載する場合は、広告・アフィリエイトであることを記事冒頭で"
        "明示し、リンク先の規約を確認してください。"
    )


def render_article_draft(item: Opportunity, checked_at: str) -> str:
    """Render a safe, fact-labelled Japanese article draft without an AI call.

    The output intentionally never claims that the author used the product. It is
    a review-ready research draft that requires an actual trial and source check.
    """
    try:
        checked_display = datetime.fromisoformat(checked_at).strftime("%Y-%m-%d %H:%M %Z")
    except (TypeError, ValueError):
        checked_display = _one_line(checked_at, 40)
    title = _one_line(item.ai_title or item.title, 180).lstrip("#").strip()
    category = CATEGORY_LABELS.get(item.ai_category or item.category, item.ai_category or item.category)
    evidence = item.evidence or item.summary
    summary = _one_line(item.summary or evidence or "公開情報から候補として検出されました。", 800)
    why_now = _one_line(item.why_now or "今回の巡回で新規または重要な変化として検出されました。", 500)
    best_for = _one_line(item.best_for or "AI・SaaSを試している人。", 500)
    skip_if = _one_line(item.skip_if or "公式条件を確認できない場合。", 500)
    monetization = _one_line(item.monetization or "利用価値を確認してから判断します。", 600)
    risk = _one_line(item.risk or "価格、期限、日本利用、商用利用、解約条件を公式ページで確認します。", 600)
    source_name = _one_line(item.source, 120)
    status = {"new": "新規", "updated": "更新", "seen": "既知"}.get(item.status, item.status or "要確認")

    lines = [
        f"# {title}",
        "",
        f"> AI VALUE RADARの公開前調査下書き｜{status}｜{category}｜レーダー {item.final_score}点",
        f"> 自動確認日時：{checked_display}",
        "> 重要：これは公開情報から作った下書きであり、筆者の実利用レビューではありません。公開前に公式情報と実体験を追記・確認してください。",
        "",
        _disclosure(item),
        "",
        "## 先に結論",
        "",
        summary,
        "",
        "この案件は、AI VALUE RADARが公開情報から検出した段階です。価格や条件が魅力的に見えても、"
        "筆者自身の試用、利用規約の確認、日本からの利用可否の確認が終わるまでは公開判断しません。",
        "",
        "## 何が起きたか",
        "",
        f"- 区分：{category}",
        f"- 検出元：{source_name}",
        f"- 収益機会としての一次判定：{item.rule_score}点 / 70点",
        f"- 参照URL：{item.url}",
        "",
        "公開情報から抽出したメモ：",
        _quote(evidence),
        "",
        "## 価格・条件（自動抽出）",
        "",
        f"- 価格：{_price_summary(item)}",
        f"- 割引率：{_discount_summary(item)}",
        f"- Affiliate条件：{_affiliate_summary(item)}",
        f"- 期限：{_deadline_summary(item)}",
        "",
        f"確認日：{checked_display}。価格・仕様・期限は変わるため、公開時点で公式ページを再確認します。",
        "",
        "## なぜ今見るべきか",
        "",
        why_now,
        "",
        "## 向いている人",
        "",
        f"{best_for}",
        "",
        "## 見送る人・不要な人",
        "",
        f"{skip_if}",
        "",
        "## 収益化の見立て",
        "",
        monetization,
        "",
        "これは売上を保証するものではありません。自分の利用体験と読者の課題が一致する場合だけ、"
        "規約に沿って紹介候補にします。",
        "",
        "## 実際に使う前の確認リスト",
        "",
        "- [ ] 公式Pricing / Affiliate / Dealページを公開時点で再確認した",
        "- [ ] 日本から登録・決済・利用できることを確認した",
        "- [ ] 商用利用、生成物の権利、解約・自動更新を確認した",
        "- [ ] 無料枠、割引、期限、報酬率を画面で確認した",
        "- [ ] 自分の用途で実際に試し、所要時間と結果を記録した",
        "- [ ] 必要なPR / アフィリエイト表記を冒頭に置いた",
        "",
        "## 筆者の実体験メモ（公開前に追記）",
        "",
        "- 試した機能：",
        "- 使った時間：",
        "- 良かった点：",
        "- 困った点：",
        "- どんな読者の課題に合うか：",
        "- 実測した料金・制限：",
        "",
        "## 注意点",
        "",
        risk,
        "",
        "## まとめ",
        "",
        f"{title}は、現時点では「確認する価値がある候補」です。公開する場合は、上の実体験メモと"
        "公式情報の確認結果を埋め、推測と事実を分けて記載します。",
        "",
        "## 参照元",
        "",
        f"- [{source_name}]({item.url})",
        f"- 取得対象：{category} / {status}",
        "",
        "---",
        "このファイルはAI VALUE RADARが自動生成した公開前下書きです。自動公開は行いません。",
        "",
    ]
    return "\n".join(lines)


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def generate_article_drafts(
    items: Iterable[Opportunity],
    data_dir: Path,
    repository_url: str,
    checked_at: str,
    limit: int = 3,
    max_bytes: int = 30_000,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Write stable per-opportunity Markdown drafts and return safe metadata."""
    draft_dir = data_dir / "drafts"
    drafts: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    base_url = repository_url.strip().rstrip("/") or "https://github.com/y-ai-lab/ai-value-radar"
    for item in list(items)[: max(0, limit)]:
        relative_path = Path("data") / "drafts" / f"{item.id}.md"
        path = draft_dir / f"{item.id}.md"
        try:
            content = render_article_draft(item, checked_at)
            byte_count = len(content.encode("utf-8"))
            if byte_count > max_bytes:
                errors.append({"stage": "article_draft", "item_id": item.id, "message": "draft exceeds byte limit"})
                continue
            previous = path.read_text(encoding="utf-8") if path.exists() else None
            if previous == content:
                status = "unchanged"
            else:
                _write_text_atomic(path, content)
                status = "updated" if previous is not None else "created"
            item.draft_path = relative_path.as_posix()
            item.draft_status = status
            drafts.append(
                {
                    "id": item.id,
                    "title": _one_line(item.ai_title or item.title, 180),
                    "path": relative_path.as_posix(),
                    "url": f"{base_url}/blob/main/{relative_path.as_posix()}",
                    "status": status,
                    "bytes": byte_count,
                }
            )
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(
                {"stage": "article_draft", "item_id": item.id, "message": type(exc).__name__}
            )
    return drafts, errors
