# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Content-free file-descriptor forensics for daemon liveness incidents."""

from __future__ import annotations

import os
from collections import Counter


def _fd_target_type(target: str) -> str:
    if target.startswith("socket:"):
        return "socket"
    if target.startswith("pipe:"):
        return "pipe"
    if target.startswith("anon_inode:"):
        return "anon_inode"
    if target.startswith("/"):
        return "file"
    if target:
        return "other"
    return "unknown"


def fd_forensics_snapshot(*, pid: int | None = None) -> dict:
    """Return a path-free snapshot of open FD pressure for a process.

    The caller gets counts and buckets only. Symlink targets under /proc are
    used for classification but never returned, because this payload can be
    exposed through /health and body tiles.
    """

    if pid is None:
        pid = os.getpid()
    fd_root = f"/proc/{int(pid)}/fd"
    task_root = f"/proc/{int(pid)}/task"
    try:
        fd_names = os.listdir(fd_root)
        buckets: Counter[str] = Counter()
        for name in fd_names:
            try:
                target = os.readlink(os.path.join(fd_root, name))
            except OSError:
                target = ""
            buckets[_fd_target_type(target)] += 1
        try:
            thread_count = len(os.listdir(task_root))
        except OSError:
            thread_count = None
        return {
            "state": "captured",
            "pid": int(pid),
            "fd_count": len(fd_names),
            "by_type": dict(sorted(buckets.items())),
            "thread_count": thread_count,
        }
    except OSError as exc:
        return {
            "state": "unavailable",
            "pid": int(pid),
            "fd_count": None,
            "by_type": {},
            "thread_count": None,
            "error_class": type(exc).__name__,
        }
