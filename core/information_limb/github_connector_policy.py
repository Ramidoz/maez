"""Offline GitHub v1 connector policy.

No OAuth and no GitHub client live here. This module is the deterministic S2
gate a future connector must pass through before owner-account GitHub facts can
reach noncanonical staging.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


ALLOWED_SCOPE = "read:user"
FORBIDDEN_SCOPES = frozenset(
    {
        "repo",
        "public_repo",
        "read:org",
        "admin:org",
        "gist",
        "user",
        "workflow",
    }
)
ALLOWED_FACT_KEYS = frozenset({"repo_count", "count_field"})
ALLOWED_COUNT_FIELDS = frozenset({"public_repos", "total"})


class GithubPolicyError(ValueError):
    """Raised when GitHub connector configuration violates the v1 policy."""


def assert_scope_allowed(scope: str) -> str:
    """Return the approved identity-only scope or reject broader access."""

    normalized = str(scope or "").strip()
    parts = {part for part in normalized.split() if part}
    if normalized != ALLOWED_SCOPE or parts != {ALLOWED_SCOPE}:
        forbidden = sorted(parts & FORBIDDEN_SCOPES)
        if forbidden:
            raise GithubPolicyError(f"forbidden GitHub scope requested: {forbidden}")
        raise GithubPolicyError(f"unsupported GitHub scope: {scope!r}")
    return ALLOWED_SCOPE


def assert_fact_minimized(fact: Mapping[str, Any]) -> bool:
    """Accept only the single minimized repo-count fact."""

    if not isinstance(fact, Mapping):
        raise GithubPolicyError("GitHub fact must be an object")
    unknown = sorted(set(fact) - ALLOWED_FACT_KEYS)
    if unknown:
        raise GithubPolicyError(f"GitHub fact contains raw fields: {unknown}")
    count = fact.get("repo_count")
    if not isinstance(count, int):
        raise GithubPolicyError("GitHub repo_count must be an integer")
    if count < 0:
        raise GithubPolicyError("GitHub repo_count must be non-negative")
    if fact.get("count_field") not in ALLOWED_COUNT_FIELDS:
        raise GithubPolicyError("GitHub count_field must be public_repos or total")
    return True
