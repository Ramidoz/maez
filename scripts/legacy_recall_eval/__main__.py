from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from scripts.legacy_recall_eval.harness import run_eval


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Legacy Recall Eval v0 runner")
    parser.add_argument("--sandbox-root", default=None, help="defaults to a fresh temp dir")
    parser.add_argument("--expect-commit", default=None)
    args = parser.parse_args(argv)

    root = Path(args.sandbox_root or tempfile.mkdtemp(prefix="legacy_recall_eval_"))
    packet = run_eval(root, expect_commit=args.expect_commit)
    print(packet.to_json())
    return 0 if packet.overall_pass else 1


if __name__ == "__main__":
    sys.exit(main())
