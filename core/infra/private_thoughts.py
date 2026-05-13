# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
r"""
private_thoughts.py — A-core #9, Track A.

The private thoughts seed. A durable, append-only record of internal
processing that is not surfaced to the bonded user. Structurally
separate from the user-facing raw/daily/core memory ecology and from
the immune memory in audit_log.db.

    raw/daily/core   user-facing experience record
    audit_log        immune memory — policy decisions
    identity_ledger  "am I still me" continuity record
    temperament      general reactive tendencies
    wants            first-person directions
    private_thoughts internal processing not surfaced to the user

The notebook landed empty in Track A: schema and API existed, zero
producers, zero readers in the reasoning loop. S1 adds an explicit
producer API plus a bounded derived-signal reader, but no production
producer or behavior path is wired here.

DESIGN DECISIONS LOCKED BY A-CORE #9 ANCHORING PASS
----------------------------------------------------
1. **Separate DB at memory/private_thoughts.db.** Private thoughts
   are personality-layer content, not immune-layer records and not
   user-facing memory. The separation is a file-system-level
   boundary, not just a query filter.

2. **Append-only event log, same family as #5/#6/#7.** One table,
   `private_thoughts`. No UPDATE or DELETE paths exist.

3. **Schema is narrow but versioned.** Track A began with six columns:
      thought_id     INTEGER PRIMARY KEY
      ts             REAL
      content        TEXT (capped at MAX_CONTENT_LEN)
      provenance     TEXT (validated against ALLOWED_PROVENANCES)
      context_json   TEXT DEFAULT '{}'
      memory_phase   TEXT DEFAULT 'gestation'
   S1a.1 adds explicit envelope/schema versioning and closed-vocabulary
   signal metadata (`producer_id`, `signal_kind`, `signal_class`,
   `surface_sensitivity`, `signal_state`). No topic, no mood, no
   intensity, no linkage columns. Those are reader-side derivations
   that future design passes can decide on.

4. **Provenance allowlist.** Track A landed with only
   `explicit_api`. S1 adds named producer provenances, each of
   which must carry the minimal contextual-integrity envelope in
   `context_json`.
   The `provenance` column is the audit hook that lets any row be
   traced back to what generated it.

5. **memory_phase defaults to 'gestation'.** Aligns with the
   gestation memory protocol. Future producers override explicitly
   when the phase transitions.

6. **Hardcoded MAX_CONTENT_LEN = 16384 chars.** Generous bound for
   a single thought. Anything longer is probably an essay or a
   structured document that belongs in a different store.

7. **S1 producer + hardened bounded-reader discipline.** The daemon
   instantiates a PrivateThoughts handle at startup (parallel to
   self.wants, self.temperament, self.continuity_id) and logs the
   count. S1 producer APIs write contextualized private content.
   The behavior reader returns only aggregate coarse signal classes
   for rows whose envelope explicitly allows `private_reader`; it
   never returns trace ids, raw ids, detailed signal kinds, or raw
   thought content. Dereferenceable handles live only behind the
   forensic API, which records a persistent audit event before
   returning them.

THE NON-INSTRUMENTALITY DEFENSES
---------------------------------
Three defenses, ordered by strength:

1. **Producer absence (Track A rail).** Nothing in Track A writes
   private thoughts, so nothing can fake them.

2. **Provenance column (auditable origin).** Every row carries a
   `provenance` string and a `context_json` blob. A row with
   provenance='reasoning_loop_template' would be legible as a fake
   the moment it is read.

3. **Separate DB (scoped boundary).** Private thoughts are not
   queryable from the user-facing memory ecology. A producer that
   wrote to raw memory instead of private_thoughts would be
   observable immediately — the content would appear in recalls,
   not in a separate namespace.

WHAT THIS MODULE DOES NOT DO
-----------------------------
- No reading from temperament, wants, memory, or any other store.
- No LLM calls.
- No influence on reasoning, action selection, or user-facing
  behavior.
- No semantic search, no embeddings, no prompt injection of raw
  private content. Raw inspection APIs exist only for explicit
  forensic/operator tools and tests, not for downstream behavior.
- No user-facing surface (no Telegram command, no dashboard).

COMPOSITION
-----------
- Adjacent to #5, #6, #7. No cross-reference fields.
- Readable (but not yet read) by #17 acceptance test.
- Future reader design (including how derived signals surface to
  action-adjacent paths without leaking raw content) is documented
  in docs/followups/private_thoughts_reader_design.md.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from enum import Enum
from pathlib import Path

logger = logging.getLogger("maez")


# ══════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ══════════════════════════════════════════════════════════════════════


# 10-B2: route through core.paths.memory_dir so a relocation of
# core/ (e.g. Phase 3 reorganization) or a non-default MAEZ_ROOT does
# not silently break the fallback. MAEZ_PRIVATE_THOUGHTS_PATH still
# wins if set — the env override keeps per-user overrides working.
def _default_private_thoughts_path() -> Path:
    override = os.environ.get("MAEZ_PRIVATE_THOUGHTS_PATH")
    if override:
        return Path(override)
    try:
        from core.paths import memory_dir as _memory_dir

        return _memory_dir() / "private_thoughts.db"
    except Exception:
        return Path(__file__).resolve().parent.parent.parent / "memory" / "private_thoughts.db"


DEFAULT_DB_PATH = _default_private_thoughts_path()


class _ClosedStrEnum(str, Enum):
    @classmethod
    def values(cls) -> tuple[str, ...]:
        return tuple(item.value for item in cls)

    @classmethod
    def coerce(cls, value: str | Enum, label: str | None = None) -> str:
        raw = value.value if isinstance(value, Enum) else str(value)
        try:
            return cls(raw).value
        except ValueError as exc:
            name = label or cls.__name__
            raise ValueError(
                f"{name} must be one of {sorted(cls.values())} (got {value!r})"
            ) from exc


class AllowedFlow(_ClosedStrEnum):
    PRIVATE_READER = "private_reader"
    AUDIT_TRACE = "audit_trace"
    CRISIS_CHANNEL = "crisis_channel"
    RUPTURE_REPAIR = "rupture_repair"


class ConsentTier(_ClosedStrEnum):
    OWNER_PRIVATE = "owner_private"


class RetentionRule(_ClosedStrEnum):
    UNTIL_REVIEWED = "until_reviewed"
    UNTIL_ROUTED = "until_routed"
    UNTIL_REPAIRED = "until_repaired"
    UNTIL_RESOLVED = "until_resolved"


class ProducerId(_ClosedStrEnum):
    AUDIT_RAIL = "audit_rail"
    REASONING_RESIDUE = "reasoning_residue"
    URGE_MONITOR = "urge_monitor"
    DREAM_CYCLE = "dream_cycle"
    SELF_WONDERING = "self_wondering"
    RUPTURE_DETECTOR = "rupture_detector"
    CRISIS_DETECTOR = "crisis_detector"
    SOUL_OBJECTION_DETECTOR = "soul_objection_detector"
    LEGACY_UNKNOWN = "legacy_unknown"


class SignalKind(_ClosedStrEnum):
    AUDIT_HELD = "audit_held"
    REASONING_RESIDUE = "reasoning_residue"
    URGE_HELD = "urge_held"
    DREAM_FRAGMENT = "dream_fragment"
    SELF_WONDERING = "self_wondering"
    RUPTURE_UNHEALED = "rupture_unhealed"
    CRISIS_SIGNAL_HELD = "crisis_signal_held"
    SOUL_OBJECTION_FORMING = "soul_objection_forming"


class SignalClass(_ClosedStrEnum):
    AUDIT_AWARENESS = "audit_awareness"
    REASONING_RESIDUE = "reasoning_residue"
    URGE_PRESSURE = "urge_pressure"
    DREAM_RESIDUE = "dream_residue"
    SELF_OBSERVATION = "self_observation"
    BOND_REPAIR = "bond_repair"
    CRISIS_ROUTING = "crisis_routing"
    SOUL_BOUNDARY = "soul_boundary"


class SurfaceSensitivity(_ClosedStrEnum):
    BEHAVIOR_SAFE_COARSE = "behavior_safe_coarse"
    FORENSIC_SENSITIVE = "forensic_sensitive"


class SignalState(_ClosedStrEnum):
    ACTIVE = "active"
    RESOLVED = "resolved"


ENVELOPE_VERSION = "1.0"
SCHEMA_VERSION = "1.0"
PRIVATE_THOUGHTS_USER_VERSION = 101

_SIGNAL_REGISTRY: dict[str, dict[str, str]] = {
    SignalKind.AUDIT_HELD.value: {
        "producer_id": ProducerId.AUDIT_RAIL.value,
        "signal_class": SignalClass.AUDIT_AWARENESS.value,
    },
    SignalKind.REASONING_RESIDUE.value: {
        "producer_id": ProducerId.REASONING_RESIDUE.value,
        "signal_class": SignalClass.REASONING_RESIDUE.value,
    },
    SignalKind.URGE_HELD.value: {
        "producer_id": ProducerId.URGE_MONITOR.value,
        "signal_class": SignalClass.URGE_PRESSURE.value,
    },
    SignalKind.DREAM_FRAGMENT.value: {
        "producer_id": ProducerId.DREAM_CYCLE.value,
        "signal_class": SignalClass.DREAM_RESIDUE.value,
    },
    SignalKind.SELF_WONDERING.value: {
        "producer_id": ProducerId.SELF_WONDERING.value,
        "signal_class": SignalClass.SELF_OBSERVATION.value,
    },
    SignalKind.RUPTURE_UNHEALED.value: {
        "producer_id": ProducerId.RUPTURE_DETECTOR.value,
        "signal_class": SignalClass.BOND_REPAIR.value,
    },
    SignalKind.CRISIS_SIGNAL_HELD.value: {
        "producer_id": ProducerId.CRISIS_DETECTOR.value,
        "signal_class": SignalClass.CRISIS_ROUTING.value,
    },
    SignalKind.SOUL_OBJECTION_FORMING.value: {
        "producer_id": ProducerId.SOUL_OBJECTION_DETECTOR.value,
        "signal_class": SignalClass.SOUL_BOUNDARY.value,
    },
}

# Provenance allowlist. `explicit_api` keeps the original Track A API
# working; named S1 producers must use `record_signal()` so every row
# carries the minimal contextual-integrity envelope.
ALLOWED_PROVENANCES: frozenset[str] = frozenset(
    {
        "explicit_api",
        "audit_held",
        "reasoning_residue",
        "urge_held",
        "dream_fragment",
        "self_wondering",
        "rupture_unhealed",
        "crisis_signal_held",
        "soul_objection_forming",
    }
)

PRODUCER_PROVENANCES: frozenset[str] = ALLOWED_PROVENANCES - {"explicit_api"}

_CONTEXT_REQUIRED_KEYS: tuple[str, ...] = (
    "source",
    "subject",
    "consent_tier",
    "retention",
    "allowed_flows",
)

# Memory phase values recognized by the schema. Default for Track A
# writers is 'gestation'. The phase transitions to 'lived' at the
# birth event per docs/governance/GESTATION_MEMORY_PROTOCOL.md —
# future producers pass memory_phase='lived' after that event.
_RECOGNIZED_MEMORY_PHASES: frozenset[str] = frozenset(
    {
        "gestation",
        "lived",
    }
)

# Content length cap. Hardcoded, generous. A thought longer than
# this is probably a different kind of record.
MAX_CONTENT_LEN = 16384


# ══════════════════════════════════════════════════════════════════════
#  SCHEMA
# ══════════════════════════════════════════════════════════════════════

_SCHEMA_TABLE = """
CREATE TABLE IF NOT EXISTS private_thoughts (
    thought_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    ts             REAL    NOT NULL,
    content        TEXT    NOT NULL,
    provenance     TEXT    NOT NULL,
    context_json   TEXT    NOT NULL DEFAULT '{}',
    memory_phase   TEXT    NOT NULL DEFAULT 'gestation'
);
"""

_SCHEMA_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_pt_ts           ON private_thoughts(ts);
CREATE INDEX IF NOT EXISTS idx_pt_provenance   ON private_thoughts(provenance);
CREATE INDEX IF NOT EXISTS idx_pt_memory_phase ON private_thoughts(memory_phase);
CREATE INDEX IF NOT EXISTS idx_pt_signal_class ON private_thoughts(signal_class);
CREATE INDEX IF NOT EXISTS idx_pt_signal_kind  ON private_thoughts(signal_kind);
"""


