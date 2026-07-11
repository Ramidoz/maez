# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Frozen contracts for the dormant Vision Slice 7 exact-repeat gate."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Literal

import core.body.atspi_sensor as atspi_sensor


SCHEMA_VERSION = "vision_exact_repeat_gate.v1"
PRIOR_SCHEMA_VERSION = "vision_exact_repeat_prior.v1"

DIMENSIONS = (
    "active_crop_sha256",
    "atspi_projection_sha256",
    "geometry_sha256",
    "focus_capture_sha256",
    "comparison_mode",
)
COMPARISON_MODES = frozenset({"full", "crop_only"})
SOFT_ATSPI_REASONS = frozenset(
    {
        "atspi_unreachable",
        "atspi_protocol_invalid",
        "identity_scan_exceeded",
        "window_binding_unavailable",
        "window_binding_ambiguous",
        "bounds_unresolvable",
        "no_visible_nodes",
        "field_limit_exceeded",
    }
)
STATES = frozenset({"changed", "unchanged", "unavailable", "refused", "excluded"})
PRIOR_DISPOSITIONS = frozenset({"absent", "valid", "unavailable", "incompatible"})
OUTCOME_AUTHORITY = MappingProxyType(
    {
        "changed": (True, None),
        "unchanged": (False, "economy"),
        "unavailable": (True, None),
        "refused": (False, "no_authority"),
        "excluded": (False, "privacy"),
    }
)
NON_BLOCKED_REASONS = MappingProxyType(
    {
        "changed": frozenset({"first_observation", "signal_delta"}),
        "unchanged": frozenset({"exact_repeat"}),
        "unavailable": frozenset(
            {
                "timestamp_unavailable",
                "current_protocol_invalid",
                "digest_unavailable",
                "prior_unavailable",
                "prior_schema_incompatible",
            }
        ),
    }
)

ComparisonMode = Literal["full", "crop_only"]
EnvelopeState = Literal["available", "refused", "excluded"]
GateState = Literal["changed", "unchanged", "unavailable", "refused", "excluded"]
SuppressionClass = Literal["economy", "no_authority", "privacy"]


def _valid_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _valid_changed_dimensions(value: object) -> bool:
    if not isinstance(value, tuple):
        return False
    if value == ("first_observation",):
        return True
    if "first_observation" in value:
        return False
    return value == tuple(dimension for dimension in DIMENSIONS if dimension in value)


def _valid_blocked_fields(
    *, state: object, reason: object, source_lane: object, source_schema_version: object
) -> bool:
    if not isinstance(reason, str):
        return False
    if source_lane == "slice4":
        schema_version = atspi_sensor.SLICE4_SCHEMA_VERSION
        reasons = atspi_sensor.SLICE4_REFUSAL_REASONS
        excluded_reasons = reasons & atspi_sensor.EXCLUDED_REASONS
    elif source_lane == "slice5":
        schema_version = atspi_sensor.SCHEMA_VERSION
        reasons = atspi_sensor.REFUSAL_REASONS
        excluded_reasons = atspi_sensor.EXCLUDED_REASONS
    else:
        return False
    if source_schema_version != schema_version or reason not in reasons:
        return False
    expected_state = "excluded" if reason in excluded_reasons else "refused"
    return state == expected_state


@dataclass(frozen=True)
class ChangeTokens:
    active_crop_sha256: str = field(repr=False)
    geometry_sha256: str = field(repr=False)
    focus_capture_sha256: str = field(repr=False)
    comparison_mode: ComparisonMode
    atspi_projection_sha256: str | None = field(default=None, repr=False)
    degraded_reason: str | None = None

    def __post_init__(self) -> None:
        if not all(
            _valid_sha256(value)
            for value in (
                self.active_crop_sha256,
                self.geometry_sha256,
                self.focus_capture_sha256,
            )
        ):
            raise ValueError("comparison digests must be lowercase SHA-256 values")
        if self.comparison_mode not in COMPARISON_MODES:
            raise ValueError("unsupported comparison mode")
        if self.comparison_mode == "full":
            if not _valid_sha256(self.atspi_projection_sha256):
                raise ValueError("full comparison requires an AT-SPI digest")
            if self.degraded_reason is not None:
                raise ValueError("full comparison cannot be degraded")
            return
        if self.atspi_projection_sha256 is not None:
            raise ValueError("crop-only comparison forbids an AT-SPI digest")
        if self.degraded_reason not in SOFT_ATSPI_REASONS:
            raise ValueError("crop-only comparison requires a closed degradation reason")


