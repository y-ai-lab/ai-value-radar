from __future__ import annotations

import json
import unittest

from ai_value_radar.sources import SOURCE_SPECS, SourceSpec, fetch_source, parse_feed


class FakeClient:
    def __init__(self, payload: str) -> None:
        self.payload = payload

    def get(self, url: str, accept: str):
        return self.payload, "200"


class SourceTests(unittest.TestCase):
    def test_atom_feed_is_parsed(self) -> None:
        payload = """<?xml version='1.0'?><feed xmlns='http://www.w3.org/2005/Atom'>
        <entry><title>New AI pricing</title><link href='https://example.com/a'/>
        <summary>Free plan added</summary><updated>2026-08-31T00:00:00Z</updated></entry></feed>"""
        items = parse_feed(payload, "fixture")
        self.assertEqual(items[0]["title"], "New AI pricing")
        self.assertEqual(items[0]["url"], "https://example.com/a")

    def test_github_release_json_is_parsed(self) -> None:
        payload = json.dumps([{"name": "v1.0", "html_url": "https://github.com/a/b/releases/tag/v1", "body": "Pricing update"}])
        spec = SourceSpec("fixture", "fixture", "github_releases", "https://api.github.com/x", "test")
        items = fetch_source(FakeClient(payload), spec)
        self.assertEqual(items[0]["title"], "v1.0")

    def test_github_repository_has_readable_project_details(self) -> None:
        payload = json.dumps({"items": [{
            "full_name": "demo/ai-workflow",
            "name": "ai-workflow",
            "html_url": "https://github.com/demo/ai-workflow",
            "description": "Automate AI workflows for small teams.",
            "language": "Python",
            "topics": ["ai", "automation"],
            "stargazers_count": 123,
        }]})
        spec = SourceSpec("fixture", "fixture", "github_search", "https://api.github.com/search", "test")
        item = fetch_source(FakeClient(payload), spec)[0]
        self.assertEqual(item["service_name"], "Ai Workflow")
        self.assertEqual(item["github_stars"], 123)
        self.assertIn("Automate AI workflows", item["project_summary"])
        self.assertIn("自動化", item["project_use"])

    def test_source_catalog_is_broader_than_github(self) -> None:
        self.assertGreaterEqual(len(SOURCE_SPECS), 25)
        self.assertTrue(any(spec.kind == "rss" and spec.official for spec in SOURCE_SPECS))
        self.assertTrue(any(spec.kind == "official_page" for spec in SOURCE_SPECS))


if __name__ == "__main__":
    unittest.main()
