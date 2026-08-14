"""The preflight must be incapable of writing, and honest when it fails.

It is the one command the owner will run repeatedly against the live
ceremony store, so "read-only" has to be enforced by SQLite rather than by
this module's good intentions -- and a FAIL has to be reported as a fact
rather than raised as a crash, because an unmigrated store failing the v2
checks is the EXPECTED state before provisioning, not an error.
"""

from __future__ import annotations

import hashlib
import sqlite3

import pytest

from scripts import s7_r11_preflight as preflight


def _fixture_store(tmp_path):
    path = tmp_path / "ceremony.sqlite3"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE s7_founder_webauthn_credentials ("
                 "credential_ref TEXT, enabled INTEGER, role_names_json TEXT)")
    conn.execute(
        "INSERT INTO s7_founder_webauthn_credentials VALUES (?, ?, ?)",
        ("cred-1", 1, '["bonded_user"]'),
    )
    conn.commit()
    conn.close()
    path.chmod(0o600)
    return path


def test_the_open_mode_is_read_only_and_pinned() -> None:
    """If this constant changes, the write-refusal below stops meaning
    anything -- so it is asserted directly rather than only implied."""
    assert preflight.READ_ONLY_URI_MODE == "ro"


def test_the_connection_physically_cannot_write(tmp_path) -> None:
    """SQLite refuses, not us. This is the witness that would fail if the
    open mode were ever widened to rw."""
    store = _fixture_store(tmp_path)
    conn = preflight._open_read_only(store)
    try:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            conn.execute(
                "INSERT INTO s7_founder_webauthn_credentials VALUES ('x', 1, '[]')"
            )
    finally:
        conn.close()


def test_running_the_preflight_leaves_the_store_byte_identical(
    tmp_path, monkeypatch
) -> None:
    store = _fixture_store(tmp_path)
    before = hashlib.sha256(store.read_bytes()).hexdigest()
    monkeypatch.setattr(preflight, "STORE", store)
    monkeypatch.setattr(preflight, "RECEIPT", tmp_path / "s7_migration_receipt.json")

    preflight.run_preflight()

    assert hashlib.sha256(store.read_bytes()).hexdigest() == before


def test_an_unmigrated_store_FAILS_rather_than_raising(tmp_path, monkeypatch) -> None:
    """The expected pre-provisioning state. It must be reportable."""
    store = _fixture_store(tmp_path)
    monkeypatch.setattr(preflight, "STORE", store)
    monkeypatch.setattr(preflight, "RECEIPT", tmp_path / "s7_migration_receipt.json")

    checks = {c.name: c for c in preflight.run_preflight()}

    assert checks["v2 plane activated"].passed is False
    assert checks["R11 evidence table"].passed is False
    assert checks["founder credential"].passed is True


def test_creating_the_v2_table_is_not_activation(tmp_path, monkeypatch) -> None:
    """Guarded execution refuses without the migration RECEIPT, so a table
    alone must not read as activated -- the same rule the store itself
    enforces elsewhere."""
    store = _fixture_store(tmp_path)
    conn = sqlite3.connect(store)
    conn.execute(f"CREATE TABLE {preflight.V2_AUTH_TABLE} (artifact_id TEXT)")
    conn.commit()
    conn.close()
    monkeypatch.setattr(preflight, "STORE", store)
    monkeypatch.setattr(preflight, "RECEIPT", tmp_path / "s7_migration_receipt.json")

    checks = {c.name: c for c in preflight.run_preflight()}

    assert checks["v2 plane activated"].passed is False
    assert "receipt" in checks["v2 plane activated"].detail


