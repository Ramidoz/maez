import unittest

from core.routing.recall_self_status import (
    RecallLiveness,
    RecallStatusReceipt,
    build_recall_practice_reply,
    build_recall_status_reply,
    is_recall_practice_query,
    is_recall_status_query,
    recall_status_query_wants_timestamp,
)


class IntentMatchTest(unittest.TestCase):
    def test_positive_triggers(self):
        for q in (
            "is your dated recall reachable?",
            "is your dated recall working right now?",
            "can you reach your dated memory?",
            "when did you last check your dated recall?",
            "is your dated recall reachable and when did you last check your dated recall?",
        ):
            self.assertTrue(is_recall_status_query(q), q)

    def test_timestamp_request_detection(self):
        self.assertTrue(recall_status_query_wants_timestamp("when did you last check your dated recall?"))
        self.assertFalse(recall_status_query_wants_timestamp("is your dated recall reachable?"))

    def test_hard_false_positive_corpus_is_empty(self):
        for q in (
            "is your memory okay?",
            "do you recall yesterday?",
            "can you reach me?",
            "what did we discuss around April 27?",
            "what were we just talking about?",
            "are you working?",
            "is your dated memory of April 27 accurate?",
            "is your dated recall what we used yesterday?",
            "is your dated recall from April 27 relevant?",
            "the dated recall system is working well after the fix",
            "if your dated recall is working, what did we decide April 27?",
            "is your dated recall up and what did we decide Monday?",
            "is your dated memory reachable and what did we note around April 27?",
            "is your dated memory reachable and when did we decide on April 27?",
        ):
            self.assertFalse(is_recall_status_query(q), q)


class StatusReplyTest(unittest.TestCase):
    def _receipt(self, **kw):
        base = dict(receipt="consulted", at_ts=1000.0, boot_id="bootA")
        base.update(kw)
        return RecallStatusReceipt(**base)

    def test_off_by_config(self):
        reply, state = build_recall_status_reply(
            triad_on=False,
            carrier_reachable_from_surface=True,
            last_receipt=None,
            current_boot_id="bootA",
            now_ts=1100.0,
        )
        self.assertIs(state, RecallLiveness.OFF_BY_CONFIG)
        self.assertIn("can't reach my dated memory", reply.lower())

    def test_unreachable_from_surface(self):
        reply, state = build_recall_status_reply(
            triad_on=True,
            carrier_reachable_from_surface=False,
            last_receipt=self._receipt(),
            current_boot_id="bootA",
            now_ts=1100.0,
        )
        self.assertIs(state, RecallLiveness.UNREACHABLE_FROM_SURFACE)
        self.assertIn("from this surface", reply.lower())

    def test_on_never_consulted_when_no_receipt(self):
        reply, state = build_recall_status_reply(
            triad_on=True,
            carrier_reachable_from_surface=True,
            last_receipt=None,
            current_boot_id="bootA",
            now_ts=1100.0,
        )
        self.assertIs(state, RecallLiveness.ON_NEVER_CONSULTED)
        self.assertIn("dated memory is reachable", reply.lower())
        self.assertIn("haven't checked", reply.lower())

    def test_on_never_consulted_when_receipt_from_prior_boot(self):
        r = self._receipt(receipt="consulted", at_ts=1099.0, boot_id="bootPREV")
        reply, state = build_recall_status_reply(
            triad_on=True,
            carrier_reachable_from_surface=True,
            last_receipt=r,
            current_boot_id="bootA",
            now_ts=1100.0,
        )
        self.assertIs(state, RecallLiveness.ON_NEVER_CONSULTED)
        self.assertNotIn("just a moment ago", reply.lower())

    def test_on_ok_recent_same_boot(self):
        r = self._receipt(receipt="consulted", at_ts=1099.0, boot_id="bootA")
        reply, state = build_recall_status_reply(
            triad_on=True,
            carrier_reachable_from_surface=True,
            last_receipt=r,
            current_boot_id="bootA",
            now_ts=1100.0,
        )
        self.assertIs(state, RecallLiveness.ON_OK)
        self.assertIn("checked it just a moment ago", reply.lower())

    def test_timestamp_only_when_requested(self):
        r = self._receipt(receipt="consulted", at_ts=1000.0, boot_id="bootA")
        no_ts, _ = build_recall_status_reply(
            triad_on=True,
            carrier_reachable_from_surface=True,
            last_receipt=r,
            current_boot_id="bootA",
            now_ts=1100.0,
            include_timestamp=False,
        )
        with_ts, _ = build_recall_status_reply(
            triad_on=True,
            carrier_reachable_from_surface=True,
            last_receipt=r,
            current_boot_id="bootA",
            now_ts=1100.0,
            include_timestamp=True,
        )
        self.assertNotIn("1970-01-01", no_ts)
        self.assertIn("1970-01-01T00:16:40+00:00", with_ts)

    def test_on_consult_failed(self):
        r = self._receipt(receipt="consult_failed", at_ts=1099.0, boot_id="bootA")
        reply, state = build_recall_status_reply(
            triad_on=True,
            carrier_reachable_from_surface=True,
            last_receipt=r,
            current_boot_id="bootA",
            now_ts=1100.0,
        )
        self.assertIs(state, RecallLiveness.ON_CONSULT_FAILED)
        self.assertIn("errored", reply.lower())
        self.assertIn("dated memory is reachable", reply.lower())

    def test_unknown_same_boot_receipt_uses_being_shaped_fallback(self):
        r = self._receipt(receipt="not_consulted", at_ts=1099.0, boot_id="bootA")
        reply, state = build_recall_status_reply(
            triad_on=True,
            carrier_reachable_from_surface=True,
            last_receipt=r,
            current_boot_id="bootA",
            now_ts=1100.0,
        )
        self.assertIs(state, RecallLiveness.ON_NEVER_CONSULTED)
        low = reply.lower()
        self.assertIn("dated memory is reachable", low)
        self.assertNotIn("last dated turn did not actually consult", low)

    def test_stale_consulted_same_boot_degrades(self):
        r = self._receipt(receipt="consulted", at_ts=1000.0, boot_id="bootA")
        reply, state = build_recall_status_reply(
            triad_on=True,
            carrier_reachable_from_surface=True,
            last_receipt=r,
            current_boot_id="bootA",
            now_ts=1000.0 + 6 * 3600 + 1,
        )
        self.assertIs(state, RecallLiveness.ON_OK)
        self.assertNotIn("just a moment ago", reply.lower())
        self.assertIn("a while back", reply.lower())

    def test_genderless(self):
        for r in (None, self._receipt()):
            reply, _ = build_recall_status_reply(
                triad_on=True,
                carrier_reachable_from_surface=True,
                last_receipt=r,
                current_boot_id="bootA",
                now_ts=1100.0,
            )
            low = reply.lower()
            for bad in (" she ", " he ", " her ", " his ", " hers "):
                self.assertNotIn(bad, f" {low} ")


