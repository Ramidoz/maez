# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Tests for core.ledger.chain primitives.

Locks the canonical-row-bytes recipe and chain-walk semantics defined
in LEDGER_ENVELOPE_SCHEMA.md §6.1. These tests must remain consistent
with tests/test_ledger_genesis.py::GenesisRecipeTests — both pin the
same recipe (sort_keys=True, separators=(",",":"), ensure_ascii=True,
omit chain_hash and prev_chain_hash).

The module under test (core.ledger.chain) does not yet exist. The
hard import below fails with ModuleNotFoundError until the
implementation slice lands. That failure is the spec.
"""
from __future__ import annotations

import hashlib
import json
import unittest

# Intentional hard import. core.ledger.chain does not yet exist; this
# import will raise ModuleNotFoundError until the chain primitives
# slice lands. No try/except — the failure is the TDD signal.
from core.ledger import chain  # noqa: E402

# Cross-recipe consistency: the genesis recipe in migrate.py and the
# generic recipe in chain.py MUST converge on the same digest for the
# canonical genesis row.
from core.ledger.migrate import (  # noqa: E402
    GENESIS_ROW,
    _canonical_genesis_chain_hash,
)


_LOWER_HEX = set("0123456789abcdef")


def _is_lower_hex_64(s: object) -> bool:
    return (
        isinstance(s, str)
        and len(s) == 64
        and all(c in _LOWER_HEX for c in s)
    )


def _canonical_bytes_expected(row: dict) -> bytes:
    """Reference implementation of the §6.1 canonical recipe.

    Used in tests to construct *expected* bytes/digests. Must NEVER
    be replaced by chain.canonical_row_bytes — that would be circular.
    """
    stripped = {
        k: v for k, v in row.items()
        if k not in ("chain_hash", "prev_chain_hash")
    }
    return json.dumps(
        stripped,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def _expected_chain_hash(row: dict, prev_chain_hash: str | None) -> str:
    """Reference implementation of compute_chain_hash for tests.

    Genesis prefix rule: if prev_chain_hash is None, prefix = b"genesis".
    Otherwise prefix is the prior chain_hash hex string itself,
    utf-8 encoded.
    """
    canonical = _canonical_bytes_expected(row)
    if prev_chain_hash is None:
        prefix = b"genesis"
    else:
        prefix = prev_chain_hash.encode("utf-8")
    return hashlib.sha256(prefix + canonical).hexdigest()


def _build_synthetic_chain(n: int) -> list[dict]:
    """Build n linked turn rows starting from the canonical genesis."""
    if n <= 0:
        return []

    rows: list[dict] = []

    # Row 0: genesis (using the canonical GENESIS_ROW from migrate)
    genesis = dict(GENESIS_ROW)
    genesis["prev_chain_hash"] = None
    genesis["chain_hash"] = _expected_chain_hash(genesis, None)
    rows.append(genesis)

    # Rows 1..n-1: synthetic user_message turns
    for i in range(1, n):
        prev = rows[-1]
        row = {
            "turn_id": f"turn-{i:04d}",
            "tenant_id": "owner",
            "timestamp": float(1_700_000_000 + i),
            "schema_version": 1,
            "turn_kind": "user_message",
            "surface": "telegram",
            "raw_surface": "telegram_text",
            "parent_turn_id": None,
            "correction_of": None,
            "model_id": None,
            "lora_hash": None,
            "soul_hash": None,
            "prompt_hash": None,
            "raw_text": f"synthetic turn {i}",
            "rewritten_text": None,
            "was_rewritten": 0,
            "signals_present": "[]",
            "signals_absent": "[]",
            "evidence_envelope_json": None,
            "action_proposal_json": None,
            "audit_verdict_json": None,
            "will_i_json": None,
            "memory_read_ids": "[]",
            "memory_written_ids": "[]",
            "audit_log_id": None,
            "fabrication_event_id": None,
            "self_mod_dialog_id": None,
            "pending_card_id": None,
            "prev_chain_hash": prev["chain_hash"],
        }
        row["chain_hash"] = _expected_chain_hash(row, prev["chain_hash"])
        rows.append(row)

    return rows


class CanonicalBytesTests(unittest.TestCase):
    """Pin the §6.1 canonical_row_bytes recipe."""

    def test_returns_bytes_not_str(self):
        out = chain.canonical_row_bytes({"a": 1})
        self.assertIsInstance(
            out, bytes,
            "canonical_row_bytes must return bytes (utf-8 encoded), not str",
        )

    def test_keys_are_sorted(self):
        row = {"b": 2, "a": 1, "c": 3}
        out = chain.canonical_row_bytes(row)
        expected = b'{"a":1,"b":2,"c":3}'
        self.assertEqual(
            out, expected,
            f"canonical_row_bytes must sort keys; got {out!r}, expected {expected!r}",
        )

    def test_no_whitespace_separators(self):
        row = {"a": 1, "b": [1, 2, 3]}
        out = chain.canonical_row_bytes(row)
        self.assertNotIn(
            b" ", out,
            f"canonical_row_bytes must use separators=(',',':') with no whitespace; got {out!r}",
        )
        self.assertEqual(out, b'{"a":1,"b":[1,2,3]}')

    def test_chain_hash_field_is_stripped(self):
        row = {"a": 1, "chain_hash": "deadbeef" * 8}
        out = chain.canonical_row_bytes(row)
        self.assertEqual(
            out, b'{"a":1}',
            f"canonical_row_bytes must omit 'chain_hash'; got {out!r}",
        )

    def test_prev_chain_hash_field_is_stripped(self):
        row = {"a": 1, "prev_chain_hash": "cafebabe" * 8}
        out = chain.canonical_row_bytes(row)
        self.assertEqual(
            out, b'{"a":1}',
            f"canonical_row_bytes must omit 'prev_chain_hash'; got {out!r}",
        )

    def test_both_chain_fields_stripped_simultaneously(self):
        row = {
            "a": 1,
            "chain_hash": "x" * 64,
            "prev_chain_hash": "y" * 64,
            "b": 2,
        }
        out = chain.canonical_row_bytes(row)
        self.assertEqual(out, b'{"a":1,"b":2}')

    def test_none_values_are_serialized_as_null_not_omitted(self):
        row = {"a": 1, "b": None}
        out = chain.canonical_row_bytes(row)
        self.assertEqual(
            out, b'{"a":1,"b":null}',
            f"canonical_row_bytes must include None as null (not strip it); got {out!r}",
        )

    def test_non_ascii_is_escaped(self):
        row = {"x": "🌱"}
        out = chain.canonical_row_bytes(row)
        expected = b'{"x":"\\ud83c\\udf31"}'
        self.assertEqual(
            out, expected,
            f"canonical_row_bytes must use ensure_ascii=True; got {out!r}, expected {expected!r}",
        )

    def test_integer_zero_vs_string_zero_are_distinct(self):
        out_int = chain.canonical_row_bytes({"x": 0})
        out_str = chain.canonical_row_bytes({"x": "0"})
        self.assertNotEqual(
            out_int, out_str,
            "canonical_row_bytes must preserve type fidelity: 0 (int) and '0' (str) must produce distinct bytes",
        )
        self.assertEqual(out_int, b'{"x":0}')
        self.assertEqual(out_str, b'{"x":"0"}')

    def test_matches_reference_recipe_on_genesis_row(self):
        out = chain.canonical_row_bytes(GENESIS_ROW)
        expected = _canonical_bytes_expected(GENESIS_ROW)
        self.assertEqual(
            out, expected,
            "canonical_row_bytes(GENESIS_ROW) must match the §6.1 reference recipe; "
            "any divergence breaks the genesis chain.",
        )


class ComputeChainHashTests(unittest.TestCase):
    """Pin sha256(prefix || canonical_row_bytes) semantics."""

    def test_genesis_row_matches_migrate_recipe(self):
        from_chain = chain.compute_chain_hash(GENESIS_ROW, None)
        from_migrate = _canonical_genesis_chain_hash()
        self.assertEqual(
            from_chain, from_migrate,
            f"chain.compute_chain_hash and migrate._canonical_genesis_chain_hash "
            f"must agree on the genesis row.\n"
            f"  chain.compute_chain_hash: {from_chain}\n"
            f"  migrate canonical:        {from_migrate}\n"
            f"Divergence here means a fresh DB's seeded genesis_hash will not "
            f"verify against the chain walker.",
        )

    def test_genesis_row_uses_literal_genesis_prefix(self):
        canonical = _canonical_bytes_expected(GENESIS_ROW)
        expected = hashlib.sha256(b"genesis" + canonical).hexdigest()
        actual = chain.compute_chain_hash(GENESIS_ROW, None)
        self.assertEqual(
            actual, expected,
            "compute_chain_hash on the genesis row must use prefix b'genesis'.",
        )

    def test_non_genesis_uses_prior_chain_hash_as_prefix(self):
        prev = "a" * 64
        row = {
            "turn_id": "turn-0001",
            "tenant_id": "owner",
            "timestamp": 1700000001.0,
            "schema_version": 1,
            "turn_kind": "user_message",
            "surface": "telegram",
            "raw_text": "hello",
        }
        canonical = _canonical_bytes_expected(row)
        expected = hashlib.sha256(prev.encode("utf-8") + canonical).hexdigest()
        actual = chain.compute_chain_hash(row, prev)
        self.assertEqual(
            actual, expected,
            "compute_chain_hash on a non-genesis row must use the prior chain_hash "
            "(the hex string itself, utf-8 encoded) as prefix — NOT the literal 'genesis'.",
        )

    def test_non_genesis_does_not_use_literal_genesis_prefix(self):
        prev = "b" * 64
        row = {"turn_id": "x", "raw_text": "hi"}
        canonical = _canonical_bytes_expected(row)
        wrong = hashlib.sha256(b"genesis" + canonical).hexdigest()
        actual = chain.compute_chain_hash(row, prev)
        self.assertNotEqual(
            actual, wrong,
            "compute_chain_hash with a non-None prev must NOT use the literal "
            "'genesis' prefix; the prior chain_hash is the prefix.",
        )

    def test_is_deterministic(self):
        row = {"turn_id": "deterministic", "raw_text": "same input"}
        prev = "c" * 64
        a = chain.compute_chain_hash(row, prev)
        b = chain.compute_chain_hash(row, prev)
        c = chain.compute_chain_hash(row, prev)
        self.assertEqual(a, b)
        self.assertEqual(b, c)

    def test_returns_64_char_lowercase_hex(self):
        row = {"turn_id": "t", "raw_text": "x"}
        out = chain.compute_chain_hash(row, None)
        self.assertTrue(
            _is_lower_hex_64(out),
            f"compute_chain_hash must return strict 64-char lowercase hex; got {out!r}",
        )
        out2 = chain.compute_chain_hash(row, "d" * 64)
        self.assertTrue(
            _is_lower_hex_64(out2),
            f"compute_chain_hash must return strict 64-char lowercase hex; got {out2!r}",
        )

    def test_different_prev_produces_different_hash(self):
        row = {"turn_id": "t", "raw_text": "x"}
        h1 = chain.compute_chain_hash(row, "a" * 64)
        h2 = chain.compute_chain_hash(row, "b" * 64)
        self.assertNotEqual(
            h1, h2,
            "Different prev_chain_hash inputs must produce different chain_hash outputs.",
        )


class VerifyChainTests(unittest.TestCase):
    """Pin the chain-walk semantics."""

    def test_empty_list_returns_empty_violations(self):
        self.assertEqual(
            chain.verify_chain([]), [],
            "verify_chain([]) must return [] (degenerate case, no chain to verify).",
        )

    def test_single_genesis_row_returns_empty_violations(self):
        rows = _build_synthetic_chain(1)
        violations = chain.verify_chain(rows)
        self.assertEqual(
            violations, [],
            f"single-row genesis chain must verify clean; got violations: {violations!r}",
        )

    def test_five_valid_rows_returns_empty_violations(self):
        rows = _build_synthetic_chain(5)
        violations = chain.verify_chain(rows)
        self.assertEqual(
            violations, [],
            f"valid 5-row chain must verify clean; got violations: {violations!r}",
        )

    def test_detects_raw_text_tampering(self):
        rows = _build_synthetic_chain(5)
        tampered_idx = 2
        rows[tampered_idx]["raw_text"] = "TAMPERED"

        violations = chain.verify_chain(rows)
        self.assertTrue(
            len(violations) >= 1,
            f"verify_chain must flag at least one violation for raw_text tampering on row {tampered_idx}; "
            f"got: {violations!r}",
        )
        offending = [v for v in violations if v.get("row_index") == tampered_idx]
        self.assertTrue(
            offending,
            f"verify_chain must flag row_index={tampered_idx} (raw_text tampered); "
            f"violations: {violations!r}",
        )
        v = offending[0]
        self.assertEqual(v.get("turn_id"), rows[tampered_idx]["turn_id"])
        self.assertIn("reason", v)
        self.assertIn("expected", v)
        self.assertIn("actual", v)

    def test_detects_prev_chain_hash_link_breakage(self):
        rows = _build_synthetic_chain(5)
        broken_idx = 3
        rows[broken_idx]["prev_chain_hash"] = "f" * 64

        violations = chain.verify_chain(rows)
        self.assertTrue(
            len(violations) >= 1,
            f"verify_chain must flag at least one violation for prev_chain_hash link breakage on row {broken_idx}; "
            f"got: {violations!r}",
        )
        offending_indices = {v.get("row_index") for v in violations}
        self.assertIn(
            broken_idx, offending_indices,
            f"verify_chain must flag row_index={broken_idx} for broken prev_chain_hash link; "
            f"violations: {violations!r}",
        )

    def test_detects_inserted_forged_row(self):
        rows = _build_synthetic_chain(5)
        forged = {
            "turn_id": "forged-row",
            "tenant_id": "owner",
            "timestamp": 1_700_000_500.0,
            "schema_version": 1,
            "turn_kind": "user_message",
            "surface": "telegram",
            "raw_surface": "telegram_text",
            "parent_turn_id": None,
            "correction_of": None,
            "model_id": None,
            "lora_hash": None,
            "soul_hash": None,
            "prompt_hash": None,
            "raw_text": "forged content",
            "rewritten_text": None,
            "was_rewritten": 0,
            "signals_present": "[]",
            "signals_absent": "[]",
            "evidence_envelope_json": None,
            "action_proposal_json": None,
            "audit_verdict_json": None,
            "will_i_json": None,
            "memory_read_ids": "[]",
            "memory_written_ids": "[]",
            "audit_log_id": None,
            "fabrication_event_id": None,
            "self_mod_dialog_id": None,
            "pending_card_id": None,
            "prev_chain_hash": "9" * 64,
        }
        forged["chain_hash"] = _expected_chain_hash(forged, "9" * 64)

        tampered = rows[:3] + [forged] + rows[3:]

        violations = chain.verify_chain(tampered)
        self.assertTrue(
            len(violations) >= 1,
            f"verify_chain must flag the forged inserted row; got no violations: {violations!r}",
        )
        flagged_indices = {v.get("row_index") for v in violations}
        self.assertTrue(
            3 in flagged_indices or 4 in flagged_indices,
            f"verify_chain must flag the insertion site (row 3 forged or row 4 broken-link); "
            f"violations: {violations!r}",
        )


if __name__ == "__main__":
    unittest.main()
