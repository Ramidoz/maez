"""Deterministic, restart-aware self-status for Maez's dated recall."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

_STALE_SECONDS = 6 * 3600
_PRACTICE_STALE_SECONDS = 30 * 60

_RECALL_NOUN = r"(?:dated\s+(?:recall|memory)|recall\s+(?:stack|system))"
_REACH_PRED = r"(?:reachable|working|online|available|active|up|down|enabled|on|off|broken)"
_REACHABILITY_RE = re.compile(
    rf"(?:\bcan\s+you\s+reach\b.*\byour\b.*\b{_RECALL_NOUN}\b)"
    rf"|(?:\b(?:is|are)\b.*\byour\b.*\b{_RECALL_NOUN}\b.*\b{_REACH_PRED}\b)",
    re.IGNORECASE,
)
_WHEN_CHECK_RE = re.compile(
    rf"\bwhen\b.*\b(?:last\s+)?(?:check|checked|look|looked)\b.*\byour\b.*\b{_RECALL_NOUN}\b",
    re.IGNORECASE,
)
_COMPOUND_CONTENT_RE = re.compile(
    r"\b(?:and|,)\b.*\b(?:what|where|who|which|why|how)\b",
    re.IGNORECASE,
)
_COMPOUND_CONTENT_WHEN_RE = re.compile(
    rf"\b(?:and|,)\b.*\bwhen\b(?!.*\b(?:last\s+)?(?:check|checked|look|looked)\b.*\byour\b.*\b{_RECALL_NOUN}\b)",
    re.IGNORECASE,
)
_PRACTICE_RE = re.compile(
    r"\b(?:are|is)\b.*\b(?:you|maez)\b.*\b(?:quietly\s+)?"
    r"(?:practic(?:e|ing)|shadow(?:ing)?|running)\b.*\b(?:recall|background)\b",
    re.IGNORECASE,
)


class RecallLiveness(Enum):
    OFF_BY_CONFIG = "off_by_config"
    UNREACHABLE_FROM_SURFACE = "unreachable_from_surface"
    ON_NEVER_CONSULTED = "on_never_consulted_since_restart"
    ON_CONSULT_FAILED = "on_consult_failed"
    ON_OK = "on_ok"


@dataclass(frozen=True)
class RecallStatusReceipt:
    receipt: str
    at_ts: float
    boot_id: str


def is_recall_status_query(text: str) -> bool:
    # Scope guard: liveness-of-faculty only, never content recall that happens
    # to mention the dated-recall faculty.
    t = (text or "").strip()
    if not t:
        return False
    if _COMPOUND_CONTENT_RE.search(t) or _COMPOUND_CONTENT_WHEN_RE.search(t):
        return False
    return bool(_REACHABILITY_RE.search(t) or _WHEN_CHECK_RE.search(t))


def recall_status_query_wants_timestamp(text: str) -> bool:
    return bool(_WHEN_CHECK_RE.search((text or "").strip()))


def is_recall_practice_query(text: str) -> bool:
    # Scope guard: liveness of the quiet shadow-practice harness only. Content
    # recall and the dated-recall reachability status keep their own routes.
    t = (text or "").strip()
    if not t:
        return False
    if is_recall_status_query(t):
        return False
    if _COMPOUND_CONTENT_RE.search(t) or _COMPOUND_CONTENT_WHEN_RE.search(t):
        return False
    return bool(_PRACTICE_RE.search(t))


def _format_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")


def build_recall_practice_reply(
    *,
    shadow_enabled: bool,
    last_shadow_receipt: dict | None,
    current_boot_id: str,
    now_ts: float,
) -> tuple[str, str]:
    if not shadow_enabled:
        return (
            "My quiet dated-recall practice path is off right now.",
            "off",
        )
    if (
        not last_shadow_receipt
        or str(last_shadow_receipt.get("boot_id") or "") != str(current_boot_id or "")
    ):
        return (
            "My quiet dated-recall practice path is reachable, but it has not run "
            "since I came back up.",
            "active_never_run",
        )
    age = max(0.0, float(now_ts) - float(last_shadow_receipt.get("at_ts") or 0.0))
    if age <= _PRACTICE_STALE_SECONDS:
        state = str(last_shadow_receipt.get("state") or "unknown")
        if state != "consulted":
            return (
                f"My quiet dated-recall practice path is reachable, but the last "
                f"quiet practice attempt was skipped with state {state} just a "
                f"moment ago.",
                "active_recent_skipped",
            )
        return (
            f"I'm quietly practicing dated recall in the background; the last "
            f"practice check reached state {state} just a moment ago.",
            "active_recent",
        )
    return (
        "My quiet dated-recall practice path is reachable, but it has not run "
        "recently enough for me to call it fresh.",
        "active_stale",
    )


def build_recall_status_reply(
    *,
    triad_on: bool,
    carrier_reachable_from_surface: bool,
    last_receipt: RecallStatusReceipt | None,
    current_boot_id: str,
    now_ts: float,
    include_timestamp: bool = False,
) -> tuple[str, RecallLiveness]:
    if not triad_on:
        return (
            "I can't reach my dated memory right now - that path isn't switched on. "
            "I won't answer dated questions from guesswork.",
            RecallLiveness.OFF_BY_CONFIG,
        )
    if not carrier_reachable_from_surface:
        return (
            "I can't reach my dated memory from this surface right now. "
            "I won't answer dated questions from guesswork here.",
            RecallLiveness.UNREACHABLE_FROM_SURFACE,
        )
    if last_receipt is None or last_receipt.boot_id != current_boot_id:
        return (
            "My dated memory is reachable from here, but I haven't checked it "
            "since I came back up.",
            RecallLiveness.ON_NEVER_CONSULTED,
        )
    if last_receipt.receipt == "consult_failed":
        suffix = (
            f" Last check: {_format_ts(last_receipt.at_ts)}."
            if include_timestamp
            else ""
        )
        return (
            "My dated memory is reachable from here, but my last check errored out - "
            f"I'd want to try again before trusting it.{suffix}",
            RecallLiveness.ON_CONSULT_FAILED,
        )
    if last_receipt.receipt == "consulted":
        recent = (now_ts - last_receipt.at_ts) <= _STALE_SECONDS
        when = "just a moment ago" if recent else "a while back"
        suffix = (
            f" Last check: {_format_ts(last_receipt.at_ts)}."
            if include_timestamp
            else ""
        )
        return (
            f"My dated memory is reachable from here; I checked it {when}.{suffix}",
            RecallLiveness.ON_OK,
        )
    return (
        "My dated memory is reachable from here, but I haven't confirmed a "
        "same-boot check yet.",
        RecallLiveness.ON_NEVER_CONSULTED,
    )
