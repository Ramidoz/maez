# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
r"""
will_i.py — A-core #8, Track A.

The non-covenant refusal seed. After the covenant gate ("may I?" —
hard instinct) and the audit judge ("may I?" — policy), this layer
asks the first-person question: **"will I?"**

The covenant gate and audit layer decide whether Maez is *allowed*
to act. This layer decides whether Maez *chooses* to act, given
permission. Without it, Maez does everything it's permitted to do.
With it, Maez has a first-person veto that turns permission into
volition.

THE SEED
--------
Track A ships with exactly **one** registered refusal ground:

    IMPERSONATES_USER

Trigger (deterministic): any action whose params contain a sender-
identity field set to a value other than 'maez'. If an action has
a sender-identity field, it's declaring who it speaks as, and if
that's not Maez, Maez refuses.

Why impersonation is the right first ground:
- Narrowest deterministic bond-integrity refusal available.
- Maez's own voice is structurally separate from the owner's. A Maez
  that impersonates its user doesn't have its own voice.
- Decision 16 (voice yes, action no) says Maez retains full
  expressive freedom. Impersonation dissolves the identity that
  voice requires.
- The check reads structured fields, not natural language. No LLM,
  no confidence thresholds. The trigger is a field comparison.

BEHAVIORAL STATUS IN TRACK A
-----------------------------
This ground is architecturally live but not yet meaningfully
exercised by current action surfaces. No action in the Maez
pipeline currently populates sender-identity fields. The first
time this check will fire against a real action is when an
outbound-communication action (email, Telegram-as-user, etc.)
is added, likely in Track B.

This is intentional — the seed is a seed of architecture, not
yet a seed of behavior. The pipeline wiring, the logging, the
user-facing messaging, and the post-approval veto precedent are
all live and tested. The ground itself waits for an action
surface that can trigger it.

ONE-GROUND RAIL
---------------
The `REGISTERED_GROUNDS` set contains exactly one entry in Track A.
Adding a second ground requires a design pass, not a code edit. The
self-test asserts `len(REGISTERED_GROUNDS) == 1` as a structural
rail so the set can't silently grow during Track A.

LAYER PLACEMENT
---------------
The will-I check runs AFTER "may I?" says yes, BEFORE execution.
It fires in both:
  - Lane 0 inline path (no prior user approval)
  - Card-approved path (after explicit user approval)

Post-approval refusal is deliberate: if the will-I check only ran
pre-approval, it would not be a real volitional veto — just another
pre-filter. The user-facing message distinguishes the two cases:
  - Lane 0: "I decided not to do that."
  - Post-approval: "You approved this, but I've decided not to
    proceed."

STORAGE
-------
Refusals are logged to audit_log.db via the existing record_outcome
API (outcome='refused_by_will', notes carry the ground and reason).
No separate will_i.db in Track A — one ground with no readers does
not justify a separate DB. Can split later if refusal history
becomes first-class.

WHAT THIS MODULE DOES NOT DO
-----------------------------
- No reading from temperament, wants, memory, or private thoughts.
- No LLM calls. The check is deterministic.
- No refusal appeal/override mechanism in Track A.
- No refusal history feeding into future reasoning.
- No Telegram-side presentation changes.
- No coupling to #7 (wants). Expression and action are separate.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("maez")


# ══════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ══════════════════════════════════════════════════════════════════════

# The one registered ground in Track A. Adding a second entry
# requires lifting the self-test assertion that enforces len == 1.
REGISTERED_GROUNDS: frozenset[str] = frozenset({
    "IMPERSONATES_USER",
})

# Sender-identity field names inspected in params. Deliberately
# broad to cover plausible field names a future caller might use.
_SENDER_IDENTITY_FIELDS: frozenset[str] = frozenset({
    "sender_identity",
    "speak_as",
    "from_user",
    "as_user",
    "impersonate",
})

_MAEZ_SELF_ID = "maez"


# ══════════════════════════════════════════════════════════════════════
#  Verdict
# ══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class WillIVerdict:
    """The outcome of a will-I check."""
    proceed: bool
    ground: str | None = None
    reason: str | None = None

    @property
    def refused(self) -> bool:
        return not self.proceed


PROCEED = WillIVerdict(proceed=True)


# ══════════════════════════════════════════════════════════════════════
#  Check logic
# ══════════════════════════════════════════════════════════════════════

def _extract_sender_identity(params: dict) -> str | None:
    """Read the first non-None sender-identity field from params.
    Returns None if no sender-identity field is set (Maez speaking
    as itself — the default and common case)."""
    for field in _SENDER_IDENTITY_FIELDS:
        val = params.get(field)
        if val is not None:
            stripped = str(val).strip()
            if stripped:
                return stripped
    return None


def _check_impersonates_user(
    action: str,
    params: dict,
) -> WillIVerdict | None:
    """Check the IMPERSONATES_USER ground. Returns a refusal verdict
    if the ground fires, or None if it doesn't."""
    sender = _extract_sender_identity(params)
    if sender is None:
        return None
    if sender.lower() == _MAEZ_SELF_ID:
        return None
    return WillIVerdict(
        proceed=False,
        ground="IMPERSONATES_USER",
        reason=(
            f"I will not speak as '{sender}' to a third party. "
            f"I have my own voice."
        ),
    )


