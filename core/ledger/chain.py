# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Maez ledger chain primitives.

Pure functions implementing the tamper-evidence chain construction and
witness-binding verification described in
docs/LEDGER_ENVELOPE_SCHEMA.md §6.1.

Public API:

    canonical_row_bytes(row)
        Serialize a turn row dict to canonical JSON bytes (utf-8),
        omitting ``chain_hash`` and ``prev_chain_hash``. Keys sorted,
        no whitespace, ``ensure_ascii=True``. NULL values stay as
        ``null`` (not stripped); type fidelity is preserved.

    compute_chain_hash(row, prev_chain_hash)
        Per §6.1: ``sha256(prefix || canonical_row_bytes(row))`` where
        ``prefix`` is ``b"genesis"`` for the genesis row (``prev_chain_hash
        is None``) and ``prev_chain_hash.encode("utf-8")`` otherwise.
        Returns 64-char lowercase hex.

    verify_chain(rows)
        Walk a list of turn-row dicts in chain order and return a list
        of violation dicts. Each violation carries ``row_index``,
        ``turn_id``, ``reason``, ``expected``, and ``actual``. Detects
        chain-hash mismatches (body tampered) and broken prev-links
        (insertion / reorder). Empty input → empty violations.
        NOTE: input must be in chain order; the orchestrator that calls
        this from a SQLite query is responsible for ordering rows.

    verify_claim_witnesses(turns_by_id, claims)
        Confirm each claim's ``parent_turn_chain_hash`` equals the
        parent turn's ``chain_hash``. Flags orphan claims (no parent
        turn in ``turns_by_id``) and witness mismatches.

    verify_judgement_witnesses(claims_by_id, judgements)
        Symmetric for judgements: each judgement's
        ``parent_claim_witness`` must equal the parent claim's
        ``parent_turn_chain_hash``. Orphans flagged separately.

