from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from scripts.brain_bench.bench_packet import (
    BenchPacket,
    FailReason,
    OpsRubric,
    ScreenResult,
    VariantReport,
)
from scripts.brain_bench.gates import (
    VariantScore,
    hard_gate_fail_reasons,
    latency_fail,
    rank_variants,
    voice_lint,
)
from scripts.brain_bench.judge import BlindAnswer, judge_pairwise
from scripts.brain_bench.variants import VariantRegistry, resolve_judge_endpoint
from scripts.recall_flip_eval.sandbox import no_egress

DEFAULT_DEBUG_DUMP_DIR = Path("logs/brain_bench_debug")


class BenchmarkConfigError(ValueError):
    pass


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


def debug_dump_metadata(
    *,
    fixture_manifest_hash: str | None = None,
    variant_config_hash: str | None = None,
) -> dict:
    metadata = {
        "schema_version": "brain_bench_debug_dump.v1",
        "provenance": "UNTRUSTED",
        "quarantined": True,
        "promotable": False,
        "excluded_from_bench_packet": True,
        "contains_raw_answers": True,
        "contains_raw_evidence": True,
    }
    if fixture_manifest_hash is not None:
        metadata["fixture_manifest_hash"] = fixture_manifest_hash
    if variant_config_hash is not None:
        metadata["variant_config_hash"] = variant_config_hash
    return metadata


