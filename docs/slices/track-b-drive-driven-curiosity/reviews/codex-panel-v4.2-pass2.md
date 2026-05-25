# Codex Engineering Panel Pass-2 -- Drive-Driven Curiosity v4.2

**Verdict:** RATIFY-WITH-AMENDMENTS

**Severity summary:** All 21 Codex pass-1 findings landed mechanically, and no
pass-2 reviewer found a NOT-LANDED, DRIFTED, or RECONSIDER-grade contradiction.
The v4.2 amendment set is implementation-ready after a micro-refold that cleans
up three prose nits: stale §23.2 references for #46b/#46c, strict
feature-flag wording around semantic-match deferral, and one ambiguous
`core/policies/exceptions.py` raise-site phrase in #58b prose. No further Codex
pass is needed if v4.3 only applies those nits.

## Per-Finding Verification

**F1:** LANDED-CORRECTLY
- v4.2 surface(s) checked: §5.2, §5.2.1, §23.1 #3/#5a/#6;
  `core/evolution/wonderings.py:272`, `:607`;
  `cli/maez_chat.py:489`, `daemon/wondering_cycle.py:286`.
- Verification notes: `Wonderings.add(...)` is specified as
  `add(question, source="manual", *, bond_id="_LEGACY")`, preserving old
  callers while the drive producer boundary enforces real `bond_id`. `resolve`
  keeps backward-compatible positional behavior, with drive marker behavior
  optional or wrapper-owned.

**F2:** LANDED-CORRECTLY
- v4.2 surface(s) checked: §5.2; `core/evolution/wonderings.py:174`.
- Verification notes: migrations are required inside `Wonderings._init_schema()`
  using the existing `existing_cols` plus duplicate-column
  `OperationalError` guard.

**F3:** LANDED-CORRECTLY
- v4.2 surface(s) checked: §5.2, §5.2.1, §23.1 #5b.
- Verification notes: `PRAGMA foreign_keys=ON`, FK list, index list, and
  negative-FK failure are all specified.

**F4:** LANDED-CORRECTLY
- v4.2 surface(s) checked: §5.1, §5.2.1, §23.1 #5d.
- Verification notes: `_LEGACY` refusal is scoped to single-row drive
  projection. Existing `Wonderings` read paths remain unchanged; collection
  drive readers skip/refusal-log legacy rows.

**F5:** LANDED-CORRECTLY
- v4.2 surface(s) checked: §13.6, §20.1, §23.6 #33b/#33c, §23.8 #58b.
- Verification notes: both `UNKNOWN` and unconsented `NAMED_THIRD_PARTY`
  paths emit `SUBJECT_BOUNDARY_REFUSED` before raising, without raw bond or
  person identifiers.

**F6:** LANDED-CORRECTLY
- v4.2 surface(s) checked: §13.5.
- Verification notes: `_provider_url_for_query(query)` replaces the nonexistent
  `query.public_safe_url()` contract. Remaining `public_safe_url` mention is a
  negative explanatory reference only.

**F7:** LANDED-CORRECTLY
- v4.2 surface(s) checked: §6.1.1, §6.2.2.
- Verification notes: `register_encounter_producer(...)` wraps callbacks with
  `_wrap_with_subject_kind_validator(...)`, named as the single enforcement
  site for creation-layer subject-kind refusal.

**F8:** LANDED-CORRECTLY
- v4.2 surface(s) checked: §6.1.1, §23.2 #7a, §24, §25, §27.3.
- Verification notes: production exclusion is mechanical:
  `canary=False AND producer_ref == ProducerRef.MANUAL_TEST_PRODUCER` raises.
  RED #7a covers refusal and `canary=True` acceptance.

**F9:** LANDED-CORRECTLY
- v4.2 surface(s) checked: §14.3.5, §23.7 #40a/#40b.
- Verification notes: runtime tests and AST predicates are separated; literal
  kwargs are required; raw `**kwargs` at authority-bearing calls are banned
  unless routed through the approved wrapper.

**F10:** LANDED-WITH-NIT
- v4.2 surface(s) checked: §6.2.2, §13.4, §23.6 #46b/#46c, §23.9.
- Verification notes: canonical #46b/#46c rows exist in §23.6 with exact test
  names and iterate-every-v1-wired-producer semantics.
- Required v4.3 fold: replace stale "§23.2" references in §6.2.2 and §13.4
  with §23.6.

**F11:** LANDED-WITH-NIT
- v4.2 surface(s) checked: §15.0, §23.8 #58b.
- Verification notes: #58b now requires a non-empty AST-discovered raise-site
  set and named anchors, with diagnostic-before-raise assertions.
- Required v4.3 fold: rephrase the §15.0 bullet that mentions
  `core/policies/exceptions.py` so that file is clearly the exception-family
  declaration surface, not a minimum raise-site anchor.

