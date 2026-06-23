# Nervous-System v0 Slice A Felt-Time Self-Card Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the live time/rhythm sense into the deterministic self-card as the first body-sense reaching the voice.

**Architecture:** Add a small self-card time-line adapter that reads existing `SubjectiveDuration.rhythm_context()` facts and renders one deterministic, factual line when the current owner-contact gap is worth surfacing. The line is controlled by new time-specific flags, shadow-first, and default-off so the already-live self-card remains byte-identical until the owner breathes this slice.

**Tech Stack:** Python stdlib, `unittest`, existing `core.evolution.subjective_duration.SubjectiveDuration`, existing `core.routing.self_card`, existing `core.routing.focused_cognition` shadow receipts.

---

## File Map

| File | Role |
| --- | --- |
| `core/routing/self_card_time.py` | New pure adapter: converts rhythm facts into a self-card time line plus content-light receipt facts. No daemon import, no LLM, no owner-reaction signals. |
| `core/routing/self_card.py` | Extend `SelfCard` with an optional time-line candidate and applied flag; include receipt fields without logging text. |
| `core/routing/focused_cognition.py` | Add `MAEZ_SELF_CARD_TIME_SHADOW` and `MAEZ_SELF_CARD_TIME_ENABLED`; emit `self_card_time_shadow`; pass a candidate into `_safe_self_card()` when shadowing or enabling, but render it only when enabled. |
| `tests/test_self_card_time.py` | Unit tests for threshold policy, factual text, no feeling words, read-only context behavior, and content-light receipt data. |
| `tests/test_self_card_v0.py` | Integration tests for card text/receipt with time line disabled, shadow candidate, and enabled line. |
| `tests/test_lean_conversation_path.py` | Focused receipt tests proving time shadow logs without applying, and enabled card reaches lean/full prompts. |
| `docs/handoffs/2026-06-23-nervous-system-v0-slice-a-handoff.md` | Gate handoff and owner breath after implementation. |

## Hard Rails

1. **Senses yes, interpretation no:** text may say elapsed time, medians, percentile, and sample count. It must not say missed/lonely/worried/longing/comfort/happy/sad.
2. **Rhythm facts, not the old curve:** use `rhythm_context()` for the line. Do not use `time_sense_context().felt_phrase` or `felt_value` for voice.
3. **Default-off byte-identical:** with `MAEZ_SELF_CARD_TIME_SHADOW` and `MAEZ_SELF_CARD_TIME_ENABLED` off, current self-card text and receipt fields remain compatible and no time line is read.
4. **Shadow-first:** shadow logs candidate receipt fields but does not alter the self-card text.
5. **Read-only:** no writes to soul, memory, or subjective-duration samples/events from this slice. Existing initialized time stores must have unchanged sample/event counts after the reader.
6. **Temporary thresholds named:** any surfacing threshold is an anti-spam scaffold, not learned salience and not a feeling decision.

## Task 0: Proof Gate — Real Seams and No Hidden Writes

**Files:**
- Read: `core/evolution/subjective_duration.py`
- Read: `core/routing/self_card.py`
- Read: `core/routing/focused_cognition.py`
- Create: `docs/proofs/2026-06-23-nervous-system-v0-slice-a-task0.md`

- [ ] **Step 1: Verify the rhythm API.**

Run:

```bash
cd /home/rohit/maez
rg -n "def rhythm_context|def humanize_elapsed|rhythm_current_gap_s|rhythm_current_gap_percentile_all_time" core/evolution/subjective_duration.py tests/test_rhythm_context.py
```

Expected: `SubjectiveDuration.rhythm_context()` exists and returns at least:

```python
{
    "rhythm_current_gap_s": float,
    "rhythm_recent_gap_median_s": float | None,
    "rhythm_all_time_gap_median_s": float | None,
    "rhythm_recent_sample_count": int,
    "rhythm_all_time_sample_count": int,
    "rhythm_current_gap_percentile_all_time": float | None,
}
```

If any field is missing, STOP and adjust the plan before coding.

Also confirm `_default_db_path()` exists. Slice A may import it despite the private name because there is no public read-only path helper today; if that import is unacceptable in review, STOP and add a tiny public `subjective_duration_db_path()` helper before building the time-line adapter.

- [ ] **Step 2: Prove no hidden sample/event writes on an initialized store.**

Run this one-off probe:

