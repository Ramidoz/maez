"""Bounded B0 runner. NO daemon, NO infinite loop -- that is B2.

Usage: python -m jetson_presence.run [--once | --loops N]
"""

from __future__ import annotations

import argparse
import os
import time
from datetime import datetime, timezone

from jetson_presence.capture import Camera
from jetson_presence.config import load_config
from jetson_presence.emitter import post_label
from jetson_presence.presence_loop import run_once


def _now_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_curtained(sentinel_path: str):
    return os.path.exists(sentinel_path)


def _run_one_cycle(*, cfg, camera):
    return run_once(
        camera=camera,
        emit=lambda label: post_label(cfg.host_url, cfg.intake_path, token=cfg.token, label=label),
        is_curtained=lambda: _is_curtained(cfg.curtain_sentinel),
        now_ts=_now_ts,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Jetson presence B0 (bounded).")
    g = parser.add_mutually_exclusive_group()
    g.add_argument("--once", action="store_true", help="run a single cycle")
    g.add_argument("--loops", type=int, default=1, help="run N cycles then exit (default 1)")
    args = parser.parse_args(argv)
    if args.loops < 1:
        parser.error("--loops must be a positive integer")
    loops = 1 if args.once else args.loops

    cfg = load_config()
    camera = Camera(device_index=cfg.device_index)
    try:
        for i in range(loops):
            _run_one_cycle(cfg=cfg, camera=camera)
            if i + 1 < loops:
                time.sleep(cfg.cadence_seconds)
    finally:
        camera.release()


if __name__ == "__main__":
    main()
