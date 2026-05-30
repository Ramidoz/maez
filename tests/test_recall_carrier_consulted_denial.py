import unittest

from daemon.maez_daemon import (
    RECALL_CARRIER_CONSULT_FAILED,
    RECALL_CARRIER_CONSULTED,
    RECALL_CARRIER_NOT_CONSULTED,
    _dated_denial_decision,
    _dated_denial_kind,
    _dated_denial_reply,
)


class DatedDenialReplyTest(unittest.TestCase):
    def test_carrier_not_consulted_says_path_unavailable(self):
        reply = _dated_denial_reply(
            carrier_receipt=RECALL_CARRIER_NOT_CONSULTED,
            had_confirmed=False,
        )
        self.assertIn("can't reach my dated memory from here right now", reply.lower())
        self.assertNotIn("capability", reply.lower())
        self.assertNotIn("don't have a dated memory", reply.lower())

    def test_carrier_consult_failed_says_lookup_errored_not_inactive(self):
        reply = _dated_denial_reply(
            carrier_receipt=RECALL_CARRIER_CONSULT_FAILED,
            had_confirmed=False,
        )
        lowered = reply.lower()
        self.assertIn("went to check my dated memory", lowered)
        self.assertIn("lookup errored out", lowered)
        self.assertIn("not an absence", lowered)
        self.assertIn("ask me again in a moment", lowered)
        self.assertNotIn("capability", lowered)
        self.assertNotIn("don't have a dated memory", reply.lower())

    def test_consulted_with_confirmed_item_but_synthesis_failed(self):
        reply = _dated_denial_reply(
            carrier_receipt=RECALL_CARRIER_CONSULTED,
            had_confirmed=True,
        )
        self.assertIn("couldn't pull it together", reply.lower())

    def test_consulted_no_match_says_no_dated_memory(self):
        reply = _dated_denial_reply(
            carrier_receipt=RECALL_CARRIER_CONSULTED,
            had_confirmed=False,
        )
        self.assertIn("don't have a dated memory for that window", reply.lower())

    def test_reply_and_telemetry_kind_are_derived_from_one_decision(self):
        decision = _dated_denial_decision(
            carrier_receipt=RECALL_CARRIER_CONSULT_FAILED,
            had_confirmed=False,
        )

        self.assertEqual(decision.kind, "carrier_failed")
        self.assertEqual(
            decision.reply,
            _dated_denial_reply(
                carrier_receipt=RECALL_CARRIER_CONSULT_FAILED,
                had_confirmed=False,
            ),
        )
        self.assertEqual(
            decision.kind,
            _dated_denial_kind(
                carrier_receipt=RECALL_CARRIER_CONSULT_FAILED,
                had_confirmed=False,
            ),
        )


class AvailabilityNotConsultationTest(unittest.TestCase):
    def test_dated_turn_without_focused_candidate_is_not_consulted(self):
        from core.routing.reply_mode import (
            ReplyDecisionSignals,
            ReplyMode,
            resolve_reply_mode,
        )

        decision = resolve_reply_mode(
            ReplyDecisionSignals(
                authoritative_tool_reply=False,
                echo_reply=False,
                honest_empty_candidate=False,
                focused_candidate=False,
                date_addressed=True,
            )
        )
        self.assertIsNot(decision.mode, ReplyMode.FOCUSED)


if __name__ == "__main__":
    unittest.main()
