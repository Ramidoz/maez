"""Regression guards for daemon native-resource shutdown.

The SIGTERM diagnostic showed that Maez can finish Python-level shutdown
while native Chroma / MediaPipe / OpenCV worker pools keep the process alive
until systemd escalates to SIGKILL. These tests pin the lifecycle hooks before
the shutdown fix is implemented.
"""

from __future__ import annotations

import importlib
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DAEMON_SRC = ROOT / "daemon" / "maez_daemon.py"
TELEGRAM_PUBLIC_SRC = ROOT / "skills" / "telegram_public.py"
TELEGRAM_VOICE_SRC = ROOT / "skills" / "telegram_voice.py"


class _FakeClient:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class ShutdownLifecycleTests(unittest.TestCase):
    def test_memory_manager_close_closes_all_chroma_clients(self) -> None:
        from memory.memory_manager import MemoryManager

        manager = MemoryManager.__new__(MemoryManager)
        manager._raw_client = _FakeClient()
        manager._daily_client = _FakeClient()
        manager._core_client = _FakeClient()

        manager.close()

        self.assertTrue(manager._raw_client.closed)
        self.assertTrue(manager._daily_client.closed)
        self.assertTrue(manager._core_client.closed)

    def test_presence_shutdown_closes_persistent_detector(self) -> None:
        presence = importlib.import_module("skills.presence_perception")

        class _Detector:
            def __init__(self) -> None:
                self.closed = False

            def close(self) -> None:
                self.closed = True

        detector = _Detector()
        presence._detector = detector
        original_cv2 = sys.modules.get("cv2")
        fake_cv2 = types.SimpleNamespace(
            destroyAllWindows=lambda: None,
            ocl=types.SimpleNamespace(setUseOpenCL=lambda _enabled: None),
        )
        sys.modules["cv2"] = fake_cv2
        try:
            presence.shutdown()
        finally:
            if original_cv2 is None:
                sys.modules.pop("cv2", None)
            else:
                sys.modules["cv2"] = original_cv2

        self.assertTrue(detector.closed)
        self.assertIsNone(presence._detector)

    def test_daemon_stop_calls_presence_and_memory_shutdown_hooks(self) -> None:
        src = DAEMON_SRC.read_text()

        self.assertIn("presence_shutdown()", src)
        self.assertIn("self.memory.close()", src)

    def test_signal_stop_exits_after_graceful_shutdown_ladder(self) -> None:
        src = DAEMON_SRC.read_text()
        stop_start = src.index("def stop(self, signum=None, frame=None):")
        stop_end = src.index("def _run_health_server", stop_start)
        block = src[stop_start:stop_end]

        self.assertIn("if signum is not None:", block)
        self.assertIn("logging.shutdown()", block)
        self.assertIn("os._exit(0)", block)
        self.assertLess(block.index("self._remove_pid()"), block.index("os._exit(0)"))

    def test_public_context_closes_temporary_chroma_client(self) -> None:
        src = DAEMON_SRC.read_text()
        start = src.index("def _get_public_context")
        end = src.index("def handle_voice_stream", start)
        block = src[start:end]

        self.assertIn("finally:", block)
        self.assertIn('getattr(client, "close"', block)
        self.assertIn("close()", block)

    def test_telegram_voice_public_context_closes_temporary_chroma_client(self) -> None:
        src = TELEGRAM_VOICE_SRC.read_text()
        start = src.index("def _get_public_context_for_telegram")
        end = src.index("SOUL_PATH", start)
        block = src[start:end]

        self.assertIn("finally:", block)
        self.assertIn('getattr(client, "close"', block)
        self.assertIn("close()", block)

    def test_public_bot_store_exposes_close_and_stop_calls_it(self) -> None:
        src = TELEGRAM_PUBLIC_SRC.read_text()
        self.assertIn("def close(self) -> None:", src)
        stop_start = src.index("def stop(self):")
        stop_block = src[stop_start:]
        self.assertIn("self.store.close()", stop_block)


if __name__ == "__main__":
    unittest.main()
