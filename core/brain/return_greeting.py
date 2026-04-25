# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Presence-return greeting composer — 2026-04-24 voice fix.

Two problems it solves:

1. **Role label leaks into surface text.** The old greetings literally
   sent "Welcome back the owner." — a system-internal label
   ungrammatically placed in owner-facing prose. `display_name()` is
   configured ("Rohit" on this install) and should be used instead.

2. **No thread continuity.** When Rohit came back 67 minutes after an
   unfinished conversation about meta-harness, the old simple-path
   greeting gave just "Welcome back the owner." — no pointer back to
   the pending exchange. The >2hr detailed path did try to surface
   context, but pulled from `memory.raw.get(limit=1)` which returns a
   cycle's internal monologue (not necessarily the chat thread) in
   insertion order (not necessarily newest).

This module composes the greeting as a pure function so the daemon's
presence-detection loop stays thin and the behavior is unit-testable."""
from __future__ import annotations

import re
from typing import Optional

# Cleaned exchange shape: "<OwnerName>: <msg>\nMaez: <reply>" (produced
# by skills.surface.maez_adapter._clean_exchange; name comes from
# core.memory.identity.display_name()). Legacy envelope form is
# "the owner (<surface>): <msg>\n[envelope]\nMaez: <reply>". Parser is
# prefix-agnostic — it locates the first ":" on line 1 and takes
# everything after as the message body. No owner name is hardcoded.
_LEGACY_SURFACE_PREFIX = re.compile(r"^the owner \([^)]+\):\s*")

# Soft cap on how much of the owner's last question we quote inline.
# Keeps long questions from blowing up the greeting length.
_QUESTION_SNIPPET_CHARS = 140

# Heuristic: only surface the last owner message in a "Last we talked
# you asked: …" suffix when it actually looks like a question or open
# request. Statements (especially closing ones — "later", "good
# night", "you'll understand") get suppressed. The 2026-04-25 incident
# that drove this fix: owner closed an overnight philosophical thread
# with "You still don't get it but I guess that's how it's supposed
# to be. You'll understand what I'm talking about later." Maez
# acknowledged with "I'll keep running." The 11:16 morning greeting
# pulled that closing remark back as if a pending question — which it
# wasn't, and the conversation had already resolved cleanly.
#
# Conservative bias: when ambiguous, suppress the suffix. A missing
# pointer is a smaller failure than a false re-open of a settled
# thread.
_QUESTION_OPENERS = (
    "how", "what", "why", "when", "where", "who", "which",
    "is", "are", "was", "were", "do", "does", "did",
    "can", "could", "would", "should", "may", "might",
    "will", "won't", "shall",
    "have", "has", "had",
    "tell me", "show me", "explain", "describe",
)


def _extract_owner_message(exchange_content: str) -> Optional[str]:
    """Return just the owner's last message text from a stored
    telegram exchange, or None if the shape is unparseable.

    Handles three shapes without hardcoding the owner name:
      1. Cleaned form written by `_clean_exchange`:
         "<display_name>: <msg>\\nMaez: <reply>"
      2. Legacy envelope: "the owner (<surface>): <msg>\\n[...]\\nMaez:"
      3. Bare "Name: <msg>" on line 1 regardless of source.

    Renamed 2026-04-25 from `_extract_owner_question` — the value
    isn't always a question (see module-level note about the closing-
    statement incident)."""
    if not exchange_content:
        return None
    first_line = exchange_content.split("\n", 1)[0].strip()
    if not first_line:
        return None
    legacy = _LEGACY_SURFACE_PREFIX.match(first_line)
    if legacy:
        return first_line[legacy.end():].strip() or None
    colon = first_line.find(":")
    if colon > 0:
        return first_line[colon + 1:].strip() or None
    return None


# Backward-compat alias — the old name was used in older tests and
# external scripts before the 2026-04-25 rename.
_extract_owner_question = _extract_owner_message


def _looks_like_open_question(message: str) -> bool:
    """True iff `message` reads as a question or open request worth
    re-opening on welcome-back. False for statements, closing
    remarks, and ambiguous text — those get suppressed.

    Heuristic, not perfect. Conservative: when in doubt, return
    False so the suffix is suppressed. A bare "Welcome back, Rohit."
    is much better voice than a misframed re-open of a settled
    thread."""
    if not message:
        return False
    stripped = message.strip()
    if not stripped:
        return False
    # Explicit question mark anywhere is the strongest signal.
    if "?" in stripped:
        return True
    low = stripped.lower()
    # Imperative / interrogative openers — owner asking Maez to do
    # something, not making a closing remark.
    for opener in _QUESTION_OPENERS:
        if low.startswith(opener + " ") or low == opener:
            return True
    return False


def _snippet(text: str, limit: int = _QUESTION_SNIPPET_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def compose_return_greeting(
    *,
    display_name: str,
    absence_secs: float,
    last_exchange: Optional[dict] = None,
    last_exchange_age_secs: Optional[float] = None,
) -> str:
    """Compose the greeting Maez sends when the owner returns.

    Returns an empty string when the absence is short enough that no
    greeting is warranted (< 20 minutes) — caller should skip sending.

    Args:
        display_name: resolved owner name (e.g. "Rohit"). Falls back to
            "Friend" if empty.
        absence_secs: how long the owner has been away.
        last_exchange: optional dict from
            `memory.get_telegram_exchanges(limit=1)`. Only the
            `"content"` field is consulted. Pass None to suppress the
            thread-continuity suffix.
        last_exchange_age_secs: optional age of the last exchange.
            When provided AND the exchange is older than 24 hours, the
            thread-continuity suffix is suppressed (stale threads
            shouldn't be reopened as if the conversation were still
            warm). Pass None to accept any age.
    """
    name = display_name.strip() if display_name else ""
    if not name:
        name = "Friend"

    if absence_secs < 1200:
        return ""  # Under 20 minutes — caller skips the send.

    short_absence = absence_secs < 7200
    if short_absence:
        base = f"Welcome back, {name}."
    else:
        hrs = int(absence_secs // 3600)
        mins = int((absence_secs % 3600) // 60)
        base = f"Welcome back, {name} — you've been away for {hrs}h {mins}m."

    # Thread-continuity suffix. Gated on three things:
    #   1. last exchange is present
    #   2. exchange is fresh enough (< 24h) to be worth reopening
    #   3. the owner's last message ACTUALLY looks like a question or
    #      open request. Closing statements get suppressed — see the
    #      2026-04-25 incident note above for why.
    message = None
    if last_exchange:
        stale = (last_exchange_age_secs is not None
                 and last_exchange_age_secs > 86400)
        if not stale:
            message = _extract_owner_message(
                last_exchange.get("content", "") if isinstance(last_exchange, dict)
                else "",
            )

    if message and _looks_like_open_question(message):
        return f"{base} Last we talked you asked: '{_snippet(message)}'"
    return base
