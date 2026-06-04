"""GitHub v1 S2-bounded ingest surface.

The connector admits exactly one minimized fact: the owner's GitHub repo count.
It does not list repositories, persist raw provider payloads, or write to Maez's
body except through the explicit reviewed body-admission function added later in
this slice.
"""

from __future__ import annotations

from collections.abc import Callable
import hashlib
import hmac
import os
from datetime import datetime, timezone
from typing import Literal, TypedDict

from core.information_limb import github_limb
from core.information_limb import github_connector_policy as policy
from core.information_limb import github_s2_envelope as envelope_guard
from core.information_limb.github_v1_config import GithubMode


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


GITHUB_INGEST_HEADER = "X-Maez-Github-Ingest"
GITHUB_INGEST_TOKEN_ENV = "MAEZ_GITHUB_INGEST_TOKEN"
_INGEST_RESPONSE_KEYS = frozenset(
    {"ok", "ingest_record_id", "fetch_batch_id", "staged", "admitted", "state", "resumed"}
)


def ingest_trusted(headers) -> bool:
    """True only for an owner-triggered caller with the ingest secret.

    This is deliberately separate from the session handoff token: opening the
    eye and writing owner-account memory are different authorities.
    """
    expected = os.environ.get(GITHUB_INGEST_TOKEN_ENV, "")
    presented = headers.get(GITHUB_INGEST_HEADER, "")
    if not expected or not presented:
        return False
    if headers.get("Origin"):
        return False
    return hmac.compare_digest(expected.encode("utf-8"), presented.encode("utf-8"))


def handle_ingest(
    *,
    headers,
    mode: GithubMode,
    limb,
    store,
    memory,
    fetch_batch_id_factory: Callable[[], str],
) -> tuple[dict, int]:
    """Hardened-loopback GitHub v1 ingest endpoint logic.

    Auth is checked before limb/store/memory are touched. The response is
    filtered to the content-free allowlist even if run_ingest changes later.
    """
    if not ingest_trusted(headers):
        return {"ok": False, "error": "github_ingest_untrusted"}, 403
    if mode != GithubMode.V1:
        return {"ok": False, "error": "github_v1_not_enabled"}, 409
    session = limb.available_session()
    if session is None:
        return {"ok": False, "error": "github_limb_unauthed"}, 409
    if store is None:
        return {"ok": False, "error": "github_store_unavailable"}, 409
    result = run_ingest(
        limb_session=session,
        store=store,
        memory=memory,
        fetch_batch_id=fetch_batch_id_factory(),
    )
    return {key: result[key] for key in _INGEST_RESPONSE_KEYS if key in result}, 200


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


def run_ingest(*, limb_session, store, memory, fetch_batch_id: str) -> dict:
    """Owner-triggered GitHub v1 ingest.

    Resumes any interrupted staged observation before fetching from GitHub,
    then admits at most once per durable ingest_record_id. The returned value
    is deliberately content-free: ids and state only.
    """
    pending = store.oldest_pending()
    if pending is not None:
        ingest_record_id = pending.ingest_record_id
        existing_body_id = memory.owner_account_row_id_by_source_ref(
            f"github.s2:{ingest_record_id}"
        )
        if existing_body_id is not None:
            store.mark_admitted(ingest_record_id, body_memory_id=str(existing_body_id))
            return _ingest_result(
                ingest_record_id=ingest_record_id,
                fetch_batch_id=pending.fetch_batch_id,
                admitted=False,
                resumed=True,
            )

        body_memory_id = admit_repo_count_to_body(
            memory=memory,
            repo_count=pending.repo_count,
            count_field=pending.count_field,
            ingest_record_id=ingest_record_id,
            fetch_batch_id=pending.fetch_batch_id,
        )
        store.mark_admitted(ingest_record_id, body_memory_id=str(body_memory_id))
        return _ingest_result(
            ingest_record_id=ingest_record_id,
            fetch_batch_id=pending.fetch_batch_id,
            admitted=True,
            resumed=True,
        )

    repo_count = github_limb.fetch_repo_count(limb_session)
    count_field = "public_repos"
    staged = ingest_repo_count(
        user_response={count_field: repo_count},
        store=store,
        fetch_batch_id=fetch_batch_id,
    )
    ingest_record_id = staged["ingest_record_id"]
    state = store.promotion_state(ingest_record_id)
    if state == "admitted":
        return _ingest_result(
            ingest_record_id=ingest_record_id,
            fetch_batch_id=fetch_batch_id,
            admitted=False,
            resumed=False,
        )

    body_memory_id = admit_repo_count_to_body(
        memory=memory,
        repo_count=repo_count,
        count_field=count_field,
        ingest_record_id=ingest_record_id,
        fetch_batch_id=fetch_batch_id,
    )
    store.mark_admitted(ingest_record_id, body_memory_id=str(body_memory_id))
    return _ingest_result(
        ingest_record_id=ingest_record_id,
        fetch_batch_id=fetch_batch_id,
        admitted=True,
        resumed=False,
    )


def _ingest_result(
    *,
    ingest_record_id: str,
    fetch_batch_id: str,
    admitted: bool,
    resumed: bool,
) -> dict:
    return {
        "ok": True,
        "ingest_record_id": ingest_record_id,
        "fetch_batch_id": fetch_batch_id,
        "staged": True,
        "admitted": bool(admitted),
        "state": "admitted",
        "resumed": bool(resumed),
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
