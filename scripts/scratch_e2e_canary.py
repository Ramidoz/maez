#!/usr/bin/env python3
from __future__ import annotations

import os
import sqlite3
import sys
import uuid
from contextlib import closing
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if os.fspath(ROOT) not in sys.path:
    sys.path.insert(0, os.fspath(ROOT))


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: scratch_e2e_canary.py /path/to/scratch_subjective_duration.db", file=sys.stderr)
        return 2
    scratch_db_path = Path(sys.argv[1])
    if scratch_db_path.exists():
        print(
            f"scratch E2E canary refuses to write to an existing DB: {scratch_db_path}",
            file=sys.stderr,
        )
        return 2
    if (ROOT / "memory") in scratch_db_path.resolve().parents:
        print(
            f"scratch E2E canary refuses to write under the repo memory directory: {scratch_db_path}",
            file=sys.stderr,
        )
        return 2
    scratch_db_path.parent.mkdir(parents=True, exist_ok=True)
    os.environ["MAEZ_SUBJECTIVE_DURATION_DB"] = os.fspath(scratch_db_path)

    from core.evolution.subjective_duration import ProducerRef, SubjectiveDuration

    scratch_fixture_bond_id = "_SCRATCH_FIXTURE"
    sd = SubjectiveDuration()
    before = {
        "curiosity": 5.0,
        "awareness": 5.0,
        "persistence": 5.0,
        "joy": 5.0,
        "warmth": 5.0,
        "caution": 5.0,
    }
    after = {**before, "curiosity": 6.0}
    event_id_str = f"scratch_canary_{uuid.uuid4()}"

    sd.record_salience_event(
        salience_event_kind="meaningful_exchange",
        producer_ref=ProducerRef.MANUAL_TEST_PRODUCER.value,
        bond_id=scratch_fixture_bond_id,
        producer_event_id=event_id_str,
        producer_temperament_before=before,
        producer_temperament_after=after,
        is_canary=True,
    )
    with closing(sqlite3.connect(scratch_db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT meaningfulness_score, is_canary, salience_event_kind, producer_ref, bond_id "
            "FROM subjective_duration_salience_events "
            "WHERE bond_id = ? AND producer_event_id = ?",
            (scratch_fixture_bond_id, event_id_str),
        ).fetchone()
    if row is None:
        raise LookupError("scratch canary row missing")
    assert row["meaningfulness_score"] > 0.0
    assert row["is_canary"] == 1
    assert row["salience_event_kind"] == "meaningful_exchange"
    assert row["producer_ref"] == ProducerRef.MANUAL_TEST_PRODUCER.value
    assert row["bond_id"] == scratch_fixture_bond_id
    print(f"scratch E2E canary passed: meaningfulness_score={row['meaningfulness_score']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
