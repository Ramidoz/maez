# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""D20 Stage-1 chat-surface gap detector.

The orchestrator (capability_orchestrator) is operator-driven —
the caller passes a felt-limitation string. Stage 1 makes Maez
recognise its own limitations from natural conversation: this
module watches user messages, runs them through the same lexical
matcher the orchestrator uses, and flags strong matches above a
threshold so the producer (chat path / daemon / future audit
hook) can fire the orchestrator without operator action.

Two gates protect against spam:

  threshold: weak matches don't fire. The matcher's score is in
    [0, 1]; default 0.3 was chosen by pinging seed-entry signals
    against natural-text probes — temporal "when did X happen?"
    scores ~0.45, RCE "audit-style summary" scores ~0.4, casual
    chat ("hello there friend") scores 0. 0.3 catches direct
    signal hits without false-positiving on common-token overlap.

  cooldown_s: per-capability_id rate limit. After a fire for cap
    X, the next ``cooldown_s`` seconds suppress further fires for
    X (other capabilities are unaffected). Default 24h: a gap
    you saw yesterday and didn't act on probably doesn't deserve
    a second card today; the existing card is still pending. The
    cooldown is per-capability so two different gaps in the same
    conversation can both fire.

The detector itself is fail-closed: any internal exception
returns a benign empty result so the caller's hot path is never
broken by detector flakiness.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from core.infra.capability_gap_matcher import match_gap

logger = logging.getLogger("maez.capability_gap_detector")

DB_PATH = Path(
    os.environ.get(
        "MAEZ_GAP_DETECTOR_DB",
        str(Path(__file__).resolve().parent.parent.parent
            / "memory" / "capability_gap_cooldown.db"),
    )
)


