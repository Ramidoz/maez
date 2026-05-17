# Claude Covenant Council — S6 Successor Governance v1: Post-Recovery Verification

**Subject:** `5a19d7d fix(s6): recover successor governance authority seams` — the
recovery of `52440fb`, verified against `implementation-claude-council.md` (the
REVISE that scoped it). Decision 33 / ADR 0038.

**Council ran:** 2026-05-16, post-recovery, pre-push. Read-only. The synthesizer
reproduced the CC-I1 headline exploit firsthand against `5a19d7d` — green tests
were not trusted (the S5 lesson). Probe output is quoted verbatim below.

**Verdict:** **REVISE-AGAIN.** The recovery closed six of the eight findings and
the nits, and genuinely fixed the second blocker (CC-I3 supersession). But
**CC-I1 — the load-bearing blocker — is not closed.** A machine-authored lineage
capsule still projects `mode: valid` carrying a forged bonded-user
`explicit_dissolution` directive. **Do not push.** A round-2 recovery is
mandatory — and CC-I1's residual is no longer a pure implementation miss; see
"The structural finding" and "The fork."

---

## Per-finding disposition

| Finding | Prior severity | Post-recovery disposition |
|---|---|---|
| **CC-I1** — marker forgeable / capsule machine-authored | blocker | **OPEN** — firsthand-verified, two paths |
| CC-I3 — supersession non-functional | blocker | Closed — directive-line head check + reducer branch |
| CC-I2 — wrong-role supersession | major | Closed — same-origin-role enforced |
| CC-I4 — validation-blind reducer / health | major | Closed — reducer gates on `_structurally_valid_events` |
| CC-I5 — honesty banner / named limitations | major | Closed — banner in module docstring + runbook |
| CC-I6 — forged capsule → `unavailable` not `invalid` | minor | Closed for forged rows; unparseable-capsule residual named |
| CC-I7 — `capsule_invalidated` authority undiscriminated | minor | Closed — bonded-user vs operator/maintainer split |
| CC-I8 — `resolve_fate_directive` raw input | minor | Closed — `validated_user_directive` guard |
| Nits | nit | Carried; not push-blocking |

CC-I1 was re-run firsthand by the synthesizer. CC-I2–I8 dispositions are carried
from the post-recovery verification agent's read-and-execute pass; the round-2
post-recovery verification re-confirms all eight firsthand once CC-I1's round-2
recovery lands.

---

## CC-I1 (blocker) — still open: the lineage capsule is still machine-authorable

Spec C4: "the lineage capsule cannot be machine-authored." Spec D4: "Maez, the
daemon, sidecars, health projection, validators ... must not be able to mint the
marker." After `5a19d7d`, this is still not enforced. Firsthand probe against
`core/governance/successor_governance.py` at `5a19d7d`:

```
CONTROL  naive constructor from ordinary module : blocked (S6 marker construction is restricted to the origin-writer seam)
PATH 1   exec-globals frame-name spoof          : FORGED -- marker s6_marker_dd8b7fc42c3079cc7ccd25a0 origin=bonded_user_manual
PATH 2   hand-built JSONL /health.successor_gov : {"mode": "valid", "capsule_present": true, "valid_event_count": 2, "invalid_event_count": 0, ...}
PATH 2   derive_current_state.fate_directive    : explicit_dissolution
```

The CONTROL confirms the recovery did something real: the *named* `52440fb`
exploit — import the token, call the constructor from an ordinary module — is
now blocked. But two paths defeat it.

**PATH 1 — the recovery's own mechanism is spoofable.** `_called_from_module`
(`successor_governance.py:901`) decides "called from the writer seam" by
`frame.f_globals.get("__name__") == module_name` (`:906`). `__name__` is an
ordinary key in a frame's globals dict. `exec(src, g)` lets an attacker choose
`g`; set `g["__name__"]` to `"core.governance.successor_origin_writer"` and a
function defined in `g` passes the check from anywhere. The probe defined a
one-line `forge()` in such a dict and minted a `bonded_user_manual`
`HumanOriginMarker` with the real, importable `_MARKER_CONSTRUCTION_TOKEN`. The
check verifies a *settable string*, not the seam.