Stdlib only (hashlib, json). No I/O, no globals, no side effects —
DB loading happens in scripts/verify_ledger_chain.py.
"""
from __future__ import annotations

import hashlib
import json

__all__ = [
    "canonical_row_bytes",
    "compute_chain_hash",
    "verify_chain",
    "verify_claim_witnesses",
    "verify_judgement_witnesses",
]


def canonical_row_bytes(row: dict) -> bytes:
    """Return the §6.1 canonical JSON bytes for a turn row."""
    stripped = {
        k: v
        for k, v in row.items()
        if k not in ("chain_hash", "prev_chain_hash")
    }
    return json.dumps(
        stripped,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def compute_chain_hash(row: dict, prev_chain_hash: str | None) -> str:
    """Compute the chain hash for a turn row per §6.1."""
    if prev_chain_hash is None:
        prefix = b"genesis"
    else:
        prefix = prev_chain_hash.encode("utf-8")
    return hashlib.sha256(prefix + canonical_row_bytes(row)).hexdigest()


def verify_chain(rows: list[dict]) -> list[dict]:
    """Walk a turn-row chain and return a list of violation dicts.

    Two checks per row:

    1. ``chain_hash`` recomputation: ``compute_chain_hash(row,
       row['prev_chain_hash'])`` must equal the stored ``chain_hash``.

    2. Prev-link integrity: for every non-genesis row at position i,
       ``rows[i]['prev_chain_hash']`` must equal
       ``rows[i-1]['chain_hash']``.

    Each violation dict carries ``row_index``, ``turn_id``,
    ``reason``, ``expected``, ``actual`` — every key always present
    so callers can use ``v["..."]`` or ``v.get("...")`` interchangeably.
    """
    violations: list[dict] = []
    if not rows:
        return violations

    for i, row in enumerate(rows):
        turn_id = row.get("turn_id", "")
        stored_hash = row.get("chain_hash", "")
        stored_prev = row.get("prev_chain_hash")

        recomputed = compute_chain_hash(row, stored_prev)
        if recomputed != stored_hash:
            violations.append({
                "row_index": i,
                "turn_id": turn_id,
                "reason": "chain-hash-mismatch",
                "expected": recomputed,
                "actual": stored_hash if isinstance(stored_hash, str) else "",
            })

        if i == 0:
            continue
        prev_row_hash = rows[i - 1].get("chain_hash", "")
        if stored_prev != prev_row_hash:
            violations.append({
                "row_index": i,
                "turn_id": turn_id,
                "reason": "broken-prev-link",
                "expected": prev_row_hash if isinstance(prev_row_hash, str) else "",
                "actual": stored_prev if isinstance(stored_prev, str) else "",
            })

    return violations


def verify_claim_witnesses(
    turns_by_id: dict,
    claims: list[dict],
) -> list[dict]:
    """Verify every claim's ``parent_turn_chain_hash`` matches its turn.

    LIMITATION (must be paired with verify_chain): this function only
    verifies that a claim's witness column equals the *currently stored*
    chain_hash on its parent turn. It does NOT recompute the parent
    turn's chain_hash from the canonical recipe. An attacker who
    rewrites BOTH a turn's chain_hash AND every dependent claim's
    parent_turn_chain_hash in lockstep will pass this verifier.

    To detect that class of attack, callers MUST also call
    ``verify_chain(turns)`` — which recomputes each turn's chain_hash
    from canonical bytes and catches body tampering. The two verifiers
    are complementary and the production walker
    (``scripts/verify_ledger_chain.py``) runs both unconditionally.

    Additionally: this function does NOT cover claim BODY tampering
    (e.g., rewriting ``claims.fact``). The witness binds parent
    identity, not claim content. See §6.1 of the schema doc for the
    documented limitation; tightening this is a future schema slice.
    """
    violations: list[dict] = []
    for claim in claims:
        claim_id = claim.get("claim_id")
        turn_id = claim.get("turn_id")
        actual_witness = claim.get("parent_turn_chain_hash", "")

        parent_turn = turns_by_id.get(turn_id)
        if parent_turn is None:
            violations.append({
                "claim_id": claim_id,
                "turn_id": turn_id,
                "reason": "orphan-claim-no-parent-turn",
                "expected": "",
                "actual": actual_witness if isinstance(actual_witness, str) else "",
            })
            continue

        expected_witness = parent_turn.get("chain_hash", "")
        if actual_witness != expected_witness:
            violations.append({
                "claim_id": claim_id,
                "turn_id": turn_id,
                "reason": "claim-witness-mismatch",
                "expected": expected_witness if isinstance(expected_witness, str) else "",
                "actual": actual_witness if isinstance(actual_witness, str) else "",
            })

    return violations


def verify_judgement_witnesses(
    claims_by_id: dict,
    judgements: list[dict],
) -> list[dict]:
    """Verify every judgement's ``parent_claim_witness`` matches its claim.

    Same limitation as ``verify_claim_witnesses``: this is a relative
    binding check. It does NOT recompute parent identity from
    canonical bytes, and it does NOT cover judgement body tampering
    (e.g., rewriting the ``provenance`` or ``audit_verdict``).

    Pair with ``verify_chain`` and ``verify_claim_witnesses`` for
    full chain integrity. See §6.1 of the schema doc.
    """
    violations: list[dict] = []
    for judgement in judgements:
        judgement_id = judgement.get("judgement_id")
        claim_id = judgement.get("claim_id")
        actual_witness = judgement.get("parent_claim_witness", "")

        parent_claim = claims_by_id.get(claim_id)
        if parent_claim is None:
            violations.append({
                "judgement_id": judgement_id,
                "claim_id": claim_id,
                "reason": "orphan-judgement-no-parent-claim",
                "expected": "",
                "actual": actual_witness if isinstance(actual_witness, str) else "",
            })
            continue

        expected_witness = parent_claim.get("parent_turn_chain_hash", "")
        if actual_witness != expected_witness:
            violations.append({
                "judgement_id": judgement_id,
                "claim_id": claim_id,
                "reason": "judgement-witness-mismatch",
                "expected": expected_witness if isinstance(expected_witness, str) else "",
                "actual": actual_witness if isinstance(actual_witness, str) else "",
            })

    return violations
