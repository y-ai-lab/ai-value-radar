from __future__ import annotations

import unittest
from datetime import datetime, timezone

from ai_value_radar.models import Opportunity
from ai_value_radar.publishing import (
    calculate_content_score,
    mark_queue_posted,
    queue_summary,
    render_content_queue,
    select_publishing_topics,
    upsert_content_queue,
)


def sample_topic(status: str = "new") -> Opportunity:
    return Opportunity(
        id="topic1234567890",
        title="n8n launches a new AI workflow feature",
        url="https://n8n.io/blog/new-ai-workflow-feature",
        source="n8n_release",
        discovered_at="2026-08-31T00:00:00+00:00",
        last_seen_at="2026-08-31T00:00:00+00:00",
        status=status,
        summary="New AI automation workflow feature released for business users.",
        evidence="New AI automation workflow feature released for business users.",
        published_at="2026-08-31T00:00:00+00:00",
    )


class PublishingTests(unittest.TestCase):
    def test_official_fresh_ai_change_gets_content_score(self) -> None:
        score = calculate_content_score(
            sample_topic(),
            {"n8n_release": {"official": True, "kind": "github_releases"}},
            now=datetime(2026, 8, 31, 1, 0, tzinfo=timezone.utc),
        )
        self.assertGreaterEqual(score, 70)

    def test_topic_selection_excludes_revenue_top3(self) -> None:
        first = sample_topic()
        second = sample_topic()
        second.id = "topic0987654321"
        second.title = "Cloudflare launches new AI automation update"
        selected = select_publishing_topics(
            [first, second],
            {
                "n8n_release": {"official": True, "kind": "github_releases"},
                "cloudflare_release": {"official": True, "kind": "rss"},
            },
            excluded_ids={first.id},
            limit=2,
            min_score=35,
            now=datetime(2026, 8, 31, 1, 0, tzinfo=timezone.utc),
        )
        self.assertEqual([item.id for item in selected], [second.id])

    def test_content_queue_tracks_next_channel(self) -> None:
        item = sample_topic()
        pack = {
            "id": item.id,
            "path": f"data/drafts/{item.id}.md",
            "url": f"https://github.com/y-ai-lab/ai-value-radar/blob/main/data/drafts/{item.id}.md",
            "kind": "publishing",
        }
        queue = upsert_content_queue([], [item], [pack], "2026-08-31T01:00:00+00:00")
        self.assertEqual(queue_summary(queue), {"total": 1, "ready": 1, "in_progress": 0, "completed": 0})
        status, message = mark_queue_posted(queue, item.id[:8], "note", "2026-08-31T02:00:00+00:00")
        self.assertEqual(status, "updated")
        self.assertIn("note", message)
        self.assertEqual(queue[0]["status"], "in_progress")
        self.assertEqual(queue[0]["next_channel"], "x")
        self.assertEqual(queue[0]["channels"]["note"]["status"], "posted")
        rendered = render_content_queue(queue, "2026-08-31T02:00:00+00:00", "https://github.com/y-ai-lab/ai-value-radar")
        self.assertIn("次：X", rendered)
        self.assertIn("/posted コード 媒体", rendered)


if __name__ == "__main__":
    unittest.main()
