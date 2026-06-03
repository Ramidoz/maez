# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Send a content-free owner alert when systemd holds Maez after crashlooping."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _maez_home() -> Path:
    return Path(os.environ.get("MAEZ_HOME") or Path(__file__).resolve().parents[1])


MAEZ_HOME = _maez_home()
sys.path.insert(0, str(MAEZ_HOME))

from skills.dev_notifier import send_service_card


def _unit_properties(unit: str) -> dict[str, str]:
    props = [
        "ActiveState",
        "SubState",
        "Result",
        "NRestarts",
        "ExecMainStatus",
        "MainPID",
    ]
    try:
        proc = subprocess.run(
            ["systemctl", "--user", "show", unit, *(f"-p{p}" for p in props), "--no-pager"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception as exc:
        return {"probe_error": type(exc).__name__}

    parsed: dict[str, str] = {}
    for line in (proc.stdout or "").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        parsed[key] = value
    if proc.returncode != 0:
        parsed["probe_returncode"] = str(proc.returncode)
    return parsed


def _normalize_unit(raw: str) -> str:
    unit = (raw or "maez.service").strip()
    if "." not in unit:
        unit = f"{unit}.service"
    return unit


def _details(unit: str, props: dict[str, str]) -> str:
    if "probe_error" in props:
        return f"systemd probe failed: {props['probe_error']}. Check {unit} locally."
    parts = [
        f"state={props.get('ActiveState', 'unknown')}/{props.get('SubState', 'unknown')}",
        f"result={props.get('Result', 'unknown')}",
        f"restarts={props.get('NRestarts', 'unknown')}",
        f"exit={props.get('ExecMainStatus', 'unknown')}",
    ]
    return "; ".join(parts) + f". Unit held by restart backstop: systemctl --user status {unit}"


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    unit = _normalize_unit(args[0] if args else "maez.service")
    props = _unit_properties(unit)
    send_service_card(
        unit,
        "restart backstop tripped",
        _details(unit, props),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
