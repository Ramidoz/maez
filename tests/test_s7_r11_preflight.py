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
