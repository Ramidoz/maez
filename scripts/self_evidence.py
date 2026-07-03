"""Owner inspection surface for A6 Self-Evidence.

The surface is deliberately small: it renders receipt counts, not a first-person
claim about what those counts mean.
"""

from __future__ import annotations

import json
import sys

from core.infra.env_flags import strict_env_flag


def _render_digest(digest: dict) -> str:
    lines = ["self-evidence integrity receipt index"]
    for name, source in (digest.get("sources") or {}).items():
        if not isinstance(source, dict):
            continue
        status = source.get("status", "unknown")
        fields = []
        for key in (
            "retained_rows",
            "count",
            "total_veto_events",
            "active_episodes",
            "total_occurrences",
            "coverage",
        ):
            if key in source:
                fields.append(f"{key}={source[key]}")
        suffix = (" " + " ".join(fields)) if fields else ""
        lines.append(f"{name}: status={status}{suffix}")
    lines.append(json.dumps(digest, sort_keys=True, indent=2))
    return "\n".join(lines)


def render(argv: list[str] | None = None) -> str:
    args = list(argv or [])
    if args and args[0] not in {"show"}:
        return "usage: self_evidence.py show"
    if not strict_env_flag("MAEZ_SELF_EVIDENCE"):
        return "self-evidence surface disabled (set MAEZ_SELF_EVIDENCE=1)"

    from core.learning import self_evidence

    return _render_digest(self_evidence.self_evidence_digest())


def main(argv: list[str] | None = None) -> int:
    print(render(sys.argv[1:] if argv is None else argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
