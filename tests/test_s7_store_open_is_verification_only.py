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
        with pytest.raises(Exception):
            s7.S7AuthorizationStore(path)
        with sqlite3.connect(path) as conn:
            names = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        assert "s7_authorization_artifacts" not in names
