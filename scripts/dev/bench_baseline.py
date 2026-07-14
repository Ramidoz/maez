"""Fail-closed repository test-baseline authority commands."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from collections.abc import Callable
from typing import Any

PY = "/home/rohit/maez/.venv/bin/python"
SUITE_CMD = ["-B", "-m", "pytest", "tests/", "-q"]
BENCH_ROOT = "/home/rohit/maez/local/cuda_migration_bench"
BASELINE = f"{BENCH_ROOT}/repo-baseline.v1.json"
WITNESS_DIR = f"{BENCH_ROOT}/bootstrap-witness"
SCHEMA = "bench_repo_baseline.v1"
PLUGIN_PATH = os.path.join(os.path.dirname(__file__), "bench_report_plugin.py")

_REQUIRED_KEYS = {
    "schema",
    "pytest_status",
    "failures",
    "known_flaky",
    "collected",
    "base_commit",
    "helper_sha256",
    "plugin_sha256",
    "interpreter",
    "suite_cmd",
    "rotated_from",
}
_WITNESS_PAYLOAD_FILES = (
    "run1.jsonl",
    "run2.jsonl",
    "run1.txt",
    "run2.txt",
    "run1.status",
    "run2.status",
    "collect.txt",
    "collect.status",
    "manifest-flaky.txt",
    "witness.json",
)
_WITNESS_FILES = set(_WITNESS_PAYLOAD_FILES) | {"hashes.txt"}
_APPROVED_MANIFEST_FLAKY = {
    "tests/test_fast_backend_cloud_retirement.py::"
    "FastReplyAuditAndStaticBoundaryTests::"
    "test_service_audit_behavior_records_cloud_retirement_without_raw_text"
}
_HEX40 = re.compile(r"[0-9a-f]{40}")
_HEX64 = re.compile(r"[0-9a-f]{64}")


def _read_helper_bytes() -> bytes:
    with open(__file__, "rb") as handle:
        return handle.read()


_STARTUP_HELPER_SHA256 = hashlib.sha256(_read_helper_bytes()).hexdigest()


def _self_sha256() -> str:
    return _STARTUP_HELPER_SHA256


def _live_helper_sha256() -> str:
    return hashlib.sha256(_read_helper_bytes()).hexdigest()


def _require_helper_stable() -> None:
    if _live_helper_sha256() != _STARTUP_HELPER_SHA256:
        raise SystemExit("baseline_helper_drift")


def _read_plugin_bytes() -> bytes:
    with open(PLUGIN_PATH, "rb") as handle:
        return handle.read()


def _plugin_sha256() -> str:
    return hashlib.sha256(_read_plugin_bytes()).hexdigest()


def _git_toplevel() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        raise SystemExit("git_toplevel_unavailable")
    return proc.stdout.strip()


def _head_commit() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or not _HEX40.fullmatch(proc.stdout.strip()):
        raise SystemExit("git_head_unavailable")
    return proc.stdout.strip()


def _is_ancestor(old: str, new: str = "HEAD") -> bool:
    proc = subprocess.run(["git", "merge-base", "--is-ancestor", old, new])
    return proc.returncode == 0


def _git_capture(args: list[str]) -> bytes:
    proc = subprocess.run(["git", *args], capture_output=True)
    if proc.returncode != 0:
        return b""
    return proc.stdout


def _hazard() -> None:
    raise SystemExit("baseline_filesystem_hazard")


def _relative_parts(abs_path: str) -> list[str]:
    root = os.path.abspath(BENCH_ROOT)
    path = os.path.abspath(abs_path)
    try:
        if os.path.commonpath([root, path]) != root:
            _hazard()
    except ValueError:
        _hazard()
    rel = os.path.relpath(path, root)
    if rel == ".":
        return []
    parts = rel.split(os.sep)
    if any(part in {"", ".", ".."} for part in parts):
        _hazard()
    return parts


def _check_directory_fd(fd: int) -> None:
    info = os.fstat(fd)
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.geteuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        _hazard()


def _check_file_fd(fd: int) -> None:
    info = os.fstat(fd)
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.geteuid()
        or info.st_nlink != 1
        or stat.S_IMODE(info.st_mode) != 0o600
    ):
        _hazard()


def _open_root_fd() -> int:
    try:
        fd = os.open(BENCH_ROOT, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError:
        _hazard()
    try:
        _check_directory_fd(fd)
    except BaseException:
        os.close(fd)
        raise
    return fd


def _open_directory_fd(abs_path: str) -> int:
    parts = _relative_parts(abs_path)
    dfd = _open_root_fd()
    for part in parts:
        try:
            nfd = os.open(
                part,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=dfd,
            )
        except OSError:
            os.close(dfd)
            _hazard()
        try:
            _check_directory_fd(nfd)
        except BaseException:
            os.close(nfd)
            os.close(dfd)
            raise
        os.close(dfd)
        dfd = nfd
    return dfd


def _open_parent_fd(abs_path: str) -> tuple[int, str]:
    parts = _relative_parts(abs_path)
    if not parts:
        _hazard()
    dfd = _open_root_fd()
    for part in parts[:-1]:
        try:
            nfd = os.open(
                part,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=dfd,
            )
        except OSError:
            os.close(dfd)
            _hazard()
        try:
            _check_directory_fd(nfd)
        except BaseException:
            os.close(nfd)
            os.close(dfd)
            raise
        os.close(dfd)
        dfd = nfd
    return dfd, parts[-1]


def _anchored_read_bytes(abs_path: str) -> bytes:
    """Read a private file through an owner-only descriptor walk."""
    dfd, name = _open_parent_fd(abs_path)
    try:
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=dfd)
        except OSError:
            _hazard()
    finally:
        os.close(dfd)
    try:
        _check_file_fd(fd)
    except BaseException:
        os.close(fd)
        raise
    try:
        with os.fdopen(fd, "rb") as handle:
            return handle.read()
    except OSError:
        _hazard()


def _anchored_listdir(abs_path: str) -> set[str]:
    dfd = _open_directory_fd(abs_path)
    try:
        try:
            return set(os.listdir(dfd))
        except OSError:
            _hazard()
    finally:
        os.close(dfd)


def _existing_create_collision(dfd: int, name: str) -> None:
    try:
        info = os.stat(name, dir_fd=dfd, follow_symlinks=False)
    except OSError:
        _hazard()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.geteuid()
        or info.st_nlink != 1
        or stat.S_IMODE(info.st_mode) != 0o600
    ):
        _hazard()
    raise FileExistsError(name)


def _json_bytes(doc: dict[str, Any]) -> bytes:
    return (json.dumps(doc, indent=1) + "\n").encode()


def _anchored_create_json(
    abs_path: str,
    doc: dict[str, Any],
    *,
    pre_publish: Callable[[], None] | None = None,
) -> None:
    dfd, name = _open_parent_fd(abs_path)
    temp_name = f".{name}.create"
    fd: int | None = None
    created = False
    try:
        try:
            fd = os.open(
                temp_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=dfd,
            )
            created = True
        except OSError:
            _hazard()
        os.fchmod(fd, 0o600)
        _check_file_fd(fd)
        with os.fdopen(fd, "wb") as handle:
            fd = None
            handle.write(_json_bytes(doc))
            handle.flush()
            os.fsync(handle.fileno())
        if pre_publish is not None:
            pre_publish()
        try:
            os.link(
                temp_name,
                name,
                src_dir_fd=dfd,
                dst_dir_fd=dfd,
                follow_symlinks=False,
            )
        except FileExistsError:
            _existing_create_collision(dfd, name)
        except OSError:
            _hazard()
        os.unlink(temp_name, dir_fd=dfd)
        created = False
        os.fsync(dfd)
    except BaseException:
        if fd is not None:
            os.close(fd)
        if created:
            try:
                os.unlink(temp_name, dir_fd=dfd)
            except OSError:
                pass
        raise
    finally:
        os.close(dfd)


def _anchored_replace_json(
    abs_path: str,
    doc: dict[str, Any],
    *,
    pre_publish: Callable[[], None] | None = None,
) -> None:
    dfd, name = _open_parent_fd(abs_path)
    temp_name = f".{name}.rotate"
    fd: int | None = None
    created = False
    try:
        try:
            fd = os.open(
                temp_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=dfd,
            )
            created = True
        except OSError:
            _hazard()
        os.fchmod(fd, 0o600)
        _check_file_fd(fd)
        with os.fdopen(fd, "wb") as handle:
            fd = None
            handle.write(_json_bytes(doc))
            handle.flush()
            os.fsync(handle.fileno())
        if pre_publish is not None:
            pre_publish()
        os.replace(temp_name, name, src_dir_fd=dfd, dst_dir_fd=dfd)
        created = False
        os.fsync(dfd)
    except BaseException:
        if fd is not None:
            os.close(fd)
        if created:
            try:
                os.unlink(temp_name, dir_fd=dfd)
            except OSError:
                pass
        raise
    finally:
        os.close(dfd)


def _failures_from_report_bytes(raw: bytes, status: int) -> list[str]:
    ids: set[str] = set()
    try:
        lines = raw.decode().splitlines()
        for line in lines:
            if not line.strip():
                continue
            entry = json.loads(line)
            if (
                not isinstance(entry, dict)
                or set(entry) != {"id", "when", "outcome"}
                or not isinstance(entry["id"], str)
                or entry["when"] not in {"setup", "call", "teardown"}
                or entry["outcome"] not in {"passed", "failed", "skipped"}
            ):
                raise ValueError
            if entry["outcome"] == "failed":
                ids.add(entry["id"])
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        raise SystemExit("failures_unparsed") from None
    found = sorted(ids)
    if status == 1 and not found:
        raise SystemExit("failures_unparsed")
    if status == 0 and found:
        raise SystemExit("failures_phantom")
    return found


def _failures_from_report(report_path: str, status: int) -> list[str]:
    with open(report_path, "rb") as handle:
        return _failures_from_report_bytes(handle.read(), status)


def _write_snapshot_file(directory: str, name: str, payload: bytes) -> None:
    path = os.path.join(directory, name)
    fd = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o600,
    )
    try:
        os.fchmod(fd, 0o600)
        _check_file_fd(fd)
        with os.fdopen(fd, "wb") as handle:
            fd = -1
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        dfd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            _check_directory_fd(dfd)
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if fd >= 0:
            os.close(fd)


def _sitecustomize_bytes(helper_sha256: str) -> bytes:
    return (
        "import os\n"
        f"_EXPECTED_HELPER_SHA256 = {helper_sha256!r}\n"
        "if os.environ.get('PYTHONSAFEPATH') == '1':\n"
        "    observed = os.environ.pop("
        "'BENCH_BASELINE_HELPER_SHA256', None)\n"
        "    if observed != _EXPECTED_HELPER_SHA256:\n"
        "        raise RuntimeError('baseline helper binding mismatch')\n"
        "    os.environ.pop('PYTHONSAFEPATH', None)\n"
        "else:\n"
        "    os.environ.pop('BENCH_BASELINE_HELPER_SHA256', None)\n"
    ).encode()


def _run_suite(
    expected_plugin_sha256: str | None = None,
) -> tuple[int, list[str], str]:
    _require_helper_stable()
    plugin_bytes = _read_plugin_bytes()
    executed_plugin_sha256 = hashlib.sha256(plugin_bytes).hexdigest()
    if (
        expected_plugin_sha256 is not None
        and executed_plugin_sha256 != expected_plugin_sha256
    ):
        raise SystemExit("baseline_helper_drift")
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tmp:
        report_path = tmp.name
    try:
        with tempfile.TemporaryDirectory(
            prefix=f"bench-plugin-{executed_plugin_sha256}-"
        ) as plugin_dir:
            os.chmod(plugin_dir, 0o700)
            _write_snapshot_file(
                plugin_dir, "bench_report_plugin.py", plugin_bytes
            )
            _write_snapshot_file(
                plugin_dir,
                "sitecustomize.py",
                _sitecustomize_bytes(_STARTUP_HELPER_SHA256),
            )
            env = dict(
                os.environ,
                BENCH_REPORT_PATH=report_path,
                BENCH_BASELINE_HELPER_SHA256=_STARTUP_HELPER_SHA256,
                PYTHONPATH=plugin_dir,
                PYTHONSAFEPATH="1",
            )
            proc = subprocess.run(
                [PY, *SUITE_CMD, "--tb=no", "-p", "bench_report_plugin"],
                capture_output=True,
                text=True,
                env=env,
            )
        _require_helper_stable()
        if proc.returncode not in (0, 1):
            raise SystemExit(f"suite_run_errored status={proc.returncode}")
        return (
            proc.returncode,
            _failures_from_report(report_path, proc.returncode),
            executed_plugin_sha256,
        )
    finally:
        try:
            os.unlink(report_path)
        except FileNotFoundError:
            pass


def _parse_collect_count(raw: str) -> int:
    matches = re.findall(r"(\d+) tests? collected", raw)
    if not matches or int(matches[-1]) <= 0:
        raise SystemExit("collect_count_unparseable_or_zero")
    return int(matches[-1])


def _collect_count() -> int:
    _require_helper_stable()
    proc = subprocess.run(
        [PY, "-B", "-m", "pytest", "tests/", "--collect-only", "-q"],
        capture_output=True,
        text=True,
    )
    _require_helper_stable()
    if proc.returncode not in (0, 1):
        raise SystemExit(f"collect_errored status={proc.returncode}")
    return _parse_collect_count(f"{proc.stdout}\n{proc.stderr}")


def _string_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _validate_shapes(base: dict[str, Any]) -> None:
    status = base.get("pytest_status")
    failures = base.get("failures")
    rotated_from = base.get("rotated_from")
    ok = (
        base.get("schema") == SCHEMA
        and isinstance(status, int)
        and not isinstance(status, bool)
        and status in (0, 1)
        and _string_list(failures)
        and _string_list(base.get("known_flaky"))
        and (status == 1) == bool(failures)
        and isinstance(base.get("collected"), int)
        and not isinstance(base.get("collected"), bool)
        and base["collected"] > 0
        and isinstance(base.get("base_commit"), str)
        and bool(_HEX40.fullmatch(base["base_commit"]))
        and isinstance(base.get("helper_sha256"), str)
        and bool(_HEX64.fullmatch(base["helper_sha256"]))
        and isinstance(base.get("plugin_sha256"), str)
        and bool(_HEX64.fullmatch(base["plugin_sha256"]))
        and isinstance(base.get("interpreter"), str)
        and _string_list(base.get("suite_cmd"))
        and (
            rotated_from is None
            or (
                isinstance(rotated_from, str)
                and bool(_HEX64.fullmatch(rotated_from))
            )
        )
    )
    if not ok:
        raise SystemExit("baseline_schema_mismatch")


def _authority_from_bytes(
    raw: bytes, *, skip_helper_check: bool = False
) -> dict[str, Any]:
    _require_helper_stable()
    try:
        base = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise SystemExit("baseline_schema_mismatch") from None
    if not isinstance(base, dict) or set(base) != _REQUIRED_KEYS:
        raise SystemExit("baseline_schema_mismatch")
    _validate_shapes(base)
    if (
        not skip_helper_check
        and base["helper_sha256"] != _STARTUP_HELPER_SHA256
    ):
        raise SystemExit("baseline_helper_drift")
    if base["plugin_sha256"] != _plugin_sha256():
        raise SystemExit("baseline_helper_drift")
    if base["interpreter"] != PY or base["suite_cmd"] != SUITE_CMD:
        raise SystemExit("baseline_command_mismatch")
    if not _is_ancestor(base["base_commit"]):
        raise SystemExit("baseline_not_ancestor")
    return base


def _open_authority_with_bytes(
    *, skip_helper_check: bool = False
) -> tuple[dict[str, Any], bytes]:
    raw = _anchored_read_bytes(BASELINE)
    return _authority_from_bytes(raw, skip_helper_check=skip_helper_check), raw


def _open_authority(*, skip_helper_check: bool = False) -> dict[str, Any]:
    base, _raw = _open_authority_with_bytes(skip_helper_check=skip_helper_check)
    return base


def _parse_status(raw: bytes) -> int:
    try:
        text = raw.decode().strip()
        if not re.fullmatch(r"\d+", text):
            raise ValueError
        return int(text)
    except (UnicodeDecodeError, ValueError):
        raise SystemExit("witness_status_invalid") from None


def _expected_witness_invocations() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    suite_argv = [PY, *SUITE_CMD, "--tb=no", "-p", "bench_report_plugin"]
    runs = [
        {
            "argv": suite_argv,
            "env": {
                "BENCH_REPORT_PATH": os.path.join(WITNESS_DIR, f"run{run}.jsonl"),
                "PYTHONPATH": "scripts/dev",
            },
        }
        for run in (1, 2)
    ]
    collection = {
        "argv": [
            PY,
            "-B",
            "-m",
            "pytest",
            "tests/",
            "--collect-only",
            "-q",
        ],
        "env": {"BENCH_REPORT_PATH": None, "PYTHONPATH": None},
    }
    return runs, collection


def _load_witness() -> dict[str, Any]:
    if _anchored_listdir(WITNESS_DIR) != _WITNESS_FILES:
        raise SystemExit("witness_file_set_mismatch")
    manifest_raw = _anchored_read_bytes(os.path.join(WITNESS_DIR, "hashes.txt"))
    hashes: dict[str, str] = {}
    try:
        for line in manifest_raw.decode().splitlines():
            match = re.fullmatch(r"([0-9a-f]{64})  ([^/]+)", line)
            if not match or match.group(2) in hashes:
                raise ValueError
            hashes[match.group(2)] = match.group(1)
    except (UnicodeDecodeError, ValueError):
        raise SystemExit("witness_file_set_mismatch") from None
    if set(hashes) != set(_WITNESS_PAYLOAD_FILES):
        raise SystemExit("witness_file_set_mismatch")
    payloads = {
        name: _anchored_read_bytes(os.path.join(WITNESS_DIR, name))
        for name in _WITNESS_PAYLOAD_FILES
    }
    for name, data in payloads.items():
        if hashlib.sha256(data).hexdigest() != hashes[name]:
            raise SystemExit("witness_hash_mismatch")

    try:
        meta = json.loads(payloads["witness.json"])
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise SystemExit("witness_meta_invalid") from None
    expected_runs, expected_collection = _expected_witness_invocations()
    if (
        not isinstance(meta, dict)
        or set(meta)
        != {"suite_runs", "collection", "cwd", "base_commit", "plugin_sha256"}
        or meta.get("suite_runs") != expected_runs
        or meta.get("collection") != expected_collection
        or not isinstance(meta.get("base_commit"), str)
        or not _HEX40.fullmatch(meta["base_commit"])
        or not isinstance(meta.get("plugin_sha256"), str)
        or not _HEX64.fullmatch(meta["plugin_sha256"])
    ):
        raise SystemExit("witness_meta_invalid")
    if meta.get("cwd") != _git_toplevel():
        raise SystemExit("witness_toplevel_mismatch")
    if meta["plugin_sha256"] != _plugin_sha256():
        raise SystemExit("baseline_helper_drift")
    if not _is_ancestor(meta["base_commit"]):
        raise SystemExit("baseline_not_ancestor")

    statuses = [
        _parse_status(payloads[f"run{run}.status"])
        for run in (1, 2)
    ]
    collect_status = _parse_status(payloads["collect.status"])
    if any(status not in (0, 1) for status in statuses) or collect_status not in (
        0,
        1,
    ):
        raise SystemExit("witness_status_invalid")
    runs = [
        set(_failures_from_report_bytes(payloads[f"run{run}.jsonl"], statuses[run - 1]))
        for run in (1, 2)
    ]
    try:
        collect_text = payloads["collect.txt"].decode()
        manifest_text = payloads["manifest-flaky.txt"].decode()
    except UnicodeDecodeError:
        raise SystemExit("witness_meta_invalid") from None
    collected = _parse_collect_count(collect_text)
    manifest_flaky = {
        line.strip() for line in manifest_text.splitlines() if line.strip()
    }
    if manifest_flaky != _APPROVED_MANIFEST_FLAKY:
        raise SystemExit("witness_manifest_invalid")
    return {
        "stable": runs[0] & runs[1],
        "flaky": (runs[0] ^ runs[1]) | manifest_flaky,
        "collected": collected,
        "statuses": statuses,
        "collect_status": collect_status,
        "base_commit": meta["base_commit"],
        "plugin_sha256": meta["plugin_sha256"],
    }


def record() -> None:
    _require_helper_stable()
    record_head = _head_commit()
    _require_helper_stable()
    witness = _load_witness()
    _require_helper_stable()
    if witness["base_commit"] != record_head:
        raise SystemExit("witness_head_mismatch")
    (
        _verification_status,
        verification_failures,
        executed_plugin_sha256,
    ) = _run_suite(witness["plugin_sha256"])
    _require_helper_stable()
    unexplained = (
        set(verification_failures) - witness["stable"] - witness["flaky"]
    )
    if unexplained:
        raise SystemExit(f"record_unstable: {sorted(unexplained)[:5]}")
    collected = _collect_count()
    _require_helper_stable()
    if collected < witness["collected"]:
        raise SystemExit("collection_count_dropped")
    doc = {
        "schema": SCHEMA,
        "pytest_status": 1 if witness["stable"] else 0,
        "failures": sorted(witness["stable"]),
        "known_flaky": sorted(witness["flaky"]),
        "collected": collected,
        "base_commit": record_head,
        "helper_sha256": _STARTUP_HELPER_SHA256,
        "plugin_sha256": executed_plugin_sha256,
        "interpreter": PY,
        "suite_cmd": SUITE_CMD,
        "rotated_from": None,
    }
    _validate_shapes(doc)

    def validate_publication() -> None:
        _require_helper_stable()
        if _head_commit() != record_head:
            raise SystemExit("record_head_drift")

    _anchored_create_json(BASELINE, doc, pre_publish=validate_publication)
    print(
        f"baseline_recorded failures={len(doc['failures'])} "
        f"flaky={len(doc['known_flaky'])} collected={doc['collected']}"
    )


def reconcile() -> None:
    _require_helper_stable()
    base = _open_authority()
    status, failures, _executed_plugin_sha256 = _run_suite(base["plugin_sha256"])
    _require_helper_stable()
    new = set(failures) - set(base["failures"]) - set(base["known_flaky"])
    collected = _collect_count()
    _require_helper_stable()
    print(
        f"status={status} new_failures={len(new)} collected={collected} "
        f"floor={base['collected']}"
    )
    if new:
        raise SystemExit(f"new_red: {sorted(new)[:5]}")
    if collected < base["collected"]:
        raise SystemExit("collection_count_dropped")


def bootstrap_check() -> None:
    _require_helper_stable()
    base = _open_authority()
    witness = _load_witness()
    _require_helper_stable()
    known = set(base["known_flaky"])
    if known != witness["flaky"]:
        raise SystemExit("bootstrap_drift: known_flaky_set")
    drift = set(base["failures"]) ^ witness["stable"]
    unexplained = drift - known
    if unexplained:
        raise SystemExit(f"bootstrap_drift: {sorted(unexplained)[:5]}")
    if base["collected"] < witness["collected"]:
        raise SystemExit("collection_count_dropped")
    print("bootstrap_equality_ok")


def _load_rotation_grant(authorization_path: str) -> dict[str, str]:
    toplevel = os.path.abspath(_git_toplevel())
    path = os.path.abspath(authorization_path)
    try:
        if os.path.commonpath([toplevel, path]) != toplevel:
            raise ValueError
    except ValueError:
        raise SystemExit("rotation_unauthorized") from None
    rel = os.path.relpath(path, toplevel)
    intro_output = _git_capture(["rev-list", "--reverse", "HEAD", "--", rel])
    try:
        intros = intro_output.decode().split()
    except UnicodeDecodeError:
        intros = []
    if not intros:
        raise SystemExit("rotation_unauthorized")
    intro = intros[0]
    blob_intro = _git_capture(["show", f"{intro}:{rel}"])
    blob_head = _git_capture(["show", f"HEAD:{rel}"])
    if not blob_intro or blob_intro != blob_head:
        raise SystemExit("rotation_unauthorized")
    try:
        grant = json.loads(blob_intro)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise SystemExit("rotation_unauthorized") from None
    if (
        not isinstance(grant, dict)
        or set(grant)
        != {"old_helper_sha256", "old_authority_sha256", "reason"}
        or not isinstance(grant.get("old_helper_sha256"), str)
        or not _HEX64.fullmatch(grant["old_helper_sha256"])
        or not isinstance(grant.get("old_authority_sha256"), str)
        or not _HEX64.fullmatch(grant["old_authority_sha256"])
        or not isinstance(grant.get("reason"), str)
        or not grant["reason"].strip()
    ):
        raise SystemExit("rotation_unauthorized")
    old_helper = _git_capture(["show", f"{intro}:scripts/dev/bench_baseline.py"])
    if (
        not old_helper
        or hashlib.sha256(old_helper).hexdigest() != grant["old_helper_sha256"]
    ):
        raise SystemExit("rotation_unauthorized")
    return grant


def rotate(authorization_path: str) -> None:
    _require_helper_stable()
    rotation_head = _head_commit()
    _require_helper_stable()
    grant = _load_rotation_grant(authorization_path)
    _require_helper_stable()
    old, old_bytes = _open_authority_with_bytes(skip_helper_check=True)
    if (
        grant["old_helper_sha256"] != old["helper_sha256"]
        or grant["old_authority_sha256"]
        != hashlib.sha256(old_bytes).hexdigest()
    ):
        raise SystemExit("rotation_unauthorized")
    status, failures, _executed_plugin_sha256 = _run_suite(old["plugin_sha256"])
    _require_helper_stable()
    regressions = set(failures) - set(old["failures"]) - set(old["known_flaky"])
    if regressions:
        raise SystemExit(f"rotate_blocked_new_red: {sorted(regressions)[:5]}")
    collected = _collect_count()
    _require_helper_stable()
    if collected < old["collected"]:
        raise SystemExit("collection_count_dropped")
    doc = {
        "schema": SCHEMA,
        "pytest_status": status,
        "failures": sorted(failures),
        "known_flaky": old["known_flaky"],
        "collected": collected,
        "base_commit": rotation_head,
        "helper_sha256": _STARTUP_HELPER_SHA256,
        "plugin_sha256": _executed_plugin_sha256,
        "interpreter": PY,
        "suite_cmd": SUITE_CMD,
        "rotated_from": grant["old_authority_sha256"],
    }
    _validate_shapes(doc)

    def validate_publication() -> None:
        _require_helper_stable()
        if _head_commit() != rotation_head:
            raise SystemExit("rotation_head_drift")

    _anchored_replace_json(BASELINE, doc, pre_publish=validate_publication)
    print(f"baseline_rotated from={doc['rotated_from'][:12]}")


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["record"]:
        record()
    elif args == ["reconcile"]:
        reconcile()
    elif args == ["bootstrap-check"]:
        bootstrap_check()
    elif len(args) == 2 and args[0] == "rotate":
        rotate(args[1])
    else:
        raise SystemExit("usage: bench_baseline.py {record|reconcile|bootstrap-check|rotate GRANT}")


if __name__ == "__main__":
    main()
