from __future__ import annotations

import contextlib
import hashlib
import ipaddress
import os
import shutil
import socket
import sys
import uuid
from datetime import date as Date
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Iterator


REAL_HOME = Path("/home/rohit/maez").resolve()
_ORIGINAL_BASE_DB = None
_ORIGINAL_SCORING_DB = None
_ORIGINAL_BIRTH_STATE_PATH = None
_ORIGINAL_LAST_CONSOLIDATION_FILE = None
_PATH_ENV_ALLOWLIST = {
    "MAEZ_HOME",
    "MAEZ_DATA",
    "MAEZ_CONFIG",
    "MAEZ_CACHE",
}
_NON_PATH_ENV_ALLOWLIST = {
    "MAEZ_OWNER_TIMEZONE",
    "MAEZ_RECALL_TRIAD_ENABLED",
    "MAEZ_RECALL_SHADOW_ENABLED",
    "MAEZ_RECALL_STATUS_INTERCEPT_ENABLED",
}
_SANDBOX_PATH_OVERRIDES = {
    "MAEZ_ROUTING_OBSERVATION_DB_PATH": ("memory", "routing_observation.db"),
    "MAEZ_LEDGER_DB_PATH": ("memory", "ledger.db"),
    "MAEZ_CALENDAR_STORE_DB": ("memory", "calendar.db"),
    "MAEZ_SELF_AWARENESS_PATH": ("memory", "self_awareness.json"),
    "MAEZ_AUDIT_LOG_PATH": ("logs", "audit.jsonl"),
}


class NotSandboxError(RuntimeError):
    pass


class EgressBlockedError(OSError):
    pass


def _resolve(path: str | os.PathLike) -> Path:
    return Path(path).expanduser().resolve()


def _under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


@contextlib.contextmanager
def sandbox_env(root: str | os.PathLike) -> Iterator[Path]:
    sandbox_root = _resolve(root)
    managed_keys = (
        "MAEZ_HOME",
        "MAEZ_DATA",
        "MAEZ_CONFIG",
        "MAEZ_CACHE",
        "MAEZ_OWNER_TIMEZONE",
        *_SANDBOX_PATH_OVERRIDES,
    )
    previous = {key: os.environ.get(key) for key in managed_keys}
    os.environ["MAEZ_HOME"] = str(sandbox_root)
    os.environ["MAEZ_DATA"] = str(sandbox_root)
    os.environ["MAEZ_CONFIG"] = str(sandbox_root / "config")
    os.environ["MAEZ_CACHE"] = str(sandbox_root / ".cache")
    os.environ["MAEZ_OWNER_TIMEZONE"] = "America/Chicago"
    for key, parts in _SANDBOX_PATH_OVERRIDES.items():
        os.environ[key] = str(sandbox_root.joinpath(*parts))
    try:
        yield sandbox_root
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def assert_no_real_path_overrides(root: str | os.PathLike) -> None:
    sandbox_root = _resolve(root)
    for key, value in os.environ.items():
        if not key.startswith("MAEZ_") or not value:
            continue
        if key in _NON_PATH_ENV_ALLOWLIST:
            continue
        if key in _PATH_ENV_ALLOWLIST:
            candidate = _resolve(value)
        elif _looks_path_bearing(key, value):
            candidate = _resolve(value)
        else:
            continue
        if not _under(candidate, sandbox_root):
            raise NotSandboxError(f"{key} points outside sandbox: {candidate}")


def _looks_path_bearing(key: str, value: str) -> bool:
    if key.endswith(("_PATH", "_DIR", "_DB", "_FILE", "_ROOT", "_HOME", "_DATA", "_CONFIG", "_CACHE")):
        return True
    return value.startswith("/") or value.startswith("~")


def patch_memory_manager_base_db(root: str | os.PathLike):
    sandbox_root = _resolve(root)
    assert_no_real_path_overrides(sandbox_root)
    import memory.memory_manager as mm_mod

    global _ORIGINAL_BASE_DB, _ORIGINAL_LAST_CONSOLIDATION_FILE
    if _ORIGINAL_BASE_DB is None:
        _ORIGINAL_BASE_DB = mm_mod.BASE_DB
    if _ORIGINAL_LAST_CONSOLIDATION_FILE is None:
        _ORIGINAL_LAST_CONSOLIDATION_FILE = mm_mod.MemoryManager._LAST_CONSOLIDATION_FILE
    mm_mod.BASE_DB = sandbox_root / "memory" / "db"
    mm_mod.BASE_DB.mkdir(parents=True, exist_ok=True)
    mm_mod.MemoryManager._LAST_CONSOLIDATION_FILE = (
        sandbox_root / "memory" / "last_consolidation.txt"
    )
    _patch_loaded_path_modules(sandbox_root)
    _reset_dispatcher_memory_manager()
    return mm_mod


