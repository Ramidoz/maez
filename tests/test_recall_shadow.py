import dataclasses
import unittest
from types import SimpleNamespace

from core.routing.recall_outcome import OutcomeClass, RecallOutcome, ReplyPath
from core.routing.recall_shadow import (
    ShadowOutcome,
    ShadowReach,
    ShadowReceipt,
    ShadowSkip,
    compute_shadow_pair_id,
    derive_shadow_outcome,
    derive_shadow_reach,
    derive_shadow_skipped,
)


class _FakeItem:
    def __init__(self, source_type, confirmed):
        self.source_type = source_type
        self.local_label = "E1"
        self.text = "x"
        self.temporal_provenance = {"confirmed": confirmed} if confirmed is not None else None


class _FakeWS:
    def __init__(self, items):
        self.items = items


def _legacy_rec(outcome, *, denial_kind="na", receipt_or_na="na", turn_kind="dated"):
    return RecallOutcome(
        mode="legacy",
        turn_kind=turn_kind,
        outcome_class=outcome,
        denial_kind=denial_kind,
        had_confirmed=None,
        citation_coverage=None,
        receipt_or_na=receipt_or_na,
        latency_ms=1,
        focused_elapsed_ms=None,
        reply_path=ReplyPath.LEGACY,
    )


class PairIdTest(unittest.TestCase):
    def test_absent_trace_id_degrades_to_na(self):
        self.assertEqual(compute_shadow_pair_id(boot_id="boot1", trace_id=""), "na")
        self.assertEqual(compute_shadow_pair_id(boot_id="boot1", trace_id=None), "na")

    def test_deterministic_and_not_raw_trace_id(self):
        a = compute_shadow_pair_id(boot_id="boot1", trace_id="TRACE_SENTINEL_RAW")
        b = compute_shadow_pair_id(boot_id="boot1", trace_id="TRACE_SENTINEL_RAW")
        self.assertEqual(a, b)
        self.assertEqual(len(a), 24)
        self.assertNotIn("TRACE_SENTINEL_RAW", a)

    def test_varies_by_boot_and_trace(self):
        self.assertNotEqual(
            compute_shadow_pair_id(boot_id="boot1", trace_id="t"),
            compute_shadow_pair_id(boot_id="boot2", trace_id="t"),
        )


class ShadowReachTest(unittest.TestCase):
    def test_confirmed_memory_context_is_grounded_material(self):
        ws = _FakeWS([_FakeItem("memory_context", True)])
        self.assertIs(
            derive_shadow_reach(ws, date_addressed=True),
            ShadowReach.GROUNDED_MATERIAL_AVAILABLE,
        )

    def test_consulted_no_confirmed_is_confirmed_absence(self):
        ws = _FakeWS([_FakeItem("memory_context", False)])
        self.assertIs(
            derive_shadow_reach(ws, date_addressed=True),
            ShadowReach.CONFIRMED_ABSENCE_WITNESSED,
        )

    def test_semantic_or_web_does_not_count_as_grounded(self):
        ws = _FakeWS([_FakeItem("web_context", True), _FakeItem("memory_context", False)])
        self.assertIs(
            derive_shadow_reach(ws, date_addressed=True),
            ShadowReach.CONFIRMED_ABSENCE_WITNESSED,
        )

    def test_confirmed_memory_evidence_does_not_count_as_grounded(self):
        ws = _FakeWS([_FakeItem("memory_evidence", True)])
        self.assertIs(
            derive_shadow_reach(ws, date_addressed=True),
            ShadowReach.CONFIRMED_ABSENCE_WITNESSED,
        )

    def test_non_dated_turn_cannot_witness_dated_absence(self):
        ws = _FakeWS([_FakeItem("memory_context", False)])
        self.assertIs(
            derive_shadow_reach(ws, date_addressed=False),
            ShadowReach.CARRIER_UNAVAILABLE,
        )

    def test_none_working_set_is_carrier_unavailable(self):
        self.assertIs(
            derive_shadow_reach(None, date_addressed=True),
            ShadowReach.CARRIER_UNAVAILABLE,
        )