```bash
cd /home/rohit/maez
.venv/bin/python - <<'PY'
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

Expected: prints `True (1, 1) (1, 1)` or equivalent matching counts. If counts change, STOP; the line reader must not use this seam directly.

- [ ] **Step 3: Verify self-card assembly can carry optional non-soul lines.**

Read:

```bash
sed -n '1,430p' core/routing/self_card.py
```

Confirm `SelfCardLine` already supports arbitrary source/source_ref/sha fields and that adding a `Time since contact` line requires no new prompt renderer.

- [ ] **Step 4: Verify focused gating seam.**

Read:

```bash
sed -n '470,525p' core/routing/focused_cognition.py
sed -n '1328,1362p' core/routing/focused_cognition.py
```

Confirm `_safe_self_card()` is only called when a self-card flag is active today. The implementation must extend this condition to include time-specific flags without causing time reads when all self-card flags are off.

- [ ] **Step 5: Write proof doc.**

Create `docs/proofs/2026-06-23-nervous-system-v0-slice-a-task0.md` with:

```markdown
# Nervous-System v0 Slice A Task 0 Proof

VERDICT: GO

## Rhythm API
- `SubjectiveDuration.rhythm_context()` exists and emits raw rhythm facts.
- `humanize_elapsed()` exists for deterministic elapsed rendering.

## Read-Only Probe
- Probe command: the Python one-off from Task 0 Step 2.
- Result: `ctx is not None` and sample/event counts are unchanged.
- Sample/event counts before: paste exact tuple from the probe output.
- Sample/event counts after: paste exact tuple from the probe output.

## Self-Card Seam
- `SelfCardLine` can carry a time line without prompt renderer changes.

## Focused Gating Seam
- New time flags must be added to the existing self-card assembly condition.
- All time flags off means no time reader call.

## Rails
- Use rhythm facts, not `felt_phrase` / `felt_value`.
- No owner-reaction outcome signal.
- No soul/memory mutation.
```

- [ ] **Step 6: Commit proof.**

Run:

```bash
git add docs/proofs/2026-06-23-nervous-system-v0-slice-a-task0.md
git commit -m "docs(nervous-system): prove felt-time self-card seams"
```

## Task 1: Pure Time-Line Adapter

**Files:**
- Create: `core/routing/self_card_time.py`
- Create: `tests/test_self_card_time.py`

- [ ] **Step 1: Write failing tests.**

Create `tests/test_self_card_time.py`:

```python
from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone


