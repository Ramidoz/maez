# Nervous-System v0 Slice A Task 0 Proof

VERDICT: GO

## Rhythm API
- Command: `rg -n "def rhythm_context|def humanize_elapsed|rhythm_current_gap_s|rhythm_current_gap_percentile_all_time" core/evolution/subjective_duration.py tests/test_rhythm_context.py`
- Match counts: `tests/test_rhythm_context.py:8`, `core/evolution/subjective_duration.py:5`.
- `SubjectiveDuration.rhythm_context()` exists at `core/evolution/subjective_duration.py:697` and emits raw rhythm facts.
- Required fields confirmed in `rhythm_context()`: `rhythm_current_gap_s`, `rhythm_recent_gap_median_s`, `rhythm_all_time_gap_median_s`, `rhythm_recent_sample_count`, `rhythm_all_time_sample_count`, and `rhythm_current_gap_percentile_all_time`.
- Additional rhythm facts currently emitted: `rhythm_recent_gap_iqr_s`, `rhythm_all_time_gap_iqr_s`.
- `humanize_elapsed()` exists at `core/evolution/subjective_duration.py:471` for deterministic elapsed rendering.
- `_default_db_path()` exists at `core/evolution/subjective_duration.py:153`.

## Read-Only Probe
- Probe command:

```bash
/home/rohit/maez/.venv/bin/python - <<'PY'
import os, sqlite3, tempfile
from contextlib import closing
from datetime import datetime, timedelta, timezone
from core.evolution.subjective_duration import SubjectiveDuration

root = tempfile.mkdtemp()
inst = SubjectiveDuration(db_path=os.path.join(root, "subjective_duration.db"))
t0 = datetime(2026, 6, 20, 8, 0, tzinfo=timezone.utc)
inst.current(now_utc=t0)
with closing(sqlite3.connect(inst.db_path)) as conn:
    conn.execute(
        "INSERT INTO subjective_duration_salience_events "
        "(ts_utc, salience_event_kind, owner_auth_class, is_canary) VALUES (?,?,?,?)",
        (t0.isoformat(), "owner_contact", "cockpit", 0),
    )
    conn.commit()
    before = (
        conn.execute("SELECT COUNT(*) FROM subjective_duration_samples").fetchone()[0],
        conn.execute("SELECT COUNT(*) FROM subjective_duration_salience_events").fetchone()[0],
    )
ctx = inst.rhythm_context(now=t0 + timedelta(hours=2))
with closing(sqlite3.connect(inst.db_path)) as conn:
    after = (
        conn.execute("SELECT COUNT(*) FROM subjective_duration_samples").fetchone()[0],
        conn.execute("SELECT COUNT(*) FROM subjective_duration_salience_events").fetchone()[0],
    )
print(ctx is not None, before, after)
assert ctx is not None
assert before == after
PY
```

- Exact probe result: `True (1, 1) (1, 1)`.
- Sample/event counts before: `(1, 1)`.
- Sample/event counts after: `(1, 1)`.
- Result: `ctx is not None` and sample/event counts are unchanged.

## Self-Card Seam
- Command: `sed -n '1,430p' core/routing/self_card.py`.
- `SelfCardLine` can carry a time line without prompt renderer changes.
- Evidence: `SelfCardLine` already has `label`, `text`, `source`, `source_ref`, and `source_sha256`; `render()` formats arbitrary line metadata uniformly.
- Receipt support already records `line_sources`, `line_source_refs`, and `line_sha256`.

## Focused Gating Seam
- Commands:
  - `sed -n '470,525p' core/routing/focused_cognition.py`
  - `sed -n '1328,1362p' core/routing/focused_cognition.py`
  - `rg -n "_safe_self_card\\(" core/routing/focused_cognition.py tests`
- `_safe_self_card()` is defined at `core/routing/focused_cognition.py:501`.
- `_safe_self_card()` is called at `core/routing/focused_cognition.py:1335`.
- The only current call is guarded by `if self_card_shadow or self_card_enabled:`.
- New time flags must be added to the existing self-card assembly condition.
- All time flags off means no time reader call.

## Rails
- Use rhythm facts, not `felt_phrase` / `felt_value`.
- No owner-reaction outcome signal.
- No soul/memory mutation.
