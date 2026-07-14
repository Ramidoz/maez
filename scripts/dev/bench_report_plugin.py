"""pytest plugin: append exact node ids and outcomes as JSON lines."""

from __future__ import annotations

import json
import os

_FAILED_NODEIDS_BY_PATH: dict[str, set[str]] = {}


def pytest_runtest_logreport(report) -> None:
    """Record call reports and failures from every pytest phase."""
    if not (report.when == "call" or report.failed):
        return
    path = os.environ.get("BENCH_REPORT_PATH")
    if path:
        if report.failed:
            failed_nodeids = _FAILED_NODEIDS_BY_PATH.setdefault(path, set())
            if report.nodeid in failed_nodeids:
                return
            failed_nodeids.add(report.nodeid)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "id": report.nodeid,
                        "when": report.when,
                        "outcome": report.outcome,
                    }
                )
                + "\n"
            )
