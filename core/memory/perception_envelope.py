# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
core/perception_envelope.py — 11b backfill, staging-only.

The envelope is the SINGLE struct the fast reply hot path consumes. It is
built by reading from the perception cache and never invokes any synchronous
perception itself.

Contract:
  build_envelope(cache) -> PerceptionEnvelope

  PerceptionEnvelope.screen        -> EnvelopeSource
  PerceptionEnvelope.system_state  -> EnvelopeSource
  PerceptionEnvelope.built_at      -> unix ts
  PerceptionEnvelope.build_ms      -> int

Each EnvelopeSource carries:
  has_value, value, age_ms, freshness_state, error, version

The hot path uses freshness_state + has_value to decide whether to inject
the value into the prompt at all. Stale and errored sources are still
readable; the prompt builder degrades gracefully.

Future fast-lane integration will:
  • Add more sources (calendar, github, presence) without changing this API.
  • Add a max-age policy per source for hard exclusion in the prompt.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from core.perception_cache import (
    PerceptionCache,
    CacheEntry,
    MISSING,
)


# Sources the envelope cares about for the fast lane.
# Order is significant — it controls the order they appear in the prompt.
# Session 11c: screen + system_state.
# Session 11d: + calendar (third worker landed).
ENVELOPE_SOURCES: tuple[str, ...] = ('screen', 'system_state', 'calendar')


@dataclass
class EnvelopeSource:
    name: str
    has_value: bool
    value: Any
    age_ms: int
    freshness_state: str
    error: Optional[str]
    version: int

    @classmethod
    def from_entry(cls, name: str, entry: Optional[CacheEntry]) -> 'EnvelopeSource':
        if entry is None:
            return cls(
                name=name,
                has_value=False,
                value=None,
                age_ms=-1,
                freshness_state=MISSING,
                error=None,
                version=0,
            )
        return cls(
            name=name,
            has_value=entry.value is not None,
            value=entry.value,
            age_ms=entry.age_ms,
            freshness_state=entry.freshness_state,
            error=entry.error,
            version=entry.version,
        )

    @property
    def is_usable(self) -> bool:
        """True if this source has SOME value worth showing the model.
        STALE and ERROR are still usable (caller decides). MISSING is not."""
        return self.has_value and self.freshness_state != MISSING


@dataclass
class PerceptionEnvelope:
    sources: dict[str, EnvelopeSource] = field(default_factory=dict)
    built_at: float = 0.0
    build_ms: int = 0

    @property
    def screen(self) -> EnvelopeSource:
        return self.sources['screen']

    @property
    def system_state(self) -> EnvelopeSource:
        return self.sources['system_state']

    @property
    def calendar(self) -> EnvelopeSource:
        return self.sources['calendar']

    def get(self, name: str) -> Optional[EnvelopeSource]:
        return self.sources.get(name)


def build_envelope(cache: PerceptionCache) -> PerceptionEnvelope:
    """Read the cache and assemble the envelope. NEVER calls perception code.

    This is the only allowed entry point on the fast reply hot path for
    perception data. If a caller wants something not in ENVELOPE_SOURCES,
    add it here, don't add an ad-hoc cache.get() call elsewhere — keeping
    the read path centralized is what enforces the no-sync-perception
    invariant for Session 11c."""
    t0 = time.perf_counter()
    out = PerceptionEnvelope()
    for name in ENVELOPE_SOURCES:
        entry = cache.get(name)              # cache.get is read-only and instant
        out.sources[name] = EnvelopeSource.from_entry(name, entry)
    out.built_at = time.time()
    out.build_ms = int((time.perf_counter() - t0) * 1000)
    return out
