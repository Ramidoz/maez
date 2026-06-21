"""Veto-event ledger (Slice 3a). Records every learned veto with its belief snapshot, and
classifies whether the veto was right from an explicit exact-repeat re-ask's second reach.
Silence -> 'uncontested' (weak), never 'likely_right'. Pure; no daemon imports."""
from __future__ import annotations
import sqlite3, uuid, os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

_REASK_WINDOW_S = 3600          # "what counts as a re-ask" window (1h). A definition, not a trust knob.
_USEFUL = {"structured_evidence"}                 # reach produced useful evidence -> veto was overcautious
_REACH_FAILED = {"unusable", "empty_but_honest"}  # reach also produced nothing useful -> restraint was wise

def classify_outcome(outcome_quality: str) -> str:
    """The re-ask's second reach -> verdict on the ORIGINAL veto. Never 'uncontested' (that is the
    no-re-ask case, set elsewhere)."""
    if outcome_quality in _USEFUL:
        return "likely_wrong"
    if outcome_quality in _REACH_FAILED:
        return "likely_right"
    return "ambiguous"

@dataclass(frozen=True)
class VetoEvent:
    id: str
    class_id: str
    tool: str
    prior_n: int
    prior_success_rate: float
    prior_confidence: float
    turn_id: str | None
    surface: str
    created_at: float
    reask_turn_id: str | None
    reask_outcome_quality: str | None
    classification: str | None   # None = open; else likely_wrong/likely_right/uncontested/ambiguous

def _default_db_path() -> Path:
    override = os.environ.get("MAEZ_VETO_LEDGER_DB_PATH")
    if override:
        return Path(override)
    from core.routing.observation import _default_db_path as _obs_db
    return _obs_db().parent / "veto_ledger.db"

class VetoLedger:
    def __init__(self, *, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else _default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path); conn.row_factory = sqlite3.Row
        try: yield conn
        finally: conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn, conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS veto_events (
                    id TEXT PRIMARY KEY, class_id TEXT NOT NULL, tool TEXT NOT NULL,
                    prior_n INTEGER NOT NULL, prior_success_rate REAL NOT NULL, prior_confidence REAL NOT NULL,
                    turn_id TEXT, surface TEXT NOT NULL, created_at REAL NOT NULL,
                    reask_turn_id TEXT, reask_outcome_quality TEXT, classification TEXT )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_veto_open ON veto_events(class_id, tool, classification)")

    def record_veto(self, *, class_id, tool, prior_n, prior_success_rate, prior_confidence,
                    turn_id, surface, now) -> str:
        eid = uuid.uuid4().hex
        with self._connect() as conn, conn:
            conn.execute("INSERT INTO veto_events (id,class_id,tool,prior_n,prior_success_rate,"
                "prior_confidence,turn_id,surface,created_at,reask_turn_id,reask_outcome_quality,classification)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (eid, class_id, tool, int(prior_n), float(prior_success_rate), float(prior_confidence),
                 turn_id, surface, float(now), None, None, None))
        return eid

    def _resolve_expired(self, now) -> None:
        """Lazy: open events past the window with no re-ask -> 'uncontested' (weak). No scheduler."""
        with self._connect() as conn, conn:
            conn.execute("UPDATE veto_events SET classification='uncontested' "
                "WHERE classification IS NULL AND reask_turn_id IS NULL AND created_at < ?",
                (float(now) - _REASK_WINDOW_S,))

    def find_open_for_class(self, class_id, tool, *, now, within_s=_REASK_WINDOW_S) -> VetoEvent | None:
        self._resolve_expired(now)
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM veto_events WHERE class_id=? AND tool=? "
                "AND classification IS NULL AND created_at >= ? ORDER BY created_at DESC LIMIT 1",
                (class_id, tool, float(now) - within_s)).fetchone()
        return _row_to_event(row) if row else None

    def attach_reask_outcome(self, event_id, *, reask_turn_id, reask_outcome_quality) -> str:
        cls = classify_outcome(reask_outcome_quality)
        with self._connect() as conn, conn:
            conn.execute("UPDATE veto_events SET reask_turn_id=?, reask_outcome_quality=?, classification=? "
                "WHERE id=?", (reask_turn_id, reask_outcome_quality, cls, event_id))
        return cls

    def all_events(self) -> list[VetoEvent]:
        with self._connect() as conn:
            return [_row_to_event(r) for r in conn.execute("SELECT * FROM veto_events ORDER BY created_at")]

def _row_to_event(row) -> VetoEvent:
    return VetoEvent(row["id"], row["class_id"], row["tool"], row["prior_n"], row["prior_success_rate"],
        row["prior_confidence"], row["turn_id"], row["surface"], row["created_at"],
        row["reask_turn_id"], row["reask_outcome_quality"], row["classification"])
