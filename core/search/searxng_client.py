"""Sovereign search body (SearXNG) behind a swappable backend.

The daemon talks to a ``SearchBackend``; only ``SearxngBackend`` touches a live
SearXNG, and only behind ``MAEZ_SEARCH_COMMITMENT_ENABLED`` at the owner witness.
Tests use ``FakeSearchBackend`` — the suite never needs a running SearXNG.
"""
from __future__ import annotations

import abc
import time

import httpx

HEALTHY, DEGRADED, DOWN = "healthy", "degraded", "down"


class SearchBackend(abc.ABC):
    @abc.abstractmethod
    def search(self, query: str, max_results: int = 8) -> list[dict]:
        raise NotImplementedError

    @abc.abstractmethod
    def health(self) -> str:  # HEALTHY | DEGRADED | DOWN
        raise NotImplementedError


class FakeSearchBackend(SearchBackend):
    """Tests only. Scripted results + scriptable health. Never loads SearXNG."""

    def __init__(self, results=None, health=HEALTHY, raises=None):
        self._results = results if results is not None else [{"title": "t", "url": "u", "content": "c"}]
        self._health = health
        self._raises = raises
        self.searched: list[str] = []

    def search(self, query, max_results=8):
        self.searched.append(query)
        if self._raises is not None:
            raise self._raises
        return list(self._results)[:max_results]

    def health(self):
        return self._health


class SearxngBackend(SearchBackend):
    """Live SearXNG client. Local JSON API; health cached briefly.

    CONFIRM the ``/search?q=...&format=json`` shape in the owner-gated smoke (the
    audition proved it) — adapt here if the live shape differs, do not force.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:8888", timeout_s: float = 8.0, health_ttl_s: float = 30.0):
        self._base = base_url.rstrip("/")
        self._timeout = timeout_s
        self._health_ttl = health_ttl_s
        self._health_val: str | None = None
        self._health_ts = 0.0

    def search(self, query, max_results=8):
        r = httpx.get(self._base + "/search", params={"q": query, "format": "json"}, timeout=self._timeout)
        r.raise_for_status()
        rows = r.json().get("results", [])[:max_results]
        return [{"title": x.get("title"), "url": x.get("url"), "content": x.get("content")} for x in rows]

    def _probe(self) -> str:
        try:
            r = httpx.get(self._base + "/search", params={"q": "healthcheck", "format": "json"}, timeout=self._timeout)
            if r.status_code != 200:
                return DOWN
            return HEALTHY if r.json().get("results") else DEGRADED
        except Exception:
            return DOWN

    def health(self, now: float | None = None) -> str:
        t = time.time() if now is None else now
        if self._health_val is not None and (t - self._health_ts) < self._health_ttl:
            return self._health_val
        self._health_val, self._health_ts = self._probe(), t
        return self._health_val
