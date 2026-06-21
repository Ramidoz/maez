import unittest
from dataclasses import dataclass as _dc

from core.routing.memory_fresh_conflict import (
    MemoryFreshConflictReceipt,
    memory_fresh_conflict_sense_enabled,
    trusted_memory_items,
    fresh_items,
    extract_memory_claims,
)


@_dc
class _Item:
    local_label: str
    source_type: str
    text: str
    origin_trust: str | None = None
    origin_provenance: str | None = None


@_dc
class _WS:
    items: tuple


class TestReceiptAndFlag(unittest.TestCase):
    def test_receipt_has_only_content_light_fields(self):
        r = MemoryFreshConflictReceipt(
            verdict="contradiction", mem_id="E2", mem_label="memory_evidence",
            fresh_id="E1", fresh_label="web_context", confidence=0.91,
            verifier="LocalNLIContradictionVerifier@rev1", mem_sha256="a" * 64,
            fresh_sha256="b" * 64, reason_code="trusted_clash",
        )
        forbidden = {"text", "mem_text", "fresh_text", "claim_text", "sense_note", "claim_details"}
        self.assertEqual(forbidden & set(vars(r)), set())
        self.assertEqual(r.verdict, "contradiction")

    def test_flag_off_by_default(self):
        self.assertFalse(memory_fresh_conflict_sense_enabled(env={}))

    def test_flag_on_when_set(self):
        self.assertTrue(
            memory_fresh_conflict_sense_enabled(env={"MAEZ_MEM_FRESH_CONFLICT_SENSE": "1"})
        )


class TestSelectors(unittest.TestCase):
    def _ws(self, *items):
        return _WS(items=tuple(items))

    def test_trusted_memory_requires_lived_or_covenant(self):
        lived = _Item("E1", "memory_evidence", "x", origin_trust="lived")
        cov = _Item("E2", "memory_context", "y", origin_trust="covenant")
        ws = self._ws(lived, cov)
        self.assertEqual([i.local_label for i in trusted_memory_items(ws)], ["E1", "E2"])

    def test_none_trust_excluded_fail_closed(self):
        untrusted = _Item("E1", "memory_evidence", "x", origin_trust=None)
        unknown = _Item("E2", "memory_evidence", "y", origin_trust="hearsay")
        self.assertEqual(list(trusted_memory_items(self._ws(untrusted, unknown))), [])

    def test_self_web_claim_excluded_even_if_trusted(self):
        sweb = _Item("E1", "memory_evidence", "x", origin_trust="lived",
                     origin_provenance="self_web_claim")
        self.assertEqual(list(trusted_memory_items(self._ws(sweb))), [])

    def test_fresh_items_are_fresh_source_types(self):
        web = _Item("E1", "web_context", "w")
        obs = _Item("E2", "fresh_evidence", "o")
        mem = _Item("E3", "memory_evidence", "m", origin_trust="lived")
        self.assertEqual([i.local_label for i in fresh_items(self._ws(web, obs, mem))],
                         ["E1", "E2"])

    def test_extract_memory_claims_splits_sentences_bounded(self):
        claims = extract_memory_claims("Rohit prefers tea. He dislikes loud rooms. Maez is calm.",
                                       limit=2)
        self.assertEqual(len(claims), 2)
        self.assertTrue(all(isinstance(c, str) and c for c in claims))


from core.routing.memory_fresh_conflict import check_memory_fresh_conflict


class _Verdict:
    def __init__(self, label, score=0.9, reason=None):
        self.label = label
        self.score = score
        self.latency_s = 0.0
        self.model_id = "nli-test"
        self.revision = "rev1"
        self.sha256 = "c" * 64
        self.reason = reason


class _FakeVerifier:
    def __init__(self, label, score=0.9):
        self._label = label
        self._score = score
        self.calls = 0

    def predict(self, premise, hypothesis):
        self.calls += 1
        return _Verdict(self._label, score=self._score)


