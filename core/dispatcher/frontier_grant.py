# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Authority-bearing, durable grants for metered external consumption.

Owner-authorized 2026-08-28 (D1 seam 2, Rulings 1 and 2).

WHY THIS REPLACES THE IN-PROCESS LEDGER. The first cut minted grants with
``GRANTS.grant(source, caller, operation)`` — self-asserted strings, any
in-process importer, no owner anywhere. That is a capability record, not
authorization. It was also process-local: a fork after granting let each
child consume the same one-shot grant.

Both defects close the same way, by not inventing an authority store at
all. A grant here IS an owner-resolved pending card:

  * AUTHORITY — the card carries ``resolved_by_user_id``,
    ``resolved_via`` and ``resolved_at`` from the authenticated owner
    decision path. A grant that cannot name the decision that created it
    cannot exist.
  * BINDING — the card's ``params`` bind source, operation, purpose,
    max calls, expiry and any model restriction; its ``state_hash``
    makes a changed request EXPIRE rather than approve.
  * DURABILITY — SQLite on disk, ``journal_mode=delete`` (a rollback
    journal, deliberately not the WAL path this host's SQLite 3.46.1 has
    a documented reset-corruption window in).
  * ATOMIC ONE-SHOT — ``APPROVED -> RUNNING`` is a single conditional
    UPDATE with a rowcount check. Sixteen real processes racing one
    approved card yield exactly one winner.

CONSUMPTION AUTHORIZES AN ATTEMPT, NOT A RESULT. The grant is spent
before the proxy is contacted, and a failed call is NOT refunded: once
the request leaves, nobody can prove whether the external resource was
consumed. ``mark_failed`` cannot return a card to APPROVED, so this is
structural rather than a promise. A retry needs a new grant.

AVAILABILITY CHECKS REMAIN NON-CONSUMING. Nothing here is called to
answer "is this source available"; that path reads local state only.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass

from core.decision.pending_cards import (
    CardStatus,
    CardStoreError,
    PendingCardStore,
)
from core.dispatcher.spec import ExternalSource
from core.governance.operator_user_boundary import (
    METERED_CONSUMPTION_ACTION,
    NON_MUTATING_METERED_OPERATIONS,
    derive_work_class,
)

#: D1 is one call per owner decision. Standing allowances are not
#: authorized: raising this needs an owner ruling, not an argument.
MAX_CALLS = 1

DEFAULT_TTL_S = 900.0


class GrantRefused(PermissionError):
    """No live, owner-authorized, correctly-bound grant. Nothing spent."""


@dataclass(frozen=True)
class AuthorityBearingGrant:
    """A consumed authorization that still names who granted it."""

    card_id: str
    source: ExternalSource
    operation: str
    purpose_hash: str
    model: str | None
    #: The owner decision that caused this grant to exist.
    owner_user_id: str
    owner_decision_at: float
    owner_decision_via: str


def purpose_hash(material: object) -> str:
    """Stable digest of what the consultation is FOR.

    Binding the purpose is what stops an approval for one question from
    funding a different one.
    """
    blob = json.dumps(material, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _envelope(
    *, source: ExternalSource, operation: str, purpose: str,
    model: str | None, expires_at: float,
) -> dict:
    return {
        "source": source.value,
        "operation": operation,
        "purpose_hash": purpose,
        "max_calls": MAX_CALLS,
        "expires_at": expires_at,
        "model": model,
    }


def request_authorization(
    *,
    source: ExternalSource,
    operation: str,
    purpose: object,
    model: str | None = None,
    ttl_s: float = DEFAULT_TTL_S,
    plain_english: str,
    store: PendingCardStore | None = None,
    now: float | None = None,
):
    """Open an owner card asking to consume a metered source.

    Creates NO grant. The card is a question; only the owner's answer
    mints authority.
    """
    if operation not in NON_MUTATING_METERED_OPERATIONS:
        raise GrantRefused(
            f"{operation!r} is not a registered non-mutating metered "
            "operation — a caller may not nominate itself"
        )
    store = store or PendingCardStore()
    now = time.time() if now is None else now
    env = _envelope(
        source=source, operation=operation, purpose=purpose_hash(purpose),
        model=model, expires_at=now + float(ttl_s),
    )
    # The class must DERIVE from the envelope. If it does not, the card is
    # not a metered-consumption card and must not be created as one.
    derived = derive_work_class(action=METERED_CONSUMPTION_ACTION, params=env)
    if derived != "metered_external_resource_use":
        raise GrantRefused(
            f"envelope does not derive metered_external_resource_use "
            f"(got {derived!r}) — failing closed"
        )
    return store.create_card(
        action=METERED_CONSUMPTION_ACTION,
        params=env,
        plain_english=plain_english,
        state_fields=env,
    )


def consume(
    *,
    card_id: str,
    source: ExternalSource,
    operation: str,
    purpose: object,
    model: str | None = None,
    store: PendingCardStore | None = None,
    now: float | None = None,
) -> AuthorityBearingGrant:
    """Atomically verify and spend one bounded authorization, or raise.

    Every check runs BEFORE the transition, and the transition itself is
    the atomic single-use step. Raising leaves nothing spent.
    """
    store = store or PendingCardStore()
    now = time.time() if now is None else now

    card = store.get(card_id)
    if card is None:
        raise GrantRefused(f"no such authorization card: {card_id}")
    if card.status != CardStatus.APPROVED.value:
        raise GrantRefused(
            f"card {card_id} is {card.status!r}, not approved — an "
            "unapproved or already-spent card authorizes nothing"
        )
    if not card.resolved_by_user_id:
        raise GrantRefused(
            "approved card carries no owner decision reference; a grant "
            "must name the authority that created it"
        )

    env = card.params or {}
    expected = _envelope(
        source=source, operation=operation, purpose=purpose_hash(purpose),
        model=model, expires_at=env.get("expires_at"),
    )
    for field in ("source", "operation", "purpose_hash", "model", "max_calls"):
        if env.get(field) != expected[field]:
            raise GrantRefused(
                f"binding mismatch on {field!r}: approved "
                f"{env.get(field)!r}, requested {expected[field]!r}"
            )
    if float(env.get("expires_at") or 0) <= now:
        raise GrantRefused(f"authorization {card_id} expired")
    if derive_work_class(action=card.action, params=env) != (
        "metered_external_resource_use"
    ):
        raise GrantRefused(
            "card no longer derives metered_external_resource_use"
        )

    # THE ATOMIC STEP. A single conditional UPDATE gated on APPROVED, so
    # concurrent processes cannot both win.
    try:
        store.mark_running(card_id)
    except CardStoreError as e:
        raise GrantRefused(f"authorization already spent: {e}") from e

    return AuthorityBearingGrant(
        card_id=card_id,
        source=source,
        operation=operation,
        purpose_hash=expected["purpose_hash"],
        model=env.get("model"),
        owner_user_id=card.resolved_by_user_id,
        owner_decision_at=card.resolved_at or 0.0,
        owner_decision_via=card.resolved_via or "",
    )


def settle(
    *, card_id: str, ok: bool, detail: str = "",
    store: PendingCardStore | None = None,
) -> None:
    """Record the outcome. NOT a refund — a spent grant stays spent."""
    store = store or PendingCardStore()
    try:
        if ok:
            store.mark_done(card_id, output=detail or "consultation returned")
        else:
            store.mark_failed(card_id, detail or "consultation failed")
    except CardStoreError:
        # Settlement is bookkeeping; never let it mask the call's result.
        pass
