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

    def test_topic_gets_reader_facing_context(self) -> None:
        item = sample_topic()
        item.service_name = "n8n"
        item.github_repository = "n8n-io/n8n"
        selected = select_publishing_topics(
            [item],
            {"n8n_release": {"official": True, "kind": "github_releases"}},
            limit=1,
            min_score=35,
            now=datetime(2026, 8, 31, 1, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(len(selected), 1)
        self.assertIn("定型作業", selected[0].content_angle)
        self.assertIn("転記", selected[0].reader_problem)
        self.assertIn("公式ドキュメント", selected[0].reader_action)

    def test_topic_selection_prefers_different_services(self) -> None:
        first = sample_topic()
        first.service_name = "n8n"
        second = sample_topic()
        second.id = "topic2222222222"
        second.service_name = "n8n"
        second.title = "n8n publishes another AI workflow update"
        third = sample_topic()
        third.id = "topic3333333333"
        third.service_name = "Flowise"
        third.title = "Flowise publishes a new AI workflow update"
        selected = select_publishing_topics(
            [first, second, third],
            {"n8n_release": {"official": True, "kind": "github_releases"}},
            limit=2,
            min_score=35,
            now=datetime(2026, 8, 31, 1, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(len(selected), 2)
        self.assertEqual({item.service_name for item in selected}, {"n8n", "Flowise"})

    def test_noisy_github_search_project_is_not_a_publishing_topic(self) -> None:
        item = Opportunity(
            id="noisy1234567890",
            title="News Minimalist",
            url="https://github.com/demo/news-minimalist",
            source="github_ai_repositories",
            discovered_at="2026-08-31T00:00:00+00:00",
            last_seen_at="2026-08-31T00:00:00+00:00",
            status="new",
            summary="AI-powered news aggregator and satirical guide.",
            evidence="AI-powered news aggregator and satirical guide.",
            github_stars=20,
            published_at="2026-08-31T00:00:00+00:00",
        )
        selected = select_publishing_topics(
            [item],
            {"github_ai_repositories": {"official": True, "kind": "github_search"}},
            limit=1,
            min_score=35,
            now=datetime(2026, 8, 31, 1, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(selected, [])

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
