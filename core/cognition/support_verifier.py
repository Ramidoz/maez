"""The claimable-entailment support verifier seam.

`SupportVerifier` is the swappable instrument contract. `HttpSupportVerifier`
talks to the out-of-process MiniCheck service; `FakeSupportVerifier` is for
tests. The real model is never loaded in this module.
"""
from __future__ import annotations

import abc
import time
from typing import Optional

import httpx

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

    name = "fake"

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
        self.last_evidence: str | None = None

    def support(self, evidence, claim, timeout_s):
        t0 = time.monotonic()
        self.calls.append((evidence, claim))
        self.last_evidence = evidence
        if self._raises is not None:
            raise self._raises
        if self._sleep_s:
            time.sleep(self._sleep_s)
        label, score = self._scripted.get(claim, self._default)
        return label, score, time.monotonic() - t0


class HttpSupportVerifier(SupportVerifier):
    """POST to the out-of-process MiniCheck service.

    Transport failures, timeouts, 5xx responses, and malformed JSON all become
    ``UNAVAILABLE``. The grounding shadow must never raise into its caller.
    """

    def __init__(
        self,
        url: str = "http://127.0.0.1:8083",
        default_timeout_s: float = 0.25,
    ):
        self._endpoint = url.rstrip("/") + "/support"
        self._default_timeout_s = default_timeout_s

    def support(self, evidence, claim, timeout_s=None):
        t0 = time.monotonic()
        timeout = self._default_timeout_s if timeout_s is None else timeout_s
        try:
            response = httpx.post(
                self._endpoint,
                json={"evidence": evidence, "claim": claim},
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()
            label = SUPPORTED if data.get("verdict") == SUPPORTED else UNSUPPORTED
            return label, data.get("score"), time.monotonic() - t0
        except Exception:
            return UNAVAILABLE, None, time.monotonic() - t0
