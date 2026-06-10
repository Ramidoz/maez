"""Offline valence thermometer reading types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping


class Sign(Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    MIXED = "mixed"
    NEUTRAL = "neutral"


class Magnitude(Enum):
    NONE = "none"
    MILD = "mild"
    MODERATE = "moderate"
    STRONG = "strong"


@dataclass(frozen=True)
class Contribution:
    setpoint: str
    sign: Sign
    reason: str
    evidence: Mapping[str, object]


@dataclass(frozen=True)
class ValenceReading:
    sign: Sign
    magnitude: Magnitude
    contributions: tuple[Contribution, ...]
    provenance: str = "computed_valence"

    def as_telemetry(self) -> str:
        label = f"{self.magnitude.name} {self.sign.name}"
        prefix = "given the substrate signals I can see, "
        if self.sign is Sign.NEUTRAL and self.magnitude is Magnitude.NONE:
            return f"{prefix}this state appears {label}; no setpoint moved."

        reasons = "; ".join(
            contribution.reason
            for contribution in self.contributions
            if contribution.sign is not Sign.NEUTRAL and contribution.reason
        )
        if reasons:
            return f"{prefix}this state appears {label}, because: {reasons}."
        return f"{prefix}this state appears {label}."


def aggregate(contributions: Iterable[Contribution]) -> ValenceReading:
    recorded = tuple(contributions)
    active = tuple(
        contribution
        for contribution in recorded
        if contribution.sign is not Sign.NEUTRAL
    )

    if not active:
        return ValenceReading(
            sign=Sign.NEUTRAL,
            magnitude=Magnitude.NONE,
            contributions=recorded,
        )

    signs = {contribution.sign for contribution in active}
    if Sign.POSITIVE in signs and Sign.NEGATIVE in signs:
        sign = Sign.MIXED
    elif len(signs) == 1:
        sign = active[0].sign
    else:
        sign = Sign.MIXED

    count = len(active)
    if count == 1:
        magnitude = Magnitude.MILD
    elif count == 2:
        magnitude = Magnitude.MODERATE
    else:
        magnitude = Magnitude.STRONG

    return ValenceReading(
        sign=sign,
        magnitude=magnitude,
        contributions=recorded,
    )
