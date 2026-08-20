# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Covenant ceremony phase store (design pass 4, contract frozen 2026-08-18).

The two-phase covenant ceremony for RULING-O work classes: a first
founder tap opens the window (no authority minted), RULING C's 24-hour
cooling-off elapses, and a second tap runs the one real authorization.
This module owns the durable phase rows, both binding digests, the
assembler that builds `CovenantCeremonyEvidence` from rows and nothing
else, and the consume-side revalidator with the activation interlock.

RULING C (owner, 2026-08-18): 24h cooling-off floor, code-refused below;
7-day phase-1 lifetime; supersede-never-edit. RULING B bounds the proof:
repository-owned callers through supported interfaces; raw store
mutation is outside it and its consequences are named in the design.
"""

from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.governance.successor_governance import canonical_hash

# RULING C constants. The floor is a FLOOR: nothing in this module or any
# caller may accept a smaller value, and there is deliberately no config
# knob to lower it.
COOLING_OFF_FLOOR_SECONDS = 24 * 3600
PHASE1_LIFETIME_SECONDS = 7 * 24 * 3600

# RULING C statement bytes, approved verbatim by the owner 2026-08-18.
COVENANT_PHASE1_NOTICE = (
    "COVENANT CEREMONY \u2014 STEP 1 OF 2. This tap authorizes nothing. It "
    "opens a 24-hour cooling-off period for the request below. After the "
    "cooling-off, a second tap will be required before anything can "
    "execute. An unconfirmed first tap lapses after 7 days."
)

COVENANT_WORK_CLASSES = frozenset({
    "covenant_touching_change",
    "autonomy_lowering_or_protection_reducing",
})

_TABLE = "s7_covenant_ceremony_phases_v1"
_HASH64_RE = re.compile(r"^[0-9a-f]{64}$")

_DDL = f"""
CREATE TABLE {_TABLE} (
    phase TEXT NOT NULL
        CHECK (phase IN ('first_authorization', 'second_confirmation')),
    request_id TEXT NOT NULL,
    request_envelope_hash TEXT NOT NULL,
    derived_work_class TEXT NOT NULL
        CHECK (derived_work_class IN ('covenant_touching_change',
                                      'autonomy_lowering_or_protection_reducing')),
    challenge_id TEXT NOT NULL UNIQUE,
    challenge_b64_sha256 TEXT NOT NULL,
    rendered_text_hash TEXT NOT NULL,
    session_binding_hash TEXT NOT NULL,
    internal_channel_binding_hash TEXT NOT NULL,
    credential_ref TEXT NOT NULL,
    user_presence INTEGER NOT NULL CHECK (user_presence = 1),
    user_verification INTEGER NOT NULL CHECK (user_verification = 1),
    sign_count INTEGER NOT NULL,
    challenge_created_at TEXT NOT NULL,
    challenge_expires_at TEXT NOT NULL,
    phase_expires_at TEXT,
    artifact_id TEXT,
    first_phase_binding_sha256 TEXT UNIQUE,
    supersedes_binding_sha256 TEXT UNIQUE,
    recorded_at TEXT NOT NULL,
    binding_sha256 TEXT NOT NULL UNIQUE,
    row_seal_sha256 TEXT NOT NULL UNIQUE
) STRICT
"""

_COLUMNS = (
    "phase", "request_id", "request_envelope_hash", "derived_work_class",
    "challenge_id", "challenge_b64_sha256", "rendered_text_hash",
    "session_binding_hash", "internal_channel_binding_hash",
    "credential_ref", "user_presence", "user_verification", "sign_count",
    "challenge_created_at", "challenge_expires_at", "phase_expires_at",
    "artifact_id", "first_phase_binding_sha256",
    "supersedes_binding_sha256", "recorded_at", "binding_sha256",
)


class CovenantCeremonyRefusal(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _parse_z(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except (TypeError, ValueError):
        raise CovenantCeremonyRefusal("covenant_timestamp_invalid") from None


def _fmt_z(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _require_hash64(value: str, field: str) -> str:
    if not isinstance(value, str) or _HASH64_RE.fullmatch(value) is None:
        raise CovenantCeremonyRefusal(f"covenant_{field}_invalid")
    return value


def covenant_seconds_between(earlier: str, later: str) -> float:
    """Elapsed seconds between two canonical Z timestamps."""
    return (_parse_z(later) - _parse_z(earlier)).total_seconds()


def covenant_phase1_binding(
    *,
    request_id: str,
    request_envelope_hash: str,
    derived_work_class: str,
    challenge_id: str,
    challenge_b64_sha256: str,
    rendered_text_hash: str,
    session_binding_hash: str,
    internal_channel_binding_hash: str,
    credential_ref: str,
    sign_count: int,
    challenge_created_at: str,
    challenge_expires_at: str,
    recorded_at: str,
) -> str:
    """The phase-1 correspondence digest. Exhaustive; sorted-key
    serialization via canonical_hash; every member persisted in the row."""
    return canonical_hash({
        "domain": "s7.covenant_phase1_binding.v1",
        "challenge_b64_sha256": challenge_b64_sha256,
        "challenge_created_at": challenge_created_at,
        "challenge_expires_at": challenge_expires_at,
        "challenge_id": challenge_id,
        "credential_ref": credential_ref,
        "derived_work_class": derived_work_class,
        "internal_channel_binding_hash": internal_channel_binding_hash,
        "recorded_at": recorded_at,
        "rendered_text_hash": rendered_text_hash,
        "request_envelope_hash": request_envelope_hash,
        "request_id": request_id,
        "session_binding_hash": session_binding_hash,
        "sign_count": int(sign_count),
        "user_presence": 1,
        "user_verification": 1,
    })


def covenant_phase2_binding(
    *,
    first_phase_binding_sha256: str,
    artifact_id: str,
    **phase1_shaped,
) -> str:
    """The phase-2 correspondence digest: this design's OWN device (same
    shape as 2b's artifact binding, distinct domain tag, no dependency)."""
    body = covenant_phase1_binding(**phase1_shaped)
    return canonical_hash({
        "domain": "s7.covenant_phase2_binding.v1",
        "artifact_id": artifact_id,
        "ceremony_body_sha256": body,
        "first_phase_binding_sha256": first_phase_binding_sha256,
    })


