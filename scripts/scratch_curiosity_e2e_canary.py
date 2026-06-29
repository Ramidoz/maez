#!/usr/bin/env python3
from __future__ import annotations

import os
import sqlite3
import sys
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if os.fspath(ROOT) not in sys.path:
    sys.path.insert(0, os.fspath(ROOT))


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: scratch_curiosity_e2e_canary.py /path/to/new/scratch-dir", file=sys.stderr)
        return 2
    scratch_root = Path(sys.argv[1])
    scratch_root_resolved = scratch_root.resolve()
    memory_root = (ROOT / "memory").resolve()
    if scratch_root_resolved == memory_root or memory_root in scratch_root_resolved.parents:
        print(
            f"curiosity scratch E2E canary refuses to write under the repo memory directory: {scratch_root}",
            file=sys.stderr,
        )
        return 2
    if scratch_root.exists():
        print(
            f"curiosity scratch E2E canary refuses to write to an existing path: {scratch_root}",
            file=sys.stderr,
        )
        return 2
    scratch_root.mkdir(parents=True)

    from core.evolution.drive_driven_curiosity import (
        EncounterSource,
        SubjectKind,
        get_registered_producer,
        record_wondering_drive_metadata,
        register_wonderings_backed_producers,
        resolve_curiosity_object,
        write_curiosity_resolution_seam_call,
    )
    from core.evolution.subjective_duration import SubjectiveDuration
    from core.evolution.temperament import Temperament
    from core.evolution.wonderings import Wonderings

    wonderings = Wonderings(db_path=scratch_root / "wonderings.db")
    temperament = Temperament(db_path=scratch_root / "temperament.db")
    subjective_duration = SubjectiveDuration(
        db_path=scratch_root / "subjective_duration.db",
        diagnostic_log_path=scratch_root / "subjective_duration.jsonl",
    )

    bond_id = "firstborn"
    marker_utc = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
    temperament.record_event(parameter="curiosity", value=5.0)
    wondering_id = wonderings.add(
        "what does this real bonded wondering become when it resolves?",
        source="manual",
        bond_id=bond_id,
    )
    record_wondering_drive_metadata(
        wonderings,
        wondering_id=wondering_id,
        bond_id=bond_id,
        encounter_source=EncounterSource.WONDERING_GENERATED.value,
        encounter_ref_digest="hmac-sha256:" + "c" * 64,
        priority_class="self_growth",
        salience=1.0,
        subject_kind=SubjectKind.SELF_MODEL,
    )
    resolve_curiosity_object(
        wonderings,
        wondering_id=wondering_id,
        conclusion="scratch curiosity canary resolved the bonded wondering",
        resolution_marker_type="explicit_self_resolved",
        resolution_marker_utc=marker_utc.timestamp(),
    )
    register_wonderings_backed_producers(wonderings)
    producer_entry = get_registered_producer(EncounterSource.WONDERING_GENERATED)
    curiosity_object = producer_entry.create({"wondering_id": wondering_id})
    if (
        curiosity_object.resolution_marker_type != "explicit_self_resolved"
        or curiosity_object.resolution_marker_utc is None
    ):
        raise RuntimeError("curiosity object did not carry resolution marker")
    result = write_curiosity_resolution_seam_call(
        curiosity_object=curiosity_object,
        temperament=temperament,
        subjective_duration=subjective_duration,
        resolution_marker_type=curiosity_object.resolution_marker_type,
        resolution_marker_utc=curiosity_object.resolution_marker_utc,
    )

    with closing(sqlite3.connect(subjective_duration.db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT meaningfulness_score, salience_event_kind, producer_ref, bond_id, producer_event_id "
            "FROM subjective_duration_salience_events "
            "WHERE bond_id = ? AND producer_event_id = ?",
            (bond_id, result.producer_event_id),
        ).fetchone()
    if row is None:
        raise LookupError("curiosity scratch canary row missing")
    expected = {
        "salience_event_kind": "meaningful_exchange",
        "producer_ref": "drive_driven_curiosity",
        "bond_id": bond_id,
    }
    failures = [
        f"{name}={row[name]!r} expected {value!r}"
        for name, value in expected.items()
        if row[name] != value
    ]
    if row["meaningfulness_score"] <= 0.0:
        failures.append(f"meaningfulness_score={row['meaningfulness_score']!r} expected > 0.0")
    if failures:
        raise RuntimeError(
            "curiosity scratch canary integrity failure: " + "; ".join(failures)
        )
    print(
        "curiosity scratch E2E canary passed: "
        f"meaningfulness_score={row['meaningfulness_score']} "
        f"resolution_marker_type={curiosity_object.resolution_marker_type} "
        f"resolution_marker_utc={curiosity_object.resolution_marker_utc}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
