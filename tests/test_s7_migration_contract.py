"""S7 v2 migration — the ratified RED matrix, written BEFORE implementation.

Without this, a skeletal table creator would satisfy every downstream link
test while violating most of the migration contract: it could migrate on
open, backfill rows, skip the freeze triggers, run outside a lock, leave
the journal in WAL, publish a receipt before fsync, or "repair" a store it
should have refused.

The design freezes an ORDERED 16-step procedure and a 5-row classification
matrix. Both are pinned here.

SAFETY. The canonical receipt lives at the LIVE locator,
`memory/s7_1_webauthn/s7_migration_receipt.json`, and the public
`read_migration_receipt()` opens exactly that. An earlier version of this
file called it from tmpdir tests and unlinked a global receipt path -- so
once migration existed, these tests would have read and DELETED the live
receipt. Every receipt access here goes through the private
`_read_migration_receipt(store_dir_fd=...)` against a tmpdir fd, and
`_drop_receipt` removes only the tmpdir's own file. No test in this module
may name the canonical path.

HONEST STATUS: the migration entrypoint does not exist yet, so every test
here fails at it. That is the intended pre-implementation state, not a
proof. Each is written so that once migration lands it fails or passes at
its OWN assertion, and the ratified order requires re-witnessing exactly
that before storage or minting is written.
"""

from __future__ import annotations

import contextlib
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from core.governance import operator_user_boundary as s7

V1_AUTH = "s7_authorization_artifacts"
V2_AUTH = "s7_authorization_artifacts_v2"
V1_VOICE = "s7_voice_consultation_bundles"
V2_VOICE = "s7_voice_source_bundles_v2"

V1_AUTH_FREEZE = ("s7_v1_frozen_delete", "s7_v1_frozen_insert", "s7_v1_frozen_update")
V1_VOICE_FREEZE = (
    "s7_vb_v1_frozen_delete",
    "s7_vb_v1_frozen_insert",
    "s7_vb_v1_frozen_update",
)
V2_AUTH_EXCLUSION = ("s7_v2_no_v1_artifact", "s7_v2_no_v1_nonce")
V2_VOICE_EXCLUSION = ("s7_vb_v2_no_v1",)

RECEIPT_NAME = "s7_migration_receipt.json"
RECEIPT_SCHEMA = "s7.migration_receipt.v1"

NOW = "2026-08-07T12:00:00Z"
FUTURE = "2026-08-07T16:00:00Z"

# A refusal is a DECISION. These are crashes, and an implementation that
# raises one has not refused -- it has broken.
_CRASHES = (
    AttributeError,
    NameError,
    ImportError,
    TypeError,
    KeyError,
    IndexError,
    AssertionError,
    NotImplementedError,
)


@contextlib.contextmanager
def _refuses():
    """Assert a deliberate refusal -- never a crash, never a missing seam.

    `pytest.raises(Exception)` around a migration call passes on the
    AttributeError from the absent entrypoint, so every refusal test here
    reported GREEN before a line of migration existed. It also accepted any
    implementation crash as a refusal. Both are closed: the entrypoint must
    exist, and the raised error must be a refusal type rather than a bug.
    """
    assert hasattr(s7, "_migrate_authorization_store_to_v2_at"), (
        "migration entrypoint absent: a refusal cannot be distinguished "
        "from a missing seam until it exists"
    )
    try:
        yield
    except _CRASHES as exc:
        raise AssertionError(f"not a refusal, a crash: {exc!r}") from exc
    except (ValueError, sqlite3.DatabaseError, OSError):
        return
    except Exception as exc:  # noqa: BLE001 - deliberately surfaced
        raise AssertionError(
            f"refusal raised an unexpected type: {exc!r}"
        ) from exc
    raise AssertionError("expected a refusal; nothing was raised")


def _store(tmp: Path):
    return s7.S7AuthorizationStore(tmp / "ceremony.sqlite3")


