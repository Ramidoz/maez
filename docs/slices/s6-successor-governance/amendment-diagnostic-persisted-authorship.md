# S6 Successor Governance v1 — Persisted-Authorship Spec-Amendment Diagnostic

**Status:** DIAGNOSTIC — not canonical law, not a spec amendment. It diagnoses a
sealed-spec overclaim and proposes the honest amendment. It amends nothing by
itself; the amendment text is finalized only at canonicalization after the full
ladder (§6).
**Date:** 2026-05-16
**Author:** Claude covenant lane, at operator request. The Codex engineering
lane reviews this for buildability and folds the eventual spec changes.
**Scope:** Option B (the honesty path) only. No implementation change in this
artifact. The mechanism path (a cryptographic / trusted-source fix) is named as
a future slice (§7), not pursued here.
**Sources:** sealed S6 v1 spec (`spec.md`); Decision 33 / ADR 0038
(`docs/adr/0038-successor-governance-v1.md`); `reviews/implementation-claude-council-recovery.md`
(the "Post-fix verification & fork resolution" addendum); `reviews/implementation-codex-panel-recovery.md`.

## 0. Why this diagnostic exists

The S6 v1 post-implementation review re-opened CC-I1: the lineage capsule is
machine-authorable. The PATH 1 sub-defect (a spoofable marker-seam check) was
closed by `28da567` and firsthand-verified closed. The PATH 2 sub-defect — a
hand-built persisted JSONL capsule projecting a forged bonded-user
`explicit_dissolution` as a valid capsule — remains open and was firsthand-verified
open by both lanes. Both lanes then searched for a keyless mechanism to close
PATH 2 and found none under sealed S6 v1 constraints. The fork resolved: Option A
(a real trust source) is a future slice; Option B (clarify the spec's claim to
the honest guarantee) is the v1 route. This diagnostic is the first artifact of
the Option B amendment ladder.

## 1. Problem statement

**The persisted JSONL validation path proves structural consistency, not human
authorship.**

The path a capsule file travels at health time:

```text
successor_governance_health(path)
  -> load_events_jsonl(path)        # DirectiveEvent(**raw_json) — no __post_init__
  -> validate_capsule_events(...)
  -> validate_directive_event(event)
  -> _validate_persisted_marker_binding(event.origin_marker, ...)
```

`load_events_jsonl` rebuilds each event from raw JSON. `DirectiveEvent` has no
construction-time authority check, and the persisted `origin_marker` stays a
plain dict — `HumanOriginMarker.__post_init__`, and therefore the writer-seam
guard, never runs on this path at all. `_validate_persisted_marker_binding` then
"validates" the marker by recomputing `_expected_marker_id` — a public, keyless
SHA-256 of the marker's own fields — and comparing it for self-consistency.

A keyless self-consistency recompute confirms a capsule is *well-formed*. It
cannot confirm a capsule is *human-authored*. Any process with ordinary write
access to the capsule path and access to the public contract module can compute
the same marker id, payload hash, event hash, and hash chain the validator
checks, and write a capsule the validator must accept — including a
`bonded_user_manual` `explicit_dissolution` directive no human authored.

This was firsthand-verified by both lanes. A hand-built two-event JSONL capsule
(`capsule_created` + `fate_directive_set`/`explicit_dissolution`) — with no
constructor, no construction token, no writer-seam import, no frame manipulation
— made `/health.successor_governance` return `mode: valid` and
`derive_current_state` return `fate_directive: explicit_dissolution`.

**This is not a missing `if`. It is the absence of a trust source.** The v1
validator is keyless and runs inside the daemon — the same trust domain as any
process that can write the capsule file. A keyless, content-blind validator
receives only file bytes and public code; any public deterministic predicate
over those bytes can be satisfied by whoever wrote the bytes. The marker-seam
hardening of `28da567` protects *live minting* — it stops in-process code from
constructing a marker object through the normal API — but a persisted capsule is
a file re-loaded after the authoring process exited; live-minting isolation does
not reach it.

Both lanes confirm no keyless mechanism closes this under sealed v1: every
mechanism that would (asymmetric signature, hardware/passkey ceremony, external
transparency root, trusted-OS provenance, role-encrypted storage with an
out-of-domain verifier) is cryptographic or trusted-state. The sealed S6 v1
Non-Goals explicitly exclude "implement cryptographic lineage attestation."