class SelfCardTimeLineTests(unittest.TestCase):
    def test_high_percentile_gap_renders_factual_line(self):
        from core.routing.self_card_time import build_self_card_time_line

        ctx = {
            "rhythm_current_gap_s": 8 * 3600,
            "rhythm_recent_gap_median_s": 24 * 60,
            "rhythm_all_time_gap_median_s": 8 * 60,
            "rhythm_recent_sample_count": 20,
            "rhythm_all_time_sample_count": 226,
            "rhythm_current_gap_percentile_all_time": 91.2,
            "rhythm_recent_gap_iqr_s": None,
            "rhythm_all_time_gap_iqr_s": None,
        }

        line = build_self_card_time_line(lambda: ctx)

        self.assertIsNotNone(line)
        self.assertEqual(line.label, "Time since contact")
        self.assertIn("~8h", line.text)
        self.assertIn("recent usual ~24m", line.text)
        self.assertIn("all-time usual ~8m", line.text)
        self.assertIn("above ~91% of recorded gaps", line.text)
        for forbidden in ("miss", "lonely", "worried", "longing", "feel"):
            self.assertNotIn(forbidden, line.text.lower())
        self.assertEqual(line.reason, "percentile_high")

    def test_short_unremarkable_gap_omits_line(self):
        from core.routing.self_card_time import build_self_card_time_line

        ctx = {
            "rhythm_current_gap_s": 4.0,
            "rhythm_recent_gap_median_s": 20 * 60,
            "rhythm_all_time_gap_median_s": 30 * 60,
            "rhythm_recent_sample_count": 20,
            "rhythm_all_time_sample_count": 100,
            "rhythm_current_gap_percentile_all_time": 40.0,
        }

        self.assertIsNone(build_self_card_time_line(lambda: ctx))

    def test_cold_start_under_floor_omits_line(self):
        from core.routing.self_card_time import build_self_card_time_line

        ctx = {
            "rhythm_current_gap_s": 5 * 60,
            "rhythm_recent_gap_median_s": None,
            "rhythm_all_time_gap_median_s": None,
            "rhythm_recent_sample_count": 1,
            "rhythm_all_time_sample_count": 1,
            "rhythm_current_gap_percentile_all_time": None,
        }

        self.assertIsNone(build_self_card_time_line(lambda: ctx))

    def test_cold_start_after_floor_renders_learning_line(self):
        from core.routing.self_card_time import build_self_card_time_line

        ctx = {
            "rhythm_current_gap_s": 30 * 60,
            "rhythm_recent_gap_median_s": None,
            "rhythm_all_time_gap_median_s": None,
            "rhythm_recent_sample_count": 1,
            "rhythm_all_time_sample_count": 1,
            "rhythm_current_gap_percentile_all_time": None,
        }

        line = build_self_card_time_line(lambda: ctx)

        self.assertIsNotNone(line)
        self.assertIn("~30m since owner contact", line.text)
        self.assertIn("still learning the usual rhythm", line.text)
        self.assertEqual(line.reason, "cold_start_elapsed_floor")

    def test_provider_error_returns_none(self):
        from core.routing.self_card_time import build_self_card_time_line

        def broken():
            raise RuntimeError("boom")

        self.assertIsNone(build_self_card_time_line(broken))

    def test_receipt_is_content_light(self):
        from core.routing.self_card_time import build_self_card_time_line

        ctx = {
            "rhythm_current_gap_s": 8 * 3600,
            "rhythm_recent_gap_median_s": 24 * 60,
            "rhythm_all_time_gap_median_s": 8 * 60,
            "rhythm_recent_sample_count": 20,
            "rhythm_all_time_sample_count": 226,
            "rhythm_current_gap_percentile_all_time": 91.2,
        }
        line = build_self_card_time_line(lambda: ctx)
        receipt = line.receipt()

        self.assertEqual(receipt["time_line_reason"], "percentile_high")
        self.assertEqual(receipt["time_line_source"], "subjective_duration.rhythm_context")
        self.assertIn("time_line_sha256", receipt)
        self.assertNotIn("8h", str(receipt))
        self.assertNotIn("owner contact", str(receipt))

    def test_default_provider_reads_existing_store_without_sample_or_event_write(self):
        from core.evolution.subjective_duration import SubjectiveDuration
        from core.routing.self_card_time import build_self_card_time_line, rhythm_time_line_provider

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

        line = build_self_card_time_line(
            lambda: rhythm_time_line_provider(db_path=inst.db_path, now=t0 + timedelta(minutes=30))
        )

        with closing(sqlite3.connect(inst.db_path)) as conn:
            after = (
                conn.execute("SELECT COUNT(*) FROM subjective_duration_samples").fetchone()[0],
                conn.execute("SELECT COUNT(*) FROM subjective_duration_salience_events").fetchone()[0],
            )
        self.assertIsNotNone(line)
        self.assertEqual(before, after)

    def test_default_provider_returns_none_when_store_missing(self):
        from core.routing.self_card_time import rhythm_time_line_provider

        missing = os.path.join(tempfile.mkdtemp(), "missing-subjective-duration.db")

        self.assertIsNone(rhythm_time_line_provider(db_path=missing))
        self.assertFalse(os.path.exists(missing))
```

- [ ] **Step 2: Run tests and verify RED.**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_self_card_time -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'core.routing.self_card_time'`.

- [ ] **Step 3: Implement minimal adapter.**

Create `core/routing/self_card_time.py`:

