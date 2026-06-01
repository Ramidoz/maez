import threading
import time
import unittest

from core.routing.cancellable_brain_call import (
    BrainPreempted,
    CancellableBrainCall,
)


class _FakeStream:
    """Blocking iterable that models llama.cpp SSE stream states."""

    def __init__(self, chunks, *, block_before_first=True):
        self._chunks = list(chunks)
        self._gate = threading.Event()
        self._closed = threading.Event()
        self._block_before_first = block_before_first

    @property
    def closed(self):
        return self._closed.is_set()

    def release(self):
        self._gate.set()

    def close(self):
        self._closed.set()
        self._gate.set()

    def __iter__(self):
        first = True
        for chunk in self._chunks:
            if first and self._block_before_first:
                while not self._gate.wait(timeout=0.05):
                    if self._closed.is_set():
                        return
            if self._closed.is_set():
                return
            first = False
            yield chunk


class _StuckStream(_FakeStream):
    def close(self):
        time.sleep(10)


class CancellableBrainCallTest(unittest.TestCase):
    def test_cancel_before_first_token_unblocks_and_raises_brain_preempted(self):
        stream = _FakeStream([{"content": "hi"}], block_before_first=True)
        call = CancellableBrainCall(raw_stream=stream)
        result = {}

        def consume():
            try:
                result["reply"] = call.collect()
            except BrainPreempted:
                result["preempted"] = True

        worker = threading.Thread(target=consume)
        worker.start()
        time.sleep(0.1)

        timed_out = call.cancel()
        worker.join(timeout=2.0)

        self.assertFalse(timed_out)
        self.assertFalse(worker.is_alive())
        self.assertTrue(stream.closed)
        self.assertTrue(result.get("preempted"))
        self.assertNotIn("reply", result)

    def test_cancel_mid_generation_raises_brain_preempted(self):
        stream = _FakeStream(
            [{"content": "a"}, {"content": "b"}, {"content": "c"}],
            block_before_first=False,
        )
        call = CancellableBrainCall(raw_stream=stream)
        tokens = call.iter_tokens()

        self.assertEqual(next(tokens), "a")
        timed_out = call.cancel()

        self.assertFalse(timed_out)
        with self.assertRaises(BrainPreempted):
            list(tokens)

    def test_cancel_is_idempotent_and_synchronous(self):
        stream = _FakeStream([{"content": "x"}], block_before_first=True)
        call = CancellableBrainCall(raw_stream=stream)

        first_timeout = call.cancel()
        second_timeout = call.cancel()

        self.assertFalse(first_timeout)
        self.assertFalse(second_timeout)
        self.assertTrue(call.cancelled)
        self.assertTrue(stream.closed)

    def test_preempt_timeout_is_not_success(self):
        call = CancellableBrainCall(
            raw_stream=_StuckStream([{"content": "x"}], block_before_first=True),
            preempt_timeout_s=0.05,
        )

        timed_out = call.cancel()

        self.assertTrue(timed_out)
        self.assertTrue(call.cancelled)


if __name__ == "__main__":
    unittest.main()