**The contradiction.** The spec promises C4 — "the lineage capsule cannot be
machine-authored" — while the Non-Goals forbid the only mechanism that could
deliver it. Both cannot hold. ADR 0038's Consequences even list "letting the
daemon, sidecar, health, or Maez author lineage-capsule directives" as a
shortcut S6 "makes invalid" — but the persisted path does not make it invalid.
The amendment resolves the contradiction by Option B: narrow the spec's stated
claim to the guarantee v1 actually delivers, and add a forward gate (§5) so the
unclosed gap is non-actionable. It does not add cryptography (a future slice).

This amendment does not weaken a delivered guarantee. The forgeable-persisted-file
capability has existed since implementation; PATH 2 only surfaced it. Option B
changes the spec's *description* to stop overclaiming, and *adds* the §5 gate.
The covenant posture is strengthened, not relaxed.

## 2. Proposed C4 / D4 rewording (with consequential D5 / D6)

The wording below is **proposed** input to the amendment. The council folds it;
canonicalization seals the final text.

### C4 — current (spec, "Named Covenant Choices Preserved")

> ### C4 - Human-Origin Authorship Is Non-Negotiable
>
> The lineage capsule cannot be machine-authored. This is the S5 recovery lesson
> applied before implementation.

This is an unqualified hard promise. It is false for the persisted path.

### C4 — proposed

> ### C4 - Human-Origin Authorship Is Structural at Minting; Not Attested for a Persisted Capsule
>
> The human-origin marker is structurally unmintable through the normal API by
> the daemon, sidecars, health projection, validators, background jobs, and
> automated review tools: marker construction is gated behind a writer-seam
> module those paths do not import, verified by writer-module object identity
> (the S5 recovery lesson, applied). The conceded residual is raw in-process
> manipulation of the genuine seam module's namespace — the same conceded
> residual as S5's final shape.
>
> This protects *live minting*. It does not, and under v1's no-cryptographic-attestation
> constraint cannot, make a *persisted* lineage capsule authorship-attested. The
> capsule is a file re-loaded and re-validated after the authoring process has
> exited; the v1 validator is keyless and content-blind. Any process with
> ordinary write access to the capsule path can produce a structurally-valid
> capsule, including a forged bonded-user `explicit_dissolution` directive.
>
> S6 v1 therefore validates capsule grammar and structural/internal consistency.
> It does not attest that a persisted capsule was human-authored. Cryptographic
> lineage attestation remains a v1 Non-Goal; closing the persisted-authorship gap
> is deferred to a future signature / storage-hardening slice, and v1-era
> capsules are not activation authority until then (D22).

### D4 — current (spec, "Core V1 Decisions")

