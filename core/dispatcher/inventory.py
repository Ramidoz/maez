"""Cached source-availability inventory for ADR 0047.

Layer 0 may ask this module whether a selected source is available. It may not
scan source content or run per-source count queries on every reply. This module
keeps the source registry explicit and returns closed availability states for
the CompositionSpec witness envelope.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable, Iterable
from dataclasses import dataclass
import time
from typing import Any

from core.dispatcher.spec import (
    AvailabilityLimitation,
    ExternalSource,
    InventoryWitness,
    SourceAvailability,
    SourceLabel,
    SubstrateSource,
)


RESERVED_SOURCES: frozenset[SourceLabel] = frozenset(
    {
        SubstrateSource.ENTITY_INDEX,
        SubstrateSource.LIVED_EPISODES,
        SubstrateSource.LIVED_GRAPH,
        SubstrateSource.WEB_FAST_TURNS,
        # FRONTIER_CONSULT was un-reserved 2026-08-28 (owner, D1 seam 2)
        # for an EXPLICIT caller/request path only. This is NOT generic
        # autonomous source selection: nothing chooses this source on
        # Maez's behalf, and no learned source preference exists. A
        # caller must name it, and consuming it still requires a bounded
        # owner grant (see PAID_SOURCES below).
    }
)

#: Sources that physically exist but spend a metered external resource.
#: Their availability answer depends on an owner grant, never on the
#: caller's wish. Kept separate from RESERVED_SOURCES because "reserved"
#: means not-yet-built while these are built and gated.
PAID_SOURCES: frozenset[SourceLabel] = frozenset(
    {ExternalSource.FRONTIER_CONSULT}
)


@dataclass(frozen=True)
class InventoryEntry:
    source: SourceLabel
    backing_store: str
    cache_key: str
    invalidation_signal: str
    max_staleness_s: float
    count_query: Callable[[], int] | None
    cursor_query: Callable[[], Hashable] | None
    privacy_gate: Callable[[], bool] = lambda: True
    is_reserved: bool = False

    @classmethod
    def reserved(
        cls,
        source: SourceLabel,
        *,
        backing_store: str,
        cache_key: str,
        invalidation_signal: str,
    ) -> "InventoryEntry":
        return cls(
            source=source,
            backing_store=backing_store,
            cache_key=cache_key,
            invalidation_signal=invalidation_signal,
            max_staleness_s=0,
            count_query=None,
            cursor_query=None,
            is_reserved=True,
        )


@dataclass(frozen=True)
class InventorySummary:
    inventory_witness: InventoryWitness
    source_availability: dict[SourceLabel, SourceAvailability]
    availability_limitations: list[AvailabilityLimitation]
    generated_at: float

    def to_spec_fields(self) -> dict[str, Any]:
        return {
            "inventory_witness": self.inventory_witness,
            "source_availability": self.source_availability,
            "availability_limitations": self.availability_limitations,
        }


@dataclass
class _CacheRecord:
    cursor: Hashable
    count: int
    seen_at: float


class InventoryRegistry:
    def __init__(
        self,
        entries: Iterable[InventoryEntry] = (),
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._entries = {entry.source: entry for entry in entries}
        self._clock = clock or time.monotonic
        self._cache: dict[str, _CacheRecord] = {}

    def register(self, entry: InventoryEntry) -> None:
        self._entries[entry.source] = entry
        self._cache.pop(entry.cache_key, None)

    def invalidate(self, cache_key: str) -> None:
        self._cache.pop(cache_key, None)

    def _paid_source_availability(self, source, now, paid_context):
        """Availability of a paid/keyed source. Consumes ZERO quota.

        Reads only local grant state and the proxy's status/budget
        interface. Never issues a completion.

        ``paid_context`` is passed per call, NOT held on the registry.
        Instance state here was a real race: one request could install
        its context, pause inside the network probe, and have another
        request's authorized context answer on its behalf.

        WITHOUT a context this reports RESERVED_UNAVAILABLE — exactly
        what a generic turn saw before paid sources existed. That is the
        owner's two-questions split made mechanical: ordinary cognition
        asks "may I generically choose this source?" and the answer stays
        no, with no probe and no leaked limitation. Only a named caller
        asking "may I, specifically, consume this?" reaches the state
        machine below.
        """
        if not paid_context:
            return (
                SourceAvailability.RESERVED_UNAVAILABLE,
                AvailabilityLimitation.RESERVED_SOURCE_UNAVAILABLE,
            )

        from core.dispatcher.paid_source_grant import GRANTS

        # 1. Is the service reachable at all? A down proxy is not an
        #    authorization problem.
        reachable = self._paid_source_reachable(source)
        if reachable is False:
            return (
                SourceAvailability.EXECUTABLE_ABSENT,
                AvailabilityLimitation.FRESH_ATTEMPT_FAILED,
            )
        if reachable is None:
            return (SourceAvailability.TIMED_OUT,
                    AvailabilityLimitation.SOURCE_TIMEOUT)

        # 2. Authorization BEFORE quota. A missing grant is reported as
        #    authorization-required even if budget happens to be full.
        caller, operation = paid_context
        if not GRANTS.is_authorized(
            source=source, caller=caller, operation=operation
        ):
            return (
                SourceAvailability.AUTHORIZATION_REQUIRED,
                AvailabilityLimitation.PAID_SOURCE_AUTHORIZATION_REQUIRED,
            )

        # 3. Only once authorized does remaining quota matter.
        budget = self._paid_source_budget(source)
        if budget is False:
            return (
                SourceAvailability.EXECUTABLE_ABSENT,
                AvailabilityLimitation.FETCH_BUDGET_EXHAUSTED,
            )
        if budget is None:
            # UNKNOWN IS NOT EXHAUSTED. can_afford() fails closed to
            # False on any read error, so using it here would report an
            # unreadable proxy as an exhausted budget — the exact
            # conflation this ordering exists to prevent.
            return (SourceAvailability.EXECUTABLE_UNKNOWN,
                    AvailabilityLimitation.INVENTORY_UNKNOWN)
        return (SourceAvailability.EXECUTABLE_PRESENT, None)

    def _paid_source_reachable(self, source):
        """True(refusable) / False(refused) / None(timeout).

        A raw accept proves something is listening, not that it is a
        healthy proxy. So this only ever downgrades: it can say
        "definitely not there", never "definitely good".
        """
        import socket
        from urllib.parse import urlparse

        from core.routing.claude_tier import PROXY_URL

        u = urlparse(PROXY_URL)
        # A URL without an explicit port takes its scheme's default, not
        # the bundled proxy's. https://proxy.example is :443, and probing
        # :11438 there would report a healthy proxy as unreachable.
        port = u.port or {"https": 443, "http": 80}.get(u.scheme) or 11438
        try:
            with socket.create_connection(
                (u.hostname or "127.0.0.1", port), timeout=1.5
            ):
                return True
        except socket.timeout:
            return None
        except OSError:
            return False

    def _paid_source_budget(self, source):
        """True(affordable) / False(exhausted) / None(unknown).

        Uses the proxy's OWN budget interface — a GET against /budget,
        not a completion. Zero quota consumed.
        """
        try:
            from core.routing import claude_tier

            b = claude_tier.budget()
        except Exception:
            return None
        entry = b.get("claude") if isinstance(b, dict) else None
        if not isinstance(entry, dict):
            return None
        # BOTH windows must be PRESENT and numeric. Defaulting a missing
        # field to 0 turned "the proxy did not tell us" into "the budget
        # is exhausted" — an incomplete answer read as a proven one, which
        # is the same conflation this three-valued return exists to stop.
        try:
            hourly = entry["hourly_remaining"]
            daily = entry["daily_remaining"]
        except (KeyError, TypeError):
            return None
        try:
            return int(hourly) >= 1 and int(daily) >= 1
        except (TypeError, ValueError):
            return None

    def summarize(
        self,
        sources: Iterable[SourceLabel],
        *,
        paid_context: tuple[str, str] | None = None,
    ) -> InventorySummary:
        now = self._clock()
        source_availability: dict[SourceLabel, SourceAvailability] = {}
        limitations: list[AvailabilityLimitation] = []

        for source in sources:
            if source in RESERVED_SOURCES:
                source_availability[source] = SourceAvailability.RESERVED_UNAVAILABLE
                _append_once(limitations, AvailabilityLimitation.RESERVED_SOURCE_UNAVAILABLE)
                continue

            if source in PAID_SOURCES:
                # ORDER IS THE CONTRACT (owner ruling 2026-08-28).
                # Authorization and remaining quota are SEPARATE facts.
                # A missing grant is never reported as budget exhaustion,
                # and an exhausted budget is never reported as
                # authorization-required.
                #
                # ZERO-QUOTA INVARIANT: every branch below reads local
                # state or the proxy's status/budget interface. None
                # issues a model completion — discovering whether a
                # source is affordable must never cost a call.
                availability, limitation = self._paid_source_availability(
                    source, now, paid_context
                )
                source_availability[source] = availability
                if limitation is not None:
                    _append_once(limitations, limitation)
                continue

            entry = self._entries.get(source)
            if entry is None:
                source_availability[source] = SourceAvailability.EXECUTABLE_UNKNOWN
                _append_once(limitations, AvailabilityLimitation.INVENTORY_UNKNOWN)
                continue

            availability, limitation = self._availability_for(entry, now)
            source_availability[source] = availability
            if limitation is not None:
                _append_once(limitations, limitation)

        return InventorySummary(
            inventory_witness=_inventory_witness(source_availability.values()),
            source_availability=source_availability,
            availability_limitations=limitations,
            generated_at=now,
        )

    def _availability_for(
        self,
        entry: InventoryEntry,
        now: float,
    ) -> tuple[SourceAvailability, AvailabilityLimitation | None]:
        if entry.is_reserved or entry.source in RESERVED_SOURCES:
            return (
                SourceAvailability.RESERVED_UNAVAILABLE,
                AvailabilityLimitation.RESERVED_SOURCE_UNAVAILABLE,
            )

        if not entry.privacy_gate():
            return SourceAvailability.PRIVACY_GATED, AvailabilityLimitation.PRIVACY_GATED

        if entry.count_query is None or entry.cursor_query is None:
            return SourceAvailability.EXECUTABLE_UNKNOWN, AvailabilityLimitation.INVENTORY_UNKNOWN

        try:
            cursor = entry.cursor_query()
            cached = self._cache.get(entry.cache_key)
            if (
                cached is not None
                and cached.cursor == cursor
                and now - cached.seen_at <= entry.max_staleness_s
            ):
                count = cached.count
            else:
                count = int(entry.count_query())
                self._cache[entry.cache_key] = _CacheRecord(
                    cursor=cursor,
                    count=count,
                    seen_at=now,
                )
        except Exception:
            return SourceAvailability.EXECUTABLE_UNKNOWN, AvailabilityLimitation.INVENTORY_UNKNOWN

        if count > 0:
            return SourceAvailability.EXECUTABLE_PRESENT, None
        return SourceAvailability.EXECUTABLE_ABSENT, AvailabilityLimitation.NO_RELEVANT_SUBSTRATE


def _append_once(
    values: list[AvailabilityLimitation],
    value: AvailabilityLimitation,
) -> None:
    if value not in values:
        values.append(value)


def _inventory_witness(availabilities: Iterable[SourceAvailability]) -> InventoryWitness:
    states = list(availabilities)
    if not states:
        return InventoryWitness.ABSENT

    if all(state == SourceAvailability.EXECUTABLE_PRESENT for state in states):
        return InventoryWitness.PRESENT
    if all(state == SourceAvailability.EXECUTABLE_ABSENT for state in states):
        return InventoryWitness.ABSENT
    if all(state == SourceAvailability.EXECUTABLE_UNKNOWN for state in states):
        return InventoryWitness.UNKNOWN
    return InventoryWitness.MIXED
