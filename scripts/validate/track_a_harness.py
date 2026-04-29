#!/usr/bin/env python3
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Track A preflight harness.

This is the parent harness for the current Track A acceptance window. It
does not replace the specialized suites; it composes the minimum
offline checks that should be green before a live/runtime change:

1. Unit test suite.
2. Lived-memory probe score.
3. Voice-LoRA dataset extraction health.
4. Reproducibility / git cleanliness.
5. Optional live service health checks.

The dataset count is advisory until enough organic chat exists. The
unit suite and lived-memory probes are hard gates.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
DEFAULT_REPORT_DIR = REPO_ROOT / "logs" / "harness"
DEFAULT_DATASET_OUT = REPO_ROOT / "training" / "datasets" / "track_a_harness_latest.jsonl"
DEFAULT_REQUIRED_SERVICES = "maez.service,llama-server.service"
DEFAULT_ADVISORY_SERVICES = "maez-web.service,maez-subscription-proxy.service"


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str
    elapsed_s: float
    required: bool = True


def _run_command(cmd: list[str], *, timeout: int | None = None) -> tuple[int, str, str, float]:
    start = time.time()
    proc = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr, time.time() - start


def _count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open() as fh:
        return sum(1 for line in fh if line.strip())


def _status_from_score(score: float, threshold: float) -> str:
    return "PASS" if score >= threshold else "FAIL"


def check_unit_tests(*, skip: bool = False) -> CheckResult:
    if skip:
        return CheckResult(
            name="unit_tests",
            status="SKIP",
            detail="skipped by --skip-tests",
            elapsed_s=0.0,
            required=False,
        )
    cmd = [".venv/bin/python", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]
    rc, _out, err, elapsed = _run_command(cmd)
    tail = "\n".join(err.strip().splitlines()[-8:])
    return CheckResult(
        name="unit_tests",
        status="PASS" if rc == 0 else "FAIL",
        detail=tail or f"exit={rc}",
        elapsed_s=elapsed,
    )


def check_lived_memory(*, threshold: float) -> CheckResult:
    from core.memory.episodes import EpisodeStore
    from core.memory.relationship_graph import RelationshipGraph
    from scripts.validate.lived_memory_probes import run_probes

    start = time.time()
    store = EpisodeStore(REPO_ROOT / "memory" / "lived_episodes.db")
    graph = RelationshipGraph(REPO_ROOT / "memory" / "lived_graph.db")
    report = run_probes(episode_store=store, graph=graph)
    passed = sum(1 for r in report.results if r.passed)
    total = len(report.results)
    failing = [r.name for r in report.results if not r.passed]
    detail = f"score={report.score:.0%} ({passed}/{total})"
    if failing:
        detail += f"; failing={','.join(failing)}"
    return CheckResult(
        name="lived_memory_probes",
        status=_status_from_score(report.score, threshold),
        detail=detail,
        elapsed_s=time.time() - start,
    )


def check_voice_dataset(*, target_pairs: int, out_path: Path) -> CheckResult:
    cmd = [
        ".venv/bin/python",
        "training/extract_training_pairs.py",
        "--out",
        str(out_path),
        "--max-pairs",
        "2000",
        "--max-per-source",
        "30",
    ]
    rc, _out, err, elapsed = _run_command(cmd)
    if rc != 0:
        return CheckResult(
            name="voice_dataset",
            status="FAIL",
            detail="\n".join(err.strip().splitlines()[-8:]) or f"exit={rc}",
            elapsed_s=elapsed,
        )
    kept = _count_jsonl(out_path)
    status = "PASS" if kept >= target_pairs else "WARN"
    return CheckResult(
        name="voice_dataset",
        status=status,
        detail=f"kept={kept}; target={target_pairs}; output={out_path.relative_to(REPO_ROOT)}",
        elapsed_s=elapsed,
        required=False,
    )


def check_git_clean() -> CheckResult:
    rc, out, err, elapsed = _run_command(["git", "status", "--short"])
    if rc != 0:
        return CheckResult(
            name="git_clean",
            status="WARN",
            detail=err.strip() or f"git status exited {rc}",
            elapsed_s=elapsed,
            required=False,
        )
    dirty = [line for line in out.splitlines() if line.strip()]
    return CheckResult(
        name="git_clean",
        status="PASS" if not dirty else "WARN",
        detail="clean" if not dirty else f"{len(dirty)} changed path(s)",
        elapsed_s=elapsed,
        required=False,
    )


