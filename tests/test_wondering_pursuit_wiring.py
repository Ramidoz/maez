# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Wondering-pursuit daemon-wiring tests (Slice 2 Session 2).

Mirrors the shape of ``test_lived_recall_prompting.py`` — source-level
structural assertions on ``daemon/maez_daemon.py`` to lock the
contract for how pursuit gets wired into ``handle_message``. Mocking
the full pipeline would be heavy; the structural invariants are what
matter.

Tests cover:

- daemon imports ``decide_pursuit`` + ``format_pursuit_utterance``
- ``MAEZ_WONDERING_PURSUIT`` env var: default DISABLED, set ``"1"`` to
  enable. Same shape as ``MAEZ_WORKING_SELF`` (Slice 1 Session 3) —
  brand-new path, opt-in until probe-validated.
- ``identity.proactive_messages()`` policy gate is consulted —
  bonded-companion shape requires explicit operator opt-in beyond
  just the env knob.
- pursuit assembly is wrapped in ``try / except Exception`` for
  silent fail-open. Synthesis must never break because pursuit
  raised.
- Trace fields ``pursuit_decision`` / ``pursuit_score`` /
  ``pursuit_question`` / ``pursuit_components`` are written when
  pursuit runs.
- Sidecar load/save behaviour for last-pursuit-at frequency budget.

The Trace schema and pursuit module are exercised behaviourally
(real Trace.start() + module imports); the daemon source is
inspected with regex/substring assertions.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_DAEMON_SRC = (_REPO / "daemon" / "maez_daemon.py").read_text()


# ── Trace schema field presence ──────────────────────────────────────


class TraceCarriesPursuitFields(unittest.TestCase):
    """Pursuit decisions must be recorded on the Trace so the JSONL
    turn record answers 'did Maez decide to surface a wondering this
    turn, and why?' Mirrors the ``working_self_goals`` pattern."""

    def test_trace_has_pursuit_fields(self):
        from core.turn_traces.trace_schema import Trace

        t = Trace.start(surface="test")
        for field in (
            "pursuit_decision",
            "pursuit_score",
            "pursuit_question",
            "pursuit_components",
        ):
            self.assertTrue(hasattr(t, field),
                            f"Trace missing field: {field}")

    def test_pursuit_fields_default_empty(self):
        from core.turn_traces.trace_schema import Trace

        t = Trace.start(surface="test")
        self.assertEqual(t.pursuit_decision, "")
        self.assertEqual(t.pursuit_score, 0.0)
        self.assertEqual(t.pursuit_question, "")
        self.assertEqual(t.pursuit_components, {})

    def test_jsonl_serialises_pursuit_fields(self):
        from core.turn_traces.trace_schema import Trace

        t = Trace.start(surface="test")
        t.pursuit_decision = "surface"
        t.pursuit_score = 0.72
        t.pursuit_question = "how does continuity hold"
        t.pursuit_components = {
            "goal": 0.8, "recency": 1.0,
            "register": 0.9, "quality": 0.5,
        }
        loaded = json.loads(t.to_jsonl_line())
        self.assertEqual(loaded["pursuit_decision"], "surface")
        self.assertAlmostEqual(loaded["pursuit_score"], 0.72)
        self.assertEqual(loaded["pursuit_question"], "how does continuity hold")
        self.assertIn("goal", loaded["pursuit_components"])


# ── daemon imports ───────────────────────────────────────────────────


class DaemonImportsPursuit(unittest.TestCase):
    def test_imports_decide_pursuit(self):
        self.assertIn(
            "from core.evolution.wondering_pursuit import",
            _DAEMON_SRC,
            "Session 2 wiring requires importing pursuit",
        )

    def test_imports_decide_and_format(self):
        # The two public callables must both be imported by the
        # daemon — decide_pursuit for the decision, and
        # format_pursuit_utterance for the surface phrasing.
        for symbol in ("decide_pursuit", "format_pursuit_utterance"):
            self.assertIn(symbol, _DAEMON_SRC,
                          f"daemon must reference {symbol}")


# ── env gate ─────────────────────────────────────────────────────────


class FeatureFlagGatesPursuit(unittest.TestCase):
    """``MAEZ_WONDERING_PURSUIT`` env knob — default DISABLED. Mirrors
    the Slice-1-Session-3 ``MAEZ_WORKING_SELF`` opt-in pattern: this
    is a brand-new path, off by default until probe-validated."""

    def test_env_var_check_present(self):
        self.assertIn("MAEZ_WONDERING_PURSUIT", _DAEMON_SRC)

    def test_default_disabled(self):
        # Match: os.environ.get("MAEZ_WONDERING_PURSUIT", "0") == "1"
        self.assertRegex(
            _DAEMON_SRC,
            r'os\.environ\.get\("MAEZ_WONDERING_PURSUIT"[^)]*"0"[^)]*\)\s*==\s*"1"',
            "MAEZ_WONDERING_PURSUIT must default disabled",
        )