@contextlib.contextmanager
def _dir_fd(tmp: Path):
    fd = os.open(tmp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        yield fd
    finally:
        os.close(fd)


def _migrate(tmp: Path) -> None:
    with _dir_fd(tmp) as fd:
        s7._migrate_authorization_store_to_v2_at(store_dir_fd=fd)


def _receipt(tmp: Path) -> dict:
    """The PRIVATE reader, against this tmpdir only.

    Never `read_migration_receipt()`: that opens the canonical live store.
    """
    with _dir_fd(tmp) as fd:
        return json.loads(s7._read_migration_receipt(store_dir_fd=fd))


def _drop_receipt(tmp: Path) -> None:
    """Simulate the crash window between COMMIT and publication.

    Removes only THIS tmpdir's receipt. It must never touch the canonical
    locator.
    """
    target = tmp / RECEIPT_NAME
    assert target.exists(), "no tmpdir receipt to remove; the test would be vacuous"
    target.unlink()


def _seed_legacy_row(tmp: Path, *, artifact_id="legacy-1", nonce=None) -> None:
    """A COMPLETE, valid v1 row, written through the real store.

    Trigger and collision tests are vacuous against an empty table: UPDATE
    and DELETE fire no BEFORE-row trigger, `INSERT ... SELECT FROM v1`
    inserts nothing, and a partial INSERT can abort on NOT NULL rather than
    on the trigger under test. Seeding through store.put guarantees the row
    is the shape production actually writes.
    """
    store = _store(tmp)
    store.put(
        s7.S7AuthorizationArtifact(
            artifact_id=artifact_id,
            request_id="req-legacy-1",
            request_envelope_hash="b" * 64,
            rendered_text_hash="c" * 64,
            action_params_hash="d" * 64,
            precondition_hash="a" * 64,
            authority_context_hash="e" * 64,
            derived_work_class="self_modification",
            derived_aggregation_group="s7agg_legacy",
            nonce=nonce or ("n" * 64),
            credential_ref="cred-1",
            auth_method="founder_webauthn",
            grant_source="founder_webauthn",
            user_presence=True,
            user_verification=True,
            created_at=NOW,
            expires_at=FUTURE,
            consumed_at=None,
            action="model_routing.cutover_cuda",
        )
    )


def _legacy_row(db_path) -> dict:
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(f"SELECT * FROM {V1_AUTH} LIMIT 1").fetchone()
    assert row is not None, "no legacy row; the caller forgot to seed"
    return dict(row)


def _tables(db_path) -> set[str]:
    with closing(sqlite3.connect(db_path)) as conn:
        return {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }


def _triggers(db_path, table: str) -> tuple[str, ...]:
    with closing(sqlite3.connect(db_path)) as conn:
        return tuple(
            sorted(
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'trigger' AND tbl_name = ?",
                    (table,),
                )
            )
        )


def _count(db_path, table: str) -> int:
    with closing(sqlite3.connect(db_path)) as conn:
        return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def _record(monkeypatch, *, fail_on_create: int | None = None):
    """An ordered event log of SQL, commits, fsyncs and links.

    sqlite3.Connection.execute is READ-ONLY, so an earlier injector that
    assigned to it never reached the fault it claimed to inject. A
    Connection SUBCLASS passed via `factory=` is the working route.
    """
    events: list[tuple[str, str]] = []
    real_connect = sqlite3.connect
    state = {"creates": 0}

    class Boom(sqlite3.DatabaseError):
        pass

    class Recording(sqlite3.Connection):
        def execute(self, sql, *a, **k):
            text = " ".join(str(sql).split())
            events.append(("sql", text[:70]))
            if fail_on_create is not None and "CREATE TABLE" in text.upper():
                state["creates"] += 1
                if state["creates"] == fail_on_create:
                    raise Boom("injected mid-migration fault")
            return super().execute(sql, *a, **k)

        def executescript(self, sql, *a, **k):
            events.append(("script", " ".join(str(sql).split())[:70]))
            return super().executescript(sql, *a, **k)

        def commit(self):
            events.append(("commit", ""))
            return super().commit()

        def rollback(self):
            events.append(("rollback", ""))
            return super().rollback()

    def connect(*args, **kwargs):
        kwargs["factory"] = Recording
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", connect)

    real_fsync = os.fsync
    monkeypatch.setattr(
        os, "fsync", lambda fd: (events.append(("fsync", str(fd))), real_fsync(fd))[1]
    )
    real_link = os.link


    def link(src, dst, **kw):
        events.append(("link", str(dst)))
        return real_link(src, dst, **kw)

    monkeypatch.setattr(os, "link", link)
    return events


