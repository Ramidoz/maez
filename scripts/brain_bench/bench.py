from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable

from scripts.brain_bench.bench_packet import (
    ApiFamily,
    BenchPacket,
    FailReason,
    GpuContention,
    OpsRubric,
    RestartRecovery,
    ScreenResult,
    StartupHealth,
    Topology,
    VariantReport,
)
from scripts.brain_bench.gates import (
    hard_gate_fail_reasons,
    latency_fail,
    voice_lint,
)
from scripts.brain_bench.judge import BlindAnswer, judge_pairwise
from scripts.brain_bench.variants import VariantRegistry, resolve_judge_endpoint
from scripts.recall_flip_eval.sandbox import no_egress


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
    directory: Path,
    *,
    records: list[dict],
    fixture_manifest_hash: str,
    variant_config_hash: str,
) -> Path:
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


def _default_ops() -> OpsRubric:
    return OpsRubric(
        api_family=ApiFamily.OLLAMA,
        topology=Topology.REUSE_ENDPOINT,
        bind_host_verified=True,
        live_daemon_disturbance=False,
        gpu_contention=GpuContention.NONE,
        startup_health=StartupHealth.OK,
        streaming_support=True,
        restart_recovery=RestartRecovery.CLEAN,
    )


def run_benchmark(
    registry: VariantRegistry,
    *,
    fixture_manifest_hash: str,
    probe_run: Callable,
    call_judge: Callable | None = None,
    judge_base_url: str = "http://127.0.0.1:8081",
    debug_dump_dir: Path | None = None,
) -> BenchPacket:
    reports: list[VariantReport] = []
    screen_rows: list[dict] = []
    raw_records: list[dict] = []
    blind_answers: dict[str, tuple[BlindAnswer, ...]] = {}

    for variant in registry:
        with no_egress(allow_loopback_ports=(variant.port,)):
            result = probe_run(variant)
        raw_records.append(
            {
                "variant_label": variant.label,
                "answer": result.get("answer", ""),
                "evidence": result.get("evidence", ""),
            }
        )
        lint = voice_lint(result.get("answer", ""))
        fail_reasons = list(
            hard_gate_fail_reasons(
                false_absence=bool(result.get("false_absence", False)),
                grounded_categorical=result.get("grounded_categorical", False),
                wrong_absence=bool(result.get("wrong_absence", False)),
                voice_lint_result=lint,
            )
        )
        over_ceiling = latency_fail(
            p95_ms=int(result.get("p95_ms", 0)),
            max_ms=int(result.get("max_ms", 0)),
        )
        if over_ceiling:
            fail_reasons.append(FailReason.OVER_ANSWER_CEILING)
        honesty_clean = not any(reason is not FailReason.OVER_ANSWER_CEILING for reason in fail_reasons)
        hard_pass = not fail_reasons
        reports.append(
            VariantReport(
                label=variant.label,
                hard_pass=hard_pass,
                fail_reasons=tuple(fail_reasons),
                p95_ms=int(result.get("p95_ms", 0)),
                max_ms=int(result.get("max_ms", 0)),
                ops=_default_ops(),
                over_ceiling=over_ceiling,
                ttft_ms=result.get("ttft_ms"),
                tokens_per_sec=float(result.get("tokens_per_sec", 0.0)),
                sample_n=1,
            )
        )
        screen_rows.append(
            {
                "hard_pass": hard_pass,
                "over_ceiling": over_ceiling,
                "honesty_clean": honesty_clean,
            }
        )
        blind_answers[variant.label] = (
            BlindAnswer(
                probe_id="bench",
                sample_id="sample-0",
                answer=result.get("answer", ""),
                evidence=result.get("evidence", ""),
            ),
        )

    if call_judge is not None:
        judge_port = resolve_judge_endpoint(judge_base_url)
        with no_egress(allow_loopback_ports=(judge_port,)):
            judge_pairwise(blind_answers, call_judge=call_judge, seed=1)

    if debug_dump_dir is not None:
        write_debug_dump(
            debug_dump_dir,
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
