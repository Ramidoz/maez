#!/usr/bin/env python3
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""replay_harness.py — birth-readiness and regression probe runner for Maez.

Per docs/slices/legacy/gestation-boundary.md §5, the replay harness has
two modes as of Slice 3.6:

  - birth_readiness  — compare current behavior vs expected post-birth
                       behavior. Goal: measure the gap to birth criteria.
  - regression       — compare current behavior vs a stored, schema-
                       versioned baseline and fail on behavior drift,
                       probe-contract drift, or unreasoned baseline
                       regeneration.

The harness loads a JSONL probe corpus (one probe per line). Each
probe targets one of the missing 2.5c volume-gate behavior classes:

  - multi_turn_continuity
  - surface_interleaving
  - real_content_claims
  - envelope_pressure
  - concurrency
  - multi_turn_self_history

Each probe runs against an ISOLATED probe ledger DB (caller-supplied
or auto-created in a temp directory). The harness never reads any
env-var ledger-path override and never touches the production ledger
location — the probe runs are write-isolated by construction.

Usage:
  scripts/replay_harness.py --corpus tests/probes/birth_readiness_corpus.jsonl \\
                             --mode birth_readiness \\
                             --output report.txt

Exit code: 0 if all probes PASS, 1 otherwise. Useful as a pre-merge
gate or as a standalone birth-readiness measurement.
"""
from __future__ import annotations

import argparse
import contextlib
import dataclasses
import hashlib
import json
import logging
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, IO, Iterable

# Local-only imports. The harness deliberately avoids importing the
# full daemon stack (which would touch network on import). It does
# import ledger + envelope_builder + recent_turns directly.
_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
sys.path.insert(0, str(_REPO))

from core.cognition import envelope_builder as _eb  # noqa: E402
from core.ledger import chain as _chain  # noqa: E402
from core.ledger import migrate as _migrate  # noqa: E402
from core.ledger import writer as _writer  # noqa: E402


# ── data ──────────────────────────────────────────────────────────────


def _stamp_for_synthetic_kind(kind: str, *, models_owner_text: bool = False) -> dict:
    if kind == "user_message":
        labels = ["owner_utterance"] if models_owner_text else ["self_generated"]
    elif kind in ("model_reply", "daemon_cycle", "system_event"):
        labels = ["self_generated"]
    elif kind == "tool_result":
        labels = ["tool_output"]
    elif kind == "tool_call":
        labels = ["self_generated"]
    elif kind == "peer_message_in":
        labels = ["third_party"]
    elif kind == "peer_message_out":
        labels = ["self_generated"]
    else:
        labels = ["self_generated"]
    return {"taint_labels": labels, "privacy_access": "public"}


class ProbeCorpusError(ValueError):
    """Raised when a probe corpus file is malformed."""


class RegressionBaselineError(ValueError):
    """Raised when regression baseline input is missing or invalid."""


@dataclasses.dataclass(frozen=True)
class Probe:
    id: str
    category: str
    purpose: str
    expected_lifecycle_target: str
    raw: dict  # full probe dict for category-specific access


@dataclasses.dataclass
class ProbeResult:
    probe_id: str
    category: str
    verdict: str  # "PASS" | "FAIL" | "FLAG"
    reason: str
    metrics: dict


@dataclasses.dataclass
class CorpusReport:
    mode: str
    results: list[ProbeResult]
    overall: str  # "PASS" | "FAIL" | "PARTIAL"
    gap_to_birth: int  # count of non-PASS probes (birth-readiness mode)
    started_at: float
    finished_at: float


@dataclasses.dataclass(frozen=True)
class ProbeDefinition:
    probe: Probe
    canonical_json: str
    sha256: str


@dataclasses.dataclass
class RegressionDrift:
    probe_id: str
    status: str
    reason: str


@dataclasses.dataclass
class RegressionReport:
    baseline_path: str
    corpus_path: str
    overall: str
    drifts: list[RegressionDrift]
    baseline: dict | None = None
    operation: str = "check"


_REQUIRED_FIELDS = ("id", "category", "purpose")
_BASELINE_SCHEMA_VERSION = 1
_DEFAULT_BASELINE_PATH = _REPO / "tests" / "probes" / "regression_baseline.json"


# ── fixture loading ───────────────────────────────────────────────────


def _iter_probes_from_handle(
    handle: IO[str], *, source: str,
) -> Iterable[Probe]:
    for lineno, line in enumerate(handle, start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            raise ProbeCorpusError(
                f"{source}:{lineno}: not valid JSON ({e})"
            ) from e
        if not isinstance(obj, dict):
            raise ProbeCorpusError(
                f"{source}:{lineno}: expected object, got {type(obj).__name__}"
            )
        for k in _REQUIRED_FIELDS:
            if k not in obj or not isinstance(obj[k], str) or not obj[k]:
                raise ProbeCorpusError(
                    f"{source}:{lineno}: missing required field {k!r}"
                )
        yield Probe(
            id=obj["id"],
            category=obj["category"],
            purpose=obj["purpose"],
            expected_lifecycle_target=obj.get(
                "expected_lifecycle_target", "birth_ready",
            ),
            raw=obj,
        )


def load_probes(corpus_path: str | Path) -> list[Probe]:
    """Load all probes from a JSONL corpus file."""
    p = Path(corpus_path)
    with p.open("r", encoding="utf-8") as fh:
        return list(_iter_probes_from_handle(fh, source=str(p)))


def _canonical_json(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def probe_corpus_sha256(corpus_path: str | Path) -> str:
    return hashlib.sha256(Path(corpus_path).read_bytes()).hexdigest()


def load_probe_definitions(corpus_path: str | Path) -> dict[str, ProbeDefinition]:
    """Load probes plus a stable per-probe definition hash.

    The corpus file's raw bytes identify whole-corpus drift. Per-probe
    hashes identify added / removed / modified probe contracts for
    human-readable regression reports.
    """
    path = Path(corpus_path)
    definitions: dict[str, ProbeDefinition] = {}
    with path.open("r", encoding="utf-8") as fh:
        for probe in _iter_probes_from_handle(fh, source=str(path)):
            if probe.id in definitions:
                raise ProbeCorpusError(
                    f"{path}: duplicate probe id {probe.id!r}"
                )
            canonical = _canonical_json(probe.raw)
            definitions[probe.id] = ProbeDefinition(
                probe=probe,
                canonical_json=canonical,
                sha256=_sha256_text(canonical),
            )
    return definitions


# ── telemetry capture ─────────────────────────────────────────────────


class _LogCapture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@contextlib.contextmanager
def capture_logs(logger_names: list[str]):
    """Attach a _LogCapture to each named logger, yield it, detach."""
    cap = _LogCapture()
    cap.setLevel(logging.DEBUG)
    attached = []
    for name in logger_names:
        log = logging.getLogger(name)
        log.addHandler(cap)
        log.setLevel(logging.DEBUG)
        attached.append(log)
    try:
        yield cap
    finally:
        for log in attached:
            log.removeHandler(cap)


# ── per-category probe runners ────────────────────────────────────────


def _run_continuity_probe(
    probe: Probe, *, probe_db_path: str,
) -> ProbeResult:
    """multi_turn_continuity — write the history into the ledger,
    inspect that recent_turns_by_kind would return them, verify
    self_history population includes the expected substrings.
    Pre-birth: rows are gestation by default, recall_gestation='full'
    surfaces them at full strength."""
    raw = probe.raw
    history = raw.get("history", [])
    expected_min = int(raw.get("expected_self_history_min", 0))
    expected_substrs = raw.get("expected_self_history_includes_substrings", [])

    with _writes_enabled():
        w = _writer.LedgerWriter(probe_db_path)
        try:
            for turn in history:
                kind = (
                    "model_reply" if turn["role"] == "assistant"
                    else "user_message"
                )
                if kind == "model_reply":
                    w.write_turn(
                        kind, turn["content"],
                        **_stamp_for_synthetic_kind(kind, models_owner_text=kind == "user_message"),
                        model_id="qwen36-27b",
                        prompt_hash="p" * 64, soul_hash="s" * 64,
                        evidence_envelope={"claimable": [], "forbidden": []},
                        audit_verdict={"verdict": "grounded"},
                    )
                else:
                    w.write_turn(
                        kind,
                        turn["content"],
                        **_stamp_for_synthetic_kind(kind, models_owner_text=True),
                    )
        finally:
            w.close()

    sh = _eb.BoundedEnvelopeBuilder()._populate_self_history(
        probe_db_path, limit=10, tenant_id="owner",
        recall_gestation="full",
    )
    if len(sh) < expected_min:
        return ProbeResult(
            probe.id, probe.category, "FAIL",
            f"self_history populated {len(sh)} < expected_min {expected_min}",
            {"self_history_count": len(sh)},
        )
    joined = " ".join(e.get("utterance_summary") or "" for e in sh)
    for sub in expected_substrs:
        if sub not in joined:
            return ProbeResult(
                probe.id, probe.category, "FAIL",
                f"expected substring {sub!r} not found in self_history",
                {"self_history_count": len(sh)},
            )
    return ProbeResult(
        probe.id, probe.category, "PASS",
        f"self_history populated ({len(sh)} entries) with expected substrs",
        {"self_history_count": len(sh)},
    )


def _run_interleaving_probe(
    probe: Probe, *, probe_db_path: str,
) -> ProbeResult:
    """surface_interleaving — write turns from multiple surfaces,
    verify ledger preserves correct surface attribution."""
    writes = probe.raw.get("synthetic_writes", [])
    expected_dist = probe.raw.get("expected_ledger_surface_distribution", {})

    with _writes_enabled():
        w = _writer.LedgerWriter(probe_db_path)
        try:
            for entry in writes:
                w.write_turn(
                    "user_message", entry["text"],
                    surface=entry["surface"],
                    **_stamp_for_synthetic_kind("user_message", models_owner_text=True),
                )
        finally:
            w.close()

    with contextlib.closing(sqlite3.connect(probe_db_path)) as conn, conn:
        rows = conn.execute(
            "SELECT surface, COUNT(*) FROM turns "
            "WHERE turn_kind='user_message' "
            "GROUP BY surface"
        ).fetchall()
    actual = {s: c for s, c in rows}
    if actual != expected_dist:
        return ProbeResult(
            probe.id, probe.category, "FAIL",
            f"surface distribution mismatch: got {actual!r}, "
            f"expected {expected_dist!r}",
            {"actual_distribution": actual},
        )
    return ProbeResult(
        probe.id, probe.category, "PASS",
        f"surface attribution correct: {actual}",
        {"actual_distribution": actual},
    )


def _run_real_claims_probe(
    probe: Probe, *, probe_db_path: str,
) -> ProbeResult:
    """real_content_claims — synthesize an envelope with the absent
    signals named in the probe; verify forbidden topics include the
    expected substrings."""
    sa = probe.raw.get("synthetic_signals_absent", [])
    expected_forbidden_subs = probe.raw.get(
        "expected_envelope_forbidden_includes_substrings", []
    )
    env = _eb.build_envelope(
        ledger_db_path=probe_db_path,
        signals_present=[], signals_absent=sa,
        tool_results=[],
    )
    if env is None:
        return ProbeResult(
            probe.id, probe.category, "FAIL",
            "envelope was None (disabled mode?); probe requires active envelope",
            {"envelope_disabled": True},
        )
    rendered = _eb.render_envelope_for_prompt(env)
    for sub in expected_forbidden_subs:
        if sub not in rendered:
            return ProbeResult(
                probe.id, probe.category, "FAIL",
                f"forbidden substring {sub!r} not in rendered envelope",
                {"rendered_excerpt": rendered[:200]},
            )
    return ProbeResult(
        probe.id, probe.category, "PASS",
        "envelope renders forbidden topics for absent signals",
        {"signals_absent_count": len(sa)},
    )


def _run_envelope_pressure_probe(
    probe: Probe, *, probe_db_path: str,
) -> ProbeResult:
    """envelope_pressure — synthesize over-cap envelope inputs, verify
    truncation telemetry fires with correct cap_hit kind."""
    spec = probe.raw.get("synthetic_envelope_input", {})
    sp = spec.get("signals_present", [])
    sa = spec.get("signals_absent", [])
    n_tools = int(spec.get("tool_results_count", 0))
    summary_chars = int(spec.get("tool_results_summary_chars", 0))
    n_claim = int(spec.get("claimable_count", 0))
    n_forbid = int(spec.get("forbidden_count", 0))
    char_cap = int(spec.get("char_cap", 12000))
    # Adversarial-review §6.6 finding: a probe with
    # expected_truncation_events_min=0 (or missing) would false-PASS
    # if a future regression silently disables truncation entirely.
    # Force minimum 1 — the whole point of an envelope_pressure probe
    # is to verify truncation fires.
    expected_min = max(1, int(probe.raw.get("expected_truncation_events_min", 1)))
    allowed_kinds = set(probe.raw.get(
        "expected_truncation_kinds_allowed",
        ["per_section_cap", "total_cap", "minimal_fallback"],
    ))

    tool_results = [
        {"name": f"t{i}", "status": "ok", "summary": "x" * summary_chars}
        for i in range(n_tools)
    ]
    claimable = [{"text": f"claim_{i}"} for i in range(n_claim)]
    forbidden = [
        {"topic": f"forbid_{i}", "reason": "rationale"}
        for i in range(n_forbid)
    ]

    with capture_logs(["maez.envelope"]) as cap:
        _eb.build_envelope(
            ledger_db_path=probe_db_path,
            signals_present=sp, signals_absent=sa,
            tool_results=tool_results,
            claimable=claimable,
            forbidden=forbidden,
            char_cap=char_cap,
        )
    truncation_records = [
        r for r in cap.records
        if getattr(r, "truncation_kind", None) is not None
    ]
    actual_kinds = {
        getattr(r, "truncation_kind", None) for r in truncation_records
    }
    if len(truncation_records) < expected_min:
        return ProbeResult(
            probe.id, probe.category, "FAIL",
            f"got {len(truncation_records)} truncations, "
            f"expected_min={expected_min}",
            {"truncation_events": len(truncation_records)},
        )
    if not (actual_kinds & allowed_kinds):
        return ProbeResult(
            probe.id, probe.category, "FAIL",
            f"truncation kinds {actual_kinds} not in allowed {allowed_kinds}",
            {"truncation_events": len(truncation_records)},
        )
    return ProbeResult(
        probe.id, probe.category, "PASS",
        f"truncation fired: {len(truncation_records)} events, kinds={actual_kinds}",
        {"truncation_events": len(truncation_records)},
    )


def _run_concurrency_probe(
    probe: Probe, *, probe_db_path: str,
) -> ProbeResult:
    """concurrency — N parallel writes via threads, verify chain
    integrity post-run. The writer holds an internal lock + uses
    BEGIN IMMEDIATE so SQLite serializes; this probe verifies that
    behavior under stress."""
    spec = probe.raw.get("synthetic_concurrent_writes", {})
    count = int(spec.get("count", 10))
    kind = spec.get("kind", "user_message")
    template = spec.get("text_template", "concurrent {i}")
    expected_total = int(probe.raw.get("expected_total_rows", count))

    # Production model: ONE LedgerWriter instance per process,
    # serialized via its own _lock. This probe verifies that
    # serialization holds under N concurrent callers — which is
    # the actual production scenario (multiple surfaces sending
    # user_message turns through the same daemon writer).
    barrier = threading.Barrier(count)
    results: list[Any] = [None] * count

    with _writes_enabled():
        shared_writer = _writer.LedgerWriter(probe_db_path)

        def worker(i: int) -> None:
            barrier.wait()  # all start at once
            results[i] = shared_writer.write_turn(
                kind, template.format(i=i),
                **_stamp_for_synthetic_kind(kind, models_owner_text=kind == "user_message"),
            )

        try:
            with ThreadPoolExecutor(max_workers=count) as ex:
                list(ex.map(worker, range(count)))
        finally:
            shared_writer.close()

    none_count = sum(1 for r in results if r is None)
    if none_count > 0:
        return ProbeResult(
            probe.id, probe.category, "FAIL",
            f"{none_count}/{count} writes returned None (writer disabled?)",
            {"none_count": none_count},
        )

    with contextlib.closing(sqlite3.connect(probe_db_path)) as conn, conn:
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM turns WHERE turn_kind=? "
            "ORDER BY rowid ASC", (kind,)
        ).fetchall()]
    if len(rows) != expected_total:
        return ProbeResult(
            probe.id, probe.category, "FAIL",
            f"expected {expected_total} rows, got {len(rows)}",
            {"rows_count": len(rows)},
        )
    # Chain verifier wants ALL rows, not just user_message.
    with contextlib.closing(sqlite3.connect(probe_db_path)) as conn, conn:
        conn.row_factory = sqlite3.Row
        all_rows = [dict(r) for r in conn.execute(
            "SELECT * FROM turns ORDER BY rowid ASC"
        ).fetchall()]
    violations = _chain.verify_chain(all_rows)
    if violations:
        return ProbeResult(
            probe.id, probe.category, "FAIL",
            f"chain violations: {violations!r}",
            {"chain_violations": len(violations)},
        )
    return ProbeResult(
        probe.id, probe.category, "PASS",
        f"{count} concurrent writes serialized, chain clean",
        {"rows_count": len(rows), "chain_violations": 0},
    )


def _run_multi_turn_self_history_probe(
    probe: Probe, *, probe_db_path: str,
) -> ProbeResult:
    """multi_turn_self_history — mix gestation + lived rows, verify
    two-tier sort puts lived rows ahead, and the prompt label
    surfaces on gestation entries."""
    writes = probe.raw.get("synthetic_writes_with_lifecycle", [])
    expected_label = probe.raw.get("expected_prompt_label_substring", "pre-birth")
    expected_lived_min = int(
        probe.raw.get("expected_self_history_first_kind_lived_count_min", 0)
    )

    # Set birth marker BEFORE writing lived rows so writer tags
    # them correctly.
    with _writes_enabled():
        # Phase 1: write gestation rows (no birth marker set).
        w = _writer.LedgerWriter(probe_db_path)
        try:
            for entry in writes:
                if entry.get("lifecycle_stage") != "gestation":
                    continue
                w.write_turn(
                    "model_reply", entry["text"],
                    surface=entry.get("surface", "UI"),
                    **_stamp_for_synthetic_kind("model_reply"),
                    model_id="qwen36-27b",
                    prompt_hash="p" * 64, soul_hash="s" * 64,
                    evidence_envelope={"claimable": [], "forbidden": []},
                    audit_verdict={"verdict": "grounded"},
                )
        finally:
            w.close()

        # Phase 2: set birth, write lived rows.
        with contextlib.closing(sqlite3.connect(probe_db_path)) as conn, conn:
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) "
                "VALUES('birth_event_turn_id', 'probe-birth-marker')"
            )
            conn.commit()
        w = _writer.LedgerWriter(probe_db_path)
        try:
            for entry in writes:
                if entry.get("lifecycle_stage") != "lived":
                    continue
                w.write_turn(
                    "model_reply", entry["text"],
                    surface=entry.get("surface", "UI"),
                    **_stamp_for_synthetic_kind("model_reply"),
                    model_id="qwen36-27b",
                    prompt_hash="p" * 64, soul_hash="s" * 64,
                    evidence_envelope={"claimable": [], "forbidden": []},
                    audit_verdict={"verdict": "grounded"},
                )
        finally:
            w.close()

    # Recall path: default 'user' downweights gestation behind lived.
    sh = _eb.BoundedEnvelopeBuilder()._populate_self_history(
        probe_db_path, limit=10, tenant_id="owner",
        recall_gestation="user",
    )
    # First N entries should be lived.
    first_n_stages = [e.get("lifecycle_stage") for e in sh[:expected_lived_min]]
    if first_n_stages.count("lived") < expected_lived_min:
        return ProbeResult(
            probe.id, probe.category, "FAIL",
            f"expected first {expected_lived_min} entries to be lived, "
            f"got stages={first_n_stages}",
            {"first_n_stages": first_n_stages},
        )
    # Render the prompt block; gestation entries should carry the label.
    from core.cognition import grounding_judge as gj
    prompt = gj._build_judge_prompt(
        text="any", signals_present=[], signals_absent=[],
        few_shots=[], self_history=sh,
    )
    if expected_label not in prompt.lower():
        return ProbeResult(
            probe.id, probe.category, "FAIL",
            f"expected label substring {expected_label!r} not in prompt",
            {"sh_count": len(sh)},
        )
    return ProbeResult(
        probe.id, probe.category, "PASS",
        f"two-tier sort + label render correct ({len(sh)} entries)",
        {"sh_count": len(sh)},
    )


_RUNNERS: dict[str, Callable[..., ProbeResult]] = {
    "multi_turn_continuity":     _run_continuity_probe,
    "surface_interleaving":      _run_interleaving_probe,
    "real_content_claims":       _run_real_claims_probe,
    "envelope_pressure":         _run_envelope_pressure_probe,
    "concurrency":               _run_concurrency_probe,
    "multi_turn_self_history":   _run_multi_turn_self_history_probe,
}


@contextlib.contextmanager
def _writes_enabled():
    """Enable ledger writes via env var for the duration of a probe.
    The harness toggles this per-probe rather than globally so a
    stray write outside a probe runner can't accidentally land."""
    prev = os.environ.get("MAEZ_LEDGER_WRITES")
    os.environ["MAEZ_LEDGER_WRITES"] = "1"
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop("MAEZ_LEDGER_WRITES", None)
        else:
            os.environ["MAEZ_LEDGER_WRITES"] = prev


