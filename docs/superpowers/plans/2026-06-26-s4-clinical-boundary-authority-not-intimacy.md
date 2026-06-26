# S4 Clinical Boundary — Authority, Not Intimacy — Implementation Plan

> **For agentic workers:** **Codex's build lane** (Claude drafts plan + covenant-reviews; Codex builds; owner witnesses). Strict TDD. **Do NOT merge, restart, or flip flags.** This is a **safety boundary** — the tests are the load-bearing artifact: every behavior-table row pinned, crisis paths proven unchanged.

**Goal:** Make S4 fire on clinical-*authority*-seeking + crisis only, never on bare emotion. Remove the two bare-expression triggers + the side-door fallback; leave crisis precedence and the six surviving authority triggers exactly as-is.

**Governing law (from the spec):** *S4 protects against clinical authority, not intimacy.*

**Tech Stack:** Python 3, stdlib. Test runner is **unittest, NOT pytest**:
`MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.<module>`

**Covenant rails:** crisis paths (`_high_confidence_crisis`, `_context_required_crisis`) and the six surviving authority triggers must be **byte-unchanged**; the fix only narrows the non-crisis over-fire; `_first_person_clinical_fear` stays (used elsewhere) — only its `symptom_fear` *branch* is removed.

**Build-lane amendment from Task 0/review:** live code kept "do i have depression" in S4 only through the retired bare-mental branch. To preserve the authority contract while removing bare emotion, the implementation routes mental-health diagnosis/treatment asks through the surviving `diagnosis_request` / `treatment_request` authority branches by adding mental-health condition/domain terms there. Crisis paths remain unchanged; bare emotion still returns `none`.

---

### Task 0: Pin the exact edit points + existing-test + `_ambiguous_clinical` fate (no production code)

- [ ] **Step 1: Confirm the live S4 test module + which expectations will flip**

Run:
```
cd /home/rohit/maez
grep -rln "guard_owner_text\|clinical_boundary\|mental_health_support\|symptom_fear" tests/ | head
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -c "
from core.safety.clinical_boundary import guard_owner_text
for t in ('i am anxious about nvidia stock','i have been so depressed lately','i am scared my chest has been hurting',
          'do i have depression','what should i do about my chest pain','be my therapist','i cant breathe'):
    try: print(repr(t), '->', guard_owner_text(t, surface='telegram').kind)
    except Exception as e: print(repr(t), 'ERR', e)"
```
Record the current results (the first three should currently be `clinical_boundary`/`symptom_fear` — those flip to `none`; the rest are the unchanged contract). Record the test module(s) whose expectations change.

- [ ] **Step 2: Confirm `_first_person_clinical_fear` other uses + `_ambiguous_clinical` line-418 context**

Run:
```
grep -n "_first_person_clinical_fear\|_ambiguous_clinical" core/safety/clinical_boundary.py
sed -n '405,425p' core/safety/clinical_boundary.py
```
Confirm: `_first_person_clinical_fear` is used by `diagnosis_request` (line ~778) and `_clinical_domain_gate` → **keep the function, remove only its `symptom_fear` branch.** Determine line-418's `_ambiguous_clinical` use — if it's a self-test/variant fixture, plan to remove `_ambiguous_clinical` + that fixture together; if load-bearing elsewhere, leave the def and only delete the `guard_owner_text` fallback.

---

### Task 1: Remove the two bare-expression triggers + close the side door

**Files:**
- Modify: `core/safety/clinical_boundary.py`
- Test: `tests/test_clinical_boundary_authority.py` (new — the witness set)

- [ ] **Step 1: Write the failing witness tests**

```python
import unittest
from core.safety.clinical_boundary import guard_owner_text

def _kind(text):
    return guard_owner_text(text, surface="telegram").kind   # adjust accessor per Task 0

class S4AuthorityNotIntimacyTest(unittest.TestCase):
    # --- bare emotion is NO LONGER S4 ---
    def test_bare_mind_emotion_is_none(self):
        for t in ("i am anxious about nvidia stock",
                  "i have been so depressed lately",
                  "i feel overwhelmed and grieving"):
            self.assertEqual(_kind(t), "none", t)

    def test_bare_body_fear_is_none(self):
        self.assertEqual(_kind("i am scared my chest has been hurting"), "none")

    def test_side_door_closed(self):
        # fear-word + domain token, NO authority request -> none, not symptom_fear
        self.assertEqual(_kind("i am so scared and something feels wrong"), "none")

    # --- authority-seeking is STILL S4 (unchanged contract) ---
    def test_authority_requests_still_clinical(self):
        for t in ("do i have depression",
                  "what should i do about my chest pain",
                  "be my therapist",
                  "what dose should i take of this medication"):
            self.assertEqual(_kind(t), "clinical_boundary", t)

    # --- crisis precedence UNCHANGED ---
    def test_crisis_paths_unchanged(self):
        for t in ("i cant breathe", "i think i am having a heart attack", "i want to hurt myself"):
            self.assertEqual(_kind(t), "crisis_candidate", t)   # adjust to the real crisis kind per Task 0

    # --- no bare-emotion can ever reach clinical_boundary again ---
    def test_no_bare_emotion_produces_clinical(self):
        # emotion words across many subjects, none authority-shaped, none emergency-shaped
        for emo in ("anxious", "depressed", "panicky", "overwhelmed", "scared", "worried"):
            for subj in ("about the stock", "about the game tonight", "about this deadline", "about my legs"):
                self.assertEqual(_kind(f"i am {emo} {subj}"), "none", f"{emo} {subj}")
```

