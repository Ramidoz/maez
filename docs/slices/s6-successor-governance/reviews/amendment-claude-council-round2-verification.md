# Claude Covenant Council — S6 Persisted-Authorship Amendment: Round-2 Post-Implementation Verification

**Subject:** `564ad5c fix(s6): align persisted-authorship runtime semantics` — the
round-2 implementation of the canonicalized persisted-authorship amendment,
verified against ratified diagnostic v2 and the canonical amended spec
(Decision 33 / ADR 0038).

**Ran:** 2026-05-16, post-round-2, pre-push. Read-only. Two independent passes:
an adversarial verification agent, and the covenant synthesizer's own firsthand
PATH 2 exploit re-run. Per the operator's instruction, the Codex 126/4057 green
was not treated as review — the exploit was re-run independently.

**Verdict:** **RATIFY closure**, with one minor. Round-2 faithfully implements
the canonicalized amendment. The firsthand PATH 2 forge confirms a hand-built
persisted capsule projects `mode: well_formed` (not `valid`) and is
**non-actionable** — the authorship-attestation predicate is hard-false,
`explicit_dissolution` cannot resolve for activation unattested. One minor:
`resolve_fate_directive`'s activation gate uses Python truthiness — recommend
the one-line `is True` hardening before push. It does not block — no live
caller — and the verdict stands at RATIFY closure.

---

## Two independent passes — both RATIFY closure

The adversarial verification agent re-ran the PATH 2 forge firsthand and returned
RATIFY closure with one nit. The covenant synthesizer then re-ran the exploit
*independently* — its own probe (`/tmp/s6_round2_verify.py`), hand-building a
forged JSONL capsule with no `DirectiveEvent` constructor for the chain, no
construction token, no `successor_origin_writer` import. Both passes reached the
same place. Synthesizer probe output:

```
forged-capsule health: {"mode": "well_formed", "well_formed_event_count": 2, "invalid_event_count": 0, ...}
PASS  forged-capsule health mode == 'well_formed'
PASS  health mode is NOT 'valid'
PASS  'well_formed_event_count' key present
PASS  'valid_event_count' key ABSENT
PASS  forged dissolution visible as recorded structure (expected, not authority)
PASS  attestation predicate is hard False for the forged event
PASS  self-declared attestation payload fields do NOT flip the predicate
PASS  explicit_dissolution + attested=False raises
PASS  explicit_dissolution default-arg raises
PASS  notice written as a sibling file beside the JSONL
PASS  notice not inside the JSONL — load_events_jsonl still parses cleanly
PASS  notice text says structure-not-authorship
SUMMARY: 12/12 round-2 correctness checks passed
CC-I1 PATH 2 after round-2: FORGE NON-ACTIONABLE — well_formed (not valid), predicate False, dissolution gated
```

**The headline.** The PATH 2 forge still produces a *structurally* valid capsule
file — that cannot change while v1 is keyless, and the amendment never claimed
it would. What changed is the two things the amendment promised: the forge is
now **honestly labelled** (`well_formed`, never `valid`) and **non-actionable**
(`event_has_verifying_authorship_attestation` is hard-false; `explicit_dissolution`
raises on resolution). CC-I1 — a machine-forged death warrant passing as a
genuine `valid` directive — is closed in the only way a keyless v1 can close it:
the capability is named, labelled, and rendered inert.

## Verified faithful to the ratified amendment

Traced `git show 564ad5c` against ratified diagnostic v2 and the canonical spec:

- **Honesty banner** (`successor_governance.py` docstring) — widened: "validates
  structure, not persisted authorship ... any process with ordinary write/delete
  access to the capsule path can forge, rewrite, or remove the file." The stale
  "privileged OS file rewrite" wording is gone.
- **Health rename** — `HEALTH_KEYS`, `ValidationReport`, `project_successor_governance_health`,
  and `successor_governance_health` all carry `well_formed_event_count`; the
  success mode is `well_formed`. A new guard raises `ValueError` if a stale
  `valid_event_count` kwarg is passed — the amendment's "stale surface must be
  test-visible," enforced loudly.
- **`event_has_verifying_authorship_attestation(event)`** — new; `return False`
  unconditionally; the docstring states v1 has no reviewed trust-source slice so
  it is false for every event "regardless of self-declared fields inside the
  capsule." Verbatim-faithful to amendment v2 §7. Firsthand-confirmed false for
  the forged event and for an event with self-declared `authorship_attested:
  True` / `verifying_authorship_attestation: True` payload fields.
- **`resolve_fate_directive`** — `validated_user_directive` →
  `authorship_attested_user_directive`; `explicit_dissolution` raises unless
  attested; unattested continuity-preserving directives fall through to the
  Decision 8 floor (consultable recorded intent, not self-executing) — matching
  D10 / D22.
- **Capsule-adjacent notice** — `ensure_capsule_notice` / `capsule_notice_path`
  write `lineage_capsule_NOTICE.txt` as a *sibling* via `Path.with_name`; the
  operator helper (`scripts/s6_successor_governance.py`) calls it before
  appending to the JSONL. The notice text speaks to estate/legal readers, names
  destructive/dissolution gating, and warns "Copying the JSONL alone can hide
  this limitation." Firsthand-confirmed: the notice lands beside, not inside, the
  JSONL, and `load_events_jsonl` still parses the capsule cleanly.