class PracticeStatusTest(unittest.TestCase):
    def test_practice_query_matches(self):
        for q in (
            "are you practicing recall quietly?",
            "are you running anything in the background?",
        ):
            self.assertTrue(is_recall_practice_query(q), q)

    def test_ordinary_not_matched(self):
        for q in (
            "what did we decide on April 27?",
            "is your dated recall reachable?",
            "are you practicing piano?",
            "what were we just talking about?",
        ):
            self.assertFalse(is_recall_practice_query(q), q)

    def test_reply_reflects_shadow_state(self):
        receipt = {"at_ts": 1099.0, "boot_id": "bootA", "state": "consulted"}
        on, state = build_recall_practice_reply(
            shadow_enabled=True,
            last_shadow_receipt=receipt,
            current_boot_id="bootA",
            now_ts=1100.0,
        )
        self.assertEqual(state, "active_recent")
        self.assertIn("quietly", on.lower())
        off, state = build_recall_practice_reply(
            shadow_enabled=False,
            last_shadow_receipt=None,
            current_boot_id="bootA",
            now_ts=1100.0,
        )
        self.assertEqual(state, "off")
        self.assertNotIn("quietly practicing", off.lower())

    def test_recent_skip_does_not_claim_active_practice(self):
        receipt = {"at_ts": 1099.0, "boot_id": "bootA", "state": "queue_full"}
        reply, state = build_recall_practice_reply(
            shadow_enabled=True,
            last_shadow_receipt=receipt,
            current_boot_id="bootA",
            now_ts=1100.0,
        )
        self.assertEqual(state, "active_recent_skipped")
        low = reply.lower()
        self.assertIn("last quiet practice attempt was skipped", low)
        self.assertNotIn("quietly practicing dated recall", low)

    def test_stale_shadow_receipt_does_not_sound_current(self):
        receipt = {"at_ts": 1000.0, "boot_id": "bootA", "state": "consulted"}
        reply, state = build_recall_practice_reply(
            shadow_enabled=True,
            last_shadow_receipt=receipt,
            current_boot_id="bootA",
            now_ts=4000.0,
        )
        self.assertEqual(state, "active_stale")
        self.assertIn("reachable", reply.lower())
        self.assertNotIn("just practiced", reply.lower())


if __name__ == "__main__":
    unittest.main()