class TestOrchestration(unittest.TestCase):
    def _ws_with(self, mem_trust="lived"):
        mem = _Item("E2", "memory_evidence", "Maez's latest model is Claude 3.",
                    origin_trust=mem_trust)
        fresh = _Item("E1", "web_context", "Anthropic released Claude Opus 4.8 in 2026.")
        return _WS(items=(fresh, mem))

    def test_contradiction_emits_redacted_receipt(self):
        r = check_memory_fresh_conflict(self._ws_with(), _FakeVerifier("contradicts"))
        self.assertEqual(r.verdict, "contradiction")
        self.assertEqual(r.mem_id, "E2")
        self.assertEqual(r.fresh_id, "E1")
        self.assertEqual(len(r.mem_sha256), 64)
        self.assertNotIn("Claude", str(vars(r)))

    def test_grounded_is_none_verdict(self):
        r = check_memory_fresh_conflict(self._ws_with(), _FakeVerifier("grounded"))
        self.assertEqual(r.verdict, "none")

    def test_unavailable_is_ambiguous_never_accuse(self):
        r = check_memory_fresh_conflict(self._ws_with(), _FakeVerifier("unavailable"))
        self.assertEqual(r.verdict, "ambiguous")

    def test_no_trusted_memory_returns_none_receipt(self):
        ws = self._ws_with(mem_trust=None)
        self.assertIsNone(check_memory_fresh_conflict(ws, _FakeVerifier("contradicts")))

    def test_pair_budget_caps_predict_calls(self):
        mem = _Item("E2", "memory_evidence",
                    "A. B. C. D. E. F. G. H.", origin_trust="lived")
        fresh1 = _Item("E1", "web_context", "fresh one")
        fresh2 = _Item("E3", "web_context", "fresh two")
        ws = _WS(items=(fresh1, fresh2, mem))
        v = _FakeVerifier("grounded")
        r = check_memory_fresh_conflict(ws, v, claim_limit=5, pair_budget=3)
        self.assertLessEqual(v.calls, 3)
        self.assertTrue(r.pair_limit_exceeded)

    def test_pair_count_is_pairs_examined_not_budget(self):
        # first (and only) pair contradicts -> pair_count must be 1, not pair_budget
        r = check_memory_fresh_conflict(self._ws_with(), _FakeVerifier("contradicts"),
                                        pair_budget=6)
        self.assertEqual(r.pair_count, 1)

    def test_neutral_verdict_is_ambiguous_non_decisive(self):
        r = check_memory_fresh_conflict(self._ws_with(), _FakeVerifier("neutral"))
        self.assertEqual(r.verdict, "ambiguous")
        self.assertEqual(r.reason_code, "non_decisive")

    def test_contradiction_confidence_is_clash_strength(self):
        # grounded score 0.05 -> strong contradiction -> confidence 0.95 (NOT 0.05)
        r = check_memory_fresh_conflict(self._ws_with(), _FakeVerifier("contradicts", score=0.05))
        self.assertEqual(r.verdict, "contradiction")
        self.assertAlmostEqual(r.confidence, 0.95, places=4)


class TestRedaction(unittest.TestCase):
    def test_no_memory_or_fresh_text_anywhere_in_receipt(self):
        SECRET_MEM = "ZZSECRETMEMZZ is the remembered fact."
        SECRET_FRESH = "ZZSECRETFRESHZZ is the fresh source."
        mem = _Item("E2", "memory_evidence", SECRET_MEM, origin_trust="lived")
        fresh = _Item("E1", "web_context", SECRET_FRESH)
        ws = _WS(items=(fresh, mem))
        r = check_memory_fresh_conflict(ws, _FakeVerifier("contradicts"))
        blob = repr(vars(r))
        self.assertNotIn("ZZSECRETMEM", blob)
        self.assertNotIn("ZZSECRETFRESH", blob)
        # digests ARE present (proof we saw the text but stored only its hash)
        self.assertEqual(len(r.mem_sha256), 64)


if __name__ == "__main__":
    unittest.main()
