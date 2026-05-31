from __future__ import annotations

import os
import sys
from pathlib import Path


_SANDBOX_PATH_OVERRIDES = {
    "MAEZ_ROUTING_OBSERVATION_DB_PATH": ("memory", "routing_observation.db"),
    "MAEZ_LEDGER_DB_PATH": ("memory", "ledger.db"),
    "MAEZ_CALENDAR_STORE_DB": ("memory", "calendar.db"),
    "MAEZ_SELF_AWARENESS_PATH": ("memory", "self_awareness.json"),
    "MAEZ_AUDIT_LOG_PATH": ("logs", "audit.jsonl"),
}


def _set_sandbox_env(sandbox_root: Path) -> None:
    os.environ["MAEZ_HOME"] = str(sandbox_root)
    os.environ["MAEZ_DATA"] = str(sandbox_root)
    os.environ["MAEZ_CONFIG"] = str(sandbox_root / "config")
    os.environ["MAEZ_CACHE"] = str(sandbox_root / ".cache")
    os.environ["MAEZ_OWNER_TIMEZONE"] = "America/Chicago"
    for key, parts in _SANDBOX_PATH_OVERRIDES.items():
        os.environ[key] = str(sandbox_root.joinpath(*parts))


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 1:
        raise SystemExit("usage: launcher.py SANDBOX_ROOT [bench args...]")
    sandbox_root = Path(args[0]).resolve()
    if sandbox_root == Path("/home/rohit/maez").resolve():
        raise SystemExit("refusing to use the real Maez home as a brain-bench sandbox")
    _set_sandbox_env(sandbox_root)
    from scripts.recall_flip_eval import sandbox

    try:
        sandbox.assert_no_real_path_overrides(sandbox_root)
    except sandbox.NotSandboxError as exc:
        raise SystemExit(str(exc)) from exc
    os.execv(
        sys.executable,
        [sys.executable, "-m", "scripts.brain_bench.bench", *args[1:]],
    )


if __name__ == "__main__":
    main()