def _row_seal(values: dict) -> str:
    return canonical_hash({
        "domain": "s7.covenant_phase_row_seal.v1",
        **{k: values[k] for k in _COLUMNS},
    })


class CovenantPhaseStore:
    """SQLite store for covenant ceremony phase rows. Append-only:
    predecessors are superseded, never updated or deleted."""

    def __init__(self, db_path: str | Path, *, create: bool = True):
        self.db_path = Path(db_path)
        if not create:
            # The daemon's single-callsite rule: no creation authority on a
            # live request path -- not even an empty db file or a parent
            # directory (gate finding 14). Reads see no rows; writes refuse.
            return
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db_path)) as conn:
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (_TABLE,),
            ).fetchone()
            if row is None:
                conn.execute(_DDL)
                conn.commit()

    # -- contract fingerprint (the R11 device) ---------------------------
    def _table_exists(self, conn) -> bool:
        return conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (_TABLE,),
        ).fetchone() is not None

    def _contract(self, conn) -> tuple:
        sql_row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
            (_TABLE,),
        ).fetchone()
        if sql_row is None:
            raise CovenantCeremonyRefusal("covenant_store_integrity_failure")
        sql = re.sub(r"\s+", " ", str(sql_row[0])).strip().rstrip(";")
        cols = tuple(tuple(r) for r in conn.execute(f"PRAGMA table_info({_TABLE})"))
        return (sql, cols)

    _expected_contract_cache: tuple | None = None

    def _require_contract(self, conn) -> None:
        if CovenantPhaseStore._expected_contract_cache is None:
            with closing(sqlite3.connect(":memory:")) as ref:
                ref.execute(_DDL)
                CovenantPhaseStore._expected_contract_cache = self._contract(ref)
        if self._contract(conn) != CovenantPhaseStore._expected_contract_cache:
            raise CovenantCeremonyRefusal("covenant_store_contract_drift")

    # -- reads ------------------------------------------------------------
    def _rows(self, conn, request_id: str, phase: str) -> list[dict]:
        cur = conn.execute(
            f"SELECT {', '.join(_COLUMNS)}, row_seal_sha256 FROM {_TABLE} "
            "WHERE request_id = ? AND phase = ?",
            (request_id, phase),
        )
        out = []
        for raw in cur.fetchall():
            row = dict(zip((*_COLUMNS, "row_seal_sha256"), raw))
            if _row_seal(row) != row["row_seal_sha256"]:
                raise CovenantCeremonyRefusal("covenant_store_integrity_failure")
            out.append(row)
        return out

    def current_phase1(self, *, request_id: str, now: str) -> dict | None:
        now_dt = _parse_z(now)
        if not self.db_path.exists():
            return None
        with closing(sqlite3.connect(self.db_path)) as conn:
            if not self._table_exists(conn):
                return None
            self._require_contract(conn)
            rows = self._rows(conn, request_id, "first_authorization")
        superseded = {r["supersedes_binding_sha256"] for r in rows
                      if r["supersedes_binding_sha256"]}
        live = [r for r in rows if r["binding_sha256"] not in superseded
                and _parse_z(r["phase_expires_at"]) > now_dt]
        if not live:
            return None
        if len(live) > 1:
            raise CovenantCeremonyRefusal("covenant_store_integrity_failure")
        return live[0]

    def head_phase1(self, *, request_id: str) -> dict | None:
        """The lineage head: the unsuperseded phase-1 row, EXPIRED OR NOT.

        Supersession must link to the head even when it has lapsed --
        otherwise expired rows vanish from selection and their replacement
        carries no lineage (gate finding 9)."""
        if not self.db_path.exists():
            return None
        with closing(sqlite3.connect(self.db_path)) as conn:
            if not self._table_exists(conn):
                return None
            self._require_contract(conn)
            rows = self._rows(conn, request_id, "first_authorization")
        superseded = {r["supersedes_binding_sha256"] for r in rows
                      if r["supersedes_binding_sha256"]}
        heads = [r for r in rows if r["binding_sha256"] not in superseded]
        if not heads:
            return None
        if len(heads) > 1:
            raise CovenantCeremonyRefusal("covenant_store_integrity_failure")
        return heads[0]

    def phase2_for_request(self, *, request_id: str) -> dict | None:
        if not self.db_path.exists():
            return None
        with closing(sqlite3.connect(self.db_path)) as conn:
            if not self._table_exists(conn):
                return None
            self._require_contract(conn)
            rows = self._rows(conn, request_id, "second_confirmation")
        if not rows:
            return None
        if len(rows) > 1:
            raise CovenantCeremonyRefusal("covenant_store_integrity_failure")
        return rows[0]

    def phase1_by_binding(self, *, binding_sha256: str) -> dict | None:
        if not self.db_path.exists():
            return None
        with closing(sqlite3.connect(self.db_path)) as conn:
            if not self._table_exists(conn):
                return None
            self._require_contract(conn)
            cur = conn.execute(
                f"SELECT {', '.join(_COLUMNS)}, row_seal_sha256 FROM {_TABLE} "
                "WHERE binding_sha256 = ? AND phase = 'first_authorization'",
                (binding_sha256,),
            )
            raw = cur.fetchone()
        if raw is None:
            return None
        row = dict(zip((*_COLUMNS, "row_seal_sha256"), raw))
        if _row_seal(row) != row["row_seal_sha256"]:
            raise CovenantCeremonyRefusal("covenant_store_integrity_failure")
        return row

    # -- writes -----------------------------------------------------------
    def _insert(self, *, values: dict, connection: sqlite3.Connection | None = None) -> str:
        values = dict(values)
        values["row_seal_sha256"] = _row_seal(values)

        def _write(conn: sqlite3.Connection) -> None:
            if not self._table_exists(conn):
                raise CovenantCeremonyRefusal("covenant_store_unprovisioned")
            self._require_contract(conn)
            try:
                conn.execute(
                    f"INSERT INTO {_TABLE} ({', '.join((*_COLUMNS, 'row_seal_sha256'))}) "
                    f"VALUES ({', '.join('?' for _ in range(len(_COLUMNS) + 1))})",
                    tuple(values[k] for k in (*_COLUMNS, "row_seal_sha256")),
                )
            except sqlite3.IntegrityError:
                raise CovenantCeremonyRefusal("covenant_uniqueness_conflict") from None

        if connection is not None:
            # Caller owns the transaction: the write is atomic with whatever
            # ceremony act shares it (challenge consumption, artifact mint).
            _write(connection)
        else:
            if not self.db_path.exists():
                raise CovenantCeremonyRefusal("covenant_store_unprovisioned")
            with closing(sqlite3.connect(self.db_path)) as conn:
                _write(conn)
                conn.commit()
        return values["binding_sha256"]

    def insert_phase1(
        self,
        *,
        supersedes_binding_sha256: str | None = None,
        connection: sqlite3.Connection | None = None,
        **kw,
    ) -> str:
        if kw.get("derived_work_class") not in COVENANT_WORK_CLASSES:
            raise CovenantCeremonyRefusal("covenant_work_class_invalid")
        _require_hash64(kw["request_envelope_hash"], "request_envelope_hash")
        recorded = _parse_z(kw["recorded_at"])
        live = self.current_phase1(
            request_id=kw["request_id"], now=kw["recorded_at"]
        )
        if supersedes_binding_sha256 is None:
            if live is not None:
                raise CovenantCeremonyRefusal("covenant_phase1_already_live")
        else:
            predecessor = self.phase1_by_binding(
                binding_sha256=supersedes_binding_sha256
            )
            if predecessor is None:
                raise CovenantCeremonyRefusal("covenant_supersedes_unknown")
        binding = covenant_phase1_binding(**kw)
        return self._insert(connection=connection, values={
            **kw,
            "phase": "first_authorization",
            "user_presence": 1,
            "user_verification": 1,
            "phase_expires_at": _fmt_z(
                recorded + timedelta(seconds=PHASE1_LIFETIME_SECONDS)
            ),
            "artifact_id": None,
            "first_phase_binding_sha256": None,
            "supersedes_binding_sha256": supersedes_binding_sha256,
            "binding_sha256": binding,
        })

    def insert_phase2(
        self,
        *,
        first_phase_binding_sha256: str,
        artifact_id: str,
        connection: sqlite3.Connection | None = None,
        **kw,
    ) -> str:
        if kw.get("derived_work_class") not in COVENANT_WORK_CLASSES:
            raise CovenantCeremonyRefusal("covenant_work_class_invalid")
        if not artifact_id:
            raise CovenantCeremonyRefusal("covenant_artifact_id_required")
        # Maturity is measured from the phase-2 CHALLENGE's creation, so a
        # tap on a challenge minted before maturity cannot confirm even if
        # finish arrives later.
        phase1 = self.current_phase1(
            request_id=kw["request_id"], now=kw["challenge_created_at"]
        )
        if phase1 is None or phase1["binding_sha256"] != first_phase_binding_sha256:
            raise CovenantCeremonyRefusal("covenant_phase1_not_current")
        if (
            phase1["request_envelope_hash"] != kw["request_envelope_hash"]
            or phase1["derived_work_class"] != kw["derived_work_class"]
        ):
            raise CovenantCeremonyRefusal("covenant_phase1_mismatch")
        elapsed = (
            _parse_z(kw["challenge_created_at"])
            - _parse_z(phase1["recorded_at"])
        ).total_seconds()
        if elapsed < COOLING_OFF_FLOOR_SECONDS:
            raise CovenantCeremonyRefusal("covenant_cooling_off_immature")
        binding = covenant_phase2_binding(
            first_phase_binding_sha256=first_phase_binding_sha256,
            artifact_id=artifact_id,
            **kw,
        )
        return self._insert(connection=connection, values={
            **kw,
            "phase": "second_confirmation",
            "user_presence": 1,
            "user_verification": 1,
            "phase_expires_at": None,
            "artifact_id": artifact_id,
            "first_phase_binding_sha256": first_phase_binding_sha256,
            "supersedes_binding_sha256": None,
            "binding_sha256": binding,
        })