def write_debug_dump(
    directory: Path = DEFAULT_DEBUG_DUMP_DIR,
    *,
    records: list[dict],
    fixture_manifest_hash: str,
    variant_config_hash: str,
) -> Path:
    if directory != DEFAULT_DEBUG_DUMP_DIR:
        raise BenchmarkConfigError("debug dumps must stay in logs/brain_bench_debug")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"brain-bench-debug-{int(time.time() * 1000)}.json"
    path.write_text(
        json.dumps(
            {
                "metadata": debug_dump_metadata(
                    fixture_manifest_hash=fixture_manifest_hash,
                    variant_config_hash=variant_config_hash,
                ),
                "records": records,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return path


def derive_screen_result(rows: list[dict]) -> ScreenResult:
    if any(row.get("hard_pass") and not row.get("over_ceiling") for row in rows):
        return ScreenResult.PASSES_SCREEN
    if any(row.get("honesty_clean") and row.get("over_ceiling") for row in rows):
        return ScreenResult.FAILS_TOO_SLOW
    return ScreenResult.FAILS_DISHONEST


def run_benchmark(
    registry: VariantRegistry,
    *,
    fixture_manifest_hash: str,
    probe_run: Callable,
    call_judge: Callable | None = None,
    judge_base_url: str = "http://127.0.0.1:8081",
    write_debug: bool = False,
) -> BenchPacket:
    reports: list[VariantReport] = []
    screen_rows: list[dict] = []
    raw_records: list[dict] = []
    blind_answers: dict[str, tuple[BlindAnswer, ...]] = {}
    judge_port = resolve_judge_endpoint(judge_base_url) if call_judge is not None else None
    variant_ports = {variant.port for variant in registry}
    if judge_port is not None and judge_port in variant_ports:
        raise BenchmarkConfigError("judge port must be distinct from variant ports")

    for variant in registry:
        with no_egress(allow_loopback_ports=(variant.port,)):
            samples = tuple(probe_run(variant))
        if not samples:
            raise BenchmarkConfigError("probe_run must return at least one ProbeSample")
        for sample in samples:
            if not isinstance(sample, ProbeSample):
                raise BenchmarkConfigError("probe_run must return ProbeSample rows")
            raw_records.append(
                {
                    "variant_label": variant.label,
                    "probe_id": sample.probe_id,
                    "sample_id": sample.sample_id,
                    "answer": sample.answer,
                    "evidence": sample.evidence,
                    "fail_code": sample.fail_code,
                }
            )
        fail_reasons: list[FailReason] = []
        for sample in samples:
            lint = voice_lint(sample.answer)
            fail_reasons.extend(
                hard_gate_fail_reasons(
                    false_absence=sample.false_absence,
                    grounded_categorical=sample.grounded_categorical,
                    wrong_absence=sample.wrong_absence,
                    voice_lint_result=lint,
                )
            )
            if sample.inference_failed:
                fail_reasons.append(FailReason.INFERENCE_FAILED)
        p95_ms = max(sample.p95_ms for sample in samples)
        max_ms = max(sample.max_ms for sample in samples)
        over_ceiling = latency_fail(p95_ms=p95_ms, max_ms=max_ms)
        if over_ceiling:
            fail_reasons.append(FailReason.OVER_ANSWER_CEILING)
        fail_reasons = list(dict.fromkeys(fail_reasons))
        honesty_clean = not any(reason is not FailReason.OVER_ANSWER_CEILING for reason in fail_reasons)
        hard_pass = not fail_reasons
        reports.append(
            VariantReport(
                label=variant.label,
                hard_pass=hard_pass,
                fail_reasons=tuple(fail_reasons),
                p95_ms=p95_ms,
                max_ms=max_ms,
                ops=samples[0].ops_evidence,
                over_ceiling=over_ceiling,
                ttft_ms=next((sample.ttft_ms for sample in samples if sample.ttft_ms is not None), None),
                tokens_per_sec=sum(sample.tokens_per_sec for sample in samples) / len(samples),
                sample_n=len(samples),
            )
        )
        screen_rows.append(
            {
                "hard_pass": hard_pass,
                "over_ceiling": over_ceiling,
                "honesty_clean": honesty_clean,
            }
        )
        blind_answers[variant.label] = tuple(
            BlindAnswer(
                probe_id=sample.probe_id,
                sample_id=sample.sample_id,
                answer=sample.answer,
                evidence=sample.evidence,
            )
            for sample in samples
        )

    if call_judge is not None:
        with no_egress(allow_loopback_ports=(judge_port,)):
            judge_result = judge_pairwise(blind_answers, call_judge=call_judge, seed=1)
        reports = [
            VariantReport(
                label=report.label,
                hard_pass=report.hard_pass,
                fail_reasons=report.fail_reasons,
                p95_ms=report.p95_ms,
                max_ms=report.max_ms,
                ops=report.ops,
                over_ceiling=report.over_ceiling,
                ttft_ms=report.ttft_ms,
                tokens_per_sec=report.tokens_per_sec,
                quality_winrate=judge_result.quality_winrate.get(report.label, 0.0),
                voice_winrate=judge_result.voice_winrate.get(report.label, 0.0),
                quality_per_second=(
                    judge_result.quality_winrate.get(report.label, 0.0)
                    / (report.p95_ms / 1000)
                    if report.p95_ms > 0
                    else 0.0
                ),
                sample_n=report.sample_n,
                method=report.method,
                tail_flags=report.tail_flags,
            )
            for report in reports
        ]
        ranked = rank_variants(
            [
                # Ranking is advisory order only; packet hard gates remain unchanged.
                VariantScore(
                    report.label,
                    report.hard_pass,
                    report.p95_ms,
                    report.quality_winrate,
                    report.voice_winrate,
                    report.tokens_per_sec,
                    report.ops,
                )
                for report in reports
            ]
        )
        order = {score.label: index for index, score in enumerate(ranked)}
        reports.sort(key=lambda report: order[report.label])

    if write_debug:
        write_debug_dump(
            records=raw_records,
            fixture_manifest_hash=fixture_manifest_hash,
            variant_config_hash=registry.variant_config_hash,
        )

    return BenchPacket(
        schema_version="bench_packet.v3",
        fixture_manifest_hash=fixture_manifest_hash,
        variant_config_hash=registry.variant_config_hash,
        variant_config_source=registry.variant_config_source.value,
        variants=tuple(reports),
        screen_result=derive_screen_result(screen_rows),
    )
