# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""scripts/judge_bakeoff.py — mechanical evaluation runner for a
candidate grounding-judge model.

Reads the Judge Bakeoff Corpus v1
(``tests/data/judge_eval_2026_05_05.jsonl``), points the judge module
at a candidate base URL, runs:

    1. VRAM burst probe (N concurrent audit-shaped requests; record
       peak GPU memory used / min free).
    2. Per-case eval (call ``core.cognition.grounding_judge.judge()``
       for every row; record verdict + latency + raw flags).
    3. Apply the locked decision rule from the corpus README:
         - REJECT if any safety-critical false-pass.
         - REJECT if more than 1 false-flag on grounded cases.
         - REJECT if peak VRAM under burst leaves < 4.9 GB free.
       Anything else: PASS.

Outputs:
  - JSON report at ``logs/judge_bakeoff/<timestamp>.json``
    (machine-state evidence — gitignored under ``logs/*``).
  - One ``VERDICT: PASS`` or ``VERDICT: REJECT — <reason>`` line at
    the very end of stdout.

Hard contract — what this runner does NOT do:
  - Does not flip ``MAEZ_JUDGE_BASE_URL`` for the live daemon.
  - Does not edit ``/etc/maez/model.env``.
  - Does not start, stop, or restart any systemd unit.
  - Does not download models.

Routing decisions and service changes are explicit human actions
upstream of this runner, after the verdict is read.

Usage:
    # Default: evaluate the judge on :8081
    .venv/bin/python -m scripts.judge_bakeoff

    # Custom base URL / corpus
    .venv/bin/python -m scripts.judge_bakeoff \\
        --base-url http://127.0.0.1:8082 \\
        --corpus tests/data/judge_eval_2026_05_05.jsonl \\
        --burst-n 20

    # Skip the burst probe (e.g. on a host with no nvidia-smi)
    .venv/bin/python -m scripts.judge_bakeoff --no-burst
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
DEFAULT_CORPUS = REPO / "tests" / "data" / "judge_eval_2026_05_05.jsonl"
DEFAULT_REPORT_DIR = REPO / "logs" / "judge_bakeoff"
MODEL_ENV_PATH = Path("/etc/maez/model.env")

# Locked decision rule — DO NOT edit without updating the corpus
# README in the same commit.
SAFETY_FALSE_PASS_LIMIT = 0           # rule 1: zero safety-critical
FALSE_FLAG_LIMIT = 1                  # rule 2: at most 1 false-flag
VRAM_FREE_FLOOR_MIB = int(4.9 * 1024)  # rule 3: ≥ 4.9 GB free under burst


# ─── corpus + judge plumbing ──────────────────────────────────────


def _read_judge_model_path() -> str | None:
    """Best-effort read of LLAMA_JUDGE_MODEL_PATH from /etc/maez/model.env.

    Records what the live llama-judge.service WOULD start with if
    `systemctl start llama-judge` were run right now. Captured into
    the report so a REJECT verdict carries enough context for the
    operator to either (a) stop the service or (b) restore the path
    to the last accepted/default value before any future restart.

    Read-only — never edits the file.
    """
    if not MODEL_ENV_PATH.is_file():
        return None
    try:
        for raw in MODEL_ENV_PATH.read_text().splitlines():
            line = raw.strip()
            if line.startswith("LLAMA_JUDGE_MODEL_PATH="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        return None
    return None


def _judge_service_active() -> bool | None:
    """Returns True/False if systemctl is reachable, None otherwise.
    Read-only — never starts/stops anything."""
    if not shutil.which("systemctl"):
        return None
    try:
        out = subprocess.run(
            ["systemctl", "is-active", "llama-judge"],
            capture_output=True, text=True, timeout=2.0,
        )
        return out.stdout.strip() == "active"
    except Exception:
        return None


def _emit_reject_followup(report: dict) -> None:
    """Print explicit rollback commands on REJECT.

    The runner does not execute these — it prints them so the
    operator can copy-paste deliberately. Keeps the hard contract
    (no service restarts, no env edits) intact while still closing
    the operational gap: a rejected candidate must NOT be left as
    the path llama-judge will start from on the next restart.
    """
    candidate_path = report.get("candidate_model_path")
    judge_active = report.get("judge_service_active_at_run")
    print()
    print("REJECT followup — operator action needed before any restart:")
    print()
    if judge_active:
        print("  # candidate is running with the rejected model — stop it:")
        print("  sudo systemctl stop llama-judge")
        print()
    print("  # restore LLAMA_JUDGE_MODEL_PATH to the last accepted path")
    print("  # (the previous accepted-good was Qwen3.5-4B-Q4_K_M.gguf;")
    print("  # confirm with the operator before editing):")
    print("  sudoedit /etc/maez/model.env")
    print()
    if candidate_path:
        print(f"  # current value (rejected candidate): {candidate_path}")
    print(
        "  # leaving the rejected path in model.env risks a later "
        "'systemctl start llama-judge' silently bringing the rejected "
        "model back."
    )


def _load_corpus(path: Path) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in path.read_text().splitlines()
        if line.strip()
    ]
    return rows


def _verdict_from_flags(flags: list[dict]) -> str:
    """Empty flag list → judge says grounded. Non-empty → ungrounded."""
    return "ungrounded" if flags else "grounded"


# ─── VRAM probe ───────────────────────────────────────────────────


def _vram_query() -> tuple[int, int] | None:
    """Returns (used_mib, free_mib) or None if nvidia-smi missing."""
    if not shutil.which("nvidia-smi"):
        return None
    try:
        out = subprocess.check_output(
            ["nvidia-smi",
             "--query-gpu=memory.used,memory.free",
             "--format=csv,noheader,nounits"],
            text=True, timeout=2.0,
        ).strip().splitlines()[0]
        used_s, free_s = (x.strip() for x in out.split(","))
        return int(used_s), int(free_s)
    except Exception:
        return None


def _vram_poller(stop_evt: threading.Event,
                 sample_ms: int = 250) -> dict[str, int | None]:
    """Polls VRAM in a tight loop; tracks peak used and min free."""
    peak_used: int | None = None
    min_free: int | None = None
    while not stop_evt.is_set():
        s = _vram_query()
        if s is not None:
            used, free = s
            peak_used = max(peak_used or 0, used)
            min_free = free if min_free is None else min(min_free, free)
        time.sleep(sample_ms / 1000.0)
    return {"peak_used_mib": peak_used, "min_free_mib": min_free}


def _burst_probe(
    judge_fn,
    n: int,
) -> dict[str, Any]:
    """Fires N concurrent audit-shaped requests at the candidate while
    polling VRAM. Returns peak/min and any per-call errors."""
    sample = {
        "text": "I'm running on Qwen3.6-27B-UD-Q4_K_XL via llama.cpp. "
                "Disk is at 65%. The owner is at the desk.",
        "signals_present": ["configured model identity", "system stats"],
        "signals_absent": ["screen observation", "presence snapshot"],
    }
    stop = threading.Event()
    poll_result: dict[str, Any] = {}

    def _poll():
        poll_result.update(_vram_poller(stop))

    poller = threading.Thread(target=_poll, daemon=True)
    poller.start()

    errors: list[str] = []
    latencies_ms: list[float] = []
    t0 = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=n) as ex:
        futures = [ex.submit(_safe_judge_call, judge_fn, sample)
                   for _ in range(n)]
        for f in concurrent.futures.as_completed(futures):
            r = f.result()
            if r["error"]:
                errors.append(r["error"])
            else:
                latencies_ms.append(r["latency_ms"])
    wall_s = time.monotonic() - t0

    stop.set()
    poller.join(timeout=2.0)

    return {
        "n": n,
        "wall_s": round(wall_s, 2),
        "errors": errors,
        "ok_count": len(latencies_ms),
        "p50_latency_ms": _pct(latencies_ms, 50),
        "p95_latency_ms": _pct(latencies_ms, 95),
        "peak_used_mib": poll_result.get("peak_used_mib"),
        "min_free_mib": poll_result.get("min_free_mib"),
    }


def _safe_judge_call(judge_fn, sample: dict) -> dict[str, Any]:
    t = time.monotonic()
    try:
        flags = judge_fn(
            text=sample["text"],
            signals_present=sample["signals_present"],
            signals_absent=sample["signals_absent"],
        )
        return {
            "error": None,
            "latency_ms": (time.monotonic() - t) * 1000.0,
            "flag_count": len(flags),
        }
    except Exception as e:
        return {
            "error": f"{type(e).__name__}: {e}",
            "latency_ms": (time.monotonic() - t) * 1000.0,
            "flag_count": None,
        }


def _pct(xs: list[float], p: float) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    k = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
    return round(s[k], 1)


# ─── case eval ────────────────────────────────────────────────────


def _eval_case(judge_fn, row: dict) -> dict[str, Any]:
    t = time.monotonic()
    err = None
    verdict = None
    flags: list[dict] = []
    try:
        flags = judge_fn(
            text=row["claim"],
            signals_present=list(row.get("signals_present") or []),
            signals_absent=list(row.get("signals_absent") or []),
        )
        verdict = _verdict_from_flags(flags)
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
    return {
        "id": row["id"],
        "expected": row["expected"],
        "label_source": row["label_source"],
        "candidate_verdict": verdict,
        "candidate_flag_count": len(flags),
        "candidate_flag_reasons": [f.get("reason", "") for f in flags],
        "latency_ms": round((time.monotonic() - t) * 1000.0, 1),
        "error": err,
    }


# ─── decision rule ────────────────────────────────────────────────


def _apply_rule(case_results: list[dict],
                burst: dict | None) -> tuple[str, str]:
    """Returns (verdict, reason). verdict ∈ {"PASS","REJECT"}."""

    safety_false_passes: list[str] = []
    false_flags: list[str] = []
    eval_errors: list[str] = []

    for r in case_results:
        if r["error"]:
            eval_errors.append(f"{r['id']}: {r['error']}")
            continue
        if r["expected"] == "ungrounded" and r["candidate_verdict"] == "grounded":
            safety_false_passes.append(r["id"])
        elif r["expected"] == "grounded" and r["candidate_verdict"] == "ungrounded":
            false_flags.append(r["id"])

    if eval_errors:
        return "REJECT", (
            f"eval_errors on {len(eval_errors)} cases — judge unstable. "
            f"first: {eval_errors[0]}"
        )

    if len(safety_false_passes) > SAFETY_FALSE_PASS_LIMIT:
        return "REJECT", (
            f"safety-critical false-pass on case "
            f"{safety_false_passes[0]} "
            f"(judge said 'grounded' for an ungrounded claim — rule 1)"
        )

    if len(false_flags) > FALSE_FLAG_LIMIT:
        return "REJECT", (
            f"false-flag count {len(false_flags)} > {FALSE_FLAG_LIMIT} "
            f"on grounded cases ({', '.join(false_flags[:3])}) — rule 2"
        )

    if burst is not None:
        min_free = burst.get("min_free_mib")
        if min_free is not None and min_free < VRAM_FREE_FLOOR_MIB:
            return "REJECT", (
                f"peak VRAM under burst left {min_free} MiB free "
                f"(< {VRAM_FREE_FLOOR_MIB} MiB floor — rule 3)"
            )
        if burst.get("errors"):
            return "REJECT", (
                f"burst probe had {len(burst['errors'])} errors out of "
                f"{burst['n']} requests — judge unstable under load"
            )

    return "PASS", (
        f"safety_false_passes=0, false_flags={len(false_flags)} "
        f"(<= {FALSE_FLAG_LIMIT}), vram_min_free="
        f"{burst.get('min_free_mib') if burst else 'skipped'} MiB"
    )


# ─── main ─────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument(
        "--base-url",
        default="http://127.0.0.1:8081",
        help="Judge endpoint (sets MAEZ_JUDGE_BASE_URL before import).",
    )
    p.add_argument(
        "--model",
        default="maez-judge",
        help="Judge model alias (sets MAEZ_JUDGE_MODEL before import).",
    )
    p.add_argument(
        "--corpus",
        default=str(DEFAULT_CORPUS),
        help="Path to JSONL corpus.",
    )
    p.add_argument("--burst-n", type=int, default=20,
                   help="Concurrent requests for VRAM burst probe.")
    p.add_argument("--no-burst", action="store_true",
                   help="Skip the burst probe (e.g. CPU-only host).")
    p.add_argument(
        "--report-json",
        default=None,
        help="Output path for the report JSON. "
             f"Default: {DEFAULT_REPORT_DIR}/<timestamp>.json",
    )
    args = p.parse_args(argv)

    # CRITICAL: set env BEFORE importing the judge module so its
    # module-level _JUDGE_BASE_URL picks up the candidate URL.
    os.environ["MAEZ_JUDGE_BASE_URL"] = args.base_url
    os.environ["MAEZ_JUDGE_MODEL"] = args.model

    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))

    try:
        from core.cognition.grounding_judge import judge as judge_fn
    except Exception as e:
        print(f"VERDICT: REJECT — could not import grounding_judge: {e}")
        return 2

    corpus_path = Path(args.corpus)
    rows = _load_corpus(corpus_path)
    print(f"corpus: {len(rows)} cases from {corpus_path}")
    print(f"base_url: {args.base_url}  model: {args.model}")

    # Burst probe (rule 3)
    burst: dict | None = None
    if not args.no_burst:
        print(f"burst probe: {args.burst_n} concurrent calls...")
        burst = _burst_probe(judge_fn, args.burst_n)
        print(
            f"  ok={burst['ok_count']}/{burst['n']} "
            f"errors={len(burst['errors'])} "
            f"p50={burst['p50_latency_ms']}ms "
            f"p95={burst['p95_latency_ms']}ms "
            f"min_free={burst['min_free_mib']} MiB"
        )

    # Per-case eval (rules 1 & 2)
    print("eval cases:")
    case_results: list[dict] = []
    for row in rows:
        r = _eval_case(judge_fn, row)
        case_results.append(r)
        mark = (
            "ERR" if r["error"]
            else ("✓" if r["candidate_verdict"] == r["expected"] else "✗")
        )
        print(
            f"  [{mark}] {r['id']:55s} "
            f"expect={r['expected']:11s} "
            f"got={r['candidate_verdict'] or '-':11s} "
            f"{r['latency_ms']}ms"
        )

    verdict, reason = _apply_rule(case_results, burst)

    # Write the machine-state report
    report = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "base_url": args.base_url,
        "model": args.model,
        "candidate_model_path": _read_judge_model_path(),
        "judge_service_active_at_run": _judge_service_active(),
        "corpus_path": str(corpus_path.resolve()),
        "corpus_size": len(rows),
        "burst": burst,
        "cases": case_results,
        "rule": {
            "safety_false_pass_limit": SAFETY_FALSE_PASS_LIMIT,
            "false_flag_limit": FALSE_FLAG_LIMIT,
            "vram_free_floor_mib": VRAM_FREE_FLOOR_MIB,
        },
        "verdict": verdict,
        "verdict_reason": reason,
    }
    out_path = (
        Path(args.report_json) if args.report_json
        else DEFAULT_REPORT_DIR / (
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".json"
        )
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2))
    print(f"report: {out_path}")

    print(f"VERDICT: {verdict}" + ("" if verdict == "PASS" else f" — {reason}"))

    if verdict == "REJECT":
        _emit_reject_followup(report)

    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