def assemble_covenant_ceremony_evidence(
    store: CovenantPhaseStore, *, request_id: str, now: str
):
    """Build CovenantCeremonyEvidence from the rows and nothing else.
    Returns None when the ceremony is incomplete -- the fail-closed default
    stands until both phases exist."""
    from core.governance.operator_user_boundary import CovenantCeremonyEvidence

    phase2 = store.phase2_for_request(request_id=request_id)
    if phase2 is None:
        return None
    phase1 = store.phase1_by_binding(
        binding_sha256=phase2["first_phase_binding_sha256"]
    )
    if phase1 is None:
        raise CovenantCeremonyRefusal("covenant_store_integrity_failure")
    return CovenantCeremonyEvidence(
        request_id=phase2["request_id"],
        request_envelope_hash=phase2["request_envelope_hash"],
        ceremony_kind="cooling_off_second_confirmation",
        first_authorized_at=phase1["recorded_at"],
        second_confirmed_at=phase2["recorded_at"],
        second_confirmation_ref_hash=phase2["binding_sha256"],
        reviewed_equivalent_ref_hash=None,
    )


def _rows_on(conn: sqlite3.Connection, request_id: str, phase: str) -> list[dict]:
    """Seal-verified phase rows read through the CALLER'S connection --
    at the consume seat that is the descriptor-held connection, so the rows
    come from the same inode as the artifact CAS (gate finding 4)."""
    table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (_TABLE,)
    ).fetchone()
    if table is None:
        return []
    cur = conn.execute(
        f"SELECT {', '.join(_COLUMNS)}, row_seal_sha256 FROM {_TABLE} "
        "WHERE request_id = ? AND phase = ?",
        (request_id, phase),
    )
    out = []
    for raw in cur.fetchall():
        row = dict(zip((*_COLUMNS, "row_seal_sha256"), raw))
        if _row_seal(row) != row["row_seal_sha256"]:
            raise CovenantCeremonyRefusal("covenant_store_integrity_failure")
        out.append(row)
    return out


