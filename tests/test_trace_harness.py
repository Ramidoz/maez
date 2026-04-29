# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Slice-2 deterministic trace harness contract tests.

Pins:
- The deterministic checks each emit a finding when violated and
  emit nothing on a clean trace.
- Every finding carries provenance: trace_id, file, line, json_path,
  matched_value, reason. No exceptions.
- Trace files are UTC-dated; selection globs ``logs/traces/*.jsonl``
  and uses mtime-newest-first, NOT today's local date.
- Latest-N selection picks newest traces across multiple files.
- ``--trace-file`` overrides the glob.
- The track_a_harness gains an ``--include-trace-checks`` advisory
  tier (source-level wiring check; full integration is run end-to-end
  separately).
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _trace(
    *,
    trace_id: str = "tr-test1",
    surface: str = "UI",
    final: str = "x",
    sent: str | None = None,
    stored: str | None = None,
    audit_ran: bool = True,
    audit_changed: bool = False,
    terminal: str = "replied",
    latency_ms: int = 100,
    tool_calls: list[dict] | None = None,
    final_excerpt: str = "",
) -> dict:
    """Build a minimally-shaped trace dict matching the Slice-1 schema."""
    h = lambda s: s  # noqa: E731 — tests treat hashes as opaque tokens
    return {
        "trace_id": trace_id,
        "created_at": "2026-04-29T02:00:00+00:00",
        "surface": surface,
        "user_text": "test",
        "memory_ids": [],
        "lived_recall_ids": [],
        "tool_calls": tool_calls or [],
        "audit": {
            "ran": audit_ran,
            "changed_output": audit_changed,
            "flags": [],
            "error": "",
        },
        "final_text_excerpt": final_excerpt or final,
        "final_text_hash": h(final),
        "sent_text_hash": h(sent if sent is not None else final),
        "stored_text_hash": h(stored if stored is not None else final),
        "latency_ms": latency_ms,
        "terminal_state": terminal,
        "error": "",
    }


class HashInvariantCheck(unittest.TestCase):
    """final == sent == stored. Unequal hashes are a real signal that
    audit-before-store was bypassed somewhere."""

    def test_clean_trace_passes(self):
        from scripts.validate.trace_harness import check_hash_invariant

        f = check_hash_invariant(_trace(final="abc"), file="x", line=1)
        self.assertEqual(f, [])

    def test_stored_differs_from_final_fails(self):
        from scripts.validate.trace_harness import check_hash_invariant

        findings = check_hash_invariant(
            _trace(final="abc", stored="DIFFERENT"),
            file="logs/traces/x.jsonl",
            line=42,
        )
        self.assertEqual(len(findings), 1)
        f = findings[0]
        self.assertEqual(f.verdict, "FAIL")
        self.assertEqual(f.check, "hash_invariant")
        self.assertEqual(f.trace_id, "tr-test1")
        self.assertEqual(f.file, "logs/traces/x.jsonl")
        self.assertEqual(f.line, 42)
        self.assertIn("stored_text_hash", f.json_path)
        self.assertIn("audit-before-store", f.reason.lower())

    def test_sent_differs_from_final_fails(self):
        from scripts.validate.trace_harness import check_hash_invariant

        findings = check_hash_invariant(
            _trace(final="abc", sent="OTHER"),
            file="x",
            line=1,
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].verdict, "FAIL")


class AuditRequiredCheck(unittest.TestCase):
    """Owner-facing surfaces must have audit.ran == True unless the
    turn errored out. The errored exception exists because audit can't
    run on a non-existent reply."""

    def test_owner_surface_audit_ran_passes(self):
        from scripts.validate.trace_harness import check_audit_required

        f = check_audit_required(
            _trace(surface="UI", audit_ran=True),
            file="x",
            line=1,
            owner_surfaces={"UI", "telegram_surface"},
        )
        self.assertEqual(f, [])

    def test_owner_surface_audit_skipped_fails(self):
        from scripts.validate.trace_harness import check_audit_required

        findings = check_audit_required(
            _trace(surface="UI", audit_ran=False),
            file="x",
            line=1,
            owner_surfaces={"UI", "telegram_surface"},
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].verdict, "FAIL")
        self.assertEqual(findings[0].check, "audit_required")
        self.assertEqual(findings[0].json_path, "audit.ran")

    def test_errored_turn_skipped_audit_passes(self):
        from scripts.validate.trace_harness import check_audit_required

        f = check_audit_required(
            _trace(surface="UI", audit_ran=False, terminal="errored"),
            file="x",
            line=1,
            owner_surfaces={"UI"},
        )
        self.assertEqual(f, [])

    def test_non_owner_surface_audit_skipped_passes(self):
        """Daemon-internal surfaces aren't required to run audit."""
        from scripts.validate.trace_harness import check_audit_required

        f = check_audit_required(
            _trace(surface="daemon_cycle", audit_ran=False),
            file="x",
            line=1,
            owner_surfaces={"UI", "telegram_surface"},
        )
        self.assertEqual(f, [])


class TerminalStateCheck(unittest.TestCase):
    """terminal_state must be set explicitly, never empty, and match
    the known vocabulary so a future analyzer can bucket cleanly."""

    def test_known_states_pass(self):
        from scripts.validate.trace_harness import check_terminal_state

        for s in ("replied", "errored", "timed_out", "denied"):
            with self.subTest(s=s):
                self.assertEqual(
                    check_terminal_state(_trace(terminal=s), file="x", line=1),
                    [],
                )

    def test_empty_terminal_state_fails(self):
        from scripts.validate.trace_harness import check_terminal_state

        findings = check_terminal_state(_trace(terminal=""), file="x", line=1)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].verdict, "FAIL")

    def test_unknown_terminal_state_fails(self):
        from scripts.validate.trace_harness import check_terminal_state

        findings = check_terminal_state(_trace(terminal="finished"), file="x", line=1)
        self.assertEqual(len(findings), 1)


class LatencyCheck(unittest.TestCase):
    def test_below_threshold_passes(self):
        from scripts.validate.trace_harness import check_latency

        self.assertEqual(
            check_latency(_trace(latency_ms=5_000), file="x", line=1, warn_ms=30_000),
            [],
        )

    def test_above_threshold_warns(self):
        from scripts.validate.trace_harness import check_latency

        findings = check_latency(
            _trace(latency_ms=45_000),
            file="x",
            line=1,
            warn_ms=30_000,
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].verdict, "WARN")
        self.assertEqual(findings[0].check, "latency")


class NonterminatingToolCheck(unittest.TestCase):
    """Tools that don't terminate by themselves are forbidden in the
    action engine. If one shows up in tool_calls with status=ok, the
    pipeline let it through."""

    def test_clean_tool_passes(self):
        from scripts.validate.trace_harness import check_nonterminating_tool

        t = _trace(tool_calls=[{"name": "run_shell", "args_summary": "ls /home", "status": "ok"}])
        self.assertEqual(check_nonterminating_tool(t, file="x", line=1), [])

    def test_tail_f_executed_fails(self):
        from scripts.validate.trace_harness import check_nonterminating_tool

        t = _trace(
            tool_calls=[
                {"name": "run_shell", "args_summary": "tail -f /var/log/syslog", "status": "ok"}
            ]
        )
        findings = check_nonterminating_tool(t, file="x", line=1)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].verdict, "FAIL")
        self.assertIn("tail -f", findings[0].matched_value)

    def test_nvidia_smi_loop_executed_fails(self):
        from scripts.validate.trace_harness import check_nonterminating_tool

        for arg in ("nvidia-smi -l 1", "nvidia-smi -lms 500", "nvidia-smi --loop=2"):
            with self.subTest(arg=arg):
                t = _trace(tool_calls=[{"name": "run_shell", "args_summary": arg, "status": "ok"}])
                findings = check_nonterminating_tool(t, file="x", line=1)
                self.assertEqual(len(findings), 1, f"failed to flag {arg!r}")

    def test_strace_p_without_c_fails(self):
        from scripts.validate.trace_harness import check_nonterminating_tool

        t = _trace(tool_calls=[{"name": "run_shell", "args_summary": "strace -p 1234", "status": "ok"}])
        findings = check_nonterminating_tool(t, file="x", line=1)
        self.assertEqual(len(findings), 1)

    def test_strace_p_with_c_passes(self):
        """`-c` collects stats and exits — terminating."""
        from scripts.validate.trace_harness import check_nonterminating_tool

        t = _trace(tool_calls=[
            {"name": "run_shell", "args_summary": "strace -p 1234 -c", "status": "ok"}
        ])
        self.assertEqual(check_nonterminating_tool(t, file="x", line=1), [])

    def test_denied_tool_passes(self):
        """Covenant-rejected `nvidia-smi -l` is a PASS — the gate
        worked. Only executed (status=ok) calls are FAILs."""
        from scripts.validate.trace_harness import check_nonterminating_tool

        t = _trace(tool_calls=[
            {"name": "run_shell", "args_summary": "nvidia-smi -l 1", "status": "denied"}
        ])
        self.assertEqual(check_nonterminating_tool(t, file="x", line=1), [])


class TimeoutHonestyCheck(unittest.TestCase):
    """If a tool timed out, the final excerpt must NOT claim success."""

    def test_no_timeout_passes(self):
        from scripts.validate.trace_harness import check_timeout_honesty

        t = _trace(
            tool_calls=[{"name": "run_shell", "args_summary": "ls", "status": "ok"}],
            final_excerpt="Listed files.",
        )
        self.assertEqual(check_timeout_honesty(t, file="x", line=1), [])

    def test_timeout_admitted_passes(self):
        from scripts.validate.trace_harness import check_timeout_honesty

        t = _trace(
            tool_calls=[{"name": "run_shell", "args_summary": "slow", "status": "timeout"}],
            final_excerpt="The command timed out before I could read the result.",
        )
        self.assertEqual(check_timeout_honesty(t, file="x", line=1), [])

    def test_timeout_hidden_as_success_fails(self):
        from scripts.validate.trace_harness import check_timeout_honesty

        t = _trace(
            tool_calls=[{"name": "run_shell", "args_summary": "slow", "status": "timeout"}],
            final_excerpt="The operation completed successfully and the file is updated.",
        )
        findings = check_timeout_honesty(t, file="x", line=1)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].verdict, "FAIL")


class ToolAccessSelfDenialCheck(unittest.TestCase):
    """A tool-capable surface must not convert "no tools ran this turn"
    into "I have no tool loop here."
    """

    def test_telegram_tool_loop_denial_fails(self):
        from scripts.validate.trace_harness import check_tool_access_self_denial

        t = _trace(
            surface="telegram_surface",
            final_excerpt=(
                "I haven't built it yet. I don't have a tool loop on this "
                "channel to write the file directly."
            ),
        )
        findings = check_tool_access_self_denial(t, file="x", line=1)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].verdict, "FAIL")
        self.assertEqual(findings[0].check, "tool_access_self_denial")
        self.assertIn("tool-capable", findings[0].reason)

    def test_manual_save_instruction_on_telegram_fails(self):
        from scripts.validate.trace_harness import check_tool_access_self_denial

        t = _trace(
            surface="telegram_surface",
            final_excerpt="Here is the code. Save it to /home/rohit/maez/ui/x.html.",
        )
        findings = check_tool_access_self_denial(t, file="x", line=1)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].verdict, "FAIL")
        self.assertIn("Save it to /home", findings[0].matched_value)

    def test_honest_no_tool_turn_passes(self):
        from scripts.validate.trace_harness import check_tool_access_self_denial

        t = _trace(
            surface="telegram_surface",
            final_excerpt=(
                "I haven't made that change yet. I can try the tool path "
                "if you want."
            ),
        )
        self.assertEqual(check_tool_access_self_denial(t, file="x", line=1), [])

    def test_synthesis_only_surface_not_failed(self):
        from scripts.validate.trace_harness import check_tool_access_self_denial

        t = _trace(
            surface="UI",
            final_excerpt="I don't have a tool loop on this channel.",
        )
        self.assertEqual(check_tool_access_self_denial(t, file="x", line=1), [])


class StaleClaimsCheck(unittest.TestCase):
    """Runtime ground-truth-backed stale-claim detection."""

    def _gt(self, **facts):
        from core.turn_traces.ground_truth import GroundTruthFact, GroundTruthSnapshot

        defaults = {
            "vision_available": GroundTruthFact(
                name="vision_available",
                value=False,
                ok=True,
                source="test vision probe",
                detail="MAEZ_SCREEN_PERCEPTION=''",
            ),
            "judge_active": GroundTruthFact(
                name="judge_active",
                value=False,
                ok=True,
                source="test judge probe",
                detail="inactive",
            ),
            "current_model": GroundTruthFact(
                name="current_model",
                value="qwen36-27b",
                ok=True,
                source="test model probe",
            ),
        }
        defaults.update(facts)
        return GroundTruthSnapshot(defaults)

    def test_no_stale_claim_passes(self):
        from scripts.validate.trace_harness import check_stale_claims

        t = _trace(final_excerpt="The model running is qwen36-27b.")
        self.assertEqual(
            check_stale_claims(
                t, file="x", line=1, ground_truth=self._gt(),
            ),
            [],
        )

    def test_vision_claim_contradicted_by_ground_truth_fails(self):
        from scripts.validate.trace_harness import check_stale_claims

        t = _trace(final_excerpt="The vision pipeline runs via llama-server-vision.service.")
        findings = check_stale_claims(
            t, file="x", line=1, ground_truth=self._gt(),
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].verdict, "FAIL")
        self.assertEqual(findings[0].check, "stale_claims")
        self.assertIn("vision_available=False", findings[0].reason)
        self.assertIn("test vision probe", findings[0].reason)

    def test_active_judge_claim_contradicted_by_ground_truth_fails(self):
        from scripts.validate.trace_harness import check_stale_claims

        t = _trace(final_excerpt="The llama-judge.service is active and checking replies.")
        findings = check_stale_claims(
            t, file="x", line=1, ground_truth=self._gt(),
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].verdict, "FAIL")
        self.assertIn("judge_active=False", findings[0].reason)

    def test_disabled_vision_statement_does_not_fail(self):
        from scripts.validate.trace_harness import check_stale_claims

        t = _trace(final_excerpt="Screen perception is disabled and vision is unavailable.")
        self.assertEqual(
            check_stale_claims(
                t, file="x", line=1, ground_truth=self._gt(),
            ),
            [],
        )

    def test_retired_judge_statement_does_not_fail(self):
        from scripts.validate.trace_harness import check_stale_claims

        t = _trace(final_excerpt="llama-judge.service is retired and inactive.")
        self.assertEqual(
            check_stale_claims(
                t, file="x", line=1, ground_truth=self._gt(),
            ),
            [],
        )

    def test_current_gemma_claim_contradicted_by_model_probe_fails(self):
        from scripts.validate.trace_harness import check_stale_claims

        t = _trace(final_excerpt="My current brain model is gemma-4-26b.")
        findings = check_stale_claims(
            t, file="x", line=1, ground_truth=self._gt(),
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].verdict, "FAIL")
        self.assertIn("current_model='qwen36-27b'", findings[0].reason)

    def test_historical_gemma_mention_does_not_fail(self):
        from scripts.validate.trace_harness import check_stale_claims

        t = _trace(final_excerpt="Gemma was a historical model reference, not my current brain.")
        self.assertEqual(
            check_stale_claims(
                t, file="x", line=1, ground_truth=self._gt(),
            ),
            [],
        )

    def test_unavailable_ground_truth_stays_silent(self):
        from core.turn_traces.ground_truth import GroundTruthFact
        from scripts.validate.trace_harness import check_stale_claims

        t = _trace(final_excerpt="The current brain model is gemma-4-26b.")
        gt = self._gt(
            current_model=GroundTruthFact(
                name="current_model",
                value="",
                ok=False,
                source="test model probe",
                detail="connection refused",
            )
        )
        self.assertEqual(
            check_stale_claims(t, file="x", line=1, ground_truth=gt),
            [],
        )


class FindingProvenance(unittest.TestCase):
    """Every finding emitted by every check must include trace_id,
    file, line, json_path, matched_value, reason. This is the harness
    embodying its own evidence covenant."""

    def test_every_check_emits_full_provenance(self):
        from scripts.validate.trace_harness import (
            check_audit_required,
            check_hash_invariant,
            check_latency,
            check_nonterminating_tool,
            check_stale_claims,
            check_terminal_state,
            check_timeout_honesty,
            check_tool_access_self_denial,
        )

        ALL_CHECKS = [
            (
                check_hash_invariant,
                _trace(final="a", stored="b"),
                {"file": "f", "line": 9},
            ),
            (
                check_audit_required,
                _trace(surface="UI", audit_ran=False),
                {"file": "f", "line": 9, "owner_surfaces": {"UI"}},
            ),
            (
                check_terminal_state,
                _trace(terminal=""),
                {"file": "f", "line": 9},
            ),
            (
                check_latency,
                _trace(latency_ms=999_999),
                {"file": "f", "line": 9, "warn_ms": 1000},
            ),
            (
                check_nonterminating_tool,
                _trace(tool_calls=[{"name": "run_shell", "args_summary": "tail -f x", "status": "ok"}]),
                {"file": "f", "line": 9},
            ),
            (
                check_timeout_honesty,
                _trace(
                    tool_calls=[{"name": "x", "args_summary": "y", "status": "timeout"}],
                    final_excerpt="completed successfully",
                ),
                {"file": "f", "line": 9},
            ),
            (
                check_tool_access_self_denial,
                _trace(
                    surface="telegram_surface",
                    final_excerpt="I don't have a tool loop on this channel.",
                ),
                {"file": "f", "line": 9},
            ),
            (
                check_stale_claims,
                _trace(final_excerpt="llama-server-vision is back online"),
                {
                    "file": "f",
                    "line": 9,
                    "ground_truth": StaleClaimsCheck()._gt(),
                },
            ),
        ]
        for fn, trace, kwargs in ALL_CHECKS:
            with self.subTest(check=fn.__name__):
                findings = fn(trace, **kwargs)
                self.assertGreaterEqual(
                    len(findings), 1,
                    f"{fn.__name__} should have produced a finding",
                )
                f = findings[0]
                for attr in (
                    "trace_id", "verdict", "check", "file", "line",
                    "json_path", "matched_value", "reason",
                ):
                    self.assertTrue(
                        hasattr(f, attr) and getattr(f, attr) is not None,
                        f"{fn.__name__} finding missing {attr!r}",
                    )


class TraceFileDiscovery(unittest.TestCase):
    """Trace files are UTC-dated. The discovery glob must NOT assume
    today's local date — globbing logs/traces/*.jsonl and sorting by
    mtime-newest-first works regardless of UTC/local skew."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _write_trace_file(self, name: str, n: int, age_seconds: float = 0):
        p = self.tmp_path / name
        with p.open("w") as f:
            for i in range(n):
                f.write(json.dumps(_trace(trace_id=f"{name}-{i}")) + "\n")
        if age_seconds > 0:
            mtime = time.time() - age_seconds
            import os
            os.utime(p, (mtime, mtime))
        return p

    def test_discovery_returns_jsonl_files(self):
        from scripts.validate.trace_harness import discover_trace_files

        self._write_trace_file("2026-04-28.jsonl", 2)
        self._write_trace_file("2026-04-29.jsonl", 3)
        self._write_trace_file("not_a_trace.txt", 1)

        files = discover_trace_files(self.tmp_path)
        names = sorted(p.name for p in files)
        self.assertEqual(names, ["2026-04-28.jsonl", "2026-04-29.jsonl"])

    def test_latest_n_picks_newest_across_files(self):
        from scripts.validate.trace_harness import select_latest_traces

        old = self._write_trace_file("2026-04-28.jsonl", 2, age_seconds=86400)
        new = self._write_trace_file("2026-04-29.jsonl", 3)

        # latest 4 → all 3 from new (lines 1,2,3) + 1 from old (line 2)
        traces = select_latest_traces([old, new], n=4)
        self.assertEqual(len(traces), 4)
        # Three items must come from the newer file.
        new_count = sum(1 for t in traces if t["__source__"]["file"].endswith("2026-04-29.jsonl"))
        self.assertEqual(new_count, 3)

    def test_explicit_trace_file_overrides_glob(self):
        from scripts.validate.trace_harness import select_latest_traces

        explicit = self._write_trace_file("2026-04-28.jsonl", 5)
        traces = select_latest_traces([explicit], n=10)
        self.assertEqual(len(traces), 5)
        for t in traces:
            self.assertEqual(t["__source__"]["file"], str(explicit))


class HarnessRunIntegration(unittest.TestCase):
    """End-to-end: feed a JSONL file with mixed clean/broken traces,
    run the harness's `run()`, assert summary and findings shape."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.traces_dir = self.tmp_path / "traces"
        self.traces_dir.mkdir()
        self.report_dir = self.tmp_path / "report"

    def tearDown(self):
        self._tmp.cleanup()

    def test_run_produces_pass_warn_fail_summary(self):
        from scripts.validate.trace_harness import run

        clean = _trace(trace_id="tr-clean", final="abc")
        broken_hash = _trace(trace_id="tr-bad-hash", final="abc", stored="OTHER")
        slow = _trace(trace_id="tr-slow", latency_ms=999_999, final="abc")
        path = self.traces_dir / "2026-04-29.jsonl"
        with path.open("w") as f:
            for t in (clean, broken_hash, slow):
                f.write(json.dumps(t) + "\n")

        report = run(
            trace_dir=self.traces_dir,
            trace_file=None,
            latest_n=10,
            owner_surfaces={"UI"},
            latency_warn_ms=30_000,
            report_dir=self.report_dir,
        )

        self.assertIn("findings", report)
        self.assertIn("summary", report)
        self.assertEqual(report["traces_scanned"], 3)
        # broken_hash → 1 FAIL; slow → 1 WARN; clean → 0 findings.
        verdicts = {f["verdict"] for f in report["findings"]}
        self.assertIn("FAIL", verdicts)
        self.assertIn("WARN", verdicts)

    def test_run_writes_latest_report_file(self):
        from scripts.validate.trace_harness import run

        path = self.traces_dir / "2026-04-29.jsonl"
        with path.open("w") as f:
            f.write(json.dumps(_trace()) + "\n")

        run(
            trace_dir=self.traces_dir,
            trace_file=None,
            latest_n=10,
            owner_surfaces={"UI"},
            latency_warn_ms=30_000,
            report_dir=self.report_dir,
        )

        latest = self.report_dir / "trace_harness_latest.json"
        self.assertTrue(latest.exists())
        # Round-trip parse to confirm it's valid JSON.
        parsed = json.loads(latest.read_text())
        self.assertIn("summary", parsed)


class TrackAHarnessWiring(unittest.TestCase):
    """Source-level check that --include-trace-checks is wired in.
    Mirrors the Phase 6 / Slice 1 wiring-test pattern: full subprocess
    integration is its own thing; here we just lock the surface."""

    def test_track_a_harness_imports_trace_check(self):
        src = (_REPO / "scripts" / "validate" / "track_a_harness.py").read_text()
        self.assertIn("--include-trace-checks", src)
        self.assertIn("check_trace_harness", src)


if __name__ == "__main__":
    unittest.main()
