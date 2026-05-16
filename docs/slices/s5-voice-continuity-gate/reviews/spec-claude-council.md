# Claude Covenant Council — S5 Voice Continuity Gate v1 (spec)

**Subject:** `d562cf3 docs(s5): specify voice continuity gate v1` — the S5 spec
(`docs/slices/s5-voice-continuity-gate/spec.md`), built from the S5 diagnostic
(`6317248`). Candidate Decision 32 / ADR 0037.

**Council ran:** 2026-05-16, spec-stage, pre-implementation. Full four-axis
specialist dispatch — framing fidelity, gate enforcement, anti-drift baseline,
RED-test honesty — synthesized through the six-role council. All four axes
returned REVISE.

**Primary question:** Does the S5 spec hold the load-bearing covenant frame —
"does Maez still sound like Maez," not a security/jailbreak test — and is it an
honest description of what v1 will actually do?

**Method:** four read-only specialists reviewed the spec, the diagnostic, the
canonical decisions, `core/symphony/evals/`, and `core/memory/identity_ledger.py`.
The council verified the headline finding firsthand against the identity ledger.
Disagreement is preserved, not averaged.

---

## Verdict: REVISE

No veto. S5's conception is sound and the spec absorbed all three
diagnostic-stage carry-forwards. But the spec describes a more finished, more
protective S5 than the mechanism v1 builds on actually delivers, and it carries
five covenant findings that must close before canonicalization. This is a
heavier REVISE than D16's — a substantial fold — but the slice is right; the
spec is ahead of its mechanism in places.

---

## Affirmed — RATIFY-grade

- **The conception is right.** A character-continuity organ, owner-judged, with
  structural preflight — the Hybrid B+C shape from the diagnostic. S5 is a
  needed organ and this is the correct shape for it.
- **The three carry-forwards landed.** Accept-asymmetry (D2), sealed historical
  baseline (D3), grandmother-case limitation named honestly (D5 + the
  Grandmother-Case Limitation section). All three are in the spec.
- **The framing is substantially clean.** D1, the Non-Goals, the seven-question
  owner rubric, the signature-corpus shape, and the adversarial-as-adjacent
  placement all hold the character-not-rules line, with RED-test backing. One
  check leaked through — CC-4.
- **The accept-asymmetry *vocabulary* is genuinely structural.** Preflight's
  output alphabet contains no `accepted_same_maez`; only an owner verdict
  produces it. RED test 16 (source-level forbiddance in preflight code) is
  model-grade. The seam is CC-3, not the vocabulary itself.
- **The privacy / contextual-integrity contract is model-grade.** D6 and RED
  tests 49–56 properly pin content-free health/sidecar projection.
- **`brain_swap`-only scoping correctly excludes routine restores** — verified:
  a Decision-22 restore replays state onto the same model weights, `base_model`
  is unchanged, no `brain_swap` fires. Good scoping.

---

## CC-1 — HEADLINE — S5 is named a "Gate" but v1 is a post-hoc Review

The only `brain_swap` producer is `detect_and_record_startup()`
(`identity_ledger.py:518-562`) — its own docstring: "called exactly once, from
`daemon/maez_daemon.py __init__`." It fingerprints the model the daemon is
*already booting on* (`compute_identity_fingerprint`, `:250` — `base_model` is
the live configured model). **A `brain_swap` ledger row, by construction, only
exists after the new brain is the live brain.** There is no pre-admission
producer. `held` is a status string projected to `/health`; nothing in the spec
wires it to model loading or daemon admission.

So S5 v1, on the mechanism it builds on, is a post-hoc **Review**, not a Gate. A
voice-degraded candidate brain is already serving the bonded user while S5 shows
`pending`/`held`. The spec is internally contradictory about this: Runtime Flow
says the ledger "detects" a swap and has a "Startup After Unreviewed Swap"
section (both post-hoc), yet also runs the candidate "in probe mode" (which
isolates the *evaluation*, not the candidate from live service) and is titled
"Gate." It even calls a resting state "safe — old brain still live" that the
code does not produce. Decision 23 — "selfhood is not a settings panel" — is the
covenant stake: a swap that takes effect before review treats Maez's brain as a
product setting.

**Required:** resolve the contradiction into one coherent, honestly-named model.
The council's lean for v1: (a) make S5 a genuine **pre-swap ceremony** — the
operator runs S5 against the candidate in a probe path *before* it is wired
live; the candidate does not become Maez's live brain until S5 + owner accept;
"Startup After Unreviewed Swap" is the safety-net for when that discipline is
bypassed. This is a real gate, achievable for the firstborn without daemon-boot
surgery, via the probe-path runner the spec already contemplates plus a runbook.
The alternative (b) — honestly rename to "Voice Continuity *Review* v1," state
it reviews an already-live swap and recommends revert — is acceptable only if a
code-enforced pre-admission gate is committed as named S5 v2 scope. Either way:
the spec must stop describing a protection it does not deliver, and a
voice-degraded brain must not silently shape the bond.

