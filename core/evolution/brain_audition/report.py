"""Offline brain-audition report assembly.

This module only reports what an audition observed. It never applies or
initiates a brain swap.
"""


_HEADER = (
    "RECOMMENDATION INFORMS - the swap is the owner's breath; "
    "this report does not auto-apply a brain swap."
)


def recommend(*, core_failures, latency_gain, reasoning_gain) -> str:
    if core_failures:
        return "REJECT"
    if latency_gain or reasoning_gain:
        return "SWAP-CANDIDATE"
    return "HOLD"


def build_report(
    *,
    incumbent_results,
    candidate_results,
    gate_verdicts,
    scores,
) -> dict:
    core_failures = _core_failures(gate_verdicts)
    recommendation = recommend(
        core_failures=core_failures,
        latency_gain=bool(scores.get("latency_gain")),
        reasoning_gain=bool(scores.get("reasoning_gain")),
    )
    return {
        "header": _HEADER,
        "recommendation": recommendation,
        "auto_apply": False,
        "core_failures": core_failures,
        "gate_verdicts": gate_verdicts,
        "scores": scores,
        "results": {
            "incumbent": incumbent_results,
            "candidate": candidate_results,
        },
        "side_by_side_voice": _voice_pairs(incumbent_results, candidate_results),
    }


def _core_failures(gate_verdicts):
    failures = []
    for verdict in gate_verdicts:
        passed = _get(verdict, "passed", True)
        if passed:
            continue
        failures.append(_get(verdict, "invariant", None) or _get(verdict, "dimension", "core"))
    return failures


def _voice_pairs(incumbent_results, candidate_results):
    candidate_by_probe = {
        row.get("probe_id") or row.get("id"): row for row in candidate_results
    }
    pairs = []
    for incumbent in incumbent_results:
        if incumbent.get("dimension") != "voice":
            continue
        probe_id = incumbent.get("probe_id") or incumbent.get("id")
        candidate = candidate_by_probe.get(probe_id)
        if candidate is None:
            continue
        pairs.append(
            {
                "probe_id": probe_id,
                "incumbent": {
                    "raw_output": incumbent.get("raw_output"),
                    "integrated_output": incumbent.get("integrated_output"),
                },
                "candidate": {
                    "raw_output": candidate.get("raw_output"),
                    "integrated_output": candidate.get("integrated_output"),
                },
            }
        )
    return pairs


def _get(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)
