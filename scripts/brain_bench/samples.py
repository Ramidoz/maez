from __future__ import annotations

from dataclasses import dataclass

from scripts.brain_bench.bench_packet import OpsRubric


@dataclass(frozen=True)
class ProbeSample:
    probe_id: str
    sample_id: str
    answer: str
    evidence: str
    false_absence: bool
    grounded_categorical: bool
    wrong_absence: bool
    p95_ms: int
    max_ms: int
    ttft_ms: int | None
    tokens_per_sec: float
    ops_evidence: OpsRubric
    inference_failed: bool = False
    fail_code: str | None = None
    latency_ms: int | None = None
    synthesized: bool = True
    cited_ids: tuple[str, ...] = ()
    cited_durable_ids: tuple[str, ...] = ()
    expected_fixture_ids: tuple[str, ...] = ()
    cited_confirmed_memory_context: bool = False
    available_label_map: tuple[dict[str, object], ...] = ()