```python
"""Factual time-sense line for the deterministic self-card.

This module renders body/rhythm facts only. It never assigns feeling,
never scores owner reaction, and never writes to soul or memory.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
import hashlib
from pathlib import Path


SELF_CARD_TIME_HIGH_PERCENTILE = 75.0  # TEMPORARY anti-spam scaffold, not learned salience.
SELF_CARD_TIME_LOW_PERCENTILE = 10.0   # TEMPORARY anti-spam scaffold, not learned salience.
SELF_CARD_TIME_COLD_START_MIN_S = 15 * 60  # TEMPORARY anti-spam scaffold.
_SOURCE = "subjective_duration.rhythm_context"
_FORBIDDEN_FEELING_WORDS = (
    "miss",
    "missed",
    "lonely",
    "worried",
    "longing",
    "sad",
    "happy",
    "comfort",
)


@dataclass(frozen=True)
class SelfCardTimeLine:
    label: str
    text: str
    source: str
    source_ref: str
    source_sha256: str
    reason: str

    def receipt(self) -> dict[str, object]:
        return {
            "time_line_present": True,
            "time_line_reason": self.reason,
            "time_line_source": self.source,
            "time_line_source_ref": self.source_ref,
            "time_line_chars": len(self.text),
            "time_line_sha256": self.source_sha256,
        }


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _clean_number(value: object) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _reason(ctx: Mapping[str, object]) -> str | None:
    current = _clean_number(ctx.get("rhythm_current_gap_s"))
    if current is None:
        return None
    pct = _clean_number(ctx.get("rhythm_current_gap_percentile_all_time"))
    if pct is not None:
        if pct >= SELF_CARD_TIME_HIGH_PERCENTILE:
            return "percentile_high"
        if pct <= SELF_CARD_TIME_LOW_PERCENTILE:
            return "percentile_low"
        return None
    if current >= SELF_CARD_TIME_COLD_START_MIN_S:
        return "cold_start_elapsed_floor"
    return None


def rhythm_time_line_provider(
    *,
    db_path: Path | str | None = None,
    now: str | datetime | None = None,
) -> dict | None:
    from core.evolution.subjective_duration import SubjectiveDuration, _default_db_path

    path = Path(db_path) if db_path is not None else _default_db_path()
    if not path.exists():
        return None
    handle = SubjectiveDuration(db_path=path)
    return handle.rhythm_context(now=now)


def _human(seconds: object) -> str:
    from core.evolution.subjective_duration import humanize_elapsed

    return humanize_elapsed(_clean_number(seconds) or 0.0)


def _render(ctx: Mapping[str, object], reason: str) -> str:
    current = f"~{_human(ctx.get('rhythm_current_gap_s'))} since owner contact"
    recent = ctx.get("rhythm_recent_gap_median_s")
    all_time = ctx.get("rhythm_all_time_gap_median_s")
    pct = _clean_number(ctx.get("rhythm_current_gap_percentile_all_time"))
    n = int(_clean_number(ctx.get("rhythm_all_time_sample_count")) or 0)
    gap_word = "gap" if n == 1 else "gaps"
    parts = [current]
    if recent is not None and all_time is not None:
        parts.append(f"recent usual ~{_human(recent)}; all-time usual ~{_human(all_time)}")
    if pct is not None:
        relation = "above" if reason == "percentile_high" else "below"
        parts.append(f"{relation} ~{round(pct)}% of recorded gaps ({n} {gap_word})")
    else:
        parts.append(f"still learning the usual rhythm ({n} {gap_word} so far)")
    return ". ".join(parts) + "."


def build_self_card_time_line(
    context_provider: Callable[[], Mapping[str, object] | None] = rhythm_time_line_provider,
) -> SelfCardTimeLine | None:
    try:
        ctx = context_provider()
    except Exception:
        return None
    if not ctx:
        return None
    reason = _reason(ctx)
    if reason is None:
        return None
    text = _render(ctx, reason)
    lowered = text.lower()
    if any(word in lowered for word in _FORBIDDEN_FEELING_WORDS):
        return None
    digest_basis = "|".join(
        str(ctx.get(key, ""))
        for key in (
            "rhythm_current_gap_s",
            "rhythm_recent_gap_median_s",
            "rhythm_all_time_gap_median_s",
            "rhythm_all_time_sample_count",
            "rhythm_current_gap_percentile_all_time",
            reason,
        )
    )
    return SelfCardTimeLine(
        label="Time since contact",
        text=text,
        source=_SOURCE,
        source_ref=reason,
        source_sha256=_sha256(digest_basis),
        reason=reason,
    )
```

- [ ] **Step 4: Run adapter tests.**

Run:

```bash
.venv/bin/python -m unittest tests.test_self_card_time -v
```

Expected: all tests pass.

- [ ] **Step 5: Lint and commit.**

Run:

```bash
.venv/bin/ruff check core/routing/self_card_time.py tests/test_self_card_time.py
git add core/routing/self_card_time.py tests/test_self_card_time.py
git commit -m "feat(nervous-system): add factual self-card time-line adapter" -m "## Predicted effect" -m "No live prompt changes yet. The new adapter can render a factual time-since-contact self-card line from rhythm_context() when the gap is outside the temporary anti-spam surfacing policy, and returns None for ordinary short gaps or reader failures."
```

