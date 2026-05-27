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
        ExternalSource.FRONTIER_CONSULT,
    }
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

    def summarize(self, sources: Iterable[SourceLabel]) -> InventorySummary:
        now = self._clock()
        source_availability: dict[SourceLabel, SourceAvailability] = {}
        limitations: list[AvailabilityLimitation] = []

        for source in sources:
            if source in RESERVED_SOURCES:
                source_availability[source] = SourceAvailability.RESERVED_UNAVAILABLE
                _append_once(limitations, AvailabilityLimitation.RESERVED_SOURCE_UNAVAILABLE)
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