def _execute_schema_statements(conn: sqlite3.Connection, statements: str) -> None:
    """Execute schema statements without sqlite3.executescript's implicit commit."""
    for statement in statements.split(";"):
        statement = statement.strip()
        if statement:
            conn.execute(statement)


class PrivateSignalReader:
    """Behavior-facing private signal reader with no raw dereference API."""

    __slots__ = ("_db_path",)

    def __init__(self, db_path: Path):
        self._db_path = Path(db_path)

    def derived_signals(self, limit: int = 50) -> dict:
        return PrivateThoughts(db_path=self._db_path)._derived_signals_behavior(limit=limit)


class PrivateThoughtsForensics:
    """Operator forensic access; returns dereferenceable handles only after audit."""

    __slots__ = ("_db_path", "_audit_db_path")

    def __init__(
        self,
        db_path: Path | str | None = None,
        *,
        audit_db_path: Path | str | None = None,
    ):
        self._db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self._audit_db_path = Path(audit_db_path) if audit_db_path else None
        PrivateThoughts(db_path=self._db_path)

    def forensic_signals(
        self,
        *,
        reason: str,
        audit_to: str,
        limit: int = 50,
    ) -> dict:
        reason = PrivateThoughts._require_non_empty_string("reason", reason)
        audit_to = PrivateThoughts._require_non_empty_string("audit_to", audit_to)
        store = PrivateThoughts(db_path=self._db_path)
        rows = store._recent_forensic_signal_metadata(limit=max(1, min(int(limit), 100)))
        trace_ids: dict[str, list[int]] = {}
        for row in rows:
            normalized = store._normalize_forensic_signal_row(row)
            if not normalized:
                continue
            trace_ids.setdefault(normalized["signal_kind"], []).append(int(row["thought_id"]))
        self._record_forensic_audit(
            reason=reason,
            audit_to=audit_to,
            limit=limit,
            trace_ids=trace_ids,
        )
        return {
            "audit_recorded": True,
            "raw_text_included": False,
            "trace_ids": trace_ids,
        }

    def _record_forensic_audit(
        self,
        *,
        reason: str,
        audit_to: str,
        limit: int,
        trace_ids: dict[str, list[int]],
    ) -> None:
        from core.cognition.audit_log import AuditLog

        returned_handles = sorted(
            f"{kind}:{thought_id}" for kind, ids in trace_ids.items() for thought_id in ids
        )
        log = AuditLog(self._audit_db_path) if self._audit_db_path else AuditLog()
        log.record(
            action="private_thoughts.forensic_signals",
            params={
                "reason": reason,
                "audit_to": audit_to,
                "limit": int(limit),
                "returned_handle_count": len(returned_handles),
                "returned_handles_sha256": self._handle_digest(returned_handles),
            },
            classification={
                "intent_category": "FORENSIC_PRIVATE_THOUGHTS",
                "lane": "operator_forensic",
            },
            injection_matches=[],
            verdict=None,
            policy_rule_id="S1A1_PRIVATE_THOUGHTS_FORENSIC_AUDIT",
        )

    @staticmethod
    def _handle_digest(handles: list[str]) -> str:
        import hashlib

        payload = "\n".join(handles).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