# ── policy gate ──────────────────────────────────────────────────────


class ProactivePolicyGate(unittest.TestCase):
    """The ``identity.proactive_messages()`` policy gate must be
    consulted before any pursuit surface. Bonded-companion shape
    requires explicit operator opt-in via per-user policy, beyond
    just the env knob."""

    def test_proactive_messages_policy_consulted(self):
        # Either via direct call or via the existing identity import
        # idiom. Match: proactive_messages() somewhere near the
        # pursuit callsite.
        self.assertIn(
            "proactive_messages",
            _DAEMON_SRC,
            "daemon must consult identity.proactive_messages() policy "
            "before surfacing a pursuit utterance",
        )


# ── safety wrapping ──────────────────────────────────────────────────


class PursuitFailureIsSilent(unittest.TestCase):
    """The pursuit callsite must not break synthesis if it raises.
    Wrapped in ``try / except Exception`` like the working-self and
    lived-recall blocks."""

    def test_decide_pursuit_in_try_except(self):
        idx = _DAEMON_SRC.find("decide_pursuit(")
        self.assertGreater(idx, 0,
                           "decide_pursuit callsite missing")
        before = _DAEMON_SRC[max(0, idx - 600):idx]
        after = _DAEMON_SRC[idx:idx + 1500]
        self.assertIn("try:", before,
                      "decide_pursuit must be inside a try: block")
        self.assertRegex(after, r"except\s+Exception",
                         "decide_pursuit must catch Exception "
                         "(silent fail-open)")


# ── trace capture ────────────────────────────────────────────────────


class TraceCaptureOfPursuit(unittest.TestCase):
    """When pursuit runs, the decision must be written to the trace
    regardless of surface/hold outcome — observability needs both."""

    def test_trace_pursuit_decision_assigned(self):
        # Match either the surface or hold outcome being assigned to
        # the trace.
        self.assertRegex(
            _DAEMON_SRC,
            r"_trace\.pursuit_decision\s*=",
            "daemon must assign pursuit_decision on the trace",
        )


# ── sidecar behaviour ────────────────────────────────────────────────


class SidecarRoundtrip(unittest.TestCase):
    """The frequency budget needs continuity across daemon restarts;
    a sidecar JSON file persists the last-pursuit timestamp. Test
    load/save roundtrip in isolation."""

    def test_save_then_load_returns_timestamp(self):
        from core.evolution.wondering_pursuit import (
            load_last_pursuit_at,
            save_last_pursuit_at,
        )

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            sidecar = f.name
        try:
            ts = datetime(2026, 4, 30, 18, 0, 0,
                          tzinfo=timezone.utc).timestamp()
            save_last_pursuit_at(ts, wondering_id=42, sidecar_path=sidecar)
            loaded = load_last_pursuit_at(sidecar_path=sidecar)
            self.assertAlmostEqual(loaded, ts, places=2)
        finally:
            Path(sidecar).unlink(missing_ok=True)

    def test_load_returns_none_when_file_missing(self):
        from core.evolution.wondering_pursuit import load_last_pursuit_at

        with tempfile.TemporaryDirectory() as tmpdir:
            missing = str(Path(tmpdir) / "does_not_exist.json")
            self.assertIsNone(load_last_pursuit_at(sidecar_path=missing))

    def test_load_returns_none_on_corrupt_file(self):
        from core.evolution.wondering_pursuit import load_last_pursuit_at

        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w"
        ) as f:
            f.write("not valid json {{{")
            corrupt = f.name
        try:
            self.assertIsNone(load_last_pursuit_at(sidecar_path=corrupt))
        finally:
            Path(corrupt).unlink(missing_ok=True)

    def test_save_swallows_disk_errors(self):
        from core.evolution.wondering_pursuit import save_last_pursuit_at

        # Path that can't be created (no permission to /proc/1)
        # must not raise. Best-effort design.
        try:
            save_last_pursuit_at(
                12345.0, wondering_id=1,
                sidecar_path="/proc/1/cant_write_here.json",
            )
        except Exception as exc:
            self.fail(f"save_last_pursuit_at must swallow disk errors: {exc}")


