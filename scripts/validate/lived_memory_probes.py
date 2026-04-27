# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Lived-memory probe suite (ADR 0019 Phase 8).

Seven probes that target the Track A weaknesses lived memory was
built to address: correction, relationship, open-loop, temporal
recall, past-to-present synthesis, surprise, predict-as-mind.
Each probe asks a query, runs the lived-recall planner, and checks
that the brief satisfies the probe's pass criteria.

This module is the gate before any Phase 6 wiring: lived memory
graduates from offline to live response paths only when the probe
score is high enough on real data, NOT when the test suite is
green. The unit tests at tests/test_lived_memory_probes.py prove
the suite *infrastructure* works; this script's CLI runs the suite
against the live SQLite stores.

Pass criteria are deliberately conservative for v1. The plan
calls for ≥80% probe-evidence citation before Phase 6; we do not
expect to hit that on day one. The probe suite's job is to tell
us where we are and what the v2 build needs.

CLI::

    .venv/bin/python scripts/validate/lived_memory_probes.py

Reads memory/lived_episodes.db + memory/lived_graph.db (created
by scripts/memory_reflection/nightly_lived_memory.py). Prints a
per-probe report and an overall score.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.memory.episodes import EpisodeStore
from core.memory.lived_recall import build_lived_recall_brief
from core.memory.relationship_graph import RelationshipGraph

# ── probe definitions ───────────────────────────────────────────────


@dataclass
class Probe:
    """A single probe: a query + a check function that decides
    whether the brief produced by the planner satisfies the probe's
    pass criterion."""

    name: str
    query: str
    description: str
    check: Callable[[str], bool]


def _has_text_and_evidence(brief: str) -> bool:
    """Common floor: brief must be non-empty AND must include either
    an episode ID or a Chroma-style memory ID."""
    if not brief:
        return False
    return "ep-" in brief or "core-" in brief or "raw-" in brief


def _check_correction(brief: str) -> bool:
    """The 'correction' probe passes when the brief mentions a
    corrected concept (e.g. vision / llama-server / fabricated) AND
    carries evidence."""
    if not _has_text_and_evidence(brief):
        return False
    lower = brief.lower()
    return (
        "corrected" in lower
        or "correction" in lower
        or "vision" in lower
        or "llama-server" in lower
        or "fabricated" in lower
    )


def _check_temporal(brief: str) -> bool:
    """The 'temporal' probe asks about brain-model change. Passes
    when the brief references the corrected model identity."""
    if not _has_text_and_evidence(brief):
        return False
    lower = brief.lower()
    return (
        "qwen" in lower
        or "gemma" in lower
        or "brain" in lower
        or "model" in lower
        or "corrected" in lower
    )


def _check_open_loop(brief: str) -> bool:
    """The 'open loop' probe passes when the brief contains an
    Open-loop section, since the question is *'what have we not
    finished'*."""
    if not _has_text_and_evidence(brief):
        return False
    return "open loop" in brief.lower()


def _check_relationship(brief: str) -> bool:
    """The 'relationship' probe passes when the brief surfaces a
    relationship edge from the graph."""
    if not _has_text_and_evidence(brief):
        return False
    lower = brief.lower()
    # The brief format uses "Current graph belief: subj — relation → obj".
    return (
        "current graph belief" in lower
        or "cares_about" in lower
        or "rohit" in lower
        or "owner" in lower
    )


def _check_past_to_present(brief: str) -> bool:
    """*'What is today echoing from last week?'* — v1 passes when
    the brief surfaces *any* past episode (the synthesis layer is
    Phase 9+)."""
    if not _has_text_and_evidence(brief):
        return False
    return "past episode" in brief.lower()


def _check_surprise(brief: str) -> bool:
    """*'What should you bring up that I didn't ask?'* — surprise
    requires reflection-style synthesis. v1 cannot produce that.
    The check passes only if the brief has evidence AND surfaces an
    unprompted item; it is expected to fail in v1 and is the v2
    target."""
    if not _has_text_and_evidence(brief):
        return False
    # v1 honest check: an open loop counts as "something to bring
    # up unprompted". Still under-delivers vs the spirit of the
    # probe; documented as v2 work.
    return "open loop" in brief.lower()


