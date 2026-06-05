"""Content-free survey gating the redact-class default-on.

Emits counts, redaction signals, and coherence flags only -- never sample content. See
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


def _impact(text: str, *, public_marker: str | None = None) -> dict:
    from core.safety.cloud_redactor import redact_for_cloud

    result = redact_for_cloud(text)
    original = len(text)
    stripped = result.text.strip()
    near_empty = len(stripped) < max(8, int(0.15 * original))
    total_redactions = int(result.total_redactions())
    impact = {
        "changed": bool(result.changed),
        "pii_counts": dict(getattr(result, "pii_counts", {}) or {}),
        "internal_counts": dict(getattr(result, "internal_counts", {}) or {}),
        "total_redactions": total_redactions,
        "redactions_per_1k_chars": (
            round((total_redactions * 1000) / original, 4) if original else 0.0
        ),
        "output_to_input_ratio": (
            round(len(result.text) / original, 4) if original else 0.0
        ),
        "near_empty": bool(near_empty),
    }
    if public_marker is not None:
        impact["public_marker_survived"] = bool(public_marker in result.text)
    return impact


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
    mixed = _impact(_MIXED, public_marker="PUBLIC-CONTEXT-OK")
    no_go = (
        prose["changed"]
        or prose["near_empty"]
        or mixed["near_empty"]
        or not dense["changed"]
        or not dense["total_redactions"]
        or not mixed["changed"]
        or not mixed["total_redactions"]
        or not mixed["public_marker_survived"]
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
