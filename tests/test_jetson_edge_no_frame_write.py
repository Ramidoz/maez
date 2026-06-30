import os
import pathlib
import tempfile
import unittest
from contextlib import contextmanager
from unittest import mock

import tests._jetson_edge_path  # noqa: F401

_PKG_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "devices",
        "jetson_presence",
        "jetson_presence",
    )
)

_FORBIDDEN_TOKENS = (
    "imwrite",
    "VideoWriter",
    "imencode",
    "write_bytes",
    ".tofile(",
    ".save(",
    "'wb'",
    '"wb"',
    "'w+b'",
    '"w+b"',
    "'wb+'",
    '"wb+"',
    "'ab'",
    '"ab"',
    "'a+b'",
    '"a+b"',
    "'ab+'",
    '"ab+"',
)


@contextmanager
def _watch_file_writes():
    import builtins

    writes = []
    real_open = builtins.open
    real_path_open = pathlib.Path.open

    def _watch_open(path, mode="r", *a, **k):
        if any(c in mode for c in "wax"):
            writes.append((str(path), mode))
        return real_open(path, mode, *a, **k)

    def _watch_path_open(path, mode="r", *a, **k):
        if any(c in mode for c in "wax"):
            writes.append((str(path), mode))
        return real_path_open(path, mode, *a, **k)

    with (
        mock.patch("builtins.open", _watch_open),
        mock.patch.object(pathlib.Path, "open", _watch_path_open),
        mock.patch.object(
            pathlib.Path,
            "write_bytes",
            lambda self, b: writes.append(("write_bytes", str(self))),
        ),
    ):
        yield writes


class NoFrameWriteStaticTests(unittest.TestCase):
    def test_no_write_token_in_any_source_file(self):
        offenders = []
        for name in os.listdir(_PKG_DIR):
            if not name.endswith(".py"):
                continue
            with open(os.path.join(_PKG_DIR, name), encoding="utf-8") as fh:
                src = fh.read()
            for tok in _FORBIDDEN_TOKENS:
                if tok in src:
                    offenders.append(f"{name}: {tok}")
        self.assertEqual(
            offenders,
            [],
            f"forbidden frame-write tokens found: {offenders}",
        )


class NoFrameWriteDynamicTests(unittest.TestCase):
    def test_running_a_cycle_writes_no_file(self):
        from jetson_presence import presence_loop

        class _Cam:
            def open(self):
                return True

            def read_frame(self):
                return (True, object())

            def release(self):
                pass

        with _watch_file_writes() as writes:
            presence_loop.run_once(
                camera=_Cam(),
                emit=lambda label: None,
                is_curtained=lambda: False,
                now_ts=lambda: "t",
            )
        self.assertEqual(
            writes,
            [],
            f"a file write happened during a B0 cycle: {writes}",
        )

    def test_write_watcher_detects_path_open_binary_write_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            probe = pathlib.Path(tmp) / "maez_b0_write_probe.bin"
            with _watch_file_writes() as writes:
                with probe.open("w+b"):
                    pass
            self.assertNotEqual(
                writes,
                [],
                "write watcher failed to detect Path.open(..., 'w+b')",
            )


if __name__ == "__main__":
    unittest.main()
