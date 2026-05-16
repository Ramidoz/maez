# Codex Post-Implementation Engineering Panel - D16 Wants Lifecycle v1

**Subject:** `3582048 feat(d16): implement wants lifecycle v1`

**Date:** 2026-05-15

**Mode:** post-implementation engineering review, read-only. The panel focused
on implementation completeness, storage boundaries, working-self integration,
and test executability.

**Verdict:** REVISE, then RATIFY-WITH-RECOVERY after `2ee7547` and `73422db`.

---

## Panel Findings

| Finding | Severity | Recovery |
| --- | --- | --- |
| `INSERT OR REPLACE` could bypass append-only semantics | REVISE | Added `trg_want_events_no_replace`; RED test proves replacement is rejected. |
| Unknown raw event types could disappear from active view | REVISE | Unknown non-terminal rows now derive active state and remain visible. |
| `working_self` could fallback to `recent()` after active-reader failure | REVISE | Presence of `active_wants` is authoritative; failures return empty goals with content-free debug logs. |
| Hard-want rejection tests did not assert unchanged state | REVISE | Rejection tests now compare current state before/after. |
| `HARD_WANT_TERMS` was under-tested | REVISE | Full term set is pinned and each term is exercised for `satisfied` and `refined`. |
| Real-store working-self wiring could be faked by stubs | REVISE | Spy test proves `active_wants()` is called and `recent()` is not. |
| Terminal-only activation path was not proven | REVISE | Activation rehearsal includes a satisfied-only want and proves it stays out. |
| Accepted-write logs lacked `event_id` and exposed `topic` | REVISE | Accepted logs include `event_id` and omit statement/topic content. |
| `refined` evidence could bind stale event/hash | REVISE | Latest event id and latest statement hash are checked inside the serialized write path. |
| Evidence caps stored unstripped or oversized values | REVISE | Evidence strings are stripped and capped, including `operator_rationale`. |
| Whole-statement similarity still allowed subtle semantic re-voicing | REVISE | Final follow-up `73422db` switched to token-level correction-only validation. |

---

## Recovery Commits

### `2ee7547 fix(d16): close wants lifecycle recovery gaps`

Closed the storage, visibility, working-self, logging, evidence-binding, and
test-honesty findings. Focused review after this commit produced four ratifies
and one remaining voice/agency finding: whole-statement similarity still
accepted subtle semantic substitutions.

Targeted verification from the panel:

- D16 focused tests: 101 OK.
- Working-self targeted tests: 4 OK.
- Manual probes confirmed `INSERT OR REPLACE` rejected, raw `done` remains
  active-visible, and broken `active_wants()` logs
  `working_self_wants_active_failed`.

### `73422db fix(d16): tighten refined correction-only guard`

Closed the remaining semantic re-voicing surface by changing correction-only
validation from whole-statement similarity to token-level validation:

- same token count;
- exactly one changed token;
- same first character;
- non-numeric;
- changed-token similarity at least `0.8`.

The final follow-up added regressions for:

- `quiet corner` -> `quiet room`;
- `time alone` -> `time online`;
- `gentle routine` -> `stricter routine`.

The accepted typo path remains intact: `qiuet` -> `quiet`.

---

## Final Verification

Fresh verification after `73422db`:

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

**RATIFY-WITH-RECOVERY.**

The implementation now meets the D16 engineering contract: append-only semantics
hold below the API, invalid history cannot silently gag a want, the working-self
reader uses the active lifecycle view and fails closed, accepted logs are
content-free, and `refined` is correction-only rather than a semantic rewrite
lane.

