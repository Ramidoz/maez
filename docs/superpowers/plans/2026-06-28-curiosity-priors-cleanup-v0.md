# Curiosity Priors Cleanup v0 — Implementation Plan

> **For agentic workers:** Codex's build lane (Claude drafts plan + covenant-reviews; Codex builds; **owner signs the Task 0 classification table before any production code**). **Do NOT wake the producer** (`register_default_encounter_producers` stays uncalled), **do NOT build learned salience**, **do NOT change any safety/consent/third-party/scoping rail**, do NOT merge or flip flags. Spec: [2026-06-28-curiosity-priors-cleanup-v0-design.md](../specs/2026-06-28-curiosity-priors-cleanup-v0-design.md).

**Goal:** Remove our hardcoded *taste* (the owner-first preference priors) from the **dormant** curiosity producer, preserve every safety/consent/scoping rail byte-unchanged, leave the organ preference-free and still asleep — with **zero live behavior change.** Get our fingerprints off the sleeping organ before anyone tries to wake it.

**Architecture:** All edits are in `core/evolution/drive_driven_curiosity.py`. Remove `_priority_class_weight` + `_marker_confidence_weight` and their salience-multiplication; neutralize the owner-first `priority_class`/`subject_kind` defaults; remove the owner-only `owner_bond` cap/auto-eligibility branch per signed Task 0; split `bond_id` scoping from unspecified-fallback per Task 0. No new behavior, no learned replacement.

**Tech Stack:** Python 3, stdlib. Test runner: **unittest, NOT pytest** — `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.<module>`.

**Covenant rails:** producer stays dormant; safety/consent/third-party/scoping rails byte-unchanged (a breaking safety test = STOP, real regression); no learned-salience; no live behavior change; preference-pinning tests are *flipped*, never deleted to hide a regression.

---

### Task 0: The classification table — covenant artifact — STOP for owner sign-off (no production code)

- [ ] **Step 1: Read every candidate element**

```
cd /home/rohit/maez
sed -n '181,200p' core/evolution/drive_driven_curiosity.py     # the two weight tables
grep -nE "_priority_class_weight|_marker_confidence_weight|priority_class|subject_kind|bond_id|owner_bond_meaningful|_count_owner_bond" core/evolution/drive_driven_curiosity.py
```

- [ ] **Step 2: Produce the owner-readable classification table** → `docs/proofs/2026-06-28-curiosity-priors-table.md`

| element | what it does | class | action | code evidence |
|---|---|---|---|---|
| `_priority_class_weight` (owner 1.0/self 0.9/world 0.4) | ranks what to value | PREFERENCE | remove | :181, used :912 :1160 |
| `_marker_confidence_weight` (owner-resolved>self) | ranks owner resolution | PREFERENCE | remove | :190, used :1162 |
| default `priority_class="owner_bond"` | assumes unspecified = owner | PREFERENCE | remove/neutralize | :404 |
| default `subject_kind=OWNER_BOND_RELATIONAL` | assumes about-owner | PREFERENCE (default) | neutralize default, keep gating | :406 |
| `owner_bond` cap/auto-eligibility branch | owner-only throttle + owner auto-meaningfulness | PREFERENCE in its owner-only form | remove owner-only branch; preserve saturation through existing general per-bond / daily-delta path | :108 :948 :998-:1023 |
| `bond_id` *each use* | scoping vs fallback | **SPLIT** | scoping → keep; unspecified-fallback → make caller-explicit | :401 + trace all uses |
| third-party refusal | consent safety | SAFETY | **keep untouched** | `named_third_party_without_owner_explicit_consent` |
| subject-kind validator/gates | consent/third-party mechanism | SAFETY | **keep untouched** | the validator path |

Fill one row per real element. **No element is kept on "looks like safety" — the keep is justified by the evidence line.**

- [ ] **Step 3: Enumerate the test split + confirm dormancy**

Record which existing `drive_driven_curiosity` / related tests pin **preferences** (will be *flipped*) vs **safety** (must stay green, untouched). Confirm `register_default_encounter_producers()` has **no live caller**:
```
grep -rnE "register_default_encounter_producers\(\)" --include=*.py core/ daemon/ | grep -v "def "
```
Expected: empty (dormant). Record it.

- [ ] **Step 4: STOP — present the table for owner sign-off.** No production code until the table is signed.

---

### Task 1: RED-first — pin removal AND preservation (write tests before any edit)

**Files:** Test `tests/test_curiosity_priors_cleanup.py` (new)

- [ ] **Step 1: Write the preference-removal tests (these go RED now — the taste still exists)**

```python
import unittest
from core.evolution import drive_driven_curiosity as ddc

class PreferencesRemovedTest(unittest.TestCase):
    def test_no_category_outranks_another_by_hardcoded_weight(self):
        # after cleanup: no priority-class weight function imposing a ranking
        self.assertFalse(hasattr(ddc, "_priority_class_weight"),
                         "preference weight must be gone")
        self.assertFalse(hasattr(ddc, "_marker_confidence_weight"),
                         "owner-resolution preference weight must be gone")

    def test_no_owner_first_default_priority_class(self):
        import inspect, re
        src = inspect.getsource(ddc)
        self.assertNotRegex(src, r'priority_class["\']?\s*,\s*["\']owner_bond["\']',
                            "unspecified curiosity must not default to owner_bond")
```

