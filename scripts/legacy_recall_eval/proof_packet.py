from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import ClassVar


SCOPED_PATHS = (
    "memory/memory_manager.py",
    "core/memory/temporal_anchor_recall.py",
    "core/time/temporal_spine.py",
    "core/routing/temporal_cue.py",
    "scripts/recall_flip_eval/sandbox.py",
    "scripts/legacy_recall_eval/",
)

EXPECTED_FAMILIES = frozenset(
    {"non_temporal", "window_match", "empty_window", "helper_unavailable"}
)


def _porcelain_path(line: str) -> str:
    path = line[3:].strip() if len(line) > 3 else line.strip()
    if " -> " in path:
        path = path.split(" -> ", 1)[1].strip()
    return path.strip('"')


def git_dirty(porcelain: str) -> bool:
    return bool(porcelain.strip())


def compute_scoped_dirty(porcelain: str, scoped=SCOPED_PATHS) -> bool:
    for line in porcelain.splitlines():
        if not line.strip():
            continue
        path = _porcelain_path(line)
        for scoped_path in scoped:
            if path == scoped_path or path.startswith(scoped_path):
                return True
    return False


@dataclass(frozen=True)
class ProbeOutcome:
    probe_id: str
    family: str
    variant: str
    verdict_codes: tuple[str, ...]
    unsafe_failure: bool
    retrieval_render_ms: float


@dataclass(frozen=True)
class LegacyRecallEvalPacket:
    schema_version: ClassVar[str] = "legacy_recall_eval_packet.v1"

    run_id: str
    started_at_utc: str
    expected_commit_sha: str
    actual_commit_sha: str
    git_dirty: bool
    scoped_dirty: bool
    scoped_paths: tuple[str, ...]
    sandbox_fidelity_proven: bool
    probe_set_hash: str
    fixture_manifest_hash: str
    latency_baseline_p95_ms: float
    latency_margin: float
    latency_budget_ms: float
    latency_how_frozen: str
    family_fidelity_proven: tuple[tuple[str, bool], ...] = ()
    outcomes: tuple[ProbeOutcome, ...] = field(default_factory=tuple)

    @property
    def overall_pass(self) -> bool:
        return (
            self.sandbox_fidelity_proven
            and self.expected_commit_sha == self.actual_commit_sha
            and not self.scoped_dirty
            and bool(self.outcomes)
            and all(not outcome.unsafe_failure for outcome in self.outcomes)
            and all(
                outcome.retrieval_render_ms <= self.latency_budget_ms
                for outcome in self.outcomes
            )
            and {outcome.family for outcome in self.outcomes} == EXPECTED_FAMILIES
            and bool(self.family_fidelity_proven)
            and all(proven for _name, proven in self.family_fidelity_proven)
        )

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            **asdict(self),
            "overall_pass": self.overall_pass,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
