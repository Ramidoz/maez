"""Capability card: live substrate self-knowledge for evidence precedence.

Each line is a probe, not prose. Probe failures render as ``unknown`` rather
than disappearing; a missing organ line would be a quieter lie than a visible
unknown.
"""
from __future__ import annotations

import logging
import os
import time
import json
from collections.abc import Callable, Sequence

logger = logging.getLogger("maez")

_CARD_TTL_S = 30.0
_CARD_CACHE: dict[str, object] = {"text": None, "ts": 0.0}
_BACKEND = None
_ENTRY_SOURCE = {
    "web sense": "probe",
    "page read": "flag",
    "recall": "flag",
    "search commitment": "flag",
    "felt time": "probe",
}
_VOICE_BOUNDARY_INSTRUCTION = (
    "Use CAPABILITY_STATE as private grounding for current self-capability "
    "questions. Do not quote field names or dashboard phrasing. Render the "
    "truth in your own voice. Memories may contextualize, but they do not "
    "override this state for what your body can do now. Do not write "
    "CAPABILITY_STATE or [CAPABILITY_STATE] in the reply."
)


def evidence_precedence_enabled() -> bool:
    return (
        (os.environ.get("MAEZ_EVIDENCE_PRECEDENCE_ENABLED", "") or "")
        .strip()
        .lower()
        in {"1", "true", "yes", "on"}
    )


def voice_boundary_enabled() -> bool:
    """Strict parser: only ``1/true/yes/on`` enable. ``"0"`` is OFF.

    Deliberately rejects the house-wide ``bool(os.environ.get(...))`` footgun
    (``"0"`` would read truthy). Mirrors ``evidence_precedence_enabled``.
    """
    return (
        (os.environ.get("MAEZ_VOICE_BOUNDARY_ENABLED", "") or "")
        .strip()
        .lower()
        in {"1", "true", "yes", "on"}
    )


def body_legibility_enabled() -> bool:
    return (
        (os.environ.get("MAEZ_BODY_LEGIBILITY", "") or "").strip().lower()
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


def _canonical_status(name: str, raw: str) -> str:
    """Map raw probe output to neutral envelope values only.

    This is a rendered-form change, not a probe change: the flag-off prose path
    keeps raw probe output byte-identical. The envelope must not feed dashboard
    jargon such as "gatekeeper mode" or "searxng healthy" into the voice.
    """
    low = (raw or "").strip().lower()
    if "unknown" in low or "error" in low:
        return "unknown"
    if name == "web sense":
        if "healthy" in low or "ok" in low:
            return "healthy"
        if "degraded" in low or "down" in low or "unhealthy" in low:
            return "degraded"
        return "unknown"
    if name == "search commitment":
        return "off" if low in ("off", "", "false", "no") else "on"
    if name == "felt time":
        if "attached" in low and "not" not in low:
            return "attached"
        return "unattached"
    if low in ("on", "true", "yes", "1"):
        return "on"
    if low in ("off", "false", "no", "", "0"):
        return "off"
    return low


def _affordance(name: str, status: str) -> str | None:
    if name != "web sense":
        return None
    if status == "healthy":
        return "can retrieve current external information"
    if status == "degraded":
        return "retrieval currently degraded"
    if status == "unknown":
        return "retrieval currently unknown"
    return None


def _build_capability_envelope(
    registry: Sequence[tuple[str, Callable[[], str]]],
) -> str:
    """Build the structured voice-boundary envelope.

    Status is a neutral rendered form of raw probe output. Failed probes remain
    explicit as unknown entries; a missing line would be a quieter lie.
    """
    entries: list[dict[str, str]] = []
    for name, probe in registry:
        source = _ENTRY_SOURCE.get(name, "probe")
        try:
            status = _canonical_status(name, probe())
            entry = {
                "name": name,
                "status": status,
                "source": source,
            }
            if body_legibility_enabled():
                aff = _affordance(name, status)
                if aff is not None:
                    entry["affordance"] = aff
            entries.append(entry)
        except Exception:
            entry = {
                "name": name,
                "status": "unknown",
                "source": source,
                "error": "probe_error",
            }
            if body_legibility_enabled():
                aff = _affordance(name, "unknown")
                if aff is not None:
                    entry["affordance"] = aff
            entries.append(entry)
    payload = {
        "kind": "capability_state",
        "freshness": "live_or_cached_30s",
        "authority": "current_self_capability_state",
        "precedence": "for current body/capability questions, this outranks stale memory",
        "entries": entries,
    }
    return (
        "CAPABILITY_STATE (current self-capability; private grounding):\n"
        + json.dumps(payload, indent=2)
        + "\n"
        + _VOICE_BOUNDARY_INSTRUCTION
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
        reg = registry if registry is not None else _default_registry()
        if voice_boundary_enabled():
            text = _build_capability_envelope(reg)
            _CARD_CACHE["text"] = text
            _CARD_CACHE["ts"] = now
            return text

        entries: list[str] = []
        for name, probe in reg:
            try:
                raw = probe()
                if body_legibility_enabled():
                    canonical = _canonical_status(name, raw)
                    aff = _affordance(name, canonical)
                    if aff is not None:
                        entries.append(f"{name}: {raw} — {aff}")
                        continue
                entries.append(f"{name}: {raw}")
            except Exception:
                raw = "unknown (probe error)"
                if body_legibility_enabled():
                    aff = _affordance(name, "unknown")
                    if aff is not None:
                        entries.append(f"{name}: {raw} — {aff}")
                        continue
                entries.append(f"{name}: {raw}")

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
