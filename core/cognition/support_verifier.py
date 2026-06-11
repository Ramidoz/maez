"""The claimable-entailment support verifier seam.

`SupportVerifier` is the swappable instrument contract. `HttpSupportVerifier`
talks to the out-of-process MiniCheck service; `FakeSupportVerifier` is for
tests. The real model is never loaded in this module.
"""
from __future__ import annotations

import abc
import time
from typing import Optional

SUPPORTED = "SUPPORTED"
UNSUPPORTED = "UNSUPPORTED"
UNAVAILABLE = "UNAVAILABLE"


class SupportVerifier(abc.ABC):
    @abc.abstractmethod
    def support(
        self,
        evidence: str,
        claim: str,
        timeout_s: float,
    ) -> tuple[str, Optional[float], float]:
        """Return (label, score, latency_s)."""
        raise NotImplementedError


class FakeSupportVerifier(SupportVerifier):
    """Tests only. Scripted verdicts; never loads a real model."""

    def __init__(
        self,
        scripted=None,
        default=(SUPPORTED, 0.99),
        raises=None,
        sleep_s=0.0,
    ):
        self._scripted = dict(scripted or {})
        self._default = default
        self._raises = raises
        self._sleep_s = sleep_s
        self.calls: list[tuple[str, str]] = []

    def support(self, evidence, claim, timeout_s):
        t0 = time.monotonic()
        self.calls.append((evidence, claim))
        if self._raises is not None:
            raise self._raises
        if self._sleep_s:
            time.sleep(self._sleep_s)
        label, score = self._scripted.get(claim, self._default)
        return label, score, time.monotonic() - t0
