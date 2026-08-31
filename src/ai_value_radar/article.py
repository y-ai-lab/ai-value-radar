from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .models import Opportunity
from .state import write_text_atomic
from .validation import (
    build_validation_plan,
    calculate_revenue_readiness,
    outcome_label,
    validation_label,
)
from .writer import CATEGORY_LABELS, display_name


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


USAGE_LABELS = {
    "not_used": "未使用",
    "trial": "試用中",
    "used": "使用済み",
    "published": "公開済み",
}


def _usage_label(status: str) -> str:
    return USAGE_LABELS.get(status, "未使用")


def _usage_sentence(status: str) -> str:
    if status == "published":
        return "公開済みの記録があります。公開内容と現在の公式情報が一致するか、再確認してから再利用します。"
    if status == "used":
        return "実際に使用済みとして記録されています。具体的な結果・制限・感想を実体験メモに追記してから公開します。"
    if status == "trial":
        return "現在は試用中として記録されています。試した範囲と未確認の範囲を分けてから公開します。"
    return "まだ実利用前の調査段階です。公式情報を確認し、自分で試してから公開判断します。"


def _x_post(
    title: str,
    summary: str,
    url: str,
    category: str,
    usage_status: str = "not_used",
    content_angle: str = "",
    reader_problem: str = "",
) -> str:
    if usage_status in {"used", "published"}:
        experience_line = "使った範囲と、まだ確認できていない条件を分けて整理します。"
    elif usage_status == "trial":
        experience_line = "試した範囲と、まだ確認できていない条件を分けて整理します。"
    else:
        experience_line = "まずは自分で試して、使えた点と微妙だった点をまとめます。"
    source_line = (
        "公開情報と使用済みの範囲を分けて整理します。"
        if usage_status in {"used", "published"}
        else "まだ公開情報で見つけた段階。価格・商用利用・日本からの利用可否は要確認です。"
    )
    angle_line = _one_line(content_angle or summary, 110)
    problem_line = f"読者の悩み：{_one_line(reader_problem, 100)}\n" if reader_problem else ""
    body = (
        f"【{category}】{title}\n"
        f"{angle_line}\n"
        f"{problem_line}"
        f"{source_line}\n"
        f"{experience_line}\n"
        "#AIツール #SaaS"
    )
    url_line = f"\n{url}"
    available = max(1, 280 - len(url_line))
    if len(body) > available:
        body = body[: max(1, available - 1)].rstrip() + "…"
    return body + url_line


def _threads_posts(
    title: str,
    summary: str,
    why_now: str,
    url: str,
    usage_status: str = "not_used",
    content_angle: str = "",
    reader_problem: str = "",
) -> str:
    experience_line = (
        "使用済みの範囲と、まだ確認できていない条件を分けて共有します。"
        if usage_status in {"used", "published"}
        else "実際に試した範囲と、まだ未確認の条件を分けて共有します。"
    )
    angle_line = _one_line(content_angle or summary, 180)
    problem_line = f"\n読者の悩み：{_one_line(reader_problem, 120)}" if reader_problem else ""
    posts = [
        f"1/3\n{title}が気になったので、公開情報を確認しました。\n"
        f"{angle_line}{problem_line}",
        "2/3\n"
        f"注目した理由は、{_one_line(why_now, 150)}\n"
        "ただし、価格や利用条件は変わる可能性があります。",
        "3/3\n"
        f"{experience_line}\n"
        "向いている人・見送る人を正直にまとめます。\n"
        f"{url}\n#AIツール #SaaS",
    ]
    return "\n\n".join(posts)


def _title_options(title: str, category: str, project_summary: str = "") -> str:
    if project_summary:
        what_it_is = _one_line(project_summary, 70).rstrip("。")
        return "\n".join(
            (
                f"1. {title}は何ができる？{what_it_is}",
                f"2. {title}を使う前に確認したい料金・制限・向いている人",
                f"3. AIツールが多すぎる人へ：{title}を調べてみた",
            )
        )
    return "\n".join(
        (
            f"1. {title}は誰に向く？{category}の条件を確認した",
            f"2. {title}を使う前に確認したい価格・制限・商用利用",
            f"3. AI/SaaSの発信候補として{title}を調べてみた",
        )
    )


def _content_angles(
    title: str,
    summary: str,
    why_now: str,
    best_for: str,
    risk: str,
    monetization: str,
) -> str:
    return "\n".join(
        (
            f"1. 価格・条件：{title}の料金、無料枠、期限を整理する。\n   下書きの軸：{_one_line(summary, 220)}",
            f"2. 初心者向け：{title}はどんな作業を減らせそうかを説明する。\n   下書きの軸：{_one_line(best_for, 220)}",
            f"3. 比較・選び方：似たAI / SaaSと比べる前に、何を確認するかを書く。\n   下書きの軸：{_one_line(why_now, 220)}",
            "4. 実験ログ：実際に試した手順、かかった時間、できたこと・できなかったことを記録する。\n   下書きの軸：実体験を追記するまで断定しない。",
            f"5. 注意点：契約、商用利用、日本利用、制限などの見落としを伝える。\n   下書きの軸：{_one_line(risk, 220)}",
            f"6. 収益化の考え方：紹介できる条件と、紹介しない条件を分ける。\n   下書きの軸：{_one_line(monetization, 220)}",
        )
    )