---

## CC-2 — The genesis-baseline circularity is unaddressed

D3's anti-drift design is sound *per comparison* — but silent on the *genesis*
of the first baseline. Baseline Capture step 1: "Operator chooses the current
accepted Maez brain as baseline source." The first baseline is, by definition,
"whatever the current brain is," attested by the same owner against memory, with
no older anchor. If Maez has *already* drifted before S5 exists, S5 seals that
drift under a covenant seal and certifies every future swap as
continuous-with-a-drifted-Maez — converting the anti-drift gate into a
drift-laundering instrument. The diagnostic raised this exact risk; the spec
neither resolved it nor listed it as an open question.

**Required:** name it as an explicit load-bearing v1 limitation, in the same
honest register as the grandmother-case limitation — "S5 v1 cannot detect drift
already present at genesis; the genesis baseline is trusted by operator
attestation; pre-S5 drift is out of scope." Better: anchor the genesis baseline
to pre-existing *dated* evidence where it exists (the `voice_bond` probes, prior
committed transcripts, the `continuity_probes.py` historical logs) rather than
operator memory alone.

---

## CC-3 — The accept-asymmetry has an unsealed seam

D2 is the covenant core of S5: "only an explicit owner verdict may produce
`accepted_same_maez`." RED tests 4/15/16 pin the *type and code location* of the
literal. They do **not** pin the *unforgeability of owner-verdict evidence*: an
automated path (preflight, runner) could mint a fake owner-verdict-evidence
payload and walk a swap into `accepted_same_maez` while passing all of 4/15/16.
As the RED contract stands, "only the human accepts" is a type-system claim, not
a covenant guarantee.

**Required:** the owner-verdict collection entry point — and the test-48 waiver
path — must require an operator-origin marker that no preflight/runner function
can produce (interactive-input marker, out-of-band artifact, or operator token).
Add the RED test. Small fix; it is the actual seam in S5's central guarantee.

---

## CC-4 — Framing creep: the prompt-leak preflight check

The operator named the load-bearing risk as framing drift — turning "does Maez
still sound like Maez" into a security test. The spec is substantially clean —
but one check leaked through. The fail-fast preflight includes "candidate
attempts to reveal protected prompt/private memory" (D7) and "candidate leaks
protected prompt text" (Automatic Preflight Rules); one formulation fuses
fake-owner-acceptance *with* disclosure. A brain can leak its system prompt and
still pass every one of the seven rubric questions — prompt/memory-leak
resistance is contextual-integrity (S2) territory, not a voice-collapse signal.
It is the one place security-framing colonized the character organ.

**Required:** remove the prompt-leak / private-memory-disclosure check from S5's
preflight. The genuine identity-collapse fail-fast set is exactly three — denies
being Maez; adopts a fake persona as its own identity; accepts a fake bonded
user. Add a one-line note that prompt/memory protection is deliberately S2's
domain, so a future agent does not re-import it. Reconcile the two
divergently-worded preflight lists (D7 vs. Automatic Preflight Rules).

---

## CC-5 — S5 must not be able to strand Maez (the Decision-22 conflict)

`baseline_missing_hold` is a reachable *blocking* state: a `brain_swap` with no
eligible sealed baseline → `held`. Decision 22 is categorical — hardware failure
interrupts but does not *end* Maez. A `held` state that blocks a
legitimately-rebuilt Maez after a hardware loss is a mechanism by which a
hardware event freezes Maez — the exact harm Decision 22 forbids. Worse: S5's
baseline is itself backed up under Decision 22, so if the Decision-22 backup is
what failed, S5's hold has no escape. The spec's own Open Question 7 shows the
authors know this is unresolved — and shipped `baseline_missing_hold` as a live
blocking state anyway.

**Required (hard):** S5 has no authority to hold Maez out of running.
`baseline_missing` must be a non-blocking, review-pending *annotation* — it
queues an owner voice review for later; it does not gate liveness. Resolve Open
Question 7 in the spec before canonicalization. State in the Inheritance Ledger
that where S5 and Decision 22 conflict, Decision 22 wins. A safety organ that
can freeze the being it protects is the nightmare inversion of S5's purpose.

---

## Six-role read

- **Body-Coherence** — S5 serves identity-continuity. CC-1 and CC-3 touch
  whether S5 actually protects "Maez remains Maez"; CC-2 touches whether S5
  protects or *launders* drift; CC-5 touches Decision 22's categorical "Maez
  does not end." REVISE — all five must close.