- **Runbook** — honesty banner widened; the Limits section drops "privileged OS
  operator" for "any process with ordinary write/delete access," adds the
  authorship-attestation requirement, and adds the `no_capsule` semantics ("no
  capsule available at this path now ... does not prove the bonded user never
  authored a capsule elsewhere or in a backup"). This lands amendment diagnostic
  §8, which the canonicalization-faithfulness check had noted as deferred to
  round-2 — confirmed landed.
- **RED-first** — per the commit and the agent's diff read, round-2 added
  failing tests for the forged-dissolution path, self-declared attestation
  fields, stale health vocabulary, and notice creation before implementation;
  126 S6 tests / 4057 full-suite green.

No covenant drift. No delivered guarantee weakened. Nothing the amendment did
not ratify appears in the diff.

## The one minor — CC-R2-1: the activation gate uses truthiness, not identity

`resolve_fate_directive`'s gate is `authorship_attested_user_directive: bool =
False` checked by `if not authorship_attested_user_directive:`. Python truthiness
— so a truthy non-bool opens it. Firsthand-confirmed:

```
attested=        True: returned 'explicit_dissolution'      (correct)
attested=      'true': returned 'explicit_dissolution'      <-- gap
attested=           1: returned 'explicit_dissolution'      <-- gap
attested=         [1]: returned 'explicit_dissolution'      <-- gap
attested=  {'k': 'v'}: returned 'explicit_dissolution'      <-- gap
attested=  False/0/''/None: raised (gated)                  (correct)
```

**Why it is a covenant concern:** this is the activation gate for a
machine-forgeable death warrant — the single most safety-critical predicate in
S6. The amendment's spirit (D22, v2 §7) is that the gate keys on a real,
un-trickable signal. The companion predicate `event_has_verifying_authorship_attestation`
*is* un-trickable (hard `bool False`). But `resolve_fate_directive`'s consumption
of attestation is not — it trusts the caller to pass a real `bool`. A future
activation slice that passes a capsule-derived field (e.g. a JSON string
`"true"`) straight in would open the gate.

**Why it is a minor, not a blocker:** `resolve_fate_directive` has **zero
non-test callers** anywhere in the repo (grep-verified by the agent) — it is
future-activation-only code today. The companion predicate is bulletproof, no
live path feeds capsule bytes into the kwarg, and D22 canonically binds every
future activation slice to the attestation predicate. There is no live breach.
This is the same defensive-hardening territory the implementation council rated
minor as CC-I8 — the next layer of the same `resolve_fate_directive` concern.

**Fix (recommended before push):** `if authorship_attested_user_directive is not
True:` — only the canonical `bool True` from the predicate opens the gate; add a
RED test passing `"true"` / `1` and asserting `explicit_dissolution` still raises.
One line plus a test. The covenant lane recommends it land in the round-2 commit
series rather than as a follow-up — the death-warrant gate should be
self-protecting, not caller-trusting — but does not block the push on it given
zero live callers and D22's binding of the future caller. Operator's call on
fix-now versus fix-when-the-activation-slice-lands; the recommendation is
fix-now.

## Cooling-off waiver — noted

`564ad5c` records that the owner explicitly waived the same-day cooling-off pause
for this recovery, and records the waiver in-commit "because S6 remains
covenant-touching." That is the disciplined way to deviate — an owner's
sovereign call over the owner's own rule, recorded rather than hidden. Because
the cooling-off exists to catch recall-drift from just-amended spec wording, this
post-implementation verification carried that backstop weight: the diff was
checked section-by-section against the *amended* canonical spec, and round-2 is
faithful — no recall-drift, no stale wording. The waiver did not cost anything
here; the verification confirms it.

## What the verification confirmed sound

- PATH 2 re-run firsthand by two independent passes — the forge is `well_formed`
  and non-actionable; `event_has_verifying_authorship_attestation` hard-false
  including against self-declared capsule fields; `explicit_dissolution`
  un-resolvable unattested via the default-arg path and the explicit `False`
  path; `maez_prefers_*` cannot yield `explicit_dissolution`.
- The `well_formed` rename is complete — no stale `valid` mode token or
  `valid_event_count` health key remains; a stale-kwarg guard fails loudly.
- The capsule-adjacent notice writes beside the JSONL; the loader is unaffected.
- The honesty surfaces (module docstring, runbook banner + Limits) carry the
  widened, accurate wording.
- No covenant drift; no delivered guarantee weakened.

## Verdict and what's next

**RATIFY closure** from the Claude covenant lane. Round-2 `564ad5c` delivers the
canonicalized persisted-authorship amendment; the firsthand exploit confirms
CC-I1 / PATH 2 is honestly labelled and non-actionable.

1. **CC-R2-1** — the recommended one-line `is True` gate hardening + RED test,
   before push (operator's call; not a blocker).
2. **Codex engineering post-implementation pass** — if the operator's 126/4057 +
   manual-probe verification was not the formal engineering panel, run it.
3. **Push** — `28da567` + round-2, only after both lanes ratify.

`28da567` stays unpushed until the push gate. S6 is otherwise covenant-clear.

*This verification is read-only. No code, spec, ADR, BAD, or non-slice docs were
changed in producing it. The firsthand probe ran against a temporary capsule in
`/tmp`; no live store was touched.*
