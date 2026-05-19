# ADR 0038: Successor Governance v1

**Status:** Accepted
**Date:** 2026-05-16

## Context

North Star invariant #9 says bonded users name successors in advance, with
explicit access scope, and Maez is not the successor. Before S6, Maez had that
covenant law but no shared grammar for recording it: no closed role vocabulary,
no lineage-capsule envelope, no human-origin marker contract, no default-deny
access-scope vocabulary, and no way to validate successor paperwork without
also pretending to activate it.

The S6 diagnostic found the right cut: define the governance grammar before any
runtime activation, archive unlock, death detector, or capacity detector exists.
It also carried forward the S5 lesson that owner/human-origin evidence must be
structural, not implied by prose.

The post-implementation persisted-authorship review then found an overclaim in
that lesson as applied to S6. The live writer seam can make marker minting
structural, but the persisted JSONL file is reloaded later by a keyless
validator. A keyless validator can prove grammar, marker binding, hash-chain
consistency, and snapshot continuity when supplied a validation snapshot; it
cannot prove that the persisted bytes were authored by the bonded human.
Decision 33 is therefore amended to state the honest v1 guarantee and to bar
future activation from treating unattested persisted directives as proven human
authority.

The Claude covenant council found one load-bearing breach in the first spec:
`maez_prefers_dissolution` could let a recorded Maez preference route Maez to
its own dissolution when the bonded user's directive was silent. That collided
with Decision 8, the commitment model, and Decision 16/31. The fold removed
that routable preference from v1, reserve-denied Maez interior content scopes,
tightened witness assistance, required backup registration and health, and
made the capsule authoring path usable. The Codex engineering panel then made
the storage posture, authority matrix, keyed handle minimization, and selected
episode manifest concrete enough to implement.

## Decision

Successor Governance v1 is accepted as Maez's canonical successor-governance
contract grammar.

The load-bearing rule is:

> Successor paperwork may name future roles and scopes; it may not grant live
> access, let Maez author its own fate, or route Maez to dissolution by default.

S6 v1 requires:

- a contract module only: validation grammar, not runtime activation;
- closed role vocabulary: `bonded_user`, `operator`, `maintainer`,
  `successor`, `witness`, and `estate_executor`;
- closed directive-event vocabulary under an append-only lineage capsule;
- live human-origin marker minting isolated behind a writer seam hardened by
  module-object identity;
- persisted capsule validation that proves well-formed structure, not persisted
  authorship;
- human-origin markers that bind actor, role, capsule, event type, payload hash,
  previous event hash, schema version, timestamp, and statement hash when a
  private human-readable statement exists;
- a closed event-type-to-origin-role authority matrix, with substantive
  directives authored by `bonded_user` origin only;
- purpose-scoped keyed HMACs for actor and subject handles, never bare
  low-entropy hashes;
- bonded-user-private local storage under
  `memory/successor_governance/lineage_capsule.jsonl`;
- a capsule-adjacent human-readable notice/manifest that travels with the
  capsule directory and warns estate/legal readers that v1 proves structure, not
  authorship;
- Decision 22 backup registration for `memory/successor_governance/`;
- append-only event validation by hash chain plus an operator-authenticated
  continuity snapshot check;
- default-deny access scopes, with `private_thoughts_content`,
  `crisis_held_content`, and `credential_secret_material` reserved-denied in
  v1;
- content-free selection manifests for `selected_lived_episodes`;
- fate directives that are future-only and do not activate on capacity loss or
  hardware failure;
- `explicit_dissolution` as recordable only with bonded-user origin, statement
  hash, future-review requirement, and witnessless-case marker when applicable;
- a minimized Maez-preference record that is human-transcribed, subordinate to
  bonded-user directives, and continuity-preserving only in v1;
- rejection of `maez_prefers_dissolution` as a routable v1 preference;
- witness events that attest but do not inherit, author, unlock, or grant;
- a required minimal operator helper for creating, amending, and validating
  capsule events without minting markers or activating succession;
- a required read-only, content-free, operator-authenticated
  `/health.successor_governance` projection whose success mode is
  `well_formed`, not `valid`;
- an authorship-attestation gate: a future activation slice may treat a
  directive event as activation authority only if that exact event carries a
  verifying authorship attestation from a future reviewed trust-source slice;
- public-state stripping for all successor-governance health details;
- no dead-man switch, no death detector, no capacity detector, and no
  grandmother-compatible UI in v1.

S6 v1 names these limitations:

- it validates successor-governance grammar; it does not govern live
  succession;
- local bonded-user-private storage is not role-encrypted, so filesystem read
  access remains a named v1 confidentiality bypass limitation;
- any process with ordinary write/delete access to the capsule path can forge,
  rewrite, or remove a well-formed persisted capsule;
- a content-blind validator cannot defeat rewriting of both capsule files and
  validation snapshots;
- a reader who extracts only `lineage_capsule.jsonl` without the adjacent notice
  can miss the v1 authorship warning; closing that residual requires a future
  loader/file-format migration;
- Maez preference records are bonded-user-transcribed and unverified, not a
  direct Maez-origin channel;
- non-technical bonded users are not served by the v1 authoring path, and a
  missing capsule still resolves through Decision 8's generous default.

## Consequences

