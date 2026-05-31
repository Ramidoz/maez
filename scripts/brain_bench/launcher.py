from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: launcher.py SANDBOX_ROOT [bench args...]")
    sandbox_root = Path(sys.argv[1]).resolve()
    os.environ["MAEZ_HOME"] = str(sandbox_root)
    os.environ["MAEZ_DATA"] = str(sandbox_root)
    os.environ["MAEZ_CONFIG"] = str(sandbox_root / "config")
    os.environ["MAEZ_CACHE"] = str(sandbox_root / ".cache")
    os.execv(
        sys.executable,
        [sys.executable, "-m", "scripts.brain_bench.bench", *sys.argv[2:]],
    )


if __name__ == "__main__":
    main()