def _kinds(events, kind: str) -> list[str]:
    return [payload for k, payload in events if k == kind]


def _first_index(events, predicate) -> int:
    for i, event in enumerate(events):
        if predicate(event):
            return i
    return -1


class TestTheEntrypointShape:
    """Two entrypoints, deliberately different: production takes NO root."""

    def test_the_public_entrypoint_takes_no_arguments(self) -> None:
        """A public-looking signature accepting a root recreates the
        alternate-root capability the design removed."""
        import inspect

        assert not inspect.signature(
            s7.migrate_authorization_store_to_v2
        ).parameters

    def test_the_private_helper_takes_a_directory_fd(self) -> None:
        import inspect

        assert set(
            inspect.signature(s7._migrate_authorization_store_to_v2_at).parameters
        ) == {"store_dir_fd"}

    def test_the_private_reader_takes_a_directory_fd(self) -> None:
        import inspect

        assert set(
            inspect.signature(s7._read_migration_receipt).parameters
        ) == {"store_dir_fd"}

    def test_the_private_reader_has_one_production_callsite(self) -> None:
        """Allowlist of exactly one: read_migration_receipt. Any other
        production caller can aim the private reader at a chosen root."""
        import ast

        import core.governance.operator_user_boundary as module

        tree = ast.parse(Path(module.__file__).read_text())
        callers = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    name = (
                        sub.func.attr
                        if isinstance(sub.func, ast.Attribute)
                        else getattr(sub.func, "id", None)
                    )
                    if name == "_read_migration_receipt":
                        callers.append(node.name)
        assert callers == ["read_migration_receipt"], callers


