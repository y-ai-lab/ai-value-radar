from __future__ import annotations

import unittest

from ai_value_radar.ai import parse_json_object, validate_ai_result


VALID = {
    "score": 87,
    "title": "AI SaaS lifetime deal",
    "category": "lifetime_deal",
    "summary": "買い切りプランが公開された。",
    "why_now": "期限候補がある。",
    "best_for": "AIツールを試す人。",
    "skip_if": "商用利用が必要で条件が不明な場合。",
    "monetization": "作業コスト削減に転用できる。",
    "risk": "公式条件を確認する。",
    "confidence": 0.82,
}


class AITests(unittest.TestCase):
    def test_json_fence_is_parsed_and_validated(self) -> None:
        parsed = parse_json_object("```json\n" + __import__("json").dumps(VALID, ensure_ascii=False) + "\n```")
        normalized, errors = validate_ai_result(parsed)
        self.assertEqual(errors, [])
        self.assertEqual(normalized["score"], 87)

    def test_invalid_score_is_rejected(self) -> None:
        invalid = dict(VALID)
        invalid["score"] = 101
        normalized, errors = validate_ai_result(invalid)
        self.assertIsNone(normalized)
        self.assertIn("invalid:score", errors)


if __name__ == "__main__":
    unittest.main()
