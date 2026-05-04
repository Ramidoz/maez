# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""F1.A — baseline observation store + lexical detector.

The 5x memory-provenance arc (commits 6feb4fc..fd823eb) closed the
metadata-layer laundering surfaces — direct promotion, daily
consolidation, fresh introspection writes — but left the
through-quotation surface open. The probe at 1e0f0fb empirically
confirmed that the audit takes no source-trust input by
construction; defense relies entirely on the LLM honoring the
prompt-time annotation.

Closing the through-quotation surface needs a baseline-write gate
that knows whether the LLM's observation depended on untrusted
recall. Designing that gate without empirical data risks either
over-blocking (operator noise) or under-blocking (false
confidence). So F1 starts in observation mode:

  F1.A (this module): isolated SQLite store + substring detector.
      No behavior change. No Chroma. No LLM judge. Captures
      candidates for hand-labeling.

  F1.B (next slice):  thread the recall context through
      ``_execute_action`` and call ``record_observation`` from
      ``_do_update_baseline`` post-audit.

  F1.C (next slice):  CLI for querying flagged observations and
      hand-labeling them.

  F1b (later slice):  add an embedding-similarity detector. NOT
      in F1.A because the production embedding model/version is
      not pinned in code (Chroma loads whatever sentence-
      transformers is available at runtime). Adding embedding
      now would produce labels that drift on every Chroma /
      sentence-transformers upgrade.

  F2 (future slice):  measured downgrade gate. Once F1 has
      labeled data, downgrade derived baselines to ``untrusted``
      when the detector says they materially depend on untrusted
      recall.

Critical isolation contract
---------------------------

This module MUST NOT import ``chromadb`` or
``memory.memory_manager``. The store is observation-only; if it
became coupled to Maez's lived-memory substrate it would turn
into a recall surface (the laundering vector F1 exists to close).
A test enforces this via AST parse:
``tests/test_baseline_observations.py::IsolationContractTests``.

Fail-soft contract
------------------