class PursuitOrderingBeforeAudit(unittest.TestCase):
    """Audit B1+B2 fix: pursuit utterance must be appended BEFORE
    ``audit_assistant_text`` so the audit pass screens any LLM-
    authored wondering content for fabrication / self-claim leaks.

    The earlier draft appended AFTER audit, smuggling LLM-authored
    text from ``daemon/wondering_cycle.py`` past the
    fabrication-prevention gate that ``audited_output.py`` exists
    to enforce. This test locks the corrected ordering at the
    source-string level."""

    def test_pursuit_callsite_precedes_audit_callsite(self):
        # Within handle_message specifically — there are several
        # other audit callsites elsewhere in the file. Anchor the
        # search to handle_message's body.
        hm_idx = _DAEMON_SRC.find("def handle_message")
        self.assertGreater(hm_idx, 0,
                           "handle_message function missing")
        body = _DAEMON_SRC[hm_idx:hm_idx + 80000]
        idx_pursuit = body.find("decide_pursuit(")
        idx_audit = body.find("reply = audit_assistant_text(")
        self.assertGreater(idx_pursuit, 0,
                           "decide_pursuit callsite missing inside handle_message")
        self.assertGreater(idx_audit, 0,
                           "reply = audit_assistant_text callsite missing inside handle_message")
        self.assertLess(
            idx_pursuit, idx_audit,
            "pursuit utterance must be appended BEFORE the handle_message "
            "audit so the audit pass screens the wondering question for "
            "fabrication / self-claim leaks (audit B1+B2 fix)",
        )


class TriStatePursuitDecision(unittest.TestCase):
    """Audit M2 fix: ``pursuit_decision`` is a tri-state (plus the
    not-run sentinel ``""``). The earlier draft conflated
    evaluator-returned-None (legitimate hold) with
    evaluator-raised-exception (errored), misreporting the trace."""

    def test_errored_state_recorded_separately_from_hold(self):
        # Source-level: the daemon must distinguish "hold" from
        # "errored" in trace.pursuit_decision assignment.
        self.assertIn(
            '"errored"', _DAEMON_SRC,
            "tri-state pursuit_decision must include 'errored' for "
            "exception-path observability (audit M2)",
        )
        self.assertIn(
            '"hold"', _DAEMON_SRC,
            "tri-state pursuit_decision must include 'hold' for "
            "evaluator-returned-None path",
        )
        self.assertIn(
            '"surface"', _DAEMON_SRC,
            "tri-state pursuit_decision must include 'surface' for "
            "the actual proactive utterance path",
        )


class AtomicSidecarWrite(unittest.TestCase):
    """Audit M1 fix: concurrent ``handle_message`` calls (Flask
    multi-threaded) could both pass the budget check and both
    write to ``last_pursuit.json``. A non-atomic ``write_text``
    yields a partial file mid-rename; ``load_last_pursuit_at``
    fail-opens to None, silently invalidating the budget. Fix:
    atomic ``os.replace`` from a same-directory tmp file."""

    def test_save_uses_atomic_replace(self):
        from pathlib import Path

        # White-box check: the implementation must use os.replace
        # (or os.rename) for the final swap. We verify by reading
        # the source — same-process atomicity is hard to test
        # behaviourally without a fault injector.
        src = (
            Path(__file__).resolve().parent.parent
            / "core" / "evolution" / "wondering_pursuit.py"
        ).read_text()
        # Search inside the save_last_pursuit_at function specifically.
        save_idx = src.find("def save_last_pursuit_at")
        self.assertGreater(save_idx, 0)
        # The next def or end-of-file is the upper bound.
        next_def = src.find("\ndef ", save_idx + 1)
        if next_def < 0:
            next_def = len(src)
        save_block = src[save_idx:next_def]
        self.assertIn(
            "os.replace", save_block,
            "save_last_pursuit_at must use os.replace for atomic "
            "rename (audit M1 fix — concurrent writers)",
        )

    def test_concurrent_save_does_not_corrupt(self):
        """Behavioural guard: many concurrent saves must leave the
        file in a parseable state. The atomic-rename pattern
        guarantees one writer wins per call; load must always
        succeed."""
        import threading
        import tempfile
        import time as _t
        from core.evolution.wondering_pursuit import (
            load_last_pursuit_at,
            save_last_pursuit_at,
        )

        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False
        ) as f:
            sidecar = f.name

        def writer(tag: int):
            for i in range(20):
                save_last_pursuit_at(
                    _t.time(), wondering_id=tag * 100 + i,
                    sidecar_path=sidecar,
                )

        threads = [threading.Thread(target=writer, args=(t,))
                   for t in range(8)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        try:
            # File must still be parseable after the storm.
            ts = load_last_pursuit_at(sidecar_path=sidecar)
            self.assertIsNotNone(
                ts,
                "concurrent saves must leave a parseable file "
                "(atomic-rename ensures one writer per swap)",
            )
        finally:
            Path(sidecar).unlink(missing_ok=True)
            # Clean up any straggler tmp file.
            Path(sidecar + ".tmp").unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
