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
        self.assertIn("今回は新規または重要更新の発信候補はありませんでした", content)
        self.assertIn("## 次にすること", content)


if __name__ == "__main__":
    unittest.main()