Mirrors ``core.learning.consequence_memory`` and
``core.learning.fabrication_memory``: every public entry point
catches DB errors and logs rather than propagating. Losing an
observation row is strictly preferable to breaking the action
path that produced it. F1.A is observation-only; F2 enforcement
will tighten this contract for its own write path.
"""
from __future__ import annotations

import contextlib
import json
import logging
import os
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("maez.baseline_observations")

# T2.C (2026-05-04 15-agent audit): SQLite connections in this
# module are opened with ``check_same_thread=False`` (intentional —
# ``record_observation`` is invoked from any of cognition,
# action-engine, and Telegram surfaces, all on different threads).
# That flag is correct; what was missing was the explicit lock
# that makes it safe. Mirrors the T1.2 / T1.7 pattern from commit
# ce3e308 (``ConversationController._offers_lock`` /
# ``soul_loader._lock``). Module-scope and independent from
# ``memory_scoring._write_lock`` — coupling unrelated write paths
# would create artificial contention.
_write_lock: threading.Lock = threading.Lock()

# DB path: env var override for tests; production default lives
# alongside the other immune-memory stores under ``memory/``.
try:
    from core.infra import paths as _paths
    _DEFAULT_DB_PATH = str(_paths.memory_dir() / "baseline_observations.db")
except Exception:
    _DEFAULT_DB_PATH = str(
        Path(__file__).resolve().parents[2]
        / "memory" / "baseline_observations.db"
    )


def _db_path() -> Path:
    """Resolve the DB path at call time so tests can monkey-patch
    ``MAEZ_BASELINE_OBSERVATIONS_DB`` between sub-tests within the
    same process. ``consequence_memory`` caches its path at module
    import; F1.A diverges to make the test surface easier."""
    return Path(
        os.environ.get(
            "MAEZ_BASELINE_OBSERVATIONS_DB", _DEFAULT_DB_PATH,
        )
    )


# Detector identity. Bumped when the substring detector's behavior
# changes in a way that would invalidate hand-labels collected
# against the prior version. Embedding detector arrives in F1b
# under a separate detector_version identifier.
DETECTOR_VERSION = "substring-v1"

# Minimum match length for the substring detector. Filters trivial
# common-phrase overlap (e.g. "the company" topical noise) without
# inventing a stop-word list. A realistic verbatim quote of an
# untrusted recall is well above 20 chars; topical-only overlap is
# typically below it. Tunable from labeled data in F1.A.1 if needed.
MIN_MATCH_LEN = 20


# ── connection / schema ─────────────────────────────────────────────


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=5.0, check_same_thread=False)
    # Schema note: ``has_untrusted`` is a denormalized boolean (0/1)
    # derived from ``untrusted_ids_json`` non-emptiness. The
    # alternative — ``WHERE untrusted_ids_json != '[]'`` — is fragile
    # to JSON serialization drift (whitespace variations, future
    # writers using different separators). The denorm column is set
    # by ``record_observation`` and queried by ``recent`` for the
    # ``only_with_untrusted=True`` filter. Migration-safety: SQLite
    # ALTER TABLE ADD COLUMN is safe for nullable / default-bearing
    # columns, so future column additions follow the same pattern
    # without backfilling existing rows.
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS baseline_observations (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            ts                   REAL    NOT NULL,
            observation          TEXT    NOT NULL,
            audited_observation  TEXT    NOT NULL,
            surface              TEXT    NOT NULL DEFAULT 'action_baseline_update',
            action               TEXT    NOT NULL DEFAULT 'update_baseline',
            recall_ids_json      TEXT    NOT NULL DEFAULT '[]',
            recall_tiers_json    TEXT    NOT NULL DEFAULT '{}',
            untrusted_ids_json   TEXT    NOT NULL DEFAULT '[]',
            substring_hits_json  TEXT    NOT NULL DEFAULT '[]',
            detector_version     TEXT    NOT NULL,
            decision             TEXT    NOT NULL DEFAULT 'observe_only',
            has_untrusted        INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_baseline_obs_ts "
        "ON baseline_observations(ts)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_baseline_obs_untrusted_ts "
        "ON baseline_observations(has_untrusted, ts)"
    )
    con.commit()
    return con


# ── dataclass ───────────────────────────────────────────────────────


@dataclass
class BaselineObservation:
    """One row from the ``baseline_observations`` table. JSON
    columns are decoded into native Python collections by
    ``recent``; F1.B / F2 callers should consume this dataclass
    rather than reading raw rows."""

    id: int
    ts: float
    observation: str
    audited_observation: str
    surface: str
    action: str
    recall_ids: list[str] = field(default_factory=list)
    recall_tiers: dict[str, str] = field(default_factory=dict)
    untrusted_ids: list[str] = field(default_factory=list)
    substring_hits: list[dict] = field(default_factory=list)
    detector_version: str = DETECTOR_VERSION
    decision: str = "observe_only"


def _row_to_obs(row) -> BaselineObservation:
    def _safe_json(s: str, default):
        try:
            return json.loads(s) if s else default
        except Exception:
            return default

    return BaselineObservation(
        id=row[0],
        ts=row[1],
        observation=row[2],
        audited_observation=row[3],
        surface=row[4],
        action=row[5],
        recall_ids=_safe_json(row[6], []),
        recall_tiers=_safe_json(row[7], {}),
        untrusted_ids=_safe_json(row[8], []),
        substring_hits=_safe_json(row[9], []),
        detector_version=row[10],
        decision=row[11],
    )


# ── substring detector ──────────────────────────────────────────────


def substring_hits(
    audited_observation: str,
    untrusted_memories: list[dict],
) -> list[dict]:
    """Return the list of substring hits that link an audited
    baseline observation to one or more untrusted recalled memories.

    Each input memory dict carries ``id`` and ``content``. Each
    returned hit carries:

        ``memory_id``    str  — the input memory's id
        ``matched_text`` str  — the longest contiguous substring
                                 present in BOTH the audited
                                 observation and the memory's content
        ``match_length`` int  — len(matched_text)

    Conservative-by-design: matches shorter than ``MIN_MATCH_LEN``
    (default 20 chars) are discarded so trivial common-phrase
    overlap doesn't produce noise. The detector is deliberately
    weak; F1's job is observation, not enforcement, and a weak
    honest detector is better than a 'semantic' detector whose
    behavior drifts with model upgrades.

    Algorithm: for each untrusted memory, find the longest common
    substring with the audited text via dynamic-programming. O(n*m)
    per memory; baseline observation texts and memory contents are
    bounded in length, so this is fine for the F1 traffic shape.
    """
    if not audited_observation or not untrusted_memories:
        return []

    hits: list[dict] = []
    a = audited_observation
    a_lower = a.lower()
    # Unicode case-fold safety: ``str.lower()`` is NOT length-
    # preserving in general. ``"İ".lower() == "i̇"``
    # (LATIN CAPITAL I WITH DOT ABOVE → "i" + combining dot).
    # When ``len(a_lower) != len(a)``, a match-end index found in
    # ``a_lower`` does not align with ``a`` and slicing ``a`` would
    # produce off-by-N or mid-codepoint garbage that would land in
    # the ``matched_text`` evidence labelers use to set F2's
    # enforcement threshold — direct contamination of the F2
    # measurement loop. When lengths diverge we fall back to
    # slicing ``a_lower`` and flag the row so a labeler can see
    # the evidence is case-normalized rather than original-case.
    case_fold_safe = len(a_lower) == len(a)
    for mem in untrusted_memories:
        mid = mem.get("id")
        content = mem.get("content") or ""
        if not mid or not content:
            continue
        b_lower = content.lower()
        match_len, match_end_a = _longest_common_substring(a_lower, b_lower)
        if match_len < MIN_MATCH_LEN:
            continue
        if case_fold_safe:
            matched_text = a[match_end_a - match_len:match_end_a]
            case_normalized = False
        else:
            matched_text = a_lower[match_end_a - match_len:match_end_a]
            case_normalized = True
        hits.append({
            "memory_id": str(mid),
            "matched_text": matched_text,
            "match_length": match_len,
            "case_normalized": case_normalized,
        })
    return hits


def _longest_common_substring(s1: str, s2: str) -> tuple[int, int]:
    """Return ``(longest_length, end_index_in_s1)``. End-index lets
    the caller slice the matched substring out of s1. Standard DP;
    uses a rolling 1D array for memory efficiency.

    Multi-match tie-breaking: when two equal-length matches exist,
    the FIRST (leftmost in s1) wins. This is intentional — labelers
    care about the evidence-bearing region, and a stable
    leftmost-wins rule keeps detector output reproducible across
    runs. The strict ``>`` comparison (not ``>=``) preserves the
    leftmost-wins property; do not change to ``>=``."""
    n, m = len(s1), len(s2)
    if n == 0 or m == 0:
        return 0, 0
    prev = [0] * (m + 1)
    curr = [0] * (m + 1)
    best_len = 0
    best_end_a = 0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if s1[i - 1] == s2[j - 1]:
                curr[j] = prev[j - 1] + 1
                if curr[j] > best_len:
                    best_len = curr[j]
                    best_end_a = i
            else:
                curr[j] = 0
        # Swap rows — the inner loop above writes every cell of
        # ``curr`` unconditionally (each j gets either prev[j-1]+1
        # or 0), so no explicit reset is needed before the next
        # outer-loop iteration. A previous version reset the row
        # explicitly; that work was redundant.
        prev, curr = curr, prev
    return best_len, best_end_a


# ── write path ──────────────────────────────────────────────────────


def record_observation(
    *,
    observation: str,
    audited_observation: str,
    recall_ids: list[str],
    recall_tiers: dict[str, str],
    untrusted_ids: list[str],
    substring_hits_: list[dict],
    surface: str = "action_baseline_update",
    action: str = "update_baseline",
    decision: str = "observe_only",
) -> Optional[int]:
    """Persist one baseline-observation row. Returns the new row id,
    or ``None`` if the write failed.

    Fail-soft contract: any DB error logs a warning and returns
    ``None``. F1.A is observation-only; losing a row is strictly
    preferable to breaking the caller's happy path. F2 enforcement
    will need its own write contract.

    The trailing underscore on ``substring_hits_`` avoids shadowing
    the ``substring_hits`` function name in the same module."""
    try:
        recall_ids_json = json.dumps(list(recall_ids))
        recall_tiers_json = json.dumps(dict(recall_tiers))
        untrusted_ids_json = json.dumps(list(untrusted_ids))
        substring_hits_json = json.dumps(list(substring_hits_))
    except (TypeError, ValueError) as exc:
        logger.warning(
            "baseline_observations: payload not JSON-serializable "
            "(%s); skipping row",
            exc,
        )
        return None

    try:
        # consequence_memory pattern: contextlib.closing because
        # sqlite3's context manager only commits/rolls back; it does
        # NOT close the connection. Wrap explicitly so file
        # descriptors are released deterministically.
        #
        # T2.C: ``_write_lock`` serializes the
        # connect-execute-commit triple across threads. The SQLite
        # connection is opened with ``check_same_thread=False`` so
        # the thread-local check is off; the lock is what makes
        # that safe.
        has_untrusted = 1 if untrusted_ids else 0
        with _write_lock, contextlib.closing(_connect()) as con:
            cur = con.execute(
                "INSERT INTO baseline_observations ("
                "ts, observation, audited_observation, surface, "
                "action, recall_ids_json, recall_tiers_json, "
                "untrusted_ids_json, substring_hits_json, "
                "detector_version, decision, has_untrusted"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    time.time(),
                    observation,
                    audited_observation,
                    surface,
                    action,
                    recall_ids_json,
                    recall_tiers_json,
                    untrusted_ids_json,
                    substring_hits_json,
                    DETECTOR_VERSION,
                    decision,
                    has_untrusted,
                ),
            )
            con.commit()
            return cur.lastrowid
    except Exception as exc:
        logger.warning(
            "baseline_observations: record failed (%s); fail-soft "
            "(returning None)",
            exc,
        )
        return None


# ── read path ───────────────────────────────────────────────────────


def recent(
    limit: int = 50,
    *,
    only_with_untrusted: bool = False,
) -> list[BaselineObservation]:
    """Return up to ``limit`` recent rows, newest first.

    ``only_with_untrusted=True`` filters to rows whose
    ``untrusted_ids_json`` is non-empty — the F1.C labeling CLI's
    primary query.

    Returns ``[]`` on DB error rather than raising (fail-soft
    consistent with the write path)."""
    try:
        with contextlib.closing(_connect()) as con:
            sql = (
                "SELECT id, ts, observation, audited_observation, "
                "surface, action, recall_ids_json, recall_tiers_json, "
                "untrusted_ids_json, substring_hits_json, "
                "detector_version, decision "
                "FROM baseline_observations "
            )
            if only_with_untrusted:
                # Use the denormalized has_untrusted flag (set by
                # record_observation) rather than a JSON-string
                # equality on untrusted_ids_json. The boolean is
                # robust against future writers that produce
                # different JSON whitespace; the JSON-string approach
                # would silently break.
                sql += "WHERE has_untrusted = 1 "
            sql += "ORDER BY ts DESC LIMIT ?"
            rows = con.execute(sql, (int(limit),)).fetchall()
            return [_row_to_obs(r) for r in rows]
    except Exception as exc:
        logger.warning(
            "baseline_observations: recent() failed (%s); fail-soft "
            "(returning [])",
            exc,
        )
        return []


__all__ = [
    "BaselineObservation",
    "DETECTOR_VERSION",
    "MIN_MATCH_LEN",
    "record_observation",
    "recent",
    "substring_hits",
]
