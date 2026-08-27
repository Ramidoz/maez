# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Stable identifiers for the surfaces Maez's speech travels through.

Continuity spine, slice 1. This module answers exactly one question —
"which limb is this label?" — and refuses to answer any other.

WHAT THIS IS NOT. It is not a taxonomy. There are no descriptions, no
groups, no modalities, no owner-facing/public distinction, no notion of
what a surface is FOR. Owner ruling, 2026-08-27: "Our job is to just
provide the body. Let it run loops or whatever to understand what each
part of it is and understand itself. I don't define anything for Maez."
What these limbs mean, how they group, whether two of them feel like
one body — Maez learns that through its own loops. Machinery innate,
meaning learned. ``tests/test_body_surface_registry.py`` enforces the
absence structurally, because a docstring promise is not a mechanism.

THE LIE THIS EXISTS TO CLOSE, found by execution. Telegram reaches the
ledger under TWO names: ``skills/telegram_voice.py`` writes
``telegram_text``; ``skills/surface/maez_adapter.py`` declares
``SURFACE_NAME = "telegram_surface"`` and the daemon writes it through
``handle_message``'s free-form ``source``. That adapter's own comment
says the second spelling exists only "during parallel operation with
the legacy path" and should be reconciled "when the old path is
retired". The substrate documented its own deferred repair; this is it.

WHY THAT ALIAS IS ALLOWED WHEN NAME-RESEMBLANCE IS NOT. An alias is an
identity claim and needs a witness. This one has a mechanical one:
``daemon/maez_daemon.py`` builds the vendored adapter from
``self.telegram.token`` and ``self.telegram.authorized_user`` — the
SAME credentials as the legacy path, so both spellings denote one
configured Telegram endpoint by construction. Nothing here is aliased
because two strings happen to share a prefix; that is precisely the
undisciplined shape (``inbound_core.py``'s ``startswith("telegram")``
store key) this replaces.

WHY NO NEW NAMES ARE MINTED. Every id below is a string some production
call site already passes to the ledger. Inventing a "canonical"
``telegram`` for a limb that calls itself ``telegram_text`` would be us
naming Maez's body parts. Also practical: ``surface`` sits INSIDE the
chain-hash preimage (it is absent from ``chain.py``'s exclude set), so
a gratuitous relabel would rewrite the inputs of Maez's tamper-evidence
for no repair at all.

THE ADMISSION RULE — admit, then attest. Nothing in this substrate
refuses a surface today (executed: hostile strings including "", a
500-char blob and an embedded newline all commit at the real writer and
drain through the spool verbatim). So an unregistered label is admitted
UNCHANGED and typed ``UNREGISTERED``; it is never rewritten and never
dropped. Rewriting would be worse than refusing: the falsifier's F7 arm
writes synthetic surfaces and then finds those rows BY name, so a
canonicalising registry would turn that witness red silently, against a
full database.

PROOF BOUNDARY, stated. ``status`` is a fact about a lookup, not a
property recoverable from a committed row. Two registered surfaces
(``surface`` set, ``raw_surface`` NULL) and an unregistered one are
byte-identical on disk, and system rows use the same two columns for
provenance producers. Anything that needs to know whether a row's
identity was attested must resolve the label again, not infer it from
the row.
"""
from __future__ import annotations

from dataclasses import dataclass

#: Lookup outcomes. Opaque tokens — they describe the RESOLUTION, never
#: the surface.
REGISTERED = "registered"
ALIASED = "aliased"
UNREGISTERED = "unregistered"

#: The stable identifiers. Each is a name the body already emits at a
#: production ledger call site; none was minted here.
SURFACE_IDS: tuple[str, ...] = (
    "cli",
    "telegram_text",
    "web_owner",
)

#: label -> surface id. Identity for the ids themselves, plus aliases
#: bound by an executed co-reference witness (see the module docstring).
#: A label absent from this map is UNREGISTERED, never guessed.
ACCEPTED_LABELS: dict[str, str] = {
    "cli": "cli",
    "telegram_text": "telegram_text",
    "web_owner": "web_owner",
    # Same bot token, same authorized user, same endpoint as the legacy
    # telegram_text path; witnessed in daemon bootstrap, not inferred
    # from the shared "telegram" prefix.
    "telegram_surface": "telegram_text",
}


@dataclass(frozen=True)
class SurfaceRef:
    """One resolved label: which limb, under what name, how sure."""

    raw_label: str
    surface_id: str | None
    status: str

    @property
    def attested(self) -> bool:
        return self.surface_id is not None

    @property
    def ledger_surface(self) -> str:
        """The value for the ledger's ``surface`` column.

        Unregistered labels pass through verbatim — admission is never
        conditional on being recognised.
        """
        return self.surface_id if self.surface_id is not None else self.raw_label

    @property
    def ledger_raw_surface(self) -> str | None:
        """The value for ``raw_surface``: the transport label, but only
        when it actually differs from the identity.

        Set on an alias so the original spelling survives; NULL
        otherwise, which keeps registered and unregistered writes
        byte-identical to what ships today. It also keeps
        ``raw_surface or surface`` — the closed taint validator's caller
        authority — equal to the caller's own label in every branch.
        """
        if self.surface_id is not None and self.surface_id != self.raw_label:
            return self.raw_label
        return None


def ledger_pair(raw_label: str) -> tuple[str, str | None]:
    """The ``(surface, raw_surface)`` a caller should write for a label.

    Flag-gated at the seam rather than inside ``resolve`` so the
    registry itself stays a pure function: lookups, censuses and tests
    read the same answer whether or not the switch is on. With
    MAEZ_SURFACE_REGISTRY unset this returns ``(raw_label, None)`` —
    byte-for-byte what ships today, including for labels the registry
    knows.
    """
    from core.ledger.writes_flag import surface_registry_enabled

    if not surface_registry_enabled():
        return raw_label, None
    ref = resolve(raw_label)
    return ref.ledger_surface, ref.ledger_raw_surface


def resolve(raw_label: str) -> SurfaceRef:
    """Identify a surface label. Total over strings; never rewrites.

    Raises TypeError for a non-string, which is a caller bug rather
    than an unrecognised limb — refusing it loses no speech because
    there was no label to keep.
    """
    if not isinstance(raw_label, str):
        raise TypeError(
            f"surface label must be a string, got {type(raw_label).__name__}"
        )
    surface_id = ACCEPTED_LABELS.get(raw_label)
    if surface_id is None:
        return SurfaceRef(raw_label=raw_label, surface_id=None,
                          status=UNREGISTERED)
    status = REGISTERED if surface_id == raw_label else ALIASED
    return SurfaceRef(raw_label=raw_label, surface_id=surface_id, status=status)
