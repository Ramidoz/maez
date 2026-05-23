# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Deterministic metacognitive loop-spiral watchdog.

HALT-only by construction: this module observes bounded structural telemetry,
writes a local non-reconstructive halt row, and raises ``WatchdogHalt``. It
does not import memory stores, soul editors, proposal machinery, or drive
writers.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from statistics import pvariance
from typing import Any, Iterable, Mapping

__all__ = [
    "MetacognitiveWatchdog",
    "WatchdogConfig",
    "WatchdogHalt",
]

WATCHDOG_VERSION = "metacognitive-watchdog-v1"


def _default_log_path() -> Path:
    override = os.environ.get("MAEZ_WATCHDOG_HALT_LOG")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "logs" / "watchdog_halts.jsonl"


@dataclass(frozen=True)
class WatchdogConfig:
    token_window_size: int = 120
    token_unique_ratio_threshold: float = 0.18
    repeated_ngram_size: int = 5
    repeated_ngram_ratio_threshold: float = 0.45
    action_window_size: int = 12
    action_max_cycle_length: int = 4
    action_repeat_threshold: int = 3
    scalar_window_size: int = 8
    scalar_variance_threshold: float = 0.0001
    scalar_consecutive_windows: int = 3
    velocity_window_size: int = 6
    velocity_min_seconds: float = 5.0
    velocity_max_seconds: float = 120.0
    velocity_consecutive_samples: int = 3
    log_path: Path = field(default_factory=_default_log_path)


class WatchdogHalt(Exception):
    """Structured HALT signal consumed by daemon safe-standby plumbing."""

    def __init__(
        self,
        *,
        detector: str,
        reason_code: str,
        observed_metrics: Mapping[str, Any],
        window_ref: str = "",
        threshold_ref: str = "",
        halt_signal_id: str = "",
    ) -> None:
        self.detector = detector
        self.reason_code = reason_code
        self.observed_metrics = dict(observed_metrics)
        self.window_ref = window_ref
        self.threshold_ref = threshold_ref
        self.halt_signal_id = halt_signal_id or _digest(
            f"{detector}:{reason_code}:{time.time_ns()}"
        )[:16]
        super().__init__(f"{detector}:{reason_code}:{self.halt_signal_id}")

    def health_summary(self) -> dict[str, Any]:
        return {
            "detector": self.detector,
            "reason_code": self.reason_code,
            "window_ref": self.window_ref,
            "threshold_ref": self.threshold_ref,
            "halt_signal_id": self.halt_signal_id,
            "observed_metrics": dict(self.observed_metrics),
        }


def _digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _ngrams(items: list[str], size: int) -> list[tuple[str, ...]]:
    if size <= 0 or len(items) < size:
        return []
    return [tuple(items[i : i + size]) for i in range(0, len(items) - size + 1)]


