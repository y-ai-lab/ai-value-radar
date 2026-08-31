from __future__ import annotations

import unittest

from ai_value_radar.normalize import (
    content_hash,
    extract_deadline,
    extract_discount,
    extract_prices,
    normalize_url,
)


class NormalizeTests(unittest.TestCase):
    def test_url_normalization_removes_tracking_and_fragment(self) -> None:
        self.assertEqual(
            normalize_url("HTTPS://Example.com/tool/?utm_source=x&b=2&a=1#read"),
            "https://example.com/tool?a=1&b=2",
        )

    def test_discount_and_prices(self) -> None:
        self.assertEqual(extract_discount("Limited time: save 60% off"), 60.0)
        self.assertEqual(extract_prices("Lifetime $69 instead of $199"), (199.0, 69.0, "USD"))

    def test_deadline(self) -> None:
        self.assertEqual(extract_deadline("Offer ends 2026-09-04"), "2026-09-04")

    def test_content_hash_is_stable(self) -> None:
        self.assertEqual(content_hash("Tool", "A short summary", "https://example.com"), content_hash("Tool", "A short summary", "https://example.com#x"))


if __name__ == "__main__":
    unittest.main()
