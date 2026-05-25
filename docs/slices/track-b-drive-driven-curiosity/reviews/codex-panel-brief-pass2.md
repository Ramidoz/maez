# Codex Engineering Panel Brief -- Drive-Driven Curiosity v4.2 Pass 2 (Narrow)

**Prepared:** 2026-05-25 (continuous from session of 2026-05-25)
**Artifact under review:** `docs/slices/track-b-drive-driven-curiosity/spec.md`
**Artifact state:** DRAFT v4.2, ~3647 lines, uncommitted
**Parent/runtime base:** `211ace6 feat(felt-time): implement meaningful salience seam`
**Review lane:** Codex engineering panel pass-2 (NARROW; amended
surfaces only)
**Operator:** Rohit relays and dispatches; Codex panel does not
auto-dispatch onward work.

---

## Why This Pass Exists And What It Is NOT

v4.1 received Codex engineering panel pass-1 review (2026-05-25):
RATIFY-WITH-AMENDMENTS, 4 Blocking + 16 Major + 8 Minor findings, no
RECONSIDER, no architectural reshape. Panel review at
`reviews/codex-panel-v4.1-pass1.md`.

v4.2 (this draft) folds the 21 engineering findings in place. The
producer-over-wonderings premise is preserved.

**This pass-2 is INTENTIONALLY NARROW.** Its only job is to verify
that the 21 pass-1 findings actually landed correctly in v4.2 — that
the engineering corrections are mechanically present, the §22
scope-realism decisions are coherent, and the §23 RED table addition/
refinement set is implementation-ready. It is NOT a full re-review of
v4.2.

