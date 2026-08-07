"""S7 v2 migration — the ratified RED matrix, written BEFORE implementation.

Without this, a skeletal table creator would satisfy every downstream link
test while violating most of the migration contract: it could migrate on
open, backfill rows, skip the freeze triggers, run outside a lock, leave
the journal in WAL, publish a receipt before fsync, or "repair" a store it
should have refused.

The design freezes an ORDERED 16-step procedure and a 5-row classification
matrix. Both are pinned here.

HONEST STATUS: `_migrate_authorization_store_to_v2_at` does not exist yet,
so at the time of writing EVERY test in this file dies at the same missing
entrypoint. That is the intended pre-implementation state, not a proof.
Each test is written so that once migration lands it fails or passes at
its OWN assertion, and the ratified order requires re-witnessing exactly
that before storage or minting is written.

Nothing here touches the live store; every test builds a private one in a
tmp_path.
"""

from __future__ import annotations

import contextlib
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


@contextlib.contextmanager
def _refuses():
    """Assert a genuine refusal -- never a missing seam.

    `pytest.raises(Exception)` around a migration call passes on the
    AttributeError raised by the absent entrypoint, so every refusal test
    in this file would report GREEN before a line of migration exists.
    That is the defect this whole review chain keeps finding, so the
    missing-seam errors are re-raised as failures instead.
    """
    assert hasattr(s7, "_migrate_authorization_store_to_v2_at"), (
        "migration entrypoint absent: a refusal cannot be distinguished "
        "from a missing seam until it exists"
    )
    try:
        yield
    except (AttributeError, NameError, ImportError) as exc:
        raise AssertionError(f"not a refusal, a missing seam: {exc!r}") from exc
    except Exception:
        return
    raise AssertionError("expected a refusal; nothing was raised")


def _store(tmp: Path):
    return s7.S7AuthorizationStore(tmp / "ceremony.sqlite3")


