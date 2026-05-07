"""Tests for the module-level helper `_run_pw_reader` in
skills/wake_word.py.

Behavior under test:
    - Polls proc.stdout fd via select.select with a short timeout so
      stop_event is checked frequently (no blocking read).
    - Reads via os.read(fd, n) (NOT proc.stdout.read) — the buffered
      file object's read waits for the full size, defeating the
      select bound. os.read returns whatever's available up to n,
      and the helper accumulates until the requested size.
    - Skips the 44-byte WAV header on first read by default.
    - Watchdog: after `watchdog_s` of continuous silence, kills proc and
      exits.
    - On EOF, OSError, ValueError, or stop_event, exits cleanly.
      Never raises.
    - Appends (np.ndarray int16, np.ndarray float32) tuples to
      audio_queue under queue_lock.
"""

from __future__ import annotations

import logging
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from skills.wake_word import _run_pw_reader


CHUNK_BYTES = 2048  # 1024 samples * 2 bytes (int16)
FAKE_FD = 42


def _make_fake_proc():
    """Build a fake subprocess.Popen. The actual reads go through os.read
    on the fd, so this just needs to expose the fd and lifecycle hooks.
    """
    proc = MagicMock()
    proc.stdout = MagicMock()
    proc.stdout.fileno = MagicMock(return_value=FAKE_FD)
    proc.kill = MagicMock()
    proc.terminate = MagicMock()
    return proc


def _osread_returning(sequence):
    """Build an os.read side_effect that returns each entry in sequence
    in order. Sequence entries can be bytes (returned as-is) or
    exceptions (raised). After exhausting the sequence, returns b''
    (EOF) so the helper exits cleanly.

    Each call to os.read receives (fd, nbytes_remaining); we ignore
    nbytes and return the full chunk — testing accumulation behavior
    is done via test_accumulates_partial_reads."""
    seq_iter = iter(sequence)

    def _side(_fd, _n):
        try:
            v = next(seq_iter)
        except StopIteration:
            return b""
        if isinstance(v, BaseException):
            raise v
        return v

    return _side


