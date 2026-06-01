from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from core.routing import focused_cognition
from scripts.brain_bench.inference import GenerationMeasurement, make_benchmark_chat_fn
from scripts.brain_bench.samples import ProbeSample
from scripts.brain_bench.variants import Variant
from scripts.recall_flip_eval import harness, probes, sandbox


@dataclass
class ProbeRun:
    k: int
    stream_factory: Callable[..., Iterable[dict[str, str]]] | None = None
    clock: Callable[[], float] | None = None
    run_id: str = "brain-bench"
    probe_run_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    fixture_manifest: list[dict] = field(default_factory=list)

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
        probe_root = (
            root
            / "brain_bench_probe_sandboxes"
            / self.probe_run_id
            / variant.label
            / probe.probe_id
        )
        prior_patch_state = sandbox.memory_patch_snapshot()
        try:
            sandbox.assert_sandbox(root)
            with sandbox.sandbox_env(probe_root):
                sandbox.patch_memory_manager_base_db(probe_root)
                sandbox.assert_sandbox(probe_root)
                expected_fixture_ids, fixture_manifest = harness._seed_for_probe(
                    probe_root,
                    probe,
                    self.run_id,
                )
                self.fixture_manifest.extend(fixture_manifest)
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
            turn_kind=probes.probe_turn_kind(probe.probe_id),
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
                ops_evidence=variant.ops_evidence,
                latency_ms=measurement.total_ms,
                synthesized=True,
                expected_fixture_ids=expected_fixture_ids,
                available_label_map=result.available_label_map,
                citation_render_version=result.citation_render_version,
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
        focused_latency_ms = result.focused_elapsed_ms
        return ProbeSample(
            probe_id=probe.probe_id,
            sample_id=f"{probe.probe_id}-s{sample_index + 1}",
            answer=result.answer,
            evidence=evidence,
            false_absence=false_absence,
            grounded_categorical=grounded_categorical,
            wrong_absence=wrong_absence,
            p95_ms=focused_latency_ms,
            max_ms=focused_latency_ms,
            ttft_ms=measurement.ttft_ms if measurement is not None else None,
            tokens_per_sec=measurement.tokens_per_sec if measurement is not None else 0.0,
            ops_evidence=variant.ops_evidence,
            latency_ms=focused_latency_ms,
            synthesized=measurement is not None,
            cited_ids=result.cited_ids,
            cited_durable_ids=result.cited_durable_ids,
            expected_fixture_ids=expected_fixture_ids,
            cited_confirmed_memory_context=result.cited_confirmed_memory_context,
            available_label_map=result.available_label_map,
            citation_render_version=result.citation_render_version,
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
    turn_kind: str,
) -> tuple[harness.ProbeArmResult, GenerationMeasurement | None, str]:
    from core.brain import brain_loop
    from core.dispatcher.spec import SubstrateSource
    from core.routing.recall_outcome import (
        citation_support,
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
                    citation_render_version=focused_cognition._citation_render_version(),
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
                citation_render_version=focused_cognition._citation_render_version(),
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
                available_label_map=harness.citation_label_map(working_set),
                citation_render_version=working_set.citation_render_version,
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
    support = citation_support(result, working_set, turn_kind=turn_kind)
    outcome = classify_outcome(
        mode="recall_triad",
        turn_kind=turn_kind,
        answered=bool(result.reply),
        receipt="consulted",
        denial_kind="none",
        had_confirmed=had_confirmed,
        cited_grounded_context=(support == "grounded"),
        unmatched_citations=len(verdict.unmatched),
        cited_mixed_support=support == "mixed",
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
            cited_ids=tuple(result.cited_ids),
            cited_durable_ids=durable_ids,
            cited_confirmed_memory_context=grounded,
            working_set_source_types=tuple(item.source_type for item in working_set.items),
            available_label_map=harness.citation_label_map(working_set),
            citation_render_version=working_set.citation_render_version,
        ),
        measurement,
        evidence,
    )
