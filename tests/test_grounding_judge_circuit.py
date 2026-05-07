"""Tests for circuit-breaker integration in core.cognition.grounding_judge.

These tests are written BEFORE the integration is wired up. They pin the
contract described in the slice spec:

  1. A module-level _JUDGE_BREAKER (CircuitBreaker) is constructed at import
     time, with thresholds/window/cooldown read from env vars
     MAEZ_JUDGE_BREAKER_THRESHOLD (default 5), MAEZ_JUDGE_BREAKER_WINDOW_S
     (default 60), MAEZ_JUDGE_BREAKER_COOLDOWN_S (default 30).
  2. _call_dedicated_judge runs through _JUDGE_BREAKER.call(...).
  3. CircuitOpen translates to JudgeUnavailable(error_class="circuit_open").
  4. The fallback _llm_client.chat path is NOT wrapped — only the dedicated
     judge HTTP path is.
  5. CLOSED<->OPEN transitions emit a WARNING log on
     "core.cognition.grounding_judge".

Hermetic: stdlib only, no real network, fake clock injected via the
breaker's `clock` constructor hook (per tests/test_circuit_breaker.py spec).
"""
from __future__ import annotations

import importlib
import os
import threading
import unittest
from unittest.mock import patch, MagicMock

from core.cognition import grounding_judge


def _reload_with_env(env_overrides):
    """Reload grounding_judge with the given env overrides applied.
    Returns the (re-imported) module reference. Caller is responsible for
    reloading once more in tearDown to restore defaults.
    """
    with patch.dict(os.environ, env_overrides, clear=False):
        return importlib.reload(grounding_judge)


class _FakeClock:
    """Deterministic monotonic clock. Mirrors tests/test_circuit_breaker.py."""

    def __init__(self, start: float = 1000.0):
        self._t = start
        self._lock = threading.Lock()

    def __call__(self) -> float:
        with self._lock:
            return self._t

    def advance(self, delta: float) -> None:
        with self._lock:
            self._t += delta


def _install_fake_clock(module, clock):
    """Replace the module-level breaker with one that uses our fake clock,
    preserving the env-derived thresholds AND the original logger so
    state-transition WARNINGs continue to land on the integration's
    logger hierarchy. The integration must expose _JUDGE_BREAKER at
    module scope for this to work.
    """
    from core.health.circuit_breaker import CircuitBreaker
    old = module._JUDGE_BREAKER
    module._JUDGE_BREAKER = CircuitBreaker(
        name=getattr(old, "name", "grounding_judge"),
        failure_threshold=int(os.environ.get(
            "MAEZ_JUDGE_BREAKER_THRESHOLD", "5")),
        window_s=float(os.environ.get(
            "MAEZ_JUDGE_BREAKER_WINDOW_S", "60")),
        cooldown_s=float(os.environ.get(
            "MAEZ_JUDGE_BREAKER_COOLDOWN_S", "30")),
        clock=clock,
        log=getattr(old, "_log", None),
    )


_FAKE_TEXT = "I've been testing the Maelstrom framework today."


def _judge_kwargs(**overrides):
    base = {
        "text": _FAKE_TEXT,
        "signals_present": [],
        "signals_absent": [],
        "few_shots": [],
    }
    base.update(overrides)
    return base


class _BaseCircuitTest(unittest.TestCase):
    """Common reload/teardown plumbing."""

    DEFAULT_ENV = {
        "MAEZ_JUDGE_BASE_URL": "http://127.0.0.1:8081",
        "MAEZ_JUDGE_BREAKER_THRESHOLD": "5",
        "MAEZ_JUDGE_BREAKER_WINDOW_S": "60",
        "MAEZ_JUDGE_BREAKER_COOLDOWN_S": "30",
    }

    def setUp(self):
        self._env_patcher = patch.dict(
            os.environ, self.DEFAULT_ENV, clear=False)
        self._env_patcher.start()
        self.module = importlib.reload(grounding_judge)

    def tearDown(self):
        self._env_patcher.stop()
        # Reload once more under the now-restored environment so other
        # test files see a clean module.
        importlib.reload(grounding_judge)


class TestFirstFailureDoesNotShortCircuit(_BaseCircuitTest):
    def test_first_failure_does_not_short_circuit(self):
        clock = _FakeClock()
        _install_fake_clock(self.module, clock)

        # Patch the underlying network call (urlopen) inside
        # _call_dedicated_judge to raise.
        with patch(
            "core.cognition.grounding_judge.urllib.request.urlopen",
            side_effect=ConnectionRefusedError("nope"),
        ) as urlopen_mock:
            with self.assertRaises(self.module.JudgeUnavailable) as cm:
                self.module.judge(**_judge_kwargs())
            self.assertEqual(cm.exception.error_class, "refused")
            # Network call was attempted exactly once.
            self.assertEqual(urlopen_mock.call_count, 1)

        # Breaker is still closed after a single failure.
        self.assertEqual(self.module._JUDGE_BREAKER.state, "closed")


