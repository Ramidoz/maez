"""Minimal S6 capsule helper.

This helper assembles hash-chain events for local operator drafting. It does
not activate succession, grant live access, read archive content, or talk to any
live conversation surface.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.governance import successor_governance as s6


DEFAULT_CAPSULE_PATH = Path("memory/successor_governance/lineage_capsule.jsonl")


def build_marker_request(
    path: Path,
    event_type: str,
    payload: dict,
    *,
    capsule_id: str = "s6_capsule_founder",
) -> dict[str, str]:
    existing = s6.load_events_jsonl(path) if path.exists() else []
    previous_hash = existing[-1].event_hash if existing else ""
    return {
        "capsule_id": capsule_id,
        "directive_event_type": event_type,
        "directive_payload_hash": s6.canonical_hash(payload),
        "directive_statement_hash": str(payload.get("directive_statement_hash") or ""),
        "previous_capsule_event_hash": previous_hash,
    }


def append_capsule_event(
    path: Path,
    event_type: str,
    payload: dict,
    *,
    marker: s6.HumanOriginMarker,
    capsule_id: str = "s6_capsule_founder",
) -> s6.DirectiveEvent:
    existing = s6.load_events_jsonl(path) if path.exists() else []
    previous_hash = existing[-1].event_hash if existing else None
    event = s6.create_directive_event(
        "s6_event_" + s6.canonical_hash({"path": str(path), "count": len(existing), "payload": payload})[:24],
        event_type,
        capsule_id,
        s6.utc_now_iso(),
        payload,
        marker=marker,
        previous_event_hash=previous_hash,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(s6.event_to_json(event) + "\n")
    return event


def _main() -> int:
    parser = argparse.ArgumentParser(description="Append a local S6 successor-governance event.")
    parser.add_argument("event_type")
    parser.add_argument("--payload-json", required=True)
    parser.add_argument("--path", default=str(DEFAULT_CAPSULE_PATH))
    parser.add_argument(
        "--print-marker-request",
        action="store_true",
        help="Print the marker fields that must be minted by the separate origin-writer seam.",
    )
    args = parser.parse_args()
    payload = json.loads(args.payload_json)
    if args.print_marker_request:
        print(json.dumps(build_marker_request(Path(args.path), args.event_type, payload), sort_keys=True))
        return 0
    parser.error("S6 append requires an in-process HumanOriginMarker from the separate origin-writer seam")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