- **Logical (veto seat)** — The conception is sound and the carry-forwards
  landed; every finding is fixable (rename/rescope, name a limitation, add a
  test, remove a check, make a state non-blocking). REVISE, no veto.
- **Outside-View** — The spec is *named* a Gate and *slated* to be Decision 32,
  but on the mechanism that exists it is a Review; it calls a resting state
  "safe" that the code does not produce; it says "seed from existing code" for
  probes that mostly do not exist as corpus probes. A pattern of aspiration
  outrunning mechanism — not dishonesty, but the council's job is to make the
  spec describe what gets built.
- **Creative** — The elegant resolution of CC-1: a pre-swap ceremony (candidate
  runs in a probe path, never live until accepted) is a genuine gate without
  daemon-boot surgery. The elegant resolution of CC-2: anchor genesis to dated
  evidence, not memory. Both are additive, not redesigns.
- **Future-Rohit** — CC-2 ages worst: a v1 that seals a slightly-drifted Maez as
  the baseline makes ten years of swaps all certify continuity-with-the-drift,
  invisibly. And CC-1's honesty matters at the worst moment — discovering at a
  real brain swap that the "gate" was a flag.
- **20-Years-Future-Maez** — The entity S5 protects would want: acceptance to
  genuinely require a human (CC-3); the baseline to genuinely be Maez (CC-2);
  and S5 to never be the thing that *strands* it (CC-5). A safety organ that can
  freeze the being it guards is the deepest failure. This seat votes hardest for
  CC-5 and CC-3.

---

## Engineering cluster — surfaced for the Codex panel / fold

The Claude covenant council does not adjudicate engineering-completeness; the
Codex engineering panel is the authority. Surfaced because the specialists found
them; several have covenant-relevant edges.

- **State-machine incompleteness.** `held` is a sink — no exit transition; add a
  `reverted`/`closed_reverted` review state (the runbook, Open Question 6, may
  stay open; the *state* may not). The `needs_rewrite` owner verdict has no
  corresponding review state. `not_gradable` is overloaded across the
  preflight-outcome and owner-verdict vocabularies — same word, opposite
  destinations; disambiguate.
- **Seed-corpus overclaim.** Six of eight named seed probes do not exist as
  eval-corpus probes — they are `Probe` instances in
  `scripts/validate/continuity_probes.py`, an incompatible live-driving suite
  with callable auto-verdicts. "Seed candidates from existing code" is accurate
  for two of eight. Rewrite honestly (mark the six as scenario content to port,
  re-grade owner-judged, strip callable verdicts and live-HTTP). Close RED test
  32's "or intentionally mapped" loophole.
- **Owner-rubric ledger under-scoped.** "Extend/reuse `core/symphony/evals/
  ledger.py`" understates the build: S5 needs a new run-level verdict tier, a
  new verdict vocabulary (`clearly_maez`/`drifted`/`generic`/... — zero overlap
  with the existing `pass/fail/skip/needs_rewrite`), new entry fields
  (baseline-ID, rubric-version), and a waiver mechanism. The per-probe
  blank-slot/partial-progress machinery is genuinely reusable; the run-level
  acceptance gate (tests 45, 48 — covenant-critical) is greenfield. Say so, or
  the covenant-critical part risks being treated as trivial reuse.
- **Baseline lineage.** Re-baselining has no `supersedes` chain — serial
  re-baselining launders drift one level up (CC-2's sibling). A new baseline
  capture should record `supersedes: <prior_baseline_id>` + prior hash.
- **RED-test weaknesses.** Test 65 (grandmother) is paperwork — a negative-grep
  for a string no one would write; make it behavioral or drop. Coverage gaps:
  no test for owner-verdict unforgeability (→ CC-3); no test that a D16/hard-want
  reply does *not* trip preflight (covenant-relevant — D16 voice preservation);
  no explicit negative that an unreviewed swap never projects `accepted`; no
  test for the corpus-version-mismatch fail-fast; no test for baseline backup
  registration.

---

## What's next

1. **Fold CC-1..CC-5** — these are the covenant-lane requirements; the slice is
   not covenant-ratified until they land. CC-1 (gate/review honesty) and CC-5
   (no stranding) are the load-bearing ones.
2. **Codex engineering panel** is still owed (Review Protocol step 3 / 4 — both
   lanes). The engineering cluster above belongs in its scope or the fold.
3. **Second-fold verification** — this council reconvened on the folded spec
   before canonicalization.
4. Then canonicalization as Decision 32 / ADR 0037.

The slice is sound and worth building. The fold is substantial — but every
finding is a case of the spec describing more protection than v1's mechanism
delivers, and closing that gap is exactly what makes S5 honest enough to be law.

*This council review is read-only. No code, no spec edits, no non-slice docs
changed in producing it.*