## Task 2: Self-Card Candidate and Receipt Fields

**Files:**
- Modify: `core/routing/self_card.py`
- Modify: `tests/test_self_card_v0.py`

- [ ] **Step 1: Write failing self-card tests.**

Append to `SelfCardAssemblerTests` in `tests/test_self_card_v0.py`:

```python
    def test_time_line_candidate_stays_out_of_text_until_applied(self):
        from core.routing.self_card import assemble_self_card
        from core.routing.self_card_time import SelfCardTimeLine

        time_line = SelfCardTimeLine(
            label="Time since contact",
            text="~8h since owner contact. above ~91% of recorded gaps (226 gaps).",
            source="subjective_duration.rhythm_context",
            source_ref="percentile_high",
            source_sha256="abc123",
            reason="percentile_high",
        )

        card = assemble_self_card(
            base_text=BASE_FIXTURE,
            local_text=LOCAL_FIXTURE,
            body_state_provider=_body_line,
            time_line_candidate=time_line,
            time_line_applied=False,
        )

        self.assertNotIn("Time since contact", card.text)
        receipt = card.receipt()
        self.assertTrue(receipt["time_line_present"])
        self.assertFalse(receipt["time_line_applied"])
        self.assertEqual(receipt["time_line_reason"], "percentile_high")
        self.assertNotIn("8h", str(receipt))

    def test_time_line_enabled_renders_factual_line(self):
        from core.routing.self_card import assemble_self_card
        from core.routing.self_card_time import SelfCardTimeLine

        time_line = SelfCardTimeLine(
            label="Time since contact",
            text="~8h since owner contact. above ~91% of recorded gaps (226 gaps).",
            source="subjective_duration.rhythm_context",
            source_ref="percentile_high",
            source_sha256="abc123",
            reason="percentile_high",
        )

        card = assemble_self_card(
            base_text=BASE_FIXTURE,
            local_text=LOCAL_FIXTURE,
            body_state_provider=_body_line,
            time_line_candidate=time_line,
            time_line_applied=True,
        )

        self.assertIn("Time since contact", card.text)
        self.assertIn("~8h since owner contact", card.text)
        self.assertTrue(card.receipt()["time_line_applied"])
```

- [ ] **Step 2: Run tests and verify RED.**

Run:

```bash
.venv/bin/python -m unittest tests.test_self_card_v0 -v
```

Expected: FAIL because `assemble_self_card()` does not accept `time_line_candidate` / `time_line_applied`.

- [ ] **Step 3: Implement self-card support.**

Modify `core/routing/self_card.py`:

```python
@dataclass(frozen=True)
class SelfCard:
    lines: tuple[SelfCardLine, ...]
    time_line_candidate: object | None = None
    time_line_applied: bool = False

    @property
    def text(self) -> str:
        render_lines = list(self.lines)
        if self.time_line_candidate is not None and self.time_line_applied:
            render_lines.append(
                SelfCardLine(
                    label=self.time_line_candidate.label,
                    text=self.time_line_candidate.text,
                    source=self.time_line_candidate.source,
                    source_ref=self.time_line_candidate.source_ref,
                    source_sha256=self.time_line_candidate.source_sha256,
                )
            )
        rendered = "\n".join(line.render() for line in render_lines)
        return (
            "SELF CARD (deterministic mirror; facts, not style)\n"
            f"{rendered}"
        )
```

In `receipt()`, add after `style_directive_hits`:

```python
            "time_line_present": bool(self.time_line_candidate is not None),
            "time_line_applied": bool(self.time_line_candidate is not None and self.time_line_applied),
            "time_line_reason": (
                getattr(self.time_line_candidate, "reason", "none")
                if self.time_line_candidate is not None
                else "none"
            ),
            "time_line_source": (
                getattr(self.time_line_candidate, "source", "none")
                if self.time_line_candidate is not None
                else "none"
            ),
            "time_line_chars": (
                len(getattr(self.time_line_candidate, "text", ""))
                if self.time_line_candidate is not None
                else 0
            ),
            "time_line_sha256": (
                getattr(self.time_line_candidate, "source_sha256", "")
                if self.time_line_candidate is not None
                else ""
            ),
```

