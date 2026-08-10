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

import contextlib
import hashlib
import sqlite3
from pathlib import Path

import pytest

from core.governance import operator_user_boundary as s7
from tests.s7_callsite_scanner import find_callsites


def find_initialiser_callsites(source: str) -> list[str]:
    """The ONE implementation, shared.

    This guard used to own a private copy. Two copies is how a hardened
    scanner and a bypassable one end up guarding two authorities that
    need the same strength.
    """
    return find_callsites(source, TARGET)
from tests.s7_store_fixture import bootstrap_shaped, open_only

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


TARGET = "initialise_authorization_store"
ALLOWED_CALLSITE = "scripts/s7_initialise_store.py::main"





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
        open_only(tmp_path / "ceremony.sqlite3")
        assert not _writes(events), _writes(events)

    def test_opening_issues_no_commit(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        _initialise(tmp_path)
        events = _record(monkeypatch)
        open_only(tmp_path / "ceremony.sqlite3")
        assert not [k for k, _ in events if k == "commit"], events

    def test_opening_changes_no_byte(self, tmp_path: Path) -> None:
        """The strongest available observation: names and counts survive an
        ALTER or a stray commit, bytes do not."""
        bootstrap_shaped(tmp_path)
        path = _initialise(tmp_path) or (tmp_path / "ceremony.sqlite3")
        path = tmp_path / "ceremony.sqlite3"
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        open_only(path)
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
        bootstrap_shaped(tmp_path)
        _initialise(tmp_path)
        tables = _tables(tmp_path / "ceremony.sqlite3")
        assert V2_AUTH not in tables
        assert "s7_voice_source_bundles_v2" not in tables

    def test_it_publishes_no_receipt(self, tmp_path: Path) -> None:
        _initialise(tmp_path)
        assert not (tmp_path / RECEIPT_NAME).exists()

    def test_it_installs_no_freeze_triggers(self, tmp_path: Path) -> None:
        """The wall belongs to migration; a freshly initialized store is
        writable v1.

        Run against a BOOTSTRAP-shaped database, not a pre-created empty
        file. An empty file has zero tables -- and so does a store whose
        only table was dropped -- so the two states were observationally
        identical and no implementation could satisfy both this test and
        the damaged-store refusal below.
        """
        bootstrap_shaped(tmp_path)
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

    def test_re_initialising_preserves_the_bootstrap_tables(
        self, tmp_path: Path
    ) -> None:
        """The live store is bootstrap's five tables PLUS the auth table.
        Initialization may not disturb the credentials that already live
        there."""
        bootstrap_shaped(tmp_path)
        path = tmp_path / "ceremony.sqlite3"
        before_tables = _tables(path)
        assert before_tables, "bootstrap created nothing; the check is vacuous"

        # Table NAMES survive a destructive initialization that empties
        # them. The credentials and metadata are what must be preserved,
        # so the rows themselves are captured and compared.
        def rows():
            snapshot = {}
            with sqlite3.connect(path) as conn:
                for table in sorted(before_tables):
                    snapshot[table] = conn.execute(
                        f"SELECT * FROM {table}"
                    ).fetchall()
            return snapshot

        with sqlite3.connect(path) as conn:
            conn.execute(
                "INSERT INTO s7_ceremony_metadata (key, value) VALUES (?, ?)",
                ("witness", "must-survive"),
            )
            conn.commit()
        before_rows = rows()
        assert any(before_rows.values()), "no bootstrap rows to preserve"

        _initialise(tmp_path)
        _initialise(tmp_path)
        assert before_tables <= _tables(path)
        assert rows() == before_rows

    def test_re_initialising_preserves_every_existing_row(
        self, tmp_path: Path
    ) -> None:
        """A COMPLETE artifact, written through store.put.

        Inserting two columns into the twenty-column v1 table fails on
        request_envelope_hash NOT NULL before the preservation claim is ever
        reached.
        """
        bootstrap_shaped(tmp_path)
        _initialise(tmp_path)
        path = tmp_path / "ceremony.sqlite3"
        open_only(path).put(
            s7.S7AuthorizationArtifact(
                artifact_id="kept-1",
                request_id="req-1",
                request_envelope_hash="b" * 64,
                rendered_text_hash="c" * 64,
                action_params_hash="d" * 64,
                precondition_hash="a" * 64,
                authority_context_hash="e" * 64,
                derived_work_class="self_modification",
                derived_aggregation_group="s7agg_kept",
                nonce="n" * 64,
                credential_ref="cred-1",
                auth_method="founder_webauthn",
                grant_source="founder_webauthn",
                user_presence=True,
                user_verification=True,
                created_at="2026-08-07T12:00:00Z",
                expires_at="2026-08-07T16:00:00Z",
                consumed_at=None,
                action="model_routing.cutover_cuda",
            )
        )
        _initialise(tmp_path)
        with sqlite3.connect(path) as conn:
            kept = conn.execute(f"SELECT artifact_id FROM {V1_AUTH}").fetchall()
        assert ("kept-1",) in kept, kept

    def test_an_altered_schema_refuses_rather_than_being_repaired(
        self, tmp_path: Path
    ) -> None:
        """IDEMPOTENT-VERIFY, third branch: the table is PRESENT and WRONG.

        A DROPPED table cannot be the damaged case -- it leaves exactly the
        state a never-initialized store is in, so refusing it would also
        refuse legitimate first initialization. Damage that is actually
        observable is a schema that exists and does not match.
        """
        bootstrap_shaped(tmp_path)
        _initialise(tmp_path)
        path = tmp_path / "ceremony.sqlite3"
        with sqlite3.connect(path) as conn:
            conn.execute(f"ALTER TABLE {V1_AUTH} ADD COLUMN stray TEXT")
            conn.commit()
        before = _fingerprint(path, [V1_AUTH])
        with pytest.raises((ValueError, sqlite3.DatabaseError)):
            _initialise(tmp_path)
        assert _fingerprint(path, [V1_AUTH]) == before, "it repaired instead"

    def test_a_stray_index_refuses(self, tmp_path: Path) -> None:
        """The fingerprint covers indexes and triggers, not just columns."""
        bootstrap_shaped(tmp_path)
        _initialise(tmp_path)
        path = tmp_path / "ceremony.sqlite3"
        with sqlite3.connect(path) as conn:
            conn.execute(f"CREATE INDEX stray_ix ON {V1_AUTH}(artifact_id)")
            conn.commit()
        with pytest.raises((ValueError, sqlite3.DatabaseError)):
            _initialise(tmp_path)

    def test_a_dropped_table_is_not_treated_as_damage(
        self, tmp_path: Path
    ) -> None:
        """The contradiction, pinned so it cannot return: a store whose
        auth table is gone is indistinguishable from one never initialized,
        so the INITIALIZER must create it. Refusing here would make first
        initialization impossible. The resurrection risk is closed on the
        OPEN side, which never creates.
        """
        bootstrap_shaped(tmp_path)
        _initialise(tmp_path)
        path = tmp_path / "ceremony.sqlite3"
        with sqlite3.connect(path) as conn:
            conn.execute(f"DROP TABLE {V1_AUTH}")
            conn.commit()
        _initialise(tmp_path)
        assert V1_AUTH in _tables(path)

    def test_the_initialiser_has_one_exact_qualified_callsite(self) -> None:
        """Creation authority must not be reachable from the request path.

        The callsite is FULLY QUALIFIED: `Hidden.main` and
        `helper.<locals>.main` are not `main`, so a call tucked into a
        class or a closure inside the allowed script does not satisfy this.
        """
        import os

        allowed: list[str] = []
        offenders: list[str] = []
        skip = {".git", ".venv", "node_modules", "__pycache__", "tests", "docs"}
        files = []
        for dirpath, dirnames, filenames in os.walk(REPO):
            dirnames[:] = [
                d for d in dirnames if d not in skip and not d.startswith(".")
            ]
            files += [Path(dirpath, n) for n in filenames if n.endswith(".py")]

        for path in files:
            rel = str(path.relative_to(REPO))
            try:
                source = path.read_text()
            except (OSError, UnicodeDecodeError):
                continue
            try:
                scopes = find_initialiser_callsites(source)
            except SyntaxError:
                continue
            for scope in scopes:
                site = f"{rel}::{scope}"
                (allowed if site == ALLOWED_CALLSITE else offenders).append(site)

        assert allowed, (
            "no bootstrap caller invokes the initializer; the allowlist is "
            "vacuous until one does"
        )
        assert not offenders, offenders
        assert allowed == [ALLOWED_CALLSITE], allowed

    def test_the_allowed_callsite_actually_runs(self, monkeypatch) -> None:
        """BEHAVIOURAL. The scanner proves a call APPEARS; it cannot prove
        it executes.

            def main():
                if False:
                    initialise_authorization_store()

        satisfies every syntactic check above and never initialises
        anything. This invokes main() and requires the seam to be reached
        exactly once.
        """
        import importlib.util

        script = REPO / "scripts" / "s7_initialise_store.py"
        assert script.is_file(), f"{script} does not exist yet"

        from core.governance.s7_webauthn_bootstrap import DEFAULT_STORE_ROOT

        calls: list[tuple] = []
        # Stub BEFORE exec_module. Loading the script first lets a
        # top-level `from ... import initialise_authorization_store` keep
        # the REAL callable -- and a module-level call would then touch the
        # canonical store during this test.
        monkeypatch.setattr(
            s7,
            "initialise_authorization_store",
            lambda *a, **k: calls.append((a, k)),
        )
        spec = importlib.util.spec_from_file_location("s7_init_script", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert calls == [], (
            "importing the script initialised something; creation must "
            "happen only when main() is invoked"
        )

        module.main()
        assert len(calls) == 1, calls

        # The RIGHT store. "exactly one call" is satisfied by a script that
        # initialises /tmp/not-the-canonical-store.
        args, kwargs = calls[0]
        target = args[0] if args else kwargs.get("path")
        assert Path(target) == DEFAULT_STORE_ROOT / "ceremony.sqlite3", target


class TestTheCallsiteScannerIsItselfAttacked:
    """Three shapes defeated earlier versions of this scanner, so it is
    attacked directly rather than trusted because the repo happens to be
    clean."""

    def test_module_level_main_is_recorded_bare(self) -> None:
        assert find_initialiser_callsites(
            "def main():\n    initialise_authorization_store()\n"
        ) == ["main"]

    def test_a_class_method_is_not_module_level_main(self) -> None:
        assert find_initialiser_callsites(
            "class Hidden:\n"
            "    def main(self):\n"
            "        initialise_authorization_store()\n"
        ) == ["Hidden.main"]

    def test_a_nested_function_is_not_module_level_main(self) -> None:
        assert find_initialiser_callsites(
            "def helper():\n"
            "    def main():\n"
            "        initialise_authorization_store()\n"
            "    return main\n"
        ) == ["helper.<locals>.main"]

    def test_a_plain_assignment_alias_is_seen(self) -> None:
        assert find_initialiser_callsites(
            "def main():\n"
            "    init = s7.initialise_authorization_store\n"
            "    init()\n"
        ) == ["main"]

    def test_an_annotated_assignment_alias_is_seen(self) -> None:
        assert find_initialiser_callsites(
            "def main():\n"
            "    init: object = s7.initialise_authorization_store\n"
            "    init()\n"
        ) == ["main"]

    def test_an_import_alias_is_seen(self) -> None:
        assert find_initialiser_callsites(
            "from core.governance.operator_user_boundary import (\n"
            "    initialise_authorization_store as boot,\n"
            ")\n"
            "def main():\n    boot()\n"
        ) == ["main"]

    def test_getattr_by_string_is_seen(self) -> None:
        assert find_initialiser_callsites(
            'def main():\n'
            '    getattr(s7, "initialise_authorization_store")()\n'
        ) == ["main"]

    def test_a_reverse_ordered_alias_chain_is_seen(self) -> None:
        """Bounded iteration resolved only as many links as it had passes.
        Written in reverse, a four-link chain outran three passes."""
        assert find_initialiser_callsites(
            "def main():\n"
            "    d = c\n"
            "    c = b\n"
            "    b = a\n"
            "    a = s7.initialise_authorization_store\n"
            "    d()\n"
        ) == ["main"]

    def test_an_unrelated_call_is_not_seen(self) -> None:
        assert find_initialiser_callsites(
            "def main():\n    something_else()\n"
        ) == []


class TestPrivateFileModes:
    """The store holds founder credentials."""

    def test_the_directory_is_0700(self, tmp_path: Path) -> None:
        import os
        import stat as stat_module

        nested = tmp_path / "nested"
        s7.initialise_authorization_store(nested / "ceremony.sqlite3")
        mode = stat_module.S_IMODE(os.stat(nested).st_mode)
        assert mode == 0o700, oct(mode)

    def test_the_database_is_0600(self, tmp_path: Path) -> None:
        """Default umask produced 0644 -- world-readable credentials."""
        import os
        import stat as stat_module

        path = s7.initialise_authorization_store(tmp_path / "ceremony.sqlite3")
        mode = stat_module.S_IMODE(os.stat(path).st_mode)
        assert mode == 0o600, oct(mode)


class TestOpeningHasNoCreateRace:
    """is_file() then connect() is a TOCTOU window."""

    def test_a_file_vanishing_after_the_check_does_not_recreate_it(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """The window made deterministic: the existence check reports True
        while the file is gone. A plain sqlite3.connect() recreates an
        EMPTY database here and the caller believes it opened the store.
        """
        path = s7.initialise_authorization_store(tmp_path / "ceremony.sqlite3")
        path.unlink()
        monkeypatch.setattr(Path, "is_file", lambda self: True)
        with pytest.raises((FileNotFoundError, ValueError, sqlite3.DatabaseError)):
            s7.S7AuthorizationStore(path)
        monkeypatch.undo()
        assert not path.exists(), "opening recreated the database"

    def test_an_empty_database_is_not_accepted_as_a_store(
        self, tmp_path: Path
    ) -> None:
        """The state the race would leave behind must also refuse."""
        path = tmp_path / "ceremony.sqlite3"
        sqlite3.connect(path).close()
        with pytest.raises((ValueError, sqlite3.DatabaseError)):
            s7.S7AuthorizationStore(path)


class TestTheDaemonNeverCreatesTheStore:
    """The daemon may translate missing setup into a controlled refusal.
    It may never create the store: that would restore creation authority on
    the live request path and break the single-callsite rule.
    """

    def test_the_constructor_refuses_without_initialising(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """The SEAM, not the route. Named honestly: an earlier version of
        this class called this a daemon-refusal proof while never invoking
        Flask at all."""
        from core.governance.s7_webauthn_bootstrap import S7WebAuthnBootstrapStore

        bootstrap = S7WebAuthnBootstrapStore(tmp_path)
        path = bootstrap.db_path
        before_bytes = path.read_bytes()

        calls: list[tuple] = []
        monkeypatch.setattr(
            s7,
            "initialise_authorization_store",
            lambda *a, **k: calls.append((a, k)),
        )
        with pytest.raises((FileNotFoundError, ValueError)):
            s7.S7AuthorizationStore(path)

        assert calls == [], "the refusal path invoked creation authority"
        assert V1_AUTH not in _tables(path), "an authorization table appeared"
        assert path.read_bytes() == before_bytes, "the refusal changed bytes"


# ROUTE-LEVEL REFUSAL RED: NOT WRITTEN HERE, DELIBERATELY.
#
# The review is right that the seam test above is not a route test. My
# first attempt at the real one invoked `maez_daemon.create_app()`, which
# DOES NOT EXIST -- an invented seam, the same failure this chain has
# caught repeatedly. The real harness is `_DaemonAppClientMixin._client()`
# in tests/test_s7_1_daemon_internal_channel.py, and it is unittest-based,
# so the route RED belongs in that file rather than being reimplemented
# here.
#
# Outstanding, and named rather than faked: a bootstrap-only REQUEST
# asserting a structured content-light 503, zero initializer calls, no
# authorization table, and unchanged database bytes.


class TestPermissionVerificationDoesNotRepair:
    """Modes are part of what "correct" means.

    Reproduced before the fix: parent 0750 -> silently repaired to 0700,
    while an insecure 0644 database was left untouched. Half the posture
    fixed, the dangerous half open, and the caller told all was well.
    """

    def test_an_insecure_database_mode_refuses(self, tmp_path: Path) -> None:
        import os

        path = s7.initialise_authorization_store(tmp_path / "ceremony.sqlite3")
        os.chmod(path, 0o644)
        with pytest.raises(ValueError, match="insecure permissions"):
            s7.initialise_authorization_store(path)

    def test_an_insecure_database_mode_is_not_repaired(
        self, tmp_path: Path
    ) -> None:
        import os
        import stat as stat_module

        path = s7.initialise_authorization_store(tmp_path / "ceremony.sqlite3")
        os.chmod(path, 0o644)
        with contextlib.suppress(ValueError):
            s7.initialise_authorization_store(path)
        assert stat_module.S_IMODE(os.stat(path).st_mode) == 0o644, "it repaired"

    def test_an_insecure_parent_mode_refuses(self, tmp_path: Path) -> None:
        import os

        nested = tmp_path / "nested"
        path = s7.initialise_authorization_store(nested / "ceremony.sqlite3")
        os.chmod(nested, 0o750)
        with pytest.raises(ValueError, match="insecure permissions"):
            s7.initialise_authorization_store(path)

    def test_an_insecure_parent_mode_is_not_repaired(
        self, tmp_path: Path
    ) -> None:
        """The exact reproduction: the parent used to be chmod'd BEFORE
        classification, so it was already 0700 by the time anything
        refused."""
        import os
        import stat as stat_module

        nested = tmp_path / "nested"
        path = s7.initialise_authorization_store(nested / "ceremony.sqlite3")
        os.chmod(nested, 0o750)
        with contextlib.suppress(ValueError):
            s7.initialise_authorization_store(path)
        assert stat_module.S_IMODE(os.stat(nested).st_mode) == 0o750, "it repaired"

    def test_a_correct_store_verifies_without_mutation(
        self, tmp_path: Path
    ) -> None:
        """CONTROL: refusing everything would satisfy the four above."""
        import hashlib

        path = s7.initialise_authorization_store(tmp_path / "ceremony.sqlite3")
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        s7.initialise_authorization_store(path)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == before
