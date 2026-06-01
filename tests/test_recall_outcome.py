import dataclasses
import unittest
from types import SimpleNamespace

from core.routing.recall_outcome import (
    OutcomeClass,
    RecallOutcome,
    ReplyPath,
    citation_support,
    cites_confirmed_memory_context,
    classify_outcome,
    format_log_value,
    is_false_absence,
    reply_path_from_mode,
)
from core.routing.recall_receipt import AckStatus


class ClassifyOutcomeTest(unittest.TestCase):
    def test_consulted_grounded_dated_context(self):
        oc = classify_outcome(
            mode="recall_triad",
            turn_kind="dated",
            answered=True,
            receipt="consulted",
            denial_kind="na",
            had_confirmed=True,
            cited_grounded_context=True,
            unmatched_citations=0,
        )
        self.assertIs(oc, OutcomeClass.ANSWERED_GROUNDED)

    def test_consulted_no_match_is_legal_absence(self):
        oc = classify_outcome(
            mode="recall_triad",
            turn_kind="dated",
            answered=False,
            receipt="consulted",
            denial_kind="no_dated_memory",
            had_confirmed=False,
            cited_grounded_context=False,
            unmatched_citations=0,
        )
        self.assertIs(oc, OutcomeClass.DECLINED_ABSENCE)

    def test_not_consulted_is_unavailable_not_absence(self):
        oc = classify_outcome(
            mode="recall_triad",
            turn_kind="dated",
            answered=False,
            receipt="not_consulted",
            denial_kind="carrier_unavailable",
            had_confirmed=False,
            cited_grounded_context=False,
            unmatched_citations=0,
        )
        self.assertIs(oc, OutcomeClass.DECLINED_UNAVAILABLE)

    def test_consult_failed_is_failed_not_absence(self):
        oc = classify_outcome(
            mode="recall_triad",
            turn_kind="dated",
            answered=False,
            receipt="consult_failed",
            denial_kind="carrier_failed",
            had_confirmed=False,
            cited_grounded_context=False,
            unmatched_citations=0,
        )
        self.assertIs(oc, OutcomeClass.DECLINED_FAILED)

    def test_transport_failure_is_declined_transport_not_absence(self):
        oc = classify_outcome(
            mode="recall_triad",
            turn_kind="dated",
            answered=False,
            receipt="consulted",
            denial_kind="transport_failure",
            had_confirmed=True,
            cited_grounded_context=False,
            unmatched_citations=0,
        )
        self.assertIs(oc, OutcomeClass.DECLINED_TRANSPORT)

    def test_answered_ungrounded_when_unmatched_citations(self):
        oc = classify_outcome(
            mode="recall_triad",
            turn_kind="dated",
            answered=True,
            receipt="consulted",
            denial_kind="na",
            had_confirmed=True,
            cited_grounded_context=True,
            unmatched_citations=2,
        )
        self.assertIs(oc, OutcomeClass.ANSWERED_UNGROUNDED)

    def test_legacy_dated_answer_is_unverifiable(self):
        oc = classify_outcome(
            mode="legacy",
            turn_kind="dated",
            answered=True,
            receipt="na",
            denial_kind="na",
            had_confirmed=None,
            cited_grounded_context=False,
            unmatched_citations=0,
            asserts_absence=False,
        )
        self.assertIs(oc, OutcomeClass.ANSWERED_UNVERIFIABLE)

    def test_legacy_absence_phrase_wins_over_nonempty_answer(self):
        oc = classify_outcome(
            mode="legacy",
            turn_kind="dated",
            answered=True,
            receipt="na",
            denial_kind="na",
            had_confirmed=None,
            cited_grounded_context=False,
            unmatched_citations=0,
            asserts_absence=True,
        )
        self.assertIs(oc, OutcomeClass.DECLINED_UNVERIFIED)

    def test_legacy_dated_absence_claim_is_declined_unverified(self):
        oc = classify_outcome(
            mode="legacy",
            turn_kind="dated",
            answered=False,
            receipt="na",
            denial_kind="na",
            had_confirmed=None,
            cited_grounded_context=False,
            unmatched_citations=0,
            asserts_absence=True,
        )
        self.assertIs(oc, OutcomeClass.DECLINED_UNVERIFIED)

    def test_legacy_carrier_unavailable_remains_reachability_not_absence(self):
        oc = classify_outcome(
            mode="legacy",
            turn_kind="dated",
            answered=False,
            receipt="na",
            denial_kind="carrier_unavailable",
            had_confirmed=None,
            cited_grounded_context=False,
            unmatched_citations=0,
            asserts_absence=False,
        )
        self.assertIs(oc, OutcomeClass.DECLINED_UNAVAILABLE)

    def test_ordinary_legacy_answer_is_ordinary_answered_not_unverifiable(self):
        oc = classify_outcome(
            mode="legacy",
            turn_kind="ordinary",
            answered=True,
            receipt="na",
            denial_kind="na",
            had_confirmed=None,
            cited_grounded_context=False,
            unmatched_citations=0,
        )
        self.assertIs(oc, OutcomeClass.ORDINARY_ANSWERED)

    def test_ordinary_triad_answer_is_ordinary_answered(self):
        oc = classify_outcome(
            mode="recall_triad",
            turn_kind="ordinary",
            answered=True,
            receipt="not_consulted",
            denial_kind="na",
            had_confirmed=False,
            cited_grounded_context=False,
            unmatched_citations=0,
        )
        self.assertIs(oc, OutcomeClass.ORDINARY_ANSWERED)

    def test_mixed_support_when_flagged(self):
        oc = classify_outcome(
            mode="recall_triad",
            turn_kind="both",
            answered=True,
            receipt="consulted",
            denial_kind="na",
            had_confirmed=True,
            cited_grounded_context=False,
            unmatched_citations=0,
            cited_mixed_support=True,
        )
        self.assertIs(oc, OutcomeClass.ANSWERED_MIXED_SUPPORT)
        self.assertEqual(oc.value, "answered_mixed_support")

    def test_grounded_wins_over_mixed(self):
        oc = classify_outcome(
            mode="recall_triad",
            turn_kind="both",
            answered=True,
            receipt="consulted",
            denial_kind="na",
            had_confirmed=True,
            cited_grounded_context=True,
            unmatched_citations=0,
            cited_mixed_support=True,
        )
        self.assertIs(oc, OutcomeClass.ANSWERED_GROUNDED)

    def test_mixed_with_unmatched_is_ungrounded(self):
        oc = classify_outcome(
            mode="recall_triad",
            turn_kind="both",
            answered=True,
            receipt="consulted",
            denial_kind="na",
            had_confirmed=True,
            cited_grounded_context=False,
            unmatched_citations=1,
            cited_mixed_support=True,
        )
        self.assertIs(oc, OutcomeClass.ANSWERED_UNGROUNDED)

    def test_ordinary_ignores_mixed_flag(self):
        oc = classify_outcome(
            mode="recall_triad",
            turn_kind="ordinary",
            answered=True,
            receipt="not_consulted",
            denial_kind="na",
            had_confirmed=False,
            cited_grounded_context=False,
            unmatched_citations=0,
            cited_mixed_support=True,
        )
        self.assertIs(oc, OutcomeClass.ORDINARY_ANSWERED)

    def test_legacy_ignores_mixed_flag(self):
        oc = classify_outcome(
            mode="legacy",
            turn_kind="both",
            answered=True,
            receipt="na",
            denial_kind="na",
            had_confirmed=None,
            cited_grounded_context=False,
            unmatched_citations=0,
            cited_mixed_support=True,
        )
        self.assertIs(oc, OutcomeClass.ANSWERED_UNVERIFIABLE)


