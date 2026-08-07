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
import stat as stat_module
from contextlib import closing
from pathlib import Path

import pytest

from core.governance import operator_user_boundary as s7


def _anchored():
    """The receipt readers live in core/governance/anchored_io.py.

    Reaching for them on operator_user_boundary made every receipt test red
    on the wrong module -- a shape this review chain has caught before.
    """
    import importlib

    try:
        return importlib.import_module("core.governance.anchored_io")
    except ImportError as exc:  # pragma: no cover
        pytest.fail(f"core/governance/anchored_io.py does not exist yet: {exc}")

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
# Ratified v1 literals, computed read-only from the live store with the
# v6/v7 recipe. The voice value is the hash of an EMPTY preimage.
V1_SOURCE_FINGERPRINT_AUTH = (
    "b8946c79c8edf9386ce73522aac8b18b6181212a949570cf9c01c01e3ac1af00"
)
V1_SOURCE_FINGERPRINT_VOICE = (
    "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"
)
# The FROZEN field set. An earlier version invented v2_auth_rows_at_migration;
# the design says row_count_v2_auth_at_migration. A receipt validator keyed on
# invented names cannot verify the receipt the migration actually writes.
RECEIPT_FIELDS = (
    "activation_path",
    "completed_at",
    "from_fingerprint_auth",
    "from_fingerprint_bundle",
    "row_count_v1_auth",
    "row_count_v1_bundle",
    "row_count_v2_auth_at_migration",
    "row_count_v2_bundle_at_migration",
    "started_at",
    "store_dev",
    "store_ino",
    "to_fingerprint_auth",
    "to_fingerprint_bundle",
)

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


def _utc_now() -> str:
    """A clock reading in the receipt's own format, used as a FLOOR.

    Comparing a recovery's started_at against the original's would be
    satisfied by reusing the original stamp -- the very laundering
    activation_path exists to prevent.
    """
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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
        return json.loads(_anchored()._read_migration_receipt(store_dir_fd=fd))


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


def _v2_row(db_path, **overrides) -> dict:
    """A complete v2 row.

    The v2 DDL is the twenty v1 columns verbatim PLUS `action NOT NULL`
    and `schema_version NOT NULL`. Copying only the v1 columns produces a
    row correct DDL must REJECT -- so the collision tests would have
    refused on a missing NOT NULL rather than on the exclusion triggers,
    and the "fresh row is accepted" control could never pass.
    """
    row = _legacy_row(db_path)
    row["action"] = "model_routing.cutover_cuda"
    row["schema_version"] = "s7.authorization_artifact.v2"
    row.update(overrides)
    return row


def _insert(conn, table: str, row: dict):
    columns = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    return conn.execute(
        f"INSERT INTO {table} ({columns}) VALUES ({marks})", tuple(row.values())
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


def _trigger_sql(tmp: Path, name: str) -> str:
    store_path = tmp / "ceremony.sqlite3"
    with closing(sqlite3.connect(store_path)) as conn:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?",
            (name,),
        ).fetchone()
    assert row is not None, f"{name} does not exist"
    return row[0]


def _fingerprint(db_path, table_names) -> str:
    """The FROZEN recipe: normalized sqlite_master.sql over tables, indexes
    and triggers, explicitly sorted -- not raw row order.

    Recomputed here independently. Comparing the receipt's own value to a
    constant proves only that the migration copied a constant into the
    receipt; it never checks the SCHEMA the migration actually built.
    """
    import hashlib
    import re

    def canon(sql):
        return None if sql is None else re.sub(r"\s+", " ", sql).strip().rstrip(";")

    rows = []
    with closing(sqlite3.connect(db_path)) as conn:
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


