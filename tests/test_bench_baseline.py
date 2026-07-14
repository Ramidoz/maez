"""Adversarial tests for the repository baseline authority tooling."""

from __future__ import annotations

import builtins
import hashlib
import json
import os
import re
import stat
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.dev import bench_baseline as baseline
from scripts.dev import bench_report_plugin as report_plugin


COMMIT = "1" * 40
HELPER_SHA = "a" * 64
PLUGIN_SHA = "b" * 64
OLD_RED = "tests/test_existing.py::test_red"
D09 = (
    "tests/test_fast_backend_cloud_retirement.py::"
    "FastReplyAuditAndStaticBoundaryTests::"
    "test_service_audit_behavior_records_cloud_retirement_without_raw_text"
)
WITNESS_PAYLOADS = (
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


def _report(nodeid: str, when: str, outcome: str) -> SimpleNamespace:
    return SimpleNamespace(
        nodeid=nodeid,
        when=when,
        outcome=outcome,
        failed=outcome == "failed",
    )


def _report_entries(path) -> list[dict[str, str]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def _write_private(path: Path, data: bytes | str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if isinstance(data, str):
        data = data.encode()
    path.write_bytes(data)
    path.chmod(0o600)


def _authority_doc(**overrides) -> dict[str, object]:
    values: dict[str, object] = {
        "schema": baseline.SCHEMA,
        "pytest_status": 1,
        "failures": [OLD_RED],
        "known_flaky": [D09],
        "collected": 100,
        "base_commit": COMMIT,
        "helper_sha256": HELPER_SHA,
        "plugin_sha256": PLUGIN_SHA,
        "interpreter": baseline.PY,
        "suite_cmd": list(baseline.SUITE_CMD),
        "rotated_from": None,
    }
    values.update(overrides)
    return values


def _report_jsonl(failures: set[str]) -> str:
    return "".join(
        json.dumps({"id": nodeid, "when": "call", "outcome": "failed"}) + "\n"
        for nodeid in sorted(failures)
    )


@pytest.fixture
def secure_root(tmp_path, monkeypatch):
    root = tmp_path / "bench"
    root.mkdir(mode=0o700)
    witness_dir = root / "bootstrap-witness"
    authority_path = root / "repo-baseline.v1.json"
    repo = tmp_path / "repo"
    repo.mkdir(mode=0o700)

    monkeypatch.setattr(baseline, "BENCH_ROOT", str(root))
    monkeypatch.setattr(baseline, "WITNESS_DIR", str(witness_dir))
    monkeypatch.setattr(baseline, "BASELINE", str(authority_path))
    monkeypatch.setattr(
        baseline, "_STARTUP_HELPER_SHA256", HELPER_SHA, raising=False
    )
    monkeypatch.setattr(
        baseline, "_live_helper_sha256", lambda: HELPER_SHA, raising=False
    )
    monkeypatch.setattr(baseline, "_self_sha256", lambda: HELPER_SHA)
    monkeypatch.setattr(baseline, "_plugin_sha256", lambda: PLUGIN_SHA)
    monkeypatch.setattr(baseline, "_git_toplevel", lambda: str(repo))
    monkeypatch.setattr(baseline, "_head_commit", lambda: COMMIT)
    monkeypatch.setattr(baseline, "_is_ancestor", lambda _old, _new="HEAD": True)
    return SimpleNamespace(
        root=root,
        witness=witness_dir,
        authority=authority_path,
        repo=repo,
    )


def _witness_meta() -> dict[str, object]:
    suite_argv = [
        baseline.PY,
        *baseline.SUITE_CMD,
        "--tb=no",
        "-p",
        "bench_report_plugin",
    ]
    return {
        "suite_runs": [
            {
                "argv": suite_argv,
                "env": {
                    "BENCH_REPORT_PATH": str(
                        Path(baseline.WITNESS_DIR) / f"run{run}.jsonl"
                    ),
                    "PYTHONPATH": "scripts/dev",
                },
            }
            for run in (1, 2)
        ],
        "collection": {
            "argv": [
                baseline.PY,
                "-B",
                "-m",
                "pytest",
                "tests/",
                "--collect-only",
                "-q",
            ],
            "env": {"BENCH_REPORT_PATH": None, "PYTHONPATH": None},
        },
        "cwd": baseline._git_toplevel(),
        "base_commit": COMMIT,
        "plugin_sha256": PLUGIN_SHA,
    }


def _seal_witness(
    *,
    run1: set[str] | None = None,
    run2: set[str] | None = None,
    statuses: tuple[int, int] = (1, 1),
    collect_status: int = 0,
    collected: int = 100,
    manifest: set[str] | None = None,
    meta_overrides: dict[str, object] | None = None,
    meta_document: object | None = None,
    meta_raw: str | None = None,
    omit_hash: str | None = None,
) -> Path:
    run1 = {OLD_RED} if run1 is None else run1
    run2 = {OLD_RED} if run2 is None else run2
    manifest = {D09} if manifest is None else manifest
    witness = Path(baseline.WITNESS_DIR)
    witness.mkdir(mode=0o700)
    payloads: dict[str, bytes | str] = {
        "run1.jsonl": _report_jsonl(run1),
        "run2.jsonl": _report_jsonl(run2),
        "run1.txt": "run one output\n",
        "run2.txt": "run two output\n",
        "run1.status": f"{statuses[0]}\n",
        "run2.status": f"{statuses[1]}\n",
        "collect.txt": f"{collected} tests collected in 0.01s\n",
        "collect.status": f"{collect_status}\n",
        "manifest-flaky.txt": "".join(f"{item}\n" for item in sorted(manifest)),
    }
    if meta_raw is not None:
        payloads["witness.json"] = meta_raw
    else:
        meta = _witness_meta() if meta_document is None else meta_document
        if meta_overrides:
            assert isinstance(meta, dict)
            meta.update(meta_overrides)
        payloads["witness.json"] = json.dumps(meta, indent=1) + "\n"
    for name, data in payloads.items():
        _write_private(witness / name, data)
    hash_lines = []
    for name in WITNESS_PAYLOADS:
        if name == omit_hash:
            continue
        digest = hashlib.sha256((witness / name).read_bytes()).hexdigest()
        hash_lines.append(f"{digest}  {name}\n")
    _write_private(witness / "hashes.txt", "".join(hash_lines))
    witness.chmod(0o700)
    return witness


def _write_authority(doc: dict[str, object] | None = None) -> Path:
    path = Path(baseline.BASELINE)
    _write_private(path, json.dumps(doc or _authority_doc(), indent=1) + "\n")
    return path


def _stub_suite(status: int, failures: list[str], plugin_sha: str = PLUGIN_SHA):
    def run(expected_plugin_sha: str | None = None):
        if expected_plugin_sha is not None:
            assert expected_plugin_sha == plugin_sha
        return status, failures, plugin_sha

    return run


class TestBenchReportPlugin:
    def test_preserves_exact_parameterized_nodeid(self, tmp_path, monkeypatch):
        report_path = tmp_path / "reports.jsonl"
        monkeypatch.setenv("BENCH_REPORT_PATH", str(report_path))

        report_plugin.pytest_runtest_logreport(
            _report("tests/test_example.py::test_x[a - b]", "call", "passed")
        )

        assert _report_entries(report_path) == [
            {
                "id": "tests/test_example.py::test_x[a - b]",
                "when": "call",
                "outcome": "passed",
            }
        ]

    def test_records_call_pass_but_ignores_nonfailed_setup(
        self, tmp_path, monkeypatch
    ):
        report_path = tmp_path / "reports.jsonl"
        monkeypatch.setenv("BENCH_REPORT_PATH", str(report_path))

        report_plugin.pytest_runtest_logreport(
            _report("tests/test_example.py::test_ok", "setup", "passed")
        )
        report_plugin.pytest_runtest_logreport(
            _report("tests/test_example.py::test_ok", "call", "passed")
        )

        assert _report_entries(report_path) == [
            {
                "id": "tests/test_example.py::test_ok",
                "when": "call",
                "outcome": "passed",
            }
        ]

    def test_records_teardown_only_failure(self, tmp_path, monkeypatch):
        report_path = tmp_path / "reports.jsonl"
        monkeypatch.setenv("BENCH_REPORT_PATH", str(report_path))

        report_plugin.pytest_runtest_logreport(
            _report("tests/test_example.py::test_teardown", "teardown", "failed")
        )

        assert _report_entries(report_path) == [
            {
                "id": "tests/test_example.py::test_teardown",
                "when": "teardown",
                "outcome": "failed",
            }
        ]

    def test_failed_setup_is_recorded_and_deduped_from_teardown(
        self, tmp_path, monkeypatch
    ):
        report_path = tmp_path / "reports.jsonl"
        monkeypatch.setenv("BENCH_REPORT_PATH", str(report_path))
        nodeid = "tests/test_example.py::test_setup_failure"

        report_plugin.pytest_runtest_logreport(_report(nodeid, "setup", "failed"))
        report_plugin.pytest_runtest_logreport(
            _report(nodeid, "teardown", "failed")
        )

        assert _report_entries(report_path) == [
            {"id": nodeid, "when": "setup", "outcome": "failed"}
        ]

    def test_failure_phase_reports_persist_one_row_per_exact_nodeid(
        self, tmp_path, monkeypatch
    ):
        report_path = tmp_path / "reports.jsonl"
        monkeypatch.setenv("BENCH_REPORT_PATH", str(report_path))
        nodeid = "tests/test_example.py::test_x[a - b]"

        report_plugin.pytest_runtest_logreport(_report(nodeid, "call", "failed"))
        report_plugin.pytest_runtest_logreport(_report(nodeid, "teardown", "failed"))

        failure_entries = [
            entry
            for entry in _report_entries(report_path)
            if entry["outcome"] == "failed"
        ]
        assert failure_entries == [
            {"id": nodeid, "when": "call", "outcome": "failed"}
        ]

    def test_run_suite_uses_snapshot_before_conflicting_cwd_plugin(
        self, tmp_path, monkeypatch
    ):
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_nested_plugin.py"
        test_file.write_text(
            """
import os
import pytest


@pytest.mark.parametrize("value", [pytest.param("value", id="a - b")])
def test_parameterized(value):
    assert value == "different"


@pytest.fixture
def teardown_failure():
    yield
    raise RuntimeError("teardown failed")


def test_teardown_only(teardown_failure):
    assert teardown_failure is None


def test_safe_path_was_consumed_before_test_code():
    assert "PYTHONSAFEPATH" not in os.environ
""".lstrip()
        )
        canary = tmp_path / "cwd-plugin-executed"
        (tmp_path / "bench_report_plugin.py").write_text(
            "from pathlib import Path\n"
            f"Path({str(canary)!r}).write_text('executed')\n"
        )
        monkeypatch.chdir(tmp_path)
        expected_plugin_sha = baseline._plugin_sha256()

        status, failures, executed_plugin_sha = baseline._run_suite(
            expected_plugin_sha
        )

        assert status == 1
        assert failures == [
            "tests/test_nested_plugin.py::test_parameterized[a - b]",
            "tests/test_nested_plugin.py::test_teardown_only",
        ]
        assert executed_plugin_sha == expected_plugin_sha
        assert not canary.exists()

    def test_run_suite_clears_safe_path_before_model_config_child_import(
        self, monkeypatch
    ):
        monkeypatch.setattr(
            baseline,
            "SUITE_CMD",
            [
                "-B",
                "-m",
                "pytest",
                "tests/test_model_config.py::ImportSafety::"
                "test_module_imports_without_env",
                "-q",
            ],
        )
        expected_plugin_sha = baseline._plugin_sha256()

        status, failures, executed_plugin_sha = baseline._run_suite(
            expected_plugin_sha
        )

        assert status == 0
        assert failures == []
        assert executed_plugin_sha == expected_plugin_sha


class TestSuiteReportParsing:
    @pytest.mark.parametrize("status", [2, 3, 4, 5])
    def test_suite_error_status_never_writes_authority(
        self, status, secure_root, monkeypatch
    ):
        plugin_bytes = b"snapshot plugin bytes"
        plugin_sha = hashlib.sha256(plugin_bytes).hexdigest()
        monkeypatch.setattr(
            baseline,
            "_load_witness",
            lambda: {
                "stable": set(),
                "flaky": set(),
                "collected": 1,
                "base_commit": COMMIT,
                "plugin_sha256": plugin_sha,
            },
        )
        monkeypatch.setattr(baseline, "_read_plugin_bytes", lambda: plugin_bytes)
        monkeypatch.setattr(
            baseline.subprocess,
            "run",
            lambda *_args, **_kwargs: subprocess.CompletedProcess([], status, "", ""),
        )

        with pytest.raises(SystemExit, match=rf"suite_run_errored status={status}"):
            baseline.record()

        assert not secure_root.authority.exists()

    def test_status_one_without_parsed_failure_refuses(self, monkeypatch):
        monkeypatch.setattr(
            baseline.subprocess,
            "run",
            lambda *_args, **_kwargs: subprocess.CompletedProcess([], 1, "", ""),
        )

        with pytest.raises(SystemExit, match="failures_unparsed"):
            baseline._run_suite()

    def test_status_zero_with_phantom_failure_refuses(self, monkeypatch):
        def fake_run(args, **kwargs):
            report_path = Path(kwargs["env"]["BENCH_REPORT_PATH"])
            report_path.write_text(_report_jsonl({OLD_RED}))
            return subprocess.CompletedProcess(args, 0, "", "")

        monkeypatch.setattr(baseline.subprocess, "run", fake_run)

        with pytest.raises(SystemExit, match="failures_phantom"):
            baseline._run_suite()

    def test_suite_refuses_helper_drift_after_subprocess(self, monkeypatch):
        state = {"helper_sha256": HELPER_SHA}
        monkeypatch.setattr(
            baseline, "_STARTUP_HELPER_SHA256", HELPER_SHA, raising=False
        )
        monkeypatch.setattr(
            baseline,
            "_live_helper_sha256",
            lambda: state["helper_sha256"],
            raising=False,
        )

        def drift_during_suite(args, **_kwargs):
            state["helper_sha256"] = "c" * 64
            return subprocess.CompletedProcess(args, 0, "", "")

        monkeypatch.setattr(baseline.subprocess, "run", drift_during_suite)

        with pytest.raises(SystemExit, match="baseline_helper_drift"):
            baseline._run_suite()

    def test_collect_refuses_helper_drift_after_subprocess(self, monkeypatch):
        state = {"helper_sha256": HELPER_SHA}
        monkeypatch.setattr(
            baseline, "_STARTUP_HELPER_SHA256", HELPER_SHA, raising=False
        )
        monkeypatch.setattr(
            baseline,
            "_live_helper_sha256",
            lambda: state["helper_sha256"],
            raising=False,
        )

        def drift_during_collection(args, **_kwargs):
            state["helper_sha256"] = "c" * 64
            return subprocess.CompletedProcess(
                args, 0, "1 test collected in 0.01s\n", ""
            )

        monkeypatch.setattr(baseline.subprocess, "run", drift_during_collection)

        with pytest.raises(SystemExit, match="baseline_helper_drift"):
            baseline._collect_count()

    def test_exact_parameterized_failure_id_is_preserved_and_deduped(self, tmp_path):
        nodeid = "tests/test_example.py::test_x[a - b]"
        report_path = tmp_path / "report.jsonl"
        report_path.write_text(
            "".join(
                [
                    json.dumps(
                        {"id": nodeid, "when": "call", "outcome": "failed"}
                    )
                    + "\n",
                    json.dumps(
                        {"id": nodeid, "when": "teardown", "outcome": "failed"}
                    )
                    + "\n",
                ]
            )
        )

        assert baseline._failures_from_report(str(report_path), 1) == [nodeid]


class TestAuthorityValidation:
    @pytest.mark.parametrize(
        "case",
        [
            "missing_key",
            "extra_key",
            "wrong_schema",
            "negative_collected",
            "bool_collected",
            "invalid_status",
            "bool_status",
            "failures_string",
            "known_flaky_string",
            "status_zero_with_failures",
            "status_one_without_failures",
            "bad_base_commit",
            "bad_helper_hash",
            "bad_plugin_hash",
            "bad_rotated_from",
            "suite_cmd_not_list",
            "interpreter_not_string",
        ],
    )
    def test_malformed_authority_shapes_refuse(
        self, case, secure_root
    ):
        doc = _authority_doc()
        if case == "missing_key":
            doc.pop("schema")
        elif case == "extra_key":
            doc["extra"] = True
        elif case == "wrong_schema":
            doc["schema"] = "wrong"
        elif case == "negative_collected":
            doc["collected"] = -1
        elif case == "bool_collected":
            doc["collected"] = False
        elif case == "invalid_status":
            doc["pytest_status"] = 7
        elif case == "bool_status":
            doc["pytest_status"] = True
        elif case == "failures_string":
            doc["failures"] = OLD_RED
        elif case == "known_flaky_string":
            doc["known_flaky"] = D09
        elif case == "status_zero_with_failures":
            doc["pytest_status"] = 0
        elif case == "status_one_without_failures":
            doc["failures"] = []
        elif case == "bad_base_commit":
            doc["base_commit"] = "A" * 40
        elif case == "bad_helper_hash":
            doc["helper_sha256"] = "A" * 64
        elif case == "bad_plugin_hash":
            doc["plugin_sha256"] = "B" * 64
        elif case == "bad_rotated_from":
            doc["rotated_from"] = "not-a-hash"
        elif case == "suite_cmd_not_list":
            doc["suite_cmd"] = "pytest"
        elif case == "interpreter_not_string":
            doc["interpreter"] = 7
        _write_authority(doc)

        with pytest.raises(SystemExit, match="baseline_schema_mismatch"):
            baseline._open_authority()

    def test_malformed_json_refuses_as_schema_mismatch(self, secure_root):
        _write_private(secure_root.authority, "{not-json")

        with pytest.raises(SystemExit, match="baseline_schema_mismatch"):
            baseline._open_authority()

    @pytest.mark.parametrize("field", ["interpreter", "suite_cmd"])
    def test_command_or_interpreter_drift_refuses(self, field, secure_root):
        doc = _authority_doc()
        doc[field] = "/different/python" if field == "interpreter" else ["different"]
        _write_authority(doc)

        with pytest.raises(SystemExit, match="baseline_command_mismatch"):
            baseline._open_authority()

    @pytest.mark.parametrize("field", ["helper_sha256", "plugin_sha256"])
    def test_helper_or_plugin_drift_refuses(self, field, secure_root):
        doc = _authority_doc()
        doc[field] = "c" * 64
        _write_authority(doc)

        with pytest.raises(SystemExit, match="baseline_helper_drift"):
            baseline._open_authority()

    def test_nonancestor_authority_refuses(
        self, secure_root, monkeypatch
    ):
        _write_authority()
        monkeypatch.setattr(baseline, "_is_ancestor", lambda _old, _new="HEAD": False)

        with pytest.raises(SystemExit, match="baseline_not_ancestor"):
            baseline._open_authority()

    def test_skip_helper_check_still_binds_plugin(self, secure_root):
        doc = _authority_doc(helper_sha256="c" * 64, plugin_sha256="d" * 64)
        _write_authority(doc)

        with pytest.raises(SystemExit, match="baseline_helper_drift"):
            baseline._open_authority(skip_helper_check=True)

    def test_skip_helper_check_never_skips_current_helper_stability(
        self, secure_root, monkeypatch
    ):
        _write_authority(_authority_doc(helper_sha256="c" * 64))
        monkeypatch.setattr(
            baseline, "_live_helper_sha256", lambda: "d" * 64, raising=False
        )

        with pytest.raises(SystemExit, match="baseline_helper_drift"):
            baseline._open_authority(skip_helper_check=True)


class TestAnchoredFilesystem:
    def test_final_component_symlink_refuses(self, secure_root):
        target = secure_root.root / "target"
        _write_private(target, "payload")
        link = secure_root.root / "link"
        link.symlink_to(target)

        with pytest.raises(SystemExit, match="baseline_filesystem_hazard"):
            baseline._anchored_read_bytes(str(link))

    def test_parent_component_symlink_refuses(self, secure_root):
        real_parent = secure_root.root / "real-parent"
        real_parent.mkdir(mode=0o700)
        _write_private(real_parent / "payload", "data")
        alias = secure_root.root / "alias"
        alias.symlink_to(real_parent, target_is_directory=True)

        with pytest.raises(SystemExit, match="baseline_filesystem_hazard"):
            baseline._anchored_read_bytes(str(alias / "payload"))

    def test_hardlink_refuses(self, secure_root):
        original = secure_root.root / "original"
        linked = secure_root.root / "linked"
        _write_private(original, "data")
        os.link(original, linked)

        with pytest.raises(SystemExit, match="baseline_filesystem_hazard"):
            baseline._anchored_read_bytes(str(linked))

    def test_world_readable_file_refuses(self, secure_root):
        path = secure_root.root / "payload"
        _write_private(path, "data")
        path.chmod(0o644)

        with pytest.raises(SystemExit, match="baseline_filesystem_hazard"):
            baseline._anchored_read_bytes(str(path))

    def test_create_fsyncs_then_validates_then_publishes_then_fsyncs_directory(
        self, secure_root, monkeypatch
    ):
        events = []
        real_fsync = os.fsync
        real_link = os.link

        def ordered_fsync(fd):
            info = os.fstat(fd)
            events.append("file" if stat.S_ISREG(info.st_mode) else "directory")
            real_fsync(fd)

        def ordered_link(*args, **kwargs):
            events.append("publish")
            return real_link(*args, **kwargs)

        monkeypatch.setattr(baseline.os, "fsync", ordered_fsync)
        monkeypatch.setattr(baseline.os, "link", ordered_link)

        baseline._anchored_create_json(
            str(secure_root.authority),
            _authority_doc(),
            pre_publish=lambda: events.append("pre_publish"),
        )

        assert events == ["file", "pre_publish", "publish", "directory"]

    def test_replace_fsyncs_then_validates_then_replaces_then_fsyncs_directory(
        self, secure_root, monkeypatch
    ):
        _write_authority()
        events = []
        real_fsync = os.fsync
        real_replace = os.replace

        def ordered_fsync(fd):
            info = os.fstat(fd)
            events.append("file" if stat.S_ISREG(info.st_mode) else "directory")
            real_fsync(fd)

        def ordered_replace(*args, **kwargs):
            events.append("replace")
            return real_replace(*args, **kwargs)

        monkeypatch.setattr(baseline.os, "fsync", ordered_fsync)
        monkeypatch.setattr(baseline.os, "replace", ordered_replace)

        baseline._anchored_replace_json(
            str(secure_root.authority),
            _authority_doc(collected=101),
            pre_publish=lambda: events.append("pre_publish"),
        )

        assert events == ["file", "pre_publish", "replace", "directory"]

    def test_foreign_uid_simulation_refuses(
        self, secure_root, monkeypatch
    ):
        path = secure_root.root / "payload"
        _write_private(path, "data")
        real_fstat = baseline.os.fstat

        def foreign_file(fd):
            info = real_fstat(fd)
            if stat.S_ISREG(info.st_mode):
                fields = list(info)
                fields[4] = os.geteuid() + 1
                return os.stat_result(fields)
            return info

        monkeypatch.setattr(baseline.os, "fstat", foreign_file)

        with pytest.raises(SystemExit, match="baseline_filesystem_hazard"):
            baseline._anchored_read_bytes(str(path))


class TestWitnessLoading:
    def test_tampered_payload_refuses(self, secure_root):
        witness = _seal_witness()
        _write_private(witness / "run1.txt", "tampered\n")

        with pytest.raises(SystemExit, match="witness_hash_mismatch"):
            baseline._load_witness()

    @pytest.mark.parametrize("status", [2, 3, 4, 5])
    def test_invalid_witness_status_refuses(self, status, secure_root):
        _seal_witness(statuses=(status, 1))

        with pytest.raises(SystemExit, match="witness_status_invalid"):
            baseline._load_witness()

    @pytest.mark.parametrize("status", [2, 3, 4, 5])
    def test_invalid_collection_status_refuses(self, status, secure_root):
        _seal_witness(collect_status=status)

        with pytest.raises(SystemExit, match="witness_status_invalid"):
            baseline._load_witness()

    def test_collection_status_one_is_accepted_when_count_is_parseable(
        self, secure_root
    ):
        _seal_witness(collect_status=1, collected=100)

        loaded = baseline._load_witness()

        assert loaded["collect_status"] == 1
        assert loaded["collected"] == 100

    def test_wrong_witness_toplevel_refuses(self, secure_root):
        _seal_witness(meta_overrides={"cwd": "/wrong/worktree"})

        with pytest.raises(SystemExit, match="witness_toplevel_mismatch"):
            baseline._load_witness()

    def test_nonancestor_witness_base_refuses(
        self, secure_root, monkeypatch
    ):
        _seal_witness()
        monkeypatch.setattr(baseline, "_is_ancestor", lambda _old, _new="HEAD": False)

        with pytest.raises(SystemExit, match="baseline_not_ancestor"):
            baseline._load_witness()

    @pytest.mark.parametrize("case", ["extra_file", "missing_file", "missing_hash"])
    def test_exact_witness_file_and_hash_sets_are_required(
        self, case, secure_root
    ):
        witness = _seal_witness(omit_hash="run1.txt" if case == "missing_hash" else None)
        if case == "extra_file":
            _write_private(witness / "extra.txt", "extra")
        elif case == "missing_file":
            (witness / "run1.txt").unlink()

        with pytest.raises(SystemExit, match="witness_file_set_mismatch"):
            baseline._load_witness()

    @pytest.mark.parametrize(
        ("case", "expected"),
        [
            ("suite_argv", "witness_meta_invalid"),
            ("suite_env", "witness_meta_invalid"),
            ("collection_argv", "witness_meta_invalid"),
            ("collection_env", "witness_meta_invalid"),
            ("plugin_hash", "baseline_helper_drift"),
            ("malformed_json", "witness_meta_invalid"),
            ("extra_key", "witness_meta_invalid"),
            ("missing_key", "witness_meta_invalid"),
            ("wrong_top_shape", "witness_meta_invalid"),
            ("bad_field_shape", "witness_meta_invalid"),
        ],
    )
    def test_witness_metadata_is_exact_and_joined(
        self, case, expected, secure_root
    ):
        meta = json.loads(json.dumps(_witness_meta()))
        if case == "suite_argv":
            meta["suite_runs"][0]["argv"].append("--different")
        elif case == "suite_env":
            meta["suite_runs"][1]["env"]["PYTHONPATH"] = "wrong"
        elif case == "collection_argv":
            meta["collection"]["argv"].append("--different")
        elif case == "collection_env":
            meta["collection"]["env"]["PYTHONPATH"] = "scripts/dev"
        elif case == "plugin_hash":
            meta["plugin_sha256"] = "c" * 64
        elif case == "malformed_json":
            _seal_witness(meta_raw="{not-json")
        elif case == "extra_key":
            meta["extra"] = True
        elif case == "missing_key":
            meta.pop("cwd")
        elif case == "wrong_top_shape":
            _seal_witness(meta_document=[])
        elif case == "bad_field_shape":
            meta["base_commit"] = False
        if case not in {"malformed_json", "wrong_top_shape"}:
            _seal_witness(meta_document=meta)

        with pytest.raises(SystemExit, match=expected):
            baseline._load_witness()

    def test_manifest_flaky_is_closed_to_approved_d09(self, secure_root):
        injected = "tests/test_other.py::test_injected_flake"
        _seal_witness(manifest={D09, injected})

        with pytest.raises(SystemExit, match="witness_manifest_invalid"):
            baseline._load_witness()

    @pytest.mark.parametrize("location", ["root", "witness", "intermediate"])
    @pytest.mark.parametrize("hazard", ["mode", "owner"])
    def test_directory_owner_and_mode_hazards_refuse_load(
        self, location, hazard, secure_root, monkeypatch
    ):
        intermediate = secure_root.root / "sealed"
        if location == "intermediate":
            intermediate.mkdir(mode=0o700)
            monkeypatch.setattr(
                baseline,
                "WITNESS_DIR",
                str(intermediate / "bootstrap-witness"),
            )
        witness = _seal_witness()
        target = {
            "root": secure_root.root,
            "witness": witness,
            "intermediate": intermediate,
        }[location]
        if hazard == "mode":
            target.chmod(0o755)
        else:
            target_info = target.stat()
            real_fstat = baseline.os.fstat

            def foreign_directory(fd):
                info = real_fstat(fd)
                if (
                    stat.S_ISDIR(info.st_mode)
                    and info.st_dev == target_info.st_dev
                    and info.st_ino == target_info.st_ino
                ):
                    fields = list(info)
                    fields[4] = os.geteuid() + 1
                    return os.stat_result(fields)
                return info

            monkeypatch.setattr(baseline.os, "fstat", foreign_directory)

        with pytest.raises(SystemExit, match="baseline_filesystem_hazard"):
            baseline._load_witness()

    def test_witness_enumeration_uses_directory_descriptor(
        self, secure_root, monkeypatch
    ):
        _seal_witness()
        real_listdir = baseline.os.listdir
        calls = []

        def descriptor_listdir(path):
            calls.append(path)
            assert isinstance(path, int)
            return real_listdir(path)

        monkeypatch.setattr(baseline.os, "listdir", descriptor_listdir)

        baseline._load_witness()

        assert len(calls) == 1

    def test_witness_reports_parse_from_anchored_bytes_without_raw_reopen(
        self, secure_root, monkeypatch
    ):
        _seal_witness()
        real_open = builtins.open

        def guarded_open(file, *args, **kwargs):
            if isinstance(file, (str, os.PathLike)) and os.fspath(file).startswith(
                str(secure_root.witness)
            ):
                raise AssertionError("raw witness reopen")
            return real_open(file, *args, **kwargs)

        monkeypatch.setattr(builtins, "open", guarded_open)

        loaded = baseline._load_witness()

        assert loaded["stable"] == {OLD_RED}
        assert loaded["flaky"] == {D09}


class TestRecord:
    def test_record_refuses_witness_from_unequal_ancestor(
        self, secure_root, monkeypatch
    ):
        older_commit = "2" * 40
        _seal_witness(meta_overrides={"base_commit": older_commit})
        events: list[str] = []
        real_load_witness = baseline._load_witness

        def tracked_head() -> str:
            events.append("head")
            return COMMIT

        def tracked_load_witness():
            events.append("load_witness")
            return real_load_witness()

        def forbidden_suite(*_args, **_kwargs):
            events.append("suite")
            raise AssertionError("suite must not run for a mismatched witness")

        monkeypatch.setattr(baseline, "_head_commit", tracked_head)
        monkeypatch.setattr(baseline, "_load_witness", tracked_load_witness)
        monkeypatch.setattr(baseline, "_run_suite", forbidden_suite)
        monkeypatch.setattr(baseline, "_collect_count", lambda: 100)

        with pytest.raises(SystemExit, match="^witness_head_mismatch$"):
            baseline.record()

        assert events == ["head", "load_witness"]
        assert not secure_root.authority.exists()

    def test_head_change_during_long_record_refuses_before_write(
        self, secure_root, monkeypatch
    ):
        _seal_witness()
        heads = iter([COMMIT, "2" * 40])
        monkeypatch.setattr(baseline, "_head_commit", lambda: next(heads))
        monkeypatch.setattr(baseline, "_run_suite", _stub_suite(1, [OLD_RED]))
        monkeypatch.setattr(baseline, "_collect_count", lambda: 100)

        with pytest.raises(SystemExit, match="^record_head_drift$"):
            baseline.record()

        assert not secure_root.authority.exists()

    def test_precode_intersection_and_manifest_define_flake_authority(
        self, secure_root, monkeypatch
    ):
        intermittent = "tests/test_existing.py::test_intermittent"
        _seal_witness(
            run1={OLD_RED, intermittent},
            run2={OLD_RED},
            manifest={D09},
        )
        monkeypatch.setattr(baseline, "_run_suite", _stub_suite(1, [OLD_RED]))
        monkeypatch.setattr(baseline, "_collect_count", lambda: 101)

        baseline.record()

        doc = json.loads(secure_root.authority.read_text())
        assert doc["pytest_status"] == 1
        assert doc["failures"] == [OLD_RED]
        assert doc["known_flaky"] == sorted([D09, intermittent])
        assert doc["collected"] == 101
        assert doc["base_commit"] == COMMIT
        assert stat.S_IMODE(secure_root.authority.stat().st_mode) == 0o600

    def test_status_zero_can_carry_green_known_flaky_manifest(
        self, secure_root, monkeypatch
    ):
        _seal_witness(
            run1=set(),
            run2=set(),
            statuses=(0, 0),
            manifest={D09},
        )
        monkeypatch.setattr(baseline, "_run_suite", _stub_suite(0, []))
        monkeypatch.setattr(baseline, "_collect_count", lambda: 100)

        baseline.record()

        doc = baseline._open_authority()
        assert doc["pytest_status"] == 0
        assert doc["failures"] == []
        assert doc["known_flaky"] == [D09]

    def test_stable_witness_failure_remains_authoritative_if_verification_greens(
        self, secure_root, monkeypatch
    ):
        _seal_witness(run1={OLD_RED}, run2={OLD_RED})
        monkeypatch.setattr(baseline, "_run_suite", _stub_suite(0, []))
        monkeypatch.setattr(baseline, "_collect_count", lambda: 100)

        baseline.record()

        doc = json.loads(secure_root.authority.read_text())
        assert doc["pytest_status"] == 1
        assert doc["failures"] == [OLD_RED]

    def test_new_record_only_intermittent_refuses_without_authority(
        self, secure_root, monkeypatch
    ):
        new_red = "tests/test_new.py::test_intermittent"
        _seal_witness()
        monkeypatch.setattr(
            baseline, "_run_suite", _stub_suite(1, [OLD_RED, new_red])
        )

        with pytest.raises(SystemExit, match=rf"record_unstable.*{new_red}"):
            baseline.record()

        assert not secure_root.authority.exists()

    def test_collection_shrink_refuses_before_authority_write(
        self, secure_root, monkeypatch
    ):
        _seal_witness(collected=100)
        monkeypatch.setattr(baseline, "_run_suite", _stub_suite(1, [OLD_RED]))
        monkeypatch.setattr(baseline, "_collect_count", lambda: 99)

        with pytest.raises(SystemExit, match="collection_count_dropped"):
            baseline.record()

        assert not secure_root.authority.exists()

    def test_second_record_uses_exclusive_create(
        self, secure_root, monkeypatch
    ):
        _seal_witness()
        monkeypatch.setattr(baseline, "_run_suite", _stub_suite(1, [OLD_RED]))
        monkeypatch.setattr(baseline, "_collect_count", lambda: 100)
        baseline.record()

        with pytest.raises(FileExistsError):
            baseline.record()

    def test_record_binds_hash_of_executed_plugin_snapshot(
        self, secure_root, monkeypatch
    ):
        executed_plugin_sha = "c" * 64
        monkeypatch.setattr(
            baseline,
            "_load_witness",
            lambda: {
                "stable": {OLD_RED},
                "flaky": {D09},
                "collected": 100,
                "base_commit": COMMIT,
                "plugin_sha256": executed_plugin_sha,
            },
        )
        monkeypatch.setattr(
            baseline,
            "_run_suite",
            _stub_suite(1, [OLD_RED], executed_plugin_sha),
        )
        monkeypatch.setattr(baseline, "_collect_count", lambda: 100)

        baseline.record()

        doc = json.loads(secure_root.authority.read_text())
        assert doc["plugin_sha256"] == executed_plugin_sha

    def test_helper_drift_during_suite_refuses_before_authority_write(
        self, secure_root, monkeypatch
    ):
        state = {"helper_sha256": HELPER_SHA}
        _seal_witness()
        monkeypatch.setattr(
            baseline,
            "_live_helper_sha256",
            lambda: state["helper_sha256"],
            raising=False,
        )

        def drift_during_suite(expected_plugin_sha256=None):
            assert expected_plugin_sha256 == PLUGIN_SHA
            state["helper_sha256"] = "c" * 64
            return 1, [OLD_RED], PLUGIN_SHA

        monkeypatch.setattr(baseline, "_run_suite", drift_during_suite)
        monkeypatch.setattr(baseline, "_collect_count", lambda: 100)

        with pytest.raises(SystemExit, match="baseline_helper_drift"):
            baseline.record()

        assert not secure_root.authority.exists()

    @pytest.mark.parametrize(
        ("drift", "refusal"),
        [
            pytest.param("helper", "baseline_helper_drift", id="helper"),
            pytest.param("head", "record_head_drift", id="head"),
        ],
    )
    def test_record_drift_during_staging_fsync_refuses_before_publication(
        self, drift, refusal, secure_root, monkeypatch
    ):
        _seal_witness()
        state = {"helper_sha256": HELPER_SHA, "head": COMMIT}
        monkeypatch.setattr(
            baseline,
            "_live_helper_sha256",
            lambda: state["helper_sha256"],
            raising=False,
        )
        monkeypatch.setattr(baseline, "_head_commit", lambda: state["head"])
        monkeypatch.setattr(baseline, "_run_suite", _stub_suite(1, [OLD_RED]))
        monkeypatch.setattr(baseline, "_collect_count", lambda: 100)
        real_fsync = os.fsync

        def drift_after_file_fsync(fd):
            info = os.fstat(fd)
            real_fsync(fd)
            if stat.S_ISREG(info.st_mode):
                if drift == "helper":
                    state["helper_sha256"] = "d" * 64
                else:
                    state["head"] = "2" * 40

        monkeypatch.setattr(baseline.os, "fsync", drift_after_file_fsync)

        with pytest.raises(SystemExit, match=rf"^{refusal}$"):
            baseline.record()

        assert not secure_root.authority.exists()


class TestReconcile:
    def test_unchanged_red_passes(self, secure_root, monkeypatch):
        _write_authority()
        monkeypatch.setattr(baseline, "_run_suite", _stub_suite(1, [OLD_RED]))
        monkeypatch.setattr(baseline, "_collect_count", lambda: 100)

        baseline.reconcile()

    def test_known_flaky_red_passes(self, secure_root, monkeypatch):
        _write_authority(_authority_doc(pytest_status=0, failures=[]))
        monkeypatch.setattr(baseline, "_run_suite", _stub_suite(1, [D09]))
        monkeypatch.setattr(baseline, "_collect_count", lambda: 100)

        baseline.reconcile()

    def test_new_red_refuses_and_names_exact_id(
        self, secure_root, monkeypatch
    ):
        new_red = "tests/test_new.py::test_x[a - b]"
        _write_authority()
        monkeypatch.setattr(
            baseline, "_run_suite", _stub_suite(1, [OLD_RED, new_red])
        )
        monkeypatch.setattr(baseline, "_collect_count", lambda: 100)

        with pytest.raises(SystemExit, match=rf"new_red.*{re.escape(new_red)}"):
            baseline.reconcile()

    def test_collection_count_drop_refuses(
        self, secure_root, monkeypatch
    ):
        _write_authority()
        monkeypatch.setattr(baseline, "_run_suite", _stub_suite(1, [OLD_RED]))
        monkeypatch.setattr(baseline, "_collect_count", lambda: 99)

        with pytest.raises(SystemExit, match="collection_count_dropped"):
            baseline.reconcile()

    def test_plugin_swap_after_authority_validation_never_executes(
        self, secure_root, monkeypatch
    ):
        authorized = b"authorized plugin bytes"
        unauthorized = b"unauthorized replacement"
        authorized_sha = hashlib.sha256(authorized).hexdigest()
        _write_authority(_authority_doc(plugin_sha256=authorized_sha))
        monkeypatch.setattr(baseline, "_plugin_sha256", lambda: authorized_sha)
        monkeypatch.setattr(
            baseline, "_read_plugin_bytes", lambda: unauthorized, raising=False
        )
        launched = []

        def must_not_launch(*args, **kwargs):
            launched.append((args, kwargs))
            return subprocess.CompletedProcess(args[0], 0, "", "")

        monkeypatch.setattr(baseline.subprocess, "run", must_not_launch)

        with pytest.raises(SystemExit, match="baseline_helper_drift"):
            baseline.reconcile()

        assert launched == []

    def test_helper_drift_during_collection_refuses_reconcile(
        self, secure_root, monkeypatch
    ):
        state = {"helper_sha256": HELPER_SHA}
        _write_authority()
        monkeypatch.setattr(
            baseline,
            "_live_helper_sha256",
            lambda: state["helper_sha256"],
            raising=False,
        )
        monkeypatch.setattr(baseline, "_run_suite", _stub_suite(1, [OLD_RED]))

        def drift_during_collection():
            state["helper_sha256"] = "c" * 64
            return 100

        monkeypatch.setattr(baseline, "_collect_count", drift_during_collection)

        with pytest.raises(SystemExit, match="baseline_helper_drift"):
            baseline.reconcile()


class TestBootstrapCheck:
    def test_matching_authority_and_witness_pass(self, secure_root):
        intermittent = "tests/test_existing.py::test_intermittent"
        _seal_witness(
            run1={OLD_RED, intermittent},
            run2={OLD_RED},
            manifest={D09},
        )
        _write_authority(
            _authority_doc(known_flaky=sorted([D09, intermittent]), collected=101)
        )

        baseline.bootstrap_check()

    def test_unexplained_drift_refuses(self, secure_root):
        new_red = "tests/test_new.py::test_red"
        _seal_witness()
        _write_authority(_authority_doc(failures=[OLD_RED, new_red]))

        with pytest.raises(SystemExit, match=rf"bootstrap_drift.*{new_red}"):
            baseline.bootstrap_check()

    def test_omitted_stable_witness_id_refuses(self, secure_root):
        omitted = "tests/test_existing.py::test_second_stable_red"
        _seal_witness(run1={OLD_RED, omitted}, run2={OLD_RED, omitted})
        _write_authority(_authority_doc(failures=[OLD_RED]))

        with pytest.raises(
            SystemExit, match=rf"bootstrap_drift.*{omitted}"
        ):
            baseline.bootstrap_check()

    def test_failing_helper_test_has_no_exemption(self, secure_root):
        helper_red = "tests/test_bench_baseline.py::test_helper_is_broken"
        _seal_witness()
        _write_authority(_authority_doc(failures=[OLD_RED, helper_red]))

        with pytest.raises(SystemExit, match=rf"bootstrap_drift.*{helper_red}"):
            baseline.bootstrap_check()

    def test_known_flaky_set_must_come_from_witness(self, secure_root):
        injected = "tests/test_other.py::test_injected_flake"
        _seal_witness()
        _write_authority(_authority_doc(known_flaky=[D09, injected]))

        with pytest.raises(SystemExit, match="bootstrap_drift"):
            baseline.bootstrap_check()

    def test_collection_floor_refuses(self, secure_root):
        _seal_witness(collected=100)
        _write_authority(_authority_doc(collected=99))

        with pytest.raises(SystemExit, match="collection_count_dropped"):
            baseline.bootstrap_check()


def _install_rotation_git(
    monkeypatch,
    secure_root,
    grant: dict[str, object],
    old_helper_bytes: bytes,
    *,
    intro_present: bool = True,
    head_grant_bytes: bytes | None = None,
) -> Path:
    grant_path = secure_root.repo / "docs" / "rotation-grant.json"
    grant_bytes = json.dumps(grant, sort_keys=True).encode()
    head_grant_bytes = grant_bytes if head_grant_bytes is None else head_grant_bytes

    def git_capture(args):
        if args == [
            "rev-list",
            "--reverse",
            "HEAD",
            "--",
            "docs/rotation-grant.json",
        ]:
            return b"intro-commit\n" if intro_present else b""
        if args == ["show", "intro-commit:docs/rotation-grant.json"]:
            return grant_bytes
        if args == ["show", "HEAD:docs/rotation-grant.json"]:
            return head_grant_bytes
        if args == ["show", "intro-commit:scripts/dev/bench_baseline.py"]:
            return old_helper_bytes
        raise AssertionError(f"unexpected git command: {args}")

    monkeypatch.setattr(baseline, "_git_capture", git_capture)
    return grant_path


def _rotation_case(secure_root, monkeypatch):
    old_helper_bytes = b"old helper bytes\n"
    old_helper_sha = hashlib.sha256(old_helper_bytes).hexdigest()
    doc = _authority_doc(helper_sha256=old_helper_sha)
    _write_authority(doc)
    old_authority_sha = hashlib.sha256(secure_root.authority.read_bytes()).hexdigest()
    grant = {
        "old_helper_sha256": old_helper_sha,
        "old_authority_sha256": old_authority_sha,
        "reason": "approved baseline helper edit",
    }
    grant_path = _install_rotation_git(
        monkeypatch, secure_root, grant, old_helper_bytes
    )
    current_helper_sha = "c" * 64
    monkeypatch.setattr(
        baseline,
        "_STARTUP_HELPER_SHA256",
        current_helper_sha,
        raising=False,
    )
    monkeypatch.setattr(
        baseline,
        "_live_helper_sha256",
        lambda: current_helper_sha,
        raising=False,
    )
    monkeypatch.setattr(baseline, "_self_sha256", lambda: current_helper_sha)
    return SimpleNamespace(
        grant=grant,
        grant_path=grant_path,
        old_helper_bytes=old_helper_bytes,
        old_authority_sha=old_authority_sha,
        current_helper_sha=current_helper_sha,
    )


class TestRotate:
    def test_valid_rotation_records_parent_and_current_plugin(
        self, secure_root, monkeypatch
    ):
        case = _rotation_case(secure_root, monkeypatch)
        monkeypatch.setattr(baseline, "_run_suite", _stub_suite(1, [OLD_RED]))
        monkeypatch.setattr(baseline, "_collect_count", lambda: 101)

        baseline.rotate(str(case.grant_path))

        rotated = json.loads(secure_root.authority.read_text())
        assert rotated["rotated_from"] == case.old_authority_sha
        assert rotated["helper_sha256"] == case.current_helper_sha
        assert rotated["plugin_sha256"] == PLUGIN_SHA
        assert rotated["failures"] == [OLD_RED]
        assert rotated["collected"] == 101
        assert stat.S_IMODE(secure_root.authority.stat().st_mode) == 0o600

    @pytest.mark.parametrize(
        "case", ["uncommitted", "grant_changed", "old_helper_mismatch", "authority_mismatch"]
    )
    def test_invalid_rotation_authorization_refuses(
        self, case, secure_root, monkeypatch
    ):
        rotation = _rotation_case(secure_root, monkeypatch)
        if case == "uncommitted":
            _install_rotation_git(
                monkeypatch,
                secure_root,
                rotation.grant,
                rotation.old_helper_bytes,
                intro_present=False,
            )
        elif case == "grant_changed":
            _install_rotation_git(
                monkeypatch,
                secure_root,
                rotation.grant,
                rotation.old_helper_bytes,
                head_grant_bytes=b"changed",
            )
        elif case == "old_helper_mismatch":
            _install_rotation_git(
                monkeypatch,
                secure_root,
                rotation.grant,
                b"different old helper",
            )
        elif case == "authority_mismatch":
            bad_grant = dict(rotation.grant)
            bad_grant["old_authority_sha256"] = "d" * 64
            _install_rotation_git(
                monkeypatch,
                secure_root,
                bad_grant,
                rotation.old_helper_bytes,
            )

        with pytest.raises(SystemExit, match="rotation_unauthorized"):
            baseline.rotate(str(rotation.grant_path))

    def test_new_red_blocks_rotation(self, secure_root, monkeypatch):
        case = _rotation_case(secure_root, monkeypatch)
        new_red = "tests/test_new.py::test_red"
        monkeypatch.setattr(
            baseline, "_run_suite", _stub_suite(1, [OLD_RED, new_red])
        )

        with pytest.raises(
            SystemExit, match=rf"rotate_blocked_new_red.*{new_red}"
        ):
            baseline.rotate(str(case.grant_path))

    def test_collection_shrink_blocks_rotation(
        self, secure_root, monkeypatch
    ):
        case = _rotation_case(secure_root, monkeypatch)
        monkeypatch.setattr(baseline, "_run_suite", _stub_suite(1, [OLD_RED]))
        monkeypatch.setattr(baseline, "_collect_count", lambda: 99)

        with pytest.raises(SystemExit, match="collection_count_dropped"):
            baseline.rotate(str(case.grant_path))

    def test_helper_drift_during_suite_refuses_before_rotation_replace(
        self, secure_root, monkeypatch
    ):
        case = _rotation_case(secure_root, monkeypatch)
        state = {"helper_sha256": case.current_helper_sha}
        monkeypatch.setattr(
            baseline,
            "_live_helper_sha256",
            lambda: state["helper_sha256"],
            raising=False,
        )

        def drift_during_suite(expected_plugin_sha256=None):
            assert expected_plugin_sha256 == PLUGIN_SHA
            state["helper_sha256"] = "d" * 64
            return 1, [OLD_RED], PLUGIN_SHA

        monkeypatch.setattr(baseline, "_run_suite", drift_during_suite)
        monkeypatch.setattr(baseline, "_collect_count", lambda: 101)
        before = secure_root.authority.read_bytes()

        with pytest.raises(SystemExit, match="baseline_helper_drift"):
            baseline.rotate(str(case.grant_path))

        assert secure_root.authority.read_bytes() == before

    @pytest.mark.parametrize(
        ("drift", "refusal"),
        [
            pytest.param("helper", "baseline_helper_drift", id="helper"),
            pytest.param("head", "rotation_head_drift", id="head"),
        ],
    )
    def test_rotation_drift_during_staging_fsync_preserves_old_authority(
        self, drift, refusal, secure_root, monkeypatch
    ):
        case = _rotation_case(secure_root, monkeypatch)
        state = {"helper_sha256": case.current_helper_sha, "head": COMMIT}
        monkeypatch.setattr(
            baseline,
            "_live_helper_sha256",
            lambda: state["helper_sha256"],
            raising=False,
        )
        monkeypatch.setattr(baseline, "_head_commit", lambda: state["head"])
        monkeypatch.setattr(baseline, "_run_suite", _stub_suite(1, [OLD_RED]))
        monkeypatch.setattr(baseline, "_collect_count", lambda: 101)
        real_fsync = os.fsync

        def drift_after_file_fsync(fd):
            info = os.fstat(fd)
            real_fsync(fd)
            if stat.S_ISREG(info.st_mode):
                if drift == "helper":
                    state["helper_sha256"] = "d" * 64
                else:
                    state["head"] = "2" * 40

        monkeypatch.setattr(baseline.os, "fsync", drift_after_file_fsync)
        before = secure_root.authority.read_bytes()

        with pytest.raises(SystemExit, match=rf"^{refusal}$"):
            baseline.rotate(str(case.grant_path))

        assert secure_root.authority.read_bytes() == before

    def test_rotation_never_pairs_parsed_authority_with_second_read(
        self, secure_root, monkeypatch
    ):
        old_helper_bytes = b"old helper bytes\n"
        old_helper_sha = hashlib.sha256(old_helper_bytes).hexdigest()
        authority_a = _authority_doc(helper_sha256=old_helper_sha, collected=100)
        authority_b = _authority_doc(helper_sha256=old_helper_sha, collected=101)
        raw_a = (json.dumps(authority_a, indent=1) + "\n").encode()
        raw_b = (json.dumps(authority_b, indent=1) + "\n").encode()
        _write_private(secure_root.authority, raw_a)
        grant = {
            "old_helper_sha256": old_helper_sha,
            "old_authority_sha256": hashlib.sha256(raw_b).hexdigest(),
            "reason": "approved baseline helper edit",
        }
        grant_path = _install_rotation_git(
            monkeypatch, secure_root, grant, old_helper_bytes
        )
        monkeypatch.setattr(
            baseline, "_STARTUP_HELPER_SHA256", "c" * 64, raising=False
        )
        monkeypatch.setattr(
            baseline, "_live_helper_sha256", lambda: "c" * 64, raising=False
        )
        monkeypatch.setattr(baseline, "_self_sha256", lambda: "c" * 64)
        reads = iter([raw_a, raw_b])
        read_count = []

        def sequential_authorities(_path):
            read_count.append(True)
            return next(reads)

        monkeypatch.setattr(baseline, "_anchored_read_bytes", sequential_authorities)
        monkeypatch.setattr(baseline, "_run_suite", _stub_suite(1, [OLD_RED]))
        monkeypatch.setattr(baseline, "_collect_count", lambda: 101)

        with pytest.raises(SystemExit, match="rotation_unauthorized"):
            baseline.rotate(str(grant_path))

        assert len(read_count) == 1
