from __future__ import annotations

import unittest

from ai_value_radar.normalize import make_opportunity
from ai_value_radar.scoring import calculate_rule_score, days_until_deadline


class ScoringTests(unittest.TestCase):
    def test_lifetime_discount_scores(self) -> None:
        item = make_opportunity(
            {
                "title": "AI automation lifetime deal 60% off",
                "url": "https://example.com/deal",
                "summary": "Lifetime access $69 instead of $199. Free trial for Japan.",
                "source": "official",
            },
            "2026-08-31T00:00:00+00:00",
        )
        assert item is not None
        self.assertGreaterEqual(calculate_rule_score(item), 30)
        self.assertLessEqual(calculate_rule_score(item), 70)

    def test_recurring_affiliate_scores(self) -> None:
        item = make_opportunity(
            {
                "title": "Affiliate program for AI SaaS",
                "url": "https://example.com/affiliate",
                "summary": "30% recurring commission, 60 day cookie, available worldwide.",
                "source": "official",
            },
            "2026-08-31T00:00:00+00:00",
        )
        assert item is not None
        self.assertGreaterEqual(calculate_rule_score(item), 40)

    def test_deadline_days(self) -> None:
        self.assertEqual(days_until_deadline("2026-09-04", today=__import__("datetime").date(2026, 8, 31)), 4)


if __name__ == "__main__":
    unittest.main()