@dataclass(frozen=True)
class CurrentEnvelope:
    state: EnvelopeState
    tokens: ChangeTokens | None = field(default=None, repr=False)
    reason: str = field(default="", repr=False)
    source_lane: str = ""
    source_schema_version: str = ""


@dataclass(frozen=True)
class GatePrior:
    tokens: ChangeTokens = field(repr=False)
    schema_version: str = PRIOR_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.tokens, ChangeTokens):
            raise ValueError("gate prior requires change tokens")
        if not isinstance(self.schema_version, str) or not self.schema_version:
            raise ValueError("gate prior requires a schema version")


@dataclass(frozen=True)
class GateDecision:
    state: GateState
    reading_warranted: bool
    suppression_class: SuppressionClass | None
    observed_at: datetime | None
    reason: str = field(default="", repr=False)
    comparison_mode: ComparisonMode | None = None
    changed_dimensions: tuple[str, ...] = ()
    candidate_prior: GatePrior | None = field(default=None, repr=False)
    upstream_lane: str = field(default="", repr=False)
    upstream_schema_version: str = field(default="", repr=False)
    prior_disposition: str = "absent"
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        expected = OUTCOME_AUTHORITY.get(self.state)
        timestamp_valid = _valid_observed_at(self.observed_at)
        candidate_valid = _valid_candidate_prior(
            self.candidate_prior, comparison_mode=self.comparison_mode
        )
        state_shape_valid = (
            self.state == "changed"
            and bool(self.changed_dimensions)
            and self.comparison_mode is not None
            and self.candidate_prior is not None
            and candidate_valid
            or self.state == "unchanged"
            and self.comparison_mode is not None
            and not self.changed_dimensions
            and self.candidate_prior is None
            or self.state in {"refused", "excluded"}
            and self.comparison_mode is None
            and not self.changed_dimensions
            and self.candidate_prior is None
            or self.state == "unavailable"
            and not self.changed_dimensions
            and (
                self.candidate_prior is None or self.comparison_mode is not None and candidate_valid
            )
        )
        blocked_fields_valid = _valid_blocked_fields(
            state=self.state,
            reason=self.reason,
            source_lane=self.upstream_lane,
            source_schema_version=self.upstream_schema_version,
        )
        non_blocked_reasons = (
            NON_BLOCKED_REASONS.get(self.state) if isinstance(self.state, str) else None
        )
        reason_and_source_valid = blocked_fields_valid or (
            non_blocked_reasons is not None
            and self.reason in non_blocked_reasons
            and self.upstream_lane == ""
            and self.upstream_schema_version == ""
        )
        reason_specific_shape_valid = (
            blocked_fields_valid
            or self.reason == "first_observation"
            and self.state == "changed"
            and self.changed_dimensions == ("first_observation",)
            and candidate_valid
            and self.comparison_mode is not None
            and self.prior_disposition == "absent"
            or self.reason == "signal_delta"
            and self.state == "changed"
            and bool(self.changed_dimensions)
            and "first_observation" not in self.changed_dimensions
            and candidate_valid
            and self.comparison_mode is not None
            and self.prior_disposition == "valid"
            or self.reason == "exact_repeat"
            and self.state == "unchanged"
            and not self.changed_dimensions
            and self.candidate_prior is None
            and self.comparison_mode is not None
            and self.prior_disposition == "valid"
            or self.reason == "timestamp_unavailable"
            and self.state == "unavailable"
            and self.observed_at is None
            and not self.changed_dimensions
            and self.candidate_prior is None
            and self.comparison_mode is None
            or self.reason in {"current_protocol_invalid", "digest_unavailable"}
            and self.state == "unavailable"
            and timestamp_valid
            and not self.changed_dimensions
            and self.candidate_prior is None
            and self.comparison_mode is None
            or self.reason == "prior_unavailable"
            and self.state == "unavailable"
            and timestamp_valid
            and not self.changed_dimensions
            and candidate_valid
            and self.comparison_mode is not None
            and self.prior_disposition == "unavailable"
            or self.reason == "prior_schema_incompatible"
            and self.state == "unavailable"
            and timestamp_valid
            and not self.changed_dimensions
            and candidate_valid
            and self.comparison_mode is not None
            and self.prior_disposition == "incompatible"
        )
        if (
            expected is None
            or self.reading_warranted is not expected[0]
            or self.suppression_class != expected[1]
            or self.schema_version != SCHEMA_VERSION
            or (
                self.observed_at is None
                and not (self.state == "unavailable" and self.reason == "timestamp_unavailable")
            )
            or (self.observed_at is not None and not timestamp_valid)
            or (self.comparison_mode is not None and self.comparison_mode not in COMPARISON_MODES)
            or not _valid_changed_dimensions(self.changed_dimensions)
            or (
                self.candidate_prior is not None and not isinstance(self.candidate_prior, GatePrior)
            )
            or self.prior_disposition not in PRIOR_DISPOSITIONS
            or not state_shape_valid
            or not reason_and_source_valid
            or not reason_specific_shape_valid
        ):
            raise ValueError("invalid gate decision")

    def to_receipt(self) -> dict[str, object]:
        """Project the decision into its content-light public receipt."""
        timestamp = (
            self.observed_at.astimezone(timezone.utc).isoformat()
            if self.observed_at is not None
            else None
        )
        compared_dimension_count = (
            5 if self.comparison_mode == "full" else 4 if self.comparison_mode == "crop_only" else 0
        )
        return {
            "schema_version": self.schema_version,
            "state": self.state,
            "timestamp": timestamp,
            "reading_warranted": self.reading_warranted,
            "suppression_class": self.suppression_class,
            "comparison_mode": self.comparison_mode,
            "degraded": self.comparison_mode == "crop_only",
            "changed_dimensions": list(self.changed_dimensions),
            "compared_dimension_count": compared_dimension_count,
            "reason": self.reason,
            "upstream_lane": self.upstream_lane,
            "upstream_schema_version": self.upstream_schema_version,
            "prior_disposition": self.prior_disposition,
        }