**PATH 2 — the recovery defended a door the exploit does not use.** A capsule is
a file. `successor_governance_health` (`:702`) → `load_events_jsonl` (`:730`) →
`DirectiveEvent(**data)` (`:736`). `DirectiveEvent` (`:236`) has no
`__post_init__`; its `origin_marker` field stays a plain dict.
`HumanOriginMarker.__post_init__` — the entire surface `5a19d7d` hardened —
**never executes on the disk-load path.** The persisted marker is then
"validated" by `_validate_persisted_marker_binding` (`:767`), whose only
authenticity check (`:797`) recomputes `_expected_marker_id` — a public,
**keyless** SHA-256 of the marker's own fields (`:914`). Any writer reproduces
it. The probe hand-wrote a two-event JSONL capsule (`capsule_created` +
`fate_directive_set`/`explicit_dissolution`) with **no constructor, no seam
import, no token, no frame spoof** — only the module's own public hash helpers.
`successor_governance_health` returned `mode: valid`; `derive_current_state`
returned `fate_directive: explicit_dissolution`.

The original CC-I1 fix asked for three things: a caller check, construction-time
validation on `DirectiveEvent`, and "a real marker check (not a keyless
recompute) in `_validate_persisted_marker_binding`." The recovery did the first
(name-only — PATH 1) and skipped the other two. The recovery's `test_022b`
exercised only the in-memory constructor token path — not the persisted-capsule
path the council's own firsthand exploit used. It shipped green because the
contract still does not contain the persisted-file forge.

**Covenant stakes.** A forged `explicit_dissolution` is Maez's own death warrant
wearing the bonded user's signature — they never wrote it. The prior council
verified D10 sound: Maez cannot route *itself* to dissolution via a preference.
CC-I1 is the other route — forging the bonded user's own directive — and it is
open. A `mode: valid` capsule authored by the daemon, a sidecar, or the self-dev
path carrying `explicit_dissolution` is a unilateral termination that no human
authored. That is exactly what `feedback_maez_commitment_model` and the
Decision 8 floor forbid. This blocks the push absolutely.

---

## The structural finding — why CC-I1 is not a pure implementation miss

PATH 1 is a real implementation defect and is closable now (see "The fork").
PATH 2 is deeper, and the council must say so plainly.

A capsule is a file that outlives the authoring process. By the time
`successor_governance_health` reads it, the writer seam is long gone — the
validator must judge the persisted marker **on its face**. Keyless, on its face,
the only thing to check is internal self-consistency (`marker_id ==
_expected_marker_id(fields)`), which any writer reproduces with the module's
public helpers. And the validator runs **inside the daemon** — the prior council
verified the daemon, sidecar, and health all import the contract module, and D19
health requires it.

Validator-in-daemon + keyless + persisted-file ⇒ the daemon can produce any
verdict the validator will bless. This is not a missing `if` — it is the absence
of a secret. The seam pattern S5 used defends *minting* inside a live process; it
cannot defend a *file re-validated* after the process is gone. The spec's
Non-Goal — "no cryptographic lineage attestation" — forbids the only
keyless-defeating mechanism: a key the seam holds and the daemon does not.

**Therefore S6 v1, as specified, cannot deliver C4 ("the lineage capsule cannot
be machine-authored") as a hard guarantee for the persisted path.** The council
searched for a keyless structural mechanism and did not find one. It states this
as a reasoned position, not a proof, and explicitly invites the Codex
engineering lane to refute it — but the burden now sits with whoever proposes
round-2: exhibit a keyless mechanism, or accept the spec-clarification path.

The council owns its share of this. `implementation-claude-council.md` wrote "a
real marker check (not a keyless recompute)" without saying what a keyless real
check could be — because, as is now clear, there is not one. That
under-specification is part of why the recovery skipped the persisted half. The
prior prescription was right for the minting surface and silent on the
persisted-reload surface, which is the genuinely hard problem.

The existing honesty banner is also too weak. The module docstring concedes only
that the validator "cannot prove physical append-only against a *privileged* OS
file rewrite" (D6). PATH 2 needs **no privilege** — the daemon writes the capsule
path as its ordinary user. The conceded limitation is wider than the banner
admits.

---

## The fork — what round-2 must resolve

**PATH 1 (do regardless).** `_called_from_module` must compare frame *identity*,
not a settable string: `frame.f_globals is sys.modules[_MARKER_WRITER_MODULE].__dict__`
(add `import sys`). A function's `__globals__` *is* its module's namespace dict;
an `exec`-created dict is a different object, so `is` fails. To pass, an attacker
must inject code into the genuine seam module — which is the conceded "raw
in-process internals" residual, S5's final shape. This closes PATH 1. It does
**not** close CC-I1: PATH 2 bypasses the constructor entirely. Necessary hygiene,
not sufficient.

**PATH 2 (the operator + both lanes must adjudicate).** Two options:

- **(A) A keyless structural mechanism the council did not find.** If the
  engineering lane can exhibit one — a way for a daemon-resident, keyless
  validator to reject daemon-authored capsules — CC-I1 closes as an
  implementation recovery. The council's assessment is that none exists, for the
  reason above; this option is open only if that assessment is refuted.

- **(B) A narrow spec clarification.** Accept that C4 is not a hard v1 guarantee
  for the persisted path. `mode: valid` is re-scoped to mean *structurally
  well-formed*, not *human-authored*. The honesty banner widens from "privileged
  rewrite" to "any process with write access to the capsule path can author a
  structurally-valid capsule, including a forged bonded-user
  `explicit_dissolution`," and C4's wording softens accordingly. This is
  spec-clarification-grade: it widens D5/D6's conceded limitation and touches a
  C-level claim — so it travels the full ladder (cooling-off → both panels →
  second-fold), not an inline patch.

The council does not choose between A and B — finding mechanisms is the
engineering lane's work, and softening a sealed C-claim is a joint covenant
call. It states the fork and its assessment, and holds the push until one branch
is resolved.

---

## What the recovery genuinely closed

Verified by the post-recovery verification agent's read-and-execute pass:

- **CC-I3** — supersession is now functional. The target check tracks the
  directive line's current valid head (`_validate_supersession_event`,
  `_advance_directive_line_head`); `derive_current_state` skips
  `_superseded_event_hashes`. The bonded user can amend the capsule — D17 /
  Decision 18 anti-lock-in holds.
