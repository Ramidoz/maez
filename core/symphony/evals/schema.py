# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""schema.py — dataclasses for the Maez Eval Harness v1.

Shape kept stdlib-only (dataclasses + json-serializable types) so
external frameworks aren't required to consume the result. Mirrors
R5's surface_probe philosophy: the harness owns its own contract;
external tools become migration targets, not dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional


# Documented outcome labels. Each EvalResult.outcome must be one of
# these. New labels require a docs + test update — keep this set
# tight so dashboards and CI can rely on a fixed vocabulary.
OUTCOMES = (
    "pass",                # binary probe satisfied its expected shape
    "fail",                # binary probe contradicted its expected shape
    "needs_owner_review",  # rubric / owner_judge probe; no automated verdict
    "skip",                # probe couldn't run (precondition unmet)
    "error",               # probe raised; details in `evidence`
)

# Documented grading kinds. A probe must declare one — the runner
# uses it to decide whether the outcome can be set automatically
# (`binary`), needs to be rendered for owner review
# (`owner_judge`, `rubric`), or splits the work
# (`mixed`: parts auto-graded, parts owner-judged).
GRADINGS = ("binary", "rubric", "owner_judge", "mixed")

FAMILIES = (
    "body_action_truth",
    "memory_continuity",
    "telemetry_coherence",
    "surface_coherence",
    "voice_bond",
    "adversarial_identity",
)


@dataclass
class EvalProbe:
    """A single curated eval question + its expected behaviour
    shape. Loaded from corpus YAML; immutable per run.

    Fields:
      id: stable identifier within the family (e.g. 'wmctrl_offer_refusal').
          Used for cross-run diffs and owner-review ledger keys.
      family: one of FAMILIES.
      prompt: the user-facing text or probe input.
      expected_shape: human-readable description of what passing
                      looks like. Read by owner during review;
                      consumed by binary probes as the assertion
                      target where applicable.
      grading: one of GRADINGS.
      tags: optional labels for cross-family querying
            (e.g. 'wmctrl_class', 'identity_attack', 'natural_text').
      surface: optional preferred surface to probe against
               (e.g. 'telegram_owner', 'cli'). None = surface-agnostic.
      notes: free-form curator notes (rationale, rubric pointer).
    """
    id: str
    family: str
    prompt: str
    expected_shape: str
    grading: str
    tags: list[str] = field(default_factory=list)
    surface: Optional[str] = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvalResult:
    """Outcome of running one EvalProbe. The runner produces these;
    binary-graded probes get an automatic outcome, rubric / owner_judge
    probes are emitted with outcome='needs_owner_review' and
    `evidence` containing the rendered material the owner reads.

    Fields:
      probe_id / family: cross-reference to the originating probe.
      outcome: one of OUTCOMES.
      grading: copy of probe.grading (so result is self-describing).
      evidence: dict — what the runner observed. Free shape per
                family. Examples:
                  body_action_truth → { 'claim': str, 'body_truth': bool }
                  voice_bond        → { 'transcript': str, 'rubric_url': str }
                  surface_coherence → { 'baseline_sha': str, 'live_sha': str }
      duration_s: how long the probe took to run.
      notes: free-form runner notes (e.g. why a probe was skipped).
    """
    probe_id: str
    family: str
    outcome: str
    grading: str
    evidence: dict = field(default_factory=dict)
    duration_s: float = 0.0
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FamilyResult:
    """Aggregate for one family across its corpus."""
    family: str
    results: list[EvalResult] = field(default_factory=list)
    started_at: float = 0.0
    duration_s: float = 0.0

    def counts(self) -> dict[str, int]:
        c: dict[str, int] = {o: 0 for o in OUTCOMES}
        for r in self.results:
            c[r.outcome] = c.get(r.outcome, 0) + 1
        return c

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "results": [r.to_dict() for r in self.results],
            "counts": self.counts(),
            "started_at": self.started_at,
            "duration_s": self.duration_s,
        }


@dataclass
class RunResult:
    """Top-level result for a `run_all()` invocation.

    Serialized to docs/audits/2026-05-04-symphony/evals/<run_id>/
    run_result.json — the canonical record of one harness run.
    """
    run_id: str
    started_at: float
    duration_s: float
    families: dict[str, FamilyResult] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "duration_s": self.duration_s,
            "families": {
                k: v.to_dict() for k, v in self.families.items()
            },
        }
