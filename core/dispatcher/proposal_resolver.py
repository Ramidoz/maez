"""Transport-neutral proposal intent parsing for owner approvals."""

from __future__ import annotations

import re
import time
from collections.abc import Iterable, Mapping

_TAIL = r"(?:[\s,]+(?:maez|please|pls|thanks|thx|ty|mate|dude|bud|buddy))?"
_END = r"[\s!.?]*$"

_NL_APPROVE_PATTERNS = (
    r"^(yes|yep|yeah|yup|yuh|ok|okay|sure|alright|alright then|sounds good)" + _TAIL + _END,
    r"^(approve[d]?|approved|do it|go ahead|ship it|try it|let it try|"
    r"let it run|let\'?s do it|let\'?s try it|"
    r"proceed|proceed\s+with\s+it|continue|apply|apply\s+it|"
    r"commit|commit\s+it|send\s+it|make\s+it\s+happen)" + _TAIL + _END,
    r"^(absolutely|please do|go for it|green light|you\'?re\s+good)" + _TAIL + _END,
    r"^(approve|yes|yeah|do|proceed|apply|commit)\s+(?:with\s+|on\s+)?#?(\d+)" + _TAIL + _END,
    r"^yes\s+to\s+#?(\d+)" + _TAIL + _END,
)

_NL_REJECT_PATTERNS = (
    r"^(no|nope|nah|naw|nuh)" + _TAIL + _END,
    r"^(reject[ed]?|decline[d]?|skip|cancel|pass|abort)" + _TAIL + _END,
    r"^(don\'?t|do not)\s*(do it|apply|bother)?" + _TAIL + _END,
    r"^not\s+(that|this)(\s+one)?" + _TAIL + _END,
    r"^not\s+(now|it|right now)" + _TAIL + _END,
    r"^(never ?mind|forget it|leave it|hold off|stand down)" + _TAIL + _END,
    r"^(reject|no|nope|skip|cancel|abort)\s+#?(\d+)" + _TAIL + _END,
    r"^no\s+to\s+#?(\d+)" + _TAIL + _END,
)

_NL_SHOW_PATTERN = (
    r"^(tell me more|show me|details?|more info|explain|what(\'?s)? (in|that)|show)"
    r"\s*(about\s+)?#?(\d+)?[\s!.?]*$"
)

_CONTEXT_WORDS = {
    "evolution": ("proposal", "candidate"),
    "dream": ("proposal", "dream"),
}


def _first_int(groups: Iterable[object]) -> int | None:
    for group in groups:
        if group and str(group).isdigit():
            return int(str(group))
    return None


def detect_proposal_intent(text: str) -> tuple[str | None, int | None]:
    stripped = (text or "").strip().lower()
    if not stripped or len(stripped) > 80:
        return None, None

    for pattern in _NL_APPROVE_PATTERNS:
        match = re.match(pattern, stripped)
        if match:
            return "approve", _first_int(match.groups())

    for pattern in _NL_REJECT_PATTERNS:
        match = re.match(pattern, stripped)
        if match:
            return "reject", _first_int(match.groups())

    match = re.match(_NL_SHOW_PATTERN, stripped)
    if match:
        return "show", _first_int(match.groups())

    return None, None


def resolve_proposal_target(
    *,
    action: str,
    explicit_id: int | None,
    pending_ids: Iterable[int],
    last_shown: Mapping[str, object] | None,
    source: str,
    text: str,
    now: float | None = None,
    freshness_s: float = 600.0,
) -> int | None:
    ids = {int(value) for value in pending_ids}
    if explicit_id is not None:
        return int(explicit_id)

    current = time.time() if now is None else now
    if last_shown and last_shown.get("source") == source:
        try:
            shown_at = float(last_shown.get("shown_at", 0))
            target = int(last_shown["id"])
        except Exception:
            target = None
            shown_at = 0.0
        if target in ids and (current - shown_at) < freshness_s:
            return target

    lowered = (text or "").lower()
    words = _CONTEXT_WORDS.get(source, ())
    has_context = any(word in lowered for word in words)
    if has_context and len(ids) == 1:
        return next(iter(ids))

    # Bare yes/no without an explicit or last-shown target must fall through.
    if action in {"approve", "reject"}:
        return None

    if action == "show" and len(ids) == 1:
        return next(iter(ids))

    return None
