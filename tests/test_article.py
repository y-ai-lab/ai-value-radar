from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ai_value_radar.article import generate_article_drafts, render_article_draft
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
        self.assertIn("Lifetime access $69 instead of $199", content)

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
