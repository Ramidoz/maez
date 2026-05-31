from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sandbox-root")
    args, rest = parser.parse_known_args()

    sandbox_root = Path(args.sandbox_root) if args.sandbox_root else Path(
        tempfile.mkdtemp(prefix="maez_recall_eval_")
    )
    os.environ["MAEZ_HOME"] = str(sandbox_root)
    os.environ["MAEZ_DATA"] = str(sandbox_root)
    os.environ["MAEZ_CONFIG"] = str(sandbox_root / "config")
    os.environ["MAEZ_CACHE"] = str(sandbox_root / ".cache")
    os.environ["MAEZ_OWNER_TIMEZONE"] = "America/Chicago"

    argv = [
        sys.executable,
        "-m",
        "scripts.recall_flip_eval.harness",
        "--sandbox-root",
        str(sandbox_root),
        *rest,
    ]
    os.execv(sys.executable, argv)


if __name__ == "__main__":
    main()

