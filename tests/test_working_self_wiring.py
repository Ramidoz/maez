# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Working-self daemon wiring tests (Session 3 of the working-self arc).

Locks the contract for assembling the working-self goal hierarchy at
the daemon's ``handle_message`` callsite and propagating it through
both the lived-recall planner and the trace record.

Mirrors the source-level shape of ``test_lived_recall_prompting.py`` —
mocking the whole daemon pipeline is heavy, and the structural
invariants are what matter:

- daemon imports ``assemble_goals`` from ``core.memory.working_self``.
- ``handle_message`` builds a ``GoalHierarchy`` from the lived stores +
  wants + the user's text, gated by ``MAEZ_WORKING_SELF`` (default
  DISABLED — this is a new capability path, opt-in until probes prove
  no regression).
- the assembled goals are passed to ``build_lived_recall_brief`` via
  the ``goals=`` kwarg.
- the assembled goals are captured on the ``Trace`` for observability.
- assembly failure is silent (handle_message must continue regardless).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_DAEMON_SRC = (_REPO / "daemon" / "maez_daemon.py").read_text()


class TraceCarriesWorkingSelfGoals(unittest.TestCase):
    """``Trace`` must carry a ``working_self_goals`` list so each turn's
    JSONL line records what the working self believed Maez was focused
    on at that moment. Empty by default — only populated when goal
    assembly fires."""

    def test_trace_has_working_self_goals_field(self):
        from core.turn_traces.trace_schema import Trace

        t = Trace.start(surface="test")
        self.assertTrue(hasattr(t, "working_self_goals"))
        self.assertIsInstance(t.working_self_goals, list)
        self.assertEqual(t.working_self_goals, [])

    def test_trace_jsonl_includes_working_self_goals(self):
        from core.turn_traces.trace_schema import Trace
        import json

        t = Trace.start(surface="test")
        t.working_self_goals = ["cares_about: Rohit cares about continuity"]
        line = t.to_jsonl_line()
        loaded = json.loads(line)
        self.assertIn("working_self_goals", loaded)
        self.assertEqual(loaded["working_self_goals"],
                         ["cares_about: Rohit cares about continuity"])


class DaemonImportsWorkingSelf(unittest.TestCase):
    def test_imports_assemble_goals(self):
        self.assertIn(
            "assemble_goals",
            _DAEMON_SRC,
            "Session 3 wiring requires importing assemble_goals.",
        )
        self.assertRegex(
            _DAEMON_SRC,
            r"from core\.memory\.working_self import [^\n]*assemble_goals",
            "assemble_goals must be imported from core.memory.working_self",
        )


class WorkingSelfFeatureFlagGatesAssembly(unittest.TestCase):
    """``MAEZ_WORKING_SELF`` env knob — default DISABLED. The
    capability exists, but production won't exercise it until the
    operator opts in by setting the env to ``"1"``. This is the
    inverse of ``MAEZ_LIVED_RECALL`` (default-enabled) because
    working-self is a brand-new path, not yet probe-validated."""

    def test_env_var_check_present(self):
        self.assertIn("MAEZ_WORKING_SELF", _DAEMON_SRC)

    def test_default_disabled(self):
        # The check shape: `os.environ.get("MAEZ_WORKING_SELF", "0") == "1"`
        # — default missing → "0" → off; explicit "1" → on.
        self.assertRegex(
            _DAEMON_SRC,
            r'os\.environ\.get\("MAEZ_WORKING_SELF"[^)]*"0"[^)]*\)\s*==\s*"1"',
            "MAEZ_WORKING_SELF must default disabled (default '0', explicit '1' enables)",
        )


class GoalsPassedToLivedRecall(unittest.TestCase):
    """When goals are assembled, they must flow into the lived-recall
    builder via the ``goals=`` kwarg added in Session 2."""

    def test_lived_recall_call_includes_goals_kwarg(self):
        # Find the build_lived_recall_brief callsite and verify it
        # has a `goals=` kwarg in the same call.
        idx = _DAEMON_SRC.find("build_lived_recall_brief(")
        self.assertGreater(idx, 0, "build_lived_recall_brief callsite missing")
        # Search forward up to the closing paren — generously sized.
        block = _DAEMON_SRC[idx:idx + 600]
        self.assertIn("goals=", block,
                      "lived recall call must pass goals= kwarg")


class GoalsAssemblyIsTryWrapped(unittest.TestCase):
    """Goal assembly must not break synthesis. Wrap in try/except like
    the lived-brief build itself."""

    def test_assemble_goals_in_try_except(self):
        idx = _DAEMON_SRC.find("assemble_goals(")
        self.assertGreater(idx, 0, "assemble_goals callsite missing")
        before = _DAEMON_SRC[max(0, idx - 300):idx]
        after = _DAEMON_SRC[idx:idx + 400]
        self.assertIn("try:", before,
                      "assemble_goals must be inside a try block")
        self.assertRegex(after, r"except\s+Exception",
                         "assemble_goals must catch Exception (silent fail-open)")


class GoalsCapturedOnTrace(unittest.TestCase):
    """The assembled goal hierarchy must be written to the trace so
    that future probes / cockpit panels can answer 'what did the
    working self believe at turn T?'"""

    def test_trace_working_self_goals_assigned(self):
        # Match: `_trace.working_self_goals = ...`
        self.assertRegex(
            _DAEMON_SRC,
            r"_trace\.working_self_goals\s*=",
            "daemon must assign working_self_goals on the trace",
        )


if __name__ == "__main__":
    unittest.main()