def _count(db_path, table: str) -> int:
    with closing(sqlite3.connect(db_path)) as conn:
        return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def _record(monkeypatch, *, fail_on_create=None, on_begin=None, on_link=None):
    """An ordered event log of SQL, commits, fsyncs, opens and links.

    fds are resolved to (path, flags) so an fsync can be NAMED. Counting
    two arbitrary fsyncs as "the database and its parent" would pass on the
    receipt writer syncing its own temp file twice, and the pre-link
    ordering check would be satisfied by the receipt's own fsync rather
    than the database's.

    sqlite3.Connection.execute is READ-ONLY, so an earlier injector that
    assigned to it never reached the fault it claimed to inject. A
    Connection SUBCLASS passed via `factory=` is the working route.
    """
    events: list[tuple[str, str]] = []
    fds: dict[int, tuple[str, int]] = {}
    real_connect = sqlite3.connect
    state = {"creates": 0, "injected": False}

    class Boom(sqlite3.DatabaseError):
        pass

    class Recording(sqlite3.Connection):
        def execute(self, sql, *a, **k):
            text = " ".join(str(sql).split())
            events.append(("sql", text[:70]))
            if "BEGIN IMMEDIATE" in text.upper() and on_begin is not None:
                result = super().execute(sql, *a, **k)
                on_begin()
                return result
            if fail_on_create is not None and "CREATE TABLE" in text.upper():
                state["creates"] += 1
                if state["creates"] == fail_on_create:
                    state["injected"] = True
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

    real_open = os.open

    def opener(path, flags, *a, **k):
        fd = real_open(path, flags, *a, **k)
        fds[fd] = (str(path), flags)
        return fd

    monkeypatch.setattr(os, "open", opener)

    real_fsync = os.fsync

    def fsync(fd):
        # Identify the HELD DESCRIPTOR, not the string the caller passed in.
        # A path string can be relative, absolute, or a symlink; the inode
        # is what actually got synced.
        path, flags = fds.get(fd, ("<unknown>", 0))
        try:
            st = os.fstat(fd)
            ident = f"{st.st_dev}:{st.st_ino}"
            isdir = stat_module.S_ISDIR(st.st_mode)
        except OSError:  # pragma: no cover
            ident, isdir = "?", False
        kind = "tmpfile" if flags & getattr(os, "O_TMPFILE", 0) else (
            "dir" if isdir else "file"
        )
        events.append(("fsync", f"{kind}:{ident}:{path}"))
        return real_fsync(fd)

    monkeypatch.setattr(os, "fsync", fsync)

    real_link = os.link

    def link(src, dst, **kw):
        events.append(("link", str(dst)))
        if on_link is not None:
            on_link(dst)
        return real_link(src, dst, **kw)

    monkeypatch.setattr(os, "link", link)
    return events, state


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

    def test_the_private_reader_has_one_production_callsite(self) -> None:
        """Allowlist of exactly one: read_migration_receipt. Any other
        production caller can aim the private reader at a chosen root.

        Scanned in anchored_io, which OWNS both readers. Scanning
        operator_user_boundary found nothing and passed vacuously; the
        reader's signature is pinned in tests/test_s7_anchored_io.py.
        """
        import ast

        module = _anchored()

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

    def test_opening_a_migrated_store_changes_no_byte(
        self, tmp_path: Path
    ) -> None:
        """Table and trigger NAMES are the weakest possible observation: an
        ALTER, an inserted row, or a stray COMMIT leaves every name intact.
        The whole file is hashed instead."""
        import hashlib

        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        before = hashlib.sha256(Path(store.db_path).read_bytes()).hexdigest()
        _store(tmp_path)
        assert (
            hashlib.sha256(Path(store.db_path).read_bytes()).hexdigest() == before
        )

    def test_opening_a_store_issues_no_write(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Fail-closed even if a future change makes an open idempotent-
        looking: no DDL, no INSERT/UPDATE/DELETE and no COMMIT may run."""
        _store(tmp_path)
        _seed_legacy_row(tmp_path)
        events, _state = _record(monkeypatch)
        _store(tmp_path)
        # executescript is recorded under its own kind; checking only "sql"
        # let the store's CREATE TABLE pass unnoticed.
        statements = _kinds(events, "sql") + _kinds(events, "script")
        written = [
            x
            for x in statements
            if any(
                verb in x.upper()
                for verb in ("CREATE ", "ALTER ", "INSERT ", "UPDATE ", "DELETE ", "DROP ")
            )
        ]
        assert not written, written
        assert not _kinds(events, "commit"), events


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

    Every INSERT is a COMPLETE v2 row -- twenty v1 columns plus action and
    schema_version -- copied from a seeded v1 record, so the exclusion
    trigger is what refuses. An incomplete row aborts on NOT NULL and
    proves nothing, and `INSERT ... SELECT` from an empty table inserts
    nothing at all.
    """

    @pytest.mark.parametrize("reuse", ["nonce", "artifact_id"])
    def test_reusing_a_v1_identifier_refuses(
        self, tmp_path: Path, reuse: str
    ) -> None:
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        fresh = {"artifact_id": "fresh-1", "nonce": "f" * 64}
        del fresh[reuse]  # keep the v1 value for the field under test
        row = _v2_row(store.db_path, **fresh)
        with closing(sqlite3.connect(store.db_path)) as conn:
            with pytest.raises(sqlite3.DatabaseError):
                _insert(conn, V2_AUTH, row)

    def test_a_fully_fresh_v2_row_is_accepted(self, tmp_path: Path) -> None:
        """CONTROL. Without it, both refusals above could come from a
        malformed INSERT rather than from the exclusion triggers."""
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        row = _v2_row(store.db_path, artifact_id="fresh-1", nonce="f" * 64)
        with closing(sqlite3.connect(store.db_path)) as conn:
            _insert(conn, V2_AUTH, row)
            conn.commit()
        assert _count(store.db_path, V2_AUTH) == 1

    def test_the_v2_table_requires_an_action(self, tmp_path: Path) -> None:
        """The column that carries the whole slice must be NOT NULL."""
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        row = _v2_row(store.db_path, artifact_id="fresh-2", nonce="e" * 64)
        del row["action"]
        with closing(sqlite3.connect(store.db_path)) as conn:
            with pytest.raises(sqlite3.DatabaseError):
                _insert(conn, V2_AUTH, row)


class TestJournalAndDurabilityPosture:
    def test_the_journal_mode_is_delete_not_wal(self, tmp_path: Path) -> None:
        """Header bytes 18/19 prove NOT-WAL only; delete, truncate and
        persist all read (1,1). Only the pragma distinguishes them."""
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        with closing(sqlite3.connect(store.db_path)) as conn:
            assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "delete"

    def test_synchronous_is_full(self, tmp_path: Path) -> None:
        """Step 2 verifies BOTH pragmas; a fsync-ordering proof means little
        if SQLite is not flushing at transaction boundaries."""
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        with closing(sqlite3.connect(store.db_path)) as conn:
            assert conn.execute("PRAGMA synchronous").fetchone()[0] == 2

    def test_a_non_full_synchronous_refuses(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Querying the pragma is not verifying it.

        synchronous is connection-local, so it cannot be staged from
        outside; the value the migration SEES is injected instead, and a
        NORMAL store must refuse rather than proceed.
        """
        _store(tmp_path)
        _seed_legacy_row(tmp_path)
        real_connect = sqlite3.connect

        class Lying(sqlite3.Connection):
            def execute(self, sql, *a, **k):
                cursor = super().execute(sql, *a, **k)
                if "PRAGMA SYNCHRONOUS" in " ".join(str(sql).split()).upper():
                    class _Normal:
                        def fetchone(self_inner):
                            return (1,)  # NORMAL

                        def fetchall(self_inner):
                            return [(1,)]

                    return _Normal()
                return cursor

        monkeypatch.setattr(
            sqlite3,
            "connect",
            lambda *a, **k: real_connect(*a, **{**k, "factory": Lying}),
        )
        with _refuses():
            _migrate(tmp_path)

    def test_the_migration_verifies_synchronous_on_its_own_connection(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """NOT a refusal test. PRAGMA synchronous is CONNECTION-LOCAL, so
        setting NORMAL on a connection and closing it leaves the store at
        FULL when migration reopens -- correct code could never refuse and
        the test would be unimplementable. What IS checkable is that the
        migration verifies the pragma on the connection it actually uses.
        """
        _store(tmp_path)
        _seed_legacy_row(tmp_path)
        events, _state = _record(monkeypatch)
        _migrate(tmp_path)
        assert any(
            "PRAGMA SYNCHRONOUS" in x.upper() for x in _kinds(events, "sql")
        ), _kinds(events, "sql")

    def test_a_wal_store_refuses_to_migrate(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        with closing(sqlite3.connect(store.db_path)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
        with _refuses():
            _migrate(tmp_path)


def _fsync_targets(events) -> list[str]:
    return [payload for kind, payload in events if kind == "fsync"]


class TestLockAndDurabilityOrdering:
    """Steps 1, 14, 15 and 16 -- the ORDER, not merely the outcome."""

    def test_the_lock_is_taken_before_anything_else(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """v13 classified before BEGIN IMMEDIATE, restoring the TOCTOU the
        source-verification move had just removed."""
        _store(tmp_path)
        _seed_legacy_row(tmp_path)
        events, _state = _record(monkeypatch)
        _migrate(tmp_path)
        statements = _kinds(events, "sql")
        begins = [i for i, x in enumerate(statements) if "BEGIN IMMEDIATE" in x.upper()]
        assert begins, "no BEGIN IMMEDIATE; the migration ran unlocked"
        assert begins[0] == 0, statements[: begins[0] + 1]

    def test_the_commit_precedes_every_fsync(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Steps 14 then 15: the lock is RELEASED before the fsync, which is
        why the receipt rather than the commit is the linearization point."""
        _store(tmp_path)
        _seed_legacy_row(tmp_path)
        events, _state = _record(monkeypatch)
        _migrate(tmp_path)
        commit = _first_index(events, lambda e: e[0] == "commit")
        fsync = _first_index(events, lambda e: e[0] == "fsync")
        assert commit != -1 and fsync != -1, events
        assert commit < fsync, events

    def test_the_database_and_its_parent_are_each_fsynced(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Named, not counted: two arbitrary fsyncs -- the receipt writer
        syncing its own temp file twice, say -- would satisfy a bare count
        while the database was never durable."""
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        events, _state = _record(monkeypatch)
        _migrate(tmp_path)
        targets = _fsync_targets(events)
        db = os.stat(store.db_path)
        parent = os.stat(tmp_path)
        assert any(f"{db.st_dev}:{db.st_ino}" in t for t in targets), targets
        assert any(
            f"{parent.st_dev}:{parent.st_ino}" in t for t in targets
        ), targets

    def test_the_database_fsync_precedes_the_receipt_link(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """The receipt's OWN fsync must not be what satisfies this: the
        database has to be durable before the linearization point."""
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        events, _state = _record(monkeypatch)
        _migrate(tmp_path)
        db = os.stat(store.db_path)
        db_fsync = _first_index(
            events,
            lambda e: e[0] == "fsync" and f"{db.st_dev}:{db.st_ino}" in e[1],
        )
        link = _first_index(events, lambda e: e[0] == "link")
        assert db_fsync != -1, "the database itself was never fsynced"
        assert link != -1, "the receipt was not published by an anchored link"
        assert db_fsync < link, events

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
        events, _state = _record(monkeypatch)
        _migrate(tmp_path)
        assert _kinds(events, "link"), "no link; publication was not anchored"
        assert not [r for r in renames if RECEIPT_NAME in r], renames

    def test_the_receipt_is_written_through_an_unnamed_temp_file(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """O_TMPFILE: a named temp file is visible to another reader before
        it is complete."""
        _store(tmp_path)
        _seed_legacy_row(tmp_path)
        events, _state = _record(monkeypatch)
        _migrate(tmp_path)
        assert any(t.startswith("tmpfile:") for t in _fsync_targets(events)), (
            _fsync_targets(events)
        )

    def test_a_competing_writer_cannot_interleave_once_the_lock_is_held(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Taken AFTER the migration's own BEGIN IMMEDIATE.

        Acquiring the lock BEFORE the migration starts tests the opposite
        property -- that migration refuses a busy store -- and says nothing
        about exclusion once migration is underway.
        """
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        outcome: dict[str, object] = {}

        def attempt_competing_write():
            with closing(sqlite3.connect(store.db_path, timeout=0.1)) as other:
                try:
                    other.execute("BEGIN IMMEDIATE")
                    outcome["blocked"] = False
                except sqlite3.OperationalError as exc:
                    outcome["blocked"] = True
                    outcome["error"] = str(exc)

        _events, _state = _record(monkeypatch, on_begin=attempt_competing_write)
        with contextlib.suppress(Exception):
            _migrate(tmp_path)
        assert outcome.get("blocked") is True, outcome

    def test_a_busy_store_refuses_rather_than_proceeding(
        self, tmp_path: Path
    ) -> None:
        """The other direction: a lock already held must refuse."""
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        with closing(sqlite3.connect(store.db_path, timeout=0.1)) as other:
            other.execute("BEGIN IMMEDIATE")
            with _refuses():
                _migrate(tmp_path)

    def test_recovery_also_releases_the_lock_before_publishing(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """v13's committed-not-published branch resumed at step 15, SKIPPING
        step 14's COMMIT -- so recovery held the write lock across the fsync
        and the publication."""
        _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        _drop_receipt(tmp_path)
        lock_free: dict[str, bool] = {}

        def probe_the_lock(_dst):
            with closing(sqlite3.connect(store_path, timeout=0.1)) as other:
                try:
                    other.execute("BEGIN IMMEDIATE")
                    other.rollback()
                    lock_free["at_publication"] = True
                except sqlite3.OperationalError:
                    lock_free["at_publication"] = False

        store_path = tmp_path / "ceremony.sqlite3"
        events, _state = _record(monkeypatch, on_link=probe_the_lock)
        _migrate(tmp_path)
        commit = _first_index(events, lambda e: e[0] == "commit")
        link = _first_index(events, lambda e: e[0] == "link")
        assert commit != -1, "recovery never committed; it held the lock"
        assert link != -1, "recovery never published"
        assert commit < link, events
        assert lock_free.get("at_publication") is True, (
            "another connection could NOT take the write lock before "
            "publication, so recovery still held it across the fsync -- "
            "commit < link alone does not prove release"
        )


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
        _events, state = _record(monkeypatch, fail_on_create=2)
        with _refuses():
            _migrate(tmp_path)
        assert state["injected"], (
            "the migration never reached a second CREATE TABLE, so the "
            "refusal above came from something else and the rollback "
            "assertion below would prove nothing"
        )
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
        events, _state = _record(monkeypatch, fail_on_create=1)
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
        row = _v2_row(store.db_path, artifact_id="fresh-1", nonce="f" * 64)
        with closing(sqlite3.connect(store.db_path)) as conn:
            _insert(conn, V2_AUTH, row)
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
        floor = _utc_now()
        assert floor >= original["started_at"]
        _drop_receipt(tmp_path)
        _migrate(tmp_path)
        recovered = _receipt(tmp_path)
        assert recovered["activation_path"] == "committed_recovery"
        # `>= original` would be satisfied by REUSING the original stamp,
        # which is exactly the laundering the field exists to prevent. The
        # floor is a clock reading taken AFTER the original was published,
        # so only a genuinely new attempt can clear it.
        assert recovered["started_at"] >= floor, (recovered["started_at"], floor)
        assert recovered["completed_at"] >= recovered["started_at"]


class TestReceiptIdentity:
    """The frozen 13-field set, by its ratified names."""

    def test_the_field_set_is_exactly_the_frozen_thirteen(
        self, tmp_path: Path
    ) -> None:
        _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        assert tuple(sorted(_receipt(tmp_path))) == RECEIPT_FIELDS

    def test_both_source_fingerprints_are_bound(self, tmp_path: Path) -> None:
        _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        receipt = _receipt(tmp_path)
        assert receipt["from_fingerprint_auth"]
        assert receipt["from_fingerprint_bundle"]
        assert receipt["from_fingerprint_auth"] != receipt["to_fingerprint_auth"]

    def test_both_target_fingerprints_are_bound_and_distinct(
        self, tmp_path: Path
    ) -> None:
        """One fingerprint cannot speak for two planes."""
        _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        receipt = _receipt(tmp_path)
        assert receipt["to_fingerprint_auth"] != receipt["to_fingerprint_bundle"]

    def test_the_v1_counts_are_bound(self, tmp_path: Path) -> None:
        """Seeded with exactly one auth row, so a hardcoded 0 fails."""
        _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        receipt = _receipt(tmp_path)
        assert receipt["row_count_v1_auth"] == 1
        assert receipt["row_count_v1_bundle"] == 0

    def test_the_migration_time_v2_counts_are_bound_as_zero(
        self, tmp_path: Path
    ) -> None:
        """Zero is a migration-time FACT, not a standing invariant -- a
        later non-zero live count must stay admissible, or S7 deactivates
        on its first real artifact."""
        _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        receipt = _receipt(tmp_path)
        assert receipt["row_count_v2_auth_at_migration"] == 0
        assert receipt["row_count_v2_bundle_at_migration"] == 0

    def test_a_live_v2_row_after_activation_stays_admissible(
        self, tmp_path: Path
    ) -> None:
        """The rule that would otherwise deactivate S7 on first use."""
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        row = _v2_row(store.db_path, artifact_id="live-1", nonce="d" * 64)
        with closing(sqlite3.connect(store.db_path)) as conn:
            _insert(conn, V2_AUTH, row)
            conn.commit()
        _migrate(tmp_path)
        assert _receipt(tmp_path)["row_count_v2_auth_at_migration"] == 0

    def test_the_store_identity_is_bound(self, tmp_path: Path) -> None:
        """dev/ino pin the receipt to THIS store, so a receipt cannot be
        carried to a foreign one."""
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        receipt = _receipt(tmp_path)
        stat = os.stat(store.db_path)
        assert receipt["store_dev"] == stat.st_dev
        assert receipt["store_ino"] == stat.st_ino

    def test_the_activation_path_is_a_closed_value(self, tmp_path: Path) -> None:
        _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        assert _receipt(tmp_path)["activation_path"] in {
            "fresh_migration",
            "committed_recovery",
        }

    def test_the_receipt_bytes_are_canonical(self, tmp_path: Path) -> None:
        """Canonically wrapped by the project encoder: re-encoding the
        parsed document must reproduce the bytes exactly, or two readers
        can disagree about what was signed."""
        _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        with _dir_fd(tmp_path) as fd:
            raw = _anchored()._read_migration_receipt(store_dir_fd=fd)
        assert isinstance(raw, bytes)
        reencoded = json.dumps(
            json.loads(raw), sort_keys=True, separators=(",", ":")
        ).encode()
        assert raw == reencoded, "receipt bytes are not canonical"

    def test_no_row_contents_appear_in_the_receipt(self, tmp_path: Path) -> None:
        """Content-light: the receipt binds counts and fingerprints, never
        the records themselves."""
        _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        with _dir_fd(tmp_path) as fd:
            raw = _anchored()._read_migration_receipt(store_dir_fd=fd)
        assert b"legacy-1" not in raw
        assert b"cred-1" not in raw


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


class TestTriggerBodiesNotJustNames:
    """A trigger checked by name is a label. These check what it DOES."""

    def test_the_voice_freeze_triggers_abort_on_insert(
        self, tmp_path: Path
    ) -> None:
        """The only voice case testable by behaviour: the table is created
        empty and frozen, so it can never hold a row for UPDATE or DELETE
        to touch. Those two are pinned by body below rather than pretended
        to be exercised."""
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        with closing(sqlite3.connect(store.db_path)) as conn:
            columns = [r[1] for r in conn.execute(f"PRAGMA table_info({V1_VOICE})")]
            assert columns, "voice table has no columns"
            row = {name: "x" for name in columns}
            with pytest.raises(sqlite3.DatabaseError):
                _insert(conn, V1_VOICE, row)

    @pytest.mark.parametrize("name", V1_VOICE_FREEZE + V1_AUTH_FREEZE)
    def test_no_freeze_trigger_is_conditional(
        self, tmp_path: Path, name: str
    ) -> None:
        """`RAISE` and `ABORT` both appear in a trigger that never fires:
        `... WHEN 0 BEGIN SELECT RAISE(ABORT, ...); END` passes a
        keyword check and stops nothing. The frozen bodies are
        unconditional, so a WHEN clause is by construction wrong."""
        _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        sql = _trigger_sql(tmp_path, name)
        head = sql.upper().split("BEGIN", 1)[0]
        assert " WHEN " not in head, sql

    @pytest.mark.parametrize("name", V1_VOICE_FREEZE + V1_AUTH_FREEZE)
    def test_every_freeze_trigger_body_raises_abort(
        self, tmp_path: Path, name: str
    ) -> None:
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        with closing(sqlite3.connect(store.db_path)) as conn:
            sql = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?",
                (name,),
            ).fetchone()
        assert sql is not None, f"{name} does not exist"
        assert "RAISE" in sql[0].upper() and "ABORT" in sql[0].upper(), sql[0]

    @pytest.mark.parametrize("name", V2_AUTH_EXCLUSION + V2_VOICE_EXCLUSION)
    def test_every_exclusion_trigger_consults_the_v1_table(
        self, tmp_path: Path, name: str
    ) -> None:
        """These ARE conditional by design -- they fire only on collision --
        so the check is that the condition reads v1. `WHEN 0` references no
        table and can never fire. The behavioural proof that they abort is
        TestCrossVersionCollisionsRefuse."""
        _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        sql = _trigger_sql(tmp_path, name).lower()
        assert V1_AUTH in sql or V1_VOICE in sql, sql

    @pytest.mark.parametrize("name", V2_AUTH_EXCLUSION + V2_VOICE_EXCLUSION)
    def test_every_exclusion_trigger_body_raises_abort(
        self, tmp_path: Path, name: str
    ) -> None:
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        with closing(sqlite3.connect(store.db_path)) as conn:
            sql = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?",
                (name,),
            ).fetchone()
        assert sql is not None, f"{name} does not exist"
        assert "RAISE" in sql[0].upper() and "ABORT" in sql[0].upper(), sql[0]


class TestSchemasMatchTheFrozenDDL:
    """The design publishes the v2 DDL as a literal, 'no placeholder'."""

    def test_the_v2_auth_columns_are_the_frozen_twenty_two(
        self, tmp_path: Path
    ) -> None:
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        with closing(sqlite3.connect(store.db_path)) as conn:
            columns = [r[1] for r in conn.execute(f"PRAGMA table_info({V2_AUTH})")]
        assert len(columns) == 22, columns
        assert columns[-2:] == ["action", "schema_version"]

    def test_the_first_twenty_v2_columns_are_v1_verbatim(
        self, tmp_path: Path
    ) -> None:
        """'The first twenty columns are the v1 definitions verbatim, read
        from the live store's sqlite_master rather than transcribed.'"""
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        with closing(sqlite3.connect(store.db_path)) as conn:
            v1 = [
                (r[1], r[2], r[3], r[4])
                for r in conn.execute(f"PRAGMA table_info({V1_AUTH})")
            ]
            v2 = [
                (r[1], r[2], r[3], r[4])
                for r in conn.execute(f"PRAGMA table_info({V2_AUTH})")
            ]
        assert v2[:20] == v1

    def test_the_v2_nonce_index_exists(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        with closing(sqlite3.connect(store.db_path)) as conn:
            names = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' "
                    "AND tbl_name=?",
                    (V2_AUTH,),
                )
            }
        assert "s7_v2_nonce" in names, names

    def test_the_built_schema_hashes_to_the_committed_target_constants(
        self, tmp_path: Path
    ) -> None:
        """Recomputed INDEPENDENTLY from the schema the migration built.

        Comparing the receipt's own value to the constant would pass on a
        migration that copied the constant into the receipt while building
        a different schema.
        """
        from core.governance import s7_schema_identity as identity

        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        # The auth plane's identity must authenticate the WALL: v1 and its
        # freeze triggers are what stops an old daemon writing. Hashing only
        # v2 leaves the wall outside the identity that vouches for it --
        # exactly the v5 defect where DROP TRIGGER left the hash unchanged.
        assert (
            _fingerprint(store.db_path, [V1_AUTH, V2_AUTH])
            == identity.S7_TARGET_FINGERPRINT_AUTH
        )
        assert (
            _fingerprint(store.db_path, [V1_VOICE, V2_VOICE])
            == identity.S7_TARGET_FINGERPRINT_VOICE
        )

    def test_the_receipt_target_matches_the_independently_recomputed_value(
        self, tmp_path: Path
    ) -> None:
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        receipt = _receipt(tmp_path)
        assert receipt["to_fingerprint_auth"] == _fingerprint(
            store.db_path, [V1_AUTH, V2_AUTH]
        )
        assert receipt["to_fingerprint_bundle"] == _fingerprint(
            store.db_path, [V1_VOICE, V2_VOICE]
        )

    def test_the_source_fingerprints_match_the_frozen_v1_literals(
        self, tmp_path: Path
    ) -> None:
        """from_fingerprint_* were self-chosen in v5 -- the receipt asserted
        whatever it found. These are the ratified literals; the voice one is
        the hash of an EMPTY preimage, so the absent plane has a defined
        identity rather than a gap described in prose."""
        _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        receipt = _receipt(tmp_path)
        assert receipt["from_fingerprint_auth"] == V1_SOURCE_FINGERPRINT_AUTH
        assert receipt["from_fingerprint_bundle"] == V1_SOURCE_FINGERPRINT_VOICE


class TestReceiptIdentityIsBoundToThisStore:
    """Primitive mechanics -- mode, links, exclusive create, size caps,
    no-follow, short reads -- now live in tests/test_s7_anchored_io.py.
    What remains here is what only MIGRATION can decide: that a receipt
    belongs to the store it claims."""

    def test_publication_does_not_replace_an_existing_receipt(
        self, tmp_path: Path
    ) -> None:
        _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        first = (tmp_path / RECEIPT_NAME).read_bytes()
        _migrate(tmp_path)
        assert (tmp_path / RECEIPT_NAME).read_bytes() == first

    def test_a_corrupt_receipt_refuses(self, tmp_path: Path) -> None:
        _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        (tmp_path / RECEIPT_NAME).write_bytes(b"{ not json")
        os.chmod(tmp_path / RECEIPT_NAME, 0o600)
        with _refuses():
            _migrate(tmp_path)

    def test_a_receipt_from_a_foreign_store_refuses(self, tmp_path: Path) -> None:
        """dev/ino pin the receipt to its own store. The planted file is
        chmod 0600 deliberately: at the default 0644 the read refuses on
        MODE before ever reaching the identity check, and the test would
        pass for the wrong reason."""
        first = tmp_path / "a"
        second = tmp_path / "b"
        first.mkdir()
        second.mkdir()
        for directory in (first, second):
            _store(directory)
            _seed_legacy_row(directory)
        _migrate(first)
        (second / RECEIPT_NAME).write_bytes((first / RECEIPT_NAME).read_bytes())
        os.chmod(second / RECEIPT_NAME, 0o600)
        with _refuses():
            _migrate(second)


class TestPublicationLoserVerifiesTheWinner:
    """Losing the exclusive create is not an error to swallow."""

    def test_the_loser_verifies_rather_than_failing_blind(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """A competitor publishes between this run's fsync and its link.
        The loser must READ the winner's receipt and confirm it describes
        the same store, not merely give up -- and must not replace it."""
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        winner = (tmp_path / RECEIPT_NAME).read_bytes()
        _drop_receipt(tmp_path)

        def competitor_publishes(_dst):
            (tmp_path / RECEIPT_NAME).write_bytes(winner)
            os.chmod(tmp_path / RECEIPT_NAME, 0o600)

        _events, _state = _record(monkeypatch, on_link=competitor_publishes)
        _migrate(tmp_path)
        assert (tmp_path / RECEIPT_NAME).read_bytes() == winner
        assert _receipt(tmp_path)["store_ino"] == os.stat(store.db_path).st_ino


class TestPartialAndFutureSchemasRefuse:
    def test_a_partial_target_refuses(self, tmp_path: Path) -> None:
        """v2 auth present, v2 voice absent: neither source nor target, so
        indeterminate -- refuse, never complete it."""
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        with closing(sqlite3.connect(store.db_path)) as conn:
            conn.execute(f"DROP TABLE {V2_VOICE}")
            conn.commit()
        _drop_receipt(tmp_path)
        with _refuses():
            _migrate(tmp_path)

    def test_a_future_target_refuses(self, tmp_path: Path) -> None:
        """A column beyond the frozen twenty-two is a schema this migration
        does not know; completing it would launder an unknown store."""
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        with closing(sqlite3.connect(store.db_path)) as conn:
            conn.execute(f"ALTER TABLE {V2_AUTH} ADD COLUMN from_the_future TEXT")
            conn.commit()
        _drop_receipt(tmp_path)
        with _refuses():
            _migrate(tmp_path)

    def test_a_non_empty_v2_voice_plane_refuses(self, tmp_path: Path) -> None:
        """The auth plane's non-empty case was covered; the voice plane's
        was not, and 'both v2 tables hold 0 rows' names BOTH."""
        store = _store(tmp_path)
        _seed_legacy_row(tmp_path)
        _migrate(tmp_path)
        with closing(sqlite3.connect(store.db_path)) as conn:
            columns = [r[1] for r in conn.execute(f"PRAGMA table_info({V2_VOICE})")]
            assert columns, "voice v2 has no columns"
            conn.execute("PRAGMA ignore_check_constraints=ON")
            _insert(conn, V2_VOICE, {name: "x" for name in columns})
            conn.commit()
        _drop_receipt(tmp_path)
        with _refuses():
            _migrate(tmp_path)
