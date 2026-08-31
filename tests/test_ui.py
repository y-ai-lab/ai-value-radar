from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class StaticDashboardTests(unittest.TestCase):
    def test_dashboard_is_mobile_first_and_reads_public_state_only(self) -> None:
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        javascript = (ROOT / "assets" / "radar.js").read_text(encoding="utf-8")
        pack_html = (ROOT / "pack.html").read_text(encoding="utf-8")
        pack_javascript = (ROOT / "assets" / "pack.js").read_text(encoding="utf-8")
        css = (ROOT / "assets" / "radar.css").read_text(encoding="utf-8")
        self.assertIn('name="viewport"', html)
        self.assertIn('href="assets/radar.css"', html)
        self.assertIn('src="assets/radar.js?', html)
        for path in ("data/last_report.json", "data/content_queue.json", "data/metrics_7d.json"):
            self.assertIn(path, javascript)
        self.assertIn("6つの切り口と30秒動画パック", html)
        self.assertIn("Telegram", html)
        self.assertIn("pack.html?file=", javascript)
        self.assertIn('id="pack-main"', pack_html)
        self.assertIn("data\\/drafts\\/", pack_javascript)
        self.assertIn("navigator.clipboard", pack_javascript)
        self.assertIn("copyReady", pack_javascript)
        self.assertIn("この部分をコピー", pack_javascript)
        self.assertIn("copy-button", pack_html)
        self.assertIn("@media (max-width: 680px)", css)
        for secret_name in ("TELEGRAM_BOT_TOKEN", "CLOUDFLARE_API_TOKEN", "TELEGRAM_CHAT_ID"):
            self.assertNotIn(secret_name, html)
            self.assertNotIn(secret_name, javascript)
            self.assertNotIn(secret_name, pack_html)
            self.assertNotIn(secret_name, pack_javascript)

    def test_dashboard_has_no_external_runtime_dependency(self) -> None:
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("fonts.googleapis.com", html)
        self.assertNotIn("cdn.", html)
        self.assertNotIn("unpkg.com", html)


if __name__ == "__main__":
    unittest.main()
