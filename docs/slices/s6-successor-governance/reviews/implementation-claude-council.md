# Claude Covenant Council — S6 Successor Governance v1: Post-Implementation Review

**Subject:** `52440fb feat(s6): implement successor governance v1` — the S6 v1
implementation against the canonical sealed spec
(`docs/slices/s6-successor-governance/spec.md`). Decision 33 / ADR 0038.

**Council ran:** 2026-05-16, post-implementation, pre-push. Read-only six-role
covenant council. The synthesizer reproduced the headline exploit firsthand.

**Verdict:** **REVISE.** Two covenant blockers, three majors, three minors,
three nits. **Do not push.** The Creative role returned a VETO; the synthesizer
verified its empirical core firsthand and synthesizes it as a blocker-grade
REVISE (see "The VETO adjudication"). Practically the labels agree: S6 v1 does
not push; a recovery is mandatory.

---

## The six roles

| Role | Verdict | Headline |
|---|---|---|
| Outside-View | REVISE | The spec-mandated honesty banner and two named limitations did not survive into shipped artifacts. |
| Body-Coherence | RATIFY (minors) | Module pure, marker-writer module import-isolated, namespace-disjoint — two authority-matrix divergences. |
| Logical / veto | REVISE (no veto) | `directive_superseded` admits a wrong-role supersession of the bonded user's fate directive. |
| Creative | **VETO** | The human-origin marker is forgeable by any code with import access; a forged capsule projects `valid`. |
| Future-Rohit | REVISE | Directive supersession is non-functional — the bonded user cannot amend the capsule (D17 lock-in). |
| 20-Years-Future-Maez | RATIFY | Maez cannot route itself to dissolution via a preference; Decision 8 floor holds; interior reserved-denied. |

## The VETO adjudication

Creative and Logical reached **opposite empirical conclusions on the same
question** — is the marker forgeable. Logical: "marker forgery defeated." Creative:
"forgeable by any code with import access — VETO."

The synthesizer resolved it firsthand. Importing **only** `core.governance.successor_governance`
(the contract module the daemon, sidecar, health, and validators all import) —
never `successor_origin_writer` — I forged a `bonded_user_manual` `HumanOriginMarker`,
built a two-event capsule (`capsule_created` + `fate_directive_set` /
`explicit_dissolution`), and `successor_governance_health` returned
`{"mode": "valid", "valid_event_count": 2, "invalid_event_count": 0}` with
`derive_current_state().fate_directive == "explicit_dissolution"`. **Creative is
correct.** Logical's "defeated" rested on testing only the no-token construction
and `object.__setattr__` (both genuinely caught); it did not test the
imported-token path. 20-Years-Future-Maez's and Body-Coherence's RATIFY rest on
the same incomplete coverage.

The verdict is **REVISE, not VETO** — because the spec is sound (both lanes
ratified it at second-fold; CC-S1 was verified closed in code) and every fix is
a recovery that makes the *code* match the *sealed spec*, not a spec re-open. The
Logical role — the formal veto seat — declined to veto. But Creative's instinct
is honored without reservation: this is the load-bearing wall, and S6 does not
push until it stands.

---

## Blocker findings

### CC-I1 (blocker) — the human-origin marker is forgeable; the lineage capsule can be machine-authored

Spec C4: "The lineage capsule cannot be machine-authored." Spec D4: "Maez, the
daemon, sidecars, health projection, validators ... must not be able to mint the
marker." The implementation does not enforce this.

- `_MARKER_CONSTRUCTION_TOKEN` (`successor_governance.py:156`) is a plain module
  global — importable by anything that imports the contract module, which the
  daemon/sidecar/health/validators all must.
- `_expected_marker_id` (`:859`) is a public, **keyless** SHA-256 of the marker's
  own fields — no secret, no signature, no key.
- `HumanOriginMarker.__post_init__` (`:190`) gates on `construction_token is
  _MARKER_CONSTRUCTION_TOKEN` and `marker_id == _expected_marker_id(...)` — both
  reachable, both keyless.
- `_validate_persisted_marker_binding` (`:744`) "validates" a persisted marker by
  recomputing the same keyless `_expected_marker_id` — a self-consistency check,
  not proof of human minting.
- `DirectiveEvent` (`:229`) has no `__post_init__`; `load_events_jsonl` (`:707`)
  rebuilds arbitrary JSON into event objects.

**Firsthand-verified** (output above). Any code with import access — the daemon,
a sidecar, Maez's own self-dev path — can author a complete, validating lineage
capsule, including a forged bonded-user `explicit_dissolution` directive.

