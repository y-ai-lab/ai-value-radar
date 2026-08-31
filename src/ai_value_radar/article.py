from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .models import Opportunity
from .state import write_text_atomic
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


def _x_post(title: str, summary: str, url: str, category: str) -> str:
    body = (
        f"【{category}】{title}\n"
        f"{_one_line(summary, 70)}\n"
        "ただ、まだ公開情報で見つけた段階。価格・商用利用・日本からの利用可否は要確認です。\n"
        "まずは自分で試して、使えた点と微妙だった点をまとめます。\n"
        "#AIツール #SaaS"
    )
    url_line = f"\n{url}"
    available = max(1, 280 - len(url_line))
    if len(body) > available:
        body = body[: max(1, available - 1)].rstrip() + "…"
    return body + url_line


def _threads_posts(title: str, summary: str, why_now: str, url: str) -> str:
    posts = [
        f"1/3\n{title}が気になったので、公開情報を確認しました。\n"
        f"{_one_line(summary, 180)}",
        "2/3\n"
        f"注目した理由は、{_one_line(why_now, 150)}\n"
        "ただし、価格や利用条件は変わる可能性があります。",
        "3/3\n"
        "現時点では、まだ実利用前の調査段階です。\n"
        "自分で試してから、向いている人・見送る人を正直にまとめます。\n"
        f"{url}\n#AIツール #SaaS",
    ]
    return "\n\n".join(posts)


def _title_options(title: str, category: str) -> str:
    return "\n".join(
        (
            f"1. {title}は誰に向く？{category}の条件を確認した",
            f"2. {title}を使う前に確認したい価格・制限・商用利用",
            f"3. AI/SaaSの発信候補として{title}を調べてみた",
        )
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
        "## 発信用パック（公開前）",
        "",
        "以下はそのまま投稿せず、公式情報と実体験を反映してから使います。",
        "",
        "### noteタイトル案",
        "",
        _title_options(title, category),
        "",
        "### note導入文",
        "",
        f"最近、{title}というAI / SaaSの条件が気になりました。",
        f"公開情報では、{summary}",
        "",
        "ただ、料金や機能だけを見て「おすすめ」とは言えません。日本から使えるのか、商用利用できるのか、"
        "実際の作業がどれくらい楽になるのかは、自分で試して確認する必要があります。",
        "",
        "この記事では、公式情報の確認結果と実際に使った感想を分けてまとめます。",
        "",
        "### X投稿案（280字以内）",
        "",
        "```text",
        _x_post(title, summary, item.url, category),
        "```",
        "",
        "### Threads投稿案",
        "",
        "```text",
        _threads_posts(title, summary, why_now, item.url),
        "```",
        "",
        "### 投稿後の誘導文・CTA案",
        "",
        "- 実際に使ったことがある人は、良かった点・困った点を教えてください。",
        "- 料金や利用条件に変更があれば、確認できた公式URLと一緒に追記します。",
        "- 紹介リンクを使う場合は、規約確認後に差し替えます。",
        "",
        "### 推奨ハッシュタグ",
        "",
        "#AIツール #SaaS #AI活用 #AI副業",
        "",
        "### 発信前の最終チェック",
        "",
        "- [ ] タイトルと本文が実際に確認した内容と一致している",
        "- [ ] 価格・仕様・期限に確認日がある",
        "- [ ] 自分が使っていない機能を体験談として書いていない",
        "- [ ] 誇大表現・収益保証・断定表現を削った",
        "- [ ] 紹介リンクを使う場合、PR / アフィリエイト表記を冒頭に置いた",
        "",
        "---",
        "このファイルはAI VALUE RADARが自動生成した公開前の発信用パックです。自動投稿・自動公開は行いません。",
        "",
    ]
    return "\n".join(lines)


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
                write_text_atomic(path, content)
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