def _valid_change_tokens(value: object) -> bool:
    if not isinstance(value, ChangeTokens):
        return False
    try:
        if not all(
            _valid_sha256(digest)
            for digest in (
                value.active_crop_sha256,
                value.geometry_sha256,
                value.focus_capture_sha256,
            )
        ):
            return False
        if value.comparison_mode == "full":
            return _valid_sha256(value.atspi_projection_sha256) and value.degraded_reason is None
        return (
            value.comparison_mode == "crop_only"
            and value.atspi_projection_sha256 is None
            and value.degraded_reason in SOFT_ATSPI_REASONS
        )
    except (AttributeError, TypeError):
        return False


def _valid_observed_at(value: object) -> bool:
    if not isinstance(value, datetime):
        return False
    try:
        return value.tzinfo is not None and value.utcoffset() is not None
    except Exception:
        return False


def _valid_candidate_prior(value: object, *, comparison_mode: ComparisonMode | None) -> bool:
    return (
        isinstance(value, GatePrior)
        and value.schema_version == PRIOR_SCHEMA_VERSION
        and _valid_change_tokens(value.tokens)
        and value.tokens.comparison_mode == comparison_mode
    )


def _prior_disposition(value: object) -> str:
    if value is None:
        return "absent"
    if not isinstance(value, GatePrior):
        return "unavailable"
    if value.schema_version != PRIOR_SCHEMA_VERSION:
        return "incompatible"
    return "valid" if _valid_change_tokens(value.tokens) else "unavailable"


def _valid_blocked_envelope(value: CurrentEnvelope) -> bool:
    return value.tokens is None and _valid_blocked_fields(
        state=value.state,
        reason=value.reason,
        source_lane=value.source_lane,
        source_schema_version=value.source_schema_version,
    )


