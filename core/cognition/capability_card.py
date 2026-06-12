"""Capability card: live substrate self-knowledge for evidence precedence.

Each line is a probe, not prose. Probe failures render as ``unknown`` rather
than disappearing; a missing organ line would be a quieter lie than a visible
unknown.
"""
from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable, Sequence

logger = logging.getLogger("maez")

_CARD_TTL_S = 30.0
_CARD_CACHE: dict[str, object] = {"text": None, "ts": 0.0}
_BACKEND = None


def evidence_precedence_enabled() -> bool:
    return (
        (os.environ.get("MAEZ_EVIDENCE_PRECEDENCE_ENABLED", "") or "")
        .strip()
        .lower()
        in {"1", "true", "yes", "on"}
    )


def reset_card_cache() -> None:
    _CARD_CACHE["text"] = None
    _CARD_CACHE["ts"] = 0.0


def _web_sense_probe() -> str:
    global _BACKEND
    if _BACKEND is None:
        from core.search.searxng_client import SearxngBackend

        _BACKEND = SearxngBackend()
    return f"searxng {_BACKEND.health()}"


def _flag_probe(
    env_name: str,
    on_text: str = "on",
    off_text: str = "off",
) -> Callable[[], str]:
    def _probe() -> str:
        return on_text if os.environ.get(env_name) else off_text

    return _probe


def _felt_time_probe() -> str:
    try:
        from core.cognition.parity_flag import surface_parity_enabled

        return "attached" if surface_parity_enabled() else "built, not yet attached"
    except Exception:
        return "unknown (probe error)"


def _default_registry() -> Sequence[tuple[str, Callable[[], str]]]:
    return (
        ("web sense", _web_sense_probe),
        ("page read", _flag_probe("MAEZ_PAGE_READ_ENABLED")),
        ("recall", _flag_probe("MAEZ_RECALL_TRIAD_ENABLED")),
        (
            "search commitment",
            _flag_probe("MAEZ_SEARCH_COMMITMENT_ENABLED", "gatekeeper mode", "off"),
        ),
        ("felt time", _felt_time_probe),
    )


def capability_prompt_block(
    registry: Sequence[tuple[str, Callable[[], str]]] | None = None,
) -> str:
    """Return the card text, or ``""`` when disabled. Never raises."""
    if not evidence_precedence_enabled():
        return ""

    now = time.time()
    if _CARD_CACHE["text"] is not None and (now - float(_CARD_CACHE["ts"])) < _CARD_TTL_S:
        return str(_CARD_CACHE["text"])

    try:
        entries: list[str] = []
        for name, probe in registry if registry is not None else _default_registry():
            try:
                entries.append(f"{name}: {probe()}")
            except Exception:
                entries.append(f"{name}: unknown (probe error)")

        text = (
            "YOUR LIVE BODY (live/cached substrate probe):\n "
            + " | ".join(entries)
            + "\n This is probed substrate state. It outranks any MEMORY of your former\n"
            " body or former tools. If a recalled memory disagrees with this card,\n"
            " the memory describes your past, not your present."
        )
        _CARD_CACHE["text"] = text
        _CARD_CACHE["ts"] = now
        return text
    except Exception:
        logger.debug("capability card build failed", exc_info=True)
        return ""