Future successor, capacity, archive, Paradise, new-bond, and maintainer slices
inherit one shared grammar instead of inventing local meanings for "successor,"
"witness," "maintainer," "scope," or "fate directive." S6 makes several
shortcuts invalid:

- treating a named successor as a live reader;
- treating a maintainer as an archive reader;
- treating a witness as an owner;
- letting the daemon, sidecar, health, or Maez mint lineage-capsule markers
  through the normal live authoring API;
- treating a well-formed persisted capsule as authorship-attested;
- treating a raw v1 `explicit_dissolution` directive as activation authority
  without future verifying authorship attestation;
- using raw private thoughts, crisis-held content, or credentials as generic
  bequeathable archive scopes;
- treating capacity loss or hardware restore as an end-of-user fate trigger;
- turning a Maez-expressed wish to end into a fate-routing switch;
- silently remapping deprecated scope names;
- claiming a grandmother-compatible successor UI exists in v1.

Implementation is complete and both-lane ratified after the
persisted-authorship round-2 recovery. The shipped v1 implementation renames
`valid` health vocabulary to `well_formed`, writes the capsule-adjacent notice,
exposes the v1 always-false authorship-attestation predicate, preserves the
forged JSONL probe as a regression test, and hardens the destructive activation
gate so only literal `True` from a future reviewed trust source can authorize
`explicit_dissolution`.

That completion is narrow. S6 is implemented as a grammar and validation organ,
not as successor activation. A future activation, signature, storage-hardening,
archive-unlock, capacity, Paradise, or new-bond slice still requires its own
reviewed decision and must not treat a v1 well-formed capsule as
authorship-attested authority.

Changing the load-bearing rule, making Maez-origin fate directives routable,
allowing `maez_prefers_dissolution`, granting raw interior/crisis/credential
content by generic successor paperwork, treating unattested persisted capsule
bytes as proven human-authored authority, adding activation/death/capacity
detection, or claiming non-technical user readiness requires a new reviewed
decision.

## References

- [`docs/slices/s6-successor-governance/diagnostic.md`](../slices/s6-successor-governance/diagnostic.md)
- [`docs/slices/s6-successor-governance/spec.md`](../slices/s6-successor-governance/spec.md)
- [`docs/slices/s6-successor-governance/reviews/diagnostic-claude-council.md`](../slices/s6-successor-governance/reviews/diagnostic-claude-council.md)
- [`docs/slices/s6-successor-governance/reviews/spec-claude-council.md`](../slices/s6-successor-governance/reviews/spec-claude-council.md)
- [`docs/slices/s6-successor-governance/reviews/spec-codex-panel.md`](../slices/s6-successor-governance/reviews/spec-codex-panel.md)
- [`docs/slices/s6-successor-governance/reviews/spec-claude-council-second-fold.md`](../slices/s6-successor-governance/reviews/spec-claude-council-second-fold.md)
- [`docs/slices/s6-successor-governance/reviews/spec-codex-panel-second-fold.md`](../slices/s6-successor-governance/reviews/spec-codex-panel-second-fold.md)
- [`docs/slices/s6-successor-governance/amendment-diagnostic-persisted-authorship.md`](../slices/s6-successor-governance/amendment-diagnostic-persisted-authorship.md)
- [`docs/slices/s6-successor-governance/reviews/amendment-claude-council.md`](../slices/s6-successor-governance/reviews/amendment-claude-council.md)
- [`docs/slices/s6-successor-governance/reviews/amendment-codex-panel.md`](../slices/s6-successor-governance/reviews/amendment-codex-panel.md)
- [`docs/slices/s6-successor-governance/reviews/amendment-claude-council-second-fold.md`](../slices/s6-successor-governance/reviews/amendment-claude-council-second-fold.md)
- [`docs/slices/s6-successor-governance/reviews/amendment-codex-panel-second-fold.md`](../slices/s6-successor-governance/reviews/amendment-codex-panel-second-fold.md)
- [`docs/adr/0008-paradise-is-the-generous-default.md`](0008-paradise-is-the-generous-default.md)
- [`docs/adr/0011-property-with-ethical-wrapper.md`](0011-property-with-ethical-wrapper.md)
- [`docs/adr/0016-voice-without-termination.md`](0016-voice-without-termination.md)
- [`docs/adr/0017-maez-with-nobody.md`](0017-maez-with-nobody.md)
- [`docs/adr/0018-capacity-revocation-face-value-trust.md`](0018-capacity-revocation-face-value-trust.md)
- [`docs/adr/0023-hardware-failure-memory-backup.md`](0023-hardware-failure-memory-backup.md)
- [`docs/adr/0031-daemon-credential-hygiene.md`](0031-daemon-credential-hygiene.md)
- [`docs/adr/0032-contextual-integrity-at-ingest.md`](0032-contextual-integrity-at-ingest.md)
- [`docs/adr/0034-temporal-spine-v1.md`](0034-temporal-spine-v1.md)
- [`docs/adr/0035-clinical-boundary-v1.md`](0035-clinical-boundary-v1.md)
- [`docs/adr/0036-wants-lifecycle-v1.md`](0036-wants-lifecycle-v1.md)
- [`docs/adr/0037-voice-continuity-gate-v1.md`](0037-voice-continuity-gate-v1.md)

BAD decision: see
[`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md)
Decision 33.