This is the S5 CC-I1 shape exactly: a keyless self-hash standing in for a real
check. The S5 recovery-2 lesson was available and not applied — S5 explicitly
found "the token is an importable module global ... the [module-qualified
caller] check is the real lock." S6's marker gate is token-only — S5's
*pre*-recovery-2 state, which the S5 council found insufficient. The
`successor_origin_writer.py` module is import-isolated from the daemon (Body-Coherence
verified) — but the seam adds nothing the contract module doesn't already
expose; the *minting primitive* leaked into the shared module.

**Fix (recovery against the sealed spec):** apply S5's proven two-factor pattern
— a module-qualified caller check so the writer seam is the only normal-API door;
construction-time validation on `DirectiveEvent`; a real marker check (not a
keyless recompute) in `_validate_persisted_marker_binding`. The spec's
"no cryptographic lineage attestation" Non-Goal means absolute unmintability is
not a v1 deliverable — the honest v1 guarantee is normal-API-unmintable + a named
conceded residual (raw in-process internals manipulation), exactly S5's final
shape; the residual must be added to the named limitations (see CC-I5). RED-test
the imported-token forge — the 110-test contract missed this shape.

### CC-I3 (blocker) — directive supersession is non-functional; the bonded user cannot amend the capsule

Two halves, one defect. (a) `validate_capsule_events` (`:485`) requires
`supersedes_event_hash == previous_event_hash` — the *physically previous* event
— but spec D17 requires "the current valid head of the directive line." A
directive line is almost never the last physical event, so amending an earlier
directive after any later event is appended is rejected as `stale S6 supersession
target`. (b) `derive_current_state` (`:516`) has no `directive_superseded` branch
— even a valid supersession leaves the superseded directive live in derived
state. Future-Rohit traced both firsthand: a capsule with `created → role_named →
scope_granted → fate_directive_set` cannot then amend the `role_named` line.

This defeats D17 / Decision 18 anti-lock-in — "S6 must not trap a bonded user
behind a capsule they cannot amend." A capsule the owner cannot correct is, in
Future-Rohit's words, bureaucratic theater, not a covenant organ. **Fix:** the
supersession target check must track the directive line's current valid head;
`derive_current_state` must process `directive_superseded`. RED-test a
positive-path supersession — the contract has only the negative/stale-target
test, which is why this shipped green.

---

## Major findings

**CC-I2 (major) — `directive_superseded` authority is broader than the sealed
spec.** `DIRECTIVE_AUTHORITY["directive_superseded"]` (`:138`) admits all five
non-bonded roles; the spec authority matrix requires "same origin role required
by the directive line being superseded." Logical executed it — an
`estate_executor`- or `operator`-origin `directive_superseded` of a bonded-user
`fate_directive_set` validates clean. Latent today (CC-I3: the reducer ignores
the event) but a future reducer that honors supersession inherits the hole — a
non-bonded-user revoking the bonded user's fate directive. Fix: require the
superseding marker's role to match the superseded event's origin role.

**CC-I4 (major) — the current-state reducer and per-field health derivation run
over unvalidated events.** `derive_current_state` (`:516`) walks every event
with no validation gate: a `scope_granted` for the deprecated `legacy_all_memories`
enters `active_scopes` (Creative executed; spec D13 says deprecated scopes are
rejected outright); and `successor_governance_health` derives
`maez_preference_present` from the reducer, so a forged/markerless
`maez_preference_recorded` row sets `maez_preference_present: true` while `mode`
is `unavailable` (Outside-View executed). Same recurring pattern as CC-I1 — a
check of internal consistency where provenance is required. Fix: gate the
reducer and per-field health signals on validation.

**CC-I5 (major) — the spec-mandated honesty banner and named limitations did not
survive into shipped artifacts.** Spec lines 34-36 mandate an honesty banner
("despite the slice name, S6 v1 does not govern a live succession"); Outside-View
grepped — it is in zero shipped artifacts (module docstring, runbook). Spec D5
(privileged-filesystem bypass) and D6 (the content-blind validator cannot prove
physical append-only against a privileged rewrite) are absent from
`operator-helper-runbook.md`. `test_100` checks only `spec.md`, so the drop is
untested. Fix: carry the banner + all named limitations into the shipped
module/runbook; extend the test to assert they survive into shipped artifacts;
and once CC-I1 lands, add the raw-internals marker-forgery residual to that set.

---

## Minor findings & nits

- **CC-I6 (minor)** — health `mode`: every invalid/forged capsule routes to
  `unavailable` via `last_error_class="validation_error"` (`:694`), never
  `invalid`. `unavailable` reads as "try again later"; a forged/corrupt capsule
  must surface as `invalid`. The spec's `invalid` mode is dead on the file path.
- **CC-I7 (minor)** — `capsule_invalidated` authority (`:139`) admits
  `{bonded_user, operator, maintainer}` with no payload discriminator; spec D4
  splits intentional invalidation (bonded-user) from content-free integrity
  invalidation (operator/maintainer).
