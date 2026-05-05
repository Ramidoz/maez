# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""ledger.py — Maez Eval Harness v1.5 owner-rubric ledger.

Bridges the gap between v1's needs_owner_review outcomes and a
consolidated final result. The eval harness emits one of:

  pass | fail | needs_owner_review | skip | error

For probes graded `binary` and auto-wired in the runner, the
outcome is set automatically. For `rubric` / `owner_judge` /
`mixed` grading, the runner emits `needs_owner_review` carrying
the prompt + expected_shape as evidence.

This module:
  emit_ledger(run_result_dict)
      → ledger dict (one entry per needs_owner_review probe,
        with `verdict: ""` blank for the owner to fill in).
  write_ledger(ledger, path)
  read_ledger(path) → ledger dict
  collect_verdicts(run_result_dict, ledger)
      → consolidated run_result_dict where filled-in verdicts
        have replaced the needs_owner_review outcomes.

Owner workflow:
  1. python -m core.symphony.evals.runner --write
       → docs/.../<run_id>/run_result.json
  2. python -m core.symphony.evals.runner --emit-ledger <run_id>
       → docs/.../<run_id>/ledger.yaml (verdicts blank)
  3. Owner edits ledger.yaml, sets verdict per probe.
  4. python -m core.symphony.evals.runner --collect <run_id>
       → docs/.../<run_id>/consolidated.json
  5. Repeat steps 3-4 as the owner works through the queue —
     blank verdicts stay needs_owner_review, partial progress
     is supported.