**Hard out-of-scope for pass-2** (re-stating Rohit's constraints):

- Slice 1 (`subjective_duration` meaningful-salience seam) remains
  canonical at `211ace6`. Do NOT re-litigate.
- Architecture reshape. The producer-over-wonderings premise was
  ratified by council pass-1 (six axes), held by Codex pass-1, and is
  not on the table.
- Council re-review. The 33 council pass-1 folds are part of v4.1's
  baseline; v4.2 inherits them. Council findings remain load-bearing.
- Full-slice re-litigation. Any surface that v4.2 did NOT amend in
  response to a pass-1 finding is out of scope — even if pass-2 would
  have a fresh opinion about it. That opinion belongs in a future
  pass on a future fold, not here.

If a real surface contradiction surfaces in an amended section that
forces RECONSIDER, name it. Do not invent reasons to expand scope.

---

## What v4.2 Amended (the only surfaces in scope)

Below is the *exhaustive* list of v4.2 amendments mapped to pass-1
finding IDs. Pass-2 reviews these and only these.

### Blocking-resolution folds

| Pass-1 finding | v4.2 amendment surface | Specific check |
|---|---|---|
| F1 (Preserve Wonderings callers) | §5.2 `add(question, source="manual", *, bond_id="_LEGACY")`; `resolve(...)` optional kwargs; RED #3 reworded to bind to drive producer boundary, #6 reworded for back-compat | Verify the signature change is non-breaking for the named callers (`cli/maez_chat.py:489-496`, `daemon/wondering_cycle.py:286-288`, `tests/test_wonderings.py`, `tests/test_wondering_pursuit_history.py`). Verify drive producer enforces real bond_id. Verify §5.1 `_LEGACY` projection refusal still holds at the drive layer |
| F5 (Emit SUBJECT_BOUNDARY_REFUSED before raise) | §13.6 `enforce_subject_boundary(...)` rewritten with `_diag.emit(...)` BEFORE both raise sites (UNKNOWN and NAMED_THIRD_PARTY); §20.1 already has the event type from v4.1 | Verify pseudocode emits before raise for BOTH paths; no raw bond/person identifier in diagnostic; RED #33b/#33c/#58b carry the ordering assertion |
| F8 (Production gate for MANUAL_TEST_PRODUCER) | §6.1.1 `register_encounter_producer(*, source, evidence_pointer_kind, producer_ref: ProducerRef, canary: bool = False, create_curiosity_object)`; refusal path explicit; RED #7a added; §24 row updated; §25 item 4 updated; §27.3 names the fold | Verify the production gate is mechanical (not commentary). Verify `canary=False AND producer_ref=MANUAL_TEST_PRODUCER` is the exact refusal predicate. Verify RED #7a covers both refusal AND `canary=True` acceptance |
| F10 (Canonical §23 rows for #46b/#46c) | §23.6 now carries `#46b test_subject_kind_omission_refused_at_creation` and `#46c test_named_third_party_without_matching_owner_explicit_consent_refused_at_creation` as canonical rows iterating every v1-wired EncounterSource | Verify rows are present in §23.6 with the exact test names and iterate-every-producer semantics. Verify inline references (§6.2.2, §13.4) cite these row numbers |

### Major / Minor non-blocking amendments

Reviewed only where text/tests/scope changed.

| Pass-1 finding | v4.2 amendment surface |
|---|---|
| F2 (Race-safe migration) | §5.2 now requires the migrations live inside `Wonderings._init_schema()` using the existing duplicate-column guard |
| F3 (FK + index + PRAGMA) | §5.2.1 specifies `PRAGMA foreign_keys=ON`; RED #5b extended to four sub-assertions (table_info / foreign_key_list / index_list / negative-FK fail) |
| F4 (`_LEGACY` refusal scope) | §5.1 + §5.2.1 explicitly name "single-row drive projector only"; old read paths unchanged; collection-level drive readers SKIP `_LEGACY` rather than RAISE; RED #5d added |
| F6 (URL contract) | §13.5 introduces `_provider_url_for_query(query)` helper; no `query.public_safe_url()` reference |
| F7 (Single creation choke point) | §6.1.1 `register_encounter_producer` wraps `create_curiosity_object` in `_wrap_with_subject_kind_validator`; §6.2.2 names the wrapper as the single un-bypassable enforcement site |
| F9 (Pin #40a/#40b AST predicates) | §14.3.5 now distinguishes runtime tests + static-AST predicates; literal-kwarg requirement pinned; `**kwargs` banned at raw authority-bearing calls; §23.7 #40a/#40b row text updated |
| F11 (Non-vacuous #58b) | §15.0 specifies discovered-raise-site set MUST be non-empty AND include named anchor surfaces; §23.8 #58b row text updated |
| F12 (Settle Q2) | §22 Q2 status SETTLED → `core/evolution/drive_driven_curiosity.py`; §24 adapter-module row reworded; §22 Q2 entry updated |
| F13 (Phase EncounterSources) | §6.2 split into v1 wired (3) + v1.1 deferred (4) with per-source deferral reasons; RED #9 reshaped to assert both sets |
| F14 (Defer semantic match entirely) | §14.1 enum reduced to EXPLICIT_*; §14.2 names full deferral and removes feature flag; §14.5.2 NOT_ELIGIBLE_LOW_CONFIDENCE marked future-only; §5.2 CuriosityStateTransition reason set drops RESOLVED_SEMANTIC; §22 Q5 settled |
| F15 (Static scan roots) | §8.5.1 + §13.5 + §24 all name "drive-layer scan roots: drive_driven_curiosity.py + core/policies/*.py + new drive-only adapter modules; reused substrate OUT of scope"; RED #10 row text updated |
| F16 (Capability surface correction) | §8.5.1 quotes `core/infra/capability_acquisition_queue.py:275` as the real handler location; refusal predicate covers `action_engine.capability.acquire` AND any `handle_capability_*` symbol via either runtime or static-AST path; RED #11 row text updated |
| F17 (Alias-aware #33d) | §13.5 enumerates alias patterns (direct import, module-qualified, `as`-aliased, etc.); RED #33d row text updated; `fetch_for_curiosity.py` exempt |
| F18 (#43 consumer allowlist) | §15.6 names exact v1 allowlist (5 entries); RED #43 row text updated; asserts zero reference from `subjective_duration.py` |
| F19 (#50 template scope enumerated) | §14.7 names exact file scope + module-level string-constant naming convention (`_PROMPT_TEMPLATE`, `_SYSTEM_PROMPT`, `_TEMPLATE`); split runtime-composition explicitly to #50b; RED #50 row text updated |
| F20 (#58a AST not grep) | §15.0 specifies AST walk with import-alias map; RED #58a row text updated |
| F21 (ProducerRef extension wording) | §2.2 and §14.4 both gain "after this slice extends `ProducerRef`" before the seam-consumption snippet |

### §22 scope decisions to verify for coherence (do NOT re-litigate)

- **Q2: `core/evolution/drive_driven_curiosity.py` as adapter module.**
  Verify §24 adapter-module row, §8.5.1 scan roots, §13.5 scan roots,
  §15.6 #43 allowlist, and §22 Q2 entry all agree.
- **Q4: 3 wired + 4 deferred EncounterSources.** Verify §6.2 split,
  §5.1.1 producer table, §22 Q4 entry, and §23.2 RED #9 row all
  agree. Confirm each deferred source has a stated reason in §6.2.
- **Q5: Semantic-match deferred entirely.** Verify §14.1
  `ResolutionMarkerType` (only EXPLICIT_*), §14.2 prose, §14.5
  `NOT_ELIGIBLE_LOW_CONFIDENCE` future-only marker, §5.2
  `CuriosityStateTransition` reason set, and §22 Q5 entry all agree.
  Confirm no feature-flag mention remains in Slice 2.

---

## Non-Negotiable Pass-2 Discipline

1. **Verify the amendment, then stop.** For each pass-1 finding above,
   confirm the v4.2 fold is mechanically correct against the real
   substrate at parent `211ace6`. Do NOT re-review surrounding text
   that did not change.
2. **Discovered drift is reportable, not re-reviewable.** If pass-2
   notices a real contradiction in v4.2's amendments to other v4.2
   amendments (cross-amendment internal inconsistency), name it as a
   pass-2 finding. If pass-2 notices something pass-1 missed in
   unchanged v4.1 surfaces, *flag it briefly* as "v4.3-or-later
   consideration" and move on — do not file it as a pass-2 finding.
3. **Preserve covenant findings as load-bearing constraints.** The
   council pass-1 covenant folds (anti-laundering, third-party
   subject boundary, anti-coercion, charter-floor invariant, OWNER_BOND
   saturation guard, mutuality framing, etc.) are inherited from
   v4.1's baseline. Codex's job remains making them mechanically true,
   not weakening them.
4. **Test count drift is fine if explained.** v4.2 went 79 → 83
   tests (additions: #5d, #7a, relocated #46b/#46c). If pass-2
   suggests further additions, count them. If pass-2 suggests
   collapse/renumbering, note the diff explicitly.

---

## Verdict Format

```markdown
# Codex Engineering Panel Pass-2 -- Drive-Driven Curiosity v4.2

**Verdict:** RATIFY-CLEAR | RATIFY-WITH-AMENDMENTS | RECONSIDER
**Severity summary:** <one paragraph on whether the 21 pass-1
findings landed correctly + any newly-surfaced cross-amendment
contradictions>

## Per-Finding Verification

For each pass-1 finding F1–F21, report:

**F<N>:** LANDED-CORRECTLY | LANDED-WITH-NIT | NOT-LANDED |
DRIFTED
- v4.2 surface(s) checked: ...
- Verification notes: ...
- (If NOT-LANDED or DRIFTED) Required v4.3 fold: ...

## §22 Scope Decisions Coherence

- Q2: COHERENT | INCOHERENT (named surfaces ...)
- Q4: COHERENT | INCOHERENT (named surfaces ...)
- Q5: COHERENT | INCOHERENT (named surfaces ...)

## §23 RED Table Verification

- Count: 83 confirmed | <other count>
- New rows present (#5d, #7a, #46b in §23.6, #46c in §23.6): all confirmed | issues ...
- Refined rows (#5b, #9, #10, #11, #33d, #40a, #40b, #43, #50,
  #58a, #58b): all confirmed | issues ...
- Implementability: all 83 implementable | flagged ...

## New Findings (v4.2 cross-amendment contradictions only)

[Use the standard Finding format from pass-1 brief if any exist.
If none, write "No new findings — v4.2 amendments are internally
coherent."]

## v4.3-or-later Considerations (drift flags, not pass-2 findings)

[Brief list of "saw this but didn't pursue per pass-2 scope" items,
if any. Use one bullet per item with the surface and the concern in
≤30 words.]

## Plain-Language Readout For Rohit

[One paragraph: is v4.2 implementation-ready, did the pass-1 folds
land honestly, what (if anything) needs another fold cycle.]
```

Verdicts:

- **RATIFY-CLEAR:** v4.2 can proceed to canonicalization + TDD
  implementation. All 21 pass-1 findings landed correctly; no new
  contradictions.
- **RATIFY-WITH-AMENDMENTS:** small NIT-level corrections needed; a
  v4.3 micro-refold suffices, no further Codex pass required.
- **RECONSIDER:** at least one pass-1 finding did NOT land
  correctly, OR a cross-amendment contradiction exists that requires
  re-engagement. Name the specific surface; cross-lane (council)
  involvement only if architectural premises are challenged.

---

## Output Path

Write the pass-2 review to:
`docs/slices/track-b-drive-driven-curiosity/reviews/codex-panel-v4.2-pass2.md`

End with the plain-language readout for Rohit.

---

## What Comes Next

After pass-2 returns:

- **RATIFY-CLEAR:** Rohit signals canonicalization (commit `spec.md` +
  reviews dir); TDD implementation cycle begins (Codex 7+3 panel
  coordinates).
- **RATIFY-WITH-AMENDMENTS:** Claude refolds v4.2 → v4.3 (micro-
  refold); proceed to canonicalization without further Codex pass
  unless v4.3 amendments touch new surfaces.
- **RECONSIDER:** synthesis surfaces the specific contradiction to
  Rohit; targeted fold (council or Codex depending on lane); v4.3
  reflects the resolution; pass-3 against v4.3 over the targeted
  surface.

Do not canonicalize, commit, implement, or relay onward work from
this brief alone. Rohit operates the switchboard.

**End of Codex engineering panel pass-2 brief.**
