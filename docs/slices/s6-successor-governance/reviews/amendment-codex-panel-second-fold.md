# Codex Engineering Lane — S6 Persisted-Authorship Amendment Diagnostic: Second-Fold Verification

**Subject:** `amendment-diagnostic-persisted-authorship.md` v2 (commit
`0f9e290`), folded against the first-pass Codex engineering panel
(`amendment-codex-panel.md`) and Claude covenant council
(`amendment-claude-council.md`).

**Ran:** 2026-05-16, read-only, after Claude covenant second-fold returned
RATIFY closure. This is the Codex engineering lane's second-fold verification
against the first-pass six-agent panel findings, not a new first-pass six-agent
panel.

**Verdict:** **RATIFY closure.** All eight first-pass Codex findings are closed
in v2. The folded diagnostic is buildable as a spec amendment path: it gives
canonicalization exact document scope, gives round-2 exact code/test surfaces,
and does not require a keyless authorship mechanism that cannot exist under the
sealed v1 Non-Goals. No engineering drift introduced.

---

## Closure Table

| Finding | First-pass requirement | v2 closure |
|---|---|---|
| F1 — capsule-local honesty surface | warning travels with estate-facing capsule; not prepended into JSONL | §5 requires a capsule-adjacent notice/manifest, keeps prose out of JSONL, requires helper/export packaging |
| F2 — positive event-level attestation predicate | no version/era gate; absence of verified attestation means non-authority | §7 D22 keys authority to the exact directive event carrying future verifying attestation |
| F3 — destructive authority vs consultable intent | hard-bar unattested dissolution; preserve genuine continuity intent for review | §7 splits destructive hard bar from consultable continuity-preserving recorded intent and names migration obligation |
| F4 — rename all success vocabulary | no stale `valid` mode or count field | §6 chooses `well_formed` / `well_formed_event_count` and lists code/test ripple |
| F5 — sidecar structural-only | green sidecar must not imply authenticity | §6 states sidecar cannot detect forged well-formed capsules |
| F6 — D6 snapshot conditional | do not claim health snapshot coverage unless implemented | §4 states snapshot continuity only when a validation snapshot is supplied |
| F7 — BAD Decision 33 scope | amend primary governance source too | §3 and §10 include BAD Decision 33 in canonicalization scope |
| F8 — delete/absence ambiguity | `no_capsule` is not proof no capsule ever existed | §8 gives `no_capsule` its own availability-only meaning |

## Engineering Verification

### F1 — Capsule-Local Honesty Surface

Closed. v2 §5 requires a mandatory capsule-adjacent human-readable notice or
manifest under `memory/successor_governance/`, with concrete candidate paths:
`lineage_capsule_NOTICE.txt` or `lineage_capsule_manifest.json`. It also states
the buildability constraint that prose must not be prepended to JSONL because
`load_events_jsonl` currently parses every nonblank line as a directive event.

The round-2 test contract includes a packaging test: the notice must be created
or preserved by the operator helper and packaged with the capsule in any future
export/archive path added in round-2. That is enough for round-2 to build
without inventing a file-format migration.

Residual, non-blocking: a reader who copies only `lineage_capsule.jsonl` still
misses the notice. v2 leaves the airtight in-file warning to a future loader
format migration; this is the correct engineering boundary.

### F2 — Positive Event-Level Attestation Predicate

Closed. v2 §7 removes the version/era gate and states that a directive event is
activation authority only if that exact event carries a verifying authorship
attestation produced by a future reviewed trust-source slice. It explicitly
rejects `schema_version`, era label, health mode, origin label, marker id,
statement hash, structural validation, and self-declared attestation fields as
authority.

The proposed code-facing shape is buildable: round-2 can add a predicate such as
`event_has_verifying_authorship_attestation(event)` that returns false for all
v1 persisted directive events. A future trust-source slice can later replace or
extend that predicate under review. The RED contract includes forged arbitrary
schema-label and self-declared-attestation probes.

