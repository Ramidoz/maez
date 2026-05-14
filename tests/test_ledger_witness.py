# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""TDD tests for core.ledger.chain witness verification.

These tests lock in the witness-binding contract from
docs/ledger/envelope-schema.md §6.1:

  - claims.parent_turn_chain_hash MUST equal the parent turn's
    chain_hash at insert time.
  - claim_judgements.parent_claim_witness MUST equal the parent
    claim's parent_turn_chain_hash at insert time.

Tampering with a parent row therefore breaks every dependent's
witness, even though claims and claim_judgements are NOT themselves
links in the primary chain. The witness verifier surfaces those
mismatches; this file is the contract.

The chain-hash recipe itself is exercised by
``tests/test_ledger_chain.py`` (chain primitives slice). This file
deliberately re-implements ``_compute_canonical_chain_hash`` from
hashlib + json directly — calling chain.compute_chain_hash here
would make the tests circular.

This file imports core.ledger.chain at module load. Until the
implementation slice lands, every test fails with
ModuleNotFoundError, which is the intended TDD red.
"""
from __future__ import annotations

import hashlib
import json
import unittest
import uuid

from core.ledger import chain  # noqa: F401


_WRONG_HEX_A = "0" * 63 + "1"
_WRONG_HEX_B = "f" * 63 + "e"
_WRONG_HEX_C = "1234567890abcdef" * 4


def _build_synthetic_turn(turn_id: str, prev_chain_hash: str | None) -> dict:
    """Produce a turn dict shaped per docs/ledger/envelope-schema.md §4.2."""
    row = {
        "turn_id": turn_id,
        "tenant_id": "owner",
        "timestamp": 1_700_000_000.0,
        "schema_version": 1,
        "turn_kind": "model_reply",
        "surface": "cockpit",
        "raw_surface": "cockpit",
        "parent_turn_id": None,
        "correction_of": None,
        "model_id": "qwen36-27b",
        "lora_hash": None,
        "soul_hash": "soul-" + turn_id,
        "prompt_hash": "prompt-" + turn_id,
        "raw_text": f"synthetic raw text for {turn_id}",
        "rewritten_text": None,
        "was_rewritten": 0,
        "signals_present": "[]",
        "signals_absent": "[]",
        "evidence_envelope_json": "{}",
        "action_proposal_json": None,
        "audit_verdict_json": "{}",
        "will_i_json": None,
        "memory_read_ids": "[]",
        "memory_written_ids": "[]",
        "audit_log_id": None,
        "fabrication_event_id": None,
        "self_mod_dialog_id": None,
        "pending_card_id": None,
    }
    row["prev_chain_hash"] = prev_chain_hash
    row["chain_hash"] = _compute_canonical_chain_hash(row, prev_chain_hash)
    return row


def _build_synthetic_claim(
    claim_id: int,
    turn_id: str,
    parent_turn_chain_hash: str,
) -> dict:
    return {
        "claim_id": claim_id,
        "turn_id": turn_id,
        "tenant_id": "owner",
        "fact": f"synthetic claim {claim_id} for {turn_id}",
        "extracted_at": 1_700_000_001.0,
        "extractor_version": "test-v0",
        "parent_turn_chain_hash": parent_turn_chain_hash,
    }


def _build_synthetic_judgement(
    judgement_id: int,
    claim_id: int,
    parent_claim_witness: str,
) -> dict:
    return {
        "judgement_id": judgement_id,
        "claim_id": claim_id,
        "tenant_id": "owner",
        "judged_at": 1_700_000_002.0,
        "judged_by": "pass_b_judge",
        "judge_model_id": "qwen35-4b",
        "provenance": "owner-said",
        "evidence_refs_json": "{}",
        "confidence": 0.9,
        "audit_verdict": "grounded",
        "parent_claim_witness": parent_claim_witness,
    }


def _compute_canonical_chain_hash(
    row: dict,
    prev_chain_hash: str | None,
) -> str:
    """Independent reimplementation of the §6.1 recipe."""
    body = {k: v for k, v in row.items() if k not in ("chain_hash", "prev_chain_hash")}
    canonical = json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    prefix = "genesis" if prev_chain_hash is None else prev_chain_hash
    return hashlib.sha256((prefix + canonical).encode("utf-8")).hexdigest()


def _new_turn_id() -> str:
    return str(uuid.uuid4())


def _violation_msg(label: str, violation: dict) -> str:
    return (
        f"{label}: violation dict missing expected fields or wrong shape. "
        f"got={violation!r}"
    )


class ClaimWitnessTests(unittest.TestCase):

    def test_all_intact_returns_empty_list(self):
        turn = _build_synthetic_turn(_new_turn_id(), prev_chain_hash=None)
        claims = [
            _build_synthetic_claim(1, turn["turn_id"], turn["chain_hash"]),
            _build_synthetic_claim(2, turn["turn_id"], turn["chain_hash"]),
        ]
        violations = chain.verify_claim_witnesses(
            {turn["turn_id"]: turn}, claims
        )
        self.assertEqual(
            violations,
            [],
            f"claims table: expected zero witness violations when every "
            f"claim.parent_turn_chain_hash equals turns.chain_hash; "
            f"got {violations!r}",
        )

    def test_empty_claims_list_returns_empty(self):
        turn = _build_synthetic_turn(_new_turn_id(), prev_chain_hash=None)
        violations = chain.verify_claim_witnesses({turn["turn_id"]: turn}, [])
        self.assertEqual(
            violations, [],
            f"claims table: empty claims list must produce no violations; got {violations!r}",
        )

    def test_tampered_claim_witness_is_flagged(self):
        turn = _build_synthetic_turn(_new_turn_id(), prev_chain_hash=None)
        good_claim = _build_synthetic_claim(1, turn["turn_id"], turn["chain_hash"])
        bad_claim = _build_synthetic_claim(2, turn["turn_id"], _WRONG_HEX_A)
        violations = chain.verify_claim_witnesses(
            {turn["turn_id"]: turn}, [good_claim, bad_claim]
        )
        self.assertEqual(
            len(violations), 1,
            f"claims table: expected exactly 1 witness violation for the tampered claim_id=2; "
            f"got {len(violations)} violations: {violations!r}",
        )
        v = violations[0]
        self.assertEqual(v.get("claim_id"), 2,
            _violation_msg("claims.parent_turn_chain_hash mismatch", v))
        self.assertEqual(v.get("turn_id"), turn["turn_id"],
            _violation_msg("claims.turn_id in violation", v))
        self.assertEqual(v.get("expected"), turn["chain_hash"],
            f"claims table: violation 'expected' must be the parent turn's chain_hash; "
            f"got {v.get('expected')!r}")
        self.assertEqual(v.get("actual"), _WRONG_HEX_A,
            f"claims table: violation 'actual' must be the tampered parent_turn_chain_hash; "
            f"got {v.get('actual')!r}")
        reason = (v.get("reason") or "").lower()
        self.assertTrue(
            "mismatch" in reason or "witness" in reason,
            f"claims table: violation reason must mention 'mismatch' or 'witness'; "
            f"got reason={v.get('reason')!r}",
        )

    def test_orphan_claim_no_parent_turn_is_flagged(self):
        turn = _build_synthetic_turn(_new_turn_id(), prev_chain_hash=None)
        orphan = _build_synthetic_claim(99, "no-such-turn-id", turn["chain_hash"])
        violations = chain.verify_claim_witnesses(
            {turn["turn_id"]: turn}, [orphan]
        )
        self.assertEqual(
            len(violations), 1,
            f"claims table: expected exactly 1 violation for an orphan claim; got {violations!r}",
        )
        v = violations[0]
        self.assertEqual(v.get("claim_id"), 99,
            _violation_msg("claims orphan violation", v))
        reason = (v.get("reason") or "").lower()
        self.assertIn("orphan", reason,
            f"claims table: orphan violation reason must contain 'orphan'; got reason={v.get('reason')!r}")

    def test_multiple_tampered_claims_flagged(self):
        turn_a = _build_synthetic_turn(_new_turn_id(), prev_chain_hash=None)
        turn_b = _build_synthetic_turn(_new_turn_id(), prev_chain_hash=turn_a["chain_hash"])
        turns_by_id = {turn_a["turn_id"]: turn_a, turn_b["turn_id"]: turn_b}
        claims = [
            _build_synthetic_claim(1, turn_a["turn_id"], turn_a["chain_hash"]),
            _build_synthetic_claim(2, turn_a["turn_id"], _WRONG_HEX_A),
            _build_synthetic_claim(3, turn_b["turn_id"], turn_b["chain_hash"]),
            _build_synthetic_claim(4, turn_b["turn_id"], _WRONG_HEX_B),
        ]
        violations = chain.verify_claim_witnesses(turns_by_id, claims)
        self.assertEqual(
            len(violations), 2,
            f"claims table: expected exactly 2 witness violations; got {len(violations)}: {violations!r}",
        )
        flagged_ids = sorted(v.get("claim_id") for v in violations)
        self.assertEqual(flagged_ids, [2, 4],
            f"claims table: expected violations for claim_ids [2, 4]; got {flagged_ids!r}")


class JudgementWitnessTests(unittest.TestCase):

    def test_all_intact_returns_empty_list(self):
        turn = _build_synthetic_turn(_new_turn_id(), prev_chain_hash=None)
        claim = _build_synthetic_claim(1, turn["turn_id"], turn["chain_hash"])
        judgements = [
            _build_synthetic_judgement(10, claim["claim_id"], claim["parent_turn_chain_hash"]),
            _build_synthetic_judgement(11, claim["claim_id"], claim["parent_turn_chain_hash"]),
        ]
        violations = chain.verify_judgement_witnesses(
            {claim["claim_id"]: claim}, judgements
        )
        self.assertEqual(violations, [],
            f"claim_judgements table: expected zero violations when every parent_claim_witness matches; got {violations!r}")

    def test_empty_judgements_list_returns_empty(self):
        violations = chain.verify_judgement_witnesses({}, [])
        self.assertEqual(violations, [],
            f"claim_judgements table: empty judgements list must produce no violations; got {violations!r}")

    def test_tampered_judgement_witness_is_flagged(self):
        turn = _build_synthetic_turn(_new_turn_id(), prev_chain_hash=None)
        claim = _build_synthetic_claim(1, turn["turn_id"], turn["chain_hash"])
        good = _build_synthetic_judgement(10, claim["claim_id"], claim["parent_turn_chain_hash"])
        bad = _build_synthetic_judgement(11, claim["claim_id"], _WRONG_HEX_C)
        violations = chain.verify_judgement_witnesses(
            {claim["claim_id"]: claim}, [good, bad]
        )
        self.assertEqual(len(violations), 1,
            f"claim_judgements table: expected exactly 1 violation; got {len(violations)}: {violations!r}")
        v = violations[0]
        self.assertEqual(v.get("judgement_id"), 11,
            _violation_msg("claim_judgements.parent_claim_witness mismatch", v))
        self.assertEqual(v.get("claim_id"), claim["claim_id"],
            _violation_msg("claim_judgements.claim_id in violation", v))
        self.assertEqual(v.get("expected"), claim["parent_turn_chain_hash"],
            f"claim_judgements: violation 'expected' must be parent claim's parent_turn_chain_hash; got {v.get('expected')!r}")
        self.assertEqual(v.get("actual"), _WRONG_HEX_C,
            f"claim_judgements: violation 'actual' must be tampered parent_claim_witness; got {v.get('actual')!r}")
        reason = (v.get("reason") or "").lower()
        self.assertTrue("mismatch" in reason or "witness" in reason,
            f"claim_judgements: violation reason must mention 'mismatch' or 'witness'; got reason={v.get('reason')!r}")

    def test_orphan_judgement_no_parent_claim_is_flagged(self):
        turn = _build_synthetic_turn(_new_turn_id(), prev_chain_hash=None)
        claim = _build_synthetic_claim(1, turn["turn_id"], turn["chain_hash"])
        orphan = _build_synthetic_judgement(42, 9999, claim["parent_turn_chain_hash"])
        violations = chain.verify_judgement_witnesses(
            {claim["claim_id"]: claim}, [orphan]
        )
        self.assertEqual(len(violations), 1,
            f"claim_judgements: expected 1 orphan violation; got {violations!r}")
        v = violations[0]
        self.assertEqual(v.get("judgement_id"), 42,
            _violation_msg("claim_judgements orphan violation", v))
        reason = (v.get("reason") or "").lower()
        self.assertIn("orphan", reason,
            f"claim_judgements: orphan violation reason must contain 'orphan'; got reason={v.get('reason')!r}")


class CrossTableTamperingTests(unittest.TestCase):
    """Verify that tampering with a parent row propagates through every
    dependent's witness — the whole point of the binding."""

    def test_tampering_turn_chain_hash_breaks_chain_and_claim_witness(self):
        turn = _build_synthetic_turn(_new_turn_id(), prev_chain_hash=None)
        claim = _build_synthetic_claim(1, turn["turn_id"], turn["chain_hash"])
        judgement = _build_synthetic_judgement(10, claim["claim_id"], claim["parent_turn_chain_hash"])

        # Sanity
        self.assertEqual(
            chain.verify_claim_witnesses({turn["turn_id"]: turn}, [claim]),
            [],
            "clean state: claim witnesses must be intact before tampering",
        )
        self.assertEqual(
            chain.verify_judgement_witnesses({claim["claim_id"]: claim}, [judgement]),
            [],
            "clean state: judgement witnesses must be intact before tampering",
        )

        original_chain_hash = turn["chain_hash"]
        turn["chain_hash"] = _WRONG_HEX_A
        self.assertNotEqual(turn["chain_hash"], original_chain_hash,
            "tampering harness: chain_hash must actually have changed")

        chain_violations = chain.verify_chain([turn])
        self.assertTrue(len(chain_violations) >= 1,
            f"verify_chain must flag the tampered turn; got {chain_violations!r}")

        claim_violations = chain.verify_claim_witnesses(
            {turn["turn_id"]: turn}, [claim]
        )
        self.assertEqual(len(claim_violations), 1,
            f"witness propagation: tampering with turn.chain_hash must flag the dependent claim; got {claim_violations!r}")
        v = claim_violations[0]
        self.assertEqual(v.get("claim_id"), claim["claim_id"],
            _violation_msg("propagation flagged wrong claim", v))
        self.assertEqual(v.get("expected"), turn["chain_hash"],
            "propagation: violation 'expected' must be the turn's CURRENT (tampered) chain_hash")
        self.assertEqual(v.get("actual"), claim["parent_turn_chain_hash"],
            "propagation: violation 'actual' must be the claim's parent_turn_chain_hash as recorded")

    def test_3_turn_chain_tampering_isolates_to_attached_claims(self):
        turn1 = _build_synthetic_turn(_new_turn_id(), prev_chain_hash=None)
        turn2 = _build_synthetic_turn(_new_turn_id(), prev_chain_hash=turn1["chain_hash"])
        turn3 = _build_synthetic_turn(_new_turn_id(), prev_chain_hash=turn2["chain_hash"])
        turns = [turn1, turn2, turn3]
        turns_by_id = {t["turn_id"]: t for t in turns}

        claims: list[dict] = []
        next_claim_id = 1
        for t in turns:
            for _ in range(2):
                claims.append(_build_synthetic_claim(next_claim_id, t["turn_id"], t["chain_hash"]))
                next_claim_id += 1
        claims_by_id = {c["claim_id"]: c for c in claims}

        judgements = []
        next_j_id = 100
        for c in claims:
            judgements.append(_build_synthetic_judgement(next_j_id, c["claim_id"], c["parent_turn_chain_hash"]))
            next_j_id += 1

        # Sanity
        self.assertEqual(chain.verify_chain(turns), [],
            "clean 3-turn chain must verify before tampering")
        self.assertEqual(chain.verify_claim_witnesses(turns_by_id, claims), [],
            "clean 3-turn chain: all 6 claim witnesses must be intact")
        self.assertEqual(chain.verify_judgement_witnesses(claims_by_id, judgements), [],
            "clean 3-turn chain: all 6 judgement witnesses must be intact")

        original = turn1["chain_hash"]
        turn1["chain_hash"] = _WRONG_HEX_B
        self.assertNotEqual(turn1["chain_hash"], original,
            "tampering harness: turn1.chain_hash must actually have changed")

        chain_violations = chain.verify_chain(turns)
        self.assertGreaterEqual(len(chain_violations), 1,
            f"verify_chain must flag at least the tampered turn1; got {chain_violations!r}")

        claim_violations = chain.verify_claim_witnesses(turns_by_id, claims)
        self.assertEqual(len(claim_violations), 2,
            f"witness propagation: exactly 2 claims attached to turn1 must be flagged; got {claim_violations!r}")
        flagged_turn_ids = {v.get("turn_id") for v in claim_violations}
        self.assertEqual(flagged_turn_ids, {turn1["turn_id"]},
            f"witness propagation: every flagged claim must be attached to turn1; got {flagged_turn_ids!r}")
        flagged_claim_ids = sorted(v.get("claim_id") for v in claim_violations)
        expected_claim_ids = sorted(c["claim_id"] for c in claims if c["turn_id"] == turn1["turn_id"])
        self.assertEqual(flagged_claim_ids, expected_claim_ids,
            f"witness propagation: flagged claim_ids must equal claims attached to turn1; expected {expected_claim_ids!r}, got {flagged_claim_ids!r}")

        # Judgement witnesses bind to claims, not turns; should still be clean.
        self.assertEqual(chain.verify_judgement_witnesses(claims_by_id, judgements), [],
            "judgement witnesses bind to claims, not turns: tampering with the turn must not flag judgements unless the claim was also rewritten")


if __name__ == "__main__":
    unittest.main()
