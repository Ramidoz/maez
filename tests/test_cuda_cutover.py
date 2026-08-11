"""Cutover authority tooling — Act-1 minting and execution-edge consumption.

Every property the ratification demanded: full parent verification,
hardened creation, decoder round-trip, and genuine single use with
TTL/boot/action-set/recovery bindings.
"""

from __future__ import annotations

import json
import ast
import inspect
import shutil
import textwrap
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


def test_legacy_consumption_path_is_structurally_retired() -> None:
    source = textwrap.dedent(
        inspect.getsource(cutover.consume_cutover_authorization)
    )
    function = ast.parse(source).body[0]
    assert isinstance(function, ast.FunctionDef)
    executable = [
        statement
        for statement in function.body
        if not (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)
        )
    ]
    assert len(executable) == 1
    assert isinstance(executable[0], ast.Raise)


def test_legacy_consumer_has_no_v1_publication_callsite() -> None:
    source = textwrap.dedent(
        inspect.getsource(cutover.consume_cutover_authorization)
    )
    tree = ast.parse(source)
    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "_anchored_exclusive_write" not in called
    assert "cuda_migration.cutover_consumption.v1" not in source


def test_document_bindings_are_closed(root: Path) -> None:
    doc = cutover.mint_cutover_authorization(root=root)
    with pytest.raises(ValueError, match="cutover_action_set"):
        replace(doc, actions=doc.actions[:-1])
    with pytest.raises(ValueError, match="recovery_identity_mismatch"):
        replace(doc, rollback_manifest_sha256="a" * 64)
    with pytest.raises(ValueError, match="authorization_ttl"):
        replace(doc, expires_at="2026-08-03T23:59:59Z")
    with pytest.raises(ValueError, match="authorization_nonce"):
        replace(doc, nonce="short")
