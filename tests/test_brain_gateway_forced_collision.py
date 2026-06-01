import threading
import time
import unittest

from core.routing.brain_gateway import BrainGateway, BrainPurpose
from core.routing.cancellable_brain_call import BrainPreempted


class ForcedCollisionTest(unittest.TestCase):
    def test_foreground_preempts_inflight_background(self):
        gateway = BrainGateway(preempt_timeout_s=0.5)
        bg_started = threading.Event()
        bg_outcome = {}

        def bg_stream():
            gate = threading.Event()

            class _Stream:
                def __iter__(self):
                    bg_started.set()
                    while not gate.wait(timeout=0.05):
                        pass
                    yield {"content": "late background"}

                def close(self):
                    gate.set()

            return _Stream()

        def run_bg():
            try:
                gateway.submit(
                    purpose=BrainPurpose.DAEMON_CYCLE_GENERATION,
                    run_streaming_fn=bg_stream,
                )
            except BrainPreempted:
                bg_outcome["preempted"] = True

        worker = threading.Thread(target=run_bg)
        worker.start()
        self.assertTrue(bg_started.wait(timeout=2.0))

        t0 = time.monotonic()
        foreground_reply = gateway.submit(
            purpose=BrainPurpose.OWNER_RECALL,
            run_streaming_fn=lambda: iter([{"content": "fast reply [E1]"}]),
        )
        foreground_ms = (time.monotonic() - t0) * 1000
        worker.join(timeout=2.0)

        self.assertFalse(worker.is_alive())
        self.assertTrue(bg_outcome.get("preempted"))
        self.assertEqual(foreground_reply, "fast reply [E1]")
        self.assertLess(foreground_ms, 1500)
        self.assertTrue(any(event["preempted"] for event in gateway.events))
        self.assertFalse(any(event["preempt_timeout"] for event in gateway.events))
        self.assertIn(1, [event["preempted_count"] for event in gateway.events])


if __name__ == "__main__":
    unittest.main()