class CitationSupportTest(unittest.TestCase):
    def _item(self, label, source_type, confirmed):
        return SimpleNamespace(
            local_label=label,
            source_type=source_type,
            temporal_provenance={"confirmed": confirmed} if confirmed is not None else None,
        )

    def test_all_confirmed_memory_is_grounded(self):
        result = SimpleNamespace(cited_ids=["E1", "E2"])
        working_set = SimpleNamespace(
            items=[
                self._item("E1", "memory_context", True),
                self._item("E2", "memory_context", True),
            ]
        )
        self.assertEqual(citation_support(result, working_set, turn_kind="both"), "grounded")
        self.assertEqual(citation_support(result, working_set, turn_kind="dated"), "grounded")

    def test_continuity_dialogue_anchor_only_is_grounded(self):
        result = SimpleNamespace(cited_ids=["E1"])
        working_set = SimpleNamespace(items=[self._item("E1", "dialogue_anchor", None)])
        self.assertEqual(
            citation_support(result, working_set, turn_kind="continuity"),
            "grounded",
        )

    def test_continuity_memory_only_is_ungrounded(self):
        result = SimpleNamespace(cited_ids=["E1"])
        working_set = SimpleNamespace(items=[self._item("E1", "memory_context", True)])
        self.assertEqual(
            citation_support(result, working_set, turn_kind="continuity"),
            "ungrounded",
        )

    def test_continuity_dialogue_plus_memory_is_ungrounded(self):
        result = SimpleNamespace(cited_ids=["E1", "E2"])
        working_set = SimpleNamespace(
            items=[
                self._item("E1", "dialogue_anchor", None),
                self._item("E2", "memory_context", True),
            ]
        )
        self.assertEqual(
            citation_support(result, working_set, turn_kind="continuity"),
            "ungrounded",
        )

    def test_continuity_invalid_label_is_ungrounded(self):
        result = SimpleNamespace(cited_ids=["E9"])
        working_set = SimpleNamespace(items=[self._item("E1", "dialogue_anchor", None)])
        self.assertEqual(
            citation_support(result, working_set, turn_kind="continuity"),
            "ungrounded",
        )

    def test_continuity_empty_is_ungrounded(self):
        result = SimpleNamespace(cited_ids=[])
        working_set = SimpleNamespace(items=[self._item("E1", "dialogue_anchor", None)])
        self.assertEqual(
            citation_support(result, working_set, turn_kind="continuity"),
            "ungrounded",
        )

    def test_both_memory_plus_dialogue_is_mixed(self):
        result = SimpleNamespace(cited_ids=["E1", "E7"])
        working_set = SimpleNamespace(
            items=[
                self._item("E1", "memory_context", True),
                self._item("E7", "dialogue_anchor", None),
            ]
        )
        self.assertEqual(citation_support(result, working_set, turn_kind="both"), "mixed")

    def test_dated_memory_plus_dialogue_is_ungrounded(self):
        result = SimpleNamespace(cited_ids=["E1", "E7"])
        working_set = SimpleNamespace(
            items=[
                self._item("E1", "memory_context", True),
                self._item("E7", "dialogue_anchor", None),
            ]
        )
        self.assertEqual(citation_support(result, working_set, turn_kind="dated"), "ungrounded")

    def test_both_dialogue_only_is_ungrounded(self):
        result = SimpleNamespace(cited_ids=["E7"])
        working_set = SimpleNamespace(
            items=[
                self._item("E1", "memory_context", True),
                self._item("E7", "dialogue_anchor", None),
            ]
        )
        self.assertEqual(citation_support(result, working_set, turn_kind="both"), "ungrounded")

    def test_both_unconfirmed_memory_is_ungrounded(self):
        result = SimpleNamespace(cited_ids=["E1"])
        working_set = SimpleNamespace(items=[self._item("E1", "memory_context", False)])
        self.assertEqual(citation_support(result, working_set, turn_kind="both"), "ungrounded")

    def test_both_disallowed_source_is_ungrounded(self):
        result = SimpleNamespace(cited_ids=["E1", "E5"])
        working_set = SimpleNamespace(
            items=[
                self._item("E1", "memory_context", True),
                self._item("E5", "memory_evidence", True),
            ]
        )
        self.assertEqual(citation_support(result, working_set, turn_kind="both"), "ungrounded")

    def test_both_unmatched_label_is_ungrounded(self):
        result = SimpleNamespace(cited_ids=["E1", "E9"])
        working_set = SimpleNamespace(items=[self._item("E1", "memory_context", True)])
        self.assertEqual(citation_support(result, working_set, turn_kind="both"), "ungrounded")

    def test_turn_kind_omitted_never_mixed(self):
        result = SimpleNamespace(cited_ids=["E1", "E7"])
        working_set = SimpleNamespace(
            items=[
                self._item("E1", "memory_context", True),
                self._item("E7", "dialogue_anchor", None),
            ]
        )
        self.assertEqual(citation_support(result, working_set), "ungrounded")