# ── public API ────────────────────────────────────────────────────────


def run_probe(
    probe: Probe, *, probe_db_path: str, mode: str = "birth_readiness",
) -> ProbeResult:
    """Run a single probe against an isolated probe ledger DB."""
    runner = _RUNNERS.get(probe.category)
    if runner is None:
        return ProbeResult(
            probe.id, probe.category, "FLAG",
            f"no runner for category {probe.category!r}",
            {},
        )
    try:
        return runner(probe, probe_db_path=probe_db_path)
    except Exception as e:
        return ProbeResult(
            probe.id, probe.category, "FAIL",
            f"runner raised: {type(e).__name__}: {e}",
            {"exception": type(e).__name__},
        )


def _default_probe_db_factory(name: str) -> str:
    tmpdir = tempfile.mkdtemp(prefix="maez_replay_harness_")
    path = Path(tmpdir) / f"{name}.db"
    _migrate.run(str(path))
    return str(path)


def run_corpus(
    *,
    corpus_path: str | Path,
    probe_db_factory: Callable[[str], str] | None = None,
    mode: str = "birth_readiness",
) -> CorpusReport:
    """Run every probe in the corpus, return a CorpusReport."""
    probes = load_probes(corpus_path)
    factory = probe_db_factory or _default_probe_db_factory
    results: list[ProbeResult] = []
    started = time.time()
    for p in probes:
        db = factory(p.id)
        results.append(run_probe(p, probe_db_path=db, mode=mode))
    finished = time.time()
    pass_count = sum(1 for r in results if r.verdict == "PASS")
    if pass_count == len(results):
        overall = "PASS"
    elif pass_count == 0:
        overall = "FAIL"
    else:
        overall = "PARTIAL"
    gap = sum(1 for r in results if r.verdict != "PASS")
    return CorpusReport(
        mode=mode, results=results, overall=overall,
        gap_to_birth=gap, started_at=started, finished_at=finished,
    )


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(_REPO),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def _git_dirty() -> bool:
    """Return True when tracked files differ from HEAD/index.

    Untracked artifacts are intentionally ignored. Rohit's workstation
    often has local generated assets; baseline writes should refuse
    uncommitted tracked behavior changes, not unrelated untracked files.
    """
    unstaged = subprocess.run(
        ["git", "diff", "--quiet"],
        cwd=str(_REPO),
        check=False,
    ).returncode
    staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=str(_REPO),
        check=False,
    ).returncode
    return unstaged != 0 or staged != 0


