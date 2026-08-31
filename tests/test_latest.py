from __future__ import annotations

import unittest

from ai_value_radar.latest import render_latest_report


class LatestReportTests(unittest.TestCase):
    def test_empty_report_is_actionable(self) -> None:
        content = render_latest_report(
            {
                "run_at": "2026-08-31T00:00:00+00:00",
                "fetched_count": 10,
                "new_count": 0,
                "promising_count": 0,
                "publishable_count": 0,
                "top3": [],
                "drafts": [],
                "errors": [],
                "metrics_7d": {"runs": 1, "draft_count": 0, "affiliate_count": 0, "ai_calls": 0, "error_count": 0},
            }
        )
        self.assertIn("今回は新規または重要更新の収益候補はありませんでした", content)
        self.assertIn("## 次にすること", content)

    def test_topic_and_queue_are_visible(self) -> None:
        content = render_latest_report(
            {
                "run_at": "2026-08-31T00:00:00+00:00",
                "fetched_count": 10,
                "new_count": 1,
                "promising_count": 0,
                "publishable_count": 0,
                "topic_count": 1,
                "publishing_topics": [
                    {
                        "id": "abcdef123456",
                        "code": "abcdef12",
                        "title": "New AI workflow feature",
                        "source": "official",
                        "url": "https://example.com/source",
                        "content_score": 82,
                        "pack_url": "https://github.com/y-ai-lab/ai-value-radar/blob/main/data/drafts/abcdef123456.md",
                    }
                ],
                "drafts": [],
                "queue_link": "https://github.com/y-ai-lab/ai-value-radar/blob/main/data/content_queue.md",
                "errors": [],
                "metrics_7d": {"runs": 1, "topic_count": 1, "content_pack_count": 1},
            }
        )
        self.assertIn("## 発信ネタ", content)
        self.assertIn("abcdef12", content)
        self.assertIn("発信キュー", content)


if __name__ == "__main__":
    unittest.main()
