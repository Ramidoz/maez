"""Strict on/off flags for Rail 2 (fetched-content immune screen).

Both default OFF; off == byte-identical to pre-Rail-2 behavior. Mirrors the
house strict parser (core.infra.env_flags.strict_env_flag); never bool(env).
"""
from __future__ import annotations

from core.infra.env_flags import strict_env_flag


def fetch_containment_enabled() -> bool:
    """Gate Layer A (envelope) AND Layer A2 (empty-success read-failure)."""
    return strict_env_flag("MAEZ_FETCH_CONTAINMENT_ENABLED")


def fetch_injection_shadow_enabled() -> bool:
    """Gate Layer B (hostile-content judge, shadow-only)."""
    return strict_env_flag("MAEZ_FETCH_INJECTION_SHADOW")