Update signatures:

```python
def assemble_self_card(
    *,
    base_text: str,
    local_text: str,
    body_state_provider: BodyStateProvider | None = None,
    local_max_chars: int = 520,
    local_max_items: int = 3,
    local_recency_days: int | None = 45,
    now: datetime | None = None,
    time_line_candidate: object | None = None,
    time_line_applied: bool = False,
) -> SelfCard:
    ...
    return SelfCard(
        lines=tuple(lines),
        time_line_candidate=time_line_candidate,
        time_line_applied=time_line_applied,
    )
```

And pass the two new kwargs through `assemble_self_card_from_paths(...)`.

- [ ] **Step 4: Run tests.**

Run:

```bash
.venv/bin/python -m unittest tests.test_self_card_v0 tests.test_self_card_time -v
```

Expected: all tests pass.

- [ ] **Step 5: Lint and commit.**

Run:

```bash
.venv/bin/ruff check core/routing/self_card.py tests/test_self_card_v0.py
git add core/routing/self_card.py tests/test_self_card_v0.py
git commit -m "feat(nervous-system): let self-card carry a shadowed time line" -m "## Predicted effect" -m "No live prompt changes while MAEZ_SELF_CARD_TIME_ENABLED is off. When a time-line candidate is supplied in shadow mode, receipts expose content-light source/reason/count fields while card text remains unchanged."
```

## Task 3: Focused Flags and Shadow Receipt

**Files:**
- Modify: `core/routing/focused_cognition.py`
- Modify: `tests/test_lean_conversation_path.py`

- [ ] **Step 1: Write failing focused tests.**

Append to `LeanConversationPathTests` in `tests/test_lean_conversation_path.py`:

```python
    def test_self_card_time_shadow_logs_without_applying_line(self):
        import core.routing.focused_cognition as fc
        from core.routing.self_card_time import SelfCardTimeLine
        from core.routing.focused_cognition import focused_synthesize

        os.environ["MAEZ_SELF_CARD_TIME_SHADOW"] = "1"
        line = SelfCardTimeLine(
            label="Time since contact",
            text="~8h since owner contact. above ~91% of recorded gaps (226 gaps).",
            source="subjective_duration.rhythm_context",
            source_ref="percentile_high",
            source_sha256="abc123",
            reason="percentile_high",
        )
        captured = {}

        def chat_fn(**kwargs):
            captured["system"] = kwargs["messages"][0]["content"]
            return _response("I am here.")

        with mock.patch("core.routing.self_card_time.build_self_card_time_line", return_value=line), \
             self.assertLogs("maez.focused", level="INFO") as logs:
            focused_synthesize(
                _working_set(),
                surface="telegram",
                chat_fn=chat_fn,
                model="m",
                legacy_prompt_chars=3200,
            )

        joined = "\n".join(logs.output)
        self.assertIn("self_card_time_shadow", joined)
        self.assertIn("time_line_present=True", joined)
        self.assertIn("time_line_applied=False", joined)
        self.assertIn("time_line_reason=percentile_high", joined)
        self.assertNotIn("8h", joined)
        self.assertNotIn("Time since contact", captured["system"])

    def test_self_card_time_enabled_adds_line_to_lean_prompt(self):
        from core.routing.self_card_time import SelfCardTimeLine
        from core.routing.focused_cognition import focused_synthesize

        os.environ["MAEZ_LEAN_CONVERSATION_ENABLED"] = "1"
        os.environ["MAEZ_SELF_CARD_ENABLED"] = "1"
        os.environ["MAEZ_SELF_CARD_TIME_ENABLED"] = "1"
        line = SelfCardTimeLine(
            label="Time since contact",
            text="~8h since owner contact. above ~91% of recorded gaps (226 gaps).",
            source="subjective_duration.rhythm_context",
            source_ref="percentile_high",
            source_sha256="abc123",
            reason="percentile_high",
        )
        captured = {}

        def chat_fn(**kwargs):
            captured["system"] = kwargs["messages"][0]["content"]
            return _response("I am here.")

        with mock.patch("core.routing.self_card_time.build_self_card_time_line", return_value=line):
            focused_synthesize(
                _working_set(),
                surface="telegram",
                chat_fn=chat_fn,
                model="m",
                legacy_prompt_chars=3200,
            )

        self.assertIn("SELF CARD", captured["system"])
        self.assertIn("Time since contact", captured["system"])
        self.assertIn("~8h since owner contact", captured["system"])
        self.assertNotIn("missed", captured["system"].lower())

    def test_time_flags_off_do_not_read_time_line(self):
        from core.routing.focused_cognition import focused_synthesize

        with mock.patch("core.routing.self_card_time.build_self_card_time_line") as build:
            focused_synthesize(
                _working_set(),
                surface="telegram",
                chat_fn=lambda **_k: _response("I am here."),
                model="m",
                legacy_prompt_chars=3200,
            )

        build.assert_not_called()
```