**F12:** LANDED-CORRECTLY
- v4.2 surface(s) checked: §22 Q2, §24, §8.5.1, §13.5, §15.6.
- Verification notes: adapter module is pinned to
  `core/evolution/drive_driven_curiosity.py`; `wonderings.py` remains storage
  substrate only.

**F13:** LANDED-CORRECTLY
- v4.2 surface(s) checked: §6.2, §22 Q4, §23.2 #9.
- Verification notes: three v1 wired sources and four v1.1 deferred sources
  are named with reasons, and RED #9 agrees.

**F14:** LANDED-WITH-NIT
- v4.2 surface(s) checked: §14.1, §14.2, §14.5.2, §5.2, §22 Q5, §25.
- Verification notes: semantic-match behavior is mechanically deferred:
  `ResolutionMarkerType` has only explicit markers, low-confidence is
  future-only, and no enabling flag mechanism ships.
- Required v4.3 fold: if the pass-2 strict checklist means zero literal
  "feature flag" mentions, rewrite the remaining explanatory phrases so they
  say "no semantic-match mechanism ships in Slice 2" without carrying feature-
  flag wording.

**F15:** LANDED-CORRECTLY
- v4.2 surface(s) checked: §8.5.1, §13.5, §23.2 #10, §24.
- Verification notes: drive-layer scan roots are explicit and reused substrate
  is out of scope.

**F16:** LANDED-CORRECTLY
- v4.2 surface(s) checked: §8.5.1, §23.2 #11.
- Verification notes: the capability surface is corrected to
  `core/infra/capability_acquisition_queue.py`; RED #11 matches queue-only
  and static-AST refusal discipline.

**F17:** LANDED-CORRECTLY
- v4.2 surface(s) checked: §13.5, §23.6 #33d.
- Verification notes: #33d is alias-aware and exempts the wrapper
  `core/egress/fetch_for_curiosity.py`.

**F18:** LANDED-CORRECTLY
- v4.2 surface(s) checked: §15.6, §23.8 #43.
- Verification notes: exact `compute_saturation` consumer allowlist is present,
  including the zero-reference assertion for `subjective_duration.py`.

**F19:** LANDED-CORRECTLY
- v4.2 surface(s) checked: §14.7, §23.8 #50/#50b.
- Verification notes: source/template scope is enumerated; runtime composition
  is explicitly split to #50b.

**F20:** LANDED-CORRECTLY
- v4.2 surface(s) checked: §15.0, §23.8 #58a.
- Verification notes: #58a is AST-based with import-alias resolution, not grep.

**F21:** LANDED-CORRECTLY
- v4.2 surface(s) checked: §2.2, §14.4.
- Verification notes: early prose now frames seam consumption as happening
  after this slice extends `ProducerRef`.

## §22 Scope Decisions Coherence

- Q2: COHERENT. §22 Q2, §24 adapter row, §8.5.1 scan roots, §13.5 scan roots,
  and §15.6 #43 allowlist agree on `core/evolution/drive_driven_curiosity.py`.
- Q4: COHERENT. §6.2, §22 Q4, and §23.2 RED #9 agree on three wired and four
  deferred `EncounterSource`s. v4.3-or-later could add a phase column to
  §5.1.1, but §6.2 is already explicit.
- Q5: COHERENT mechanically; LANDED-WITH-NIT under the strict "no feature-flag
  mention remains" checklist. No semantic-match mechanism ships.

## §23 RED Table Verification

- Count: 83 confirmed by table-row parse across §23.1-§23.8, matching §23.9.
- New rows present: #5d, #7a, #46b in §23.6, #46c in §23.6 all confirmed.
- Refined rows: #5b, #9, #10, #11, #33d, #40a, #40b, #43, #50, #58a, and #58b
  all confirmed.
- Implementability: all v4.2-amended rows appear implementable as RED-first
  tests. No amended row appears impossible, trivially green, or trivially red.

## New Findings (v4.2 cross-amendment contradictions only)

No new findings. The v4.2 amendments are internally coherent. The remaining
items are wording nits, not mechanical contradictions.

## v4.3-or-later Considerations

- §5.1.1 lists all seven `EncounterSource`s without a phase column; §6.2 is
  explicit, so this is optional polish.
- RED #6 leaves either optional `Wonderings.resolve(...)` kwargs or a
  drive-layer wrapper acceptable; implementation should choose one before
  writing the RED.

## Plain-Language Readout For Rohit

v4.2 did the real work: every pass-1 engineering fold landed, the four
Blocking issues are resolved mechanically, §22 has no open questions, and the
83-test RED table is coherent. The only remaining work is a tiny v4.3 prose
cleanup: fix stale #46b/#46c section references, remove or reword leftover
"feature flag" phrasing around semantic-match deferral, and clarify that
`core/policies/exceptions.py` declares the exception family rather than being a
raise-site anchor. After that micro-refold, this spec is ready for
canonicalization and TDD implementation without another Codex pass.
