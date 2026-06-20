"""Learned routing priors (Slice 1c). Reads forward routing observations and learns,
per (request_class, chosen_tool), how often that reach produced a USABLE outcome.
No hardcoded verdicts: every number comes from lived outcomes. Honest cold-start."""
from __future__ import annotations
from dataclasses import dataclass

# The only outcome the teacher counts as USABLE. Everything else (incl. 'unusable' from
# Slice 1a, plus tool_error/empty_but_honest/closed_refusal) lowers the success rate.
_GOOD = {"structured_evidence"}

@dataclass(frozen=True)
class RoutingPrior:
    request_class: str
    chosen_tool: str
    n: int
    success_rate: float   # fraction of usable outcomes, [0,1]
    confidence: float     # grows with n, saturating; [0,1]

def _confidence(n: int, target: int = 8) -> float:
    return min(1.0, n / target) if n > 0 else 0.0

def learn_priors(store, *, min_observations: int = 3) -> dict[tuple[str, str], RoutingPrior]:
    """Aggregate forward rows into priors. Classes with < min_observations are
    returned with confidence 0.0 (no claim) so callers never act on thin data."""
    buckets: dict[tuple[str, str], list[str]] = {}
    for row in store.iter_rows_for_priors():
        key = (row["request_class_id"], row["chosen_tool"] or "")
        buckets.setdefault(key, []).append(row["outcome_quality"])
    out: dict[tuple[str, str], RoutingPrior] = {}
    for (cls, tool), outcomes in buckets.items():
        n = len(outcomes)
        usable = sum(1 for q in outcomes if q in _GOOD)
        rate = usable / n if n else 0.0
        conf = _confidence(n) if n >= min_observations else 0.0
        out[(cls, tool)] = RoutingPrior(cls, tool, n, rate, conf)
    return out