def _silent_chunk(nbytes=CHUNK_BYTES):
    return (b"\x00\x01" * (nbytes // 2))[:nbytes]


class RunPwReaderTests(unittest.TestCase):
    def setUp(self):
        self.stop_event = threading.Event()
        self.queue: list = []
        self.lock = threading.Lock()

    # ------------------------------------------------------------------
    # 1. stop_event short-circuits the reader even if read would block.
    # ------------------------------------------------------------------
    def test_reader_exits_on_stop_event(self):
        proc = _make_fake_proc()
        self.stop_event.set()  # already set before call

        with patch("select.select", return_value=([], [], [])), \
             patch("os.read", side_effect=lambda *_: time.sleep(60) or b""):
            t0 = time.monotonic()
            _run_pw_reader(
                proc,
                self.stop_event,
                self.queue,
                self.lock,
                CHUNK_BYTES,
                watchdog_s=10.0,
                skip_wav_header=False,
            )
            elapsed = time.monotonic() - t0

        self.assertLess(elapsed, 1.0,
                        f"reader did not exit promptly on stop_event ({elapsed:.2f}s)")

    # ------------------------------------------------------------------
    # 2. Data chunks land in the queue with proper shape.
    # ------------------------------------------------------------------
    def test_reader_appends_data_to_queue(self):
        chunks = [_silent_chunk(), _silent_chunk(), _silent_chunk(), b""]
        proc = _make_fake_proc()

        # select.select reports stdout always ready; os.read returns
        # full chunks (test_accumulates_partial_reads covers partials)
        with patch("select.select",
                   return_value=([FAKE_FD], [], [])), \
             patch("os.read", side_effect=_osread_returning(chunks)):
            _run_pw_reader(
                proc,
                self.stop_event,
                self.queue,
                self.lock,
                CHUNK_BYTES,
                watchdog_s=5.0,
                skip_wav_header=False,
            )

        self.assertEqual(len(self.queue), 3, "expected 3 data chunks queued")
        # The original inline _reader stored
        # (np.ndarray int16, np.ndarray float32) — the slice 1.4
        # refactor preserves that contract so downstream consumers
        # don't change.
        for raw, fl in self.queue:
            self.assertIsInstance(raw, np.ndarray)
            self.assertEqual(raw.dtype, np.int16)
            self.assertEqual(raw.shape[0], CHUNK_BYTES // 2)
            self.assertEqual(np.asarray(fl).dtype, np.float32)
            self.assertEqual(np.asarray(fl).shape[0], CHUNK_BYTES // 2)

    # ------------------------------------------------------------------
    # 3. WAV header skipped on first read by default.
    # ------------------------------------------------------------------
    def test_reader_skip_wav_header_on_by_default(self):
        # First os.read returns 44 bytes (the WAV header). Helper should
        # accumulate exactly 44 bytes, discard them, then proceed.
        seq = [b"H" * 44, _silent_chunk(), b""]
        proc = _make_fake_proc()

        with patch("select.select",
                   return_value=([FAKE_FD], [], [])), \
             patch("os.read", side_effect=_osread_returning(seq)):
            _run_pw_reader(
                proc,
                self.stop_event,
                self.queue,
                self.lock,
                CHUNK_BYTES,
                watchdog_s=5.0,
                # default skip_wav_header=True
            )

        # Only the post-header chunk should land in the queue.
        self.assertEqual(len(self.queue), 1,
                         "WAV header must not be queued as audio data")

    # ------------------------------------------------------------------
    # 4. With skip_wav_header=False, the first chunk is processed.
    # ------------------------------------------------------------------
    def test_reader_skip_wav_header_off_for_test_mode(self):
        seq = [_silent_chunk(), b""]
        proc = _make_fake_proc()

        with patch("select.select",
                   return_value=([FAKE_FD], [], [])), \
             patch("os.read", side_effect=_osread_returning(seq)):
            _run_pw_reader(
                proc,
                self.stop_event,
                self.queue,
                self.lock,
                CHUNK_BYTES,
                watchdog_s=5.0,
                skip_wav_header=False,
            )

        self.assertEqual(len(self.queue), 1,
                         "first read should be processed when skip_wav_header=False")

    # ------------------------------------------------------------------
    # 5. EOF (read returns b'') causes a clean exit.
    # ------------------------------------------------------------------
    def test_reader_exits_on_eof(self):
        seq = [_silent_chunk(), b""]
        proc = _make_fake_proc()

        with patch("select.select",
                   return_value=([FAKE_FD], [], [])), \
             patch("os.read", side_effect=_osread_returning(seq)):
            t0 = time.monotonic()
            _run_pw_reader(
                proc,
                self.stop_event,
                self.queue,
                self.lock,
                CHUNK_BYTES,
                watchdog_s=5.0,
                skip_wav_header=False,
            )
            elapsed = time.monotonic() - t0

        self.assertLess(elapsed, 1.0, "EOF should cause prompt exit")

    # ------------------------------------------------------------------
    # 6. OSError on read → log warning, exit cleanly.
    # ------------------------------------------------------------------
    def test_reader_handles_oserror(self):
        seq = [_silent_chunk(), OSError("pipe closed")]
        proc = _make_fake_proc()
        custom = logging.getLogger("test_reader_oserror")
        custom.setLevel(logging.DEBUG)

        with patch("select.select",
                   return_value=([FAKE_FD], [], [])), \
             patch("os.read", side_effect=_osread_returning(seq)):
            with self.assertLogs(custom, level="WARNING"):
                _run_pw_reader(
                    proc,
                    self.stop_event,
                    self.queue,
                    self.lock,
                    CHUNK_BYTES,
                    watchdog_s=5.0,
                    log=custom,
                    skip_wav_header=False,
                )

    # ------------------------------------------------------------------
    # 7. Watchdog fires when no data ever arrives.
    # ------------------------------------------------------------------
    def test_watchdog_kills_proc_on_silence(self):
        # os.read should never be called because select reports nothing
        # ready — but if it is, hang it.
        proc = _make_fake_proc()

        with patch("select.select", return_value=([], [], [])), \
             patch("os.read", side_effect=lambda *_: time.sleep(60) or b""):
            t0 = time.monotonic()
            _run_pw_reader(
                proc,
                self.stop_event,
                self.queue,
                self.lock,
                CHUNK_BYTES,
                watchdog_s=0.3,
                skip_wav_header=False,
            )
            elapsed = time.monotonic() - t0

        self.assertGreater(proc.kill.call_count, 0,
                           "watchdog should have called proc.kill() on silence")
        self.assertLess(elapsed, 1.5,
                        f"watchdog should fire within ~watchdog_s, took {elapsed:.2f}s")

    # ------------------------------------------------------------------
    # 8. Watchdog resets when data arrives intermittently.
    # ------------------------------------------------------------------
    def test_watchdog_resets_on_data(self):
        # 6 alternations: ready, not-ready, ready, not-ready, ready, EOF.
        # Each "not-ready" select returns after a short timeout (<0.3s).
        # The "ready" reads reset the watchdog before it fires.
        ready = ([1], [], [])
        not_ready = ([], [], [])

        select_sequence = [
            ready, not_ready, ready, not_ready, ready, not_ready, ready,
        ]
        # Mock select to consume from the sequence then default to ready
        # (so we still hit EOF promptly via the read sequence).
        select_iter = iter(select_sequence)

        def fake_select(*_a, **_kw):
            try:
                return next(select_iter)
            except StopIteration:
                return ready

        # Reads: when "ready" was returned, helper calls os.read.
        # We yield small data chunks then EOF.
        read_sequence = [
            _silent_chunk(),
            _silent_chunk(),
            _silent_chunk(),
            _silent_chunk(),
            b"",
        ]
        proc = _make_fake_proc()

        with patch("select.select", side_effect=fake_select), \
             patch("os.read", side_effect=_osread_returning(read_sequence)):
            # Simulate the small "no-data" windows by sleeping inside
            # select. Easiest: patch time.monotonic? No — just keep
            # not_ready windows shorter than watchdog_s by giving select
            # a short return.  Our fake_select returns immediately, so
            # the helper's own select_timeout dictates pacing. We pick
            # watchdog_s=0.3 and rely on fast iteration plus periodic
            # data arrival to keep the watchdog from firing.
            t0 = time.monotonic()
            _run_pw_reader(
                proc,
                self.stop_event,
                self.queue,
                self.lock,
                CHUNK_BYTES,
                watchdog_s=0.3,
                skip_wav_header=False,
            )
            elapsed = time.monotonic() - t0

        self.assertEqual(proc.kill.call_count, 0,
                         "watchdog must not fire when data arrives within window")
        self.assertLess(elapsed, 1.0,
                        f"reset-on-data test ran too long: {elapsed:.2f}s")
        self.assertGreaterEqual(len(self.queue), 1)

    # ------------------------------------------------------------------
    # 9. Custom logger receives the warning on OSError.
    # ------------------------------------------------------------------
    def test_logger_is_used(self):
        seq = [OSError("pipe closed")]
        proc = _make_fake_proc()
        custom = logging.getLogger("custom_pw_reader_logger")
        custom.setLevel(logging.DEBUG)

        with patch("select.select",
                   return_value=([FAKE_FD], [], [])), \
             patch("os.read", side_effect=_osread_returning(seq)):
            with self.assertLogs(custom, level="WARNING") as cm:
                _run_pw_reader(
                    proc,
                    self.stop_event,
                    self.queue,
                    self.lock,
                    CHUNK_BYTES,
                    watchdog_s=5.0,
                    log=custom,
                    skip_wav_header=False,
                )

        self.assertTrue(
            any("custom_pw_reader_logger" == r.name for r in cm.records),
            "warning should be emitted on the custom logger",
        )

    # ------------------------------------------------------------------
    # 10b. Watchdog fires DURING the WAV header phase (not just after).
    # Adversarial review Critical #1: the original design had the
    # header read happen BEFORE the select loop, leaving the same
    # D-state hang vector open. The header read must also be select-
    # polled with watchdog protection.
    # ------------------------------------------------------------------
    def test_watchdog_fires_during_wav_header_silence(self):
        # If select stays not-ready forever, the helper must NOT block
        # on a raw read(44) for the WAV header; the watchdog must fire
        # the same way it does for chunk reads.
        proc = _make_fake_proc()

        with patch("select.select", return_value=([], [], [])), \
             patch("os.read", side_effect=lambda *_: time.sleep(60) or b""):
            t0 = time.monotonic()
            _run_pw_reader(
                proc,
                self.stop_event,
                self.queue,
                self.lock,
                CHUNK_BYTES,
                watchdog_s=0.3,
                skip_wav_header=True,  # <-- the path being guarded
            )
            elapsed = time.monotonic() - t0

        self.assertGreater(
            proc.kill.call_count, 0,
            "watchdog should fire during WAV header read on sustained "
            "silence; otherwise the D-state hang vector remains open "
            "on the spawn path",
        )
        self.assertLess(
            elapsed, 1.5,
            f"watchdog should fire within ~watchdog_s during header "
            f"phase; took {elapsed:.2f}s",
        )

    # ------------------------------------------------------------------
    # 10. No exceptions propagate to the caller, even with mixed events.
    # ------------------------------------------------------------------
    def test_no_exceptions_propagate(self):
        seq = [
            _silent_chunk(),
            b"",                    # EOF — but reader may continue past?
            OSError("late error"),
            _silent_chunk(),
        ]
        proc = _make_fake_proc()

        with patch("select.select",
                   return_value=([FAKE_FD], [], [])), \
             patch("os.read", side_effect=_osread_returning(seq)):
            try:
                _run_pw_reader(
                    proc,
                    self.stop_event,
                    self.queue,
                    self.lock,
                    CHUNK_BYTES,
                    watchdog_s=5.0,
                    skip_wav_header=False,
                )
            except Exception as e:  # pragma: no cover
                self.fail(f"_run_pw_reader leaked an exception: {e!r}")

    # ------------------------------------------------------------------
    # 11. ValueError on read (e.g. closed file from stop()'s escalation
    # ladder) is caught — original review caught this as a contract
    # violation: helper claimed "never raises" but only handled OSError.
    # ------------------------------------------------------------------
    def test_reader_handles_valueerror(self):
        seq = [_silent_chunk(), ValueError("read of closed file")]
        proc = _make_fake_proc()
        custom = logging.getLogger("test_reader_valueerror")
        custom.setLevel(logging.DEBUG)

        with patch("select.select",
                   return_value=([FAKE_FD], [], [])), \
             patch("os.read", side_effect=_osread_returning(seq)):
            with self.assertLogs(custom, level="WARNING"):
                try:
                    _run_pw_reader(
                        proc,
                        self.stop_event,
                        self.queue,
                        self.lock,
                        CHUNK_BYTES,
                        watchdog_s=5.0,
                        log=custom,
                        skip_wav_header=False,
                    )
                except Exception as e:  # pragma: no cover
                    self.fail(f"ValueError leaked from reader: {e!r}")

    # ------------------------------------------------------------------
    # 12. os.read can return fewer bytes than requested (a Linux pipe
    # only gives what's currently buffered). The helper must accumulate
    # until the full requested size is read — otherwise downstream
    # np.frombuffer parses garbage.
    # Adversarial review High finding 2026-05-07: select+buffered-read
    # was NOT actually bounded; the os.read+accumulate fix must handle
    # partial reads correctly.
    # ------------------------------------------------------------------
    def test_accumulates_partial_reads(self):
        # Helper requests 2048 bytes for a chunk. We deliver it in
        # 4 partial reads of 512 bytes each.
        partial = bytes(512)  # silent 256 samples worth
        seq = [partial, partial, partial, partial, b""]
        proc = _make_fake_proc()

        with patch("select.select",
                   return_value=([FAKE_FD], [], [])), \
             patch("os.read", side_effect=_osread_returning(seq)):
            _run_pw_reader(
                proc,
                self.stop_event,
                self.queue,
                self.lock,
                CHUNK_BYTES,
                watchdog_s=5.0,
                skip_wav_header=False,
            )

        # Exactly one full chunk should have been assembled and queued.
        self.assertEqual(
            len(self.queue), 1,
            "expected accumulator to assemble 4×512 bytes into one "
            f"{CHUNK_BYTES}-byte chunk; got {len(self.queue)} queued",
        )
        raw, _ = self.queue[0]
        self.assertEqual(raw.shape[0], CHUNK_BYTES // 2)

    # ------------------------------------------------------------------
    # 13. Partial WAV HEADER reads also accumulate correctly.
    # The historical D-state hang vector is the header read, and the
    # accumulation path is shared with chunk reads. This test pins the
    # header path explicitly — review note (slice 1.4 follow-up):
    # "the high-risk historical header path deserves its own
    # partial-header test."
    # ------------------------------------------------------------------
    def test_partial_header_accumulates_correctly(self):
        # Header is 44 bytes. Deliver it in 3 partial reads (22+11+11),
        # then a normal chunk, then EOF. Helper must accumulate the
        # header to exactly 44 bytes before processing the chunk.
        seq = [
            b"R" * 22,       # partial header 1
            b"I" * 11,       # partial header 2
            b"FF" * 5 + b"X", # partial header 3 (fills to 44)
            _silent_chunk(), # post-header chunk
            b"",             # EOF
        ]
        proc = _make_fake_proc()

        with patch("select.select",
                   return_value=([FAKE_FD], [], [])), \
             patch("os.read", side_effect=_osread_returning(seq)):
            _run_pw_reader(
                proc,
                self.stop_event,
                self.queue,
                self.lock,
                CHUNK_BYTES,
                watchdog_s=5.0,
                skip_wav_header=True,  # exercise the header accumulation
            )

        # Exactly one chunk queued — the post-header data. The 44-byte
        # accumulated header must NOT have leaked into the audio queue.
        self.assertEqual(
            len(self.queue), 1,
            "partial header must accumulate to 44 bytes and be "
            "discarded; only the post-header chunk should land in the "
            f"queue. Got {len(self.queue)} queued items.",
        )
        # And the queued chunk must have the right shape (proves no
        # off-by-one truncation from header-vs-chunk boundary).
        raw, _ = self.queue[0]
        self.assertEqual(raw.shape[0], CHUNK_BYTES // 2)

    # ------------------------------------------------------------------
    # 14. Sets the fd to non-blocking via os.set_blocking. The High
    # finding from slice 1.4 follow-up review: blocking-fd os.read can
    # still wedge despite select admission. The contract requires
    # non-blocking semantics.
    # ------------------------------------------------------------------
    def test_sets_fd_nonblocking(self):
        proc = _make_fake_proc()
        # Reader will exit immediately on EOF; we just need to verify
        # set_blocking(False) was called on the fd.
        seq = [b""]

        with patch("select.select",
                   return_value=([FAKE_FD], [], [])), \
             patch("os.read", side_effect=_osread_returning(seq)), \
             patch("os.set_blocking") as set_blocking_mock:
            _run_pw_reader(
                proc,
                self.stop_event,
                self.queue,
                self.lock,
                CHUNK_BYTES,
                watchdog_s=5.0,
                skip_wav_header=False,
            )

        set_blocking_mock.assert_called_once_with(FAKE_FD, False)

    # ------------------------------------------------------------------
    # 15. BlockingIOError on os.read is treated as "no data, retry" —
    # not as a fatal error. Race scenario: select reports ready but
    # the data was consumed between admission and read.
    # ------------------------------------------------------------------
    def test_watchdog_fires_on_slow_trickle(self):
        """Slice 1.4 follow-up CRITICAL: a slow-trickle stream (bytes
        arriving, but never enough to complete a chunk within
        watchdog_s) must still trip the watchdog. The previous
        implementation reset last_data on every partial os.read, so
        a 1-byte-every-4s feed would refresh the timestamp
        indefinitely without ever completing a chunk — wedged reader,
        watchdog never fires.

        Fix: watchdog tracks LAST FULL-CHUNK COMPLETION, not last-byte
        arrival.
        """
        # Feed a slow trickle with a real per-byte delay so chunks
        # CANNOT complete within watchdog_s. Without the sleep, the
        # mock returns microseconds-fast and 2048 bytes accumulate
        # well under the watchdog window — defeating the test intent.
        single_byte = bytes(1)
        # Infinite-ish trickle — generator yields 1 byte forever.
        def trickle():
            while True:
                yield single_byte

        gen = trickle()

        def osread_trickle(_fd, _n):
            # 50ms per byte → ~100s to accumulate 2048 bytes; well
            # past the 0.3s watchdog. This is the production-realistic
            # "stream is alive but starving" scenario.
            time.sleep(0.05)
            return next(gen)

        proc = _make_fake_proc()

        with patch("select.select",
                   return_value=([FAKE_FD], [], [])), \
             patch("os.read", side_effect=osread_trickle):
            t0 = time.monotonic()
            _run_pw_reader(
                proc,
                self.stop_event,
                self.queue,
                self.lock,
                CHUNK_BYTES,
                watchdog_s=0.3,
                skip_wav_header=False,
            )
            elapsed = time.monotonic() - t0

        # Watchdog must have fired despite the trickle.
        self.assertGreater(
            proc.kill.call_count, 0,
            "watchdog must fire on slow-trickle starvation (no full "
            "chunk in watchdog_s); previous design false-passed by "
            "resetting on every partial byte",
        )
        # Bounded time: ~watchdog_s plus iteration overhead.
        self.assertLess(
            elapsed, 1.5,
            f"watchdog should fire within ~watchdog_s on trickle; "
            f"took {elapsed:.2f}s",
        )
        # No chunk should have made it to the queue (we never
        # accumulated 2048 bytes).
        self.assertEqual(len(self.queue), 0)

    def test_blocking_io_error_continues_loop(self):
        # First os.read raises BlockingIOError (race), second returns
        # a real chunk, third EOFs.
        seq = [
            BlockingIOError("EAGAIN"),
            _silent_chunk(),
            b"",
        ]
        proc = _make_fake_proc()

        with patch("select.select",
                   return_value=([FAKE_FD], [], [])), \
             patch("os.read", side_effect=_osread_returning(seq)):
            t0 = time.monotonic()
            _run_pw_reader(
                proc,
                self.stop_event,
                self.queue,
                self.lock,
                CHUNK_BYTES,
                watchdog_s=5.0,
                skip_wav_header=False,
            )
            elapsed = time.monotonic() - t0

        # The chunk after the BlockingIOError must have made it to the
        # queue — proving the loop continued instead of bailing.
        self.assertEqual(
            len(self.queue), 1,
            "BlockingIOError must be treated as 'no data, retry'; "
            "the next successful read should still queue a chunk",
        )
        # And no proc.kill from a false watchdog fire.
        self.assertEqual(proc.kill.call_count, 0)
        self.assertLess(elapsed, 1.0)


if __name__ == "__main__":
    unittest.main()
