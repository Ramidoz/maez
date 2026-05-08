#!/usr/bin/env python3
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Read-only probe for Slice 4a/4b recall projection.

Shows raw ledger-derived self_history beside the projection view.
This is operator tooling, not a birth-readiness fixture. It never writes
to the ledger and does not feed production prompts or audit evidence.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from core.ledger import envelope_schema as _es  # noqa: E402
from core.ledger import recent_turns as _rt  # noqa: E402
from core.memory import recall_projection as _rp  # noqa: E402


def _rows_to_self_history(rows: list[dict]) -> list[dict]:
    entries: list[dict] = []
    for row in rows:
        entries.append({
            "turn_id": row.get("turn_id", ""),
            "timestamp": row.get("timestamp"),
            "kind": row.get("turn_kind", ""),
            "utterance_summary": (row.get("raw_text") or "")[:200],
            "lifecycle_stage": row.get("lifecycle_stage") or "unknown",
        })
    return entries


def build_report(
    *,
    ledger_db_path: str,
    tenant_id: str,
    limit: int,
    recall_gestation: str,
    projection_rule: str,
) -> dict:
    rows = _rt.recent_turns_by_kind(
        ledger_db_path,
        kinds=list(_es.SELF_HISTORY_KINDS),
        limit=limit,
        tenant_id=tenant_id,
        recall_gestation=recall_gestation,
    )
    raw_self_history = _rows_to_self_history(rows)
    policy = {
        "identity.v1": _rp.DEFAULT_POLICY,
        "repetition_with_continuity.v1": (
            _rp.REPETITION_WITH_CONTINUITY_POLICY
        ),
    }[projection_rule]
    projection = _rp.project_self_history(raw_self_history, policy=policy)
    return {
        "mode": "read_only_memory_projection_probe",
        "projection_rule": projection_rule,
        "raw_self_history": raw_self_history,
        "projection": projection.to_dict(),
    }


def _candidate_by_id(
    candidates: list[_rp.ProjectionCandidate],
) -> dict[str, _rp.ProjectionCandidate]:
    return {candidate.candidate_id: candidate for candidate in candidates}


def projection_observation_records(
    *,
    report: _rp.ProjectionReport,
    candidates: list[_rp.ProjectionCandidate],
) -> list[dict[str, Any]]:
    """Return diagnostic-only records for Slice 4c observation logs."""

    candidates_by_id = _candidate_by_id(candidates)
    records: list[dict[str, Any]] = []
    for item in report.items:
        candidate = candidates_by_id[item.turn_id]
        records.append({
            "schema_version": report.schema_version,
            "policy": report.policy.to_dict(),
            "candidate_count": len(candidates),
            "projected_count": report.projected_count,
            "candidate_id": candidate.candidate_id,
            "candidate_kind": candidate.candidate_kind,
            "trust_scope": candidate.trust_scope,
            "source_ids": list(candidate.source_ids),
            "continuity_key": candidate.continuity_key,
            "would_strengthen": item.projection_effect == "strengthened",
            "projection_effect": item.projection_effect,
            "strength_reasons": list(item.strength_reasons),
            "rule_inputs": dict(item.rule_inputs),
            "counterevidence_refs": [
                ref.to_dict() for ref in item.counterevidence_refs
            ],
            "audit_boundary": report.audit_boundary,
            "policy_doc_sha256": report.policy_doc_sha256,
        })
    return records


def write_projection_observation(
    *,
    report: _rp.ProjectionReport,
    candidates: list[_rp.ProjectionCandidate],
    log_path: Path,
) -> None:
    """Append Slice 4c projection diagnostics to a JSONL log file.

    This writes operator diagnostics only. It does not write the ledger,
    alter prompt context, or feed audit evidence.
    """

    log_path.parent.mkdir(parents=True, exist_ok=True)
    records = projection_observation_records(
        report=report,
        candidates=candidates,
    )
    with log_path.open("a", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger_db_path")
    parser.add_argument("--tenant-id", default="owner")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument(
        "--recall-gestation",
        choices=("user", "full"),
        default="user",
    )
    parser.add_argument(
        "--projection-rule",
        choices=("identity.v1", "repetition_with_continuity.v1"),
        default="identity.v1",
    )
    args = parser.parse_args(argv)
    report = build_report(
        ledger_db_path=args.ledger_db_path,
        tenant_id=args.tenant_id,
        limit=args.limit,
        recall_gestation=args.recall_gestation,
        projection_rule=args.projection_rule,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