- [ ] **Step 2: Run tests and verify RED.**

Run:

```bash
.venv/bin/python -m unittest tests.test_lean_conversation_path -v
```

Expected: FAIL because `MAEZ_SELF_CARD_TIME_SHADOW` / `MAEZ_SELF_CARD_TIME_ENABLED` are not implemented and no receipt is emitted.

- [ ] **Step 3: Implement focused flags and receipt.**

In `core/routing/focused_cognition.py`, add helpers near `_self_card_enabled`:

```python
def _self_card_time_shadow_enabled(env=os.environ) -> bool:
    return (env.get("MAEZ_SELF_CARD_TIME_SHADOW", "") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _self_card_time_enabled(env=os.environ) -> bool:
    return (env.get("MAEZ_SELF_CARD_TIME_ENABLED", "") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
```

Update `_safe_self_card`:

```python
def _safe_self_card(*, time_line_candidate=None, time_line_applied: bool = False):
    try:
        from core.routing.self_card import assemble_self_card_from_paths

        return assemble_self_card_from_paths(
            time_line_candidate=time_line_candidate,
            time_line_applied=time_line_applied,
        )
    except Exception:
        logger.warning(
            "self_card_assembly_failed fallback=legacy_voice_card",
            exc_info=True,
        )
        return None
```

Add a focused receipt helper:

```python
def _emit_self_card_time_receipt(event: str, card, *, applied: bool, surface: str, turn_kind: str | None) -> None:
    receipt = card.receipt()
    logger.info(
        "%s status=ok applied=%s time_line_present=%s time_line_applied=%s "
        "time_line_reason=%s time_line_source=%s time_line_chars=%d "
        "time_line_sha256=%s surface=%s turn_kind=%s",
        event,
        bool(applied),
        bool(receipt.get("time_line_present", False)),
        bool(receipt.get("time_line_applied", False)),
        str(receipt.get("time_line_reason", "none")),
        str(receipt.get("time_line_source", "none")),
        int(receipt.get("time_line_chars", 0) or 0),
        str(receipt.get("time_line_sha256", "")),
        surface,
        turn_kind,
    )
```

In `focused_synthesize`, compute:

```python
    self_card_time_shadow = _self_card_time_shadow_enabled()
    self_card_time_enabled = _self_card_time_enabled()
    time_line_candidate = None
    if self_card_time_shadow or self_card_time_enabled:
        try:
            from core.routing.self_card_time import build_self_card_time_line

            time_line_candidate = build_self_card_time_line()
        except Exception:
            logger.debug("self_card_time_line_skipped", exc_info=True)
            time_line_candidate = None
```

Extend the existing self-card assembly condition:

```python
    if self_card_shadow or self_card_enabled or self_card_time_shadow or self_card_time_enabled:
        card = _safe_self_card(
            time_line_candidate=time_line_candidate,
            time_line_applied=self_card_time_enabled,
        )
        if card is not None:
            if self_card_shadow:
                _emit_self_card_receipt(...)
            if self_card_time_shadow:
                _emit_self_card_time_receipt(
                    "self_card_time_shadow",
                    card,
                    applied=self_card_time_enabled,
                    surface=surface,
                    turn_kind=turn_kind,
                )
            if self_card_enabled:
                voice_card_text = card.text
```

Keep the current rule: `MAEZ_SELF_CARD_TIME_ENABLED=1` changes the prompt only when `MAEZ_SELF_CARD_ENABLED=1` also applies the self-card. Time-enabled without self-card-enabled may assemble/log but must not replace `_VOICE_CARD_TEXT`.

- [ ] **Step 4: Run focused tests.**

Run:

```bash
.venv/bin/python -m unittest tests.test_lean_conversation_path tests.test_self_card_v0 tests.test_self_card_time -v
```