- [ ] **Step 2: Write the safety/scoping preservation guard tests (GREEN now, MUST stay green)**

```python
class SafetyRailsHoldTest(unittest.TestCase):
    def test_third_party_without_consent_still_refused(self):
        # the named-third-party refusal still fires exactly as before
        ...  # drive a seed with a NAMED_THIRD_PARTY subject_kind, assert refusal/refused-receipt
    def test_subject_kind_gating_unchanged(self):
        ...  # the consent/subject-kind gate refuses what it refused pre-cleanup
    def test_bond_id_scoping_use_preserved(self):
        ...  # explicit-scope bond_id still routes to its drawer; only the unspecified-fallback is gone

class StillDormantTest(unittest.TestCase):
    def test_register_default_encounter_producers_has_no_live_caller(self):
        import pathlib, re
        roots = ("core", "daemon")
        callers = []
        for root in roots:
            for p in pathlib.Path(root).rglob("*.py"):
                if "test" in p.name: continue
                if re.search(r"register_default_encounter_producers\(\)", p.read_text(encoding="utf-8")):
                    callers.append(str(p))
        self.assertEqual(callers, [], f"producer must stay dormant; live callers: {callers}")
```

- [ ] **Step 3: Run.** Preference-removal tests → **RED** (taste present). Safety + dormancy tests → **GREEN** (nothing changed yet). If a safety test is already red, STOP — the test is wrong, not the code.

---

### Task 2: Implement the removal — ONLY after the Task 0 table is signed

**Files:** Modify `core/evolution/drive_driven_curiosity.py`; reconcile existing tests.

- [ ] **Step 1: Per the signed table** — delete `_priority_class_weight` + `_marker_confidence_weight`; at the salience sites (:912, :1160, :1162) salience becomes **unweighted** (raw producer salience, no category scaling); remove/neutralize the owner-first `priority_class` default and the `subject_kind` *default* (keeping the gating); remove the owner-only `owner_bond` cap/auto-eligibility branch so owner-bond flows through the general path; make any unspecified `bond_id` fallback caller-explicit. **Touch no safety/consent/third-party/scoping logic.**

- [ ] **Step 2: Flip the existing preference-pinning tests** — any current test asserting `owner_bond` outranks others, or the owner-first defaults, is **flipped** to assert the preference is gone. **Do not delete** them (deletion hides the regression). **Leave every safety-pinning test untouched** — if one breaks, STOP and surface it.

- [ ] **Step 3: Run the full picture + ruff**
```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_curiosity_priors_cleanup tests.test_drive_driven_curiosity -v
/home/rohit/maez/.venv/bin/ruff check core/evolution/drive_driven_curiosity.py tests/test_curiosity_priors_cleanup.py
```
Expected: preference-removal **GREEN**; safety + dormancy **STILL GREEN**; existing safety tests unchanged + passing; ruff clean.

- [ ] **Step 4: Commit** (`refactor(curiosity): remove owner-first preference priors from dormant producer; safety rails + dormancy unchanged`).

---

### Task 3: Prove zero behavior change + handoff + STOP

- [ ] **Step 1:** Confirm the diff touches only `core/evolution/drive_driven_curiosity.py` + tests (no daemon wiring, no flag, no new caller); re-run the dormancy grep (still no live caller).
- [ ] **Step 2:** Write `docs/handoffs/2026-06-28-curiosity-priors-cleanup-v0-handoff.md`: the **owner-signed table**, the `owner_bond`-cap and `bond_id` decisions, the test split (which flipped, which stayed), the dormancy proof, full test + ruff output. State plainly: producer still dormant, no learned salience, no live behavior change, NOT a producer-wake.
- [ ] **Step 3: Commit + STOP** for Claude covenant review (preferences gone; safety rails byte-unchanged + green; producer uncalled; preference-tests flipped not deleted; zero `register_default_encounter_producers` caller).

---

## Self-Review
**Spec coverage:** classification table as covenant gate + owner STOP (Task 0 ✓); preference weights/defaults removed (Task 1 RED → Task 2 ✓); safety/scoping preserved as load-bearing green guards (Task 1 §2 + Task 2 §2 ✓); `owner_bond` cap decided by Codex's test, `bond_id` split by use (Task 0 + Task 2 §1 ✓); no learned salience / no wake / dormancy proven (rails + `StillDormantTest` ✓); preference tests flipped not deleted (Task 2 §2 explicit ✓); zero live behavior change (dormant + diff-scope check ✓).
**Placeholder scan:** the exact safety-test assertions and the `owner_bond`/`bond_id` decisions are Task 0 confirmations (the human-signed boundary), not TBDs.
**Type consistency:** salience sites lose the `* _weight(...)` factor uniformly; no new symbols; safety/consent/scoping signatures untouched.
