"""Cutover authority tooling — Act-1 minting and execution-edge consumption.

Every property the ratification demanded: full parent verification,
hardened creation, decoder round-trip, and genuine single use with
TTL/boot/action-set/recovery bindings.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from scripts import cuda_cutover as cutover
from scripts import cuda_migration as cm

REAL_ROOT = Path("/home/rohit/maez/local/cuda_migration_bench")


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    """A private bench-root replica carrying the real durable receipt."""

    replica = tmp_path / "bench"
    (replica / "receipts").mkdir(parents=True, mode=0o700)
    (replica / "markers").mkdir(mode=0o700)
    (replica / "recovery").mkdir(mode=0o700)
    shutil.copy2(REAL_ROOT / cutover.RECEIPT_NAME, replica / cutover.RECEIPT_NAME)
    shutil.copy2(
        REAL_ROOT / "recovery" / "llama-server.service",
        replica / "recovery" / "llama-server.service",
    )
    shutil.copy2(
        REAL_ROOT / "recovery" / "mtp.conf", replica / "recovery" / "mtp.conf"
    )
    return replica


def test_mint_round_trips_and_binds_the_real_parent(root: Path) -> None:
    doc = cutover.mint_cutover_authorization(root=root)
    payload = (root / cutover.AUTHORIZATION_NAME).read_bytes()
    rebuilt = cm.PersistedDoc(payload).obj
    assert type(rebuilt) is cm.CutoverAuthorizationDoc
    assert rebuilt.binding_sha256 == doc.binding_sha256
    assert rebuilt.actions == cm.CUTOVER_ACTION_SET
    receipt = json.loads((root / cutover.RECEIPT_NAME).read_bytes())
    assert (
        rebuilt.parent_bench_evidence_sha256
        == receipt["fields"]["bench_binding_sha256"]
    )
    mode = (root / cutover.AUTHORIZATION_NAME).stat().st_mode & 0o777
    assert mode == 0o600


def test_mint_refuses_tampered_or_non_passed_parent(root: Path) -> None:
    receipt_path = root / cutover.RECEIPT_NAME
    wrapper = json.loads(receipt_path.read_bytes())
    wrapper["fields"]["decision"] = "keep_vulkan"
    receipt_path.write_bytes(cm._canonical_wrapper_bytes(wrapper))
    with pytest.raises(cutover.CutoverRefusal, match="not_bench_passed"):
        cutover.mint_cutover_authorization(root=root)

    wrapper = json.loads(receipt_path.read_bytes())
    wrapper["fields"]["decision"] = "bench_passed"
    receipt_path.write_bytes(
        cm._canonical_wrapper_bytes(wrapper) + b"\n"
    )
    with pytest.raises(cutover.CutoverRefusal, match="noncanonical"):
        cutover.mint_cutover_authorization(root=root)


def test_mint_refuses_symlinked_target_and_double_mint(root: Path) -> None:
    target = root / cutover.AUTHORIZATION_NAME
    outside = root.parent / "outside.json"
    outside.write_bytes(b"{}")
    target.symlink_to(outside)
    with pytest.raises(OSError):
        cutover.mint_cutover_authorization(root=root)
    target.unlink()

    cutover.mint_cutover_authorization(root=root)
    with pytest.raises(FileExistsError):
        cutover.mint_cutover_authorization(root=root)


def test_consumption_is_atomic_and_single_use(root: Path) -> None:
    minted = cutover.mint_cutover_authorization(root=root)
    consumed = cutover.consume_cutover_authorization(root=root)
    assert consumed.nonce == minted.nonce
    marker = root / "markers" / f"cutover-{minted.nonce}.consumed"
    assert marker.exists()
    with pytest.raises(cutover.CutoverRefusal, match="authorization_consumed"):
        cutover.consume_cutover_authorization(root=root)


def test_consumption_refuses_expired_and_boot_mismatch(root: Path) -> None:
    doc = cutover.mint_cutover_authorization(root=root)
    with pytest.raises(cutover.CutoverRefusal, match="authorization_expired"):
        cutover.consume_cutover_authorization(
            root=root, now_utc=doc.expires_at
        )

    payload = json.loads((root / cutover.AUTHORIZATION_NAME).read_bytes())
    payload["fields"]["boot_id"] = "not-the-current-boot"
    fields = dict(payload["fields"])
    forged = cm.CutoverAuthorizationDoc(
        **{**fields, "actions": tuple(fields["actions"])}
    )
    payload["binding_sha256"] = forged.binding_sha256
    (root / cutover.AUTHORIZATION_NAME).write_bytes(
        cm._canonical_wrapper_bytes(payload)
    )
    with pytest.raises(
        cutover.CutoverRefusal, match="authorization_boot_mismatch"
    ):
        cutover.consume_cutover_authorization(root=root)


def test_document_bindings_are_closed(root: Path) -> None:
    doc = cutover.mint_cutover_authorization(root=root)
    with pytest.raises(ValueError, match="cutover_action_set"):
        replace(doc, actions=doc.actions[:-1])
    with pytest.raises(ValueError, match="recovery_identity_mismatch"):
        replace(doc, recovery_unit_sha256="a" * 64)
    with pytest.raises(ValueError, match="authorization_ttl"):
        replace(doc, expires_at="2026-08-03T23:59:59Z")
    with pytest.raises(ValueError, match="authorization_nonce"):
        replace(doc, nonce="short")