@dataclass
class DetectorResult:
    """Output of one detection pass.

    fired_for: the single highest-scoring match that cleared
        threshold AND wasn't cooldown-blocked. Producer should
        call orchestrate_from_felt_limitation when this is set.
        None when nothing fires (no match / weak match / all
        cooldown-blocked).

    matches_above_threshold: every match above threshold,
        regardless of cooldown. Lets callers log what would have
        fired in a "no cooldown" world.

    cooldown_blocked: capability_ids that scored above threshold
        but were suppressed by cooldown. Useful telemetry.
    """
    fired_for: Optional[Any] = None  # CapabilityMatch when set
    matches_above_threshold: list = field(default_factory=list)
    cooldown_blocked: list[str] = field(default_factory=list)


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=2.0)
    # WAL allows concurrent readers + a writer without "database
    # is locked" errors on the hot-path producer (chat handler
    # firing while daemon cycle could fire its own check). Cheap.
    con.execute("PRAGMA journal_mode=WAL")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS gap_fires (
            capability_id TEXT PRIMARY KEY,
            last_fired_at REAL NOT NULL
        )
        """
    )
    con.commit()
    return con


def _last_fired_at(capability_id: str) -> Optional[float]:
    try:
        with _connect() as con:
            row = con.execute(
                "SELECT last_fired_at FROM gap_fires "
                "WHERE capability_id = ?",
                (capability_id,),
            ).fetchone()
            return row[0] if row else None
    except Exception as e:
        logger.debug("gap_detector: cooldown read failed: %s", e)
        return None


def _record_fire(capability_id: str, *, ts: Optional[float] = None) -> None:
    try:
        with _connect() as con:
            con.execute(
                "INSERT OR REPLACE INTO gap_fires "
                "(capability_id, last_fired_at) VALUES (?, ?)",
                (capability_id, ts if ts is not None else time.time()),
            )
            con.commit()
    except Exception as e:
        logger.debug("gap_detector: cooldown write failed: %s", e)


def detect_gap(
    user_text: str,
    *,
    threshold: float = 0.3,
    cooldown_s: float = 24 * 3600,
    manual: Any = None,
) -> DetectorResult:
    """Scan ``user_text`` for capability gap signals. Return the
    single highest-scoring match that clears both threshold and
    cooldown gates, or DetectorResult(fired_for=None) if nothing
    qualifies.

    Args:
        user_text: the user's most recent message. Empty / blank
            returns empty result without DB hits.
        threshold: minimum match score in [0, 1] to consider.
            Default 0.3 — calibrated against seed-entry signals.
        cooldown_s: per-capability suppression window. After
            firing for cap X, X is blocked for this many seconds.
            Set to 0 to disable cooldown (every detection fires).
            Default 24h.
        manual: optional pre-loaded ManualLoadResult passed to
            match_gap; None lets the matcher use the default.
    """
    if not user_text or not user_text.strip():
        return DetectorResult()

    try:
        all_matches = match_gap(user_text, manual=manual)
    except Exception as e:
        logger.debug("gap_detector: match_gap failed: %s", e)
        return DetectorResult()

    above = [m for m in all_matches if m.score >= threshold]
    if not above:
        return DetectorResult(matches_above_threshold=[])

    result = DetectorResult(matches_above_threshold=list(above))

    # Walk in score order; first cap not in cooldown wins. Cooldown-
    # blocked caps go in the telemetry list.
    now = time.time()
    for m in above:
        if cooldown_s > 0:
            last = _last_fired_at(m.capability_id)
            if last is not None and (now - last) < cooldown_s:
                result.cooldown_blocked.append(m.capability_id)
                continue
        # Winner
        result.fired_for = m
        _record_fire(m.capability_id, ts=now)
        return result

    return result


# ── high-level fire-and-forget helper for hot-path producers ──────────


def maybe_fire_capability_proposal(
    user_text: str,
    *,
    pending_card_store: Any = None,
    chat_id: Optional[str] = None,
    user_id: Optional[str] = None,
    threshold: float = 0.3,
    cooldown_s: float = 24 * 3600,
) -> dict:
    """Best-effort: detect a capability gap in ``user_text``, and if
    one fires, run the orchestrator end-to-end (match → eval →
    propose → card). Returns a dict summary; never raises.

    Designed for hot-path producers (chat handler, daemon cycle)
    that should never break on a detector failure. Any exception
    inside the detect + orchestrate path is swallowed, logged,
    and reported in the return dict. The caller's reply path is
    unaffected.

    Idempotent on a per-cooldown-window basis — the detector's
    cooldown gate prevents the same capability from producing
    more than one card per cooldown_s window.
    """
    summary: dict = {
        "fired": False, "capability_id": None, "cards_created": [],
    }
    try:
        det = detect_gap(
            user_text, threshold=threshold, cooldown_s=cooldown_s,
        )
        summary["matches_above_threshold"] = [
            m.capability_id for m in det.matches_above_threshold
        ]
        summary["cooldown_blocked"] = list(det.cooldown_blocked)
        if det.fired_for is None:
            return summary
        from core.infra.capability_orchestrator import (
            orchestrate_from_felt_limitation,
        )
        if pending_card_store is None:
            from core.decision.pending_cards import PendingCardStore
            pending_card_store = PendingCardStore()
        result = orchestrate_from_felt_limitation(
            user_text,
            pending_card_store=pending_card_store,
            chat_id=chat_id,
            user_id=user_id,
            source="capability_gap_detector",
        )
        summary["fired"] = True
        summary["capability_id"] = det.fired_for.capability_id
        summary["cards_created"] = list(result.cards_created)
        if result.stage_errors:
            summary["stage_errors"] = result.stage_errors
        logger.info(
            "capability_gap_detector: fired for %s on text %r — "
            "cards_created=%s",
            det.fired_for.capability_id, user_text[:80],
            result.cards_created,
        )
    except Exception as e:
        logger.warning(
            "capability_gap_detector: fire helper failed: %s", e,
        )
        summary["error"] = str(e)
    return summary
