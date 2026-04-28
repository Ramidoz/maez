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
    args = ap.parse_args(argv)

    results = [
        check_unit_tests(skip=args.skip_tests),
        check_lived_memory(threshold=args.lived_threshold),
        check_voice_dataset(
            target_pairs=args.voice_target,
            out_path=Path(args.dataset_out),
        ),
    ]
    report_path = write_report(results, report_dir=Path(args.report_dir))
    print(format_summary(results, report_path))
    return 0 if all(r.status == "PASS" for r in results if r.required) else 1


if __name__ == "__main__":
    sys.exit(main())
