from __future__ import annotations

import unittest

from ai_value_radar.filtering import deduplicate_current
from ai_value_radar.normalize import make_opportunity


class FilteringTests(unittest.TestCase):
    def test_duplicate_url_and_title_are_removed(self) -> None:
        raw = [
            {"title": "Lifetime AI Tool", "url": "https://example.com/tool?utm_source=x", "summary": "Lifetime $69", "source": "a"},
            {"title": "Lifetime AI Tool", "url": "https://example.com/tool#details", "summary": "Lifetime $69", "source": "b"},
            {"title": "A different tool", "url": "https://example.com/other", "summary": "Free plan", "source": "c"},
        ]
        items = [make_opportunity(value, "2026-08-31T00:00:00+00:00") for value in raw]
        unique, duplicates = deduplicate_current([item for item in items if item])
        self.assertEqual(len(unique), 2)
        self.assertEqual(duplicates, 1)


if __name__ == "__main__":
    unittest.main()
