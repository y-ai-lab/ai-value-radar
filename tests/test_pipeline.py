from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from ai_value_radar.config import Settings
from ai_value_radar.pipeline import run_scan


class PipelineTests(unittest.TestCase):
    def test_publish_candidate_between_40_and_69_is_not_silently_dropped(self) -> None:
        notifications: list[str] = []

        def collector(settings: Settings):
            raw = [
                {
                    "title": "n8n cloud affiliate partner program",
                    "url": "https://n8n.io/affiliates/",
                    "summary": (
                        "Affiliate program: receive 30% revenue share for 12 months. "
                        "AI automation for businesses worldwide."
                    ),
                    "source": "n8n_affiliate_page",
                }
            ]
            return raw, {"n8n_affiliate_page": {"status": "ok", "items": 1}}, []

        with tempfile.TemporaryDirectory() as directory:
            result = run_scan(
                Settings(max_http_requests=5, max_source_items=5, max_ai_candidates_per_run=0),
                collector=collector,
                notifier=lambda message: notifications.append(message) or "dry_run",
                now=datetime(2026, 8, 31, 0, 0, tzinfo=timezone.utc),
                data_dir=Path(directory),
            )

        self.assertEqual(result["promising_count"], 0)
        self.assertEqual(result["publishable_count"], 1)
        self.assertEqual(result["top3_count"], 1)
        self.assertEqual(result["top3"][0]["final_score"], 60)
        self.assertIn("発信候補・要確認", notifications[0])
        self.assertNotIn("%%", notifications[0])
        self.assertIn("記事下書き：https://github.com/y-ai-lab/ai-value-radar/blob/main/data/drafts/", notifications[0])
        self.assertIn("次にすること：下書き → 公式条件確認 → 実体験を追記", notifications[0])
        self.assertIn("詳細レポート：https://github.com/y-ai-lab/ai-value-radar/blob/main/data/latest.md", notifications[0])

    def test_clear_rule_candidate_reaches_top3_at_default_threshold(self) -> None:
        notifications: list[str] = []

        def collector(settings: Settings):
            raw = [
                {
                    "title": "AI automation lifetime deal 60% off",
                    "url": "https://vendor.example/clear-rule-deal",
                    "summary": (
                        "Lifetime access $69 instead of $199. 60% off. "
                        "Available worldwide. Free trial. Ends soon."
                    ),
                    "source": "official_vendor",
                }
            ]
            return raw, {"official_vendor": {"status": "ok", "items": 1}}, []

        def notifier(message: str) -> str:
            notifications.append(message)
            return "dry_run"

        with tempfile.TemporaryDirectory() as directory:
            result = run_scan(
                Settings(max_http_requests=5, max_source_items=5, max_ai_candidates_per_run=0),
                collector=collector,
                notifier=notifier,
                now=datetime(2026, 8, 31, 0, 0, tzinfo=timezone.utc),
                data_dir=Path(directory),
            )

        self.assertEqual(result["promising_count"], 1)
        self.assertEqual(result["top3_count"], 1)
        self.assertEqual(result["top3"][0]["rule_score"], 70)
        self.assertEqual(result["top3"][0]["final_score"], 70)
        self.assertEqual(result["notification"]["status"], "dry_run")
        self.assertEqual(len(notifications), 1)
        self.assertIn("🥇 70点", notifications[0])

    def test_fetch_filter_score_report_without_network(self) -> None:
        def collector(settings: Settings):
            raw = [
                {
                    "title": "AI automation lifetime deal 60% off",
                    "url": "https://vendor.example/deal?utm_source=feed",
                    "summary": "Lifetime access $69 instead of $199. Available worldwide.",
                    "source": "fixture",
                },
                {
                    "title": "AI automation lifetime deal 60% off",
                    "url": "https://vendor.example/deal#same",
                    "summary": "Lifetime access $69 instead of $199. Available worldwide.",
                    "source": "fixture-copy",
                },
                {
                    "title": "Small update",
                    "url": "https://vendor.example/other",
                    "summary": "A normal release.",
                    "source": "fixture",
                },
            ]
            return raw, {"fixture": {"status": "ok", "items": 3}}, []

        with tempfile.TemporaryDirectory() as directory:
            result = run_scan(
                Settings(max_http_requests=5, max_source_items=5, max_ai_candidates_per_run=0, notify_min_score=50),
                collector=collector,
                notifier=lambda text: "dry_run",
                now=datetime(2026, 8, 31, 0, 0, tzinfo=timezone.utc),
                data_dir=Path(directory),
            )
            self.assertEqual(result["fetched_count"], 3)
            self.assertEqual(result["unique_count"], 2)
            self.assertEqual(result["top3_count"], 1)
            self.assertEqual(result["draft_count"], 1)
            self.assertEqual(result["drafts"][0]["status"], "created")
            self.assertTrue((Path(directory) / "drafts" / f"{result['top3'][0]['id']}.md").exists())
            self.assertTrue((Path(directory) / "latest.md").exists())
            latest = (Path(directory) / "latest.md").read_text(encoding="utf-8")
            self.assertIn("## 次にすること", latest)
            self.assertIn("data/drafts/", latest)
            self.assertEqual(result["notification"]["status"], "dry_run")
            stored = json.loads((Path(directory) / "opportunities.json").read_text(encoding="utf-8"))
            self.assertEqual(len(stored), 2)
            report = json.loads((Path(directory) / "last_report.json").read_text(encoding="utf-8"))
            self.assertIn("top3", report)
            repeated = run_scan(
                Settings(max_http_requests=5, max_source_items=5, max_ai_candidates_per_run=0, notify_min_score=50),
                collector=collector,
                notifier=lambda text: "dry_run",
                now=datetime(2026, 8, 31, 1, 0, tzinfo=timezone.utc),
                data_dir=Path(directory),
            )
            self.assertEqual(repeated["new_count"], 0)
            self.assertEqual(repeated["top3_count"], 0)
            self.assertEqual(repeated["draft_count"], 0)


if __name__ == "__main__":
    unittest.main()
