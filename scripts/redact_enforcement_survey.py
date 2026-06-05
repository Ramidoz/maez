"""Content-free survey gating the redact-class default-on.

Emits counts, ratios, and coherence flags only -- never sample content. See
docs/superpowers/specs/2026-06-05-redact-class-enforcement-flip-design.md.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing


_PROSE = (
    "We reviewed the recall plan this morning and agreed the temporal slice "
    "lands before the embodiment work; notes captured in the usual place."
)
_PII_DENSE = (
    "contacts: a@x.test b@y.test c@z.test phones 555-0101 555-0102 555-0103 "
    "keys sk-aaaa1111 sk-bbbb2222 path /home/owner/secret.txt"
)
_MIXED = "PUBLIC-CONTEXT-OK reach me at owner@x.test and 555-0199 then continue."


def _impact(text: str) -> dict:
    from core.safety.cloud_redactor import redact_for_cloud

    result = redact_for_cloud(text)
    original = len(text)
    masked = max(0, original - len(result.text))
    ratio = (masked / original) if original else 0.0
    stripped = result.text.strip()
    near_empty = len(stripped) < max(8, int(0.15 * original))
    return {
        "masking_ratio": round(ratio, 4),
        "pii_counts": dict(getattr(result, "pii_counts", {}) or {}),
        "near_empty": bool(near_empty),
    }


def survey(db_path: str | None = None) -> dict:
    volume = None
    if db_path:
        try:
            with closing(sqlite3.connect(db_path)) as con:
                volume = con.execute(
                    "SELECT COUNT(*) FROM calls WHERE egress_decision='redact'"
                ).fetchone()[0]
        except sqlite3.Error:
            volume = None

    prose = _impact(_PROSE)
    dense = _impact(_PII_DENSE)
    mixed = _impact(_MIXED)
    no_go = (
        prose["masking_ratio"] > 0.25
        or prose["near_empty"]
        or mixed["near_empty"]
    )
    return {
        "schema": "redact_enforcement_survey.v1",
        "redact_volume": volume,
        "prose": prose,
        "pii_dense": dense,
        "mixed": mixed,
        "provisional_verdict": "NO_GO" if no_go else "CLEAN",
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=None)
    args = parser.parse_args()
    print(json.dumps(survey(args.db), indent=2, sort_keys=True))
