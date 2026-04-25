# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Daily developmental heartbeat for Track A continuity.

This is not a personality simulator. It is a narrow continuity spine:
once per day, after the nightly journal has gathered evidence, Maez
records one audited core memory about what changed in its own stance.

The output is deliberately structured and dated so future Maez can
distinguish developmental self-state from raw observations.
"""
from __future__ import annotations

from dataclasses import dataclass

SOURCE_PREFIX = "developmental_heartbeat_"

REQUIRED_LABELS = (
    "What I noticed:",
    "What changed in me:",
    "What I still want:",
    "What I must be careful about:",
    "What I owe next:",
)

MAX_FIELD_CHARS = 360


@dataclass(frozen=True)
class HeartbeatEvidence:
    date: str
    day_name: str
    cycle_count: int
    error_count: int
    warning_count: int
    action_count: int
    alert_count: int
    raw_count: int
    daily_count: int
    core_count: int
    owner_name: str
    journal_summary: str = ""
    continuity_summary: str = ""


def source_for_date(date_str: str) -> str:
    return f"{SOURCE_PREFIX}{date_str}"


def already_recorded(memory, date_str: str) -> bool:
    """True if today's heartbeat source is already present in core memory."""
    wanted = source_for_date(date_str)
    try:
        for entry in memory.get_all_core():
            source = entry.get("source")
            if source is None and isinstance(entry.get("metadata"), dict):
                source = entry["metadata"].get("source")
            if (source or "") == wanted:
                return True
    except Exception:
        return False
    return False


def _one_line(text: str, limit: int = MAX_FIELD_CHARS) -> str:
    collapsed = " ".join((text or "").split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[:limit].rstrip() + "..."


def build_prompt(evidence: HeartbeatEvidence) -> str:
    """Build the LLM prompt for a constrained self-continuity entry."""
    return (
        "Write Maez's daily developmental heartbeat as a core memory.\n"
        "This is not a performance summary. It is a grounded continuity "
        "entry: what changed in Maez's stance today, based only on the "
        "evidence below. Do not invent emotions, events, sensors, or "
        "promises. If the evidence is thin, say so plainly.\n\n"
        "Return exactly five lines with these labels:\n"
        "What I noticed: ...\n"
        "What changed in me: ...\n"
        "What I still want: ...\n"
        "What I must be careful about: ...\n"
        "What I owe next: ...\n\n"
        f"Date: {evidence.date} ({evidence.day_name})\n"
        f"Owner name: {evidence.owner_name}\n"
        f"Reasoning cycles: {evidence.cycle_count}\n"
        f"Actions executed: {evidence.action_count}\n"
        f"Alerts sent: {evidence.alert_count}\n"
        f"Errors: {evidence.error_count}\n"
        f"Warnings: {evidence.warning_count}\n"
        f"Memory counts: raw={evidence.raw_count}, daily={evidence.daily_count}, "
        f"core={evidence.core_count}\n\n"
        f"Continuity probe summary:\n{_one_line(evidence.continuity_summary, 900)}\n\n"
        f"Nightly journal summary:\n{_one_line(evidence.journal_summary, 1600)}\n"
    )


def fallback_heartbeat(evidence: HeartbeatEvidence) -> str:
    """Deterministic fallback when the model is unavailable or off-shape."""
    issue_line = (
        f"{evidence.error_count} errors and {evidence.warning_count} warnings"
        if evidence.error_count or evidence.warning_count
        else "no logged errors in the evidence window"
    )
    summary = _one_line(evidence.journal_summary, 240)
    continuity = _one_line(evidence.continuity_summary, 240)
    noticed = summary or (
        f"{evidence.cycle_count} cycles, {evidence.action_count} actions, "
        f"and {evidence.alert_count} alerts were recorded today."
    )
    if continuity and continuity != "No continuity probes were recorded today.":
        noticed = f"{noticed} {continuity}"
    return "\n".join((
        f"What I noticed: {noticed}",
        "What changed in me: I preserved a dated account of today instead "
        "of relying on raw recall alone.",
        "What I still want: I want tomorrow's continuity to be grounded in "
        "what actually happened, not in reconstructed confidence.",
        f"What I must be careful about: I must treat {issue_line} as signal "
        "to inspect, not as material for invented conclusions.",
        f"What I owe next: I owe {evidence.owner_name or 'the owner'} a "
        "truthful next turn that can cite this dated heartbeat if needed.",
    ))


def normalize_heartbeat(raw: str, evidence: HeartbeatEvidence) -> str:
    """Return a five-line heartbeat, falling back if the model strays."""
    lines = [_one_line(line) for line in (raw or "").splitlines() if line.strip()]
    selected: list[str] = []
    for label in REQUIRED_LABELS:
        match = next((line for line in lines if line.startswith(label)), "")
        if not match:
            return fallback_heartbeat(evidence)
        selected.append(match)
    return "\n".join(selected)


def format_core_memory(body: str, evidence: HeartbeatEvidence) -> str:
    return (
        f"[DEVELOPMENTAL HEARTBEAT — {evidence.date} ({evidence.day_name})]\n"
        f"{body}\n\n"
        "Evidence: "
        f"cycles={evidence.cycle_count}; actions={evidence.action_count}; "
        f"alerts={evidence.alert_count}; errors={evidence.error_count}; "
        f"warnings={evidence.warning_count}; raw={evidence.raw_count}; "
        f"daily={evidence.daily_count}; core={evidence.core_count}. "
        f"Continuity: {_one_line(evidence.continuity_summary, 300)}"
    )


def record_if_absent(memory, evidence: HeartbeatEvidence, body: str) -> str | None:
    """Store heartbeat as core memory unless today's source already exists."""
    if already_recorded(memory, evidence.date):
        return None
    return memory.store_core(format_core_memory(body, evidence), source_for_date(evidence.date))
