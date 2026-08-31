from __future__ import annotations

import unittest

from ai_value_radar.models import Opportunity
from ai_value_radar.validation import (
    calculate_revenue_readiness,
    outcome_status_for,
    outcome_totals,
    update_outcome_metrics,
)


class ValidationTests(unittest.TestCase):
    def test_readiness_is_separate_from_final_score(self) -> None:
        item = Opportunity(
            id="abc123",
            title="AI lifetime deal",
            url="https://example.com/deal",
            source="official_pricing",
            discovered_at="2026-08-31T00:00:00+00:00",
            last_seen_at="2026-08-31T00:00:00+00:00",
            category="lifetime_deal",
            current_price=69,
            original_price=199,
            summary="Lifetime access $69 instead of $199.",
            reader_problem="料金比較が難しい。",
            reader_action="公式ページで条件を確認する。",
            monetization="作業コストを下げられる可能性。",
            confidence=0.8,
            final_score=40,
        )
        self.assertGreaterEqual(calculate_revenue_readiness(item), 60)
        self.assertEqual(item.final_score, 40)

    def test_outcome_update_is_aggregate_and_derives_status(self) -> None:
        entry = {"id": "abc", "views": 0, "clicks": 0, "signups": 0, "sales": 0, "revenue": 0.0}
        update_outcome_metrics(entry, {"views": 100, "clicks": 5, "signups": 1}, "2026-08-31T00:00:00+00:00")
        self.assertEqual(entry["outcome_status"], "signal")
        self.assertEqual(outcome_status_for(entry), "signal")
        update_outcome_metrics(entry, {"sales": 1, "revenue": 4900}, "2026-08-31T01:00:00+00:00")
        self.assertEqual(entry["outcome_status"], "converted")
        self.assertEqual(outcome_totals([entry])["revenue"], 4900.0)


if __name__ == "__main__":
    unittest.main()
