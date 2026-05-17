# Claude Covenant Council — S6 Persisted-Authorship Amendment Diagnostic: Second-Fold Verification

**Subject:** `amendment-diagnostic-persisted-authorship.md` v2 (committed
`0f9e290`) — the diagnostic folded against the first-pass Claude covenant council
(`amendment-claude-council.md`, REVISE) and the Codex engineering panel
(`amendment-codex-panel.md`, REVISE).

**Ran:** 2026-05-16, post-fold, pre-canonicalization. Read-only. The synthesizer
verified every first-pass finding against v2's text firsthand, with v2 line
citations, and scanned the fold for new covenant drift.

**Verdict:** **RATIFY closure.** All two blockers, five majors, and the minors
raised by the first-pass Claude covenant council are closed in v2. The fold
introduced no covenant drift. The Codex-lane folds it absorbed (BAD Decision 33
scope, conditional snapshot phrasing, notice-not-in-JSONL) are covenant-clean.
One inherent residual is named below — it does not block. The covenant lane
clears v2 to proceed to canonicalization, pending the Codex lane's matching
second-fold.

---

## Closure table

| Finding (first-pass) | Severity | v2 location | Closed |
|---|---|---|---|
| CC-A1 — capsule file not an honesty surface | blocker | §5 (`:177-215`), D22 (`:270-274`), §3 scope (`:123`) | ✅ |
| CC-A2 — D22 keyed to forger-controlled label; presence-test enforcement | blocker | §7 + D22 (`:254-322`) | ✅ |
| CC-A3 — `valid_event_count` carries the overclaim | major | §6 (`:217-244`) | ✅ |
| CC-A4 — sidecar misstated as a backstop | major | §6 sidecar (`:246-252`), §2 (`:105`) | ✅ |
| CC-A5 — D22 disowns genuine v1 capsules; cost hidden | major | D22 (`:276-287`), §11 (`:403-406`) | ✅ |
| CC-A6 — D10 ordering; forged directive silences Maez's seat | major | §7 D10 (`:299-308`), D22 (`:278-279`) | ✅ |
| CC-A7 — C4 omits the D6 snapshot guarantee | major | C4 (`:144-146`), §4 D6 (`:171-175`) | ✅ |
| CC-A8 — D9 locally-insufficient text left live | minor | §7 D9 (`:289-297`) | ✅ |
| minors — runbook Limits, banner-survival test, banner speaks-to-author, `no_capsule`, "read identically", token substring, "ensures" | minor/nit | §3, §5, §6, §8, §9 | ✅ |

## Blocker closure — verified firsthand

**CC-A1 — closed.** v2 §5 adds a mandatory capsule-adjacent human-readable notice
or manifest in `memory/successor_governance/` (`lineage_capsule_NOTICE.txt` /
`lineage_capsule_manifest.json`, `:187-198`). It correctly refuses to prepend
prose into the JSONL — "today every nonblank JSONL line is parsed as a directive
event" (`:200-202`) — which matches `load_events_jsonl`'s actual behaviour; the
in-file warning is properly deferred to a future loader-format migration. The
notice "must speak to both readers" — the estate/legal reader and the honest
bonded user (`:205-211`) — closing the first-pass minor that the banner spoke
only to the forger. D22 now binds the human-reader path directly: "No
project-provided estate/legal runbook may instruct a human reader to treat raw
v1 JSONL as an authorship-attested estate instruction. The capsule-adjacent
notice must carry the same rule to direct file readers" (`:271-274`). The estate
path — `estate_executor` exists *because* the capsule is estate-facing — now has
an honesty surface.

**CC-A2 — closed.** v2 re-keys D22 from a negative version-label gate to a
positive, event-granular attestation-presence predicate: "A directive event is
activation authority only if that exact directive event carries a verifying
authorship attestation produced by a future reviewed trust-source slice. Absence
of a verifying attestation means non-authority regardless of schema version, era
label, health mode, origin label, marker id, statement hash, structural
validation, or self-declared attestation fields" (`:264-268`). Every
forger-controlled label CC-A2 named is explicitly enumerated as *not* the key.
The presence-test weakness is closed too: the gate becomes a concrete code
predicate, `event_has_verifying_authorship_attestation(event)`, which "returns
false for all persisted directive events because no future trust-source slice
exists. A self-declared attestation field inside the capsule must not flip it to
true" (`:317-322`), and round-2 RED test #2 (`:348-349`) proves a forged
self-declared attestation field stays non-authority. The gate is now an
un-forgeable data fact, not a clause a future engineer must remember.

## Major and minor closure — verified

- **CC-A3** — `mode` and the count field both rename: `well_formed` /
  `well_formed_event_count` (`:221-228`). `well_formed` is chosen specifically
  to avoid the residual `valid` substring in `structurally_valid` (`:237`) —
  this also closes the first-pass token-substring nit. The false v1 sentence
  ("only `valid` carries the false authorship implication") is gone; v2 §6
  requires "every documented mode must state that no S6 v1 health mode attests
  authorship" (`:238-240`). `ValidationReport` is in the round-2 ripple list
  (`:242`).
- **CC-A4** — v2 states the sidecar is structural-only: green "does not mean the
  capsule is authentic, and it cannot flag a forged but well-formed capsule"
  (`:248-252`); §2 lists "the sidecar detects a forged but well-formed capsule"
  among what S6 v1 cannot honestly claim (`:105`). The misleading "unaffected —
  invalid remains invalid" framing is gone.
