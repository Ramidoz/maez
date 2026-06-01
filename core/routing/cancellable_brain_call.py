"""Cancellable wrappers for priority-preemptible brain calls.

The gateway uses this small primitive to turn streaming backend responses into
buffered replies while still holding a real cross-thread cancellation handle.
"""

from __future__ import annotations

import threading
from typing import Any, Iterable


class BrainPreempted(Exception):
    """A brain call was deliberately preempted; this is not a backend error."""


class CancellableBrainCall:
    """Wrap a streaming response with idempotent cross-thread cancellation."""

    def __init__(self, *, raw_stream: Iterable[Any], preempt_timeout_s: float = 1.5):
        self._raw_stream = raw_stream
        self._preempt_timeout_s = preempt_timeout_s
        self._cancelled = threading.Event()
        self._closed = threading.Event()
        self._cancel_lock = threading.Lock()
        self._preempt_timeout = False

    @property
    def cancelled(self) -> bool:
        return self._cancelled.is_set()

    @property
    def preempt_timeout(self) -> bool:
        return self._preempt_timeout

    def cancel(self) -> bool:
        """Cancel the stream.

        Returns True when closing the underlying stream exceeded the preempt
        timeout. That is a recorded failure state, not a success.
        """

        with self._cancel_lock:
            if self._closed.is_set():
                return self._preempt_timeout
            self._cancelled.set()
            closer = getattr(self._raw_stream, "close", None)
            if closer is not None:
                closer_thread = threading.Thread(target=closer, daemon=True)
                closer_thread.start()
                closer_thread.join(timeout=self._preempt_timeout_s)
                if closer_thread.is_alive():
                    self._preempt_timeout = True
                    return True
            self._closed.set()
            return False

    def iter_tokens(self):
        try:
            for chunk in self._raw_stream:
                if self._cancelled.is_set():
                    raise BrainPreempted()
                yield _chunk_content(chunk)
        except BrainPreempted:
            raise
        except Exception:
            if self._cancelled.is_set():
                raise BrainPreempted()
            raise
        finally:
            if not self._closed.is_set() and not self._preempt_timeout:
                self._closed.set()
        if self._cancelled.is_set():
            raise BrainPreempted()

    def collect(self) -> str:
        return "".join(self.iter_tokens())


def _chunk_content(chunk: Any) -> str:
    if isinstance(chunk, dict):
        return str(chunk.get("content") or "")
    message = getattr(chunk, "message", None)
    if message is not None:
        return str(getattr(message, "content", "") or "")
    return str(getattr(chunk, "content", "") or "")