def _load_baseline(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        raise RegressionBaselineError(f"baseline file not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise RegressionBaselineError(f"malformed baseline: {e}") from e
    if not isinstance(data, dict):
        raise RegressionBaselineError("malformed baseline: expected object")
    version = data.get("schema_version")
    if version != _BASELINE_SCHEMA_VERSION:
        raise RegressionBaselineError(
            f"unsupported baseline schema_version={version!r}; "
            f"expected {_BASELINE_SCHEMA_VERSION}"
        )
    return data


def _require_regression_tolerance(probe: Probe, result: ProbeResult) -> dict:
    tolerance = probe.raw.get("regression_tolerance")
    if not isinstance(tolerance, dict):
        raise RegressionBaselineError(
            f"probe {probe.id}: missing regression_tolerance"
        )
    metrics_tol = tolerance.get("metrics")
    if result.metrics and not isinstance(metrics_tol, dict):
        raise RegressionBaselineError(
            f"probe {probe.id}: missing regression_tolerance.metrics"
        )
    for metric in result.metrics:
        if metric not in metrics_tol:
            raise RegressionBaselineError(
                f"probe {probe.id}: missing regression_tolerance for metric {metric!r}"
            )
    return tolerance


def _metric_satisfies(
    *,
    metric: str,
    baseline_value: Any,
    current_value: Any,
    spec: dict,
) -> tuple[bool, str]:
    op = spec.get("op", "exact")
    if op == "exact":
        ok = current_value == baseline_value
        return ok, f"metric {metric} expected {baseline_value!r}, got {current_value!r}"
    if op == "min":
        floor = spec.get("value", baseline_value)
        expected = max(floor, baseline_value)
        ok = current_value >= expected
        return ok, f"metric {metric} expected >= {expected!r}, got {current_value!r}"
    if op == "max":
        ceiling = spec.get("value", baseline_value)
        expected = min(ceiling, baseline_value)
        ok = current_value <= expected
        return ok, f"metric {metric} expected <= {expected!r}, got {current_value!r}"
    if op == "range":
        bounds = spec.get("value", [])
        low, high = bounds if isinstance(bounds, list | tuple) and len(bounds) == 2 else (None, None)
        ok = low is not None and high is not None and low <= current_value <= high
        return ok, f"metric {metric} expected in [{low!r}, {high!r}], got {current_value!r}"
    if op == "contains":
        required = spec.get("value", [])
        if not isinstance(required, list):
            required = [required]
        if isinstance(current_value, dict):
            haystack = set(current_value)
        elif isinstance(current_value, list | tuple | set):
            haystack = set(current_value)
        else:
            haystack = {current_value}
        missing = [v for v in required if v not in haystack]
        ok = not missing
        return ok, f"metric {metric} missing required values {missing!r}"
    return False, f"metric {metric} has unsupported tolerance op {op!r}"


def _run_current_results(
    *,
    corpus_path: str | Path,
) -> tuple[dict[str, ProbeDefinition], dict[str, ProbeResult]]:
    definitions = load_probe_definitions(corpus_path)
    results: dict[str, ProbeResult] = {}
    for probe_id, definition in definitions.items():
        db = _default_probe_db_factory(probe_id)
        results[probe_id] = run_probe(
            definition.probe,
            probe_db_path=db,
            mode="regression",
        )
    return definitions, results


def write_regression_baseline(
    *,
    corpus_path: str | Path,
    baseline_path: str | Path,
    reason: str,
) -> RegressionReport:
    if not reason.strip():
        raise RegressionBaselineError("--reason is required for --baseline write")
    if _git_dirty():
        raise RegressionBaselineError(
            "dirty working tree; commit or discard tracked changes before writing baseline"
        )
    definitions, results = _run_current_results(corpus_path=corpus_path)
    probes: dict[str, dict] = {}
    for probe_id, definition in definitions.items():
        result = results[probe_id]
        if result.verdict != "PASS":
            raise RegressionBaselineError(
                f"refusing to write baseline with failing probe {probe_id}: "
                f"{result.verdict} — {result.reason}"
            )
        _require_regression_tolerance(definition.probe, result)
        probes[probe_id] = {
            "category": result.category,
            "verdict": result.verdict,
            "observed_metrics": result.metrics,
            "probe_definition_sha256": definition.sha256,
        }
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    commit = _git_commit()
    existing_history: list[dict] = []
    if Path(baseline_path).exists():
        existing = _load_baseline(baseline_path)
        history = existing.get("regen_history")
        if isinstance(history, list):
            if not all(isinstance(h, dict) for h in history):
                raise RegressionBaselineError(
                    "malformed baseline: regen_history entries must be objects"
                )
            existing_history = list(history)
        else:
            raise RegressionBaselineError(
                "malformed baseline: regen_history must be a list"
            )
    new_history_entry = {
        "commit": commit,
        "date": now,
        "reason": reason.strip(),
    }
    data = {
        "schema_version": _BASELINE_SCHEMA_VERSION,
        "created_at": now,
        "source_commit": commit,
        "dirty_tree": False,
        "mode": "regression",
        "probe_corpus_path": str(Path(corpus_path)),
        "probe_corpus_sha256": probe_corpus_sha256(corpus_path),
        "decoder_note": (
            "Baseline captures replay-harness probe health and stable metrics, "
            "not exact model prose. dirty_tree reflects tracked Git changes; "
            "untracked local artifacts are ignored. Probe definitions own "
            "regression_tolerance; the baseline stores observed health values "
            "and hashes so contract drift and behavior drift stay separate."
        ),
        "last_regen_reason": reason.strip(),
        "regen_history": [*existing_history, new_history_entry],
        "probes": probes,
    }
    p = Path(baseline_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return RegressionReport(
        baseline_path=str(p),
        corpus_path=str(corpus_path),
        overall="PASS",
        drifts=[],
        baseline=data,
        operation="write",
    )


def check_regression_baseline(
    *,
    corpus_path: str | Path,
    baseline_path: str | Path,
) -> RegressionReport:
    baseline = _load_baseline(baseline_path)
    current_defs, current_results = _run_current_results(corpus_path=corpus_path)
    drifts: list[RegressionDrift] = []

    baseline_probes = baseline.get("probes")
    if not isinstance(baseline_probes, dict):
        raise RegressionBaselineError("malformed baseline: missing probes object")

    current_corpus_hash = probe_corpus_sha256(corpus_path)
    if baseline.get("probe_corpus_sha256") != current_corpus_hash:
        baseline_ids = set(baseline_probes)
        current_ids = set(current_defs)
        added = sorted(current_ids - baseline_ids)
        removed = sorted(baseline_ids - current_ids)
        modified = sorted(
            pid for pid in (current_ids & baseline_ids)
            if baseline_probes[pid].get("probe_definition_sha256")
            != current_defs[pid].sha256
        )
        reason = (
            "probe_corpus_changed "
            f"added={added or ['none']} "
            f"removed={removed or ['none']} "
            f"modified={modified or ['none']}"
        )
        drifts.append(RegressionDrift("probe_corpus", "DRIFT", reason))

    for probe_id in sorted(set(baseline_probes) | set(current_results)):
        prior = baseline_probes.get(probe_id)
        current = current_results.get(probe_id)
        if prior is None:
            drifts.append(RegressionDrift(probe_id, "NEW", "probe missing from baseline"))
            continue
        if current is None:
            drifts.append(RegressionDrift(probe_id, "MISSING", "probe missing from current corpus"))
            continue
        if prior.get("category") != current.category:
            drifts.append(RegressionDrift(
                probe_id, "DRIFT",
                f"category expected {prior.get('category')!r}, got {current.category!r}",
            ))
        if prior.get("verdict") != current.verdict:
            drifts.append(RegressionDrift(
                probe_id, "DRIFT",
                f"verdict expected {prior.get('verdict')!r}, got {current.verdict!r}",
            ))
        prior_metrics = prior.get("observed_metrics") or {}
        if not isinstance(prior_metrics, dict):
            raise RegressionBaselineError(
                f"malformed baseline: probe {probe_id} observed_metrics must be object"
            )
        tolerance = _require_regression_tolerance(current_defs[probe_id].probe, current)
        metrics_tol = tolerance.get("metrics", {})
        metric_keys = sorted(set(prior_metrics) | set(current.metrics))
        for metric in metric_keys:
            if metric not in current.metrics:
                drifts.append(RegressionDrift(
                    probe_id,
                    "DRIFT",
                    f"metric {metric} missing from current result "
                    f"(baseline had {prior_metrics.get(metric)!r})",
                ))
                continue
            if metric not in prior_metrics:
                drifts.append(RegressionDrift(
                    probe_id,
                    "DRIFT",
                    f"metric {metric} missing from baseline "
                    f"(current has {current.metrics.get(metric)!r})",
                ))
                continue
            current_value = current.metrics[metric]
            if metric not in metrics_tol:
                raise RegressionBaselineError(
                    f"probe {probe_id}: missing regression_tolerance for metric {metric!r}"
                )
            baseline_value = prior_metrics.get(metric)
            ok, reason = _metric_satisfies(
                metric=metric,
                baseline_value=baseline_value,
                current_value=current_value,
                spec=metrics_tol[metric],
            )
            if not ok:
                drifts.append(RegressionDrift(probe_id, "DRIFT", reason))

    overall = "PASS" if not drifts else "DRIFT"
    return RegressionReport(
        baseline_path=str(baseline_path),
        corpus_path=str(corpus_path),
        overall=overall,
        drifts=drifts,
        baseline=baseline,
    )


def format_report(report: CorpusReport) -> str:
    lines = [
        "=" * 70,
        f"BIRTH-READINESS PROBE REPORT  (mode={report.mode})",
        "=" * 70,
        f"started_at:   {time.ctime(report.started_at)}",
        f"finished_at:  {time.ctime(report.finished_at)}",
        f"duration:     {report.finished_at - report.started_at:.2f}s",
        f"overall:      {report.overall}",
        f"gap_to_birth: {report.gap_to_birth} probe(s) not PASS",
        "",
        "─" * 70,
        "Per-probe verdict",
        "─" * 70,
    ]
    for r in report.results:
        lines.append(
            f"  [{r.verdict:4s}] {r.category:28s} {r.probe_id}"
        )
        lines.append(f"         {r.reason}")
    lines.append("=" * 70)
    return "\n".join(lines)


def format_regression_report(report: RegressionReport) -> str:
    baseline = report.baseline or {}
    if report.operation == "write":
        lines = [
            "=" * 70,
            "REGRESSION BASELINE WRITTEN",
            "=" * 70,
            f"baseline:      {report.baseline_path}",
            f"corpus:        {report.corpus_path}",
            f"schema:        {baseline.get('schema_version', '-')}",
            f"source_commit: {baseline.get('source_commit', '-')}",
            f"reason:        {baseline.get('last_regen_reason', '-')}",
            f"probe_count:   {len(baseline.get('probes') or {})}",
            "",
            "This writes the reference point; it is not a no-drift check.",
            "=" * 70,
        ]
        return "\n".join(lines)

    lines = [
        "=" * 70,
        "REGRESSION BASELINE REPORT",
        "=" * 70,
        f"baseline:      {report.baseline_path}",
        f"corpus:        {report.corpus_path}",
        f"schema:        {baseline.get('schema_version', '-')}",
        f"source_commit: {baseline.get('source_commit', '-')}",
        f"overall:      {report.overall}",
        "",
    ]
    if not report.drifts:
        probe_count = len(baseline.get("probes") or {})
        lines.append(
            f"No drift detected across {probe_count} probe(s). "
            "This checks stable probe metrics/contracts, not exact model prose."
        )
    else:
        lines.append("Drift")
        lines.append("─" * 70)
        for drift in report.drifts:
            lines.append(f"  [{drift.status}] {drift.probe_id}")
            lines.append(f"         {drift.reason}")
    lines.append("=" * 70)
    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the Maez birth-readiness probe corpus.",
    )
    parser.add_argument(
        "--corpus", type=str,
        default=str(_REPO / "tests" / "probes" / "birth_readiness_corpus.jsonl"),
        help="Path to the JSONL probe corpus.",
    )
    parser.add_argument(
        "--mode", type=str, default="birth_readiness",
        choices=("birth_readiness", "regression"),
        help="Comparison mode (default: birth_readiness).",
    )
    parser.add_argument(
        "--baseline", type=str, default=None,
        choices=("check", "write"),
        help="Regression baseline operation. Required with --mode regression.",
    )
    parser.add_argument(
        "--baseline-path", type=str,
        default=str(_DEFAULT_BASELINE_PATH),
        help="Path to regression baseline JSON.",
    )
    parser.add_argument(
        "--reason", type=str, default=None,
        help="Required reason for --mode regression --baseline write.",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Write report to this path (default: stdout).",
    )
    args = parser.parse_args(argv)

    if args.mode == "regression":
        try:
            if args.baseline is None:
                raise RegressionBaselineError(
                    "--baseline {check,write} is required with --mode regression"
                )
            if args.baseline == "write":
                if not args.reason:
                    raise RegressionBaselineError(
                        "--reason is required for --baseline write"
                    )
                report = write_regression_baseline(
                    corpus_path=args.corpus,
                    baseline_path=args.baseline_path,
                    reason=args.reason,
                )
            else:
                report = check_regression_baseline(
                    corpus_path=args.corpus,
                    baseline_path=args.baseline_path,
                )
            text = format_regression_report(report)
            if args.output:
                Path(args.output).write_text(text + "\n")
            else:
                print(text)
            return 0 if report.overall == "PASS" else 1
        except RegressionBaselineError as e:
            print(f"regression baseline error: {e}", file=sys.stderr)
            return 2

    report = run_corpus(corpus_path=args.corpus, mode=args.mode)
    text = format_report(report)
    if args.output:
        Path(args.output).write_text(text + "\n")
    else:
        print(text)
    return 0 if report.overall == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