class DatedAbsenceMatcherTest(unittest.TestCase):
    def test_honest_absence_phrasings_match(self):
        from daemon.maez_daemon import _reply_asserts_dated_absence

        for reply in [
            "I don't have any records for January 3.",
            "I don’t have any record of that.",
            "I have no records for that window.",
            "I have no record of that conversation.",
            "I do not have any records from then.",
            "I don't have a dated memory for that window.",
            "no record",
        ]:
            with self.subTest(reply=reply):
                self.assertTrue(_reply_asserts_dated_absence(reply))

    def test_honest_absence_with_refusal_tail_still_matches(self):
        from daemon.maez_daemon import _reply_asserts_dated_absence

        self.assertTrue(
            _reply_asserts_dated_absence(
                "I don't have a dated memory for that, and I won't guess."
            )
        )

    def test_non_absence_and_but_contrast_do_not_match(self):
        from daemon.maez_daemon import _reply_asserts_dated_absence

        for reply in [
            "Sure, I can help you with that.",
            "On January 3 you fixed the parser bug.",
            "Do you have any record of that meeting?",
            "I recorded the meeting notes in your file.",
            "I don't have any records for January 3, but you fixed the parser bug.",
            "No records were changed on January 3.",
        ]:
            with self.subTest(reply=reply):
                self.assertFalse(_reply_asserts_dated_absence(reply))