def _split_csv(value: str) -> list[str]:
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def check_trace_harness(
    *,
    trace_dir: Path,
    report_dir: Path,
    latest_n: int = 50,
) -> CheckResult:
    """Slice 2 advisory tier — runs the deterministic trace harness
    over recent JSONL traces and folds the result into the parent
    summary. Advisory: WARNs/FAILs surface but never gate the parent
    harness's exit code (per the soak-before-promote discipline in
    docs/HANDOFF-2026-04-28.md).
    """
    from scripts.validate.trace_harness import run as run_trace_harness

    start = time.time()
    try:
        report = run_trace_harness(
            trace_dir=trace_dir,
            trace_file=None,
            latest_n=latest_n,
            owner_surfaces=None,  # use module default
            latency_warn_ms=30_000,
            report_dir=report_dir,
        )
    except Exception as exc:
        return CheckResult(
            name="trace_harness",
            status="WARN",
            detail=f"trace harness raised: {exc!r}",
            elapsed_s=time.time() - start,
            required=False,
        )
    summary = report.get("summary") or {}
    scanned = report.get("traces_scanned", 0)
    fail_count = int(summary.get("FAIL", 0))
    warn_count = int(summary.get("WARN", 0))
    files = len(report.get("files_read") or [])
    if scanned == 0:
        # No traces yet (e.g. fresh install or wiped logs/traces). Not
        # a fail-class signal — Slice 1 has only been live since
        # 2026-04-29; ramps as the daemon runs.
        return CheckResult(
            name="trace_harness",
            status="WARN",
            detail=f"scanned=0 from {files} file(s); no traces to grade yet",
            elapsed_s=time.time() - start,
            required=False,
        )
    detail = (
        f"scanned={scanned} from {files} file(s); "
        f"PASS={summary.get('PASS', 0)} WARN={warn_count} FAIL={fail_count}; "
        f"findings={len(report.get('findings') or [])}"
    )
    if fail_count:
        status = "FAIL"
    elif warn_count:
        status = "WARN"
    else:
        status = "PASS"
    return CheckResult(
        name="trace_harness",
        status=status,
        detail=detail,
        elapsed_s=time.time() - start,
        required=False,  # advisory until soak proves false-positive rate is low
    )


def check_services(*, services: list[str], required: bool) -> CheckResult:
    if not services:
        return CheckResult(
            name="service_health_required" if required else "service_health_advisory",
            status="SKIP",
            detail="no services configured",
            elapsed_s=0.0,
            required=False,
        )
    start = time.time()
    bad: list[str] = []
    states: list[str] = []
    for service in services:
        rc, out, err, _elapsed = _run_command(
            ["systemctl", "is-active", service],
            timeout=10,
        )
        state = (out or err).strip() or f"exit={rc}"
        states.append(f"{service}:{state}")
        if rc != 0 or state != "active":
            bad.append(f"{service}:{state}")
    elapsed = time.time() - start
    if bad:
        return CheckResult(
            name="service_health_required" if required else "service_health_advisory",
            status="FAIL" if required else "WARN",
            detail=", ".join(bad),
            elapsed_s=elapsed,
            required=required,
        )
    return CheckResult(
        name="service_health_required" if required else "service_health_advisory",
        status="PASS",
        detail=", ".join(states),
        elapsed_s=elapsed,
        required=required,
    )


def write_report(results: list[CheckResult], *, report_dir: Path) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = report_dir / f"track_a_harness_{stamp}.json"
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "results": [asdict(r) for r in results],
        "required_pass": all(r.status == "PASS" for r in results if r.required),
        "advisory_warn": [r.name for r in results if r.status == "WARN"],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")
    latest = report_dir / "track_a_harness_latest.json"
    latest.write_text(path.read_text())
    return path


def format_summary(results: list[CheckResult], report_path: Path) -> str:
    lines = ["=== TRACK A PREFLIGHT HARNESS ==="]
    for r in results:
        req = "required" if r.required else "advisory"
        lines.append(f"{r.status:4s} {r.name:22s} {req:8s} {r.detail}")
    lines.append(f"report={report_path.relative_to(REPO_ROOT)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--skip-tests", action="store_true", help="skip full unittest suite")
    ap.add_argument("--lived-threshold", type=float, default=0.85)
    ap.add_argument("--voice-target", type=int, default=500)
    ap.add_argument("--dataset-out", default=str(DEFAULT_DATASET_OUT))
    ap.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR))
    ap.add_argument(
        "--include-live-services",
        action="store_true",
        help=(
            "also check systemd service health. Required services are hard "
            "gates in this mode; advisory services warn only."
        ),
    )
    ap.add_argument("--required-services", default=DEFAULT_REQUIRED_SERVICES)
    ap.add_argument("--advisory-services", default=DEFAULT_ADVISORY_SERVICES)
    ap.add_argument(
        "--include-trace-checks",
        action="store_true",
        help=(
            "also run the deterministic trace harness over recent "
            "logs/traces/*.jsonl traces. Advisory tier — WARNs and "
            "FAILs surface in the report but do not gate the parent "
            "harness's exit code (Slice 2 soak discipline)."
        ),
    )
    ap.add_argument(
        "--trace-dir",
        default=str(REPO_ROOT / "logs" / "traces"),
        help="directory of per-turn JSONL traces (Slice 1 output)",
    )
    ap.add_argument(
        "--trace-latest-n",
        type=int,
        default=50,
        help="grade the N most-recent traces across all files (default 50)",
    )
    args = ap.parse_args(argv)

    results = [
        check_unit_tests(skip=args.skip_tests),
        check_lived_memory(threshold=args.lived_threshold),
        check_voice_dataset(
            target_pairs=args.voice_target,
            out_path=Path(args.dataset_out),
        ),
        check_git_clean(),
    ]
    if args.include_live_services:
        results.append(
            check_services(
                services=_split_csv(args.required_services),
                required=True,
            )
        )
        results.append(
            check_services(
                services=_split_csv(args.advisory_services),
                required=False,
            )
        )
    if args.include_trace_checks:
        results.append(
            check_trace_harness(
                trace_dir=Path(args.trace_dir),
                report_dir=REPO_ROOT / "logs" / "trace_harness",
                latest_n=args.trace_latest_n,
            )
        )
    report_path = write_report(results, report_dir=Path(args.report_dir))
    print(format_summary(results, report_path))
    return 0 if all(r.status == "PASS" for r in results if r.required) else 1


if __name__ == "__main__":
    sys.exit(main())