def test_a_missing_store_fails_the_first_check_and_stops(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(preflight, "STORE", tmp_path / "absent.sqlite3")

    checks = preflight.run_preflight()

    assert len(checks) == 1
    assert checks[0].passed is False


def test_a_world_readable_store_FAILS(tmp_path, monkeypatch) -> None:
    """Found by mutation: nothing covered the mode check. The ceremony store
    holds founder credentials; if its mode has drifted open, that is a fact
    the owner must see before tapping, not after."""
    store = _fixture_store(tmp_path)
    store.chmod(0o644)
    monkeypatch.setattr(preflight, "STORE", store)

    checks = preflight.run_preflight()

    assert checks[0].passed is False
    assert "0644" in checks[0].detail


def _authorization_doc(**overrides):
    from scripts import cuda_migration as cm

    fields = {
        "window_id": "cutover-20260813-1500",
        "actions": cm.CUTOVER_ACTION_SET,
        "boot_id": "boot-fixture",
        "nonce": "ab12" * 16,
        "issued_at": "2026-08-13T15:00:00Z",
        "expires_at": "2026-08-13T19:00:00Z",
        "owner": "rohit",
        "parent_bench_evidence_sha256": "a" * 64,
        "rollback_manifest_sha256": cm.FROZEN_ROLLBACK_MANIFEST_SHA256,
    }
    fields.update(overrides)
    return cm.CutoverAuthorizationDoc(**fields)


def _install_authorization(tmp_path, monkeypatch, doc) -> None:
    """Place a real, canonically-encoded authorization where the check looks."""
    from scripts import cuda_cutover
    from scripts import cuda_migration as cm

    root = tmp_path / "bench"
    (root / "receipts").mkdir(parents=True)
    wrapper = {
        "schema": cm.CUTOVER_AUTHORIZATION_SCHEMA,
        "binding_sha256": doc.binding_sha256,
        "fields": {
            "window_id": doc.window_id,
            "actions": list(doc.actions),
            "boot_id": doc.boot_id,
            "nonce": doc.nonce,
            "issued_at": doc.issued_at,
            "expires_at": doc.expires_at,
            "owner": doc.owner,
            "parent_bench_evidence_sha256": doc.parent_bench_evidence_sha256,
            "rollback_manifest_sha256": doc.rollback_manifest_sha256,
        },
    }
    (root / cuda_cutover.AUTHORIZATION_NAME).write_bytes(
        cm._canonical_wrapper_bytes(wrapper)
    )
    monkeypatch.setattr(cuda_cutover, "BENCH_ROOT", root)


def test_a_missing_authorization_FAILS_rather_than_reading_READY(monkeypatch, tmp_path) -> None:
    """The gap that let the preflight report READY while the ceremony would
    have refused: it checked the store and the locator but never the
    authority the ceremony actually consumes."""
    from scripts import cuda_cutover

    monkeypatch.setattr(cuda_cutover, "BENCH_ROOT", tmp_path / "empty")

    check = preflight._check_cutover_authorization()

    assert check.passed is False
    assert "absent" in check.detail


def test_an_EXPIRED_authorization_fails_here_not_at_the_execution_edge(
    monkeypatch, tmp_path
) -> None:
    _install_authorization(
        tmp_path,
        monkeypatch,
        _authorization_doc(
            issued_at="2026-01-01T00:00:00Z", expires_at="2026-01-01T04:00:00Z"
        ),
    )

    check = preflight._check_cutover_authorization()

    assert check.passed is False
    assert "EXPIRED" in check.detail


def test_a_STALE_BOOT_authorization_fails(monkeypatch, tmp_path) -> None:
    """Boot binding exists so an authorization cannot survive a restart. If
    the host rebooted since minting, that must be visible before the tap."""
    import datetime

    # TTL is exact: issued + 4h, or the document itself refuses.
    issued = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    now = issued.strftime("%Y-%m-%dT%H:%M:%SZ")
    future = (issued + datetime.timedelta(seconds=14_400)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    _install_authorization(
        tmp_path,
        monkeypatch,
        _authorization_doc(
            boot_id="a-boot-that-is-not-this-one", issued_at=now, expires_at=future
        ),
    )

    check = preflight._check_cutover_authorization()

    assert check.passed is False
    assert "boot id" in check.detail


def test_a_broken_probe_becomes_a_FAIL_not_a_crash(tmp_path, monkeypatch) -> None:
    """The owner runs this to learn the truth; it must never die halfway
    and leave them guessing which checks never ran."""
    store = _fixture_store(tmp_path)
    monkeypatch.setattr(preflight, "STORE", store)
    monkeypatch.setattr(preflight, "RECEIPT", tmp_path / "s7_migration_receipt.json")

    def _boom():
        raise RuntimeError("probe exploded")

    monkeypatch.setattr(preflight, "_check_not_born", _boom)

    checks = preflight.run_preflight()

    assert any(c.passed is False and "probe exploded" in c.detail for c in checks)
    # every later probe still ran
    assert any(c.name == "completion locator" for c in checks)


class TestPinnedModeChecks:
    """The two live-run findings the preflight could not see: a group-writable
    pinned source and a 775 unit directory. Fixtures monkeypatch the
    ceremony's OWN path constants -- the predicate itself is imported from the
    ceremony, so these tests also witness that the two cannot drift."""

    @pytest.fixture()
    def _pinned_fixture(self, tmp_path, monkeypatch):
        from scripts import cuda_cutover

        unit_dir = tmp_path / "systemd-user"
        unit_dir.mkdir(mode=0o700)
        dropin_dir = tmp_path / "systemd-user" / "llama-server.service.d"
        dropin_dir.mkdir(mode=0o700)
        recovery_dir = tmp_path / "bench" / "recovery"
        recovery_dir.mkdir(mode=0o700, parents=True)

        unit = unit_dir / "llama-server.service"
        dropin = dropin_dir / "mtp.conf"
        override = tmp_path / "override.conf"
        for path in (unit, dropin, override):
            path.write_bytes(b"fixture")
            path.chmod(0o600)

        monkeypatch.setattr(
            cuda_cutover,
            "CUTOVER_RECOVERY_SOURCES",
            ((unit, "llama-server.service"), (dropin, "mtp.conf")),
        )
        monkeypatch.setattr(cuda_cutover, "CUTOVER_OVERRIDE_SOURCE", override)
        monkeypatch.setattr(cuda_cutover, "CUTOVER_OVERRIDE_DIRECTORY", dropin_dir)
        monkeypatch.setattr(cuda_cutover, "BENCH_ROOT", tmp_path / "bench")
        # Unit-fragment resolution shells out to systemctl; the fixture
        # resolves to the same files the pin would receive.
        monkeypatch.setattr(
            cuda_cutover,
            "_resolve_user_unit_fragments",
            lambda names: {"llama-server.service": unit},
        )
        return {
            "unit": unit,
            "dropin": dropin,
            "override": override,
            "dropin_dir": dropin_dir,
            "recovery_dir": recovery_dir,
        }

    def test_clean_fixtures_pass_both_checks(self, _pinned_fixture) -> None:
        assert preflight._check_pinned_sources().passed is True
        assert preflight._check_pinned_directories().passed is True

    def test_a_group_writable_pinned_source_FAILS_by_name(
        self, _pinned_fixture
    ) -> None:
        """Live finding 4: the CUDA override was group-writable and only the
        ceremony noticed. The preflight must now name the file and the mode."""
        _pinned_fixture["override"].chmod(0o660)

        check = preflight._check_pinned_sources()

        assert check.passed is False
        assert "cuda-override-source" in check.detail
        assert "0660" in check.detail

    def test_a_group_writable_unit_fragment_FAILS(self, _pinned_fixture) -> None:
        _pinned_fixture["unit"].chmod(0o664)

        check = preflight._check_pinned_sources()

        assert check.passed is False
        assert "unit-fragment:llama-server.service" in check.detail

    def test_a_775_unit_directory_FAILS_by_name(self, _pinned_fixture) -> None:
        """Live finding 5: every systemd unit directory was 775."""
        _pinned_fixture["dropin_dir"].chmod(0o775)

        check = preflight._check_pinned_directories()

        assert check.passed is False
        assert "systemd-user-override-directory" in check.detail
        assert "0775" in check.detail

    def test_an_absent_pinned_source_FAILS_rather_than_raising(
        self, _pinned_fixture
    ) -> None:
        _pinned_fixture["dropin"].unlink()

        check = preflight._check_pinned_sources()

        assert check.passed is False
        assert "mtp.conf" in check.detail

    def test_unresolvable_unit_fragments_FAIL_rather_than_raising(
        self, _pinned_fixture, monkeypatch
    ) -> None:
        from scripts import cuda_cutover

        def _boom(names):
            raise cuda_cutover.CutoverRefusal("consumer_internal_pre")

        monkeypatch.setattr(cuda_cutover, "_resolve_user_unit_fragments", _boom)

        check = preflight._check_pinned_sources()

        assert check.passed is False
        assert "unit fragments unresolvable" in check.detail

    def test_the_predicate_is_the_ceremonys_not_a_copy(self) -> None:
        """The preflight must report through the SAME callable the pin
        refuses through; a re-encoded predicate could drift silently."""
        import inspect

        from scripts import cuda_cutover

        source = inspect.getsource(preflight._check_pinned_sources)
        assert "cuda_cutover._pinned_file_mode_violation" in source
        assert "& 0o022" not in source
        dir_source = inspect.getsource(preflight._check_pinned_directories)
        assert "cuda_cutover._pinned_directory_mode_violation" in dir_source
        assert "& 0o022" not in dir_source

    def test_both_checks_are_wired_into_run_preflight(
        self, _pinned_fixture, tmp_path, monkeypatch
    ) -> None:
        """Direct-call tests above cannot notice the probe being dropped
        from the roster; the owner only ever sees run_preflight's output."""
        store = _fixture_store(tmp_path)
        monkeypatch.setattr(preflight, "STORE", store)
        monkeypatch.setattr(
            preflight, "RECEIPT", tmp_path / "s7_migration_receipt.json"
        )

        names = {check.name for check in preflight.run_preflight()}

        assert "pinned sources" in names
        assert "pinned directories" in names


class TestWebAuthnDependencyCheck:
    """The wrong-interpreter class (live, 2026-08-13): py_webauthn is lazy,
    so a bare python3 passed every other check and first failed mid-ceremony
    under a misleading name. This check runs the verifier's own probe."""

    def test_a_present_dependency_passes_and_names_the_interpreter(self) -> None:
        import sys

        check = preflight._check_webauthn_dependency()

        assert check.passed is True
        assert sys.executable in check.detail

    def test_a_missing_dependency_FAILS_and_names_the_interpreter(
        self, monkeypatch
    ) -> None:
        import sys

        from core.governance import s7_webauthn_verifier as verifier_mod

        def _absent(self):
            return None

        monkeypatch.setattr(
            verifier_mod.S7ProductionWebAuthnVerifier, "_load", _absent
        )

        check = preflight._check_webauthn_dependency()

        assert check.passed is False
        assert "MISSING" in check.detail
        assert sys.executable in check.detail

    def test_the_check_is_wired_into_run_preflight(
        self, tmp_path, monkeypatch
    ) -> None:
        store = _fixture_store(tmp_path)
        monkeypatch.setattr(preflight, "STORE", store)
        monkeypatch.setattr(
            preflight, "RECEIPT", tmp_path / "s7_migration_receipt.json"
        )

        names = {check.name for check in preflight.run_preflight()}

        assert "webauthn dependency" in names
