import unittest

from core.safety.action_receipts import (
    ACTION_WEB_SEARCH,
    build_search_tool_result,
    has_action_receipt,
)


class ActionReceipts(unittest.TestCase):
    def test_build_search_tool_result_is_content_light_and_typed(self):
        result = {
            "success": True,
            "result_count": 3,
            "source": "searxng",
            "timestamp": "2026-07-01 17:45:56",
            "results": [
                {
                    "title": "A",
                    "url": "https://example.test/a",
                    "snippet": "long private snippet",
                },
            ],
        }

        receipt = build_search_tool_result(
            query="singularity recent developments",
            result=result,
            source="telegram_pipeline_a",
        )

        self.assertEqual(receipt["name"], "web_search")
        self.assertEqual(receipt["tool"], "web_search")
        self.assertEqual(receipt["action_type"], ACTION_WEB_SEARCH)
        self.assertEqual(receipt["status"], "ok")
        self.assertEqual(receipt["result_count"], 3)
        self.assertEqual(receipt["source"], "telegram_pipeline_a")
        self.assertIn("web_search ok result_count=3", receipt["summary"])
        self.assertNotIn("long private snippet", str(receipt))
        self.assertNotIn("https://example.test", str(receipt))

    def test_empty_search_is_still_a_search_receipt(self):
        receipt = build_search_tool_result(
            query="rare query",
            result={
                "success": True,
                "result_count": 0,
                "results": [],
                "source": "searxng",
            },
            source="telegram_pipeline_a",
        )

        self.assertEqual(receipt["status"], "empty")
        self.assertTrue(
            has_action_receipt({"tool_results": [receipt]}, ACTION_WEB_SEARCH),
        )

    def test_failed_search_is_still_a_search_receipt(self):
        receipt = build_search_tool_result(
            query="rare query",
            result={
                "success": False,
                "result_count": 0,
                "results": [],
                "source": "searxng",
            },
            source="telegram_pipeline_a",
        )

        self.assertEqual(receipt["status"], "failed")
        self.assertTrue(
            has_action_receipt({"tool_results": [receipt]}, ACTION_WEB_SEARCH),
        )

    def test_unrelated_tool_does_not_satisfy_search(self):
        envelope = {
            "tool_results": [
                {
                    "name": "weather",
                    "tool": "weather",
                    "action_type": "weather",
                    "status": "ok",
                    "summary": "weather fetched",
                },
            ],
        }

        self.assertFalse(has_action_receipt(envelope, ACTION_WEB_SEARCH))

    def test_explicit_mismatched_action_type_does_not_satisfy_search(self):
        envelope = {
            "tool_results": [
                {
                    "name": "web_search",
                    "tool": "web_search",
                    "action_type": "weather",
                    "status": "ok",
                    "summary": "weather result shaped like a search label",
                },
            ],
        }

        self.assertFalse(has_action_receipt(envelope, ACTION_WEB_SEARCH))


if __name__ == "__main__":
    unittest.main()
