import tempfile
import unittest
from pathlib import Path

from core.routing.focused_cognition import (
    GroundednessVerdict,
    FocusedCognitionStore,
    check_groundedness,
    FocusedResult,
    WorkingSet,
    EvidenceItem,
)


def _ws(n):
    items = tuple(
        EvidenceItem(local_label=f"E{i+1}", source_type="memory_evidence",
                     text=f"item {i+1}", durable_id=f"d{i+1}")
        for i in range(n)
    )
    return WorkingSet(items=items, owner_question="q", ordered_evidence_text="",
                      working_set_chars=0, working_set_tokens_est=0)


def _result(reply, cited):
    return FocusedResult(reply=reply, cited_ids=list(cited), working_set_chars=0)


class TestGroundednessVerdictCompat(unittest.TestCase):
    def test_existing_positional_constructor_still_builds(self):
        v = GroundednessVerdict("grounded", 1.0, [])
        self.assertEqual(v.verdict, "grounded")
        self.assertEqual(v.reply_grounding, 0.0)
        self.assertEqual(v.grounded_sentences, 0)
        self.assertEqual(v.total_sentences, 0)


class TestReplyGrounding(unittest.TestCase):
    def test_denominator_is_reply_not_working_set(self):
        ws = _ws(16)
        r = _result("The sky is blue [E1]. It is sunny [E2].", {"E1", "E2"})
        v = check_groundedness(r, ws)
        self.assertEqual(v.total_sentences, 2)
        self.assertEqual(v.grounded_sentences, 2)
        self.assertEqual(v.reply_grounding, 1.0)
        self.assertEqual(v.citation_coverage, 2 / 16)

    def test_uncited_self_narrative_is_zero(self):
        ws = _ws(16)
        r = _result("I am the engine keeping the lights on. I hold the space.", set())
        v = check_groundedness(r, ws)
        self.assertEqual(v.grounded_sentences, 0)
        self.assertEqual(v.reply_grounding, 0.0)

    def test_invalid_citation_not_grounded(self):
        ws = _ws(2)
        r = _result("A real fact [E1]. A hallucinated one [E99].", {"E1", "E99"})
        v = check_groundedness(r, ws)
        self.assertEqual(v.grounded_sentences, 1)
        self.assertEqual(v.total_sentences, 2)
        self.assertEqual(v.reply_grounding, 0.5)
        self.assertIn("E99", v.unmatched)

    def test_deterministic(self):
        ws = _ws(3)
        r = _result("Fact one [E1]. Fact two [E2].", {"E1", "E2"})
        self.assertEqual(check_groundedness(r, ws).reply_grounding,
                         check_groundedness(r, ws).reply_grounding)

    def test_no_punctuation_single_clause(self):
        ws = _ws(3)
        r = _result("just one grounded clause [E1]", {"E1"})
        v = check_groundedness(r, ws)
        self.assertEqual(v.total_sentences, 1)
        self.assertEqual(v.grounded_sentences, 1)
        self.assertEqual(v.reply_grounding, 1.0)


class TestStoreColumns(unittest.TestCase):
    def _store(self):
        d = tempfile.mkdtemp()
        return FocusedCognitionStore(db_path=Path(d) / "fc.db")

    def test_record_persists_grounding_numbers(self):
        store = self._store()
        ws = _ws(3)
        r = _result("Fact [E1]. Filler.", {"E1"})
        v = check_groundedness(r, ws)
        rid = store.record(surface="telegram_surface", chat_id=None, working_set=ws,
                           result=r, verdict=v, legacy_prompt_chars=None,
                           fallback_reason=None, routing_observation_id=None)
        row = store.get(rid)
        self.assertAlmostEqual(row["reply_grounding"], 0.5)
        self.assertEqual(row["grounded_sentences"], 1)
        self.assertEqual(row["total_sentences"], 2)
        # content-light: the reply text must NOT appear in any column
        self.assertNotIn("Fact", " ".join(str(row[k]) for k in row.keys()))

    def test_migration_idempotent(self):
        d = tempfile.mkdtemp()
        p = Path(d) / "fc.db"
        FocusedCognitionStore(db_path=p)   # creates + migrates
        FocusedCognitionStore(db_path=p)   # re-open: migration must NOT error
        self.assertTrue(p.exists())

    def test_verdict_none_writes_null_grounding(self):
        store = self._store()
        ws = _ws(2)
        r = _result("anything", set())
        rid = store.record(surface="telegram_surface", chat_id=None, working_set=ws,
                           result=r, verdict=None, legacy_prompt_chars=None,
                           fallback_reason=None, routing_observation_id=None)
        row = store.get(rid)
        self.assertIsNone(row["reply_grounding"])
        self.assertIsNone(row["grounded_sentences"])
        self.assertIsNone(row["total_sentences"])


if __name__ == "__main__":
    unittest.main()
