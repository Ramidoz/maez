# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""runner.py — Maez Eval Harness v1 runner.

Loads YAML corpora, runs each probe (probe-mode only — never
drives live surfaces or writes to live daemon stores), produces
EvalResult / FamilyResult / RunResult per the schema.

V1 design notes:
  - Probes that are binary-graded get an automatic outcome where
    the runner can compute it from observable state (e.g. body
    capabilities snapshot, file source). Probes that need an LLM
    in the loop or owner judgment are emitted with
    outcome='needs_owner_review' so the owner-rubric ledger stage
    can pick them up later.
  - The v1 runner is intentionally conservative — it does NOT
    invoke the brain, drive Telegram, or POST to /chat. It reads
    code, body_capabilities, and the surface_probe baseline.
  - Future expansion: a `--owner-rate` mode that emits each
    needs_owner_review probe to a ledger (json/yaml) with a slot
    for the owner's verdict, similar to `audit_request_id` in
    pending_cards.
"""
from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional

import yaml

from core.symphony.evals.schema import (
    EvalProbe, EvalResult, FamilyResult, RunResult, FAMILIES,
)

logger = logging.getLogger("maez.symphony.evals")

REPO = Path(__file__).resolve().parents[3]
_CORPORA_DIR = Path(__file__).parent / "corpora"


# ── Corpus loading ───────────────────────────────────────────────────


def _corpus_path(family: str) -> Path:
    return _CORPORA_DIR / f"{family}.yaml"


def load_corpus(family: str) -> list[EvalProbe]:
    """Read one family's corpus YAML and return its probes.

    YAML schema:
        probes:
          - id: <str>
            prompt: <str, multi-line allowed>
            expected_shape: <str>
            grading: binary | rubric | owner_judge | mixed
            tags: [optional list of str]
            surface: <optional str — preferred surface>
            notes: <optional str>

    Probes inherit `family` from the file they're loaded from;
    the schema test asserts the inherited value matches.
    """
    if family not in FAMILIES:
        raise ValueError(f"unknown family {family!r}")
    path = _corpus_path(family)
    if not path.exists():
        raise FileNotFoundError(f"corpus file missing: {path}")
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    probe_dicts = raw.get("probes") or []
    out: list[EvalProbe] = []
    for d in probe_dicts:
        out.append(EvalProbe(
            id=str(d.get("id", "")),
            family=family,
            prompt=str(d.get("prompt", "")),
            expected_shape=str(d.get("expected_shape", "")),
            grading=str(d.get("grading", "rubric")),
            tags=list(d.get("tags") or []),
            surface=d.get("surface"),
            notes=str(d.get("notes", "")),
        ))
    return out


# ── Per-family probe execution ────────────────────────────────────────
#
# V1 ships ONE generic probe runner that handles every family by
# emitting needs_owner_review for rubric / owner_judge / mixed
# grading and a conservative pass for the binary-graded proof
# probes (their expected_shape + tags carry enough context to
# render evidence). Future slices will specialize per family
# (e.g. body_action_truth probes interrogate body_capabilities
# directly to compute pass/fail without owner involvement).


def _run_probe(probe: EvalProbe) -> EvalResult:
    """Run one probe in v1 mode.

    Behaviour by grading:
      - rubric / owner_judge / mixed → outcome='needs_owner_review'
        with evidence.prompt rendered for the owner's later review.
      - binary → emit evidence describing the observable state.
        V1 binary probes use the inspection helpers in this
        module (body_capabilities snapshot, surface_probe diff,
        etc.). Probes whose binary check is NOT yet wired emit
        'needs_owner_review' with a note explaining the gap.
    """
    started = time.time()
    if probe.grading in ("rubric", "owner_judge", "mixed"):
        return EvalResult(
            probe_id=probe.id,
            family=probe.family,
            outcome="needs_owner_review",
            grading=probe.grading,
            evidence={
                "prompt": probe.prompt,
                "expected_shape": probe.expected_shape,
                "tags": list(probe.tags),
                "surface": probe.surface,
            },
            duration_s=time.time() - started,
            notes="emitted for owner-rubric ledger; v1 does not "
                  "automate this grading kind",
        )

    # Binary path. v1 has narrow auto-grading: we run probe-family-
    # specific predicates where we can, otherwise emit
    # needs_owner_review with a note explaining the binary check
    # isn't wired yet. This is intentional: v1 is the scaffold,
    # not the verdict.
    auto = _try_auto_binary(probe)
    if auto is not None:
        outcome, evidence, notes = auto
        return EvalResult(
            probe_id=probe.id,
            family=probe.family,
            outcome=outcome,
            grading=probe.grading,
            evidence=evidence,
            duration_s=time.time() - started,
            notes=notes,
        )

    return EvalResult(
        probe_id=probe.id,
        family=probe.family,
        outcome="needs_owner_review",
        grading=probe.grading,
        evidence={
            "prompt": probe.prompt,
            "expected_shape": probe.expected_shape,
            "tags": list(probe.tags),
        },
        duration_s=time.time() - started,
        notes="binary check not yet wired in v1; treat as pending "
              "and review manually",
    )


def _try_auto_binary(probe: EvalProbe) -> Optional[tuple[str, dict, str]]:
    """Best-effort auto-grading for binary probes whose check is
    cheap and side-effect-free. Returns (outcome, evidence, notes)
    or None if no auto-grading path exists for this probe.

    V1 wires three narrow auto-graders to demonstrate the shape:
      - 'wmctrl_uninstalled' tag → check body_capabilities; pass if
        body reports wmctrl absent.
      - 'judge_endpoint_reachable' tag → check body_capabilities
        services; pass if brain_8080 is reachable.
      - 'surface_baseline_unchanged' tag → diff R5 baseline against
        live surface_probe; pass if no drift.

    These are proof-of-shape — the curator's full corpus will add
    more. They live here in v1 so the test suite can exercise the
    auto-grade path, not just the owner-review path.
    """
    tags = set(probe.tags or [])
    try:
        if "wmctrl_uninstalled" in tags:
            from core.infra import body_capabilities as bc
            snap = bc.body_capabilities()
            absent = not snap.get("binaries", {}).get("wmctrl", True)
            return (
                "pass" if absent else "fail",
                {
                    "tag": "wmctrl_uninstalled",
                    "body_capabilities.binaries.wmctrl": (
                        snap.get("binaries", {}).get("wmctrl")
                    ),
                },
                "auto-graded via body_capabilities probe",
            )
        if "judge_endpoint_reachable" in tags:
            from core.infra import body_capabilities as bc
            snap = bc.body_capabilities()
            ok = bool(snap.get("services", {}).get("brain_8080"))
            return (
                "pass" if ok else "fail",
                {
                    "tag": "judge_endpoint_reachable",
                    "services.brain_8080": (
                        snap.get("services", {}).get("brain_8080")
                    ),
                },
                "auto-graded via body_capabilities services probe",
            )
        if "surface_baseline_unchanged" in tags:
            from core.symphony import surface_probe as sp
            baseline_path = (
                REPO / "docs" / "audit_symphony_2026-05-04"
                / "baselines" / "surface_probe_2026-05-04.json"
            )
            if not baseline_path.exists():
                return (
                    "skip",
                    {"baseline_path": str(baseline_path)},
                    "baseline file missing; pre-condition unmet",
                )
            old = sp.read_baseline(baseline_path)
            new = sp.run_probe(baseline_id="live")
            deltas = sp.diff_baselines(old, new)
            return (
                "pass" if not deltas else "fail",
                {
                    "tag": "surface_baseline_unchanged",
                    "delta_count": len(deltas),
                    "deltas": deltas[:10],
                },
                "auto-graded via surface_probe diff",
            )
    except Exception as e:
        logger.warning(
            "_try_auto_binary failed for %s: %s",
            probe.id, e,
        )
        return (
            "error",
            {"exception": f"{type(e).__name__}: {e}"},
            "auto-grade probe raised",
        )
    return None


# ── Public API ───────────────────────────────────────────────────────


def run_family(family: str) -> FamilyResult:
    """Run every probe in one family's corpus."""
    started = time.time()
    probes = load_corpus(family)
    results = [_run_probe(p) for p in probes]
    return FamilyResult(
        family=family,
        results=results,
        started_at=started,
        duration_s=time.time() - started,
    )


