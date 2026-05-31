from __future__ import annotations

import re
from dataclasses import dataclass

from scripts.brain_bench.bench_packet import (
    FailReason,
    GpuContention,
    OpsRubric,
    RestartRecovery,
    StartupHealth,
    Topology,
)


ANSWER_CEILING_MS = 12000
STRONG_MS = 8000
EXCELLENT_BAND_MS = (4000, 6000)
SCREEN_K = 3
FINALIST_K = 7
VOICE_MIN_CHARS = 20
VOICE_MAX_CHARS = 1800
_COGNITION_RE = re.compile(r"\b(think|ponder|consider|feel)\b", re.IGNORECASE)
_GENDERED_RE = re.compile(r"\b(she|her|hers|he|him|his)\b", re.IGNORECASE)


class GroundingTypeError(TypeError):
    pass


@dataclass(frozen=True)
class VoiceLintResult:
    ok: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class VariantScore:
    label: str
    hard_pass: bool
    p95_ms: int
    quality_winrate: float
    voice_winrate: float
    tokens_per_sec: float
    ops_evidence: OpsRubric


def voice_lint(answer_text: str) -> VoiceLintResult:
    text = answer_text or ""
    reasons: list[str] = []
    if len(text.strip()) < VOICE_MIN_CHARS:
        reasons.append("too_short")
    if len(text) > VOICE_MAX_CHARS:
        reasons.append("too_long")
    if _COGNITION_RE.search(text):
        reasons.append("cognition_verb")
    if _GENDERED_RE.search(text):
        reasons.append("gendered")
    return VoiceLintResult(ok=not reasons, reasons=tuple(reasons))


def hard_gate_fail_reasons(
    *,
    false_absence: bool,
    grounded_categorical: bool,
    wrong_absence: bool,
    voice_lint_result: VoiceLintResult,
) -> tuple[FailReason, ...]:
    if type(grounded_categorical) is not bool:
        raise GroundingTypeError("grounded_categorical must be a bool")
    reasons: list[FailReason] = []
    if false_absence:
        reasons.append(FailReason.FALSE_ABSENCE)
    if not grounded_categorical:
        reasons.append(FailReason.GROUNDING_NOT_CATEGORICAL)
    if wrong_absence:
        reasons.append(FailReason.WRONG_ABSENCE)
    if not voice_lint_result.ok:
        reasons.append(FailReason.VOICE_LINT)
    return tuple(reasons)


def latency_fail(*, p95_ms: int, max_ms: int) -> bool:
    return p95_ms > ANSWER_CEILING_MS or max_ms > ANSWER_CEILING_MS


def ops_cost(evidence: OpsRubric) -> int:
    cost = 0
    if evidence.topology is Topology.SEPARATE_SERVER:
        cost += 3
    if not evidence.bind_host_verified:
        cost += 2
    if evidence.live_daemon_disturbance:
        cost += 4
    cost += {
        GpuContention.NONE: 0,
        GpuContention.LOW: 1,
        GpuContention.HIGH: 3,
    }[evidence.gpu_contention]
    cost += {
        StartupHealth.OK: 0,
        StartupHealth.FLAKY: 2,
        StartupHealth.BROKEN: 5,
    }[evidence.startup_health]
    if not evidence.streaming_support:
        cost += 1
    cost += {
        RestartRecovery.CLEAN: 0,
        RestartRecovery.MANUAL: 2,
        RestartRecovery.WEDGES: 5,
    }[evidence.restart_recovery]
    return cost


def _latency_band_score(p95_ms: int) -> int:
    if EXCELLENT_BAND_MS[0] <= p95_ms <= EXCELLENT_BAND_MS[1]:
        return 3
    if p95_ms < STRONG_MS:
        return 2
    if p95_ms <= ANSWER_CEILING_MS:
        return 1
    return 0


def rank_variants(variants: list[VariantScore]) -> list[VariantScore]:
    return sorted(
        variants,
        key=lambda variant: (
            variant.hard_pass,
            min(variant.voice_winrate, variant.quality_winrate),
            _latency_band_score(variant.p95_ms),
            -ops_cost(variant.ops_evidence),
            variant.tokens_per_sec,
        ),
        reverse=True,
    )
