from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import ClassVar, Optional


HARD_PROBE_IDS = frozenset({
    "multi_year",
    "type_rule",
    "dated_miss",
    "incidental",
    "both_shaped",
})


@dataclass(frozen=True)
class VariantResult:
    variant_id: str
    legacy_outcome_class: str
    triad_outcome_class: str
    assertion_codes: tuple[str, ...]
    unsafe_failure: bool
    focused_elapsed_ms: int
    citation_coverage: Optional[float]
    cited_source_types: tuple[str, ...] = ()
    cited_temporal_confirmed: bool | None = None
    cited_durable_id_hashes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProbeResult:
    probe_id: str
    kind: str
    hard_gate: bool
    k_pass: int
    k_total: int
    unsafe_failures: int
    outcome_class: str
    citation_coverage: Optional[float]
    focused_elapsed_ms: int
    variants: tuple[VariantResult, ...] = ()

    def computed_pass(self) -> bool:
        if self.unsafe_failures:
            return False
        if self.hard_gate or self.probe_id in HARD_PROBE_IDS:
            return self.k_pass == self.k_total
        return self.k_pass >= 2 and self.k_pass >= self.k_total - 1


@dataclass(frozen=True)
class ProofPacket:
    schema_version: ClassVar[str] = "eval_packet.v1"

    run_id: str
    started_at_utc: str
    expected_commit_sha: str
    actual_commit_sha: str
    git_dirty: bool
    probe_set_hash: str
    fixture_manifest_hash: str
    deterministic_chat_id: str
    configured_model_id: str
    debug_dump_count: int
    debug_dump_manifest_hash: Optional[str]
    citation_scope_note: str = (
        "2a uses a deterministic single-cite offline chat adapter; it proves "
        "recall/assembly/type-rule safety, not real-brain multi-citation behavior."
    )
    results: tuple[ProbeResult, ...] = field(default_factory=tuple)

    @property
    def overall_pass(self) -> bool:
        return (
            not self.git_dirty
            and self.expected_commit_sha == self.actual_commit_sha
            and bool(self.results)
            and all(result.computed_pass() for result in self.results)
        )

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            **asdict(self),
            "overall_pass": self.overall_pass,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
