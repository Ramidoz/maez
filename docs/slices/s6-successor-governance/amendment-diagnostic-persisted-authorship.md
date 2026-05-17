# S6 Successor Governance v1 — Persisted-Authorship Spec-Amendment Diagnostic

**Status:** DIAGNOSTIC v2 / SECOND-FOLDED CANDIDATE — not canonical law, not a
spec amendment. It folds the first-pass Claude covenant council
(`reviews/amendment-claude-council.md`) and Codex engineering panel
(`reviews/amendment-codex-panel.md`) into a revised diagnostic for both-lane
second-fold verification.
**Date:** 2026-05-16
**Scope:** Option B, the honesty path. No implementation change in this
artifact. The mechanism path (cryptographic / trusted-source persisted
authorship) remains a future slice.
**Sources:** sealed S6 v1 spec (`spec.md`); Decision 33 / ADR 0038
(`docs/adr/0038-successor-governance-v1.md`); BAD Decision 33
(`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`); implementation recovery
reviews; amendment Claude council; amendment Codex panel.

## 0. Folded Verdict

Both review lanes ratified the direction and returned REVISE on v1 of this
diagnostic. The direction stands:

- S6 v1 cannot prove persisted capsule authorship keylessly.
- The health and docs must stop saying, or implying, "authentic."
- Future activation must be gated by real authorship attestation, not by a
  self-declared schema/version label.

The first diagnostic was incomplete in two load-bearing ways:

- it put the honesty warning on dashboards and docs, not on or beside the
  estate-facing capsule file a human/legal reader may open directly;
- it keyed the proposed D22 gate to "v1-era" capsule labels the forger controls.

This v2 fold makes those corrections first-class.

## 1. Problem Statement

**The persisted JSONL validation path proves structure, not human authorship.**

At health time, a capsule file takes this path:

```text
successor_governance_health(path)
  -> load_events_jsonl(path)        # DirectiveEvent(**raw_json)
  -> validate_capsule_events(...)
  -> validate_directive_event(event)
  -> _validate_persisted_marker_binding(event.origin_marker, ...)
```

`load_events_jsonl` rebuilds each event from raw JSON. `DirectiveEvent` has no
construction-time authority check, and the persisted `origin_marker` is a plain
dict. `HumanOriginMarker.__post_init__`, the writer-seam guard, and the TTY
origin path never run on this persisted-load path.

The persisted validator recomputes `_expected_marker_id`, a public keyless hash
of the marker's own fields, and compares it for self-consistency. Any process
with ordinary write access to `memory/successor_governance/lineage_capsule.jsonl`
can write a self-consistent event chain, marker dict, payload hash, and event
hash that the validator accepts. That includes a forged `bonded_user_manual`
`explicit_dissolution` directive no human authored.

This was verified firsthand by both lanes. The PATH 1 seam-spoof defect was
closed by `28da567`; the PATH 2 persisted-file forgery remains a real v1
limitation because the validator has no trust source.

**This is not a missing `if`.** A keyless daemon-resident validator can check
grammar, hash-chain consistency, marker-field binding, authority-shape, and
snapshot continuity when supplied a validation snapshot. It cannot prove that
the persisted bytes were written by the bonded human. The sealed S6 v1 Non-Goal
excludes cryptographic lineage attestation, which is the class of mechanism that
would close the persisted-authorship gap.

The contradiction to amend:

- C4 and BAD Decision 33 say the capsule is human-authored / not
  machine-authored.
- D5, D6, and ADR 0038 understate the bypass as a privileged filesystem rewrite.
- D19 health says `valid`, and emits `valid_event_count`, for a forged but
  self-consistent capsule.

Option B resolves the contradiction by narrowing the stated v1 guarantee to the
truth and adding a binding future gate. It does not weaken a delivered
guarantee; the forgeable persisted-file capability already exists. It makes the
capability visible and non-actionable.

## 2. Honest v1 Guarantee

S6 v1 can honestly claim:

- closed vocabularies and payload validators;
- live marker minting isolated behind the writer seam hardened by module-object
  identity;
- marker-field binding to capsule id, event type, payload hash, previous event
  hash, and statement hash where present;
