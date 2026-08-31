from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ai_value_radar.telegram as telegram
from ai_value_radar.article import generate_article_drafts
from ai_value_radar.config import Settings
from ai_value_radar.models import Opportunity
from ai_value_radar.publishing import upsert_content_queue, write_content_queue
from ai_value_radar.state import write_json_atomic


def sample_history_item() -> Opportunity:
    return Opportunity(
        id="abcdef1234567890",
        title="AI automation lifetime deal",
        url="https://vendor.example/deal",
        source="official_vendor",
        discovered_at="2026-08-31T00:00:00+00:00",
        last_seen_at="2026-08-31T00:00:00+00:00",
        category="lifetime_deal",
        summary="Lifetime access $69 instead of $199.",
        evidence="Lifetime access $69 instead of $199.",
        rule_score=70,
        final_score=70,
        content_hash="hash",
    )


class TelegramCommandTests(unittest.TestCase):
    def test_parse_documented_commands_only(self) -> None:
        self.assertEqual(telegram.parse_command("/good abc12345"), ("good", ["abc12345"]))
        self.assertEqual(telegram.parse_command("/posted abc12345 threads"), ("posted", ["abc12345", "threads"]))
        self.assertEqual(
            telegram.parse_command("/result abc12345 views=100 clicks=5 sales=1 revenue=4900"),
            ("result", ["abc12345", "views=100", "clicks=5", "sales=1", "revenue=4900"]),
        )
        self.assertEqual(telegram.parse_command("/validate abc12345 signal"), ("validate", ["abc12345", "signal"]))
        self.assertEqual(telegram.parse_command("/good@my_radar abc12345"), ("good", ["abc12345"]))
        self.assertIsNone(telegram.parse_command("hello"))
        self.assertIsNone(telegram.parse_command("/unknown abc12345"))

    def test_feedback_usage_and_queue_commands_are_applied_without_saving_chat_data(self) -> None:
        item = sample_history_item()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json_atomic(root / "opportunities.json", [item.to_dict()])
            with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test-token", "TELEGRAM_CHAT_ID": "123"}, clear=False):
                settings = Settings(max_telegram_updates_per_run=10)
                drafts, errors = generate_article_drafts(
                    [item], root, "https://github.com/y-ai-lab/ai-value-radar", "2026-08-31T00:00:00+00:00"
                )
                self.assertEqual(errors, [])
                queue = upsert_content_queue([], [item], drafts, "2026-08-31T00:00:00+00:00")
                write_json_atomic(root / "content_queue.json", queue)
                write_content_queue(root / "content_queue.md", queue, "2026-08-31T00:00:00+00:00", settings.repository_url)
                updates = [
                    {"update_id": 100, "message": {"chat": {"id": 123}, "text": "/good abcdef12"}},
                    {"update_id": 101, "message": {"chat": {"id": 123}, "text": "/used abcdef12"}},
                    {"update_id": 102, "message": {"chat": {"id": 123}, "text": "/posted abcdef12 x"}},
                    {"update_id": 103, "message": {"chat": {"id": 123}, "text": "/result abcdef12 views=100 clicks=5 signups=1 sales=0 revenue=0"}},
                    {"update_id": 104, "message": {"chat": {"id": 123}, "text": "/validate abcdef12 signal"}},
                ]
                sent: list[str] = []
                with patch.object(telegram, "_get_updates", return_value=updates), patch.object(
                    telegram, "_send", side_effect=lambda text: sent.append(text)
                ):
                    result = telegram.process_telegram_updates(settings, root, "2026-08-31T01:00:00+00:00")

            self.assertEqual(result["received"], 5)
            self.assertEqual(result["feedback_valuable"], 1)
            self.assertEqual(result["usage_updated"], 1)
            self.assertEqual(result["posted_count"], 1)
            self.assertEqual(result["outcome_updated"], 1)
            self.assertEqual(result["validation_updated"], 1)
            stored = json.loads((root / "opportunities.json").read_text(encoding="utf-8"))
            self.assertEqual(stored[0]["value_feedback"], "valuable")
            self.assertEqual(stored[0]["usage_status"], "used")
            self.assertEqual(stored[0]["validation_status"], "signal")
            self.assertEqual(stored[0]["clicks"], 5)
            self.assertEqual(stored[0]["outcome_status"], "signal")
            queued = json.loads((root / "content_queue.json").read_text(encoding="utf-8"))
            self.assertEqual(queued[0]["channels"]["x"]["status"], "posted")
            self.assertEqual(queued[0]["signups"], 1)
            self.assertTrue((root / "drafts" / f"{item.id}.md").exists())
            offset = json.loads((root / "telegram_state.json").read_text(encoding="utf-8"))
            self.assertEqual(offset, {"update_offset": 105})
            self.assertTrue(sent)
            self.assertNotIn("123", (root / "telegram_state.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
