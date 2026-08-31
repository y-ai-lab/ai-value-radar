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
        self.assertIn("発信用パック：https://github.com/y-ai-lab/ai-value-radar/blob/main/data/drafts/", notifications[0])
        self.assertIn("次にすること：発信用パック → 公式条件確認 → 実体験を追記", notifications[0])
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

    def test_fresh_official_change_generates_publishing_topic_pack(self) -> None:
        notifications: list[str] = []

        def collector(settings: Settings):
            raw = [
                {
                    "title": "n8n launches a new AI workflow feature",
                    "url": "https://n8n.io/blog/new-ai-workflow-feature",
                    "summary": "New AI automation workflow feature released for business users worldwide.",
                    "source": "n8n_release",
                    "published_at": "2026-08-31T00:00:00+00:00",
                }
            ]
            stats = {"n8n_release": {"status": "ok", "items": 1, "official": True, "kind": "github_releases"}}
            return raw, stats, []

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = run_scan(
                Settings(
                    max_http_requests=5,
                    max_source_items=5,
                    max_ai_candidates_per_run=0,
                    max_publishing_topics_per_run=2,
                    max_total_content_packs_per_run=5,
                ),
                collector=collector,
                notifier=lambda message: notifications.append(message) or "dry_run",
                now=datetime(2026, 8, 31, 1, 0, tzinfo=timezone.utc),
                data_dir=root,
            )

            self.assertEqual(result["top3_count"], 0)
            self.assertEqual(result["topic_count"], 1)
            self.assertEqual(result["topic_pack_count"], 1)
            self.assertEqual(result["content_pack_count"], 1)
            self.assertIn("発信ネタ（収益候補とは別枠）", notifications[0])
            self.assertIn("発信用パック：https://github.com/y-ai-lab/ai-value-radar/blob/main/data/drafts/", notifications[0])
            self.assertEqual(result["queue"]["ready"], 1)
            self.assertTrue((root / "content_queue.json").exists())
            self.assertTrue((root / "content_queue.md").exists())
            latest = (root / "latest.md").read_text(encoding="utf-8")
            self.assertIn("## 発信ネタ", latest)
            self.assertIn("発信キュー", latest)

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

    def test_existing_ready_pack_is_refreshed_after_format_change(self) -> None:
        def collector(settings: Settings):
            raw = [{
                "title": "Open WebUI update",
                "url": "https://github.com/open-webui/open-webui/releases/tag/v1",
                "summary": "New AI chat workflow update for self-hosted users.",
                "source": "github_openwebui_releases",
                "service_name": "Open WebUI",
                "project_summary": "自分で用意したAIを、ChatGPTのような画面から使えるようにするツール。",
                "project_use": "自分用・チーム用のAIチャット環境を試したい人向け。",
                "github_repository": "open-webui/open-webui",
                "github_stars": 50000,
                "published_at": "2026-08-31T00:00:00+00:00",
            }]
            stats = {"github_openwebui_releases": {"status": "ok", "items": 1, "official": True, "kind": "github_releases"}}
            return raw, stats, []

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = Settings(
                max_http_requests=5,
                max_source_items=5,
                max_ai_candidates_per_run=0,
                max_publishing_topics_per_run=1,
                max_total_content_packs_per_run=2,
            )
            first = run_scan(
                settings,
                collector=collector,
                notifier=lambda message: "dry_run",
                now=datetime(2026, 8, 31, 1, 0, tzinfo=timezone.utc),
                data_dir=root,
            )
            self.assertEqual(first["topic_pack_count"], 1)
            draft_path = root / "drafts" / f"{first['publishing_topics'][0]['id']}.md"
            old_content = draft_path.read_text(encoding="utf-8").replace(
                "### Xにそのまま投稿（280字以内）", "### X投稿案（280字以内）"
            )
            draft_path.write_text(old_content, encoding="utf-8")

            second = run_scan(
                settings,
                collector=collector,
                notifier=lambda message: "dry_run",
                now=datetime(2026, 8, 31, 2, 0, tzinfo=timezone.utc),
                data_dir=root,
            )
            self.assertEqual(second["topic_count"], 0)
            self.assertEqual(second["content_pack_count"], 1)
            self.assertEqual(second["drafts"][0]["status"], "updated")
            self.assertIn("### Xにそのまま投稿（280字以内）", draft_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
