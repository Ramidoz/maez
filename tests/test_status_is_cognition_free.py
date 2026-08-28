# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""/status must survive the failure it exists to diagnose.

OWNER RULING 2026-08-28 (birth-surface freeze): the operator plane
exists precisely for when Maez's cognition may be unavailable or
untrusted, so its primary health diagnostic MUST NOT depend on
cognition. It reports what the body knows directly; it never asks the
brain whether the brain is healthy.

MEASURED DEFECT: `_handle_status` was 95% substrate already —
`perception_snapshot()` yields CPU/RAM/GPU with no brain involvement.
But `self.memory.count()` was interpolated into the SAME f-string as
those facts, so a wedged or raising memory store destroyed the WHOLE
reply, including the resource numbers that would have explained the
failure. The one diagnostic you reach for when Maez is sick was the one
guaranteed to go silent when Maez was sick.

The fix is narrow by ruling: each section degrades INDEPENDENTLY, and
the handler still emits. No new organ, no new surface.
"""

from __future__ import annotations

import asyncio
import unittest
from unittest import mock


class _StubVoice:
    """Only what _handle_status reaches for."""

    from skills.telegram_voice import TelegramVoice as _T
    _handle_status = _T._handle_status
    del _T

    def __init__(self, memory):
        self.memory = memory

    def _is_authorized(self, _uid):
        return True


class _Msg:
    pass


class _User:
    id = 1


class _Update:
    message = _Msg()
    effective_user = _User()


def _run_status(memory) -> str:
    """Drive the REAL handler; capture what it would send."""
    sent: list[str] = []

    async def _capture(update, text, *a, **k):
        sent.append(text)

    from skills import telegram_voice as tv

    with mock.patch.object(tv, "_reply_text", _capture):
        asyncio.run(_StubVoice(memory)._handle_status(_Update(), None))
    return sent[0] if sent else ""


class _WedgedMemory:
    def count(self):
        raise RuntimeError("chroma is wedged")


class _HealthyMemory:
    def count(self):
        return 44137


class StatusSurvivesTheFailureItDiagnoses(unittest.TestCase):
    def test_status_still_reports_resources_when_memory_is_wedged(self):
        out = _run_status(_WedgedMemory())
        self.assertTrue(
            out,
            "THE DIAGNOSTIC WENT SILENT. A wedged memory store killed the "
            "whole /status reply — the operator plane's primary health "
            "check fails exactly when it is needed.",
        )
        for fact in ("CPU", "RAM"):
            self.assertIn(
                fact, out,
                f"{fact} is a pure substrate fact and must survive a "
                "memory-store failure",
            )

    def test_a_wedged_memory_is_reported_honestly_not_hidden(self):
        out = _run_status(_WedgedMemory())
        self.assertNotIn(
            "Memories: 0", out,
            "a failed count must NOT render as zero — that is a false "
            "substrate claim, not a degradation",
        )
        self.assertRegex(
            out, r"Memories:\s*(unavailable|unknown|n/?a)",
            "the failure must be NAMED in the reply; silence about a "
            "broken subsystem is what the operator plane exists to avoid",
        )

    def test_the_healthy_path_still_reports_the_count(self):
        out = _run_status(_HealthyMemory())
        self.assertIn("44137", out, "the healthy count regressed")

    def test_status_makes_no_cognition_call(self):
        """Ruled: it must not ask the brain whether the brain is healthy."""
        import ast
        import inspect

        from skills.telegram_voice import TelegramVoice

        src = inspect.getsource(TelegramVoice._handle_status)
        tree = ast.parse(src.strip())
        called = {
            getattr(n.func, "attr", getattr(n.func, "id", ""))
            for n in ast.walk(tree)
            if isinstance(n, ast.Call)
        }
        forbidden = {"chat", "generate", "generate_response", "run_brain_loop",
                     "synthesize", "ask", "complete"}
        self.assertFalse(
            called & forbidden,
            f"/status reached cognition via {sorted(called & forbidden)} — "
            "the operator plane must not depend on the brain",
        )


if __name__ == "__main__":
    unittest.main()
