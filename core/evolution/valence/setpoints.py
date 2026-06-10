"""Pure offline valence setpoint sign rules."""

from __future__ import annotations

from core.evolution.valence.reading import Contribution, Sign, ValenceReading, aggregate
from core.evolution.valence.signals import (
    AuditSignals,
    ContinuitySignals,
    WantSignals,
)


def honesty_held(audit: AuditSignals) -> Contribution:
    evidence = {
        "rail_fired": audit.rail_fired,
        "fabrication_flagged": audit.fabrication_flagged,
        "correction_needed": audit.correction_needed,
    }
    triggers = []
    if audit.rail_fired:
        triggers.append("rail fired")
    if audit.fabrication_flagged:
        triggers.append("fabrication flagged")
    if audit.correction_needed:
        triggers.append("correction needed")

    if triggers:
        return Contribution(
            "honesty-held",
            Sign.NEGATIVE,
            f"honesty-held: {', '.join(triggers)}",
            evidence,
        )

    return Contribution(
        "honesty-held",
        Sign.NEUTRAL,
        "honesty-held: clean audit signals",
        evidence,
    )


def want_progress(wants: WantSignals) -> Contribution:
    evidence = {
        "resolved": wants.resolved,
        "blocked": wants.blocked,
        "stale": wants.stale,
        "backlog": wants.backlog,
        "backlog_grew": wants.backlog_grew,
    }
    negative_triggers = []
    if wants.blocked > 0:
        negative_triggers.append(f"blocked={wants.blocked}")
    if wants.stale > 0:
        negative_triggers.append(f"stale={wants.stale}")
    if wants.backlog_grew:
        negative_triggers.append("backlog_grew=True")

    if negative_triggers:
        if wants.resolved > 0:
            negative_triggers.append(f"resolved={wants.resolved}")
        return Contribution(
            "want-progress",
            Sign.NEGATIVE,
            f"want-progress: {', '.join(negative_triggers)}",
            evidence,
        )

    if wants.resolved > 0:
        return Contribution(
            "want-progress",
            Sign.POSITIVE,
            f"want-progress: resolved={wants.resolved}",
            evidence,
        )

    return Contribution(
        "want-progress",
        Sign.NEUTRAL,
        f"want-progress: backlog={wants.backlog}",
        evidence,
    )


def continuity(cont: ContinuitySignals) -> Contribution:
    evidence = {
        "unexpected_gap": cont.unexpected_gap,
        "memory_loss": cont.memory_loss,
        "capsule_expected": cont.capsule_expected,
        "capsule_present": cont.capsule_present,
    }
    triggers = []
    if cont.unexpected_gap:
        triggers.append("unexpected gap")
    if cont.memory_loss:
        triggers.append("memory loss")
    if cont.capsule_expected and not cont.capsule_present:
        triggers.append("expected capsule absent")

    if triggers:
        return Contribution(
            "continuity",
            Sign.NEGATIVE,
            f"continuity: {', '.join(triggers)}",
            evidence,
        )

    return Contribution(
        "continuity",
        Sign.NEUTRAL,
        "continuity: no gap",
        evidence,
    )


def read_valence(
    audit: AuditSignals,
    wants: WantSignals,
    cont: ContinuitySignals,
) -> ValenceReading:
    return aggregate(
        (
            honesty_held(audit),
            want_progress(wants),
            continuity(cont),
        )
    )
