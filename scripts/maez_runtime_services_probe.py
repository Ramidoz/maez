from __future__ import annotations

import json
import sys

import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from core.infra.runtime_services import runtime_services_snapshot


def main(argv: list[str] | None = None) -> int:
    del argv
    try:
        snapshot = runtime_services_snapshot()
    except Exception as exc:
        print(
            json.dumps(
                {
                    "schema_version": "maez_runtime_services.v0",
                    "overall": "unknown",
                    "error_class": exc.__class__.__name__,
                },
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(snapshot, sort_keys=True, indent=2))
    return 2 if snapshot.get("overall") == "degraded" else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
