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

def beta_belief(usable: int, n: int, *, prior_alpha: float = 1.0, prior_beta: float = 1.0,
                max_success: float = 0.4) -> tuple[float, float]:
    """Beta-Binomial belief about a (class,tool)'s USABLE-work-rate. Returns
    (posterior_mean, p_below) where p_below = P(work_rate <= max_success) under
    Beta(prior_alpha+usable, prior_beta+failures). Confidence EMERGES from consistency:
    a few mixed/thin observations stay near the prior (uncertain); only sustained
    consistency pushes p_below high. The prior is the 'how cautious' knob (HARDCODED in
    3b; 3c earns it)."""
    from scipy.stats import beta as _beta_dist   # lazy: heavy; only when a Beta flag is on
    a = prior_alpha + usable
    b = prior_beta + (n - usable)
    mean = a / (a + b)
    p_below = float(_beta_dist.cdf(max_success, a, b))
    return mean, p_below

@dataclass(frozen=True)
class BeliefComparison:
    request_class: str
    chosen_tool: str
    n: int
    usable: int
    n8_confidence: float
    n8_success_rate: float
    n8_would_veto: bool
    beta_mean: float
    beta_p_below: float
    beta_would_veto: bool

def compare_beliefs(store, *, min_observations: int = 3, n8_min_conf: float = 0.6,
                    max_success: float = 0.4, credence: float = 0.9,
                    prior_alpha: float = 1.0, prior_beta: float = 1.0
                    ) -> dict[tuple[str, str], BeliefComparison]:
    """Per (class,tool): the old n/8 verdict and the new Beta verdict, side by side.
    Pure shadow — computes both, decides nothing. n8 mirrors Slice 1's _prior_vetoes_reflex
    defaults (conf>=0.6, success<=0.4); beta vetoes when P(rate<=max_success) >= credence."""
    buckets: dict[tuple[str, str], list[str]] = {}
    for row in store.iter_rows_for_priors():
        key = (row["request_class_id"], row["chosen_tool"] or "")
        buckets.setdefault(key, []).append(row["outcome_quality"])
    out: dict[tuple[str, str], BeliefComparison] = {}
    for (cls, tool), outcomes in buckets.items():
        n = len(outcomes)
        usable = sum(1 for q in outcomes if q in _GOOD)
        rate = usable / n if n else 0.0
        n8_conf = _confidence(n) if n >= min_observations else 0.0
        n8_veto = bool(n8_conf >= n8_min_conf and rate <= max_success)
        mean, p_below = beta_belief(usable, n, prior_alpha=prior_alpha, prior_beta=prior_beta,
                                    max_success=max_success)
        beta_veto = bool(p_below >= credence)
        out[(cls, tool)] = BeliefComparison(cls, tool, n, usable, n8_conf, rate, n8_veto,
                                            mean, p_below, beta_veto)
    return out