def evaluate(
    current: CurrentEnvelope,
    prior: GatePrior | None,
    *,
    observed_at: datetime | None = None,
) -> GateDecision:
    """Evaluate opaque comparison tokens without acquiring or retaining state."""
    prior_disposition = _prior_disposition(prior)
    if not _valid_observed_at(observed_at):
        return GateDecision(
            state="unavailable",
            reading_warranted=True,
            suppression_class=None,
            observed_at=None,
            reason="timestamp_unavailable",
            prior_disposition=prior_disposition,
        )

    if not isinstance(current, CurrentEnvelope):
        return GateDecision(
            state="unavailable",
            reading_warranted=True,
            suppression_class=None,
            observed_at=observed_at,
            reason="current_protocol_invalid",
            prior_disposition=prior_disposition,
        )

    if current.state in {"refused", "excluded"}:
        if not _valid_blocked_envelope(current):
            return GateDecision(
                state="unavailable",
                reading_warranted=True,
                suppression_class=None,
                observed_at=observed_at,
                reason="current_protocol_invalid",
                prior_disposition=prior_disposition,
            )
        reading_warranted, suppression_class = OUTCOME_AUTHORITY[current.state]
        return GateDecision(
            state=current.state,
            reading_warranted=reading_warranted,
            suppression_class=suppression_class,
            observed_at=observed_at,
            reason=current.reason,
            upstream_lane=current.source_lane,
            upstream_schema_version=current.source_schema_version,
            prior_disposition=prior_disposition,
        )

    if current.state != "available":
        return GateDecision(
            state="unavailable",
            reading_warranted=True,
            suppression_class=None,
            observed_at=observed_at,
            reason="current_protocol_invalid",
            prior_disposition=prior_disposition,
        )

    if current.reason != "" or current.source_lane != "" or current.source_schema_version != "":
        return GateDecision(
            state="unavailable",
            reading_warranted=True,
            suppression_class=None,
            observed_at=observed_at,
            reason="current_protocol_invalid",
            prior_disposition=prior_disposition,
        )

    if not _valid_change_tokens(current.tokens):
        return GateDecision(
            state="unavailable",
            reading_warranted=True,
            suppression_class=None,
            observed_at=observed_at,
            reason="digest_unavailable",
            prior_disposition=prior_disposition,
        )

    current_tokens = current.tokens
    candidate = GatePrior(tokens=current_tokens)
    if prior is None:
        return GateDecision(
            state="changed",
            reading_warranted=True,
            suppression_class=None,
            observed_at=observed_at,
            reason="first_observation",
            comparison_mode=current_tokens.comparison_mode,
            changed_dimensions=("first_observation",),
            candidate_prior=candidate,
            prior_disposition="absent",
        )
    if not isinstance(prior, GatePrior):
        return GateDecision(
            state="unavailable",
            reading_warranted=True,
            suppression_class=None,
            observed_at=observed_at,
            reason="prior_unavailable",
            comparison_mode=current_tokens.comparison_mode,
            candidate_prior=candidate,
            prior_disposition="unavailable",
        )
    if prior.schema_version != PRIOR_SCHEMA_VERSION:
        return GateDecision(
            state="unavailable",
            reading_warranted=True,
            suppression_class=None,
            observed_at=observed_at,
            reason="prior_schema_incompatible",
            comparison_mode=current_tokens.comparison_mode,
            candidate_prior=candidate,
            prior_disposition="incompatible",
        )
    if not _valid_change_tokens(prior.tokens):
        return GateDecision(
            state="unavailable",
            reading_warranted=True,
            suppression_class=None,
            observed_at=observed_at,
            reason="prior_unavailable",
            comparison_mode=current_tokens.comparison_mode,
            candidate_prior=candidate,
            prior_disposition="unavailable",
        )

    changed_dimensions = tuple(
        dimension
        for dimension in DIMENSIONS
        if getattr(current_tokens, dimension) != getattr(prior.tokens, dimension)
    )
    if changed_dimensions:
        return GateDecision(
            state="changed",
            reading_warranted=True,
            suppression_class=None,
            observed_at=observed_at,
            reason="signal_delta",
            comparison_mode=current_tokens.comparison_mode,
            changed_dimensions=changed_dimensions,
            candidate_prior=candidate,
            prior_disposition="valid",
        )
    return GateDecision(
        state="unchanged",
        reading_warranted=False,
        suppression_class="economy",
        observed_at=observed_at,
        reason="exact_repeat",
        comparison_mode=current_tokens.comparison_mode,
        prior_disposition="valid",
    )


def advance_prior(
    previous: GatePrior | None,
    decision: GateDecision,
    *,
    downstream_succeeded: bool,
) -> GatePrior | None:
    """Advance only after a successful downstream read; blocks clear the prior."""
    if previous is not None and not isinstance(previous, GatePrior):
        raise ValueError("previous prior must be a GatePrior or None")
    if not isinstance(decision, GateDecision):
        raise ValueError("decision must be a GateDecision")
    if type(downstream_succeeded) is not bool:
        raise ValueError("downstream_succeeded must be an exact bool")
    if decision.state in {"excluded", "refused"}:
        return None
    if downstream_succeeded is True and decision.candidate_prior is not None:
        return decision.candidate_prior
    return previous