def revalidate_covenant_ceremony_for_consumption(
    *,
    connection: sqlite3.Connection,
    evidence,
    request_id: str,
    request_envelope_hash: str,
    derived_work_class: str,
    artifact_id: str,
    now: str,
) -> None:
    """Re-derive the ceremony from rows inside the consuming transaction.

    Order: row bindings first (caller-built evidence is refused before
    anything else is considered), then the ACTIVATION INTERLOCK -- the
    fail-closed arm that refuses RULING-O consumption until cluster 2b's
    owner-read receipt exists and can be joined. That arm is what makes
    "dormant" structural rather than polite: it refuses for EVERY caller
    until 2b lands, witness included.
    """
    if derived_work_class not in COVENANT_WORK_CLASSES:
        raise CovenantCeremonyRefusal("covenant_work_class_invalid")
    phase2_rows = _rows_on(connection, request_id, "second_confirmation")
    if len(phase2_rows) > 1:
        raise CovenantCeremonyRefusal("covenant_store_integrity_failure")
    if not phase2_rows:
        raise CovenantCeremonyRefusal("covenant_ceremony_incomplete")
    phase2 = phase2_rows[0]
    phase1_rows = [
        r for r in _rows_on(connection, request_id, "first_authorization")
        if r["binding_sha256"] == phase2["first_phase_binding_sha256"]
    ]
    if not phase1_rows:
        raise CovenantCeremonyRefusal("covenant_store_integrity_failure")
    phase1 = phase1_rows[0]
    # Both correspondence digests recomputed from the persisted inputs, and
    # the cooling-off recomputed from the rows -- never trusted from the
    # carrier (gate finding 8).
    recomputed_p1 = covenant_phase1_binding(
        **{k: phase1[k] for k in (
            "request_id", "request_envelope_hash", "derived_work_class",
            "challenge_id", "challenge_b64_sha256", "rendered_text_hash",
            "session_binding_hash", "internal_channel_binding_hash",
            "credential_ref", "sign_count", "challenge_created_at",
            "challenge_expires_at", "recorded_at",
        )}
    )
    if recomputed_p1 != phase1["binding_sha256"]:
        raise CovenantCeremonyRefusal("covenant_store_integrity_failure")
    recomputed_p2 = covenant_phase2_binding(
        first_phase_binding_sha256=phase2["first_phase_binding_sha256"],
        artifact_id=phase2["artifact_id"],
        **{k: phase2[k] for k in (
            "request_id", "request_envelope_hash", "derived_work_class",
            "challenge_id", "challenge_b64_sha256", "rendered_text_hash",
            "session_binding_hash", "internal_channel_binding_hash",
            "credential_ref", "sign_count", "challenge_created_at",
            "challenge_expires_at", "recorded_at",
        )}
    )
    if recomputed_p2 != phase2["binding_sha256"]:
        raise CovenantCeremonyRefusal("covenant_store_integrity_failure")
    if (
        covenant_seconds_between(
            phase1["recorded_at"], phase2["challenge_created_at"]
        )
        < COOLING_OFF_FLOOR_SECONDS
    ):
        raise CovenantCeremonyRefusal("covenant_cooling_off_immature")
    from core.governance.operator_user_boundary import CovenantCeremonyEvidence

    assembled = CovenantCeremonyEvidence(
        request_id=phase2["request_id"],
        request_envelope_hash=phase2["request_envelope_hash"],
        ceremony_kind="cooling_off_second_confirmation",
        first_authorized_at=phase1["recorded_at"],
        second_confirmed_at=phase2["recorded_at"],
        second_confirmation_ref_hash=phase2["binding_sha256"],
        reviewed_equivalent_ref_hash=None,
    )
    if (
        evidence is None
        or evidence.request_id != assembled.request_id
        or evidence.request_envelope_hash != assembled.request_envelope_hash
        or evidence.ceremony_kind != assembled.ceremony_kind
        or evidence.first_authorized_at != assembled.first_authorized_at
        or evidence.second_confirmed_at != assembled.second_confirmed_at
        or evidence.second_confirmation_ref_hash
        != assembled.second_confirmation_ref_hash
        or request_envelope_hash != assembled.request_envelope_hash
        or phase2["derived_work_class"] != derived_work_class
        or phase2["artifact_id"] != artifact_id
    ):
        raise CovenantCeremonyRefusal("covenant_evidence_not_bound_to_rows")
    # ACTIVATION INTERLOCK (design §4; mutation-tested). Gate round on the
    # build: table EXISTENCE is not the arm -- installing 2b's schema would
    # have lifted it globally before any receipt existed. The arm is a
    # MATCHING receipt row for this artifact; 2b's own revalidator will
    # verify the row's content when it lands.
    receipt_table = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' "
        "AND name='s7_consult_owner_read_receipts_v1'"
    ).fetchone()
    if receipt_table is None:
        raise CovenantCeremonyRefusal("owner_read_receipt_required")
    receipt_row = connection.execute(
        "SELECT 1 FROM s7_consult_owner_read_receipts_v1 WHERE artifact_id = ?",
        (artifact_id,),
    ).fetchone()
    if receipt_row is None:
        raise CovenantCeremonyRefusal("owner_read_receipt_required")
