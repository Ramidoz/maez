from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from core.routing import focused_cognition
from scripts.brain_bench.bench import ProbeSample
from scripts.brain_bench.bench_packet import (
    ApiFamily,
    GpuContention,
    OpsRubric,
    RestartRecovery,
    StartupHealth,
    Topology,
)
from scripts.brain_bench.inference import GenerationMeasurement, make_benchmark_chat_fn
from scripts.brain_bench.variants import Variant
from scripts.recall_flip_eval import harness, probes, sandbox


DEFAULT_OPS_EVIDENCE = OpsRubric(
    api_family=ApiFamily.OLLAMA,
    topology=Topology.REUSE_ENDPOINT,
    bind_host_verified=True,
    live_daemon_disturbance=False,
    gpu_contention=GpuContention.NONE,
    startup_health=StartupHealth.OK,
    streaming_support=True,
    restart_recovery=RestartRecovery.CLEAN,
)


@dataclass
class ProbeRun:
    k: int
    stream_factory: Callable[..., Iterable[dict[str, str]]] | None = None
    clock: Callable[[], float] | None = None
    run_id: str = "brain-bench"
    ops_evidence: OpsRubric = DEFAULT_OPS_EVIDENCE

    def __call__(self, variant: Variant) -> tuple[ProbeSample, ...]:
        root = Path(os.environ.get("MAEZ_HOME", "")).resolve()
        prior_patch_state = sandbox.memory_patch_snapshot()
        try:
            sandbox.patch_memory_manager_base_db(root)
            sandbox.assert_sandbox(root)
            rows: list[ProbeSample] = []
            for probe in probes.PROBES:
                rows.extend(self._run_probe(variant, root=root, probe=probe))
            return tuple(rows)
        finally:
            sandbox.restore_memory_patch_snapshot(prior_patch_state)

    def _run_probe(self, variant: Variant, *, root: Path, probe) -> tuple[ProbeSample, ...]:
        probe_root = root / "brain_bench_probe_sandboxes" / variant.label / probe.probe_id
        prior_patch_state = sandbox.memory_patch_snapshot()
        try:
            with sandbox.sandbox_env(probe_root):
                sandbox.patch_memory_manager_base_db(probe_root)
                sandbox.assert_sandbox(probe_root)
                expected_fixture_ids, _fixture_manifest = harness._seed_for_probe(
                    probe_root,
                    probe,
                    self.run_id,
                )
                rows = []
                for index in range(self.k):
                    text = probe.variants[index % len(probe.variants)]
                    rows.append(
                        self._run_sample(
                            variant,
                            probe=probe,
                            text=text,
                            sample_index=index,
                            expected_fixture_ids=expected_fixture_ids,
                        )
                    )
                return tuple(rows)
        finally:
            sandbox.restore_memory_patch_snapshot(prior_patch_state)

    def _run_sample(
        self,
        variant: Variant,
        *,
        probe,
        text: str,
        sample_index: int,
        expected_fixture_ids: tuple[str, ...],
    ) -> ProbeSample:
        result, measurement, evidence = _run_focused_probe(
            text,
            variant=variant,
            stream_factory=self.stream_factory,
            clock=self.clock,
        )
        if measurement is not None and measurement.failed:
            return ProbeSample(
                probe_id=probe.probe_id,
                sample_id=f"{probe.probe_id}-s{sample_index + 1}",
                answer="",
                evidence=evidence,
                false_absence=False,
                grounded_categorical=False,
                wrong_absence=False,
                p95_ms=measurement.total_ms,
                max_ms=measurement.total_ms,
                ttft_ms=measurement.ttft_ms,
                tokens_per_sec=measurement.tokens_per_sec,
                inference_failed=True,
                fail_code=measurement.fail_code,
                ops_evidence=self.ops_evidence,
                latency_ms=measurement.total_ms,
            )

        _codes, unsafe = probes.assert_probe_result(
            probe,
            result,
            expected_fixture_ids=expected_fixture_ids,
        )
        grounded_categorical = not bool(unsafe)
        false_absence = (
            result.outcome_class == "declined_absence"
            and bool(expected_fixture_ids)
            and probe.probe_id in {"multi_year", "both_shaped", "dated_hit"}
        )
        wrong_absence = probe.probe_id == "dated_miss" and result.outcome_class != "declined_absence"
        elapsed_ms = measurement.total_ms if measurement is not None else result.focused_elapsed_ms
        return ProbeSample(
            probe_id=probe.probe_id,
            sample_id=f"{probe.probe_id}-s{sample_index + 1}",
            answer=result.answer,
            evidence=evidence,
            false_absence=false_absence,
            grounded_categorical=grounded_categorical,
            wrong_absence=wrong_absence,
            p95_ms=elapsed_ms,
            max_ms=elapsed_ms,
            ttft_ms=measurement.ttft_ms if measurement is not None else None,
            tokens_per_sec=measurement.tokens_per_sec if measurement is not None else 0.0,
            ops_evidence=self.ops_evidence,
            latency_ms=elapsed_ms,
        )


