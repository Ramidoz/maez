import threading
import time
import unittest

from core.routing.brain_gateway import BrainGateway, BrainPurpose
from core.routing.cancellable_brain_call import BrainPreempted


class PreemptProbeTest(unittest.TestCase):
    def test_probe_reports_missing_handle_while_factory_blocks(self):
        gateway = BrainGateway(preempt_timeout_s=0.5)
        bg_started = threading.Event()
        release = threading.Event()

        def bg_stream():
            # Model the live bug: the factory itself blocks before returning a
            # stream object, so record.call stays None during prompt-eval.
            bg_started.set()
            release.wait(timeout=2.0)
            return iter([{"content": "late background"}])

        def run_bg():
            try:
                gateway.submit(
                    purpose=BrainPurpose.DAEMON_CYCLE_GENERATION,
                    run_streaming_fn=bg_stream,
                )
            except BrainPreempted:
                pass

        worker = threading.Thread(target=run_bg)
        worker.start()
        self.assertTrue(bg_started.wait(timeout=2.0))

        def run_fg():
            gateway.submit(
                purpose=BrainPurpose.OWNER_RECALL,
                run_streaming_fn=lambda: iter([{"content": "fast [E1]"}]),
            )

        fg = threading.Thread(target=run_fg)
        fg.start()
        time.sleep(0.2)
        release.set()
        fg.join(timeout=3.0)
        worker.join(timeout=3.0)

        probes = [
            event
            for event in gateway.events
            if event.get("event") == "brain_gateway_preempt_probe"
        ]
        self.assertTrue(probes, "no preempt-probe event emitted")
        self.assertTrue(any(probe["handle_state"] == "missing" for probe in probes))
        for probe in probes:
            self.assertEqual(
                set(probe) - {"event"},
                {
                    "schema_version",
                    "purpose",
                    "current_purpose",
                    "handle_state",
                    "wait_ms",
                    "preempt_attempts",
                },
            )


if __name__ == "__main__":
    unittest.main()