def _video_pack(title: str, summary: str, why_now: str, risk: str, usage_status: str) -> str:
    usage_note = _usage_sentence(usage_status)
    return "\n".join(
        (
            f"- 想定尺：30秒 / 縦型",
            f"- Hook（0〜3秒）：『{_one_line(title, 70)}。安さより先に、確認したい条件があります。』",
            f"- 0〜3秒：{_one_line(title, 100)}を大きく表示。",
            f"- 4〜10秒：{_one_line(summary, 180)}",
            f"- 11〜18秒：なぜ今見るのか。{_one_line(why_now, 160)}",
            f"- 19〜25秒：注意点。{_one_line(risk, 160)}",
            "- 26〜30秒：『自分で試して、向いている人・見送る人をまとめます。』",
            "- 映像：公式ページの確認、料金表、操作画面、メモを書く手元を短く切り替える。",
            "- 音声：本人収録。未確認の情報は断定せず、画面内の出典URLも確認する。",
            f"- 実利用ステータス：{_usage_label(usage_status)}。{usage_note}",
            "- 投稿文：AI / SaaSの条件を調べたメモ。実際に使った結果は別途追記します。",
        )
    )


def render_article_draft(item: Opportunity, checked_at: str, mode: str = "revenue") -> str:
    """Render a safe, fact-labelled Japanese article draft without an AI call.

    The output intentionally never claims that the author used the product. It is
    a review-ready research draft that requires an actual trial and source check.
    """
    try:
        checked_display = datetime.fromisoformat(checked_at).strftime("%Y-%m-%d %H:%M %Z")
    except (TypeError, ValueError):
        checked_display = _one_line(checked_at, 40)
    title = _one_line(display_name(item), 180).lstrip("#").strip()
    category = CATEGORY_LABELS.get(item.ai_category or item.category, item.ai_category or item.category)
    evidence = item.evidence or item.summary
    summary = _one_line(item.summary or evidence or "公開情報から候補として検出されました。", 800)
    why_now = _one_line(item.why_now or "今回の巡回で新規または重要な変化として検出されました。", 500)
    best_for = _one_line(item.best_for or "AI・SaaSを試している人。", 500)
    skip_if = _one_line(item.skip_if or "公式条件を確認できない場合。", 500)
    monetization = _one_line(item.monetization or "利用価値を確認してから判断します。", 600)
    risk = _one_line(item.risk or "価格、期限、日本利用、商用利用、解約条件を公式ページで確認します。", 600)
    content_angle = _one_line(item.content_angle or f"{title}が、どんな作業に役立つのかを具体例で確認する。", 500)
    reader_problem = _one_line(item.reader_problem or "AIの情報は多いのに、自分の作業で試す方法まで落とし込めない。", 400)
    reader_action = _one_line(item.reader_action or "公式ページで条件を確認し、自分の用途で一つだけ試して結果を記録する。", 400)
    validation_plan = _one_line(item.validation_plan or build_validation_plan(item), 800)
    revenue_readiness = calculate_revenue_readiness(item)
    demand_evidence = _one_line(
        item.demand_evidence or "未記録。公式情報は機会の根拠であり、読者需要や成約の証拠ではありません。",
        500,
    )
    source_name = _one_line(item.source, 120)
    status = {"new": "新規", "updated": "更新", "seen": "既知"}.get(item.status, item.status or "要確認")
    mode_label = "発信ネタ" if mode == "publishing" else "収益候補"
    score_label = item.content_score if mode == "publishing" else item.final_score
    conclusion = (
        "これは収益案件の確定ではなく、AI / SaaSについて発信する価値があるかを確認するためのネタです。"
        if mode == "publishing"
        else "この案件は、AI VALUE RADARが公開情報から検出した段階です。"
    )

    lines = [
        f"# {title}",
        "",
        f"> AI VALUE RADARの公開前調査下書き｜{status}｜{category}｜{mode_label} {score_label}点",
        f"> 自動確認日時：{checked_display}",
        f"> 実利用ステータス：{_usage_label(item.usage_status)}",
        "> 重要：これは公開情報から作った下書きであり、筆者の実利用レビューではありません。公開前に公式情報と実体験を追記・確認してください。",
        "",
        _disclosure(item),
        "",
        "## 先に結論",
        "",
        summary,
        "",
        conclusion + "価格や条件が魅力的に見えても、"
        "筆者自身の試用、利用規約の確認、日本からの利用可否の確認が終わるまでは公開判断しません。",
        "",
        "## 何が起きたか",
        "",
        f"- 区分：{category}",
        f"- 検出元：{source_name}",
        f"- {('発信価値の一次判定' if mode == 'publishing' else '収益機会としての一次判定')}：{score_label}点 / {('100' if mode == 'publishing' else '70')}点",
        f"- 参照URL：{item.url}",
        "",
        "公開情報から抽出したメモ：",
        _quote(evidence),
        "",
    ]
    if item.github_repository:
        lines.extend(
            [
                "## GitHubプロジェクトの説明",
                "",
                f"- 表示名：{title}",
                f"- リポジトリ：{item.github_repository}",
                f"- GitHubページ：https://github.com/{item.github_repository}",
                f"- これは何か：{_one_line(item.project_summary or item.summary or '公開プロジェクトの情報です。', 700)}",
                f"- 用途の目安：{_one_line(item.project_use or 'GitHub上の公開プロジェクトを試したい人向け。', 300)}",
                f"- 使用言語：{item.github_language}" if item.github_language else "",
                f"- Stars：{item.github_stars:,}" if isinstance(item.github_stars, int) else "",
                f"- トピック：{', '.join(item.github_topics[:8])}" if item.github_topics else "",
                f"- 補足：これは完成済みのSaaSとは限らず、開発者向けの公開プロジェクトやコードの場合があります。",
                "",
            ]
        )
    lines.extend(
        [
        "## 読者に伝える切り口",
        "",
        f"- 読者の悩み：{reader_problem}",
        f"- この記事の切り口：{content_angle}",
        f"- 読者が次にすること：{reader_action}",
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
        "## 収益検証（公開前に必ず行う）",
        "",
        f"- 収益化準備度：{revenue_readiness}点 / 100点（行動に移しやすい情報量の目安）",
        f"- 需要検証：{validation_label(item.validation_status)}",
        f"- 現在の根拠：{demand_evidence}",
        f"- 投稿後の結果：{outcome_label(item.outcome_status)}",
        f"- 検証プラン：{validation_plan}",
        "- 成功とみなす目安：クリック・登録・成約のいずれかを確認し、数字と日付を記録する。",
        "- 見送りとみなす目安：公式条件が確認できない、読者の悩みが曖昧、複数回試しても反応がない。",
        f"- Telegramで需要状態を更新：`/validate {item.id[:8]} signal` または `validated`",
        f"- Telegramで結果を記録：`/result {item.id[:8]} views=100 clicks=5 signups=1 sales=0 revenue=0`",
        "- `revenue` は円。省略した項目は前回値を維持します。",
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
        _title_options(title, category, item.project_summary),
        "",
        "### note導入文",
        "",
        f"最近、{title}というAI / SaaSの条件が気になりました。",
        f"公開情報では、{summary}",
        "",
        f"この記事では、{content_angle}",
        "",
        "ただ、料金や機能だけを見て「おすすめ」とは言えません。日本から使えるのか、商用利用できるのか、"
        "実際の作業がどれくらい楽になるのかは、自分で試して確認する必要があります。",
        "",
        "この記事では、公式情報の確認結果と実際に使った感想を分けてまとめます。",
        "",
        "### 6つの発信切り口",
        "",
        _content_angles(title, summary, why_now, best_for, risk, monetization),
        "",
        "### 30秒動画パック",
        "",
        _video_pack(title, summary, why_now, risk, item.usage_status),
        "",
        "### X投稿案（280字以内）",
        "",
        "```text",
        _x_post(
            title,
            summary,
            item.url,
            category,
            item.usage_status,
            content_angle,
            reader_problem,
        ),
        "```",
        "",
        "### Threads投稿案",
        "",
        "```text",
        _threads_posts(
            title,
            summary,
            why_now,
            item.url,
            item.usage_status,
            content_angle,
            reader_problem,
        ),
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
    )
    return "\n".join(lines)


def generate_article_drafts(
    items: Iterable[Opportunity],
    data_dir: Path,
    repository_url: str,
    checked_at: str,
    limit: int = 3,
    max_bytes: int = 30_000,
    mode: str = "revenue",
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
            item.content_kind = mode if mode in {"revenue", "publishing"} else "revenue"
            item.revenue_readiness = calculate_revenue_readiness(item)
            content = render_article_draft(item, checked_at, mode=mode)
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
                    "title": _one_line(display_name(item), 180),
                    "path": relative_path.as_posix(),
                    "url": f"{base_url}/blob/main/{relative_path.as_posix()}",
                    "status": status,
                    "bytes": byte_count,
                    "kind": mode,
                    "content_score": item.content_score,
                    "revenue_readiness": item.revenue_readiness,
                    "validation_status": item.validation_status,
                    "outcome_status": item.outcome_status,
                    "usage_status": item.usage_status,
                }
            )
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(
                {"stage": "article_draft", "item_id": item.id, "message": type(exc).__name__}
            )
    return drafts, errors
