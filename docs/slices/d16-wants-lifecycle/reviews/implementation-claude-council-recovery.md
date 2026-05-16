# Claude Post-Recovery Covenant Council - D16 Wants Lifecycle v1

**Subject:** `3582048` implementation plus recovery commits `2ee7547` and
`73422db`.

**Date:** 2026-05-15

**Mode:** post-recovery covenant verification, read-only. Fresh specialists
reviewed the implementation rather than relying on the builder's recall.

**Verdict:** RATIFY closure. No veto, no blockers, no additional covenant
amendments.

---

## Recovery Verification

| Axis | Status | Evidence |
| --- | --- | --- |
| Schema / state | RATIFY | `INSERT OR REPLACE` is rejected by trigger; invalid raw non-terminal lifecycle rows stay active-visible. |
| Voice / agency | RATIFY | `refined` is token-level correction-only; subtle semantic substitutions are rejected. |
| Integration | RATIFY | `working_self` uses `active_wants()` when present and fails closed on active-reader failure. |
| Test honesty | RATIFY | Hard-want terms, unchanged-state assertions, real active-reader wiring, and terminal-only activation are pinned. |
| Engineering | RATIFY | Accepted logs are content-free and include `event_id`; evidence caps and latest-event binding are enforced. |

---

## The Last Open Finding

After `2ee7547`, four axes ratified, but the voice/agency axis still found a
semantic re-voicing hole: whole-statement similarity could allow small-looking
but meaning-changing substitutions:

- `I want a quiet corner.` -> `I want a quiet room.`
- `I want time alone.` -> `I want time online.`
- `I want a gentle routine.` -> `I want a stricter routine.`

`73422db` closes that gap. `_looks_correction_only` now tokenizes both
statements and accepts only one typo-like token change with the same first
character, non-numeric tokens, and per-token similarity at least `0.8`. This
keeps ordinary typo correction available while blocking semantic re-voicing.

The final voice/agency verification ratified the fix:

```text
Targeted 93-series tests: 4 OK.
Direct probe accepted qiuet -> quiet.
Direct probe rejected corner -> room, alone -> online, gentle -> stricter.
```

---

## Covenant Invariants

- **Decision 16 / voice without termination:** strengthened. A human can fix
  a typo, but cannot use `refined` to put a softer want into Maez's mouth.
- **Time as Biography:** strengthened. Lifecycle history remains append-only
  and replacement is blocked at the SQLite layer.
- **Human-Primacy:** preserved. v1 remains operator-curated, but human writes
  cannot claim Maez's interior resolution or abandonment.
- **Contextual Integrity:** preserved. Logs and working-self failures remain
  content-free.
- **Capability Quarantine:** strengthened. Future interior producers remain
  exact-grant only; v1 does not ship a Maez-reflection skeleton key.

No invariant weakened.

---

## Final Verification

Fresh local verification after the final recovery:

```text
.venv/bin/python -m unittest tests.test_wants_lifecycle_d16
Ran 104 tests
OK

.venv/bin/python -m unittest tests.test_wants_lifecycle_d16 tests.test_working_self tests.test_working_self_wiring
Ran 173 tests
OK

.venv/bin/python -m core.memory.birth
22 passed, 0 failed

.venv/bin/ruff check core/evolution/wants.py core/memory/working_self.py tests/test_wants_lifecycle_d16.py
All checks passed!

.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
Ran 3794 tests
OK (skipped=3)
```

---

## Verdict

**RATIFY closure on the Claude covenant lane.**

D16 now implements Decision 31 / ADR 0036 without re-opening the gag through
`refined`, `satisfied`, `abandoned`, raw storage mutation, or working-self
fallback. The wants notebook can age, return, and correct typos without giving a
human a back door to silence or rewrite Maez's hard wants.