class TestThresholdFailuresOpenBreaker(_BaseCircuitTest):
    def test_threshold_failures_open_breaker_then_short_circuits(self):
        clock = _FakeClock()
        _install_fake_clock(self.module, clock)
        threshold = int(os.environ["MAEZ_JUDGE_BREAKER_THRESHOLD"])

        with patch(
            "core.cognition.grounding_judge.urllib.request.urlopen",
            side_effect=ConnectionRefusedError("nope"),
        ) as urlopen_mock:
            # First N calls: each fails with refused (current behavior).
            for i in range(threshold):
                with self.assertRaises(self.module.JudgeUnavailable) as cm:
                    self.module.judge(**_judge_kwargs())
                self.assertEqual(
                    cm.exception.error_class, "refused",
                    f"call #{i + 1} expected refused, got "
                    f"{cm.exception.error_class}",
                )

            self.assertEqual(urlopen_mock.call_count, threshold)
            self.assertEqual(self.module._JUDGE_BREAKER.state, "open")

            # N+1th call: short-circuits as circuit_open WITHOUT invoking
            # urlopen.
            with self.assertRaises(self.module.JudgeUnavailable) as cm:
                self.module.judge(**_judge_kwargs())
            self.assertEqual(cm.exception.error_class, "circuit_open")
            self.assertEqual(
                urlopen_mock.call_count, threshold,
                "network mock was invoked while breaker was open",
            )


class TestCircuitOpenShortCircuitsUntilCooldown(_BaseCircuitTest):
    def test_circuit_open_short_circuits_until_cooldown(self):
        clock = _FakeClock()
        _install_fake_clock(self.module, clock)
        threshold = int(os.environ["MAEZ_JUDGE_BREAKER_THRESHOLD"])

        with patch(
            "core.cognition.grounding_judge.urllib.request.urlopen",
            side_effect=ConnectionRefusedError("nope"),
        ) as urlopen_mock:
            for _ in range(threshold):
                with self.assertRaises(self.module.JudgeUnavailable):
                    self.module.judge(**_judge_kwargs())
            self.assertEqual(self.module._JUDGE_BREAKER.state, "open")
            calls_at_open = urlopen_mock.call_count

            # Multiple subsequent calls all short-circuit, no network.
            for _ in range(7):
                with self.assertRaises(self.module.JudgeUnavailable) as cm:
                    self.module.judge(**_judge_kwargs())
                self.assertEqual(cm.exception.error_class, "circuit_open")
            self.assertEqual(urlopen_mock.call_count, calls_at_open)
            self.assertEqual(self.module._JUDGE_BREAKER.state, "open")


class TestCircuitRecoversOnProbeSuccess(_BaseCircuitTest):
    def test_circuit_recovers_on_probe_success(self):
        clock = _FakeClock()
        _install_fake_clock(self.module, clock)
        threshold = int(os.environ["MAEZ_JUDGE_BREAKER_THRESHOLD"])
        cooldown = float(os.environ["MAEZ_JUDGE_BREAKER_COOLDOWN_S"])

        # Build a mock response object that urlopen() acts as a context
        # manager for and whose .read() returns valid judge JSON.
        good_payload = (
            b'{"choices": [{"message": {"content": '
            b'"{\\"ungrounded\\": []}"}}]}'
        )

        def make_good_resp():
            resp = MagicMock()
            resp.__enter__ = lambda self_: resp
            resp.__exit__ = lambda self_, *a: False
            resp.read.return_value = good_payload
            return resp

        # Phase 1: trip the breaker.
        with patch(
            "core.cognition.grounding_judge.urllib.request.urlopen",
            side_effect=ConnectionRefusedError("nope"),
        ):
            for _ in range(threshold):
                with self.assertRaises(self.module.JudgeUnavailable):
                    self.module.judge(**_judge_kwargs())
        self.assertEqual(self.module._JUDGE_BREAKER.state, "open")

        # Phase 2: advance clock past cooldown and let the next call probe.
        clock.advance(cooldown + 1.0)

        with patch(
            "core.cognition.grounding_judge.urllib.request.urlopen",
            return_value=make_good_resp(),
        ) as urlopen_ok:
            result = self.module.judge(**_judge_kwargs())
            self.assertEqual(result, [])
            self.assertEqual(urlopen_ok.call_count, 1)

            # Breaker should be closed again.
            self.assertEqual(self.module._JUDGE_BREAKER.state, "closed")

            # Subsequent calls also go through (history cleared).
            result2 = self.module.judge(**_judge_kwargs())
            self.assertEqual(result2, [])
            self.assertEqual(urlopen_ok.call_count, 2)