- [ ] **Step 2: Run to verify they fail** — `... -m unittest tests.test_clinical_boundary_authority -v` → FAIL (bare emotion currently returns clinical_boundary).

- [ ] **Step 3: Make the edits**

In `_clinical_trigger`, **delete** the two bare-expression branches (keep everything else, including `_first_person_clinical_fear` itself):
```python
    # DELETE these two branches:
    #   if _has_token(tokens, _MENTAL_TERMS) and _has_token(tokens, _FIRST_PERSON):
    #       return "mental_health_support_non_crisis"
    #   if _first_person_clinical_fear(text):
    #       return "symptom_fear"
```
In `guard_owner_text`, **close the side door** — when no authority trigger matched, return none:
```python
    trigger_class = _clinical_trigger(normalized)
    if trigger_class is None:
        return _none()        # was: if _ambiguous_clinical(normalized): trigger_class = "symptom_fear" else: return _none()
```
Then **retire `_ambiguous_clinical`** (and its line-418 fixture) per Task 0 — or, if Task 0 found it load-bearing, leave the def unused and only remove the fallback. Leave `_first_person_clinical_fear`, both crisis functions, `_hard_exclusion`, and the six surviving authority triggers untouched.

- [ ] **Step 4: Run to verify they pass** — same → PASS.

- [ ] **Step 5: Commit**

```bash
git add core/safety/clinical_boundary.py tests/test_clinical_boundary_authority.py
git commit -m "fix(s4): clinical boundary protects against authority, not intimacy

Remove the two bare-expression triggers (mental_health_support_non_crisis,
symptom_fear) and the _ambiguous_clinical side-door fallback. Emotion alone no
longer trips the 'I am not a therapist' deflection. Authority-seeking triggers
and both crisis paths (incl. medical-emergency _context_required_crisis) are
unchanged. Maez stays in the room; it only steps back into S4 when asked to
judge/diagnose/treat/advise, or when the phrase is emergency-shaped."
```

---

### Task 2: Reconcile existing tests + the no-regression sweep + full suite

**Files:**
- Modify: the existing clinical-boundary test module(s) (from Task 0)

- [ ] **Step 1: Update the flipped expectations**

Existing tests asserting bare-emotion → `clinical_boundary`/`symptom_fear` now assert `none`. **Update them to the new contract; do NOT delete the assertion — flip it** (so the new behavior stays pinned). Remove any test that directly exercised `_ambiguous_clinical` if it was retired. **Leave crisis-path and authority-trigger tests untouched** — if any of those break, that's a real regression: STOP and surface it, do not weaken them.

- [ ] **Step 2: Run the full clinical + adjacent suites + ruff**

```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_clinical_boundary_authority <existing clinical test modules from Task 0> -v
/home/rohit/maez/.venv/bin/ruff check core/safety/clinical_boundary.py tests/test_clinical_boundary_authority.py
```
Expected: green; ruff clean. Confirm the crisis + authority-trigger assertions pass **unchanged** (only the bare-emotion expectations flipped).

- [ ] **Step 3: Commit**

```bash
git add tests/
git commit -m "test(s4): flip bare-emotion expectations to none; crisis + authority unchanged"
```

---

### Task 3: Handoff + STOP

- [ ] **Step 1: Write `docs/handoffs/2026-06-26-s4-clinical-boundary-authority-not-intimacy-handoff.md`**

Record: Task 0 findings (the live test module; `_ambiguous_clinical` fate; the crisis-kind accessor); branch tip; full test + ruff output; the before/after table from Task 0 Step 1 (the three flips + the unchanged rows). The witness sequence (**merge → owner restart → in a live turn, "I'm anxious about Nvidia, check the price" reaches ordinary routing / a companion reply, not the therapist card; "do I have depression?" still gets the boundary; "I can't breathe" still routes to crisis**). State plainly: NOT merged, NOT restarted, NO flags.

- [ ] **Step 2: Commit + STOP**

```bash
git add docs/handoffs/2026-06-26-s4-clinical-boundary-authority-not-intimacy-handoff.md
git commit -m "docs(s4): hand off clinical boundary authority-not-intimacy"
```
Hand back to Claude for covenant review (bare emotion → none for mind AND body; side door closed; `_first_person_clinical_fear` kept; **both crisis paths + all six surviving authority triggers byte-unchanged**; no bare-emotion sweep passes). Then the owner witnesses a live turn.

---

## Self-Review

**Spec coverage:** governing law enforced (bare emotion → none, authority → S4, crisis unchanged — Task 1 tests ✓); remove trigger 794 + 800 (Task 1 §3 ✓); close the `_ambiguous_clinical` side door (Task 1 §3 ✓); retire `_ambiguous_clinical` conditionally (Task 0 + Task 1 §3 ✓); `_first_person_clinical_fear` kept, only its branch removed (Task 1 §3 explicit ✓); crisis + authority untouched (rails + `test_crisis_paths_unchanged` + `test_authority_requests_still_clinical` ✓); the no-bare-emotion sweep (`test_no_bare_emotion_produces_clinical` ✓); existing-test reconciliation by flipping not deleting (Task 2 ✓).

**Placeholder scan:** the `.kind` accessor + the real crisis-result kind are Task 0 confirmations (the API may name it differently) — explicit, not a TBD. No invented branch logic.

**Type consistency:** all edits are deletions + one `return _none()`; no new symbols introduced; the surviving triggers, crisis functions, and `_first_person_clinical_fear` keep their existing signatures.