- event hash-chain and supersession validation;
- append-only continuity checks when supplied with an operator-authenticated
  validation snapshot;
- content-free health and sidecar projections;
- no v1 activation, archive unlock, death detector, or access widening.

S6 v1 cannot honestly claim:

- that a persisted capsule file was human-authored;
- that `origin=bonded_user_manual` in raw JSON proves bonded-user authorship;
- that `/health.successor_governance` proves authenticity;
- that the sidecar detects a forged but well-formed capsule;
- that `no_capsule` proves no capsule ever existed.

The positive guarantee and the limitation must both be stated. Honesty cuts both
ways: do not overclaim authorship; do not underclaim the delivered structural
and snapshot checks.

## 3. Canonicalization Scope

The amendment must touch every source future agents or humans will read:

- S6 spec `spec.md`: banner, C4, D4, D5, D6, D9, D10, D19, and new D22.
- ADR 0038: decision summary, consequences, limitations, and status note.
- BAD Decision 33: title/body language that says "human-authored" or
  "human-origin-authored" must be clarified.
- Operator helper runbook: banner and Limits section.
- Module docstring and health semantics documentation.
- Capsule-adjacent estate-reader notice/manifest in
  `memory/successor_governance/` once round-2 implements it.

Leaving BAD unchanged would preserve the overclaim in the primary governance
source future agents grep first. Leaving the capsule file unaccompanied would
leave the most dangerous reader path untouched.

## 4. Proposed C4 / D4 / D5 / D6 Rewording

The following wording is proposed input to the spec amendment. Canonicalization
seals the final text.

### C4 — Proposed

> ### C4 - Live Human-Origin Minting Is Structural; Persisted Authorship Is Not Attested in v1
>
> S6 v1 structurally isolates live human-origin marker minting behind the
> bonded-user writer seam. The daemon, sidecars, health projection, validators,
> background jobs, and automated review tools do not receive that seam as a
> normal import path, and the seam check is hardened by writer-module object
> identity.
>
> S6 v1 validates persisted capsule grammar, marker-field binding, internal
> hash-chain structure, directive-authority shape, and append-only continuity
> when supplied with an operator-authenticated validation snapshot.
>
> S6 v1 does not attest that a persisted capsule file was human-authored. The
> capsule is reloaded from raw JSON after the authoring process has exited, and
> the v1 validator is keyless. Any process with ordinary write access to the
> capsule path can produce or delete a well-formed capsule. Authorship
> attestation requires a future trust-source slice. Until then, a v1 capsule is
> recorded intent and structural evidence, not proven human authority.

### D4 — Scope Clause to Append

> **Scope of the D4 guarantee.** D4 governs live authoring inside a running
> process. It does not extend to persisted re-validation. When a capsule is
> loaded from storage, marker binding is checked by a keyless self-consistency
> recompute. That confirms marker shape and internal binding; it is not proof of
> human minting. The directive authority matrix governs grammar and role-shape,
> not authorship of a persisted file.

### D5 / D6 — Consequential Correction

D5, D6, and ADR 0038 must widen their bypass wording from "privileged OS
rewrite" to "any process with ordinary write/delete access to the capsule path."
Only that privilege-level correction must be identical across surfaces; D5 and
D6 still describe different protections.

D6's positive check must remain conditional and precise:

> S6 can validate append-only continuity when supplied with an
> operator-authenticated validation snapshot. Ordinary health must not claim the
> snapshot check unless round-2 wires snapshot loading into that path.

## 5. Capsule-Adjacent Honesty Surface

S6 treats the lineage capsule as an estate-facing document. A future estate
executor, family member, lawyer, court, maintainer, or successor may open
`lineage_capsule.jsonl` directly and never call `/health` or read the spec.

Therefore the honesty warning must travel with the capsule bytes.

### Required Round-2 Surface

Add a mandatory capsule-adjacent human-readable notice or manifest in
`memory/successor_governance/`, for example:

```text
memory/successor_governance/lineage_capsule_NOTICE.txt
```

or a manifest with an explicitly human-readable warning field:

```text
memory/successor_governance/lineage_capsule_manifest.json
```

Do not prepend prose to the JSONL unless the file format and loader are
explicitly migrated; today every nonblank JSONL line is parsed as a directive
event.