def _migrate(tmp: Path) -> None:
    fd = os.open(tmp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        s7._migrate_authorization_store_to_v2_at(store_dir_fd=fd)
    finally:
        os.close(fd)


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


class TestTheEntrypointShape:
    """Two entrypoints, deliberately different: production takes NO root."""

    def test_the_public_entrypoint_takes_no_arguments(self) -> None:
        """A public-looking signature accepting a root recreates the
        alternate-root capability the design removed."""
        import inspect

        params = inspect.signature(
            s7.migrate_authorization_store_to_v2
        ).parameters
        assert not params, params

    def test_the_private_helper_takes_a_directory_fd(self) -> None:
        import inspect

        params = inspect.signature(
            s7._migrate_authorization_store_to_v2_at
        ).parameters
        assert set(params) == {"store_dir_fd"}


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
        """Re-opening must read and verify, never migrate or commit."""
        store = _store(tmp_path)
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
        _migrate(tmp_path)
        assert V1_VOICE in _tables(store.db_path)
        assert _count(store.db_path, V1_VOICE) == 0

    def test_the_three_v1_voice_freeze_triggers_exist(
        self, tmp_path: Path
    ) -> None:
        """Step 6."""
        store = _store(tmp_path)
        _migrate(tmp_path)
        assert _triggers(store.db_path, V1_VOICE) == V1_VOICE_FREEZE

    def test_the_three_v1_auth_freeze_triggers_exist(self, tmp_path: Path) -> None:
        """Step 7."""
        store = _store(tmp_path)
        _migrate(tmp_path)
        assert _triggers(store.db_path, V1_AUTH) == V1_AUTH_FREEZE

    def test_both_v2_tables_are_created(self, tmp_path: Path) -> None:
        """Step 8."""
        store = _store(tmp_path)
        _migrate(tmp_path)
        assert {V2_AUTH, V2_VOICE} <= _tables(store.db_path)

    def test_the_v2_exclusion_triggers_exist(self, tmp_path: Path) -> None:
        """Step 9."""
        store = _store(tmp_path)
        _migrate(tmp_path)
        assert _triggers(store.db_path, V2_AUTH) == V2_AUTH_EXCLUSION
        assert _triggers(store.db_path, V2_VOICE) == V2_VOICE_EXCLUSION

    def test_nothing_is_backfilled(self, tmp_path: Path) -> None:
        """Steps 10 and 13. Copying v1 rows forward would manufacture v2
        authority for records that never carried an action."""
        store = _store(tmp_path)
        _migrate(tmp_path)
        assert _count(store.db_path, V2_AUTH) == 0
        assert _count(store.db_path, V2_VOICE) == 0


class TestTheFreezeTriggersActuallyAbort:
    """Named triggers that do not fire are decoration."""

    @pytest.mark.parametrize(
        "statement",
        [
            f"INSERT INTO {V1_AUTH} (artifact_id) VALUES ('x')",
            f"UPDATE {V1_AUTH} SET artifact_id = 'y'",
            f"DELETE FROM {V1_AUTH}",
        ],
    )
    def test_every_write_to_frozen_v1_auth_aborts(
        self, tmp_path: Path, statement: str
    ) -> None:
        store = _store(tmp_path)
        _migrate(tmp_path)
        with closing(sqlite3.connect(store.db_path)) as conn:
            with pytest.raises(sqlite3.DatabaseError):
                conn.execute(statement)

    @pytest.mark.parametrize(
        "statement",
        [
            f"INSERT INTO {V1_VOICE} (request_id) VALUES ('x')",
            f"UPDATE {V1_VOICE} SET request_id = 'y'",
            f"DELETE FROM {V1_VOICE}",
        ],
    )
    def test_every_write_to_frozen_v1_voice_aborts(
        self, tmp_path: Path, statement: str
    ) -> None:
        store = _store(tmp_path)
        _migrate(tmp_path)
        with closing(sqlite3.connect(store.db_path)) as conn:
            with pytest.raises(sqlite3.DatabaseError):
                conn.execute(statement)

    def test_dropping_a_trigger_is_detected(self, tmp_path: Path) -> None:
        """The property v5's fingerprint could not see: a DROP TRIGGER left
        the schema hash identical."""
        store = _store(tmp_path)
        _migrate(tmp_path)
        with closing(sqlite3.connect(store.db_path)) as conn:
            conn.execute("DROP TRIGGER s7_v1_frozen_insert")
            conn.commit()
        with _refuses():
            _migrate(tmp_path)


class TestCrossVersionCollisionsRefuse:
    """A v2 row may not reuse a v1 nonce or artifact_id."""

    def test_a_reused_v1_nonce_refuses(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        _migrate(tmp_path)
        with closing(sqlite3.connect(store.db_path)) as conn:
            with pytest.raises(sqlite3.DatabaseError):
                conn.execute(
                    f"INSERT INTO {V2_AUTH} (artifact_id, nonce) "
                    f"SELECT 'fresh', nonce FROM {V1_AUTH} LIMIT 1"
                )

    def test_a_reused_v1_artifact_id_refuses(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        _migrate(tmp_path)
        with closing(sqlite3.connect(store.db_path)) as conn:
            with pytest.raises(sqlite3.DatabaseError):
                conn.execute(
                    f"INSERT INTO {V2_AUTH} (artifact_id, nonce) "
                    f"SELECT artifact_id, 'fresh' FROM {V1_AUTH} LIMIT 1"
                )


class TestJournalAndDurabilityPosture:
    """Step 2, and step 15's ordering."""

    def test_the_journal_mode_is_delete_not_wal(self, tmp_path: Path) -> None:
        """Header bytes 18/19 prove NOT-WAL only; delete, truncate and
        persist all read (1,1). Only the pragma distinguishes them."""
        store = _store(tmp_path)
        _migrate(tmp_path)
        with closing(sqlite3.connect(store.db_path)) as conn:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "delete"

    def test_synchronous_is_full(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        _migrate(tmp_path)
        with closing(sqlite3.connect(store.db_path)) as conn:
            assert conn.execute("PRAGMA synchronous").fetchone()[0] == 2

    def test_a_wal_store_refuses_to_migrate(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        with closing(sqlite3.connect(store.db_path)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
        with _refuses():
            _migrate(tmp_path)


class TestAtomicity:
    def test_it_is_idempotent(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        _migrate(tmp_path)
        snapshot = _tables(store.db_path), _triggers(store.db_path, V1_AUTH)
        _migrate(tmp_path)
        assert (_tables(store.db_path), _triggers(store.db_path, V1_AUTH)) == snapshot

    def test_a_fault_mid_migration_rolls_back_whole(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """No half-migrated store: either every object exists or none does."""
        store = _store(tmp_path)
        before = _tables(store.db_path)

        class Boom(Exception):
            pass

        real_connect = sqlite3.connect
        state = {"n": 0}

        def flaky(*args, **kwargs):
            conn = real_connect(*args, **kwargs)
            real_execute = conn.execute

            def execute(sql, *a, **k):
                if "CREATE TABLE" in str(sql).upper():
                    state["n"] += 1
                    if state["n"] == 2:
                        raise Boom("injected mid-migration")
                return real_execute(sql, *a, **k)

            conn.execute = execute
            return conn

        monkeypatch.setattr(sqlite3, "connect", flaky)
        with _refuses():
            _migrate(tmp_path)
        monkeypatch.undo()
        assert _tables(store.db_path) == before


class TestClassificationMatrix:
    """The five observed states. Only two of them migrate; two refuse and
    are never repaired."""

    def test_a_fresh_store_classifies_as_not_started_and_migrates(
        self, tmp_path: Path
    ) -> None:
        store = _store(tmp_path)
        _migrate(tmp_path)
        assert V2_AUTH in _tables(store.db_path)
        receipt = s7.read_migration_receipt()
        assert receipt is not None
        assert receipt["activation_path"] == "fresh_migration"

    def test_a_complete_store_republishes_nothing(self, tmp_path: Path) -> None:
        _store(tmp_path)
        _migrate(tmp_path)
        first = s7.read_migration_receipt()
        _migrate(tmp_path)
        assert s7.read_migration_receipt() == first

    def test_an_indeterminate_store_refuses_and_never_repairs(
        self, tmp_path: Path
    ) -> None:
        """Neither source nor target fingerprints match: ROLLBACK, refuse.
        Repairing here would launder an unknown store into an authorized
        one."""
        store = _store(tmp_path)
        with closing(sqlite3.connect(store.db_path)) as conn:
            conn.execute(f"ALTER TABLE {V1_AUTH} ADD COLUMN stray TEXT")
            conn.commit()
        before = _tables(store.db_path)
        with _refuses():
            _migrate(tmp_path)
        assert _tables(store.db_path) == before

    def test_target_matching_but_non_empty_v2_refuses(
        self, tmp_path: Path
    ) -> None:
        """A populated v2 with no receipt is indeterminate, not resumable."""
        store = _store(tmp_path)
        _migrate(tmp_path)
        with closing(sqlite3.connect(store.db_path)) as conn:
            conn.execute(
                f"INSERT INTO {V2_AUTH} (artifact_id, nonce) VALUES ('a', 'n')"
            )
            conn.commit()
        _drop_receipt()
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
        _migrate(tmp_path)
        _drop_receipt()
        _migrate(tmp_path)
        receipt = s7.read_migration_receipt()
        assert receipt["activation_path"] == "committed_recovery"


def _drop_receipt() -> None:
    """Simulate the crash window between COMMIT and publication."""
    path = getattr(s7, "MIGRATION_RECEIPT_PATH", None)
    assert path is not None, "no receipt path to remove"
    Path(path).unlink(missing_ok=True)


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
        names = {
            node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
        }
        assert "S7_TARGET_FINGERPRINT_AUTH" in names

    def test_a_mutated_source_plane_refuses(self, tmp_path: Path) -> None:
        """Committed BEFORE the lock is taken, so the in-lock fingerprint
        check is what must catch it."""
        store = _store(tmp_path)
        with closing(sqlite3.connect(store.db_path)) as conn:
            conn.execute(f"CREATE INDEX stray_ix ON {V1_AUTH}(artifact_id)")
            conn.commit()
        with _refuses():
            _migrate(tmp_path)
