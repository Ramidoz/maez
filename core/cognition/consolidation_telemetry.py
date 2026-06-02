from __future__ import annotations

import json


CONSOLIDATION_TELEMETRY_FIELDS = frozenset(
    {
        "organ",
        "inputs_count",
        "outputs_count",
        "model",
        "duration_ms",
        "rails_blocked",
        "status",
        "reason",
    }
)


def consolidation_telemetry_summary(
    *,
    organ: str,
    inputs_count: int,
    outputs_count: int,
    model: str,
    duration_ms: float | int,
    rails_blocked: int,
    status: str,
    reason: str,
) -> dict[str, object]:
    return {
        "organ": str(organ),
        "inputs_count": int(inputs_count),
        "outputs_count": int(outputs_count),
        "model": str(model or "unknown"),
        "duration_ms": int(round(float(duration_ms))),
        "rails_blocked": int(rails_blocked),
        "status": str(status),
        "reason": str(reason),
    }


def emit_consolidation_telemetry(logger, **kwargs) -> dict[str, object]:
    summary = consolidation_telemetry_summary(**kwargs)
    logger.info(
        "consolidation_telemetry summary=%s",
        json.dumps(summary, sort_keys=True),
    )
    return summary
