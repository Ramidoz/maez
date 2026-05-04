# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""REGRESSION GUARDS for R1 — Restore the grounding rail.

The 2026-05-04 symphony audit (S2 finding F1, top-10 #1) found that
`core/cognition/grounding_judge.py:judge()` swallowed every transport
failure and returned `[]`. `self_claim_audit._find_flags` then read
that as "judge ran clean," setting `judge_available=True` and
`mode=noop`. For 7 days every Maez turn ran with the honesty audit
silently disabled (1,821 `Connection refused` lines / 7d in
journalctl, all DEBUG, none surfaced).

Codex gatekeeper review sharpened the contract:
    clean audit  !=  unavailable audit
The two MUST NOT collapse to the same mode tag. R1 fixes this.

Contract enforced by these tests:
- judge() raises typed JudgeUnavailable on transport failure (not
  swallow-as-empty-list).
- error_class field distinguishes refused / timeout / http_5xx /
  bad_response.
- self_claim_audit.audit() emits mode="judge_unavailable" (not
  "noop") on judge failure; AuditResult.skipped_reason is set.
- WARNING-level log on first failure + cooldown (no DEBUG spam).
- Healthy judge with empty findings still produces mode="noop"
  (the clean path is preserved).
- Timeout default ≤5s (was 30s; the wmctrl-incident audit row had
  latency_ms=21692 because of the long judge timeout under
  Connection refused).

Tests are runtime-shaped where the contract is observable through
the public API (judge raise, audit mode tag); source-pinned where
the invariant is structural (timeout default, error_class shape).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


# ── grounding_judge.judge() typed-exception contract ─────────────────


class R1_JudgeRaisesTypedException(unittest.TestCase):
    """REGRESSION GUARD: judge() must distinguish 'ran clean' from
    'could not run' by raising JudgeUnavailable on transport failure
    — no longer swallow as `[]`."""

    def test_judge_unavailable_class_exists(self):
        """The typed exception class must exist on the module so
        callers can catch it specifically."""
        from core.cognition import grounding_judge as gj
        self.assertTrue(
            hasattr(gj, "JudgeUnavailable"),
            "grounding_judge must export a JudgeUnavailable exception class",
        )
        self.assertTrue(
            issubclass(gj.JudgeUnavailable, Exception),
            "JudgeUnavailable must subclass Exception",
        )

    def test_connection_refused_raises_judge_unavailable(self):
        """A ConnectionRefusedError from the HTTP layer must surface
        as JudgeUnavailable, not as a silent `[]` return."""
        from core.cognition import grounding_judge as gj

        def _boom(_prompt):
            raise ConnectionRefusedError("simulated refused")

        with mock.patch.object(gj, "_call_dedicated_judge", side_effect=_boom):
            with self.assertRaises(gj.JudgeUnavailable) as ctx:
                gj.judge(
                    text="some claim",
                    signals_present=[], signals_absent=[],
                    few_shots=[],
                )
        self.assertEqual(
            getattr(ctx.exception, "error_class", None),
            "refused",
            "JudgeUnavailable must record error_class='refused' for "
            "connection refusal",
        )

    def test_timeout_raises_judge_unavailable_with_class(self):
        """A socket/HTTP timeout must surface as JudgeUnavailable
        with error_class='timeout'."""
        from core.cognition import grounding_judge as gj
        import socket

        def _boom(_prompt):
            raise TimeoutError("simulated read timeout")

        with mock.patch.object(gj, "_call_dedicated_judge", side_effect=_boom):
            with self.assertRaises(gj.JudgeUnavailable) as ctx:
                gj.judge(
                    text="some claim",
                    signals_present=[], signals_absent=[],
                    few_shots=[],
                )
        self.assertEqual(
            getattr(ctx.exception, "error_class", None),
            "timeout",
        )

        # socket.timeout is a separate type that should also classify
        # as 'timeout'.
        def _boom2(_prompt):
            raise socket.timeout("simulated socket timeout")

        with mock.patch.object(gj, "_call_dedicated_judge", side_effect=_boom2):
            with self.assertRaises(gj.JudgeUnavailable) as ctx:
                gj.judge(
                    text="some claim",
                    signals_present=[], signals_absent=[],
                    few_shots=[],
                )
        self.assertEqual(
            getattr(ctx.exception, "error_class", None),
            "timeout",
        )

    def test_malformed_json_raises_judge_unavailable_with_class(self):
        """If the judge endpoint responds with non-JSON or shape we
        can't parse, judge() must surface JudgeUnavailable
        error_class='bad_response' rather than swallow as clean."""
        from core.cognition import grounding_judge as gj

        def _bad_response(_prompt):
            return "this is not parseable JSON {{{"

        with mock.patch.object(gj, "_call_dedicated_judge",
                               side_effect=lambda p: "not json {{{"):
            with self.assertRaises(gj.JudgeUnavailable) as ctx:
                gj.judge(
                    text="some claim",
                    signals_present=[], signals_absent=[],
                    few_shots=[],
                )
        self.assertEqual(
            getattr(ctx.exception, "error_class", None),
            "bad_response",
        )

    def test_healthy_judge_empty_findings_returns_clean_list(self):
        """The healthy-judge path must still work: a judge that
        responds normally with no findings must return [] without
        raising. The 'clean' path is the load-bearing baseline; R1
        must not break it."""
        from core.cognition import grounding_judge as gj

        def _clean(_prompt):
            return '{"ungrounded": []}'

        with mock.patch.object(gj, "_call_dedicated_judge", side_effect=_clean):
            result = gj.judge(
                text="i am here at the desk",
                signals_present=[], signals_absent=[],
                few_shots=[],
            )
        self.assertEqual(
            result, [],
            "healthy judge with empty findings must return []"
        )

    def test_healthy_judge_with_findings_returns_list(self):
        """Healthy judge with actual findings must return a list of
        dicts with the expected shape (text, reason, [rewrite])."""
        from core.cognition import grounding_judge as gj

        def _flagged(_prompt):
            return ('{"ungrounded": [{"text": "I have run a deep '
                    'system scan.", "reason": "no scan ran"}]}')

        with mock.patch.object(gj, "_call_dedicated_judge", side_effect=_flagged):
            result = gj.judge(
                text="I have run a deep system scan.",
                signals_present=[], signals_absent=[],
                few_shots=[],
            )
        self.assertEqual(len(result), 1)
        self.assertIn("text", result[0])
        self.assertIn("reason", result[0])


# ── self_claim_audit.audit() mode contract ───────────────────────────


class R1_AuditEmitsJudgeUnavailableMode(unittest.TestCase):
    """REGRESSION GUARD: audit() must emit mode='judge_unavailable'
    (not 'noop') when the judge can't run. The cognition log line
    must contain `mode=judge_unavailable` so cockpit telemetry can
    distinguish clean from blind."""

    def test_audit_returns_judge_unavailable_mode_when_judge_raises(self):
        from core.safety import self_claim_audit as sca
        from core.cognition import grounding_judge as gj

        def _boom(*_, **__):
            raise gj.JudgeUnavailable(
                "simulated", error_class="refused",
            )

        with mock.patch.object(gj, "judge", side_effect=_boom):
            result = sca.audit(
                text="i can see your screen right now",
                surface="r1_test",
            )
        self.assertEqual(
            result.mode, "judge_unavailable",
            "AuditResult.mode must be 'judge_unavailable' when judge raised",
        )
        self.assertEqual(
            result.skipped_reason, "judge_unavailable",
            "AuditResult.skipped_reason must be set when audit could not run",
        )
        self.assertFalse(
            result.rewritten,
            "rewritten must be False when audit didn't run",
        )

    def test_audit_emits_mode_judge_unavailable_to_cognition_log(self):
        """The cognition log line must contain `mode=judge_unavailable`
        so cockpit / quality telemetry / journalctl scans see it."""
        from core.safety import self_claim_audit as sca
        from core.cognition import grounding_judge as gj

        def _boom(*_, **__):
            raise gj.JudgeUnavailable(
                "simulated", error_class="refused",
            )

        with mock.patch.object(gj, "judge", side_effect=_boom):
            with self.assertLogs("maez.cognition", level="INFO") as cm:
                sca.audit(
                    text="i can see your screen right now",
                    surface="r1_test_log",
                )
        log_text = "\n".join(cm.output)
        self.assertIn(
            "mode=judge_unavailable", log_text,
            f"cognition log must include mode=judge_unavailable; got {log_text}",
        )
        self.assertNotIn(
            "mode=noop", log_text,
            "must NOT collapse unavailable into noop",
        )

    def test_audit_returns_noop_when_judge_clean(self):
        """The clean-path must still produce mode='noop' — the
        invariant is `clean != unavailable`, both must remain
        distinguishable from the rewrote path."""
        from core.safety import self_claim_audit as sca
        from core.cognition import grounding_judge as gj

        with mock.patch.object(gj, "judge", return_value=[]):
            result = sca.audit(
                text="i'm here, listening",
                surface="r1_test_clean",
            )
        self.assertEqual(
            result.mode, "noop",
            "clean judge must still produce mode='noop', not "
            "mode='judge_unavailable'",
        )
        self.assertIsNone(
            result.skipped_reason,
            "skipped_reason must be None when judge ran clean",
        )


# ── WARNING level + cooldown on degraded-capability surface ─────────


class R1_DegradedCapabilityVisibility(unittest.TestCase):
    """REGRESSION GUARD: the FIRST judge-unavailable in a cooldown
    window must log at WARNING (not DEBUG) and emit a
    capability_degraded consequence_memory row. Subsequent calls
    within the cooldown window do NOT spam (cooldown).

    Cooldown is 15 min by default; tests use a tighter window via
    monkey-patch."""

    def test_first_unavailable_emits_warning(self):
        """First judge-unavailable in the cooldown window must
        produce a WARNING-level log. 1821 DEBUG lines/7d is exactly
        the regression we are guarding against."""
        from core.safety import self_claim_audit as sca
        from core.cognition import grounding_judge as gj

        # Reset cooldown state so test starts clean.
        if hasattr(sca, "_judge_unavailable_last_warning_ts"):
            sca._judge_unavailable_last_warning_ts = 0.0

        def _boom(*_, **__):
            raise gj.JudgeUnavailable("simulated", error_class="refused")

        with mock.patch.object(gj, "judge", side_effect=_boom):
            with self.assertLogs("maez", level="WARNING") as cm:
                # Use claim-length text so the prefilter
                # (_looks_obviously_clean) doesn't short-circuit
                # before _find_flags is reached.
                sca.audit(
                    text="I have run a deep system scan and I can see "
                         "your active windows right now.",
                    surface="r1_warning_test",
                )
        warning_lines = [m for m in cm.output if "WARNING" in m]
        self.assertTrue(
            warning_lines,
            f"first judge-unavailable must emit a WARNING log line; "
            f"got {cm.output}",
        )
        self.assertTrue(
            any("judge" in m.lower() for m in warning_lines),
            "WARNING line must mention the judge",
        )

    def test_cooldown_suppresses_subsequent_warnings(self):
        """Within the cooldown window, the SECOND
        judge-unavailable must NOT emit another WARNING (otherwise
        we recreate the 1821-lines/7d spam)."""
        from core.safety import self_claim_audit as sca
        from core.cognition import grounding_judge as gj
        import time

        # Force a recent-ish "last warning" by setting the timestamp.
        # The cooldown logic in self_claim_audit consults this.
        sca._judge_unavailable_last_warning_ts = time.time()

        def _boom(*_, **__):
            raise gj.JudgeUnavailable("simulated", error_class="refused")

        with mock.patch.object(gj, "judge", side_effect=_boom):
            # No WARNING expected. assertLogs requires at least one log
            # at the level so we use assertNoLogs instead.
            try:
                with self.assertNoLogs("maez", level="WARNING"):
                    sca.audit(
                        text="I have run a deep system scan and "
                             "I can see your active windows right now.",
                        surface="r1_cooldown_test",
                    )
            except AttributeError:
                # Python <3.10 doesn't have assertNoLogs; skip that
                # check on older runtimes — the assertLogs path above
                # covers the load-bearing invariant.
                self.skipTest("assertNoLogs unavailable on this runtime")


# ── Source-pin: tight timeout default ────────────────────────────────


class R1_TightTimeoutDefault(unittest.TestCase):
    """REGRESSION GUARD: the default judge timeout must be ≤5s.

    The 30s default is what made the wmctrl turn's audit_log
    latency_ms = 21692 — the daemon was waiting on retries of an
    unreachable judge while the owner watched. Fail-loud only
    matters if the failure is fast."""

    def test_default_timeout_is_at_most_5s(self):
        from core.cognition import grounding_judge as gj
        # Read the resolved value at import time. Env var override is
        # honored — this asserts the BUILT-IN default if env is unset.
        # In CI / dev we set MAEZ_JUDGE_TIMEOUT_S, so we read the
        # underlying value rather than re-resolving from env.
        timeout = getattr(gj, "_JUDGE_TIMEOUT_S", None)
        self.assertIsNotNone(timeout, "module must expose _JUDGE_TIMEOUT_S")
        self.assertLessEqual(
            float(timeout), 5.0,
            f"_JUDGE_TIMEOUT_S default must be ≤5s; got {timeout}. "
            f"A 30s default is what produced audit_log latency_ms=21692 "
            f"on the wmctrl incident.",
        )


if __name__ == "__main__":
    unittest.main()