### F3 — Destructive Authority and Consultable Intent Split

Closed. v2 §7 hard-bars unattested destructive or irreversible directives,
including `explicit_dissolution`, from activation authority. It also keeps
continuity-preserving directives consultable as recorded intent under future
human review rather than discarding them.

The migration obligation is stated explicitly: the future trust-source slice
must offer a re-attestation path for genuine v1 capsules. That makes the
engineering path honest: round-2 does not need to build migration now, but the
future slice cannot silently strand genuine user intent.

D10 is also conditioned in place: an unattested v1 directive cannot satisfy the
"valid explicit bonded-user fate directive wins" ordering and cannot suppress
Maez's preference seat.

### F4 — Success Vocabulary Rename

Closed. v2 §6 chooses `well_formed` and `well_formed_event_count`, avoiding the
`valid` substring entirely. It names the concrete round-2 blast radius:
`HEALTH_KEYS`, `ValidationReport`, health projection JSON, tests, sidecar
fixtures, examples, runbook text, and docs.

The RED contract requires stale `valid` mode or `valid_event_count` surfaces to
be visible. That is enough to prevent the old terminology from lingering under
a green test suite.

### F5 — Sidecar Structural-Only Semantics

Closed. v2 §6 states sidecar green means no structural invalidity,
reserved-scope leak, unavailable state, or public-state leak was observed. It
does not mean authenticity and cannot flag a forged but well-formed capsule.

That is the correct engineering posture. Round-2 should not invent an
authorship-aware sidecar gate without a trust source; it should make the current
sidecar semantics honest.

### F6 — Conditional D6 Snapshot Guarantee

Closed. v2 §4 states S6 can validate append-only continuity when supplied with
an operator-authenticated validation snapshot, and ordinary health must not
claim snapshot coverage unless round-2 wires snapshot loading into that path.

This matches the current code shape: `validate_capsule_events(..., snapshot=...)`
has the capability, while `/health.successor_governance` currently calls
validation without a snapshot. The diagnostic no longer overcommits health.

### F7 — BAD Decision 33 Canonicalization Scope

Closed. v2 §3 and §10 require canonicalization to amend the S6 spec, ADR 0038,
and BAD Decision 33. That is necessary because BAD Decision 33 currently carries
the primary overclaim future agents will grep first.

This is buildable as docs canonicalization work and does not require runtime
changes before cooling-off.

### F8 — Delete / Absence Ambiguity

Closed. v2 §8 defines `no_capsule` as "no capsule is available at this path now"
and explicitly rejects the stronger reading "the bonded user never authored a
capsule." It points future review to Decision-22 backups, validation snapshots,
and operator-held continuity records where available.

That is the correct engineering distinction. It prevents an availability state
from becoming false negative authorship evidence.

## Buildability Notes for Canonicalization and Round-2

- Canonicalization is docs-only but broad: `spec.md`, ADR 0038, and BAD Decision
  33 must all be amended together.
- Round-2 remains no-cryptography and no-new-trust-source. It implements honest
  surfaces, the `well_formed` rename, the capsule-adjacent notice, and the
  always-false v1 authorship-attestation predicate.
- The PATH 2 forged JSONL probe must become a RED-first regression and must be
  re-run firsthand during post-recovery review.
- The JSONL-only extraction residual must stay named as a v1 limitation during
  canonicalization; it is not solved by the notice-beside-file approach.

## Verdict

**RATIFY closure.** The v2 diagnostic closes the Codex first-pass engineering
findings and is ready for canonicalization, with the same condition the covenant
lane named: preserve the JSONL-only extraction residual as an explicit v1
limitation.

Next: canonicalize the amendment into the S6 spec, ADR 0038, and BAD Decision
33; then cooling-off night; then RED-first round-2 implementation.

`28da567` remains unpushed. S6 remains blocked until canonicalization and
round-2 implementation land and both lanes ratify the post-implementation
state.

*Read-only verification. No code, spec, ADR, BAD, or runtime data was changed in
producing this review artifact.*
