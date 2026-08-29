# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Bounded one-shot grants for paid/keyed external sources.

Owner-authorized 2026-08-28 (D1 seam 2). Deliberately minimal: this is
NOT a spending policy, NOT a standing allowance, and NOT autonomous
quota management. It exists so a paid source can be gated by an
explicit, bounded owner grant instead of by an action lane.

Why grants are bound to more than "yes": a generic approval must not
silently become unlimited frontier spend. Each grant binds the SOURCE,
the intended CALLER/operation, a call COUNT (initially 1) and an
expiry, and is consumed atomically.

AUTHORIZATION AND QUOTA ARE SEPARATE FACTS. This module answers only
"may it be consumed"; remaining budget is the proxy's answer and must
not be reported as an authorization problem, or vice versa.

**ZERO-QUOTA INVARIANT:** nothing here issues a model completion.
Deciding availability uses local state only. Discovering whether a
source is affordable must never cost a call.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field

from core.dispatcher.spec import SourceLabel


@dataclass(frozen=True)
class PaidSourceGrant:
    """One bounded authorization to consume a paid source."""

    grant_id: str
    source: SourceLabel
    caller: str
    operation: str
    max_calls: int
    expires_at: float
    model: str | None = None

    def __post_init__(self) -> None:
        if self.max_calls < 1:
            raise ValueError("a grant must permit at least one call")
        if not str(self.caller).strip() or not str(self.operation).strip():
            raise ValueError(
                "a grant must name its caller and operation — an unbound "
                "approval is how a single yes becomes unlimited spend"
            )


class GrantLedger:
    """Process-local store of bounded grants. Not autobiographical."""

    def __init__(self, clock=None) -> None:
        self._clock = clock or time.time
        self._lock = threading.Lock()
        self._grants: dict[str, PaidSourceGrant] = {}
        self._used: dict[str, int] = {}

    def grant(
        self,
        *,
        source: SourceLabel,
        caller: str,
        operation: str,
        max_calls: int = 1,
        ttl_s: float = 900.0,
        model: str | None = None,
    ) -> PaidSourceGrant:
        g = PaidSourceGrant(
            grant_id=uuid.uuid4().hex,
            source=source,
            caller=caller,
            operation=operation,
            max_calls=int(max_calls),
            expires_at=self._clock() + float(ttl_s),
            model=model,
        )
        with self._lock:
            self._grants[g.grant_id] = g
            self._used[g.grant_id] = 0
        return g

    def _live_grant(self, source, caller, operation):
        now = self._clock()
        for gid, g in self._grants.items():
            if (
                g.source == source
                and g.caller == caller
                and g.operation == operation
                and g.expires_at > now
                and self._used.get(gid, 0) < g.max_calls
            ):
                return gid, g
        return None, None

    def is_authorized(self, *, source, caller: str, operation: str) -> bool:
        """Local-only check. Issues NO model call (zero-quota invariant)."""
        with self._lock:
            gid, _ = self._live_grant(source, caller, operation)
            return gid is not None

    def consume(self, *, source, caller: str, operation: str) -> PaidSourceGrant:
        """Atomically spend one call from a live grant, or raise."""
        with self._lock:
            gid, g = self._live_grant(source, caller, operation)
            if gid is None:
                raise PermissionError(
                    f"no live grant for {source} / {caller} / {operation} — "
                    "a paid source may not be consumed without one"
                )
            self._used[gid] += 1
            return g

    def remaining(self, grant_id: str) -> int:
        with self._lock:
            g = self._grants.get(grant_id)
            if g is None:
                return 0
            return max(0, g.max_calls - self._used.get(grant_id, 0))


#: Process-local default. Grants do not survive a restart BY DESIGN —
#: a spend authorization should not outlive the conversation that gave it.
GRANTS = GrantLedger()