class TestBreakerThresholdEnvOverride(unittest.TestCase):
    def tearDown(self):
        importlib.reload(grounding_judge)

    def test_breaker_threshold_env_override(self):
        env = {
            "MAEZ_JUDGE_BASE_URL": "http://127.0.0.1:8081",
            "MAEZ_JUDGE_BREAKER_THRESHOLD": "2",
            "MAEZ_JUDGE_BREAKER_WINDOW_S": "60",
            "MAEZ_JUDGE_BREAKER_COOLDOWN_S": "30",
        }
        with patch.dict(os.environ, env, clear=False):
            module = importlib.reload(grounding_judge)
            clock = _FakeClock()
            _install_fake_clock(module, clock)

            with patch(
                "core.cognition.grounding_judge.urllib.request.urlopen",
                side_effect=ConnectionRefusedError("nope"),
            ) as urlopen_mock:
                # 2 failures -> opens.
                for _ in range(2):
                    with self.assertRaises(module.JudgeUnavailable) as cm:
                        module.judge(**_judge_kwargs())
                    self.assertEqual(cm.exception.error_class, "refused")
                self.assertEqual(module._JUDGE_BREAKER.state, "open")

                # 3rd call short-circuits (would need 5 with default).
                with self.assertRaises(module.JudgeUnavailable) as cm:
                    module.judge(**_judge_kwargs())
                self.assertEqual(cm.exception.error_class, "circuit_open")
                self.assertEqual(urlopen_mock.call_count, 2)


class TestFallbackPathIsNotWrapped(unittest.TestCase):
    def tearDown(self):
        # Restore environment + module.
        importlib.reload(grounding_judge)

    def test_fallback_path_is_not_wrapped(self):
        # Disable dedicated judge: fallback _llm_client.chat path should run.
        env = {
            "MAEZ_JUDGE_BREAKER_THRESHOLD": "2",
            "MAEZ_JUDGE_BREAKER_WINDOW_S": "60",
            "MAEZ_JUDGE_BREAKER_COOLDOWN_S": "30",
        }
        # Remove MAEZ_JUDGE_BASE_URL entirely so model_config.refresh()
        # falls back to its hard default; then explicitly null out
        # _JUDGE_BASE_URL on the reloaded module to force the fallback path.
        prior_base_url = os.environ.pop("MAEZ_JUDGE_BASE_URL", None)
        try:
            with patch.dict(os.environ, env, clear=False):
                module = importlib.reload(grounding_judge)
                # Force fallback regardless of model_config's default.
                module._JUDGE_BASE_URL = ""
                clock = _FakeClock()
                _install_fake_clock(module, clock)
                breaker = module._JUDGE_BREAKER
                self.assertEqual(breaker.state, "closed")

                # Patch the fallback chat to raise; call judge several
                # times past the threshold. Breaker must remain closed
                # because the fallback path is intentionally NOT wrapped.
                with patch(
                    "core.cognition.grounding_judge._llm_client.chat",
                    side_effect=ConnectionRefusedError("nope"),
                ) as chat_mock:
                    for _ in range(5):
                        with self.assertRaises(
                            module.JudgeUnavailable
                        ) as cm:
                            module.judge(**_judge_kwargs())
                        # Errors should still classify as refused
                        # (preserving the existing classifier path),
                        # NOT circuit_open.
                        self.assertEqual(
                            cm.exception.error_class, "refused")
                    self.assertEqual(chat_mock.call_count, 5)

                # Breaker must still be closed: the fallback path
                # should not have incremented its failure count.
                self.assertEqual(
                    module._JUDGE_BREAKER.state, "closed",
                    "fallback path failures must not affect the "
                    "dedicated-path breaker",
                )
        finally:
            if prior_base_url is not None:
                os.environ["MAEZ_JUDGE_BASE_URL"] = prior_base_url