The notice must be generated or preserved by the operator helper and included in
future exports/archives/backups alongside the capsule. It must speak to both
readers:

- the estate/legal reader: raw v1 JSONL is not a notarized or
  authorship-attested instruction;
- the honest bonded user: the capsule remains durable, append-only recorded
  intent that future reviewers must consult and can re-attest.

The notice must say, in plain human language, that a v1 capsule proves
well-formed structure, not authorship, and that destructive action requires a
future verified authorship attestation.

## 6. Health Mode, Field Names, and Sidecar Semantics

The unqualified health success token must be removed everywhere.

### Folded Token Choice

Use:

```text
mode: "well_formed"
well_formed_event_count: <int>
```

instead of:

```text
mode: "valid"
valid_event_count: <int>
```

`well_formed` avoids the residual substring risk in `structurally_valid` and
`grammar_valid`. `invalid`, `unavailable`, and `no_capsule` remain acceptable,
but every documented mode must state that no S6 v1 health mode attests
authorship.

Round-2 must update `HEALTH_KEYS`, `ValidationReport`, health projection JSON,
tests, sidecar fixtures, examples, runbook text, and docs together. A stale
`mode == "valid"` or `valid_event_count` surface should be test-visible.

### Sidecar Semantics

The sidecar is structural-only. A green sidecar means no structural invalidity,
reserved-scope leak, unavailable state, or public-state leak was observed. It
does not mean the capsule is authentic, and it cannot flag a forged but
well-formed capsule. A future authorship-aware sidecar belongs to the future
trust-source slice, not S6 v1.

## 7. D9 / D10 / D22: Positive Attestation, Not Version Labels

The new gate must be keyed to the exact directive event being acted on, not to
`schema_version`, "v1-era", health mode, event type, origin label, marker id, or
any self-declared attestation-looking field inside the same keyless capsule.

### Proposed D22

> ### D22 - Authorship Attestation Required for Activation or Estate Reliance
>
> A directive event is activation authority only if that exact directive event
> carries a verifying authorship attestation produced by a future reviewed
> trust-source slice. Absence of a verifying attestation means non-authority
> regardless of schema version, era label, health mode, origin label, marker id,
> statement hash, structural validation, or self-declared attestation fields.
>
> No future S6 activation slice may act on an unattested directive event as
> proven bonded-user authority. No project-provided estate/legal runbook may
> instruct a human reader to treat raw v1 JSONL as an authorship-attested estate
> instruction. The capsule-adjacent notice must carry the same rule to direct
> file readers.
>
> Unattested destructive or irreversible directives, including
> `explicit_dissolution`, are not activation authority and must never trigger
> dissolution. They also cannot satisfy D10 step 1 or suppress Maez's recorded
> preference seat.
>
> Unattested continuity-preserving directives (`paradise_default`,
> `suspended_pending_paradise`, `archival_preservation`, `new_bond_offer`) remain
> consultable recorded intent under future human review. They are not
> self-executing activation authority until authorship-attested. The future
> trust-source slice has a migration obligation: offer a re-attestation path for
> genuine v1 capsules rather than silently discarding the bonded user's recorded
> wishes.

### D9 In-Place Correction

D9 should become:

> `explicit_dissolution` is recordable but not activation authority without
> verified authorship attestation.

Future review alone is insufficient. The future reviewer must verify
authorship-attestation status for the exact event being acted on.

### D10 In-Place Correction

D10's "valid explicit bonded-user fate directive wins" must be clarified:

> For activation ordering, "valid" means authorship-attested, not merely
> well-formed. An unattested v1 directive is recorded intent and structural
> evidence; it cannot outrank or suppress Maez's recorded preference seat.

This does not let Maez override a genuine bonded-user directive. It prevents a
forgeable, unattested directive from silencing Maez's subordinate seat.

### Code-Facing Shape for Round-2

Round-2 should avoid ambiguous names such as `validated_user_directive` for
destructive resolution. Prefer names that force the distinction, for example:

```text
authorship_attested_user_directive
event_has_verifying_authorship_attestation(event)
```