def _patch_loaded_path_modules(sandbox_root: Path) -> None:
    global _ORIGINAL_BIRTH_STATE_PATH, _ORIGINAL_SCORING_DB
    scoring = sys.modules.get("core.memory.memory_scoring")
    if scoring is not None:
        if _ORIGINAL_SCORING_DB is None:
            _ORIGINAL_SCORING_DB = scoring._DB_PATH
        scoring._DB_PATH = sandbox_root / "memory" / "recall_stats.db"
    birth = sys.modules.get("core.memory.birth")
    if birth is not None:
        if _ORIGINAL_BIRTH_STATE_PATH is None:
            _ORIGINAL_BIRTH_STATE_PATH = birth.DEFAULT_STATE_PATH
        birth.DEFAULT_STATE_PATH = sandbox_root / "memory" / "self_awareness.json"


def _reset_dispatcher_memory_manager() -> None:
    brain_loop = sys.modules.get("core.brain.brain_loop")
    if brain_loop is None:
        return
    manager = getattr(brain_loop, "_DISPATCHER_MEMORY_MANAGER", None)
    close = getattr(manager, "close", None)
    if callable(close):
        close()
    setattr(brain_loop, "_DISPATCHER_MEMORY_MANAGER", None)


def assert_sandbox(root: str | os.PathLike | None = None) -> None:
    sandbox_root = _resolve(root or os.environ.get("MAEZ_HOME", ""))
    if not str(sandbox_root):
        raise NotSandboxError("MAEZ_HOME is unset")
    if sandbox_root == REAL_HOME or _under(REAL_HOME, sandbox_root):
        raise NotSandboxError(f"sandbox root resolves to real home: {sandbox_root}")

    assert_no_real_path_overrides(sandbox_root)
    from core.infra import paths

    for actual in (
        paths.home(),
        paths.data_dir(),
        paths.config_dir(),
        paths.cache_dir(),
        paths.memory_dir(),
        paths.logs_dir(),
    ):
        resolved = _resolve(actual)
        if not _under(resolved, sandbox_root):
            raise NotSandboxError(f"path outside sandbox: {resolved}")

    mm_mod = sys.modules.get("memory.memory_manager")
    if mm_mod is not None:
        if not _under(_resolve(mm_mod.BASE_DB), sandbox_root):
            raise NotSandboxError(f"memory_manager.BASE_DB outside sandbox: {mm_mod.BASE_DB}")
        last_consolidation = mm_mod.MemoryManager._LAST_CONSOLIDATION_FILE
        if not _under(_resolve(last_consolidation), sandbox_root):
            raise NotSandboxError(
                "memory_manager._LAST_CONSOLIDATION_FILE outside sandbox: "
                f"{last_consolidation}"
            )

    scoring = sys.modules.get("core.memory.memory_scoring")
    if scoring is not None and not _under(_resolve(scoring._DB_PATH), sandbox_root):
        raise NotSandboxError(f"memory_scoring._DB_PATH outside sandbox: {scoring._DB_PATH}")

    birth = sys.modules.get("core.memory.birth")
    if birth is not None and not _under(_resolve(birth.DEFAULT_STATE_PATH), sandbox_root):
        raise NotSandboxError(f"birth.DEFAULT_STATE_PATH outside sandbox: {birth.DEFAULT_STATE_PATH}")


def _port_value(port) -> int | None:
    try:
        return int(port)
    except (TypeError, ValueError):
        return None


def _host_is_loopback(host: object) -> bool:
    if not isinstance(host, str):
        return False
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _addr_is_allowed(address: object, ports: set[int]) -> bool:
    if not ports or not isinstance(address, tuple) or len(address) < 2:
        return False
    host = address[0]
    port = _port_value(address[1])
    return port in ports and _host_is_loopback(host)


@contextlib.contextmanager
def no_egress(*, allow_loopback_ports: tuple[int, ...] = ()) -> Iterator[None]:
    allowed_ports = {int(port) for port in allow_loopback_ports}
    original_create_connection = socket.create_connection
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_sendto = socket.socket.sendto
    original_getaddrinfo = socket.getaddrinfo

    def blocked(*_args, **_kwargs):
        raise EgressBlockedError("offline eval harness blocks socket egress")

    def guarded_create_connection(address, *args, **kwargs):
        if not _addr_is_allowed(address, allowed_ports):
            blocked()
        return original_create_connection(address, *args, **kwargs)

    def guarded_connect(sock, address):
        if not _addr_is_allowed(address, allowed_ports):
            blocked()
        return original_connect(sock, address)

    def guarded_connect_ex(sock, address):
        if not _addr_is_allowed(address, allowed_ports):
            blocked()
        return original_connect_ex(sock, address)

    def guarded_getaddrinfo(host, port, *args, **kwargs):
        address = (host, port)
        if not _addr_is_allowed(address, allowed_ports):
            blocked()
        rows = original_getaddrinfo(host, port, *args, **kwargs)
        loopback_rows = [row for row in rows if _addr_is_allowed(row[-1], allowed_ports)]
        if not loopback_rows:
            blocked()
        return loopback_rows

    socket.create_connection = guarded_create_connection
    socket.socket.connect = guarded_connect
    socket.socket.connect_ex = guarded_connect_ex
    socket.socket.sendto = blocked
    socket.getaddrinfo = guarded_getaddrinfo
    try:
        yield
    finally:
        socket.create_connection = original_create_connection
        socket.socket.connect = original_connect
        socket.socket.connect_ex = original_connect_ex
        socket.socket.sendto = original_sendto
        socket.getaddrinfo = original_getaddrinfo