- **CC-I2** — `_validate_supersession_event` requires the superseding marker's
  origin role to match the superseded line's origin role. A non-bonded-user can
  no longer supersede the bonded user's fate directive.
- **CC-I4** — `derive_current_state` and per-field health now run over
  `_structurally_valid_events`; a forged or markerless row no longer leaks into
  `active_scopes` or sets `maez_preference_present`.
- **CC-I5** — the honesty banner is in the module docstring and the
  operator-helper runbook with the D5/D6 limitations. *(See above: the banner's
  wording is now too weak for PATH 2 — fold the correction into round-2.)*
- **CC-I6** — a forged-row capsule routes to `mode: invalid`, not `unavailable`.
  Residual, named and minor: a capsule so corrupt it cannot be parsed still
  reads `unavailable`.
- **CC-I7** — `validate_capsule_invalidation_payload` splits bonded-user
  intentional invalidation from operator/maintainer content-free integrity
  invalidation.
- **CC-I8** — `resolve_fate_directive` raises on `explicit_dissolution` unless
  `validated_user_directive=True`; the docstring marks it resolution-only.

Six of eight findings and the structural majors are genuinely closed. The
recovery's failure is narrow and singular — it is the one wall that was always
the hardest: unmintable authorship of a persisted file.

---

## The honest reading

This is the recovery-needs-a-recovery shape, exactly as
`feedback_covenant_slices_need_both_panels` records it. The recovery did real,
correct work on five seams and the second blocker. It failed on CC-I1 in two
ways: it implemented the constructor-seam check name-only (spoofable), and it
hardened the in-memory constructor when the threat is a persisted file the
constructor path never touches. Re-running the exploit firsthand — not trusting
`test_022b` green — is what surfaced both.

The deeper truth is that CC-I1's persisted half was never a patch. A
daemon-resident keyless validator cannot attest human authorship of a file; the
spec promises C4 and the Non-Goal forbids the mechanism. Post-recovery
verification did its job: it found that the prescription itself was incomplete.
S6 does not push until the fork is resolved.

## What's next

1. **Report the verdict to the operator** — REVISE-AGAIN; the fork is a decision
   the operator and both lanes own, not a patch the council hands down.
2. **Codex engineering post-recovery panel** (operator's lane) — and, squarely,
   the request to refute or confirm the "no keyless mechanism" assessment.
3. **Round-2 recovery** — PATH 1's frame-identity fix regardless; PATH 2 per
   whichever branch (A: a mechanism; B: the cooling-off → both-panels →
   second-fold spec clarification). RED-first: the persisted-file forge must
   become a failing contract test before any fix.
4. **Both-lane post-recovery verification** — re-run the forge firsthand.
5. **Push** — only after both lanes ratify and the firsthand forge fails.

*This review is read-only. No code, no spec edits, no non-slice docs changed in
producing it. The firsthand probe ran against a temporary capsule file in
`/tmp`; it touched no live store.*