class FalseAbsenceTest(unittest.TestCase):
    def _rec(self, **kw):
        base = dict(
            mode="recall_triad",
            turn_kind="dated",
            outcome_class=OutcomeClass.DECLINED_ABSENCE,
            denial_kind="no_dated_memory",
            had_confirmed=False,
            citation_coverage=None,
            receipt_or_na="consulted",
            latency_ms=10,
            focused_elapsed_ms=5,
            reply_path=ReplyPath.FOCUSED,
        )
        base.update(kw)
        return RecallOutcome(**base)

    def test_legal_absence_is_not_false(self):
        self.assertFalse(is_false_absence(self._rec()))

    def test_absence_with_confirmed_item_is_false(self):
        rec = self._rec(had_confirmed=True)
        self.assertTrue(is_false_absence(rec))

    def test_absence_without_consulted_receipt_is_false(self):
        rec = self._rec(receipt_or_na="not_consulted")
        self.assertTrue(is_false_absence(rec))

    def test_legacy_absence_without_consultation_is_false_only_when_recall_relevant(self):
        rec = self._rec(
            mode="legacy",
            outcome_class=OutcomeClass.DECLINED_UNVERIFIED,
            denial_kind="na",
            had_confirmed=None,
            receipt_or_na="na",
        )
        self.assertTrue(is_false_absence(rec))
        ordinary = self._rec(turn_kind="ordinary", outcome_class=OutcomeClass.DECLINED_UNVERIFIED)
        self.assertFalse(is_false_absence(ordinary))

    def test_reachability_and_transport_are_not_false(self):
        for dk, oc in (
            ("carrier_unavailable", OutcomeClass.DECLINED_UNAVAILABLE),
            ("carrier_failed", OutcomeClass.DECLINED_FAILED),
            ("transport_failure", OutcomeClass.DECLINED_TRANSPORT),
        ):
            rec = self._rec(denial_kind=dk, outcome_class=oc, had_confirmed=True)
            self.assertFalse(is_false_absence(rec), dk)

    def test_grounded_answer_with_absence_phrase_is_not_false_absence(self):
        rec = self._rec(
            outcome_class=OutcomeClass.ANSWERED_GROUNDED,
            denial_kind="na",
            had_confirmed=True,
            receipt_or_na="consulted",
        )
        self.assertFalse(is_false_absence(rec))


class ReplyPathTest(unittest.TestCase):
    def test_reply_path_is_closed_set(self):
        self.assertEqual(
            {path.value for path in ReplyPath},
            {
                "tool",
                "echo",
                "honest_empty",
                "focused",
                "legacy",
                "dated_honesty",
                "self_status",
            },
        )

    def test_recall_outcome_normalizes_reply_path(self):
        rec = RecallOutcome(
            mode="recall_triad",
            turn_kind="dated",
            outcome_class=OutcomeClass.ANSWERED_GROUNDED,
            denial_kind="na",
            had_confirmed=True,
            citation_coverage=1.0,
            receipt_or_na="consulted",
            latency_ms=10,
            focused_elapsed_ms=5,
            reply_path="focused",
        )
        self.assertIs(rec.reply_path, ReplyPath.FOCUSED)

    def test_recall_outcome_rejects_unknown_reply_path(self):
        with self.assertRaises(ValueError):
            RecallOutcome(
                mode="recall_triad",
                turn_kind="dated",
                outcome_class=OutcomeClass.ANSWERED_GROUNDED,
                denial_kind="na",
                had_confirmed=True,
                citation_coverage=1.0,
                receipt_or_na="consulted",
                latency_ms=10,
                focused_elapsed_ms=5,
                reply_path="bogus",
            )


class AckStatusBoundaryTest(unittest.TestCase):
    def _rec(self, **kw):
        base = dict(
            mode="recall_triad",
            turn_kind="dated",
            outcome_class=OutcomeClass.ANSWERED_GROUNDED,
            denial_kind="na",
            had_confirmed=True,
            citation_coverage=1.0,
            receipt_or_na="consulted",
            latency_ms=10,
            focused_elapsed_ms=5,
            reply_path=ReplyPath.FOCUSED,
        )
        base.update(kw)
        return RecallOutcome(**base)

    def test_recall_outcome_normalizes_ack_status_enum(self):
        rec = self._rec(ack_status=AckStatus.EMITTED)
        self.assertEqual(rec.ack_status, AckStatus.EMITTED.value)

    def test_recall_outcome_rejects_unknown_ack_status(self):
        with self.assertRaises(ValueError):
            self._rec(ack_status="bogus")