def seed_dated_memory(
    probe_id: str,
    variant_id: str,
    *,
    date: Date,
    content: str,
    tier: str = "core",
    run_id: str,
) -> str:
    root = os.environ.get("MAEZ_HOME")
    if not root:
        raise NotSandboxError("MAEZ_HOME is unset")
    patch_memory_manager_base_db(root)
    assert_sandbox(root)

    from memory.memory_manager import MemoryManager

    timestamp = datetime.combine(date, time(hour=12), timezone.utc).isoformat()
    fixture_id = f"eval-{probe_id}-{variant_id}-{uuid.uuid4().hex[:8]}"
    metadata = {
        "timestamp": timestamp,
        "date": date.isoformat(),
        "source": "recall_flip_eval",
        "type": "synthetic_test_fixture",
        "synthetic_test_fixture": True,
        "fixture_run_id": run_id,
        "fixture_probe_id": probe_id,
        "fixture_variant_id": variant_id,
        "fixture_origin": "recall_flip_eval_2a",
        "trust_tier": "untrusted",
    }
    manager = MemoryManager()
    collection = manager.core if tier == "core" else manager.daily
    collection.add(ids=[fixture_id], documents=[content], metadatas=[metadata])
    return fixture_id


def real_substrate_fingerprint() -> tuple:
    paths = [
        REAL_HOME / "memory" / "db",
        REAL_HOME / "memory" / "recall_stats.db",
        REAL_HOME / "memory" / "routing_observation.db",
    ]
    return tuple(_fingerprint_path(path) for path in paths)


def _fingerprint_path(path: Path) -> tuple:
    if not path.exists():
        return (str(path), "missing")
    if path.is_file():
        stat = path.stat()
        return (str(path), "file", stat.st_size, _file_hash(path))
    digest = hashlib.sha256()
    file_count = 0
    total_size = 0
    for child in sorted(path.rglob("*")):
        if not child.is_file():
            continue
        relative = str(child.relative_to(path))
        stat = child.stat()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(_file_hash(child).encode("ascii"))
        digest.update(b"\0")
        total_size += stat.st_size
        file_count += 1
    return (str(path), "dir", file_count, total_size, digest.hexdigest())


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def teardown(root: str | os.PathLike) -> None:
    restore_memory_patches()
    shutil.rmtree(root, ignore_errors=True)


def memory_patch_snapshot() -> dict:
    snapshot = {}
    mm_mod = sys.modules.get("memory.memory_manager")
    if mm_mod is not None:
        snapshot["base_db"] = mm_mod.BASE_DB
        snapshot["last_consolidation_file"] = (
            mm_mod.MemoryManager._LAST_CONSOLIDATION_FILE
        )
    scoring = sys.modules.get("core.memory.memory_scoring")
    if scoring is not None:
        snapshot["scoring_db_path"] = scoring._DB_PATH
    birth = sys.modules.get("core.memory.birth")
    if birth is not None:
        snapshot["birth_state_path"] = birth.DEFAULT_STATE_PATH
    return snapshot


def restore_memory_patch_snapshot(snapshot: dict) -> None:
    mm_mod = sys.modules.get("memory.memory_manager")
    if mm_mod is not None:
        if "base_db" in snapshot:
            mm_mod.BASE_DB = snapshot["base_db"]
        if "last_consolidation_file" in snapshot:
            mm_mod.MemoryManager._LAST_CONSOLIDATION_FILE = snapshot[
                "last_consolidation_file"
            ]
    scoring = sys.modules.get("core.memory.memory_scoring")
    if scoring is not None and "scoring_db_path" in snapshot:
        scoring._DB_PATH = snapshot["scoring_db_path"]
    birth = sys.modules.get("core.memory.birth")
    if birth is not None and "birth_state_path" in snapshot:
        birth.DEFAULT_STATE_PATH = snapshot["birth_state_path"]
    _reset_dispatcher_memory_manager()


def restore_memory_patches() -> None:
    import memory.memory_manager as mm_mod

    _reset_dispatcher_memory_manager()
    if _ORIGINAL_BASE_DB is not None:
        mm_mod.BASE_DB = _ORIGINAL_BASE_DB
    if _ORIGINAL_LAST_CONSOLIDATION_FILE is not None:
        mm_mod.MemoryManager._LAST_CONSOLIDATION_FILE = _ORIGINAL_LAST_CONSOLIDATION_FILE
    scoring = sys.modules.get("core.memory.memory_scoring")
    if scoring is not None and _ORIGINAL_SCORING_DB is not None:
        scoring._DB_PATH = _ORIGINAL_SCORING_DB
    birth = sys.modules.get("core.memory.birth")
    if birth is not None and _ORIGINAL_BIRTH_STATE_PATH is not None:
        birth.DEFAULT_STATE_PATH = _ORIGINAL_BIRTH_STATE_PATH