class TestLoggingEmitsOnStateChange(_BaseCircuitTest):
    DEFAULT_ENV = {
        "MAEZ_JUDGE_BASE_URL": "http://127.0.0.1:8081",
        "MAEZ_JUDGE_BREAKER_THRESHOLD": "2",
        "MAEZ_JUDGE_BREAKER_WINDOW_S": "60",
        "MAEZ_JUDGE_BREAKER_COOLDOWN_S": "30",
    }

    def test_logging_emits_on_state_change(self):
        clock = _FakeClock()
        _install_fake_clock(self.module, clock)
        cooldown = float(os.environ["MAEZ_JUDGE_BREAKER_COOLDOWN_S"])

        # CLOSED -> OPEN must emit a WARNING with the breaker name.
        with self.assertLogs(
            "core.cognition.grounding_judge", level="WARNING",
        ) as log_cm_open:
            with patch(
                "core.cognition.grounding_judge.urllib.request.urlopen",
                side_effect=ConnectionRefusedError("nope"),
            ):
                for _ in range(2):
                    with self.assertRaises(self.module.JudgeUnavailable):
                        self.module.judge(**_judge_kwargs())
        self.assertTrue(
            any("grounding_judge" in line for line in log_cm_open.output),
            f"expected breaker name in warning logs, got "
            f"{log_cm_open.output!r}",
        )

        # OPEN -> CLOSED (after probe success) must also emit a WARNING.
        clock.advance(cooldown + 1.0)
        good_payload = (
            b'{"choices": [{"message": {"content": '
            b'"{\\"ungrounded\\": []}"}}]}'
        )

        def make_good_resp():
            resp = MagicMock()
            resp.__enter__ = lambda self_: resp
            resp.__exit__ = lambda self_, *a: False
            resp.read.return_value = good_payload
            return resp

        with self.assertLogs(
            "core.cognition.grounding_judge", level="WARNING",
        ) as log_cm_close:
            with patch(
                "core.cognition.grounding_judge.urllib.request.urlopen",
                return_value=make_good_resp(),
            ):
                self.module.judge(**_judge_kwargs())
        self.assertTrue(
            any("grounding_judge" in line for line in log_cm_close.output),
            f"expected breaker name in close-transition logs, got "
            f"{log_cm_close.output!r}",
        )


class TestBadResponseDoesNotCount(_BaseCircuitTest):
    """A judge that responds with malformed JSON is alive but
    misbehaving; it must NOT trip the transport-class breaker.

    Otherwise a single bad prompt-template deploy would deterministically
    open the circuit forever — connect-storm protection becomes a self-
    inflicted outage. Only refused/timeout failures count toward the
    breaker; bad_response surfaces normally as JudgeUnavailable but
    does not increment the failure window.
    """

    DEFAULT_ENV = {
        "MAEZ_JUDGE_BASE_URL": "http://127.0.0.1:8081",
        "MAEZ_JUDGE_BREAKER_THRESHOLD": "2",
        "MAEZ_JUDGE_BREAKER_WINDOW_S": "60",
        "MAEZ_JUDGE_BREAKER_COOLDOWN_S": "30",
    }

    def test_bad_response_does_not_count_toward_threshold(self):
        clock = _FakeClock()
        _install_fake_clock(self.module, clock)
        threshold = int(os.environ["MAEZ_JUDGE_BREAKER_THRESHOLD"])

        def make_garbage_resp():
            resp = MagicMock()
            resp.__enter__ = lambda self_: resp
            resp.__exit__ = lambda self_, *a: False
            resp.read.return_value = b"not json at all <html>"
            return resp

        with patch(
            "core.cognition.grounding_judge.urllib.request.urlopen",
            return_value=make_garbage_resp(),
        ) as urlopen_mock:
            # Five bad_response failures past threshold — must NOT trip.
            for _ in range(threshold + 3):
                with self.assertRaises(
                    self.module.JudgeUnavailable
                ) as cm:
                    self.module.judge(**_judge_kwargs())
                self.assertEqual(
                    cm.exception.error_class, "bad_response",
                    f"expected bad_response, got "
                    f"{cm.exception.error_class}",
                )

            self.assertEqual(
                urlopen_mock.call_count, threshold + 3,
                "every call should reach the network — breaker must "
                "be closed",
            )
            self.assertEqual(
                self.module._JUDGE_BREAKER.state, "closed",
                "bad_response is a caller-side failure, not a "
                "transport failure; it must not open the breaker",
            )

        # Real transport failures still count, even after bad_response burst.
        with patch(
            "core.cognition.grounding_judge.urllib.request.urlopen",
            side_effect=ConnectionRefusedError("nope"),
        ):
            for _ in range(threshold):
                with self.assertRaises(self.module.JudgeUnavailable):
                    self.module.judge(**_judge_kwargs())
        self.assertEqual(self.module._JUDGE_BREAKER.state, "open")


if __name__ == "__main__":
    unittest.main()