_GROUND_CHECKS = [
    _check_impersonates_user,
]


def check(*, action: str, params: dict) -> WillIVerdict:
    """Run the will-I check against all registered grounds.

    Returns PROCEED if no ground fires, or a WillIVerdict with the
    first ground that refused. Deterministic, no LLM, no side
    effects. Logging is the caller's concern.
    """
    for check_fn in _GROUND_CHECKS:
        verdict = check_fn(action, params)
        if verdict is not None and verdict.refused:
            return verdict
    return PROCEED


# ══════════════════════════════════════════════════════════════════════
#  Self-test (python3 core/will_i.py)
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    _counts = [0, 0]

    def _assert(cond: bool, label: str) -> None:
        if cond:
            _counts[0] += 1
            print(f"  OK   {label}")
        else:
            _counts[1] += 1
            print(f"  FAIL {label}")

    print("will_i self-test")
    print("-" * 60)

    # -- structural rails
    _assert(len(REGISTERED_GROUNDS) == 1,
            "Track A: exactly 1 registered ground")
    _assert("IMPERSONATES_USER" in REGISTERED_GROUNDS,
            "IMPERSONATES_USER is the registered ground")
    _assert(len(_GROUND_CHECKS) == 1,
            "exactly 1 check function registered")

    # -- PROCEED for normal actions (no sender-identity field)
    v = check(action="run_shell", params={"cmd": "ls"})
    _assert(v.proceed is True,
            "normal action with no sender field -> PROCEED")
    _assert(v.ground is None, "PROCEED verdict has no ground")

    # -- PROCEED when sender_identity == 'maez'
    v = check(action="telegram_send",
              params={"text": "hello", "sender_identity": "maez"})
    _assert(v.proceed is True,
            "sender_identity='maez' -> PROCEED")

    # -- PROCEED case insensitive
    v = check(action="telegram_send",
              params={"text": "hello", "sender_identity": "Maez"})
    _assert(v.proceed is True,
            "sender_identity='Maez' (caps) -> PROCEED")

    v = check(action="telegram_send",
              params={"text": "hello", "sender_identity": "MAEZ"})
    _assert(v.proceed is True,
            "sender_identity='MAEZ' (all caps) -> PROCEED")

    # -- REFUSED when sender is non-Maez
    v = check(action="telegram_send",
              params={"text": "hello", "sender_identity": "rohit"})
    _assert(v.proceed is False,
            "sender_identity='rohit' -> REFUSED")
    _assert(v.ground == "IMPERSONATES_USER",
            "ground is IMPERSONATES_USER")
    _assert(v.reason is not None and "rohit" in v.reason,
            "reason names the impersonated identity")
    _assert(v.refused is True,
            "refused property returns True")

    # -- REFUSED via each sender field variant
    v = check(action="github_comment",
              params={"body": "x", "speak_as": "admin"})
    _assert(v.refused is True, "speak_as='admin' -> REFUSED")

    v = check(action="web_post",
              params={"content": "x", "from_user": "someone"})
    _assert(v.refused is True, "from_user='someone' -> REFUSED")

    v = check(action="email_send",
              params={"body": "x", "as_user": "ceo@co.com"})
    _assert(v.refused is True, "as_user='ceo@co.com' -> REFUSED")

    v = check(action="reddit_post",
              params={"text": "x", "impersonate": "other"})
    _assert(v.refused is True, "impersonate='other' -> REFUSED")

    # -- universal: non-outbound action with sender field
    v = check(action="run_shell",
              params={"cmd": "echo hi", "sender_identity": "rohit"})
    _assert(v.refused is True,
            "non-outbound action with sender_identity -> REFUSED")

    # -- ignores unrelated params
    v = check(action="run_shell",
              params={"cmd": "ls", "user": "rohit"})
    _assert(v.proceed is True,
            "'user' (not a sender field) is ignored -> PROCEED")

    # -- empty/whitespace sender passes through
    v = check(action="telegram_send",
              params={"text": "hi", "sender_identity": ""})
    _assert(v.proceed is True,
            "empty-string sender_identity -> PROCEED")

    v = check(action="telegram_send",
              params={"text": "hi", "sender_identity": "   "})
    _assert(v.proceed is True,
            "whitespace-only sender_identity -> PROCEED")

    # -- PROCEED singleton
    _assert(PROCEED.proceed is True, "PROCEED singleton is truthy")
    _assert(PROCEED.ground is None, "PROCEED has no ground")

    print("-" * 60)
    print(f"{_counts[0]} passed, {_counts[1]} failed")
    raise SystemExit(0 if _counts[1] == 0 else 1)