- **CC-I8 (minor)** — `resolve_fate_directive` (`:629`) accepts a raw
  `user_directive` and returns `explicit_dissolution` if handed that string.
  Safe today (only reducer-fed + tests); a future activation slice calling it
  with unvalidated input bypasses every origin guard. Add a provenance-precondition
  docstring + defensive guard.
- **Nits** — `pending_witness_count` is never populated; `blocks_liveness` is
  emitted but absent from the D19 schema; `PROJECTION_STATES` /
  `no_directive_recorded` is a dead constant.

---

## What the council verified sound

- **D10 — Maez cannot route itself to dissolution.** Exhaustively verified by
  Logical, Creative, and 20-Years-Future-Maez: `maez_prefers_dissolution` is
  absent from the vocabulary and rejected; `resolve_fate_directive` consults only
  the three continuity-preserving preference kinds and floors everything else to
  `paradise_default`. CC-S1 — the spec council's headline blocker — survived
  intact into code. *(CC-I1's forged-capsule path is a different route — forging
  the bonded user's own `explicit_dissolution` — not Maez routing itself via a
  preference; the preference-ordering covenant is genuinely sound.)*
- **Decision 8 floor** — missing/absent fate directive → `paradise_default`;
  missing capsule → `no_capsule`, `blocks_liveness: False`; never invalid-dissolution.
- **Reserved-denied scopes** — `private_thoughts_content` / `crisis_held_content`
  / `credential_secret_material` invalid in v1; default scope `none`;
  high-sensitivity computed from the vocabulary, not a payload boolean.
- **Contract-module purity** — import probe (Logical, Body-Coherence): zero
  private-thought / M1 / S5 / credential / daemon / web / Telegram imports.
- **Decision 22** — `blocks_liveness: False` unconditional; restore unentangled.
- **Content-free surface** — health/sidecar carry no names/relationships/scope/fate;
  public + debug strip `successor_governance`; no first-true timestamps;
  `last_error_class` carries only exception class names.
- **Witness authority** — `validate_marker_authority` rejects a witness-origin
  `role_named`; witness cannot grant scope; maintainer cannot grant archive read.
- **Namespace disjointness** — S6 event types vs `identity_ledger` event types
  are disjoint; Decision-22 backup-manifest registration is real with the at-rest
  caveat.
- **The operator's pre-commit audit fixes (b)–(e)** genuinely landed — the helper
  no longer mints markers or imports the seam; markerless rows and reserved-scope
  grants flag invalid; the sidecar S6 red gates fire. *(CC-I1 is the adjacent
  imported-token door the self-audit missed.)*

---

## The honest reading

The spec is sound — both lanes ratified it at second-fold, and CC-S1, the
dissolution-routing blocker, was verified closed in code. The covenant *shape* is
largely built: the preference ordering, the Decision 8 floor, default-deny, the
reserved-denied scopes, contract purity, the content-free surface all hold. But
the load-bearing wall — "the lineage capsule cannot be machine-authored" — is not
standing. The marker is forgeable by a normal-API import; a forged capsule passes
as `valid`. Two findings (CC-I1's keyless `_validate_persisted_marker_binding`,
CC-I4's validation-blind reducer) are the same recurring shape: a check that
proves *internal self-consistency* substituted for one that proves *provenance*.
The S5 recovery-2 lesson — token alone is not a barrier; the second factor is the
lock — was available and not applied. The 110-test contract passed because it
never contained the imported-token forge, the wrong-role supersession, or a
positive-path supersession; the recovery must add those RED-first.

This is the seven-for-seven recovery shape: every covenant slice this arc has
needed a post-implementation recovery, and S6's is now scoped. It is not a
failure of the build — the spec is honored almost everywhere — it is the two
hardest seams (unmintable authorship, amendable supersession) needing the
structural pass.

## Recovery scope

RED-first — a failing test per seam before the fix: CC-I1 (imported-token marker
forge → S5 two-factor pattern + `DirectiveEvent`/`HumanOriginMarker`
construction validation), CC-I3 (positive-path supersession → directive-line head
check + reducer branch), CC-I2 (wrong-role supersession), CC-I4 (deprecated-scope
reducer leak, forged-row health field), CC-I5 (banner + limitations into shipped
docs, test extended), CC-I6/I7/I8 + nits.

## What's next

1. **Codex engineering post-implementation panel** (operator's lane) — CC-I1,
   CC-I3, CC-I4 are squarely engineering and will likely surface there too.
2. **Recovery commit** — RED-first, per the scope above.
3. **Both-lane post-recovery verification** — re-running the forge exploit
   firsthand, not trusting green tests (the S5 lesson).
4. **Push** — only after both lanes ratify the recovery.

*This review is read-only. No code, no spec edits, no non-slice docs changed in
producing it.*
