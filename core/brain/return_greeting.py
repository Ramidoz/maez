# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Presence-return greeting composer — 2026-04-24 voice fix, simplified
2026-04-25.

Original problem this module solved: the daemon's presence-detection
loop sent two hardcoded strings verbatim — "Welcome back the owner."
and "Welcome back the owner — you've been away for ... Here's what
I've been thinking about: <random raw memory entry>". Both leaked
the role label "the owner" into surface text, and the >2hr path
pulled an arbitrary raw-memory entry as a "thought" hook.

The 2026-04-24 voice fix replaced them with this composer: name
resolved from `display_name()`, absence-duration on long absences,
and a "Last we talked you asked: '...'" suffix when there was a
recent prior exchange.

The suffix turned out to be the wrong feature. Two follow-on
incidents on 2026-04-25:
  - Owner closed an overnight philosophical thread cleanly. Next
    morning's greeting re-quoted the closing remark as if it were
    an open question.
  - Owner sent casual "What is good maez?" mid-day. Two return
    greetings re-quoted it as "Last we talked you asked: 'What
    is good maez?'" — uncanny.

Each was patchable with another rule (closing-statement detector,
casual-greeting detector). But the right answer was simpler: the
suffix duplicates work that `chat_history` threading (commit
cc462c5) already does. When the owner returns and types anything,
Maez sees the last 3 exchanges in messages[] and can naturally
re-engage. The greeting doesn't need to guess what's pending.

So this module is now minimal: a deterministic greeting with the
configured owner name and the absence duration when meaningful.
No re-quoting. No question detection. No edge cases. Whatever
context Maez should bring up arrives organically when the owner
speaks again.
"""
from __future__ import annotations


def compose_return_greeting(
    *,
    display_name: str,
    absence_secs: float,
) -> str:
    """Compose the greeting Maez sends when the owner returns.

    Empty string for absences under 20 minutes (caller skips send).
    Short greeting under 2 hours; absence duration appended for
    longer breaks. Owner name resolved from `display_name()` —
    falls back to "Friend" if empty.
    """
    name = display_name.strip() if display_name else ""
    if not name:
        name = "Friend"

    if absence_secs < 1200:
        return ""  # Under 20 minutes — caller skips the send.

    if absence_secs < 7200:
        return f"Welcome back, {name}."

    hrs = int(absence_secs // 3600)
    mins = int((absence_secs % 3600) // 60)
    return f"Welcome back, {name} — you've been away for {hrs}h {mins}m."
