import os
import unittest

from core.brain.conversation_controller import ConversationController


def _make_controller() -> ConversationController:
    return ConversationController(memory=None, pipeline=None, daemon=None)


def _offer_reply() -> str:
    return "I can search for the current SearXNG release if you want."


def _probe_bridge_reply() -> str:
    return "I've already proposed a search for your approval."


class SearchCommitmentLegacySupersessionTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("MAEZ_SEARCH_COMMITMENT_ENABLED", None)
        self.addCleanup(lambda: os.environ.pop("MAEZ_SEARCH_COMMITMENT_ENABLED", None))

    def test_flag_on_short_circuits_all_three_legacy_offer_paths(self):
        os.environ["MAEZ_SEARCH_COMMITMENT_ENABLED"] = "1"
        ctrl = _make_controller()

        stored = ctrl.maybe_store_offer(
            "telegram_text",
            "owner",
            reply=_offer_reply(),
            raw_user_text="searxng release",
            query_deriver=lambda raw: raw,
        )
        probe_stored = ctrl.maybe_store_probe_bridge_offer(
            "telegram_text",
            "owner",
            reply=_probe_bridge_reply(),
            raw_user_text="searxng release",
            query_deriver=lambda raw: raw,
            had_action=True,
        )
        status, offer = ctrl.consume_offer_approval("telegram_text", "owner", "sure")

        self.assertFalse(stored)
        self.assertFalse(probe_stored)
        self.assertEqual((status, offer), ("none", None))
        self.assertEqual(ctrl._offers, {})

    def test_flag_off_preserves_legacy_offer_storage_and_fire_contract(self):
        ctrl = _make_controller()

        self.assertTrue(
            ctrl.maybe_store_offer(
                "telegram_text",
                "owner",
                reply=_offer_reply(),
                raw_user_text="searxng release",
                query_deriver=lambda raw: raw,
            )
        )
        status, offer = ctrl.consume_offer_approval("telegram_text", "owner", "sure")

        self.assertEqual(status, "fire")
        self.assertEqual(offer["kind"], "web_search")
        self.assertEqual(offer["query"], "searxng release")
        self.assertEqual(ctrl._offers, {})


if __name__ == "__main__":
    unittest.main()