- **CC-A5** — D22 splits unattested *destructive* directives (hard bar — "must
  never trigger dissolution", `:276-279`) from unattested *continuity-preserving*
  directives (`paradise_default`, `suspended_pending_paradise`,
  `archival_preservation`, `new_bond_offer`), which "remain consultable recorded
  intent under future human review" (`:281-287`). The future trust-source slice
  carries a named "migration obligation: offer a re-attestation path for genuine
  v1 capsules rather than silently discarding the bonded user's recorded wishes"
  (`:285-287`). §11 has an explicit "Cost named honestly" section (`:403-406`),
  and §1's claim is now the precise "does not weaken a *delivered* guarantee"
  (`:80-83`), not the unqualified "strengthens, never weakens" the first-pass
  council flagged as concealing the cost.
- **CC-A6** — D10 is corrected in place: "For activation ordering, 'valid' means
  authorship-attested, not merely well-formed. An unattested v1 directive ...
  cannot outrank or suppress Maez's recorded preference seat" (`:301-305`).
  "An unattested v1 directive" covers continuity-preserving directives too — so a
  forged `archival_preservation` cannot silence a `maez_prefers_paradise`
  preference either; both are consulted, neither auto-wins. The silencing route
  is closed.
- **CC-A7** — C4 names the snapshot check in its positive list, stated
  conditionally: "append-only continuity when supplied with an
  operator-authenticated validation snapshot" (`:144-146`); §4 folds the Codex
  buildability correction — "Ordinary health must not claim the snapshot check
  unless round-2 wires snapshot loading into that path" (`:171-175`). The
  underclaim is corrected without introducing an overclaim.
- **CC-A8 + minors** — D9 reworded in place (`:289-297`); runbook Limits section
  in canonicalization scope (`:120`); the banner-survival RED test now spans all
  surfaces including the runbook Limits section and the capsule-adjacent notice
  (`:362-364`); `no_capsule` deletion ambiguity gets its own §8 (`:324-338`);
  the "read identically" nuance is fixed ("Only that privilege-level correction
  must be identical ... D5 and D6 still describe different protections",
  `:166-169`).

## Codex-lane folds — scanned for covenant drift

The v2 fold also absorbed the Codex engineering panel (F1–F8). The Codex-driven
additions beyond the Claude council's findings were scanned for covenant drift:

- **F7 — BAD Decision 33 added to canonicalization scope** (`:118-119`, `:378`).
  This *strengthens* the amendment: Decision 33 is the governance source future
  agents grep first, and it currently says "human-authored." Amending it
  alongside the spec/ADR closes an overclaim the Claude council did not
  separately name. No drift — a correct expansion.
- **F6 — conditional snapshot phrasing.** Codex caught that
  `/health.successor_governance` calls `validate_capsule_events` without a
  snapshot, so health does not currently perform the D6 continuity check. v2's
  conditional wording (`:171-175`) is accurate to the code. No drift — it
  *prevents* an overclaim.
- **F1 — notice-not-in-JSONL.** A buildability constraint, not a covenant
  change; the honesty content is unchanged, only its file location. No drift.

The Codex-lane folds are covenant-clean.

## Residual named (does not block)

The capsule-adjacent notice (§5) closes CC-A1 for a reader who receives the
`memory/successor_governance/` directory or an operator-helper export — both
carry the notice. A reader who extracts *only* `lineage_capsule.jsonl` in
isolation still sees raw, unannotated forged bytes. This residual is inherent to
a notice-beside-file approach; the airtight fix (an honesty line inside the
JSONL) is correctly deferred by v2 because it requires a `load_events_jsonl`
format migration. v2 mitigates it as far as Option B allows — the operator
helper packages the notice with the capsule in every export/archive/backup path
(`:204-205`), and round-2 RED test #7 verifies that packaging (`:359-361`).
Canonicalization should keep this residual in the named v1 limitations so it is
not silently treated as fully closed. It is a limitation to name, not a finding
to fold — consistent with how the spec already names its other v1 limitations.

## Verdict and what's next

**RATIFY closure** from the Claude covenant lane. v2 closes every first-pass
council finding, introduces no covenant drift, and is materially more honest and
more complete than v1 — the warning now travels with the capsule, and the
activation gate keys on an un-forgeable positive predicate. The covenant lane
clears v2 to proceed.

1. **Codex lane second-fold verification** (operator's lane) — the matching
   engineering closure check.
2. **Canonicalization** — amend the S6 spec, ADR 0038, and BAD Decision 33; keep
   the §5 copy-only-JSONL residual in the named v1 limitations.
3. **Cooling-off night.**
4. **Round-2 implementation** — RED-first, no cryptography; the `well_formed`
   rename, the honesty surfaces, the capsule-adjacent notice, and the
   always-false `event_has_verifying_authorship_attestation` predicate.
5. **Both-lane post-implementation review** — re-run the PATH 2 forge firsthand.
6. **Push** — `28da567` + round-2, only after both lanes ratify.

`28da567` stays unpushed. S6 remains blocked until the amendment is canonicalized
and round-2 lands.

*This verification is read-only. No code, spec, ADR, BAD, or non-slice docs were
changed in producing it. Closure was verified by reading v2 against the
first-pass findings firsthand, with v2 line citations.*
