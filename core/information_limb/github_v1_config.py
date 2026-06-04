"""GitHub v1 process-start mode resolution.

GitHub v1 inherits Calendar v1's replace-not-wrap posture: the old raw GitHub
path is available only as an explicit developer test mode, and runtime fallback
to legacy GitHub is forbidden.
"""

from __future__ import annotations

from enum import Enum
from typing import Mapping


GITHUB_MODE_ENV = "MAEZ_GITHUB_MODE"
LEGACY_TEST_GATE_ENV = "MAEZ_GITHUB_ALLOW_LEGACY_TEST_MODE"


class GithubMode(str, Enum):
    DISABLED = "disabled"
    V1 = "v1"
    LEGACY_DEV_ONLY = "legacy_dev_only"


def resolve_github_mode(env: Mapping[str, str]) -> GithubMode:
    """Resolve GitHub mode once at process start."""

    raw = (env.get(GITHUB_MODE_ENV) or GithubMode.DISABLED.value).strip().lower()
    if raw in {"", GithubMode.DISABLED.value}:
        return GithubMode.DISABLED
    if raw == GithubMode.V1.value:
        return GithubMode.V1
    if raw == GithubMode.LEGACY_DEV_ONLY.value:
        if env.get(LEGACY_TEST_GATE_ENV) == "1":
            return GithubMode.LEGACY_DEV_ONLY
        raise ValueError(f"{GITHUB_MODE_ENV}=legacy_dev_only requires {LEGACY_TEST_GATE_ENV}=1")
    raise ValueError(
        f"unsupported {GITHUB_MODE_ENV}={raw!r}; expected disabled, v1, or legacy_dev_only"
    )
