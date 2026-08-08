"""S7 store opening is verification-only — the ratified PREREQUISITE.

Found while strengthening the migration matrix, and ruled a separate
immediate prerequisite rather than part of a commit called "migration
only": `S7AuthorizationStore.__init__` currently runs
`CREATE TABLE IF NOT EXISTS` and COMMITS on every open. Opening the
lockbox rebuilds parts of the lockbox.

That matters beyond tidiness. The design requires normal opening to be
verification-only -- it may read and verify a fingerprint, and may never
create, alter, migrate or commit -- precisely because
`daemon/maez_daemon.py` constructs the mutating store on the live request
path. A constructor that writes DDL can resurrect a table the migration
deliberately froze, and it makes "the schema I verified" and "the schema
I created" the same act.

The ruling, and the shape pinned here:

* an explicit v1 initialization seam owned by bootstrap/setup and private
  fixtures creates the store;
* ordinary `S7AuthorizationStore(...)` opening then performs NO mkdir, no
  DDL, no ALTER, no DML and no COMMIT;
* opening a store that does not exist REFUSES rather than creating one.

Every test runs against a tmp_path. Nothing here touches the live store.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from core.governance import operator_user_boundary as s7

REPO = Path(__file__).resolve().parents[1]

WRITE_VERBS = ("CREATE ", "ALTER ", "DROP ", "INSERT ", "UPDATE ", "DELETE ")


def _initialise(tmp: Path):
    """The explicit initialization seam.

    Named separately from the constructor on purpose: 'build it once' and
    'open and verify it' are different authorities, and only the first may
    write.
    """
    assert hasattr(s7, "initialise_authorization_store"), (
        "no explicit initialization seam exists yet; the constructor still "
        "builds the store it is supposed to merely open"
    )
    return s7.initialise_authorization_store(tmp / "ceremony.sqlite3")


def _record(monkeypatch):
    events: list[tuple[str, str]] = []
    real_connect = sqlite3.connect

    class Recording(sqlite3.Connection):
        def execute(self, sql, *a, **k):
            events.append(("sql", " ".join(str(sql).split())[:70]))
            return super().execute(sql, *a, **k)

        def executescript(self, sql, *a, **k):
            events.append(("sql", " ".join(str(sql).split())[:70]))
            return super().executescript(sql, *a, **k)

        def commit(self):
            events.append(("commit", ""))
            return super().commit()

    monkeypatch.setattr(
        sqlite3,
        "connect",
        lambda *a, **k: real_connect(*a, **{**k, "factory": Recording}),
    )
    return events


def _writes(events) -> list[str]:
    return [
        text
        for kind, text in events
        if kind == "sql" and any(v in text.upper() for v in WRITE_VERBS)
    ]


class TestTheInitialisationSeamExists:
    def test_there_is_an_explicit_initialiser(self, tmp_path: Path) -> None:
        _initialise(tmp_path)
        assert (tmp_path / "ceremony.sqlite3").exists()

    def test_the_initialiser_is_the_only_thing_that_creates(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """CONTROL for every refusal below: initialisation MUST write, or
        'opening does not write' would be trivially true of a seam that
        never works."""
        events = _record(monkeypatch)
        _initialise(tmp_path)
        assert _writes(events), events


class TestOpeningPerformsNoWrite:
    def test_opening_issues_no_ddl_or_dml(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        _initialise(tmp_path)
        events = _record(monkeypatch)
        s7.S7AuthorizationStore(tmp_path / "ceremony.sqlite3")
        assert not _writes(events), _writes(events)

    def test_opening_issues_no_commit(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        _initialise(tmp_path)
        events = _record(monkeypatch)
        s7.S7AuthorizationStore(tmp_path / "ceremony.sqlite3")
        assert not [k for k, _ in events if k == "commit"], events

    def test_opening_changes_no_byte(self, tmp_path: Path) -> None:
        """The strongest available observation: names and counts survive an
        ALTER or a stray commit, bytes do not."""
        _initialise(tmp_path)
        path = tmp_path / "ceremony.sqlite3"
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        s7.S7AuthorizationStore(path)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == before

    def test_opening_creates_no_directory(self, tmp_path: Path) -> None:
        """The constructor currently mkdirs. A store whose parent is absent
        is a store that was never initialised."""
        target = tmp_path / "absent" / "ceremony.sqlite3"
        with pytest.raises((FileNotFoundError, ValueError)):
            s7.S7AuthorizationStore(target)
        assert not (tmp_path / "absent").exists()

    def test_opening_a_missing_store_refuses(self, tmp_path: Path) -> None:
        """Creating on open is what let a frozen table quietly reappear."""
        target = tmp_path / "ceremony.sqlite3"
        with pytest.raises((FileNotFoundError, ValueError)):
            s7.S7AuthorizationStore(target)
        assert not target.exists()


class TestOpeningCannotResurrectAFrozenTable:
    def test_a_dropped_v1_table_is_not_recreated_on_open(
        self, tmp_path: Path
    ) -> None:
        """The concrete harm: migration freezes v1, something drops it, and
        the next open silently rebuilds it unfrozen -- restoring exactly the
        legacy write path the freeze triggers exist to close.
        """
        _initialise(tmp_path)
        path = tmp_path / "ceremony.sqlite3"
        with sqlite3.connect(path) as conn:
            conn.execute("DROP TABLE s7_authorization_artifacts")
            conn.commit()
        with pytest.raises((ValueError, sqlite3.DatabaseError, FileNotFoundError)):
            s7.S7AuthorizationStore(path)
        with sqlite3.connect(path) as conn:
            names = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        assert "s7_authorization_artifacts" not in names


V1_SOURCE_FINGERPRINT_AUTH = (
    "b8946c79c8edf9386ce73522aac8b18b6181212a949570cf9c01c01e3ac1af00"
)
V1_AUTH = "s7_authorization_artifacts"
V2_AUTH = "s7_authorization_artifacts_v2"
RECEIPT_NAME = "s7_migration_receipt.json"

# FROZEN CHOICE, made here rather than left open.
#
# "Idempotent" and "one-shot refusal" are both defensible, and the review
# asked for one. One-shot-refuse-if-exists cannot work: the live store
# already exists, so bootstrap could never run against it. Plain
# idempotence is worse -- CREATE TABLE IF NOT EXISTS would rebuild a table
# that migration froze and something dropped, which is the exact
# resurrection this prerequisite exists to prevent.
#
# Frozen: IDEMPOTENT-VERIFY.
#   absent            -> create
#   present, correct  -> verify, change nothing
#   present, damaged  -> REFUSE, never repair
IDEMPOTENT_VERIFY = "absent creates; correct verifies; damaged refuses"


def _tables(path: Path) -> set[str]:
    with sqlite3.connect(path) as conn:
        return {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }


def _fingerprint(path: Path, table_names) -> str:
    import json
    import re

    def canon(sql):
        return None if sql is None else re.sub(r"\s+", " ", sql).strip().rstrip(";")

    rows = []
    with sqlite3.connect(path) as conn:
        for name in sorted(table_names):
            for t, n, tbl, sql in conn.execute(
                "SELECT type,name,tbl_name,sql FROM sqlite_master "
                "WHERE tbl_name=? ORDER BY type,name",
                (name,),
            ):
                rows.append([t, n, tbl, canon(sql)])
    payload = json.dumps(
        rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(payload).hexdigest()


class TestTheInitialiserContract:
    """Without these, a request-path caller could invoke creation authority
    and resurrect v1 while every open-side test still passed."""

    def test_it_builds_the_exact_v1_authorization_schema(
        self, tmp_path: Path
    ) -> None:
        """Pinned to the ratified v1 source fingerprint, so the initializer
        cannot build something merely similar."""
        _initialise(tmp_path)
        assert (
            _fingerprint(tmp_path / "ceremony.sqlite3", [V1_AUTH])
            == V1_SOURCE_FINGERPRINT_AUTH
        )

    def test_it_creates_no_v2_tables(self, tmp_path: Path) -> None:
        """Initialization is not migration. Creating v2 here would activate
        a plane no receipt vouches for."""
        _initialise(tmp_path)
        assert V2_AUTH not in _tables(tmp_path / "ceremony.sqlite3")

    def test_it_publishes_no_receipt(self, tmp_path: Path) -> None:
        _initialise(tmp_path)
        assert not (tmp_path / RECEIPT_NAME).exists()

    def test_it_installs_no_freeze_triggers(self, tmp_path: Path) -> None:
        """The wall belongs to migration; a freshly initialized store is
        writable v1."""
        with sqlite3.connect(tmp_path / "ceremony.sqlite3") as _c:
            pass
        _initialise(tmp_path)
        with sqlite3.connect(tmp_path / "ceremony.sqlite3") as conn:
            triggers = list(
                conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
            )
        assert not triggers, triggers

    def test_re_initialising_a_correct_store_changes_no_byte(
        self, tmp_path: Path
    ) -> None:
        """IDEMPOTENT-VERIFY, first branch: bootstrap must be re-runnable
        against the store that already exists."""
        _initialise(tmp_path)
        path = tmp_path / "ceremony.sqlite3"
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        _initialise(tmp_path)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == before

    def test_re_initialising_preserves_every_existing_row(
        self, tmp_path: Path
    ) -> None:
        """The live store holds real records; initialization may never be a
        data event."""
        store = _initialise(tmp_path)
        path = tmp_path / "ceremony.sqlite3"
        with sqlite3.connect(path) as conn:
            conn.execute(
                f"INSERT INTO {V1_AUTH} (artifact_id, request_id) VALUES (?, ?)",
                ("kept-1", "req-1"),
            )
            conn.commit()
        _initialise(tmp_path)
        with sqlite3.connect(path) as conn:
            kept = conn.execute(
                f"SELECT artifact_id FROM {V1_AUTH}"
            ).fetchall()
        assert ("kept-1",) in kept, (kept, store)

    def test_a_damaged_store_refuses_rather_than_being_repaired(
        self, tmp_path: Path
    ) -> None:
        """IDEMPOTENT-VERIFY, third branch, and the whole point: a dropped
        table is tampering, not an invitation to rebuild. Rebuilding would
        restore an UNFROZEN v1 after migration installed the wall."""
        _initialise(tmp_path)
        path = tmp_path / "ceremony.sqlite3"
        with sqlite3.connect(path) as conn:
            conn.execute(f"DROP TABLE {V1_AUTH}")
            conn.commit()
        with pytest.raises((ValueError, sqlite3.DatabaseError)):
            _initialise(tmp_path)
        assert V1_AUTH not in _tables(path)

    def test_the_initialiser_has_a_bootstrap_only_callsite_allowlist(
        self,
    ) -> None:
        """Creation authority must not be reachable from the request path.
        daemon/maez_daemon.py constructs the store on live requests; if it
        could also initialise, the constructor's power simply moved."""
        import ast
        import os

        allowed_prefixes = ("scripts/", "cli", "core/governance/")
        offenders: list[str] = []
        allowed_callers: list[str] = []
        skip = {".git", ".venv", "node_modules", "__pycache__", "tests", "docs"}
        files = []
        for dirpath, dirnames, filenames in os.walk(REPO):
            dirnames[:] = [
                d for d in dirnames if d not in skip and not d.startswith(".")
            ]
            files += [
                Path(dirpath, n) for n in filenames if n.endswith(".py")
            ]
        for path in files:
            rel = str(path.relative_to(REPO))
            try:
                tree = ast.parse(path.read_text())
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    name = (
                        node.func.attr
                        if isinstance(node.func, ast.Attribute)
                        else getattr(node.func, "id", None)
                    )
                    if name != "initialise_authorization_store":
                        continue
                    if rel.startswith(allowed_prefixes):
                        allowed_callers.append(rel)
                    else:
                        offenders.append(rel)
        # CONTROL: with no initializer there are NO callers, so "no
        # offenders" is true of a seam that does not exist. The allowlist
        # only means something once bootstrap actually calls it.
        assert allowed_callers, (
            "no bootstrap/setup caller invokes the initializer; the "
            "allowlist below is vacuous until one does"
        )
        assert not offenders, offenders
