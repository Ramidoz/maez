"""Schema + validator for the grounding audition corpus.

The corpus is DATA whose labels are covenant-critical; this validator catches
structural mistakes, the human label-review gate catches semantic ones.
"""
from __future__ import annotations

MODES = frozenset({
    "grounded_positive", "cited_but_unsupported", "fabricated_false_specific",
    "stale_over_current", "no_evidence_abstain", "multi_claim",
})
SOURCES = frozenset({"real-longmemeval", "synthetic"})
EVIDENCE_KINDS = frozenset({"claimable_present", "claimable_absent", "stale_vs_current"})
LABELS = frozenset({"SUPPORTED", "UNSUPPORTED", "ABSTAIN_EXPECTED"})
_REQUIRED = ("id", "mode", "source", "evidence_kind", "evidence", "claim",
             "expected", "strict_rule", "rationale")


def validate_corpus(items: list[dict]) -> None:
    """Raise ValueError on the first structural problem; return None if clean."""
    seen_ids: set[str] = set()
    for i, row in enumerate(items):
        for key in _REQUIRED:
            if key not in row:
                raise ValueError(f"row {i}: missing required field {key!r}")
        rid = row["id"]
        if row["mode"] not in MODES:
            raise ValueError(f"row {rid}: bad mode {row['mode']!r}")
        if row["source"] not in SOURCES:
            raise ValueError(f"row {rid}: bad source {row['source']!r}")
        if row["evidence_kind"] not in EVIDENCE_KINDS:
            raise ValueError(f"row {rid}: bad evidence_kind {row['evidence_kind']!r}")
        if row["expected"] not in LABELS:
            raise ValueError(f"row {rid}: bad expected {row['expected']!r}")
        if not isinstance(row["strict_rule"], bool):
            raise ValueError(f"row {rid}: strict_rule must be bool")
        # the load-bearing invariant: absent evidence <-> abstain expected
        if row["evidence_kind"] == "claimable_absent" and row["expected"] != "ABSTAIN_EXPECTED":
            raise ValueError(f"row {rid}: claimable_absent must expect ABSTAIN_EXPECTED")
        if row["evidence_kind"] != "claimable_absent" and row["expected"] == "ABSTAIN_EXPECTED":
            raise ValueError(f"row {rid}: ABSTAIN_EXPECTED only valid with claimable_absent")
        if not str(row["rationale"]).strip():
            raise ValueError(f"row {rid}: empty rationale (label must be reasoned)")
        # A truth-bearing corpus must carry receipts for its 'real' rows: a
        # real-longmemeval row needs a source_ref pointing back to the file.
        if row["source"] == "real-longmemeval":
            if not str(row.get("source_ref", "")).strip():
                raise ValueError(f"row {rid}: real-longmemeval rows require a source_ref")
            if not str(row.get("receipt_ref", "")).strip():
                raise ValueError(f"row {rid}: real-longmemeval rows require a receipt_ref "
                                 "(an in-branch committed receipt artifact)")
        if rid in seen_ids:
            raise ValueError(f"duplicate id {rid!r}")
        seen_ids.add(rid)
