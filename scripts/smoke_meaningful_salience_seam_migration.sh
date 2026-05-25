#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  printf 'usage: %s /path/to/source_subjective_duration.db /path/to/scratch_copy.db\n' "$0" >&2
  exit 2
fi

source_db="$1"
scratch_db="$2"
repo_root="$(cd "$(dirname "$0")/.." && pwd -P)"
python_bin="${PYTHON:-python3}"

cp "$source_db" "$scratch_db"
cd "$repo_root"
MAEZ_SUBJECTIVE_DURATION_DB="$scratch_db" "$python_bin" - <<'PY'
from core.evolution.subjective_duration import SubjectiveDuration

SubjectiveDuration()
SubjectiveDuration()
PY

sqlite3 "$scratch_db" "PRAGMA table_info(subjective_duration_salience_events);" | grep -q 'bond_id'
sqlite3 "$scratch_db" "PRAGMA table_info(subjective_duration_salience_events);" | grep -q 'producer_event_id'
sqlite3 "$scratch_db" "PRAGMA table_info(subjective_duration_salience_events);" | grep -q 'producer_temperament_before_json'
sqlite3 "$scratch_db" "PRAGMA table_info(subjective_duration_salience_events);" | grep -q 'producer_temperament_after_json'
sqlite3 "$scratch_db" "PRAGMA table_info(subjective_duration_salience_events);" | grep -q 'is_canary'
sqlite3 "$scratch_db" "PRAGMA index_list(subjective_duration_salience_events);" | grep -q 'idx_sd_events_bond_producer'

printf 'meaningful-salience seam migration smoke passed: %s\n' "$scratch_db"