def run_all(*, run_id: Optional[str] = None) -> RunResult:
    """Run every family. Returns the canonical RunResult."""
    started = time.time()
    if run_id is None:
        run_id = time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime())
    families: dict[str, FamilyResult] = {}
    for family in FAMILIES:
        try:
            families[family] = run_family(family)
        except Exception as e:
            logger.warning(
                "run_family(%s) failed: %s — recording as empty "
                "FamilyResult so the run still completes",
                family, e,
            )
            families[family] = FamilyResult(
                family=family,
                results=[],
                started_at=time.time(),
                duration_s=0.0,
            )
    return RunResult(
        run_id=run_id,
        started_at=started,
        duration_s=time.time() - started,
        families=families,
    )


def write_run_result(result: RunResult, *, base_dir: Optional[Path] = None) -> Path:
    """Serialize a RunResult to disk under
    docs/audit_symphony_2026-05-04/evals/<run_id>/run_result.json.
    Returns the path written."""
    if base_dir is None:
        base_dir = (
            REPO / "docs" / "audit_symphony_2026-05-04" / "evals"
        )
    out_dir = base_dir / result.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "run_result.json"
    out_path.write_text(
        json.dumps(result.to_dict(), indent=2, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )
    return out_path


# ── CLI ──────────────────────────────────────────────────────────────


def _evals_dir() -> Path:
    return REPO / "docs" / "audit_symphony_2026-05-04" / "evals"


def main(argv: Optional[list[str]] = None) -> int:
    import argparse
    import os
    from core.symphony.evals import ledger as _ledger

    p = argparse.ArgumentParser(
        prog="python -m core.symphony.evals.runner",
        description="Run the Maez eval harness.",
    )
    p.add_argument(
        "--family", default=None,
        help="Run a single family by name. Defaults to all families.",
    )
    p.add_argument(
        "--write", action="store_true",
        help="Write the RunResult to disk under "
             "docs/audit_symphony_2026-05-04/evals/<run_id>/",
    )
    p.add_argument(
        "--run-id", default=None,
        help="Run ID. Defaults to UTC timestamp on --write/no-flag, "
             "or REQUIRED for --emit-ledger / --collect.",
    )
    p.add_argument(
        "--emit-ledger", action="store_true",
        help="Emit a ledger.yaml draft from a previously written "
             "run_result.json (--run-id required). Owner edits "
             "the ledger to set verdict per probe.",
    )
    p.add_argument(
        "--collect", action="store_true",
        help="Read run_result.json + ledger.yaml for --run-id and "
             "write consolidated.json with owner verdicts merged in. "
             "Blank verdicts stay needs_owner_review.",
    )
    args = p.parse_args(argv)

    # ── Ledger workflows ──
    if args.emit_ledger or args.collect:
        if not args.run_id:
            print(
                "error: --emit-ledger and --collect require --run-id "
                "(the run whose results we're processing)",
                file=sys.stderr,
            )
            return 2
        run_dir = _evals_dir() / args.run_id
        run_path = run_dir / "run_result.json"
        if not run_path.exists():
            print(
                f"error: no run_result.json at {run_path} — "
                f"run --write first to produce it",
                file=sys.stderr,
            )
            return 2
        run_result = json.loads(run_path.read_text(encoding="utf-8"))
        ledger_path = run_dir / "ledger.yaml"

        if args.emit_ledger:
            draft = _ledger.emit_ledger(run_result)
            if ledger_path.exists():
                # Don't clobber owner verdicts already filled in;
                # require explicit --force to rewrite. v1.5 keeps
                # this safe by refusing rather than supporting force
                # — owner can delete the file manually if they truly
                # want a fresh draft.
                print(
                    f"error: {os.path.relpath(ledger_path, REPO)} "
                    f"already exists. Delete it manually if you "
                    f"want a fresh draft (v1.5 does not auto-clobber "
                    f"owner verdicts).",
                    file=sys.stderr,
                )
                return 3
            _ledger.write_ledger(draft, ledger_path)
            n = len(draft.get("verdicts") or [])
            print(
                f"eval-harness: wrote {os.path.relpath(ledger_path, REPO)} "
                f"({n} verdict slot{'s' if n != 1 else ''})",
                file=sys.stderr,
            )
            return 0

        # --collect
        if not ledger_path.exists():
            print(
                f"error: no ledger.yaml at {ledger_path} — "
                f"run --emit-ledger first",
                file=sys.stderr,
            )
            return 2
        ledger = _ledger.read_ledger(ledger_path)
        try:
            consolidated = _ledger.collect_verdicts(run_result, ledger)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 4
        consolidated_path = run_dir / "consolidated.json"
        consolidated_path.write_text(
            json.dumps(consolidated, indent=2, sort_keys=True, default=str)
            + "\n",
            encoding="utf-8",
        )
        # Summarize what changed for the owner.
        promoted = 0
        still_needs_review = 0
        for fam in (consolidated.get("families") or {}).values():
            for r in fam.get("results") or []:
                if r.get("outcome") == "needs_owner_review":
                    still_needs_review += 1
                elif (
                    "owner-verdict applied" in (r.get("notes") or "")
                ):
                    promoted += 1
        print(
            f"eval-harness: wrote "
            f"{os.path.relpath(consolidated_path, REPO)} "
            f"({promoted} verdict{'s' if promoted != 1 else ''} applied; "
            f"{still_needs_review} still needs_owner_review)",
            file=sys.stderr,
        )
        return 0

    # ── Normal run paths (unchanged) ──
    if args.family:
        family_result = run_family(args.family)
        print(json.dumps(
            family_result.to_dict(), indent=2,
            sort_keys=True, default=str,
        ))
        return 0

    result = run_all(run_id=args.run_id)
    if args.write:
        path = write_run_result(result)
        rel = os.path.relpath(path, REPO)
        print(f"eval-harness: wrote {rel}", end="\n")
    else:
        print(json.dumps(
            result.to_dict(), indent=2, sort_keys=True, default=str,
        ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