class ShadowOutcomeDeriveTest(unittest.TestCase):
    def test_rescuable_when_legacy_declined_and_shadow_grounded(self):
        rec = derive_shadow_outcome(
            legacy_rec=_legacy_rec(OutcomeClass.DECLINED_UNAVAILABLE),
            shadow_reach=ShadowReach.GROUNDED_MATERIAL_AVAILABLE,
            date_addressed=True,
            shadow_pair_id="p",
            latency_delta_ms=3,
            ts=1,
            boot_id="b",
        )
        self.assertTrue(rec.rescuable_candidate)
        self.assertFalse(rec.false_absence_candidate)
        self.assertEqual(rec.shadow_skipped, "na")
        self.assertIs(rec.receipt_state, ShadowReceipt.CONSULTED)

    def test_false_absence_candidate_when_shadow_absent_but_legacy_answered(self):
        rec = derive_shadow_outcome(
            legacy_rec=_legacy_rec(OutcomeClass.ANSWERED_UNVERIFIABLE),
            shadow_reach=ShadowReach.CONFIRMED_ABSENCE_WITNESSED,
            date_addressed=True,
            shadow_pair_id="p",
            latency_delta_ms=3,
            ts=1,
            boot_id="b",
        )
        self.assertTrue(rec.false_absence_candidate)

    def test_continuity_only_cannot_be_false_absence_candidate(self):
        rec = derive_shadow_outcome(
            legacy_rec=_legacy_rec(OutcomeClass.ANSWERED_UNVERIFIABLE, turn_kind="continuity"),
            shadow_reach=ShadowReach.CONFIRMED_ABSENCE_WITNESSED,
            date_addressed=False,
            shadow_pair_id="p",
            latency_delta_ms=3,
            ts=1,
            boot_id="b",
        )
        self.assertFalse(rec.false_absence_candidate)

    def test_legacy_false_absence_rescuable(self):
        false_absence = _legacy_rec(
            OutcomeClass.DECLINED_UNVERIFIED,
            denial_kind="no_dated_memory",
            receipt_or_na="na",
        )
        rec = derive_shadow_outcome(
            legacy_rec=false_absence,
            shadow_reach=ShadowReach.GROUNDED_MATERIAL_AVAILABLE,
            date_addressed=True,
            shadow_pair_id="p",
            latency_delta_ms=3,
            ts=1,
            boot_id="b",
        )
        self.assertTrue(rec.legacy_false_absence_rescuable)

    def test_skipped_rows_are_pairable_and_content_free(self):
        rec = derive_shadow_skipped(
            legacy_rec=_legacy_rec(OutcomeClass.DECLINED_UNAVAILABLE),
            skip_reason=ShadowSkip.QUEUE_FULL,
            shadow_pair_id="p",
            latency_delta_ms=0,
            ts=1,
            boot_id="b",
        )
        self.assertEqual(rec.shadow_skipped, ShadowSkip.QUEUE_FULL.value)
        self.assertEqual(rec.shadow_pair_id, "p")
        self.assertEqual(rec.ts, 1)
        self.assertEqual(rec.boot_id, "b")
        self.assertIs(rec.receipt_state, ShadowReceipt.NOT_CONSULTED)


class ContentFreeAndClosedEnumTest(unittest.TestCase):
    def test_record_is_content_free(self):
        names = {f.name for f in dataclasses.fields(ShadowOutcome)}
        forbidden = {
            "query_text",
            "text",
            "raw_text",
            "reply",
            "recalled_snippet",
            "content",
            "owner_question",
            "snippet",
            "trace_id",
            "exception_message",
        }
        self.assertEqual(names & forbidden, set())

    def test_skip_reasons_closed(self):
        self.assertEqual(
            {s.value for s in ShadowSkip},
            {"budget_exceeded", "queue_full", "exception"},
        )

    def test_receipt_state_closed(self):
        self.assertEqual({s.value for s in ShadowReceipt}, {"consulted", "not_consulted"})

    def test_schema_version(self):
        self.assertEqual(ShadowOutcome.schema_version, "shadow_outcome.v1")


if __name__ == "__main__":
    unittest.main()
