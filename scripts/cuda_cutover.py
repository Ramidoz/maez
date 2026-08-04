"""Cutover authority tooling — Act 1 minting and execution-edge consumption.

Tracked and tested (unlike the retired local minter). Nothing here mutates
a service: minting writes one authorization document; consumption burns its
nonce atomically. Every mutating ceremony command remains owner-typed.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import secrets
from pathlib import Path

from scripts import cuda_migration as cm
from scripts import cuda_bench_driver as driver

BENCH_ROOT = Path("/home/rohit/maez/local/cuda_migration_bench")
RECEIPT_NAME = "command-assemble-stage1-attempt-026-terminal.json"
AUTHORIZATION_NAME = "receipts/cutover-authorization.json"
MARKER_DIR = "markers"


class CutoverRefusal(Exception):
    """Typed refusal; the message is the closed reason code."""


def _now_z() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _verified_bench_parent(root: Path) -> tuple[str, str]:
    """Fully verify the bench_passed receipt; return (evidence, artifact) hashes."""

    receipt_path = root / RECEIPT_NAME
    try:
        raw = receipt_path.read_bytes()
    except OSError as exc:
        raise CutoverRefusal("parent_receipt_unreadable") from exc
    try:
        wrapper = json.loads(raw)
    except ValueError as exc:
        raise CutoverRefusal("parent_receipt_malformed") from exc
    if (
        type(wrapper) is not dict
        or set(wrapper) != {"schema", "binding_sha256", "fields"}
        or wrapper["schema"] != driver.ASSEMBLE_RECEIPT_SCHEMA
        or type(wrapper["fields"]) is not dict
    ):
        raise CutoverRefusal("parent_receipt_malformed")
    if cm._canonical_wrapper_bytes(wrapper) != raw:
        raise CutoverRefusal("parent_receipt_noncanonical")
    fields = wrapper["fields"]
    bench = fields.get("bench_binding_sha256")
    bundle = fields.get("bundle_binding_sha256")
    if (
        fields.get("decision") != "bench_passed"
        or fields.get("reasons") != []
        or type(bench) is not str
        or cm._SHA256_RE.fullmatch(bench) is None
        or type(bundle) is not str
        or cm._SHA256_RE.fullmatch(bundle) is None
        or wrapper.get("binding_sha256") != bundle
    ):
        raise CutoverRefusal("parent_receipt_not_bench_passed")
    return bench, hashlib.sha256(raw).hexdigest()


def _anchored_exclusive_write(root: Path, relative: str, payload: bytes) -> Path:
    """O_NOFOLLOW/O_EXCL creation at 0600 inside the bench root."""

    target = root / relative
    parent_fd = os.open(
        target.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    )
    try:
        fd = os.open(
            target.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent_fd,
        )
        try:
            os.write(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        os.close(parent_fd)
    return target


def mint_cutover_authorization(
    *,
    root: Path = BENCH_ROOT,
    owner: str = "rohit",
) -> cm.CutoverAuthorizationDoc:
    """Act 1: mint the enforceable cutover authorization (owner-run)."""

    bench_evidence, _artifact = _verified_bench_parent(root)
    recovery_unit = hashlib.sha256(
        (root / "recovery" / "llama-server.service").read_bytes()
    ).hexdigest()
    recovery_dropin = hashlib.sha256(
        (root / "recovery" / "mtp.conf").read_bytes()
    ).hexdigest()
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    doc = cm.CutoverAuthorizationDoc(
        window_id=now.strftime("cutover-%Y%m%d-%H%M"),
        actions=cm.CUTOVER_ACTION_SET,
        boot_id=Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        nonce=secrets.token_hex(32),
        issued_at=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        expires_at=(
            now + datetime.timedelta(seconds=cm.CUTOVER_TTL_S)
        ).strftime("%Y-%m-%dT%H:%M:%SZ"),
        owner=owner,
        parent_bench_evidence_sha256=bench_evidence,
        recovery_unit_sha256=recovery_unit,
        recovery_dropin_sha256=recovery_dropin,
    )
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
            "recovery_unit_sha256": doc.recovery_unit_sha256,
            "recovery_dropin_sha256": doc.recovery_dropin_sha256,
        },
    }
    payload = cm._canonical_wrapper_bytes(wrapper)
    path = _anchored_exclusive_write(root, AUTHORIZATION_NAME, payload)
    rebuilt = cm.PersistedDoc(path.read_bytes()).obj
    if (
        type(rebuilt) is not cm.CutoverAuthorizationDoc
        or rebuilt.binding_sha256 != doc.binding_sha256
    ):
        raise CutoverRefusal("mint_roundtrip_failed")
    return doc


def consume_cutover_authorization(
    *,
    root: Path = BENCH_ROOT,
    now_utc: str | None = None,
) -> cm.CutoverAuthorizationDoc:
    """Burn the nonce atomically at the execution edge.

    Refuses when expired, boot-mismatched, or already consumed. The O_EXCL
    marker is the single-use guarantee; a consumption receipt binds the
    burn to the document and the moment.
    """

    path = root / AUTHORIZATION_NAME
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CutoverRefusal("authorization_missing") from exc
    doc = cm.PersistedDoc(raw).obj
    if type(doc) is not cm.CutoverAuthorizationDoc:
        raise CutoverRefusal("authorization_wrong_type")
    moment = now_utc if now_utc is not None else _now_z()
    if cm._compare_utc_z(moment, doc.expires_at) >= 0:
        raise CutoverRefusal("authorization_expired")
    live_boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    if live_boot != doc.boot_id:
        raise CutoverRefusal("authorization_boot_mismatch")
    marker = f"{MARKER_DIR}/cutover-{doc.nonce}.consumed"
    try:
        _anchored_exclusive_write(
            root,
            marker,
            cm._canonical_wrapper_bytes(
                {
                    "schema": "cuda_migration.cutover_consumption.v1",
                    "binding_sha256": doc.binding_sha256,
                    "fields": {
                        "nonce": doc.nonce,
                        "window_id": doc.window_id,
                        "consumed_at": moment,
                    },
                }
            ),
        )
    except FileExistsError:
        raise CutoverRefusal("authorization_consumed") from None
    return doc


def main() -> None:
    doc = mint_cutover_authorization()
    print(f"wrote      {BENCH_ROOT / AUTHORIZATION_NAME}")
    print(f"window_id  {doc.window_id}")
    print(f"valid      {doc.issued_at} -> {doc.expires_at}  (4h)")
    print(f"boot_id    {doc.boot_id}")
    print(f"parent     bench evidence {doc.parent_bench_evidence_sha256[:24]}…")
    print(f"actions    {', '.join(doc.actions)}")
    print("single-use: consumed atomically at the execution edge.")


if __name__ == "__main__":
    main()
