from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ai_value_radar.article import _x_post, generate_article_drafts, render_article_draft
from ai_value_radar.models import Opportunity


def sample_opportunity() -> Opportunity:
    return Opportunity(
        id="abc123",
        title="AI automation lifetime deal 60% off",
        url="https://vendor.example/deal",
        source="official_vendor",
        discovered_at="2026-08-31T00:00:00+00:00",
        last_seen_at="2026-08-31T00:00:00+00:00",
        category="lifetime_deal",
        original_price=199,
        current_price=69,
        currency="USD",
        discount=60,
        deadline="期限が近い可能性あり",
        rule_score=70,
        final_score=70,
        status="new",
        content_hash="hash",
        evidence="Lifetime access $69 instead of $199. Available worldwide.",
        summary="買い切りプランが公開された。",
        why_now="期限が近い可能性がある。",
        best_for="AI自動化を試す人。",
        skip_if="商用利用条件を確認できない場合。",
        monetization="作業コストを下げられる可能性。",
        risk="公式条件を確認する。",
        confidence=0.8,
    )


class ArticleDraftTests(unittest.TestCase):
    def test_render_labels_draft_and_does_not_claim_usage(self) -> None:
        content = render_article_draft(sample_opportunity(), "2026-08-31T00:00:00+00:00")
        self.assertIn("公開前調査下書き", content)
        self.assertIn("実利用レビューではありません", content)
        self.assertIn("実際に使う前の確認リスト", content)
        self.assertIn("発信用パック", content)
        self.assertIn("6つの発信切り口", content)
        self.assertIn("30秒動画パック", content)
        self.assertIn("Xにそのまま投稿（280字以内）", content)
        self.assertIn("Threads投稿案", content)
        self.assertIn("読者に伝える切り口", content)
        self.assertIn("読者が次にすること", content)
        self.assertIn("収益検証（公開前に必ず行う）", content)
        self.assertIn("/result abc123", content)
        self.assertIn("Lifetime access $69 instead of $199", content)

    def test_x_post_stays_within_280_characters(self) -> None:
        post = _x_post(
            "とても長いAIツールのタイトル" * 20,
            "公開情報の長い要約" * 100,
            "https://vendor.example/deal",
            "Lifetime Deal",
        )
        self.assertLessEqual(len(post), 280)

    def test_x_post_is_plain_and_natural_for_copy_paste(self) -> None:
        post = _x_post(
            "Open WebUI",
            "公開情報では、自分で用意したAIをChatGPTのような画面から使えるツール。",
            "https://github.com/open-webui/open-webui/releases/tag/v0.11.2",
            "AI/SaaS情報",
            project_summary="自分で用意したAIを、ChatGPTのような画面から使えるようにするツール。",
            project_use="自分用・チーム用のAIチャット環境を試したい人向け。",
        )
        self.assertLessEqual(len(post), 280)
        self.assertIn("最近、Open WebUIの更新が気になった。", post)
        self.assertIn("https://github.com/open-webui/open-webui/releases/tag/v0.11.2", post)
        self.assertNotIn("【", post)
        self.assertNotIn("読者の悩み：", post)
        self.assertNotIn("公開情報では", post)
        self.assertNotIn("AI / SaaS", post)

    def test_used_status_changes_pack_language_without_claiming_results(self) -> None:
        item = sample_opportunity()
        item.usage_status = "used"
        content = render_article_draft(item, "2026-08-31T00:00:00+00:00")
        self.assertIn("実利用ステータス：使用済み", content)
        self.assertIn("使用済みの範囲と、まだ確認できていない条件を分けて共有します", content)
        self.assertIn("具体的な結果・制限・感想を実体験メモに追記", content)
        self.assertIn("売上を保証するものではありません", content)

    def test_github_project_explanation_is_included(self) -> None:
        item = sample_opportunity()
        item.title = "demo/ai-workflow"
        item.service_name = "AI Workflow"
        item.github_repository = "demo/ai-workflow"
        item.project_summary = "AI workflows for small teams."
        item.project_use = "業務自動化や複数サービスの連携を試したい人向け。"
        content = render_article_draft(item, "2026-08-31T00:00:00+00:00", mode="publishing")
        self.assertIn("## GitHubプロジェクトの説明", content)
        self.assertIn("これは何か：AI workflows for small teams.", content)
        self.assertIn("用途の目安：業務自動化", content)

    def test_generate_is_stable_and_reports_unchanged(self) -> None:
        item = sample_opportunity()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, errors = generate_article_drafts(
                [item], root, "https://github.com/y-ai-lab/ai-value-radar", "2026-08-31T00:00:00+00:00"
            )
            self.assertEqual(errors, [])
            self.assertEqual(first[0]["status"], "created")
            self.assertEqual(first[0]["path"], "data/drafts/abc123.md")
            self.assertTrue((root / "drafts" / "abc123.md").exists())

            second, errors = generate_article_drafts(
                [item], root, "https://github.com/y-ai-lab/ai-value-radar", "2026-08-31T00:00:00+00:00"
            )
            self.assertEqual(errors, [])
            self.assertEqual(second[0]["status"], "unchanged")
            self.assertEqual(item.draft_path, "data/drafts/abc123.md")


if __name__ == "__main__":
    unittest.main()