class MetacognitiveWatchdog:
    """Bounded structural detectors for daemon loop/fixation patterns."""

    def __init__(self, *, config: WatchdogConfig | None = None) -> None:
        self.config = config or WatchdogConfig()
        self._tokens: deque[str] = deque(maxlen=self.config.token_window_size)
        self._actions: deque[str] = deque(maxlen=self.config.action_window_size)
        self._scalars: dict[str, deque[float]] = {}
        self._flatline_windows: dict[str, int] = {}
        self._durations: deque[float] = deque(maxlen=self.config.velocity_window_size)
        self._velocity_outliers = 0

    def observe_tokens(self, tokens: Iterable[Any]) -> None:
        for token in tokens:
            self._tokens.append(str(token))
        if len(self._tokens) < self.config.token_window_size:
            return

        window = list(self._tokens)
        unique_ratio = len(set(window)) / len(window)
        grams = _ngrams(window, self.config.repeated_ngram_size)
        repeated_ngram_ratio = 0.0
        if grams:
            seen: set[tuple[str, ...]] = set()
            repeated = 0
            for gram in grams:
                if gram in seen:
                    repeated += 1
                seen.add(gram)
            repeated_ngram_ratio = repeated / len(grams)

        metrics = {
            "token_count": len(window),
            "unique_count": len(set(window)),
            "unique_ratio": round(unique_ratio, 6),
            "ngram_size": self.config.repeated_ngram_size,
            "repeated_ngram_ratio": round(repeated_ngram_ratio, 6),
        }
        if unique_ratio < self.config.token_unique_ratio_threshold:
            self._halt(
                detector="token_repetition",
                reason_code="low_unique_token_ratio",
                observed_metrics=metrics,
                threshold_ref="token_unique_ratio_threshold",
                window_ref=f"last_{len(window)}_tokens",
            )
        if repeated_ngram_ratio >= self.config.repeated_ngram_ratio_threshold:
            self._halt(
                detector="token_repetition",
                reason_code="repeated_ngram_ratio",
                observed_metrics=metrics,
                threshold_ref="repeated_ngram_ratio_threshold",
                window_ref=f"last_{len(window)}_tokens",
            )

    def observe_actions(self, actions: Iterable[Any]) -> None:
        for action in actions:
            self._actions.append(str(action))
        seq = list(self._actions)
        for length in range(1, self.config.action_max_cycle_length + 1):
            needed = length * self.config.action_repeat_threshold
            if len(seq) < needed:
                continue
            tail = seq[-needed:]
            pattern = tail[:length]
            if pattern and tail == pattern * self.config.action_repeat_threshold:
                self._halt(
                    detector="action_loop",
                    reason_code="repeated_action_cycle",
                    observed_metrics={
                        "cycle_length": length,
                        "repeat_count": self.config.action_repeat_threshold,
                    },
                    threshold_ref="action_repeat_threshold",
                    window_ref=f"last_{needed}_actions",
                )

    def observe_scalars(self, scalars: Mapping[str, Any]) -> None:
        for name, value in scalars.items():
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            window = self._scalars.setdefault(
                str(name),
                deque(maxlen=self.config.scalar_window_size),
            )
            window.append(numeric)
            if len(window) < self.config.scalar_window_size:
                continue
            variance = pvariance(window)
            if variance < self.config.scalar_variance_threshold:
                count = self._flatline_windows.get(str(name), 0) + 1
                self._flatline_windows[str(name)] = count
            else:
                self._flatline_windows[str(name)] = 0
                continue
            if count >= self.config.scalar_consecutive_windows:
                self._halt(
                    detector="drive_scalar_flatline",
                    reason_code="scalar_variance_flatline",
                    observed_metrics={
                        "scalar": str(name),
                        "sample_count": len(window),
                        "variance": round(variance, 10),
                        "consecutive_windows": count,
                    },
                    threshold_ref="scalar_variance_threshold",
                    window_ref=f"{name}:last_{len(window)}_samples",
                )

    def observe_cycle_duration(self, duration_seconds: float) -> None:
        duration = float(duration_seconds)
        self._durations.append(duration)
        if (
            duration < self.config.velocity_min_seconds
            or duration > self.config.velocity_max_seconds
        ):
            self._velocity_outliers += 1
        else:
            self._velocity_outliers = 0
        if self._velocity_outliers >= self.config.velocity_consecutive_samples:
            self._halt(
                detector="cycle_velocity",
                reason_code="cycle_duration_out_of_envelope",
                observed_metrics={
                    "duration_seconds": round(duration, 6),
                    "consecutive_outliers": self._velocity_outliers,
                    "min_seconds": self.config.velocity_min_seconds,
                    "max_seconds": self.config.velocity_max_seconds,
                },
                threshold_ref="velocity_min_seconds:velocity_max_seconds",
                window_ref=f"last_{len(self._durations)}_durations",
            )

    def health(self) -> dict[str, Any]:
        return {
            "version": WATCHDOG_VERSION,
            "token_samples": len(self._tokens),
            "action_samples": len(self._actions),
            "scalar_names": sorted(self._scalars),
            "duration_samples": len(self._durations),
        }

    def _halt(
        self,
        *,
        detector: str,
        reason_code: str,
        observed_metrics: Mapping[str, Any],
        threshold_ref: str,
        window_ref: str,
    ) -> None:
        halt = WatchdogHalt(
            detector=detector,
            reason_code=reason_code,
            observed_metrics=observed_metrics,
            window_ref=window_ref,
            threshold_ref=threshold_ref,
        )
        self._write_halt_row(halt)
        raise halt

    def _write_halt_row(self, halt: WatchdogHalt) -> None:
        path = Path(self.config.log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "daemon_pid": os.getpid(),
            "watchdog_version": WATCHDOG_VERSION,
            "detector": halt.detector,
            "reason_code": halt.reason_code,
            "window_ref": halt.window_ref,
            "threshold_ref": halt.threshold_ref,
            "observed_metrics": halt.observed_metrics,
            "halt_signal_id": halt.halt_signal_id,
            "safe_standby_state": "requested",
            "content_recorded": False,
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
        try:
            path.chmod(0o600)
        except OSError:
            pass