class TestNoTestHereTouchesTheLiveStore:
    """The hazard that made this module unsafe."""

    def test_this_module_never_names_the_canonical_receipt(self) -> None:
        """No executable string here may point at the live store.

        The needle is ASSEMBLED at runtime: written literally, it appears in
        this test's own source and the check fails on itself. Docstrings are
        excluded -- the module docstring names the locator deliberately, to
        record why this guard exists.
        """
        import ast

        needle = "memory/" + "s7_1_webauthn"
        tree = ast.parse(Path(__file__).read_text())
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(
                node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                doc = ast.get_docstring(node, clean=False)
                if doc:
                    docstrings.add(doc)
        offenders = [
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and needle in node.value
            and node.value not in docstrings
        ]
        assert not offenders, offenders

    def test_this_module_never_calls_the_public_reader(self) -> None:
        import ast

        tree = ast.parse(Path(__file__).read_text())
        called = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        assert "read_migration_receipt" not in called
        assert "_read_migration_receipt" in called


class TestNormalOpeningIsVerificationOnly:
    """`daemon/maez_daemon.py` constructs the mutating store on the live
    request path, so this must be structural rather than a convention."""

    def test_opening_a_store_does_not_create_v2(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        assert V2_AUTH not in _tables(store.db_path)

    def test_opening_a_store_does_not_create_freeze_triggers(
        self, tmp_path: Path
    ) -> None:
        store = _store(tmp_path)
        assert _triggers(store.db_path, V1_AUTH) == ()

    def test_opening_a_migrated_store_does_not_alter_it(
        self, tmp_path: Path
    ) -> None:
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        before = _tables(store.db_path), _triggers(store.db_path, V1_AUTH)
        _store(tmp_path)
        assert (_tables(store.db_path), _triggers(store.db_path, V1_AUTH)) == before


class TestTheOrderedProcedure:
    """Steps 5-13, observed through the state they leave behind."""

    def test_the_legacy_voice_table_is_created_empty(self, tmp_path: Path) -> None:
        """Step 5. v7 omitted this: an ABSENT voice plane must migrate to
        empty-and-frozen, not be skipped."""
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        assert V1_VOICE in _tables(store.db_path)
        assert _count(store.db_path, V1_VOICE) == 0

    def test_the_three_v1_voice_freeze_triggers_exist(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        assert _triggers(store.db_path, V1_VOICE) == V1_VOICE_FREEZE

    def test_the_three_v1_auth_freeze_triggers_exist(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        assert _triggers(store.db_path, V1_AUTH) == V1_AUTH_FREEZE

    def test_both_v2_tables_are_created(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        assert {V2_AUTH, V2_VOICE} <= _tables(store.db_path)

    def test_the_v2_exclusion_triggers_exist(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        assert _triggers(store.db_path, V2_AUTH) == V2_AUTH_EXCLUSION
        assert _triggers(store.db_path, V2_VOICE) == V2_VOICE_EXCLUSION

    def test_nothing_is_backfilled(self, tmp_path: Path) -> None:
        """Steps 10 and 13, with a v1 row PRESENT -- against an empty store
        "nothing was copied" is true for the wrong reason."""
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        assert _count(store.db_path, V1_AUTH) == 1
        _migrate(tmp_path)
        assert _count(store.db_path, V2_AUTH) == 0
        assert _count(store.db_path, V2_VOICE) == 0
        assert _count(store.db_path, V1_AUTH) == 1


class TestTheFreezeTriggersActuallyAbort:
    """Named triggers that do not fire are decoration.

    Every case runs against a SEEDED table: UPDATE and DELETE fire no
    BEFORE-row trigger on an empty one, so the earlier versions of these
    tests were watching empty rooms.
    """

    def test_insert_into_frozen_v1_auth_aborts(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        row = _legacy_row(store.db_path)
        _migrate(tmp_path)
        row["artifact_id"] = "fresh-1"
        row["nonce"] = "f" * 64
        columns = ", ".join(row)
        marks = ", ".join("?" for _ in row)
        with closing(sqlite3.connect(store.db_path)) as conn:
            with pytest.raises(sqlite3.DatabaseError):
                conn.execute(
                    f"INSERT INTO {V1_AUTH} ({columns}) VALUES ({marks})",
                    tuple(row.values()),
                )

    def test_update_of_frozen_v1_auth_aborts(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        assert _count(store.db_path, V1_AUTH) == 1
        with closing(sqlite3.connect(store.db_path)) as conn:
            with pytest.raises(sqlite3.DatabaseError):
                conn.execute(f"UPDATE {V1_AUTH} SET credential_ref = 'x'")

    def test_delete_from_frozen_v1_auth_aborts(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        assert _count(store.db_path, V1_AUTH) == 1
        with closing(sqlite3.connect(store.db_path)) as conn:
            with pytest.raises(sqlite3.DatabaseError):
                conn.execute(f"DELETE FROM {V1_AUTH}")

    def test_the_row_survives_a_refused_delete(self, tmp_path: Path) -> None:
        """Aborting is not enough if the row goes anyway."""
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        with closing(sqlite3.connect(store.db_path)) as conn, contextlib.suppress(
            sqlite3.DatabaseError
        ):
            conn.execute(f"DELETE FROM {V1_AUTH}")
            conn.commit()
        assert _count(store.db_path, V1_AUTH) == 1

    def test_dropping_a_trigger_is_detected(self, tmp_path: Path) -> None:
        """The property v5's fingerprint could not see: a DROP TRIGGER left
        the schema hash identical."""
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        with closing(sqlite3.connect(store.db_path)) as conn:
            conn.execute("DROP TRIGGER s7_v1_frozen_insert")
            conn.commit()
        with _refuses():
            _migrate(tmp_path)


class TestCrossVersionCollisionsRefuse:
    """A v2 row may not reuse a v1 nonce or artifact_id.

    Both cases INSERT a complete row copied from a seeded v1 record, so the
    trigger is what refuses -- an incomplete INSERT could abort on NOT NULL
    and prove nothing, and an `INSERT ... SELECT` from an empty table
    inserts no row at all.
    """

    def _v2_row_from_legacy(self, store, *, reuse: str):
        row = _legacy_row(store.db_path)
        row["artifact_id"] = row["artifact_id"] if reuse == "artifact_id" else "fresh"
        row["nonce"] = row["nonce"] if reuse == "nonce" else "f" * 64
        return row

    @pytest.mark.parametrize("reuse", ["nonce", "artifact_id"])
    def test_reusing_a_v1_identifier_refuses(
        self, tmp_path: Path, reuse: str
    ) -> None:
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        row = self._v2_row_from_legacy(store, reuse=reuse)
        columns = ", ".join(row)
        marks = ", ".join("?" for _ in row)
        with closing(sqlite3.connect(store.db_path)) as conn:
            with pytest.raises(sqlite3.DatabaseError):
                conn.execute(
                    f"INSERT INTO {V2_AUTH} ({columns}) VALUES ({marks})",
                    tuple(row.values()),
                )

    def test_a_fully_fresh_v2_row_is_accepted(self, tmp_path: Path) -> None:
        """CONTROL. Without it, both refusals above could come from a
        malformed INSERT rather than from the exclusion triggers."""
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        row = _legacy_row(store.db_path)
        row["artifact_id"] = "fresh"
        row["nonce"] = "f" * 64
        columns = ", ".join(row)
        marks = ", ".join("?" for _ in row)
        with closing(sqlite3.connect(store.db_path)) as conn:
            conn.execute(
                f"INSERT INTO {V2_AUTH} ({columns}) VALUES ({marks})",
                tuple(row.values()),
            )
            conn.commit()
        assert _count(store.db_path, V2_AUTH) == 1


class TestJournalAndDurabilityPosture:
    def test_the_journal_mode_is_delete_not_wal(self, tmp_path: Path) -> None:
        """Header bytes 18/19 prove NOT-WAL only; delete, truncate and
        persist all read (1,1). Only the pragma distinguishes them."""
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        with closing(sqlite3.connect(store.db_path)) as conn:
            assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "delete"

    def test_a_wal_store_refuses_to_migrate(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        with closing(sqlite3.connect(store.db_path)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
        with _refuses():
            _migrate(tmp_path)


class TestLockAndDurabilityOrdering:
    """Steps 1, 14, 15 and 16 -- the ORDER, not merely the outcome."""

    def test_the_lock_is_taken_before_anything_else(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """v13 classified before BEGIN IMMEDIATE, restoring the TOCTOU the
        source-verification move had just removed."""
        _store(tmp_path)
        _seed_legacy_row(tmp_path)
        events = _record(monkeypatch)
        _migrate(tmp_path)
        statements = _kinds(events, "sql")
        begins = [i for i, s in enumerate(statements) if "BEGIN IMMEDIATE" in s.upper()]
        assert begins, "no BEGIN IMMEDIATE; the migration ran unlocked"
        assert begins[0] == 0, statements[: begins[0] + 1]

    def test_the_commit_precedes_every_fsync(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Steps 14 then 15: the lock is RELEASED before the fsync, which is
        why the receipt rather than the commit is the linearization point."""
        _store(tmp_path)
        _seed_legacy_row(tmp_path)
        events = _record(monkeypatch)
        _migrate(tmp_path)
        commit = _first_index(events, lambda e: e[0] == "commit")
        fsync = _first_index(events, lambda e: e[0] == "fsync")
        assert commit != -1 and fsync != -1, events
        assert commit < fsync, events

    def test_both_the_database_and_its_parent_are_fsynced(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Step 15 names BOTH. A file fsync without the parent leaves the
        directory entry unsynced."""
        _store(tmp_path)
        _seed_legacy_row(tmp_path)
        events = _record(monkeypatch)
        _migrate(tmp_path)
        assert len(_kinds(events, "fsync")) >= 2, events

    def test_the_receipt_is_published_after_the_fsyncs(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Step 16 is THE linearization point and must come last."""
        _store(tmp_path)
        _seed_legacy_row(tmp_path)
        events = _record(monkeypatch)
        _migrate(tmp_path)
        link = _first_index(events, lambda e: e[0] == "link")
        fsync = _first_index(events, lambda e: e[0] == "fsync")
        assert link != -1, "the receipt was not published by an anchored link"
        assert fsync < link, events

    def test_the_receipt_is_published_by_link_not_rename(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Anchored I/O: O_TMPFILE -> write -> fsync -> exclusive link ->
        parent fsync. rename() would silently clobber an existing receipt."""
        _store(tmp_path)
        _seed_legacy_row(tmp_path)
        renames: list[str] = []
        real_rename = os.rename
        monkeypatch.setattr(
            os,
            "rename",
            lambda a, b, **k: (renames.append(str(b)), real_rename(a, b, **k))[1],
        )
        events = _record(monkeypatch)
        _migrate(tmp_path)
        assert _kinds(events, "link"), "no link; publication was not anchored"
        assert not [r for r in renames if RECEIPT_NAME in r], renames

    def test_a_competing_writer_cannot_interleave(self, tmp_path: Path) -> None:
        """A second writer holding the lock must block the migration, not
        let it proceed alongside."""
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        with closing(sqlite3.connect(store.db_path, timeout=0.1)) as other:
            other.execute("BEGIN IMMEDIATE")
            with _refuses():
                _migrate(tmp_path)


class TestAtomicity:
    def test_it_is_idempotent(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        snapshot = _tables(store.db_path), _triggers(store.db_path, V1_AUTH)
        _migrate(tmp_path)
        assert (_tables(store.db_path), _triggers(store.db_path, V1_AUTH)) == snapshot

    def test_a_fault_mid_migration_rolls_back_whole(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """No half-migrated store: either every object exists or none does.

        The fault is injected through a Connection SUBCLASS -- assigning to
        sqlite3.Connection.execute is impossible, so the previous injector
        never reached the fault it claimed to inject.
        """
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        before = _tables(store.db_path)
        _record(monkeypatch, fail_on_create=2)
        with _refuses():
            _migrate(tmp_path)
        monkeypatch.undo()
        assert _tables(store.db_path) == before
        assert _triggers(store.db_path, V1_AUTH) == ()

    def test_the_injector_actually_fires(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """CONTROL for the test above: prove the subclass route reaches
        CREATE TABLE at all, so a rollback assertion cannot pass because
        nothing was ever injected."""
        _store(tmp_path)
        events = _record(monkeypatch, fail_on_create=1)
        with pytest.raises(sqlite3.DatabaseError, match="injected"):
            with closing(sqlite3.connect(tmp_path / "probe.sqlite3")) as conn:
                conn.execute("CREATE TABLE probe (a TEXT)")
        assert any("CREATE TABLE" in s.upper() for s in _kinds(events, "sql"))


class TestClassificationMatrix:
    """The five observed states. Two migrate; two refuse and are never
    repaired; one returns without republishing."""

    def test_a_fresh_store_classifies_as_not_started_and_migrates(
        self, tmp_path: Path
    ) -> None:
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        assert V2_AUTH in _tables(store.db_path)
        assert _receipt(tmp_path)["activation_path"] == "fresh_migration"

    def test_a_complete_store_republishes_nothing(self, tmp_path: Path) -> None:
        _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        first = _receipt(tmp_path)
        _migrate(tmp_path)
        assert _receipt(tmp_path) == first

    def test_an_indeterminate_store_refuses_and_never_repairs(
        self, tmp_path: Path
    ) -> None:
        """Neither source nor target fingerprints match: ROLLBACK, refuse.
        Repairing here would launder an unknown store into an authorized
        one."""
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        with closing(sqlite3.connect(store.db_path)) as conn:
            conn.execute(f"ALTER TABLE {V1_AUTH} ADD COLUMN stray TEXT")
            conn.commit()
        before = _tables(store.db_path)
        with _refuses():
            _migrate(tmp_path)
        assert _tables(store.db_path) == before

    def test_target_matching_but_non_empty_v2_refuses(self, tmp_path: Path) -> None:
        """A populated v2 with no receipt is indeterminate, not resumable."""
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        row = _legacy_row(store.db_path)
        row["artifact_id"] = "fresh"
        row["nonce"] = "f" * 64
        columns = ", ".join(row)
        marks = ", ".join("?" for _ in row)
        with closing(sqlite3.connect(store.db_path)) as conn:
            conn.execute(
                f"INSERT INTO {V2_AUTH} ({columns}) VALUES ({marks})",
                tuple(row.values()),
            )
            conn.commit()
        _drop_receipt(tmp_path)
        with _refuses():
            _migrate(tmp_path)

    def test_committed_not_published_recovers_and_discloses_itself(
        self, tmp_path: Path
    ) -> None:
        """Interrupted between COMMIT and publication. The rerun must
        classify, publish and activate -- and the receipt must SAY it is a
        recovery, because the original started_at is unknowable and
        stamping the retry would make an interrupted migration look
        uninterrupted."""
        _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        _drop_receipt(tmp_path)
        _migrate(tmp_path)
        assert _receipt(tmp_path)["activation_path"] == "committed_recovery"

    def test_recovery_does_not_stamp_the_original_start(
        self, tmp_path: Path
    ) -> None:
        """started_at and completed_at belong to the attempt that PUBLISHED
        the receipt, so a recovery must not present the original timing."""
        _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        original = _receipt(tmp_path)
        _drop_receipt(tmp_path)
        _migrate(tmp_path)
        recovered = _receipt(tmp_path)
        assert recovered["activation_path"] == "committed_recovery"
        assert recovered["started_at"] != original["started_at"]


class TestReceiptIdentity:
    def test_the_receipt_declares_its_schema(self, tmp_path: Path) -> None:
        _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        assert _receipt(tmp_path)["schema_version"] == RECEIPT_SCHEMA

    def test_the_receipt_binds_both_tables(self, tmp_path: Path) -> None:
        """One fingerprint cannot speak for two planes."""
        _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        receipt = _receipt(tmp_path)
        assert receipt["to_fingerprint_auth"]
        assert receipt["to_fingerprint_bundle"]
        assert receipt["to_fingerprint_auth"] != receipt["to_fingerprint_bundle"]

    def test_the_receipt_binds_the_migration_time_zero_counts(
        self, tmp_path: Path
    ) -> None:
        """Zero counts bind into the receipt; a later non-zero LIVE count
        must stay admissible, or S7 deactivates on its first real artifact."""
        _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        receipt = _receipt(tmp_path)
        assert receipt["v2_auth_rows_at_migration"] == 0
        assert receipt["v2_bundle_rows_at_migration"] == 0

    def test_the_activation_path_is_a_closed_value(self, tmp_path: Path) -> None:
        _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        assert _receipt(tmp_path)["activation_path"] in {
            "fresh_migration",
            "committed_recovery",
        }


class TestFingerprintsAreVerifiedNotEmitted:
    """Generation and verification are separate programs."""

    def test_the_constants_live_in_committed_source(self) -> None:
        from core.governance import s7_schema_identity

        assert isinstance(s7_schema_identity.S7_TARGET_FINGERPRINT_AUTH, str)
        assert isinstance(s7_schema_identity.S7_TARGET_FINGERPRINT_VOICE, str)

    def test_the_migration_compares_rather_than_derives(self) -> None:
        """It must import the committed constant, never recompute the
        target from the schema under test -- which would make any schema
        its own authority."""
        import ast
        import inspect
        import textwrap

        tree = ast.parse(
            textwrap.dedent(
                inspect.getsource(s7._migrate_authorization_store_to_v2_at)
            )
        )
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        assert "S7_TARGET_FINGERPRINT_AUTH" in names

    def test_a_mutated_source_plane_refuses(self, tmp_path: Path) -> None:
        """Committed BEFORE the lock is taken, so the in-lock fingerprint
        check is what must catch it."""
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        with closing(sqlite3.connect(store.db_path)) as conn:
            conn.execute(f"CREATE INDEX stray_ix ON {V1_AUTH}(artifact_id)")
            conn.commit()
        with _refuses():
            _migrate(tmp_path)