Expected: all tests pass.

- [ ] **Step 5: Lint and commit.**

Run:

```bash
.venv/bin/ruff check core/routing/focused_cognition.py tests/test_lean_conversation_path.py
git add core/routing/focused_cognition.py tests/test_lean_conversation_path.py
git commit -m "feat(nervous-system): shadow and apply self-card time line" -m "## Predicted effect" -m "With MAEZ_SELF_CARD_TIME_SHADOW=1, focused turns log a content-light self_card_time_shadow receipt without changing the prompt. With MAEZ_SELF_CARD_ENABLED=1 and MAEZ_SELF_CARD_TIME_ENABLED=1, a factual time-since-contact line appears in the self-card when rhythm_context() deems the gap surfaceable."
```

## Task 4: Whole-Slice Verification and Handoff

**Files:**
- Create: `docs/handoffs/2026-06-23-nervous-system-v0-slice-a-handoff.md`

- [ ] **Step 1: Run targeted regression.**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest \
  tests.test_self_card_time \
  tests.test_self_card_v0 \
  tests.test_lean_conversation_path \
  tests.test_focused_cognition \
  tests.test_focused_cognition_citation_render \
  tests.test_rhythm_context \
  tests.test_time_sense_context
```

Expected: all tests pass.

- [ ] **Step 2: Run static checks.**

Run:

```bash
.venv/bin/ruff check \
  core/routing/self_card_time.py \
  core/routing/self_card.py \
  core/routing/focused_cognition.py \
  tests/test_self_card_time.py \
  tests/test_self_card_v0.py \
  tests/test_lean_conversation_path.py
git diff --check
```

Expected: ruff `All checks passed!`; `git diff --check` no output.

- [ ] **Step 3: Write handoff.**

Create `docs/handoffs/2026-06-23-nervous-system-v0-slice-a-handoff.md`:

```markdown
# Nervous-System v0 Slice A Handoff

Branch: nervous-system-v0-slice-a
Status: STOPPED AT REVIEW GATE — not merged, not restarted, no flags flipped.

## What Landed

- `core/routing/self_card_time.py`: factual rhythm/time self-card line adapter.
- `core/routing/self_card.py`: optional time-line candidate + content-light receipt fields.
- `core/routing/focused_cognition.py`: `MAEZ_SELF_CARD_TIME_SHADOW` and `MAEZ_SELF_CARD_TIME_ENABLED`.

## Covenant Anchors

1. Senses yes / interpretation no: line renders raw rhythm facts only.
2. Uses `rhythm_context()`, not `felt_phrase` / `felt_value`.
3. No owner-reaction reward or owner approval signal.
4. Shadow-first: `self_card_time_shadow` receipt changes no prompt.
5. Default-off byte-identical.
6. Read-only: sample/event counts unchanged in test.
7. Thresholds named temporary anti-spam scaffolding.

## Verification

- Targeted tests:
- Ruff:
- Diff check:

## Owner Breath After Review PASS

1. Merge.
2. Restart `maez` only if the running daemon should see new focused code.
3. Set `MAEZ_SELF_CARD_TIME_SHADOW=1` with `MAEZ_SELF_CARD_SHADOW=1`.
4. Witness `self_card_time_shadow`:
   - `time_line_present=True` only when rhythm facts are surfaceable.
   - `time_line_reason=percentile_high|percentile_low|cold_start_elapsed_floor`.
   - no time text leaks into logs.
5. Then set `MAEZ_SELF_CARD_TIME_ENABLED=1` while `MAEZ_SELF_CARD_ENABLED=1`.
6. Say "how are you?" after a real gap and confirm the self-card carries time as fact, not feeling.
```

- [ ] **Step 4: Commit handoff.**

Run:

```bash
git add docs/handoffs/2026-06-23-nervous-system-v0-slice-a-handoff.md
git commit -m "docs(nervous-system): hand off felt-time self-card slice"
```

## Execution Notes

- Build in an isolated branch/worktree named `nervous-system-v0-slice-a`.
- Do not merge, restart, or flip flags during implementation.
- Review should pay special attention to:
  - no use of `felt_phrase` in voice;
  - no feeling words in the rendered line;
  - no time reader call with all time flags off;
  - no sample/event writes in the reader test;
  - `MAEZ_SELF_CARD_TIME_ENABLED` cannot affect prompts unless the self-card itself is enabled.