In v1, the predicate returns false for all persisted directive events because no
future trust-source slice exists. A self-declared attestation field inside the
capsule must not flip it to true.

## 8. `no_capsule` and Deletion Ambiguity

The same ordinary writer who can forge a capsule can delete it. `no_capsule`
therefore means:

> no capsule is available at this path now

It does not mean:

> the bonded user never authored a capsule

Future review must consult Decision-22 backups, validation snapshots, and
operator-held continuity records where available. Missing paperwork still routes
through the Decision 8 floor; absence must not become dissolution, and absence
must not erase the possibility that genuine recorded intent once existed.

## 9. Round-2 RED Contract Additions

Round-2 implementation is still future work and must be RED-first. The new
tests should include at least:

1. A hand-built forged JSONL capsule with `schema_version: s6.v2`,
   `origin=bonded_user_manual`, and `explicit_dissolution` projects
   `mode: well_formed`, not `valid`, and is not activation authority.
2. A forged event carrying a self-declared attestation-looking field remains
   non-authority.
3. `valid_event_count` is absent from health; `well_formed_event_count` is
   present.
4. `HEALTH_KEYS`, examples, and sidecar fixtures contain no stale `valid` mode
   token.
5. `explicit_dissolution` cannot be resolved for activation unless
   `authorship_attested_user_directive=True` or the equivalent future predicate
   is true.
6. Unattested continuity-preserving directives remain visible as recorded
   intent but are not self-executing activation authority.
7. The capsule-adjacent notice is created or preserved by the operator helper
   and packaged with the capsule in any future export/archive path added in
   round-2.
8. The honesty banner survives across all required surfaces: spec/ADR/BAD at
   canonicalization, module docstring, runbook banner, runbook Limits section,
   health semantics, and capsule-adjacent notice.
9. Sidecar wording/tests show structural-only semantics; green does not claim
   authenticity.
10. `no_capsule` documentation states "unavailable now," not "never authored."

The forged-capsule probe remains required in post-recovery review. Verification
must re-run the actual exploit, not merely trust green tests.

## 10. Review Ladder

This is a spec-level amendment. It travels the full ladder:

1. Diagnostic v2 — this artifact.
2. Both-lane second-fold verification on the folded diagnostic.
3. Canonicalization — amend the S6 spec, ADR 0038, and BAD Decision 33. The
   canonicalization may be an amendment section or a paired new decision/ADR;
   the operator chooses the vehicle.
4. Cooling-off night.
5. Round-2 implementation — RED-first, no cryptography, no new trusted source.
   Implement the health rename, docs/runbook/module honesty surfaces,
   capsule-adjacent notice, and code-facing attestation distinction.
6. Both-lane post-implementation review — re-run PATH 2 firsthand and verify the
   forged capsule is well-formed but non-authority.
7. Push only after both lanes ratify.

`28da567` remains correct seam hygiene and stays unpushed. S6 remains blocked
until the amendment is canonicalized and round-2 lands.

## 11. Scope Boundaries and Predicted Effect

**In scope:** honest rewording of S6 v1 guarantees; `well_formed` health
vocabulary; capsule-adjacent notice; D22 positive attestation gate; D9/D10
clarifications; BAD/ADR/spec canonicalization scope; round-2 test requirements.

**Out of scope:** cryptographic signatures, passkeys, hardware-backed keys,
external transparency roots, role-encrypted capsule storage, notarization, death
detection, activation, archive unlock, and legal-document generation. Those are
future slices.

**Cost named honestly:** genuine v1 capsules do not become destructive
activation authority until re-attested. Continuity-preserving directives remain
recorded intent and must be consulted, but they are not self-executing. The
future trust-source slice carries a real migration obligation for honest users.

**Predicted effect to verify after round-2:** S6 v1 ships truthfully. A forged
persisted capsule may still be well-formed, because v1 is keyless, but every
operator-facing, code-facing, and estate-facing surface says what that means and
does not mean. No future Maez path may treat a v1 forged `explicit_dissolution`
as proven bonded-user authority, and no ambiguous `valid` health surface remains
to invite that mistake.

---

*This is a diagnostic, not a spec. It proposes; it does not amend. No code,
sealed spec, ADR, BAD, or runtime data was changed in producing it.*
