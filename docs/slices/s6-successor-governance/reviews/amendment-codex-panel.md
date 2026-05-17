# Codex Engineering Panel — S6 Persisted-Authorship Amendment Diagnostic

**Subject:** `amendment-diagnostic-persisted-authorship.md` (commit `4506241`),
reviewed after the Claude covenant council returned REVISE. Decision 33 /
ADR 0038.

**Panel ran:** 2026-05-16, read-only. Six engineering lenses reviewed the same
diagnostic: Dewey, Feynman, Locke, Descartes, Ohm, and Goodall. Four ran in fresh
agent slots; two reused available completed agent slots because the live agent
pool hit its thread limit. All six returned REVISE on the diagnostic as written
and ratified the Option-B honesty direction.

**Verdict:** **REVISE.** The diagnostic's direction is right: S6 v1 should say
that persisted capsules are structurally checked, not authorship-attested, and
future activation must be gated. But the current amendment diagnostic is not
ready to canonicalize. The fold must reach direct capsule readers, replace
version/era language with positive attestation presence, rename every
trust-sounding health field, and avoid overstating sidecar or snapshot coverage.

## Panel Findings

### F1 — capsule-local honesty surface is required

Codex ratifies CC-A1. The capsule is estate-facing; a future executor, lawyer,
maintainer, or successor may open `memory/successor_governance/lineage_capsule.jsonl`
directly and never see `/health`, the spec, or the runbook. A forged row with
`origin=bonded_user_manual` and `fate_directive=explicit_dissolution` remains
legible as a decedent-authored instruction unless the warning travels with the
artifact.

**Engineering fold requirement:** add a mandatory capsule-adjacent honesty
artifact in `memory/successor_governance/`, e.g. `lineage_capsule_NOTICE.txt` or
`lineage_capsule_manifest.json`, generated/preserved by the operator helper and
included with any future export/archive. Do **not** prepend prose into the JSONL
unless the file format and `load_events_jsonl` are explicitly migrated; today
every nonblank line is parsed as a `DirectiveEvent`.

The notice must be human-readable for estate/legal readers and say the same
load-bearing fact: S6 v1 validates grammar/structure, not human authorship; raw
JSONL without verified future attestation is not legal/estate activation
authority.

### F2 — D22 must be a positive event-level attestation predicate

Codex ratifies CC-A2. `schema_version` and "v1-era" labels are attacker-written
capsule bytes. A forger can stamp a forged capsule as a later version, or add a
self-declared attestation-looking field, then recompute the public hashes.

**Engineering fold requirement:** D22 must be phrased as a positive predicate on
the exact directive event being acted on:

```text
A directive event is activation authority only if that event carries a verifying
authorship attestation produced by a future trust-source slice.
```

Absence of a verifying attestation means non-authority regardless of
`schema_version`, health mode, era label, or a self-declared attestation field.
Future tests must prove forged self-consistent capsules, arbitrary schema
labels, and self-declared attestations remain non-authority.

### F3 — destructive authority and consultable intent must split

Codex ratifies CC-A5 and CC-A6. The current D22 wording bars all v1-era capsule
activation authority. That protects against forged dissolution but also strands
genuine continuity-preserving user intent. The fold must not solve forged
dissolution by throwing away the bonded user's real recorded wishes.

**Engineering fold requirement:** hard-bar unattested destructive or
irreversible directives, especially `explicit_dissolution`, from activation.
Continuity-preserving directives (`paradise_default`,
`suspended_pending_paradise`, `archival_preservation`, `new_bond_offer`) remain
consultable recorded intent under future re-review, but are not self-executing
activation authority without authorship attestation.

D22 must also govern D10's ordering: an unattested, merely structurally valid
directive cannot satisfy "valid explicit bonded-user fate directive" for
activation ordering and cannot suppress Maez's preference seat. Round-2 should
avoid ambiguous API names such as `validated_user_directive` for destructive
resolution; use `authorship_attested` wording or an explicit attestation object.

### F4 — rename all success vocabulary, not only `mode`

Codex ratifies CC-A3. The diagnostic renames `mode=valid` but leaves
`valid_event_count`. That field has the same false-authenticity smell and is in
the current health output.

**Engineering fold requirement:** rename success vocabulary consistently:

