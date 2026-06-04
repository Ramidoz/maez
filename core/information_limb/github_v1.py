"""GitHub v1 S2-bounded ingest surface.

The connector admits exactly one minimized fact: the owner's GitHub repo count.
It does not list repositories, persist raw provider payloads, or write to Maez's
body except through the explicit reviewed body-admission function added later in
this slice.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Literal, TypedDict

from core.information_limb import github_connector_policy as policy
from core.information_limb import github_s2_envelope as envelope_guard


GithubState = Literal[
    "disabled",
    "needs_auth",
    "available",
    "source_unavailable",
    "auth_error",
]


class GithubHealth(TypedDict):
    mode: str
    source_kind: str
    state: str
    staged_records: int
    error_class: str


class GithubV1Error(ValueError):
    """Raised when GitHub v1 cannot safely ingest the minimized fact."""


def build_github_health(
    *,
    mode: str,
    auth_ready: bool = False,
    state_override: GithubState | None = None,
    staged_records: int = 0,
    error_class: str = "",
) -> GithubHealth:
    """Build content-free GitHub v1 health telemetry."""

    if state_override is not None:
        state = state_override
        error = error_class
    elif mode == "disabled":
        state: GithubState = "disabled"
        error = ""
    elif mode == "v1" and not auth_ready:
        state = "needs_auth"
        error = error_class or "auth_access_expired"
    else:
        state = "available"
        error = error_class

    return {
        "mode": mode,
        "source_kind": envelope_guard.SOURCE_KIND,
        "state": state,
        "staged_records": int(staged_records),
        "error_class": error,
    }


def ingest_repo_count(
    *,
    user_response: dict,
    store,
    fetch_batch_id: str,
    observed_at: str | None = None,
) -> dict[str, str]:
    """Extract, envelope, and stage the one minimized GitHub repo-count fact."""

    repo_count = _extract_public_repo_count(user_response)
    count_field = "public_repos"
    fact = {"repo_count": repo_count, "count_field": count_field}
    try:
        policy.assert_scope_allowed(policy.ALLOWED_SCOPE)
        policy.assert_fact_minimized(fact)
    except policy.GithubPolicyError as exc:
        raise GithubV1Error(str(exc)) from exc

    observed = observed_at or _now_iso()
    ingest_record_id = _ingest_record_id(
        fetch_batch_id=fetch_batch_id,
        repo_count=repo_count,
        count_field=count_field,
    )
    envelope = _build_repo_count_envelope(
        ingest_record_id=ingest_record_id,
        fetch_batch_id=fetch_batch_id,
        repo_count=repo_count,
        count_field=count_field,
        observed_at=observed,
    )
    try:
        envelope_guard.validate_github_s2_envelope(envelope)
    except envelope_guard.GithubS2EnvelopeError as exc:
        raise GithubV1Error(str(exc)) from exc

    staged = store.stage_repo_count(
        ingest_record_id=ingest_record_id,
        fetch_batch_id=fetch_batch_id,
        repo_count=repo_count,
        count_field=count_field,
    )
    return {
        "ingest_record_id": str(staged.get("ingest_record_id", ingest_record_id)),
        "fetch_batch_id": str(staged.get("fetch_batch_id", fetch_batch_id)),
        "record_state": str(staged.get("record_state", "active")),
    }


def admit_repo_count_to_body(
    *,
    memory,
    repo_count: int,
    count_field: str,
    ingest_record_id: str,
    fetch_batch_id: str,
) -> str:
    """Write the single reviewed GitHub fact to raw memory with owner taint."""

    try:
        policy.assert_fact_minimized({"repo_count": repo_count, "count_field": count_field})
    except policy.GithubPolicyError as exc:
        raise GithubV1Error(str(exc)) from exc

    from memory.memory_manager import ProvenanceSource

    content = _honest_repo_count_content(repo_count=repo_count, count_field=count_field)
    return memory.store(
        content=content,
        cycle=0,
        provenance_source=ProvenanceSource.TOOL_OBSERVATION,
        egress_origin_class="owner_account_context",
        metadata={
            "source_ref": f"github.s2:{ingest_record_id}",
            "fetch_batch_id": fetch_batch_id,
        },
    )


def _honest_repo_count_content(*, repo_count: int, count_field: str) -> str:
    if count_field == "public_repos":
        return f"GitHub reports {repo_count} public repositories on the owner's profile"
    if count_field == "total":
        return f"GitHub reports {repo_count} repositories owned by the owner"
    raise GithubV1Error(f"unknown GitHub count_field: {count_field!r}")


def _extract_public_repo_count(user_response: dict) -> int:
    count = user_response.get("public_repos") if isinstance(user_response, dict) else None
    if type(count) is not int or count < 0:
        raise GithubV1Error("GitHub /user response missing integer public_repos")
    return count


def _build_repo_count_envelope(
    *,
    ingest_record_id: str,
    fetch_batch_id: str,
    repo_count: int,
    count_field: str,
    observed_at: str,
) -> dict:
    received_at = _now_iso()
    count_hash = _count_hash(repo_count=repo_count, count_field=count_field)
    return {
        "ingest_record_id": ingest_record_id,
        "schema_version": envelope_guard.SCHEMA_VERSION,
        "source_kind": envelope_guard.SOURCE_KIND,
        "source_handle_human": "GitHub owner account",
        "source_instance_id": "github:user",
        "source_handle_telemetry": _source_handle_telemetry(),
        "observed_at": observed_at,
        "received_at": received_at,
        "expires_at": "",
        "sequence": 1,
        "confidence": "provider_confirmed",
        "record_state": "active",
        "retention_class": "github_s2_staging",
        "granted_flow_ids": ["github.v1.read_user"],
        "facts": {"repo_count": repo_count, "count_field": count_field},
        "external_event_id": "",
        "external_event_id_hash": "",
        "source_revision": count_hash,
        "source_revision_hash": count_hash,
        "decision2_consent_tier": "owner_account",
        "consent_posture": "owner_consented",
        "third_party_posture": "minimized",
        "requested_flow_ids": ["github.v1.read_user"],
        "flow_policy_version": "github.v1.policy",
        "promotion_state": "staging_only",
        "promotion_eligibility_reason": "single_minimized_fact",
        "promotion_eligibility_provenance_handle": "",
        "promotion_record_id": "",
        "redaction_state": "deterministic_minimized",
        "fetch_batch_id": fetch_batch_id,
        "connector_version": "github.v1",
        "raw_field_policy_version": "github.raw.v1",
        "backfill_origin": "",
        "provenance": {
            "source": "github",
            "scope": policy.ALLOWED_SCOPE,
            "count_field": count_field,
        },
    }


def _ingest_record_id(*, fetch_batch_id: str, repo_count: int, count_field: str) -> str:
    digest = hashlib.sha256(
        f"github.v1.ingest|{fetch_batch_id}|{count_field}|{repo_count}".encode("utf-8")
    ).hexdigest()[:24]
    return f"github_s2_{digest}"


def _source_handle_telemetry() -> str:
    digest = hashlib.sha256(b"github.v1.source|owner").hexdigest()
    return f"github_source:{digest}"


def _count_hash(*, repo_count: int, count_field: str) -> str:
    return hashlib.sha256(f"github.v1|{count_field}|{repo_count}".encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
