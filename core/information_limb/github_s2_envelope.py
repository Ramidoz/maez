"""GitHub v1 canonical S2 envelope guard.

This module is deliberately offline: it performs no OAuth, no GitHub calls, and
no storage writes. Its job is to inherit Calendar v1's canonical S2 envelope
shape while source-scoping it to GitHub's single minimized repo-count fact.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.information_limb.calendar_s2_envelope import CANONICAL_S2_REQUIRED_FIELDS


SOURCE_KIND = "github.repo_count"
SCHEMA_VERSION = "github.s2.v1"

_FORBIDDEN_GITHUB_ALIASES = frozenset(
    {
        "consent_tier",
        "requested_flows",
        "granted_flows",
        "github_login",
        "github_user_id",
        "repo_names",
        "repositories",
    }
)

_CONNECTOR_FORBIDDEN_AUTHORITY_FIELDS = frozenset(
    {
        "decision2_consent_tier",
        "third_party_posture",
        "granted_flow_ids",
        "promotion_state",
        "promotion_eligibility_reason",
        "promotion_eligibility_provenance_handle",
        "promotion_record_id",
    }
)

_ALLOWED_CONFIDENCE = frozenset(
    {
        "provider_confirmed",
        "provider_partial",
        "redacted_safe",
        "stale_below_max",
        "unavailable",
    }
)

_ALLOWED_FACT_KEYS = frozenset({"repo_count", "count_field"})
_ALLOWED_COUNT_FIELDS = frozenset({"public_repos", "total"})


class GithubS2EnvelopeError(ValueError):
    """Raised when a GitHub record would violate the canonical S2 envelope."""


def validate_connector_github_payload(payload: Mapping[str, Any]) -> bool:
    """Reject connector records that try to stamp S2 authority fields."""

    forbidden = sorted(set(payload) & _CONNECTOR_FORBIDDEN_AUTHORITY_FIELDS)
    if forbidden:
        raise GithubS2EnvelopeError(f"connector authority fields are not accepted: {forbidden}")
    return True


def validate_github_s2_envelope(envelope: Mapping[str, Any]) -> bool:
    """Validate the canonical GitHub v1 S2 envelope shape."""

    aliases = sorted(set(envelope) & _FORBIDDEN_GITHUB_ALIASES)
    if aliases:
        raise GithubS2EnvelopeError(f"GitHub envelope alias fields rejected: {aliases}")

    missing = sorted(CANONICAL_S2_REQUIRED_FIELDS - set(envelope))
    if missing:
        raise GithubS2EnvelopeError(f"GitHub S2 envelope missing fields: {missing}")

    if envelope.get("schema_version") != SCHEMA_VERSION:
        raise GithubS2EnvelopeError("GitHub S2 envelope schema_version mismatch")
    if envelope.get("source_kind") != SOURCE_KIND:
        raise GithubS2EnvelopeError("GitHub S2 envelope source_kind mismatch")
    if envelope.get("confidence") not in _ALLOWED_CONFIDENCE:
        raise GithubS2EnvelopeError("GitHub S2 envelope confidence is not allowed")
    facts = envelope.get("facts")
    if not isinstance(facts, Mapping):
        raise GithubS2EnvelopeError("GitHub S2 envelope facts must be an object")
    _validate_count_fact(facts)
    if not isinstance(envelope.get("requested_flow_ids"), list):
        raise GithubS2EnvelopeError("GitHub S2 envelope requested_flow_ids must be a list")
    if not isinstance(envelope.get("granted_flow_ids"), list):
        raise GithubS2EnvelopeError("GitHub S2 envelope granted_flow_ids must be a list")
    if not isinstance(envelope.get("provenance"), Mapping):
        raise GithubS2EnvelopeError("GitHub S2 envelope provenance must be an object")
    return True


def _validate_count_fact(facts: Mapping[str, Any]) -> None:
    unknown = sorted(set(facts) - _ALLOWED_FACT_KEYS)
    if unknown:
        raise GithubS2EnvelopeError(f"GitHub S2 envelope facts contain raw fields: {unknown}")
    if not isinstance(facts.get("repo_count"), int):
        raise GithubS2EnvelopeError("GitHub S2 envelope repo_count must be an integer")
    if facts.get("repo_count", -1) < 0:
        raise GithubS2EnvelopeError("GitHub S2 envelope repo_count must be non-negative")
    if facts.get("count_field") not in _ALLOWED_COUNT_FIELDS:
        raise GithubS2EnvelopeError("GitHub S2 envelope count_field is not allowed")