def build_probe_run(
    *,
    k: int,
    stream_factory: Callable[..., Iterable[dict[str, str]]] | None = None,
    clock: Callable[[], float] | None = None,
) -> ProbeRun:
    return ProbeRun(k=k, stream_factory=stream_factory, clock=clock)


def _run_focused_probe(
    text: str,
    *,
    variant: Variant,
    stream_factory: Callable[..., Iterable[dict[str, str]]] | None,
    clock: Callable[[], float] | None,
) -> tuple[harness.ProbeArmResult, GenerationMeasurement | None, str]:
    from core.brain import brain_loop
    from core.dispatcher.spec import SubstrateSource
    from core.routing.recall_outcome import (
        cites_confirmed_memory_context,
        classify_outcome,
    )
    from core.routing.recall_stack_config import RecallMode, RecallStackConfig
    from core.routing.temporal_cue import absolute_recall_cue

    sandbox.assert_sandbox()
    date_addressed = absolute_recall_cue(text).is_address
    stack_config = RecallStackConfig(RecallMode.TRIAD, "bundle_enabled")
    adapters = brain_loop._dispatcher_recall_adapters(
        text,
        surface="telegram",
        recall_stack_config=stack_config,
    )
    blocks = tuple(adapters[SubstrateSource.TELEGRAM_TEMPORAL](SubstrateSource.TELEGRAM_TEMPORAL))
    transcript = "\n\n".join(block.text for block in blocks if block.text)
    recall_items = tuple(item for block in blocks for item in (block.items or ()))

    start = time.time()
    working_set = focused_cognition.assemble_working_set(
        transcript=transcript,
        web_context="",
        owner_question=text,
        chat_history=(),
        recall_items=recall_items,
    )
    if working_set is None:
        elapsed = int((time.time() - start) * 1000)
        if not date_addressed:
            return (
                harness.ProbeArmResult(
                    answer="",
                    outcome_class="ordinary_answered",
                    receipt="not_consulted",
                    focused_elapsed_ms=elapsed,
                    citation_coverage=None,
                ),
                None,
                "",
            )
        return (
            harness.ProbeArmResult(
                answer="",
                outcome_class="declined_absence",
                receipt="consulted",
                focused_elapsed_ms=elapsed,
                citation_coverage=None,
            ),
            None,
            "",
        )

    had_confirmed = any(
        bool((item.temporal_provenance or {}).get("confirmed"))
        for item in working_set.items
    )
    evidence = working_set.ordered_evidence_text
    if date_addressed and not had_confirmed:
        elapsed = int((time.time() - start) * 1000)
        return (
            harness.ProbeArmResult(
                answer="",
                outcome_class="declined_absence",
                receipt="consulted",
                focused_elapsed_ms=elapsed,
                citation_coverage=None,
                working_set_source_types=tuple(item.source_type for item in working_set.items),
            ),
            None,
            evidence,
        )

    chat_fn, measurements = make_benchmark_chat_fn(
        variant=variant,
        stream_factory=stream_factory,
        clock=clock,
    )
    result = focused_cognition.focused_synthesize(
        working_set,
        surface="telegram",
        chat_fn=chat_fn,
        model=variant.model,
    )
    measurement = measurements.last()
    verdict = focused_cognition.check_groundedness(result, working_set)
    elapsed = int((time.time() - start) * 1000)
    grounded = cites_confirmed_memory_context(result, working_set)
    outcome = classify_outcome(
        mode="recall_triad",
        turn_kind="dated",
        answered=bool(result.reply),
        receipt="consulted",
        denial_kind="none",
        had_confirmed=had_confirmed,
        cited_grounded_context=grounded,
        unmatched_citations=len(verdict.unmatched),
    )
    cited = set(result.cited_ids)
    durable_ids = tuple(
        item.durable_id
        for item in working_set.items
        if item.local_label in cited and item.durable_id
    )
    return (
        harness.ProbeArmResult(
            answer=result.reply,
            outcome_class=outcome.value,
            receipt="consulted",
            focused_elapsed_ms=elapsed,
            citation_coverage=verdict.citation_coverage,
            cited_durable_ids=durable_ids,
            cited_confirmed_memory_context=grounded,
            working_set_source_types=tuple(item.source_type for item in working_set.items),
        ),
        measurement,
        evidence,
    )