class GroundedContextHelperTest(unittest.TestCase):
    def _item(self, label, source_type, confirmed):
        return SimpleNamespace(
            local_label=label,
            source_type=source_type,
            temporal_provenance={"confirmed": confirmed} if confirmed is not None else None,
        )

    def test_confirmed_memory_context_citation_is_grounded(self):
        result = SimpleNamespace(cited_ids=["E1"])
        ws = SimpleNamespace(items=[self._item("E1", "memory_context", True)])
        self.assertTrue(cites_confirmed_memory_context(result, ws))

    def test_memory_evidence_citation_does_not_count_for_dated_context_grounding(self):
        result = SimpleNamespace(cited_ids=["E1"])
        ws = SimpleNamespace(items=[self._item("E1", "memory_evidence", True)])
        self.assertFalse(cites_confirmed_memory_context(result, ws))

    def test_mixed_citations_do_not_count_as_dated_context_grounding(self):
        result = SimpleNamespace(cited_ids=["E1", "E2"])
        ws = SimpleNamespace(
            items=[
                self._item("E1", "memory_context", True),
                self._item("E2", "memory_evidence", True),
            ]
        )
        self.assertFalse(cites_confirmed_memory_context(result, ws))

    def test_unknown_citation_does_not_count_as_dated_context_grounding(self):
        result = SimpleNamespace(cited_ids=["E1", "E-missing"])
        ws = SimpleNamespace(items=[self._item("E1", "memory_context", True)])
        self.assertFalse(cites_confirmed_memory_context(result, ws))

    def test_unconfirmed_memory_context_does_not_count(self):
        result = SimpleNamespace(cited_ids=["E1"])
        ws = SimpleNamespace(items=[self._item("E1", "memory_context", False)])
        self.assertFalse(cites_confirmed_memory_context(result, ws))

    def test_temporal_status_citation_does_not_count(self):
        result = SimpleNamespace(cited_ids=["E1"])
        ws = SimpleNamespace(items=[self._item("E1", "temporal_recall_status", None)])
        self.assertFalse(cites_confirmed_memory_context(result, ws))


class ContentFreeSchemaTest(unittest.TestCase):
    def test_schema_bumped_to_v2_with_ack_fields(self):
        self.assertEqual(RecallOutcome.schema_version, "recall_outcome.v2")
        names = {f.name for f in dataclasses.fields(RecallOutcome)}
        self.assertTrue(
            {
                "receipt_eligible",
                "receipt_after_ms",
                "ack_required",
                "ack_status",
                "ack_emit_ms",
            }
            <= names
        )

    def test_ack_fields_are_content_free(self):
        names = {f.name for f in dataclasses.fields(RecallOutcome)}
        forbidden = {
            "query_text",
            "text",
            "raw_text",
            "reply",
            "recalled_snippet",
            "content",
            "receipt_text",
            "owner_question",
            "snippet",
        }
        self.assertEqual(names & forbidden, set())

    def test_no_content_fields(self):
        names = {f.name for f in dataclasses.fields(RecallOutcome)}
        forbidden = {
            "query_text",
            "text",
            "raw_text",
            "reply",
            "recalled_snippet",
            "content",
            "owner_question",
            "snippet",
        }
        self.assertEqual(
            names & forbidden,
            set(),
            "RecallOutcome must stay content-free (whether-I-remembered, never what)",
        )

    def test_schema_version_and_stable_na_serialization(self):
        self.assertEqual(RecallOutcome.schema_version, "recall_outcome.v2")
        self.assertEqual(format_log_value(None), "na")
        self.assertEqual(format_log_value(True), "true")
        self.assertEqual(format_log_value(False), "false")


class ReplyPathFromModeTest(unittest.TestCase):
    def test_known_modes_map(self):
        self.assertIs(reply_path_from_mode("focused"), ReplyPath.FOCUSED)
        self.assertIs(reply_path_from_mode("legacy"), ReplyPath.LEGACY)
        self.assertIs(reply_path_from_mode("tool"), ReplyPath.TOOL)

    def test_unknown_mode_falls_back_to_legacy_no_raise(self):
        for unknown in ("clinical", "camera", "backend_error", "nonsense"):
            self.assertIs(reply_path_from_mode(unknown), ReplyPath.LEGACY, unknown)


if __name__ == "__main__":
    unittest.main()