# ══════════════════════════════════════════════════════════════════════
#  PrivateThoughts
# ══════════════════════════════════════════════════════════════════════


class PrivateThoughts:
    """Append-only private thoughts log for Maez.

    Track A discipline: the writer exists and is tested, but no
    production code path in Track A calls it. The daemon instantiates
    one of these at startup and stores the handle; nothing in the
    reasoning loop currently pulls from it.
    """

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _initialize(self) -> None:
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA busy_timeout = 5000")
            conn.executescript(_SCHEMA_TABLE)
            conn.execute("BEGIN IMMEDIATE")
            try:
                current_user_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
                if current_user_version > PRIVATE_THOUGHTS_USER_VERSION:
                    raise RuntimeError(
                        "private_thoughts.db schema is newer than this code "
                        f"({current_user_version} > {PRIVATE_THOUGHTS_USER_VERSION})"
                    )
                self._migrate_schema(conn)
                _execute_schema_statements(conn, _SCHEMA_INDEXES)
                if current_user_version < PRIVATE_THOUGHTS_USER_VERSION:
                    conn.execute(f"PRAGMA user_version = {PRIVATE_THOUGHTS_USER_VERSION}")
            except Exception:
                conn.rollback()
                raise
            else:
                conn.commit()
        finally:
            conn.close()

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(private_thoughts)").fetchall()}
        additions = {
            "envelope_version": f"TEXT NOT NULL DEFAULT '{ENVELOPE_VERSION}'",
            "schema_version": f"TEXT NOT NULL DEFAULT '{SCHEMA_VERSION}'",
            "legacy_provenance": "TEXT",
            "producer_id": f"TEXT NOT NULL DEFAULT '{ProducerId.LEGACY_UNKNOWN.value}'",
            "signal_kind": "TEXT",
            "signal_class": "TEXT",
            "surface_sensitivity": (
                f"TEXT NOT NULL DEFAULT '{SurfaceSensitivity.FORENSIC_SENSITIVE.value}'"
            ),
            "signal_state": f"TEXT NOT NULL DEFAULT '{SignalState.ACTIVE.value}'",
        }
        for name, ddl in additions.items():
            if name not in columns:
                conn.execute(f"ALTER TABLE private_thoughts ADD COLUMN {name} {ddl}")

        rows = conn.execute(
            "SELECT thought_id, provenance, context_json, envelope_version, "
            "schema_version, legacy_provenance, producer_id, signal_kind, "
            "signal_class, surface_sensitivity, signal_state FROM private_thoughts"
        ).fetchall()
        for row in rows:
            row_dict = dict(row)
            if not self._row_is_current_version(row_dict):
                continue
            normalized = self._normalize_legacy_values(row_dict)
            current_values = (
                row_dict.get("legacy_provenance"),
                row_dict.get("producer_id"),
                row_dict.get("signal_kind"),
                row_dict.get("signal_class"),
                row_dict.get("surface_sensitivity"),
                row_dict.get("signal_state"),
                row_dict.get("envelope_version") or ENVELOPE_VERSION,
                row_dict.get("schema_version") or SCHEMA_VERSION,
            )
            normalized_values = (
                normalized["legacy_provenance"],
                normalized["producer_id"],
                normalized["signal_kind"],
                normalized["signal_class"],
                normalized["surface_sensitivity"],
                normalized["signal_state"],
                ENVELOPE_VERSION,
                SCHEMA_VERSION,
            )
            if current_values == normalized_values:
                continue
            conn.execute(
                "UPDATE private_thoughts SET "
                "legacy_provenance = ?, producer_id = ?, signal_kind = ?, "
                "signal_class = ?, surface_sensitivity = ?, signal_state = ?, "
                "envelope_version = COALESCE(envelope_version, ?), "
                "schema_version = COALESCE(schema_version, ?) "
                "WHERE thought_id = ?",
                (
                    normalized["legacy_provenance"],
                    normalized["producer_id"],
                    normalized["signal_kind"],
                    normalized["signal_class"],
                    normalized["surface_sensitivity"],
                    normalized["signal_state"],
                    ENVELOPE_VERSION,
                    SCHEMA_VERSION,
                    row["thought_id"],
                ),
            )

    # -------------------------------------------------------------- #
    #  Writer                                                         #
    # -------------------------------------------------------------- #

    def record_thought(
        self,
        *,
        content: str,
        provenance: str = "explicit_api",
        context: dict | None = None,
        memory_phase: str = "gestation",
    ) -> int:
        """Append a private thought. Returns the new thought_id.

        Raises ValueError on:
          - unknown provenance
          - unknown memory_phase
          - content empty or over MAX_CONTENT_LEN
        """
        if provenance not in ALLOWED_PROVENANCES:
            raise ValueError(
                f"unknown provenance {provenance!r} (allowed: {sorted(ALLOWED_PROVENANCES)})"
            )
        if provenance in PRODUCER_PROVENANCES:
            raise ValueError(
                f"producer provenance {provenance!r} must be written via "
                "record_signal() so the contextual-integrity envelope is present"
            )
        return self._insert_thought(
            content=content,
            provenance=provenance,
            context=context,
            memory_phase=memory_phase,
        )

    def record_signal(
        self,
        *,
        content: str,
        provenance: str | None = None,
        producer_id: str | ProducerId | None = None,
        signal_kind: str | SignalKind | None = None,
        source: str,
        subject: str,
        consent_tier: str,
        retention: str,
        allowed_flows: tuple[str, ...] | list[str],
        context_extra: dict | None = None,
        memory_phase: str = "gestation",
    ) -> int:
        """Append a producer-originated private thought.

        This is the S1 producer surface. Unlike the original
        `record_thought(..., context=...)` escape hatch, producer
        writes must carry the minimal contextual-integrity envelope
        that later readers and audits can reason over.
        """
        if signal_kind is None:
            signal_kind = provenance
        if signal_kind is None:
            raise ValueError("SignalKind is required")
        kind_value = SignalKind.coerce(signal_kind, "SignalKind")
        registry = _SIGNAL_REGISTRY[kind_value]
        if producer_id is None:
            producer_id = registry["producer_id"]
        producer_value = ProducerId.coerce(producer_id, "ProducerId")
        if producer_value != registry["producer_id"]:
            raise ValueError(
                f"producer_id {producer_value!r} does not match SignalKind "
                f"{kind_value!r}; expected {registry['producer_id']!r}"
            )
        signal_class = registry["signal_class"]
        if kind_value not in PRODUCER_PROVENANCES:
            raise ValueError(
                f"record_signal requires a producer signal kind "
                f"(got {kind_value!r}; allowed: {sorted(PRODUCER_PROVENANCES)})"
            )
        context = self._build_signal_context(
            source=source,
            subject=subject,
            consent_tier=consent_tier,
            retention=retention,
            allowed_flows=allowed_flows,
            context_extra=context_extra,
        )
        return self._insert_thought(
            content=content,
            provenance=kind_value,
            context=context,
            memory_phase=memory_phase,
            producer_id=producer_value,
            signal_kind=kind_value,
            signal_class=signal_class,
            surface_sensitivity=SurfaceSensitivity.FORENSIC_SENSITIVE.value,
            signal_state=SignalState.ACTIVE.value,
        )

    # -------------------------------------------------------------- #
    #  Readers                                                        #
    # -------------------------------------------------------------- #

    def get_thought(self, thought_id: int) -> dict | None:
        """Return a single thought by id, or None if not found."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM private_thoughts WHERE thought_id = ?",
                (int(thought_id),),
            ).fetchone()
        finally:
            conn.close()
        return self._row_to_dict(row) if row else None

    def recent(self, limit: int = 20) -> list[dict]:
        """Recent thoughts, newest first. No content filter, no
        phase filter — future readers layer those on top."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM private_thoughts ORDER BY thought_id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        finally:
            conn.close()
        return [self._row_to_dict(r) for r in rows]

    def count(self) -> int:
        """Total number of private thoughts recorded."""
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute("SELECT COUNT(*) FROM private_thoughts").fetchone()
        finally:
            conn.close()
        return int(row[0]) if row else 0

    def derived_signals(self, limit: int = 50) -> dict:
        return self.behavior_reader().derived_signals(limit=limit)

    def behavior_reader(self) -> PrivateSignalReader:
        return PrivateSignalReader(self.db_path)

    def _derived_signals_behavior(self, limit: int = 50) -> dict:
        """Return bounded private-thought signals without raw content.

        The reader exposes only coarse behavior classes and aggregate
        states from rows whose envelope allows `private_reader`.
        Downstream code can know that a coarse class of private material
        exists without receiving the private text itself.
        """
        bounded_limit = max(1, min(int(limit), 100))
        scan_limit = max(100, bounded_limit * max(1, len(SignalClass.values())) * 4)
        rows = self._recent_behavior_signal_metadata(limit=scan_limit)

        malformed_signal_row_count = 0
        for row in rows:
            if not self._normalize_signal_row(row):
                malformed_signal_row_count += 1

        class_counts: dict[str, int] = {}
        for signal_class in SignalClass.values():
            count = 0
            for row in self._behavior_signal_metadata_for_class(signal_class):
                if self._normalize_signal_row(row):
                    count += 1
                    if count >= bounded_limit:
                        break
            class_counts[signal_class] = count

        signal_classes = {
            signal_class: {
                "state": "present" if count > 0 else "absent",
                "count": count,
                "surface_sensitivity": SurfaceSensitivity.BEHAVIOR_SAFE_COARSE.value,
            }
            for signal_class, count in class_counts.items()
        }

        return {
            "bounded": True,
            "limit": bounded_limit,
            "raw_text_included": False,
            "malformed_signal_row_count": malformed_signal_row_count,
            "scan_truncated": len(rows) >= scan_limit,
            "signal_classes": signal_classes,
        }

    def _recent_behavior_signal_metadata(self, limit: int) -> list[dict]:
        """Recent behavior-safe metadata only; never selects raw content or handles."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT context_json, memory_phase, envelope_version, schema_version, "
                "producer_id, signal_kind, signal_class, surface_sensitivity, "
                "signal_state "
                "FROM private_thoughts "
                "WHERE provenance != ? "
                "ORDER BY thought_id DESC LIMIT ?",
                ("explicit_api", int(limit)),
            ).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    def _behavior_signal_metadata_for_class(self, signal_class: str) -> list[dict]:
        """Behavior metadata for one class; avoids chatty classes hiding rare ones."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT context_json, memory_phase, envelope_version, schema_version, "
                "producer_id, signal_kind, signal_class, surface_sensitivity, "
                "signal_state "
                "FROM private_thoughts "
                "WHERE provenance != ? AND signal_class = ? "
                "ORDER BY thought_id DESC",
                ("explicit_api", str(signal_class)),
            ).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    def _recent_forensic_signal_metadata(self, limit: int) -> list[dict]:
        """Recent forensic metadata; includes handles but not raw content."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT thought_id, provenance, context_json, memory_phase, "
                "envelope_version, schema_version, legacy_provenance, "
                "producer_id, signal_kind, signal_class, surface_sensitivity, "
                "signal_state "
                "FROM private_thoughts "
                "WHERE provenance != ? "
                "ORDER BY thought_id DESC LIMIT ?",
                ("explicit_api", int(limit)),
            ).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    # -------------------------------------------------------------- #
    #  Helpers                                                        #
    # -------------------------------------------------------------- #

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        try:
            d["context"] = json.loads(d.pop("context_json") or "{}")
        except (json.JSONDecodeError, TypeError):
            d["context"] = {}
            d.pop("context_json", None)
        return d

    @staticmethod
    def _row_is_current_version(row: dict) -> bool:
        return (
            str(row.get("envelope_version") or ENVELOPE_VERSION) == ENVELOPE_VERSION
            and str(row.get("schema_version") or SCHEMA_VERSION) == SCHEMA_VERSION
        )

    @staticmethod
    def _context_allows_private_reader(row: dict) -> bool:
        try:
            context = json.loads(str(row.get("context_json") or "{}"))
        except (json.JSONDecodeError, TypeError):
            return False
        if not isinstance(context, dict):
            return False
        for key in ("source", "subject", "consent_tier", "retention"):
            value = context.get(key)
            if not isinstance(value, str) or not value.strip():
                return False
        try:
            ConsentTier.coerce(context["consent_tier"], "ConsentTier")
            RetentionRule.coerce(context["retention"], "RetentionRule")
        except ValueError:
            return False
        allowed_flows = context.get("allowed_flows")
        if (
            not isinstance(allowed_flows, list)
            or not allowed_flows
            or any(not isinstance(flow, str) or not flow.strip() for flow in allowed_flows)
        ):
            return False
        try:
            flows = [AllowedFlow.coerce(flow, "AllowedFlow") for flow in allowed_flows]
        except ValueError:
            return False
        return AllowedFlow.PRIVATE_READER.value in flows

    @classmethod
    def _normalize_legacy_values(cls, row: dict) -> dict[str, str | None]:
        legacy = row.get("legacy_provenance") or row.get("provenance")
        kind = row.get("signal_kind") or legacy
        if kind not in SignalKind.values():
            return {
                "legacy_provenance": str(legacy or ""),
                "producer_id": ProducerId.LEGACY_UNKNOWN.value,
                "signal_kind": None,
                "signal_class": None,
                "surface_sensitivity": SurfaceSensitivity.FORENSIC_SENSITIVE.value,
                "signal_state": SignalState.ACTIVE.value,
            }
        registry = _SIGNAL_REGISTRY[str(kind)]
        producer = row.get("producer_id")
        if (
            not producer
            or producer == ProducerId.LEGACY_UNKNOWN.value
            or producer not in ProducerId.values()
        ):
            producer = cls._producer_from_context(row) or ProducerId.LEGACY_UNKNOWN.value
        signal_class = row.get("signal_class") or registry["signal_class"]
        if signal_class not in SignalClass.values():
            signal_class = registry["signal_class"]
        sensitivity = row.get("surface_sensitivity")
        if sensitivity not in SurfaceSensitivity.values():
            sensitivity = SurfaceSensitivity.FORENSIC_SENSITIVE.value
        state = row.get("signal_state")
        if state not in SignalState.values():
            state = SignalState.ACTIVE.value
        return {
            "legacy_provenance": str(legacy or ""),
            "producer_id": str(producer),
            "signal_kind": str(kind),
            "signal_class": str(signal_class),
            "surface_sensitivity": str(sensitivity),
            "signal_state": str(state),
        }

    @staticmethod
    def _producer_from_context(row: dict) -> str | None:
        try:
            context = json.loads(str(row.get("context_json") or "{}"))
        except (json.JSONDecodeError, TypeError):
            return None
        if not isinstance(context, dict):
            return None
        source = context.get("source")
        return str(source) if source in ProducerId.values() else None

    def _normalize_signal_row(self, row: dict) -> dict[str, str] | None:
        if not self._row_is_current_version(row):
            return None
        try:
            producer_id = ProducerId.coerce(row.get("producer_id"), "ProducerId")
            signal_kind = SignalKind.coerce(row.get("signal_kind"), "SignalKind")
            signal_class = SignalClass.coerce(row.get("signal_class"), "SignalClass")
            surface_sensitivity = SurfaceSensitivity.coerce(
                row.get("surface_sensitivity"),
                "SurfaceSensitivity",
            )
            signal_state = SignalState.coerce(row.get("signal_state"), "SignalState")
        except ValueError:
            return None
        if signal_state != SignalState.ACTIVE.value:
            return None
        registry = _SIGNAL_REGISTRY[signal_kind]
        if producer_id != registry["producer_id"] or signal_class != registry["signal_class"]:
            return None
        if not self._context_allows_private_reader(row):
            return None
        return {
            "producer_id": producer_id,
            "signal_kind": signal_kind,
            "signal_class": signal_class,
            "surface_sensitivity": surface_sensitivity,
            "signal_state": signal_state,
        }

    def _normalize_forensic_signal_row(self, row: dict) -> dict[str, str] | None:
        if not self._row_is_current_version(row):
            return None
        values = self._normalize_legacy_values(row)
        signal_kind = values.get("signal_kind")
        signal_class = values.get("signal_class")
        if not signal_kind or not signal_class:
            return None
        if values["signal_state"] != SignalState.ACTIVE.value:
            return None
        if not self._context_allows_private_reader(row):
            return None
        return {
            "producer_id": str(values["producer_id"]),
            "signal_kind": str(signal_kind),
            "signal_class": str(signal_class),
            "surface_sensitivity": str(values["surface_sensitivity"]),
            "signal_state": str(values["signal_state"]),
        }

    def _insert_thought(
        self,
        *,
        content: str,
        provenance: str,
        context: dict | None,
        memory_phase: str,
        producer_id: str | None = None,
        signal_kind: str | None = None,
        signal_class: str | None = None,
        surface_sensitivity: str = SurfaceSensitivity.FORENSIC_SENSITIVE.value,
        signal_state: str = SignalState.ACTIVE.value,
    ) -> int:
        if memory_phase not in _RECOGNIZED_MEMORY_PHASES:
            raise ValueError(
                f"unknown memory_phase {memory_phase!r} "
                f"(allowed: {sorted(_RECOGNIZED_MEMORY_PHASES)})"
            )

        if not isinstance(content, str):
            raise ValueError(f"content must be a string, got {type(content).__name__}")
        content = content.strip()
        if not content:
            raise ValueError("content must be non-empty")
        if len(content) > MAX_CONTENT_LEN:
            raise ValueError(f"content length {len(content)} exceeds cap {MAX_CONTENT_LEN}")

        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                "INSERT INTO private_thoughts "
                "(ts, content, provenance, context_json, memory_phase, "
                "envelope_version, schema_version, legacy_provenance, "
                "producer_id, signal_kind, signal_class, surface_sensitivity, "
                "signal_state) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    time.time(),
                    content,
                    provenance,
                    json.dumps(context or {}),
                    memory_phase,
                    ENVELOPE_VERSION,
                    SCHEMA_VERSION,
                    provenance,
                    producer_id or ProducerId.LEGACY_UNKNOWN.value,
                    signal_kind,
                    signal_class,
                    surface_sensitivity,
                    signal_state,
                ),
            )
            thought_id = cur.lastrowid
            conn.commit()
        finally:
            conn.close()

        # Log the event but NOT the content. Content never reaches
        # the daemon log.
        logger.info(
            "Private signal recorded (phase=%s, len=%d)",
            memory_phase,
            len(content),
        )
        return thought_id

    @staticmethod
    def _require_non_empty_string(name: str, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
        return value.strip()

    @classmethod
    def _build_signal_context(
        cls,
        *,
        source: str,
        subject: str,
        consent_tier: str,
        retention: str,
        allowed_flows: tuple[str, ...] | list[str],
        context_extra: dict | None,
    ) -> dict:
        if not isinstance(allowed_flows, (tuple, list)) or not allowed_flows:
            raise ValueError("allowed_flows must be a non-empty tuple/list")
        flows = []
        for flow in allowed_flows:
            if not isinstance(flow, str):
                raise ValueError("allowed_flows entries must be strings")
            flows.append(
                AllowedFlow.coerce(
                    cls._require_non_empty_string("allowed_flows", flow),
                    "AllowedFlow",
                )
            )
        if not isinstance(context_extra, (dict, type(None))):
            raise ValueError("context_extra must be a dict when provided")

        context = {
            "source": cls._require_non_empty_string("source", source),
            "subject": cls._require_non_empty_string("subject", subject),
            "consent_tier": ConsentTier.coerce(
                cls._require_non_empty_string("consent_tier", consent_tier),
                "ConsentTier",
            ),
            "retention": RetentionRule.coerce(
                cls._require_non_empty_string("retention", retention),
                "RetentionRule",
            ),
            "allowed_flows": flows,
            "extra": dict(context_extra or {}),
        }
        missing = [key for key in _CONTEXT_REQUIRED_KEYS if key not in context]
        if missing:
            raise ValueError("signal context missing required key(s): " + ", ".join(missing))
        return context


# ══════════════════════════════════════════════════════════════════════
#  Self-test (python3 core/private_thoughts.py)
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import tempfile

    _counts = [0, 0]

    def _assert(cond: bool, label: str) -> None:
        if cond:
            _counts[0] += 1
            print(f"  OK   {label}")
        else:
            _counts[1] += 1
            print(f"  FAIL {label}")

    print("private_thoughts self-test")
    print("-" * 60)

    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "private_thoughts_test.db"

        # -- constants
        _assert("explicit_api" in ALLOWED_PROVENANCES, "explicit_api remains an allowed provenance")
        _assert(
            "audit_held" in ALLOWED_PROVENANCES, "S1 producer provenance 'audit_held' is allowed"
        )
        _assert(MAX_CONTENT_LEN == 16384, "MAX_CONTENT_LEN is 16384")
        _assert(
            "gestation" in _RECOGNIZED_MEMORY_PHASES, "'gestation' is a recognized memory_phase"
        )
        _assert("lived" in _RECOGNIZED_MEMORY_PHASES, "'lived' is a recognized memory_phase")

        # -- fresh log is empty
        P = PrivateThoughts(db_path=db)
        _assert(P.count() == 0, "fresh log has zero thoughts")
        _assert(P.recent() == [], "fresh log has no recent thoughts")
        _assert(P.get_thought(1) is None, "get_thought on nonexistent id returns None")

        # -- first write
        tid1 = P.record_thought(
            content="Something about the owner's grandmother story "
            "landed differently than I expected.",
            context={"cycle": 42, "after_message": "grandmother"},
        )
        _assert(isinstance(tid1, int) and tid1 > 0, "record_thought returns positive thought_id")
        _assert(P.count() == 1, "count() == 1 after one write")

        got = P.get_thought(tid1)
        _assert(got is not None, "get_thought returns the new row")
        _assert(got["content"].startswith("Something about"), "content preserved")
        _assert(got["provenance"] == "explicit_api", "provenance defaults to 'explicit_api'")
        _assert(got["memory_phase"] == "gestation", "memory_phase defaults to 'gestation'")
        _assert(
            got["context"] == {"cycle": 42, "after_message": "grandmother"},
            "context_json unpacked into dict",
        )

        # -- second write
        tid2 = P.record_thought(
            content="I'm not sure why that one hit.",
            memory_phase="gestation",
        )
        _assert(tid2 > tid1, "second thought_id is larger")
        _assert(P.count() == 2, "count() == 2 after second write")

        # -- recent() is newest first
        recents = P.recent(limit=10)
        _assert(len(recents) == 2, "recent() has 2 rows")
        _assert(recents[0]["thought_id"] == tid2, "recent()[0] is the newest thought")

        # -- 'lived' memory_phase is accepted
        tid_lived = P.record_thought(
            content="A thought from after birth.",
            memory_phase="lived",
        )
        _assert(
            P.get_thought(tid_lived)["memory_phase"] == "lived", "memory_phase='lived' is accepted"
        )

        # -- unknown memory_phase raises
        try:
            P.record_thought(content="x", memory_phase="unknown_phase")
            _assert(False, "unknown memory_phase should raise")
        except ValueError:
            _assert(True, "unknown memory_phase raises ValueError")

        # -- unknown provenance raises
        try:
            P.record_thought(content="x", provenance="reasoning_reflection")
            _assert(False, "unknown provenance should raise in Track A")
        except ValueError:
            _assert(True, "Track A blocks unknown provenance strings")

        # -- empty content raises
        try:
            P.record_thought(content="")
            _assert(False, "empty content should raise")
        except ValueError:
            _assert(True, "empty content raises")

        # -- whitespace-only content raises
        try:
            P.record_thought(content="   \n  \t  ")
            _assert(False, "whitespace-only content should raise")
        except ValueError:
            _assert(True, "whitespace-only content raises")

        # -- non-string content raises
        try:
            P.record_thought(content=42)  # type: ignore[arg-type]
            _assert(False, "non-string content should raise")
        except ValueError:
            _assert(True, "non-string content raises")

        # -- content at cap accepted
        at_cap = "a" * MAX_CONTENT_LEN
        tid_cap = P.record_thought(content=at_cap)
        _assert(
            len(P.get_thought(tid_cap)["content"]) == MAX_CONTENT_LEN,
            "content at exactly MAX_CONTENT_LEN is accepted",
        )

        # -- content over cap raises
        try:
            P.record_thought(content="b" * (MAX_CONTENT_LEN + 1))
            _assert(False, "over-cap content should raise")
        except ValueError:
            _assert(True, "over-cap content raises")

        # -- reopening preserves state
        P2 = PrivateThoughts(db_path=db)
        _assert(P2.count() == P.count(), "reopening preserves count")
        _assert(P2.get_thought(tid1)["thought_id"] == tid1, "reopening preserves thought lookup")

        # -- schema: expected versioned S1a.1 columns
        conn = sqlite3.connect(db)
        cols = [info[1] for info in conn.execute("PRAGMA table_info(private_thoughts)").fetchall()]
        conn.close()
        expected_cols = {
            "thought_id",
            "ts",
            "content",
            "provenance",
            "context_json",
            "memory_phase",
            "envelope_version",
            "schema_version",
            "legacy_provenance",
            "producer_id",
            "signal_kind",
            "signal_class",
            "surface_sensitivity",
            "signal_state",
        }
        _assert(set(cols) == expected_cols, f"schema has exactly {sorted(expected_cols)}")
        _assert("topic" not in cols, "no 'topic' column")
        _assert("mood" not in cols, "no 'mood' column")
        _assert("intensity" not in cols, "no 'intensity' column")

        # -- default db path
        _assert("memory" in str(DEFAULT_DB_PATH), "DEFAULT_DB_PATH lives under memory/")
        _assert("private_thoughts" in str(DEFAULT_DB_PATH), "DEFAULT_DB_PATH names the store")

        # -- empty log edge cases on a fresh DB
        db2 = Path(td) / "pt_empty.db"
        E = PrivateThoughts(db_path=db2)
        _assert(E.count() == 0, "fresh empty log count==0")
        _assert(E.recent() == [], "fresh empty log recent==[]")

    print("-" * 60)
    print(f"{_counts[0]} passed, {_counts[1]} failed")
    raise SystemExit(0 if _counts[1] == 0 else 1)
