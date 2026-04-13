"""
scripts/run_screen_cache_worker.py — Session 11a staging harness.

Starts the real ScreenCacheWorker (calling skills.screen_perception.observe)
and prints cache snapshots on a fixed interval. Use this to manually verify
that the worker populates the cache against the real screen perception
pipeline, completely separate from maez.service.

  cd /home/rohit/maez
  source .venv/bin/activate
  python scripts/run_screen_cache_worker.py            # ctrl-c to exit
  python scripts/run_screen_cache_worker.py --interval 4 --print 2

Critical: this is a manual diagnostic only. It is NOT registered with
systemd and the daemon never imports it.
"""

from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.perception_cache import get_cache
from skills.screen_cache_worker import ScreenCacheWorker, SOURCE_NAME


def main() -> int:
    p = argparse.ArgumentParser(description='Staging harness for the screen cache worker.')
    p.add_argument('--interval', type=float, default=8.0,
                   help='worker refresh interval in seconds (default 8)')
    p.add_argument('--timeout', type=float, default=30.0,
                   help='per-observe timeout in seconds (default 30)')
    p.add_argument('--print', dest='print_every', type=float, default=2.0,
                   help='cache snapshot print cadence in seconds (default 2)')
    args = p.parse_args()

    cache = get_cache()
    worker = ScreenCacheWorker(
        cache=cache,
        interval_s=args.interval,
        observe_timeout_s=args.timeout,
    )

    stop = {'flag': False}
    def _on_signal(signum, frame):
        print(f"\nreceived signal {signum}, stopping worker...")
        stop['flag'] = True
    signal.signal(signal.SIGINT,  _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    print(f"starting ScreenCacheWorker (interval={args.interval}s, timeout={args.timeout}s)")
    print("press Ctrl-C to stop\n")
    worker.start()

    try:
        while not stop['flag']:
            entry = cache.get(SOURCE_NAME)
            if entry is None:
                print("  [no entry yet]")
            else:
                line = (
                    f"  freshness={entry.freshness_state:7s}  "
                    f"age_ms={entry.age_ms:6d}  "
                    f"version={entry.version:3d}  "
                    f"has_value={entry.value is not None}"
                )
                if entry.error:
                    line += f"  error={entry.error[:60]!r}"
                print(line)
            time.sleep(args.print_every)
    finally:
        worker.stop()
        print("worker stopped.")
        # Final snapshot for inspection
        snap = cache.snapshot()
        print("final snapshot:")
        print(json.dumps(snap, indent=2, default=str))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
