# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""M1 lived-episode promotion from bonded conversation.

Decision 25 / ADR 0030: promote biography; do not widen recall.
This module owns the pure promotion mechanics. Daemon code wires it after
audited Telegram storage and during daemon-cycle flush.
"""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Sequence


_MARKERS = (
    "remember this",
    "don't forget this",
    "do not forget this",
    "this matters",
    "mark this",
    "save this",
)

_NEGATED_MARKERS = (
    "don't remember this",
    "do not remember this",
    "don't save this",
    "do not save this",
    "don't mark this",
    "do not mark this",
)

VALID_ELIGIBILITY_REASONS = frozenset(
    {
        "explicit_marker",
        "open_loop",
        "correction",
        "commitment",
        "owner_affect",
    }
)

VALID_PROMOTION_TRIGGERS = frozenset(
    {
        "explicit_marker",
        "turn_count_boundary",
        "silence_boundary",
    }
)

_THIRD_PARTY_MARKER_REPORT = re.compile(
    r"\b("
    r"he|she|they|someone|somebody|"
    r"my\s+\w+|[a-z][a-z]+|"
    r"claude|codex|gemini"
    r")\s+(said|told\s+me|asked\s+me|wanted\s+me\s+to)\b.*"
    r"(remember\s+this|save\s+this|mark\s+this|don't\s+forget\s+this|"
    r"do\s+not\s+forget\s+this|this\s+matters)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class M1Config:
    enabled: bool = False
    silence_boundary_seconds: int = 900
    max_turn_pairs: int = 4
    max_promotions_per_day: int = 8
    producer_version: str = "m1.v1"


@dataclass(frozen=True)
class PendingWindow:
    window_id: str
    source_memory_ids: list[str]
    first_owner_at: str
    last_owner_at: str
    pair_count: int
    explicit_marker_seen: bool = False
    promotion_state: str = "pending"
    last_flush_checked_at: str | None = None
    eligibility_reasons: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _validate_eligibility_reasons(self.eligibility_reasons)

    def __repr__(self) -> str:
        return (
            "PendingWindow("
            f"window_id={self.window_id!r}, "
            f"source_memory_ids={self.source_memory_ids!r}, "
            f"first_owner_at={self.first_owner_at!r}, "
            f"last_owner_at={self.last_owner_at!r}, "
            f"pair_count={self.pair_count!r}, "
            f"explicit_marker_seen={self.explicit_marker_seen!r}, "
            f"promotion_state={self.promotion_state!r}, "
            f"last_flush_checked_at={self.last_flush_checked_at!r}, "
            f"eligibility_reasons={self.eligibility_reasons!r})"
        )


@dataclass(frozen=True)
class PromotionOutcome:
    promoted: bool
    episode_id: str | None = None
    skipped_reason: str | None = None
    source_id_count: int = 0


_SCHEMA = """
CREATE TABLE IF NOT EXISTS pending_window (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    window_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_index (
    source_memory_id TEXT PRIMARY KEY,
    episode_id TEXT NOT NULL,
    window_id TEXT NOT NULL,
    promoted_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS promotion_provenance (
    episode_id TEXT PRIMARY KEY,
    provenance_json TEXT NOT NULL
);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_iso(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _json_dumps(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _owner_display_name() -> str:
    try:
        from core.identity import display_name

        name = (display_name() or "").strip()
    except Exception:
        name = ""
    return name or "Friend"


def _validate_eligibility_reason(reason: str) -> str:
    normalized = (reason or "").strip()
    if normalized not in VALID_ELIGIBILITY_REASONS:
        raise ValueError(f"invalid M1 eligibility reason: {reason!r}")
    return normalized


def _validate_eligibility_reasons(reasons: Sequence[str]) -> list[str]:
    return [_validate_eligibility_reason(str(reason)) for reason in reasons]


def _validate_promotion_trigger(trigger: str) -> str:
    normalized = (trigger or "").strip()
    if normalized not in VALID_PROMOTION_TRIGGERS:
        raise ValueError(f"invalid M1 promotion trigger: {trigger!r}")
    return normalized


def marker_is_owner_authored(text: str) -> bool:
    """Return true for direct owner-authored marker phrases only."""

    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    if any(phrase in lowered for phrase in _NEGATED_MARKERS):
        return False
    if _THIRD_PARTY_MARKER_REPORT.search(lowered):
        return False
    if "quoting" in lowered:
        return False
    if re.search(r"['\"].*(remember this|save this|mark this|this matters).*['\"]", lowered):
        return False
    return any(marker in lowered for marker in _MARKERS)


def _eligibility_reasons(owner_text: str, *, explicit_marker: bool) -> list[str]:
    lowered = (owner_text or "").lower()
    reasons: list[str] = []
    if explicit_marker:
        reasons.append("explicit_marker")
    if any(p in lowered for p in ("we need to revisit", "still pending", "we have not finished")):
        reasons.append("open_loop")
    if any(p in lowered for p in ("correction:", "actually,", "i was wrong")):
        reasons.append("correction")
    if any(p in lowered for p in ("i promise", "i will", "we will", "commit to")):
        reasons.append("commitment")
    if re.search(r"\b(i feel|i'm feeling|i am feeling|i felt)\b", lowered):
        reasons.append("owner_affect")
    return list(dict.fromkeys(reasons))


def build_structural_summary(
    *,
    pair_count: int,
    start_at: str,
    end_at: str,
    trigger: str,
    reason: str,
    owner_display_name: str | None = None,
) -> str:
    owner_name = (owner_display_name or "").strip() or _owner_display_name()
    pair_label = "pair" if int(pair_count) == 1 else "pairs"
    if int(pair_count) == 1:
        return (
            f"Bonded Telegram exchange. 1 audited owner/Maez pair at {start_at}. "
            f"Participants: {owner_name}, Maez. Owner-initiated; promoted by {reason}."
        )[:400]
    return (
        f"Bonded Telegram exchange. {int(pair_count)} audited owner/Maez {pair_label} "
        f"between {start_at} and {end_at}. Participants: {owner_name}, Maez. "
        f"Owner-initiated; concluded by {trigger}; promoted by {reason}."
    )[:400]


class M1PromotionStore:
    """Sidecar state for pending M1 windows and source-ID idempotency."""

    def __init__(self, db_path: str):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn:
            with conn:
                conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), timeout=0.15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 150")
        return conn

    def load_pending_window(self) -> PendingWindow:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT window_json FROM pending_window WHERE id = 1").fetchone()
        if row is None:
            return PendingWindow(
                window_id="m1-window-1",
                source_memory_ids=[],
                first_owner_at="",
                last_owner_at="",
                pair_count=0,
            )
        data = json.loads(row["window_json"])
        return PendingWindow(
            window_id=str(data.get("window_id") or "m1-window-1"),
            source_memory_ids=list(data.get("source_memory_ids") or []),
            first_owner_at=str(data.get("first_owner_at") or ""),
            last_owner_at=str(data.get("last_owner_at") or ""),
            pair_count=int(data.get("pair_count") or 0),
            explicit_marker_seen=bool(data.get("explicit_marker_seen") or False),
            promotion_state=str(data.get("promotion_state") or "pending"),
            last_flush_checked_at=data.get("last_flush_checked_at"),
            eligibility_reasons=list(data.get("eligibility_reasons") or []),
        )

    def save_pending_window(self, window: PendingWindow) -> None:
        payload = {
            "window_id": window.window_id,
            "source_memory_ids": list(window.source_memory_ids),
            "first_owner_at": window.first_owner_at,
            "last_owner_at": window.last_owner_at,
            "pair_count": int(window.pair_count),
            "explicit_marker_seen": bool(window.explicit_marker_seen),
            "promotion_state": window.promotion_state,
            "last_flush_checked_at": window.last_flush_checked_at,
            "eligibility_reasons": list(window.eligibility_reasons),
        }
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    "INSERT INTO pending_window (id, window_json) VALUES (1, ?) "
                    "ON CONFLICT(id) DO UPDATE SET window_json = excluded.window_json",
                    (_json_dumps(payload),),
                )

    def clear_pending_window(self) -> None:
        with closing(self._connect()) as conn:
            with conn:
                conn.execute("DELETE FROM pending_window WHERE id = 1")

    def promoted_source_ids(self, source_memory_ids: Sequence[str]) -> set[str]:
        ids = [sid for sid in source_memory_ids if sid]
        if not ids:
            return set()
        placeholders = ",".join("?" for _ in ids)
        with closing(self._connect()) as conn:
            rows = conn.execute(
                f"SELECT source_memory_id FROM source_index WHERE source_memory_id IN ({placeholders})",
                ids,
            ).fetchall()
        return {str(row["source_memory_id"]) for row in rows}

    def filter_unpromoted(self, source_memory_ids: Sequence[str]) -> list[str]:
        promoted = self.promoted_source_ids(source_memory_ids)
        return [sid for sid in source_memory_ids if sid and sid not in promoted]

    def rebuild_source_index_from_episodes(self, episode_store) -> None:
        """Recover idempotency if the M1 sidecar is restored behind biography."""

        try:
            active = episode_store.list_active()
        except Exception:
            return
        with closing(self._connect()) as conn:
            with conn:
                for ep in active:
                    if ep.get("source_kind") != "telegram_exchange":
                        continue
                    episode_id = str(ep.get("id") or "")
                    if not episode_id:
                        continue
                    promoted_at = str(
                        ep.get("created_at") or ep.get("occurred_at") or _now_iso()
                    )
                    for sid in ep.get("source_memory_ids") or []:
                        if not sid:
                            continue
                        conn.execute(
                            "INSERT OR IGNORE INTO source_index "
                            "(source_memory_id, episode_id, window_id, promoted_at) "
                            "VALUES (?, ?, ?, ?)",
                            (str(sid), episode_id, "reconstructed", promoted_at),
                        )

    def mark_promoted(
        self,
        *,
        source_memory_ids: Sequence[str],
        episode_id: str,
        window_id: str,
        promoted_at: str,
        provenance: dict,
    ) -> None:
        with closing(self._connect()) as conn:
            with conn:
                for sid in source_memory_ids:
                    conn.execute(
                        "INSERT OR IGNORE INTO source_index "
                        "(source_memory_id, episode_id, window_id, promoted_at) "
                        "VALUES (?, ?, ?, ?)",
                        (sid, episode_id, window_id, promoted_at),
                    )
                conn.execute(
                    "INSERT OR REPLACE INTO promotion_provenance "
                    "(episode_id, provenance_json) VALUES (?, ?)",
                    (episode_id, _json_dumps(provenance)),
                )

    def count_promotions_since(self, since_iso: str) -> int:
        since = _parse_iso(since_iso).astimezone(timezone.utc)
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT episode_id, promoted_at FROM source_index").fetchall()
        counted: set[str] = set()
        for row in rows:
            try:
                promoted_at = _parse_iso(str(row["promoted_at"])).astimezone(timezone.utc)
            except Exception:
                continue
            if promoted_at >= since:
                counted.add(str(row["episode_id"]))
        return len(counted)

    def get_provenance(self, episode_id: str) -> dict:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT provenance_json FROM promotion_provenance WHERE episode_id = ?",
                (episode_id,),
            ).fetchone()
        if row is None:
            return {}
        return dict(json.loads(row["provenance_json"]))


class M1LivedEpisodePromoter:
    def __init__(
        self,
        *,
        episode_store,
        promotion_store: M1PromotionStore,
        config: M1Config | None = None,
        now_fn: Callable[[], datetime] | None = None,
    ):
        self.episode_store = episode_store
        self.promotion_store = promotion_store
        self.config = config or M1Config()
        self.now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self.promotion_store.rebuild_source_index_from_episodes(self.episode_store)

    def consider_audited_exchange(
        self,
        *,
        owner_text: str,
        maez_reply: str,
        raw_memory_id: str,
        occurred_at: str,
    ) -> PromotionOutcome:
        if not self.config.enabled:
            return PromotionOutcome(False, skipped_reason="disabled")
        if not raw_memory_id:
            return PromotionOutcome(False, skipped_reason="no_source_id")

        if marker_is_owner_authored(owner_text):
            outcome = self.promote_window(
                source_memory_ids=[raw_memory_id],
                first_owner_at=occurred_at,
                last_owner_at=occurred_at,
                pair_count=1,
                trigger="explicit_marker",
                reason="explicit_marker",
            )
            if outcome.skipped_reason == "rate_limited":
                self.promotion_store.save_pending_window(
                    PendingWindow(
                        window_id="m1-window-1",
                        source_memory_ids=[raw_memory_id],
                        first_owner_at=occurred_at,
                        last_owner_at=occurred_at,
                        pair_count=1,
                        explicit_marker_seen=True,
                        promotion_state="deferred_rate_limited",
                        eligibility_reasons=["explicit_marker"],
                    )
                )
                return outcome
            self.promotion_store.clear_pending_window()
            return outcome

        reasons = _eligibility_reasons(owner_text, explicit_marker=False)
        window = self._append_to_window(
            raw_memory_id=raw_memory_id,
            occurred_at=occurred_at,
            explicit_marker=False,
            eligibility_reasons=reasons,
        )

        if window.pair_count >= self.config.max_turn_pairs:
            if window.eligibility_reasons:
                reason = window.eligibility_reasons[0]
                outcome = self.promote_window(
                    source_memory_ids=window.source_memory_ids,
                    first_owner_at=window.first_owner_at,
                    last_owner_at=window.last_owner_at,
                    pair_count=window.pair_count,
                    trigger="turn_count_boundary",
                    reason=reason,
                    window_id=window.window_id,
                )
                if outcome.skipped_reason == "rate_limited":
                    self.promotion_store.save_pending_window(
                        PendingWindow(
                            window_id=window.window_id,
                            source_memory_ids=window.source_memory_ids,
                            first_owner_at=window.first_owner_at,
                            last_owner_at=window.last_owner_at,
                            pair_count=window.pair_count,
                            explicit_marker_seen=window.explicit_marker_seen,
                            promotion_state="deferred_rate_limited",
                            eligibility_reasons=window.eligibility_reasons,
                        )
                    )
                    return outcome
                self.promotion_store.clear_pending_window()
                return outcome
            self.promotion_store.clear_pending_window()
            return PromotionOutcome(False, skipped_reason="not_eligible")

        return PromotionOutcome(False, skipped_reason="pending")

    def _append_to_window(
        self,
        *,
        raw_memory_id: str,
        occurred_at: str,
        explicit_marker: bool,
        eligibility_reasons: Sequence[str],
    ) -> PendingWindow:
        current = self.promotion_store.load_pending_window()
        source_ids = list(current.source_memory_ids)
        if raw_memory_id not in source_ids:
            source_ids.append(raw_memory_id)
        first_owner_at = current.first_owner_at or occurred_at
        reasons = list(dict.fromkeys([*current.eligibility_reasons, *eligibility_reasons]))
        next_window = PendingWindow(
            window_id=current.window_id or "m1-window-1",
            source_memory_ids=source_ids,
            first_owner_at=first_owner_at,
            last_owner_at=occurred_at,
            pair_count=int(current.pair_count) + 1,
            explicit_marker_seen=bool(current.explicit_marker_seen or explicit_marker),
            promotion_state="pending",
            last_flush_checked_at=current.last_flush_checked_at,
            eligibility_reasons=reasons,
        )
        self.promotion_store.save_pending_window(next_window)
        return next_window

    def flush_due_windows(self) -> list[PromotionOutcome]:
        if not self.config.enabled:
            return []
        window = self.promotion_store.load_pending_window()
        now = self.now_fn()
        checked = PendingWindow(
            window_id=window.window_id,
            source_memory_ids=window.source_memory_ids,
            first_owner_at=window.first_owner_at,
            last_owner_at=window.last_owner_at,
            pair_count=window.pair_count,
            explicit_marker_seen=window.explicit_marker_seen,
            promotion_state=window.promotion_state,
            last_flush_checked_at=now.isoformat(),
            eligibility_reasons=window.eligibility_reasons,
        )
        self.promotion_store.save_pending_window(checked)
        if not window.source_memory_ids or not window.last_owner_at:
            return []
        try:
            elapsed = (now - _parse_iso(window.last_owner_at)).total_seconds()
        except Exception:
            return [PromotionOutcome(False, skipped_reason="invalid_pending_timestamp")]
        if elapsed < self.config.silence_boundary_seconds:
            return []
        if not window.eligibility_reasons:
            self.promotion_store.clear_pending_window()
            return [PromotionOutcome(False, skipped_reason="not_eligible")]
        outcome = self.promote_window(
            source_memory_ids=window.source_memory_ids,
            first_owner_at=window.first_owner_at,
            last_owner_at=window.last_owner_at,
            pair_count=window.pair_count,
            trigger="silence_boundary",
            reason=window.eligibility_reasons[0],
            window_id=window.window_id,
        )
        if outcome.skipped_reason == "rate_limited":
            self.promotion_store.save_pending_window(
                PendingWindow(
                    window_id=window.window_id,
                    source_memory_ids=window.source_memory_ids,
                    first_owner_at=window.first_owner_at,
                    last_owner_at=window.last_owner_at,
                    pair_count=window.pair_count,
                    explicit_marker_seen=window.explicit_marker_seen,
                    promotion_state="deferred_rate_limited",
                    last_flush_checked_at=now.isoformat(),
                    eligibility_reasons=window.eligibility_reasons,
                )
            )
            return [outcome]
        self.promotion_store.clear_pending_window()
        return [outcome]

    def promote_window(
        self,
        *,
        source_memory_ids: Sequence[str],
        first_owner_at: str,
        last_owner_at: str,
        pair_count: int,
        trigger: str,
        reason: str,
        window_id: str = "m1-window-1",
    ) -> PromotionOutcome:
        trigger = _validate_promotion_trigger(trigger)
        reason = _validate_eligibility_reason(reason)
        unpromoted = self.promotion_store.filter_unpromoted(source_memory_ids)
        if not unpromoted:
            return PromotionOutcome(False, skipped_reason="duplicate_source")
        if len(unpromoted) < len([sid for sid in source_memory_ids if sid]):
            return PromotionOutcome(False, skipped_reason="partial_overlap")

        now = self.now_fn().astimezone(timezone.utc)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if self.promotion_store.count_promotions_since(day_start.isoformat()) >= int(
            self.config.max_promotions_per_day
        ):
            return PromotionOutcome(False, skipped_reason="rate_limited")

        promoted_at = now.isoformat(timespec="seconds")
        owner_name = _owner_display_name()
        summary = build_structural_summary(
            pair_count=len(unpromoted),
            start_at=first_owner_at,
            end_at=last_owner_at,
            trigger=trigger,
            reason=reason,
            owner_display_name=owner_name,
        )
        episode_id = self.episode_store.add(
            title=f"Bonded conversation with {owner_name}",
            summary=summary,
            participants=[owner_name, "Maez"],
            source_memory_ids=unpromoted,
            source_kind="telegram_exchange",
            occurred_at=first_owner_at,
            importance=3,
            authorship="bonded_dialogue",
            memory_voice="mixed_owner_maez",
        )
        provenance = {
            "producer_version": self.config.producer_version,
            "promotion_trigger": trigger,
            "promotion_reason": reason,
            "promoted_at": promoted_at,
            "window_start": first_owner_at,
            "window_end": last_owner_at,
            "consent_posture": "bonded_user_dialogue",
            "source_id_count": len(unpromoted),
        }
        self.promotion_store.mark_promoted(
            source_memory_ids=unpromoted,
            episode_id=episode_id,
            window_id=window_id,
            promoted_at=promoted_at,
            provenance=provenance,
        )
        return PromotionOutcome(True, episode_id=episode_id, source_id_count=len(unpromoted))

    def status_health(self) -> dict:
        window = self.promotion_store.load_pending_window()
        return {
            "enabled": bool(self.config.enabled),
            "pending_source_count": len(window.source_memory_ids),
            "pending_state": window.promotion_state,
            "last_flush_checked_at": window.last_flush_checked_at,
        }


def _iter_active_episode_times(active_episodes: Iterable[dict]) -> Iterable[datetime]:
    for ep in active_episodes:
        raw = ep.get("occurred_at") or ep.get("created_at")
        if not raw:
            continue
        try:
            yield _parse_iso(str(raw))
        except Exception:
            continue


def biography_staleness_health(
    episode_store,
    *,
    now: datetime | None = None,
) -> dict:
    now = now or datetime.now(timezone.utc)
    try:
        aggregate = getattr(episode_store, "active_count_and_newest_time", None)
        if callable(aggregate):
            active_count, newest_raw = aggregate()
        else:
            active = episode_store.list_active()
            active_count = len(active)
            newest = max(_iter_active_episode_times(active), default=None)
            newest_raw = newest.isoformat() if newest is not None else None
        if not active_count:
            return {
                "active_count": 0,
                "newest_created_at": None,
                "newest_age_hours": None,
                "staleness_status": "empty",
            }
        newest = _parse_iso(str(newest_raw)) if newest_raw else None
        if newest is None:
            return {
                "active_count": active_count,
                "newest_created_at": None,
                "newest_age_hours": None,
                "staleness_status": "unavailable",
            }
        age_hours = max(0.0, (now - newest).total_seconds() / 3600.0)
        if age_hours > 168:
            status = "alarm"
        elif age_hours > 48:
            status = "warn"
        else:
            status = "ok"
        return {
            "active_count": active_count,
            "newest_created_at": newest.isoformat(),
            "newest_age_hours": age_hours,
            "staleness_status": status,
        }
    except Exception as exc:
        return {
            "active_count": None,
            "newest_created_at": None,
            "newest_age_hours": None,
            "staleness_status": "unavailable",
            "error": str(exc)[:120],
        }