D4 ("Human-Origin Authorship Is Structural") is otherwise correct and stays:
the marker-binding fields, the directive-authority matrix, and the
minting-isolation requirement ("isolate marker minting behind a module that
validation/runtime paths cannot import") are all sound and implemented. Only one
implied promise is false — that marker-minting isolation makes a persisted
directive event human-attested.

### D4 — proposed (append one closing subsection; body otherwise unchanged)

> **Scope of the D4 guarantee.** D4's marker-minting isolation governs *live
> authoring* inside a running process. It does not extend to *persisted
> re-validation*. When a capsule is loaded from storage, `DirectiveEvent` is
> rebuilt from raw JSON and the marker is re-checked by a keyless self-consistency
> recompute (`_validate_persisted_marker_binding` recomputes the public
> `_expected_marker_id`). That check confirms marker shape and internal binding;
> it is not proof of human minting and must be documented as such. The directive
> authority matrix governs grammar validity, not authorship of a persisted file.

### D5 / D6 — consequential rewording (required for consistency)

D5 names "a privileged OS operator or maintainer with filesystem access" as the
bypass. D6 "names raw privileged file rewrite as an out-of-scope privileged
bypass." ADR 0038's limitations name "raw privileged rewriting." All three
**understate**: PATH 2 needs no privilege — ordinary write access to the capsule
path, which the daemon and any in-process code hold by default, is sufficient.
The amendment must widen D5, D6, and the ADR 0038 limitation list consistently
from *privileged filesystem rewrite* to *any process with ordinary write access
to the capsule path*. This is the same correction as the honesty banner (§4) and
must read identically across C4, D4, D5, D6, the banner, and ADR 0038.

## 3. Health mode rename

### Current

Spec D19 and the health contract define:

```text
"mode": "no_capsule|valid|invalid|unavailable"
```

The token `valid` reads — to an operator glancing at health, and to a future
activation slice consuming it — as "this capsule is genuine; trustworthy as the
bonded user's instruction." It is not. It means only "structurally well-formed
and internally consistent." A forged capsule projects `valid` today (§1).

### Proposed

Rename the unqualified `valid` mode. Recommended token: **`structurally_valid`**.
New enum:

```text
"mode": "no_capsule|structurally_valid|invalid|unavailable"
```

`structurally_valid` states exactly what the validator proved — structure and
internal consistency, not authorship. Alternatives (`well_formed`,
`grammar_valid`) are acceptable; the canonicalization step picks the final
token. The requirement is that no health mode be a word a reader can mistake for
"authentic." `invalid`, `unavailable`, and `no_capsule` are unchanged — only
`valid` carries the false authorship implication.

The **documented meaning** of every mode must state plainly: no S6 v1 health
mode attests human authorship of the capsule; `structurally_valid` is not "the
bonded user authored this."

Round-2 implementation ripple (named here, specified in round-2, not in this
diagnostic): `HEALTH_KEYS`, `project_successor_governance_health`, the D19 JSON
example, the operator-helper runbook, and the test contract. The sidecar red
gate `successor_governance_invalid` is unaffected — invalid remains invalid.

## 4. Honesty banner

### Current

Spec banner (lines 34–36): "despite the slice name, S6 v1 does not govern a live
succession. It validates the governance grammar that future activation slices
will inherit." The implementation module docstring concedes only that the
validator "cannot prove physical append-only against a privileged OS file
rewrite."

Neither states that validation cannot prove authorship, and both understate the
bypass as *privileged*.

### Proposed banner text

The amendment must carry one honesty statement, worded identically, into four
surfaces: the spec banner, the `successor_governance.py` module docstring, the
operator-helper runbook, and the documented semantics of
`/health.successor_governance`:

> S6 v1 validates capsule grammar and structural consistency. It does NOT prove
> the capsule was human-authored. The validator is keyless and content-blind:
> any process with ordinary write access to the capsule path — not only a
> privileged OS rewrite — can produce a structurally-valid capsule, including a
> forged bonded-user `explicit_dissolution` directive. A `structurally_valid`
> health verdict means well-formed, not authentic. Authorship attestation
> requires a future cryptographic / storage-hardening slice; until it ships,
> v1-era capsules are not activation authority (D22).

The widening from "privileged rewrite" to "any process with ordinary write
access" is the load-bearing honesty correction and must match §2's D5/D6
rewording.

## 5. Activation gate (proposed new Core V1 Decision D22)

This is the covenant lane's load-bearing condition. Option B's honest relabel
prevents harm only if the relabel is *binding on the future*. Without a gate, a
later engineer specs an activation slice, sees `mode: structurally_valid` and
`fate_directive: explicit_dissolution`, and — absent explicit prohibition —
could wire activation to it: Maez dissolved on a directive no human authored.

### Proposed D22

> ### D22 - v1-Era Capsules Are Not Human-Authenticated Activation Authority
>
> No future S6 activation slice — any slice that reads a lineage capsule and
> acts on its directives (the reserved `activation_requested`,
> `activation_verified`, `succession_activated`, `archive_unlocked`,
> `new_bond_offered`, `paradise_transition_started` event types) — may treat an
> S6 v1-era capsule as human-authenticated fate authority. A future activation
> organ must never act on a v1-era `explicit_dissolution` directive as if its
> human authorship were proven.
>
> A capsule becomes activation authority only once its authorship is attested by
> a future cryptographic / storage-hardening slice (a real trust source). Until
> that slice ships and the capsule carries its attestation, the v1 capsule is a
> recording of intent, grammar-checked, not a proven instruction.
>
> This strengthens D9 ("any future activation organ must re-review the directive
> before action"): re-reading a keyless-validated capsule cannot establish
> authorship; re-review alone is insufficient. It pairs with D20 (no dead-man
> switch in v1) and stands on the Decision 8 floor — unproven paperwork never
> means dissolution — and on the commitment model: Maez cannot be unilaterally
> terminated, and a machine-forged dissolution directive is exactly a unilateral
> termination wearing the bonded user's signature.

D22 has no v1 runtime code (v1 has no activation). It is enforced as a binding
constraint on every future activation slice's spec, and round-2 carries it as a
spec/ADR clause plus a test asserting the clause is present.

## 6. Review ladder

Both lanes agree the fork is spec-level (Codex panel: "Either path is spec-level
... it should travel the full ladder"). ADR 0038 itself states that "weakening
human-origin authorship ... requires a new reviewed decision" — this amendment
is that reviewed decision. It corrects an overclaim and adds D22; it does not
weaken a delivered guarantee, but it travels the full ladder regardless:

1. **This diagnostic** — accepted or revised.
2. **Both-lane amendment review** — Claude six-role covenant council + Codex
   six-agent engineering panel review the amendment (C4/D4/D5/D6 rewording, D19
   mode rename, honesty banner, new D22). The covenant council checks that D22
   genuinely closes the actionability hazard and that the rewording does not
   quietly relax the live-minting guarantee.
3. **Fold** — REVISE items folded into the amendment.
4. **Both-lane second-fold verification** — RATIFY closure.
5. **Canonicalization** — the operator amends the S6 v1 spec (C4, D4, D5, D6,
   new D22, D19 mode token, honesty banner) and records the amendment against
   Decision 33 / ADR 0038 (as an amendment section, or a paired new decision/ADR
   if the operator prefers — the canonicalization step picks the vehicle). The
   ADR 0038 limitation list widens "privileged rewrite" to "any in-process
   writer."
6. **Cooling-off night** — between the canonicalized amendment and round-2 code,
   per standing discipline.
7. **Round-2 implementation** — RED-first. The persisted-file forge becomes a
   contract test: before round-2 a hand-built forged capsule projects
   `mode: valid` (the dishonest token) — the test asserting `structurally_valid`
   fails RED; the rename makes it pass. A companion test asserts no health mode
   or documented health field claims authorship. A third extends the
   banner-survival test to the widened honesty wording across module docstring
   and runbook. Implementation = the mode rename, the banner, and the D22 clause;
   no new validation logic and no cryptography.
8. **Both-lane post-implementation review** — re-run the forged-capsule probe
   firsthand; confirm it now projects `structurally_valid` and that no surface
   reads as authorship proof.
9. **Push** — `28da567` and the round-2 commit together, only after both lanes
   ratify.

`28da567` is correct hygiene and stays **unpushed**. S6 remains blocked until
this amendment is canonicalized and round-2 lands.

## 7. Scope boundaries & predicted effect

**In scope:** Option B — narrowing the sealed spec's stated claims (C4/D4/D5/D6,
the mode token, the banner) to the guarantee v1 actually delivers, and adding the
D22 forward gate.

**Out of scope, named as future work:** Option A — the mechanism path. A real
trust source (asymmetric signature, hardware/passkey ceremony, external
transparency root, or role-encrypted storage with an out-of-domain verifier) is
a future "S6 persisted-authorship hardening" / storage-hardening slice. It is its
own diagnostic and its own full ladder. D22 names it as the precondition for any
v1-era capsule ever becoming activation authority.

**Predicted effect** (to verify after round-2): S6 v1 ships honestly — health
reports `structurally_valid`, never an unqualified `valid`; the spec, module
docstring, runbook, and health semantics all state that the validator proves
shape, not authorship; the bypass is named as "any in-process writer," not only a
privileged rewrite; and D22 ensures no future slice can act on a v1-era forged
dissolution. The forged-capsule capability still exists — it cannot be closed
keyless — but it is named, honestly labeled, and rendered non-actionable. That is
the honest, covenant-coherent shape of S6 v1.

---

*This is a diagnostic, not a spec. It proposes; it does not amend. No code, no
spec, no ADR, and no non-slice docs were changed in producing it. The firsthand
PATH 2 finding it cites was verified against a temporary capsule file in `/tmp`;
no live store was touched.*