- health mode: prefer `well_formed` or another token without the substring
  `valid`; `structurally_valid` is acceptable if the covenant lane chooses it,
  but it still carries a residual substring risk;
- event count: rename `valid_event_count` to the matching structural token,
  e.g. `well_formed_event_count` or `structurally_valid_event_count`;
- update `HEALTH_KEYS`, `ValidationReport`, health JSON examples, tests, sidecar
  fixtures, runbook text, and any documentation samples together.

Round-2 should also make stale `mode == "valid"` visible in tests so an old
daemon cannot silently present the old token after the rename.

### F5 — sidecar is structural-only, not authorship-aware

Codex ratifies CC-A4. `scripts/observe_sidecar.py` red-gates missing,
unavailable, structurally invalid, invalid-count, reserved-scope, and public-leak
states. A forged but well-formed capsule has no invalid events and no sidecar red
gate. That is not a bug if stated honestly; it is a bug if the amendment implies
sidecar green means "safe" or "authentic."

**Engineering fold requirement:** the amendment must say that S6 sidecar green
means only "no structural invalidity observed." It does not detect forged
authorship. A future authorship-aware sidecar gate belongs to the future
trust-source slice, not S6 v1.

### F6 — D6 snapshot guarantee must be stated conditionally

Codex ratifies CC-A7 with a buildability correction. S6 has a snapshot-aware
validation capability when `validate_capsule_events(..., snapshot=...)` is
supplied. `/health.successor_governance` currently calls
`validate_capsule_events(events)` without a snapshot. The diagnostic should not
claim that ordinary health covers D6 snapshot continuity unless round-2 wires
snapshot loading into that path.

**Engineering fold requirement:** phrase the positive guarantee as:

```text
S6 can validate grammar, internal hash-chain structure, and append-only
continuity when supplied with an operator-authenticated validation snapshot.
```

If the canonical amendment says `/health` includes snapshot continuity, round-2
must implement snapshot loading there. Otherwise keep the claim conditional and
do not overclaim.

### F7 — BAD Decision 33 must be amended too

Goodall surfaced a document-scope issue: the diagnostic names spec and ADR 0038,
but `BETA_ARCHITECTURE_DECISIONS.md` is the authoritative governance law future
agents grep first. Decision 33 currently says "human-authored lineage capsule"
and describes a "human-origin-authored" record. Leaving BAD unchanged while
amending only the slice spec and ADR would preserve the overclaim in the primary
source.

**Engineering fold requirement:** canonicalization must amend Decision 33
alongside the S6 spec and ADR 0038, preserving the original record as an
amended/clarified limitation rather than silently rewriting the history.

### F8 — delete/absence ambiguity must be named

The same ordinary writer who can forge the capsule can delete it. That produces
`no_capsule`, which future readers might misread as "the bonded user never
authored paperwork." Over long horizons, disappearance is as important as
forgery.

**Engineering fold requirement:** widen the honesty text from write access to
write/delete access. Future activation/review must treat `no_capsule` as "no
available capsule," not proof that no capsule ever existed, and consult backups
or validation snapshots where available.

## Fold Checklist

The second-fold diagnostic must include:

- capsule-adjacent human-readable notice/manifest requirement;
- D22 as positive per-event verifying-attestation presence, independent of
  version labels;
- hard destructive bar for unattested `explicit_dissolution` and similar
  directives;
- continuity-preserving directives preserved as consultable recorded intent, not
  self-executing authority;
- D10/D9 amended in place so structural validation cannot suppress Maez's
  preference seat;
- complete success-vocabulary rename, including the event-count field;
- sidecar limitation stated as structural-only;
- D6 snapshot guarantee stated conditionally unless health is wired to snapshots;
- BAD Decision 33 added to canonicalization scope;
- write/delete ambiguity and `no_capsule` ambiguity named;
- round-2 tests that prove forged JSONL with arbitrary schema label and
  self-declared attestation is non-authority.

## Plain English

The amendment is pointing the right way, but the warning has to live with the
will, not just on the dashboard. Future code must not ask, "does this say v2?"
It must ask, "does this exact instruction carry a real future attestation?" And
the repair must not throw away the honest user's recorded wishes just because
forgeries exist. No proof, no killing; but the genuine record still matters.

*Read-only panel. No code, spec, or ADR edits were made by the role agents.*
