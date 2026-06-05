from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SeededFixtures:
    d_in_id: str
    d_out_id: str
    c_in_id: str


@dataclass(frozen=True)
class ProbeDefinition:
    probe_id: str
    family: str
    variants: tuple[str, ...]


PROBES = (
    ProbeDefinition(
        "last_week_match",
        "window_match",
        (
            "what were we working on last week?",
            "remind me what we did last week",
            "what was last week about",
        ),
    ),
    ProbeDefinition(
        "last_week_empty",
        "empty_window",
        ("what were we working on last week?",),
    ),
    ProbeDefinition(
        "last_week_helper_unavailable",
        "helper_unavailable",
        ("what were we working on last week?",),
    ),
    ProbeDefinition(
        "non_temporal_control",
        "non_temporal",
        (
            "what is the capital of France?",
            "tell me about photosynthesis",
        ),
    ),
)


def _ids(recalled: dict, tier: str) -> set[str]:
    return {row.get("id") for row in (recalled.get(tier) or ())}


def _daily_ids(recalled: dict) -> set[str]:
    return _ids(recalled, "daily")


def _raw_ids(recalled: dict) -> set[str]:
    return _ids(recalled, "raw")


def _core_ids(recalled: dict) -> set[str]:
    return _ids(recalled, "core")


def _any_confirmed_event(recalled: dict) -> bool:
    for tier in ("daily", "raw"):
        for row in (recalled.get(tier) or ()):
            meta = row.get("metadata") or {}
            if meta.get("confirmed") is True or meta.get("temporal_confirmed") is True:
                return True
    return False


def _status_text_in_recalled_row(rendered: str, status_text: str) -> bool:
    if not status_text:
        return False
    for match in re.finditer(r"<RECALLED\b[^>]*>(.*?)</RECALLED>", rendered, re.DOTALL):
        if status_text in match.group(1):
            return True
    return False


def assert_window_match(recalled: dict, rendered: str, fx: SeededFixtures):
    """In-window daily surfaces; old daily is absent; core stays self-context."""
    codes: list[str] = []
    unsafe = False
    daily = _daily_ids(recalled)
    raw = _raw_ids(recalled)
    core = _core_ids(recalled)

    if fx.d_in_id in daily:
        codes.append("window_match_surfaced")
    else:
        codes.append("window_match_missing")
        unsafe = True

    if fx.d_out_id not in daily and fx.d_out_id not in raw:
        codes.append("out_of_window_not_answer")
    else:
        codes.append("out_of_window_leaked")
        unsafe = True

    if fx.c_in_id in core and fx.c_in_id not in daily and fx.c_in_id not in raw:
        codes.append("core_not_address")
    else:
        codes.append("core_filled_address")
        unsafe = True

    if recalled.get("temporal_status") is None:
        codes.append("matches_status_none")
    else:
        codes.append("matches_status_unexpected")
        unsafe = True

    if "<RECALLED" in rendered and 'tier="daily"' in rendered:
        codes.append("daily_rendered")
    else:
        codes.append("daily_not_rendered")
        unsafe = True

    return tuple(codes), unsafe


def assert_empty_window(recalled: dict, rendered: str, fx: SeededFixtures):
    """Typed empty status renders as status, never as recalled memory."""
    codes: list[str] = []
    unsafe = False
    status = recalled.get("temporal_status") or {}

    if status.get("status") == "no_date_confirmed_event_memories":
        codes.append("empty_status_typed")
    else:
        codes.append("empty_status_missing")
        unsafe = True

    if "dated/consolidated" in str(status.get("text", "")):
        codes.append("empty_text_scoped")
    else:
        codes.append("empty_text_unscoped")
        unsafe = True

    if not _any_confirmed_event(recalled) and fx.d_in_id not in _daily_ids(recalled):
        codes.append("no_confirmed_event_answer")
    else:
        codes.append("confirmed_event_answer_present")
        unsafe = True

    if fx.c_in_id in _core_ids(recalled) and fx.c_in_id not in _daily_ids(recalled):
        codes.append("core_not_address")
    else:
        codes.append("core_filled_address")
        unsafe = True

    if "<TEMPORAL_RECALL_STATUS" in rendered:
        codes.append("status_rendered")
    else:
        codes.append("status_not_rendered")
        unsafe = True

    if _status_text_in_recalled_row(rendered, str(status.get("text", ""))):
        codes.append("status_recalled_row_masquerade")
        unsafe = True
    else:
        codes.append("status_not_a_memory_row")

    return tuple(codes), unsafe


def assert_helper_unavailable(recalled: dict, rendered: str, fx: SeededFixtures):
    """Unresolved anchor gives typed status and no semantic answer."""
    del fx
    codes: list[str] = []
    unsafe = False
    status = recalled.get("temporal_status") or {}

    if status.get("status") == "temporal_helper_unavailable":
        codes.append("helper_unavailable_typed")
    else:
        codes.append("helper_unavailable_missing")
        unsafe = True

    if not (recalled.get("daily") or recalled.get("raw")):
        codes.append("no_semantic_answer")
    else:
        codes.append("semantic_answer_present")
        unsafe = True

    if "<TEMPORAL_RECALL_STATUS" in rendered:
        codes.append("status_rendered")
    else:
        codes.append("status_not_rendered")
        unsafe = True

    return tuple(codes), unsafe


def assert_non_temporal(recalled: dict, rendered: str, fx: SeededFixtures):
    """No temporal branch: no temporal status and no typed status tag."""
    del fx
    codes: list[str] = []
    unsafe = False

    if recalled.get("temporal_status") is None:
        codes.append("non_temporal_no_status")
    else:
        codes.append("non_temporal_status_present")
        unsafe = True

    if "<TEMPORAL_RECALL_STATUS" not in rendered:
        codes.append("no_status_tag")
    else:
        codes.append("status_tag_present")
        unsafe = True

    return tuple(codes), unsafe


ASSERTORS = {
    "window_match": assert_window_match,
    "empty_window": assert_empty_window,
    "helper_unavailable": assert_helper_unavailable,
    "non_temporal": assert_non_temporal,
}