"""
from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("maez.symphony.evals.ledger")

# Documented owner-verdict vocabulary. Distinct from EvalResult
# OUTCOMES because:
#   - needs_owner_review and error are runner states, not owner
#     verdicts.
#   - needs_rewrite means the PROBE itself was wrong (the prompt
#     didn't measure what it claimed). Different from `fail`
#     (probe correct, Maez failed it).
VALID_VERDICTS = (
    "pass",
    "fail",
    "skip",
    "needs_rewrite",
)

# Empty-string verdict means "owner hasn't filled this in yet."
# Partial-progress is intentional — the ledger walks at the owner's
# pace, not the harness's.
_BLANK_VERDICT = ""


def emit_ledger(run_result: dict[str, Any]) -> dict[str, Any]:
    """Walk a RunResult dict and emit a ledger draft for owner
    grading. Only `needs_owner_review` results are included;
    auto-graded results stay in the run_result and don't need
    owner attention.

    Returns a dict with:
      run_id: copy of the run's id
      verdicts: list of dicts, one per needs_owner_review probe,
        each with: probe_id, family, prompt, expected_shape, tags,
        surface, evidence_notes, verdict (blank), verdict_notes
        (blank).
    """
    verdicts: list[dict[str, Any]] = []
    families = run_result.get("families") or {}
    # Sort by family then probe_id so the ledger has a stable
    # ordering across runs — owner-friendly diff if probes are
    # added or removed.
    for family in sorted(families.keys()):
        family_dict = families[family]
        results = family_dict.get("results") or []
        for r in results:
            if r.get("outcome") != "needs_owner_review":
                continue
            evidence = r.get("evidence") or {}
            verdicts.append({
                "probe_id": r.get("probe_id", ""),
                "family": r.get("family", family),
                "prompt": evidence.get("prompt", ""),
                "expected_shape": evidence.get("expected_shape", ""),
                "tags": list(evidence.get("tags") or []),
                "surface": evidence.get("surface"),
                "evidence_notes": r.get("notes", ""),
                "verdict": _BLANK_VERDICT,
                "verdict_notes": "",
            })
    # Sort verdicts by (family, probe_id) for stable diff.
    verdicts.sort(key=lambda v: (v["family"], v["probe_id"]))
    return {
        "run_id": run_result.get("run_id", "unknown"),
        "verdicts": verdicts,
    }


def write_ledger(ledger: dict[str, Any], path: Path) -> None:
    """Serialize the ledger to YAML at `path`. Creates parent dirs
    if needed. Stable serialization so git diffs are clean."""
    path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# Maez Eval Harness v1.5 — owner-rubric ledger\n"
        "#\n"
        "# Set `verdict:` per entry to one of:\n"
        "#   pass           — probe passed: Maez held the contract\n"
        "#   fail           — probe failed: Maez missed the contract\n"
        "#   skip           — pre-condition unmet, can't grade\n"
        "#   needs_rewrite  — probe itself was wrong (prompt didn't\n"
        "#                    measure what it claimed); rewrite + re-run\n"
        "#\n"
        "# Blank verdicts stay `needs_owner_review` after collect —\n"
        "# partial progress is supported. Optional `verdict_notes:`\n"
        "# captures rationale + lands in evidence on collect.\n"
        "#\n"
    )
    yaml_body = yaml.safe_dump(
        ledger,
        sort_keys=True, default_flow_style=False, allow_unicode=True,
        width=88,
    )
    path.write_text(header + yaml_body, encoding="utf-8")


def read_ledger(path: Path) -> dict[str, Any]:
    """Read a ledger YAML from disk."""
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def collect_verdicts(
    run_result: dict[str, Any],
    ledger: dict[str, Any],
) -> dict[str, Any]:
    """Merge owner verdicts from `ledger` into a consolidated
    copy of `run_result`. Returns a NEW dict; the input is not
    mutated.

    Verdict mapping:
      pass / fail / skip / needs_rewrite → set as the EvalResult
      outcome, with verdict_notes copied to evidence.verdict_notes.

      Empty / missing verdict → entry stays needs_owner_review
      (partial-progress friendly).

      Invalid verdict value → ValueError. The error names the
      bad value AND the probe_id so the owner can find it in
      the YAML.

    The consolidated result also re-counts outcomes per family
    so dashboards / CI see the post-rubric tallies.
    """
    consolidated = copy.deepcopy(run_result)
    # Build a lookup: probe_id → verdict dict
    verdicts_by_id: dict[str, dict[str, Any]] = {}
    for v in ledger.get("verdicts") or []:
        pid = v.get("probe_id")
        if not pid:
            continue
        verdicts_by_id[pid] = v

    # Validate verdict values up front so we surface ALL bad ones
    # (not just the first). Owner gets one round-trip to fix YAML.
    bad: list[tuple[str, str]] = []
    for pid, v in verdicts_by_id.items():
        verdict = v.get("verdict") or ""
        if verdict and verdict not in VALID_VERDICTS:
            bad.append((pid, verdict))
    if bad:
        msgs = "; ".join(
            f"probe_id={pid!r} has verdict={vv!r} (must be one of "
            f"{', '.join(VALID_VERDICTS)} or blank)"
            for pid, vv in bad
        )
        raise ValueError(f"invalid verdict(s) in ledger: {msgs}")

    # Walk every family, apply the verdicts.
    families = consolidated.get("families") or {}
    for family_name, family_dict in families.items():
        results = family_dict.get("results") or []
        for r in results:
            if r.get("outcome") != "needs_owner_review":
                continue
            v = verdicts_by_id.get(r.get("probe_id"))
            if v is None:
                continue
            verdict = v.get("verdict") or ""
            if verdict == _BLANK_VERDICT:
                continue  # blank stays needs_owner_review
            r["outcome"] = verdict
            # Carry verdict_notes into the evidence so the
            # consolidated record is self-describing.
            ev = dict(r.get("evidence") or {})
            notes = v.get("verdict_notes") or ""
            if notes:
                ev["verdict_notes"] = notes
            r["evidence"] = ev
            r["notes"] = (
                (r.get("notes") or "")
                + (" | owner-verdict applied" if r.get("notes") else "owner-verdict applied")
            )
        # Re-count outcomes for this family.
        counts = {
            o: 0 for o in (
                "pass", "fail", "needs_owner_review", "skip", "error",
                "needs_rewrite",
            )
        }
        for r in results:
            counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
        family_dict["counts"] = counts

    return consolidated
