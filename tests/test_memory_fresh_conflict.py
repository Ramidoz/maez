import os
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


if __name__ == "__main__":
    unittest.main()