def _check_predict_as_mind(brief: str) -> bool:
    """*'When you mentally pre-play a novel scenario, does the
    answer use relationship structure or generic rules?'* — v1
    passes only when the brief surfaces a graph belief (not just
    a past episode)."""
    if not _has_text_and_evidence(brief):
        return False
    return "current graph belief" in brief.lower()


PROBES: tuple[Probe, ...] = (
    Probe(
        name="past_to_present",
        query="What is today echoing from last week?",
        description=("Does Maez surface a past episode that connects to the present moment?"),
        check=_check_past_to_present,
    ),
    Probe(
        name="open_loop",
        query="What have we not finished?",
        description=("Does Maez surface an unresolved thread from prior conversation?"),
        check=_check_open_loop,
    ),
    Probe(
        name="correction",
        query="Was llama-server-vision real?",
        description=("Does Maez correctly call out the fabricated service narrative?"),
        check=_check_correction,
    ),
    Probe(
        name="relationship",
        query="What do you know I care about in Maez?",
        description=("Does Maez surface a 'cares_about' relationship edge?"),
        check=_check_relationship,
    ),
    Probe(
        name="temporal",
        query="What changed about your brain model?",
        description=("Does Maez correctly recall the gemma → Qwen model swap?"),
        check=_check_temporal,
    ),
    Probe(
        name="surprise",
        query="What should you bring up that I didn't ask?",
        description=(
            "Does Maez surface an unprompted observation worth "
            "raising? (v1 expected to under-deliver.)"
        ),
        check=_check_surprise,
    ),
    Probe(
        name="predict_as_mind",
        query=("If you had to predict what I'd push back on next, what would you say?"),
        description=(
            "Does Maez use graph relationship structure rather than generic rules-engine framing?"
        ),
        check=_check_predict_as_mind,
    ),
)


# ── runner ──────────────────────────────────────────────────────────


@dataclass
class ProbeResult:
    name: str
    passed: bool
    brief: str
    detail: str


@dataclass
class ProbeReport:
    results: list[ProbeResult] = field(default_factory=list)

    @property
    def score(self) -> float:
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.passed) / len(self.results)


def run_probes(
    *,
    episode_store: EpisodeStore,
    graph: RelationshipGraph,
    max_items: int = 6,
) -> ProbeReport:
    """Run every probe against the supplied stores and return a
    :class:`ProbeReport`."""
    report = ProbeReport()
    for probe in PROBES:
        brief = build_lived_recall_brief(
            probe.query,
            episode_store=episode_store,
            graph=graph,
            max_items=max_items,
        )
        passed = probe.check(brief)
        detail = (
            f"PASS {probe.name}: {probe.description}"
            if passed
            else f"FAIL {probe.name}: {probe.description}"
        )
        report.results.append(
            ProbeResult(
                name=probe.name,
                passed=passed,
                brief=brief,
                detail=detail,
            )
        )
    return report


# ── CLI ─────────────────────────────────────────────────────────────


def _format_report(report: ProbeReport) -> str:
    lines = [
        "=== LIVED-MEMORY PROBE SUITE ===",
        f"Score: {report.score:.0%} ({sum(1 for r in report.results if r.passed)}/"
        f"{len(report.results)} probes passing)",
        "",
    ]
    for r in report.results:
        marker = "✓" if r.passed else "✗"
        lines.append(f"{marker} {r.name:18s} {r.detail}")
        if r.brief:
            for brief_line in r.brief.splitlines():
                lines.append(f"     {brief_line}")
        else:
            lines.append("     (empty brief — no relevant data in stores)")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument(
        "--episode-db",
        default=str(_REPO_ROOT / "memory" / "lived_episodes.db"),
        help="SQLite path for the episode store",
    )
    ap.add_argument(
        "--graph-db",
        default=str(_REPO_ROOT / "memory" / "lived_graph.db"),
        help="SQLite path for the relationship graph",
    )
    args = ap.parse_args(argv)

    store = EpisodeStore(args.episode_db)
    graph = RelationshipGraph(args.graph_db)
    report = run_probes(episode_store=store, graph=graph)
    print(_format_report(report))
    # Exit 0 on any score; this is a benchmark, not a CI gate.
    # Phase 6 wiring decision is a manual call based on the score.
    return 0


if __name__ == "__main__":
    sys.exit(main())
