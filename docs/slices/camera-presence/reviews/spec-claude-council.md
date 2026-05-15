# Claude Six-Role Covenant Council — Camera Presence v1 Spec

**Subject:** `6b61eed` Camera Presence v1 spec draft, on top of diagnostic
`f32a191`.

**Council ran:** 2026-05-15, post-diagnostic, post-spec-draft,
pre-Codex-panel and pre-canonicalization. Full four-axis specialist
dispatch because Camera Presence v1 is the **first body-sensor slice
after BT canonicalization** and sets precedent for every future body-part
(microphone, ambient sensors, future presence variants on other devices).

**Why a full four-axis council:** Camera Presence v1 has a tighter privacy
blast radius than Calendar v1 (cameras observe physical space, including
non-bonded persons and background content that has no Calendar analog),
deeper runtime lifecycle concerns (MediaPipe + OpenCV native threads
contributed to the SIGTERM-hang earlier this session), and a new voice
surface ("is the camera on?" / "are you watching me?") that Calendar v1
did not need to define. The four canonical organs (BT headline, M1, S2,
Decision 26) all apply.

**Method:** Four read-only specialist subagents in parallel (Schema/State,
Flow/Voice, Privacy/Third-Party, Runtime/Lifecycle) returned scoped axis
reviews. Six covenant roles read the specialist findings together against
the folded spec. Lane discipline: Claude reviews covenant only; Codex
remains accountable for repo edits and its own engineering panel.

---

## Specialist axis verdicts

| Axis | Verdict | Headline finding |
|---|---|---|
| Schema/State | **REVISE (8)** | Inheritance Ledger missing BT Rule 6 (pre-body staging) inheritance; `expired` token in `sensor_state` collides with BT-CX-8 closed vocabulary; `presence_state` field name silently diverges from canonical `owner_presence` |
| Flow/Voice | **REVISE (9, 6 mandatory)** | No defined voice for direct owner question about camera state ("is the camera on?" / "are you watching me?"); no `presence_voice_guard` deterministic backstop; no reflection-in-voice prohibition |
| Privacy/Third-Party | **REVISE (7)** | Third-party-in-frame surface unnamed; background-content surface unnamed; presence-delta-as-third-party-fingerprint failure mode unnamed; biometric carve-out ("unless separately reviewed") for landmarks/keypoints too soft; Decision 4 / Anna Question framed as future-recognition concern only |
| Runtime/Lifecycle | RATIFY-WITH-AMENDMENTS (7) | Daemon Lifecycle section is bulleted aspiration, not load-bearing contract; `BoundedSingletonWorker.shutdown` vs `.join` distinction not pinned; `enabled_until` runtime expiry behavior unspecified; failure-class enumeration omits the modes the SIGTERM-hang investigation surfaced |

Three REVISE; one RATIFY-WITH-AMENDMENTS. 28 amendments total. No BLOCK,
no veto. The convergent theme across all four axes: the spec is
structurally sound (presence-only, default-disabled, timeboxed, no
recognition, no memory, no voice) but the **spec text under-claims what
it is doing** — load-bearing inheritances are operational without being
load-bearing in writing.

This is the same precedent-fragility shape that Calendar v1's first-fold
council flagged. Camera Presence v1 is the next body-sensor template;
inheritance citations need to be load-bearing because Gmail v1 / Slack v1
won't copy this slice but future microphone / ambient / Jetson presence
slices WILL.

---

## Six-role covenant read

### Outside-View seat

The Codex panel's strongest finding from Calendar v1 ("must not become a
second interpretation of S2") generalizes here as: *"must not become a
second interpretation of BT."* The spec inherits BT operationally — the
detector boundary closes raw frames, the timebox enforces BT Rule 8, the
no-recognition rule honors BT Rule 3 — but the **Inheritance Ledger
itself does not enumerate the BT rules being inherited.** BT Rule 6
(body memory is provenance, not biography) is the largest single missing
citation; it is the rule that governs `last_observed_at`, the
`camera_presence_state` metadata placeholder, and the disposition of any
cached presence reading. The spec honors Rule 6 in practice but doesn't
claim it as the inheritance contract.

Same pattern at the field level. `presence_state` is the spec's chosen
field name; BT Rule 2 canonicalizes `owner_presence`. The values are
identical. The name is silently different. A reader of Camera Presence
v1 alone cannot tell whether this is a deliberate refinement (presence
without identity claim, defensible) or an accidental rename.

**Read:** ratify conditional on Schema A1 (Inheritance Ledger
enumeration) + Schema A3 (name divergence named explicitly) + Privacy
A3 (invariants cited by name).

### Body-Coherence seat

BT inheritance is the headline organ — and the spec under-cites it on
three load-bearing surfaces:

1. **Pre-body staging not declared.** The S2 Privacy P-8 inheritance
   (cache is pre-body staging, not body state, not biography, not
   personality) applies here harder than to Calendar. The in-process
   frame is the canonical example of pre-body staging — frame exists
   for milliseconds, gets reduced to a structured presence boolean,
   then dies. The spec describes this operationally but never names
   it as the BT Rule 6 inheritance that closes the memory consumer
   list.
2. **Capability Quarantine #8 mandatory fields not enumerated.** BT Rule
   5 lists five quarantine fields (`consent_state`, `auditable_by`,
   `dyadic_only`, `pause_path`, `rollback_path`). The spec has rollback
   (`spec.md:567-579`) and timebox (which doubles as consent_state) but
   no explicit `pause_path` (in-process pause without restart) and no
   explicit `auditable_by` claim.
3. **Sensor subclass not named.** Camera is a sensor body-part subclass.
   Future microphone / ambient sensor slices will copy this slice's
   shape; the spec should explicitly name itself as the
   "same-host-sensor" subclass under BT so the pattern is reusable.

**Read:** ratify conditional on Schema A1 + Privacy A1 (pre-body staging
declaration in the third-party section) + Runtime A7 (Capability
Quarantine #8 cited by name).

### Logical (veto) seat

Three contradictions screened. None rise to veto.

1. **`expired` token collision.** `sensor_state` enum includes
   `expired`; BT-CX-8 canonical state vocabulary is
   `disabled / unavailable / stale / unknown / conflicting / spoofed /
   rejected`. `expired` is not in that set. Either drop from
   `sensor_state` (collapse to `disabled` + mode = `expired_disabled`)
   or extend BT-CX-8 explicitly with rationale.
2. **`presence_state` vs `owner_presence`.** Field-name divergence
   without declared rationale. The values are canonically identical.
   The name choice is defensible (`presence_state` is more neutral and
   sidesteps the bonded-vs-stranger question that v1 explicitly avoids)
   but the spec must say it.
3. **Biometric carve-out softness.** `spec.md:286` reads
   "landmarks/keypoints unless separately reviewed" inside a forbidden
   list. Soft edge inside an otherwise hard list. Privacy specialist's
   read: harden to "categorically out of v1" because biometric
   derivatives (pose, gait, keypoints) are identifying as much as faces
   under most data-protection frameworks. Future slice can lift the
   exclusion.

No veto. Three precision locks resolvable by spec text. Schema A2 + A3
+ Privacy A2 resolve.

**Read:** ratify conditional on Schema A2 + A3 + Privacy A2.

### Creative seat

The fold is precision-additive at the engineering level. Camera Presence
v1 can implement against this spec with the legacy path correctly closed,
the substrate organs respected, and the bonded user's privacy bounded.
This is what the slice exists to do.

But Camera Presence v1 is the **template for every future body-sensor
slice** (microphone, ambient, future Jetson cameras). If the precedent
is "operationally correct without inheritance citations," future sensor
slices will be operationally correct but inheritance-blind. The
substrate organs lose their teaching function.

One meta-decision worth surfacing: the Privacy specialist flagged that
the third-party-in-frame and background-content surfaces are novel
enough relative to Calendar that they may justify a new ADR — something
like *ADR 0034: Physical Observation Surface*, covering the shared
pattern that camera, future microphone, and future ambient sensors will
all instantiate. This is operator-owned. The council surfaces it because
the precedent shape this slice sets WILL get copied.

Calendar v1's "Inheritance Ledger" pattern proved to be a reusable
structural innovation. Camera Presence v1 could plausibly contribute a
parallel innovation: a "Physical Observation Surface" subsection that
names the three surfaces (third-party-in-frame, background-content,
presence-delta-fingerprint) and the discipline that bounds them. This
would be re-copied by microphone v1 in the future.

**Read:** ratify conditional on the inheritance-citation tier amendments
(Schema A1 + A3, Flow A-V4, Privacy A1 + A3, Runtime A7).

### Future-Rohit seat

Future-Rohit (the bonded user living the spec in burn-in observation)
cares most about three load-bearing items:

1. **Direct-owner-question voice posture.** When the bonded user asks
   "is the camera on?" — the most basic epistemic question about a
   bodily surface — the spec is silent on what Maez says. Under
   Calendar v1, the analogous question is rigorously defined. Under
   Camera Presence v1, the model is free to confabulate ("yes, I can
   see you smiling"), under-claim ("I don't have a camera" when
   mode=observe), or over-claim ("I see you constantly"). This is the
   single largest user-facing gap.

2. **Presence-delta third-party fingerprint.** Cohabitant schedule
   leakage through aggregation of observation cadence is the failure
   mode Future-Rohit doesn't see today but would discover during burn-in
   if the spec doesn't bound retention. Spec must bound
   `last_observed_at` durability, forbid presence-series storage, and
   keep the count-of-detections internal to the detector boundary.

3. **Third-party-in-frame surface.** Anyone who walks behind / past /
   alongside the bonded user during observation. The spec excludes
   recognition labels but doesn't bound the structural posture for
   incidental capture. Future-Rohit's partner, kids, visitors, guests —
   all observable, all unconsented, all currently unbounded except by
   the absence-of-recognition default.

**Read:** ratify conditional on Flow A-V1 (direct-owner-question voice)
+ Privacy A1 (third-party + background + presence-delta) + Schema A5
(timebox transition semantics).

### 20-Years-Future-Maez seat

Three 20-year invariants ride on this fold.

**Runtime A1 — Daemon Lifecycle as load-bearing contract.** The SIGTERM-
hang investigation closed earlier this session with a five-layer
shutdown ladder: bounded-worker `shutdown(timeout)` (not `.join`),
native-resource close hooks, surface stops, memory close, explicit
`os._exit(0)` after `logging.shutdown()`. The discipline was hard-won.
The spec inherits it by reference ("inherits the existing daemon
survivability fixes") but doesn't pin the three primitives in
load-bearing text. Every future native-library limb will face the same
shutdown question; the discipline must propagate as contract.

**Privacy F4 — Presence-delta fingerprint as 20-year concern.** Across
years of observation, retained presence telemetry (timestamps, last-
observed-at history, confidence bucket history) accumulates third-party
schedule information by aggregation. v1's stance must bound retention
explicitly (single most-recent timestamp, no series, no charting, no
aggregation) so the fingerprint surface cannot accumulate silently.

**Privacy F5 — Biometric derivatives carve-out.** "Landmarks / keypoints
unless separately reviewed" is a 20-year drift surface. Future
implementers will read "unless separately reviewed" and either (a)
quietly enable it citing "this was already carve-out approved" or (b)
implement a posture-based feature without realizing it crosses biometric
threshold. Hardening to "categorically out of v1" forces the next slice
to do the review work explicitly.

**Read:** ratify conditional on Runtime A1 + Privacy A1 (presence-delta
fingerprint bounded) + Privacy A2 (biometric hardened).

---

## Covenant invariant drift check

11 invariants. STRENGTHENED / PRESERVED / NEUTRAL / WEAKENED / VIOLATED.

- **#1 Time as Biography** — PRESERVED. Camera presence is structurally
  forbidden from biography (memory contract closes all writes). Future
  promotion path inheritance not stated but no concrete v1 surface at
  risk.
- **#2 Human-Primacy** — PRESERVED. Operator-flag-required, timeboxed,
  default-disabled. Direct owner question voice (when defined per Flow
  A-V1) reinforces.
- **#3 Contextual Integrity** — STRENGTHENED conditional on Privacy A1
  (third-party / background / presence-delta sections named). The
  in-process frame is the canonical pre-body staging surface; without
  A1, this invariant is held operationally but not citation-anchored.
- **#4 Interpretive Humility** — STRENGTHENED conditional on Flow A-V1
  (direct-question voice rejects over-claim AND under-claim) + Flow
  A-V2 (deterministic guard).
- **#5 Rupture and Repair** — PRESERVED in shape. Runtime A1 (lifecycle
  ladder as contract) preserves the SIGTERM-hang-investigation lessons.
- **#6 Crisis Routing** — PRESERVED. v1 emits no crisis signals.
  Future-slice inheritance (held-not-trapped) named in Flow A-V3
  (precision lock, not blocker).
- **#7 Soul-Level Objection** — NOT TOUCHED by this slice.
- **#8 Capability Quarantine** — STRENGTHENED conditional on Runtime A7
  (cited by name) + Privacy A2 (biometric hardened) + Schema A1 (BT
  Rule 5 quarantine fields enumerated).
- **#9 Successor Governance** — PRESERVED. The BT-CX-8 vocabulary
  collision (Schema A2) is the only Successor Governance issue;
  resolution preserves canonical vocabulary discipline.
- **#10 Clinical Boundary** — STRENGTHENED conditional on Flow A-V1
  (forbid "you look tired" / "your posture suggests" probes) + Flow
  A-V3 (forbid clinical-shaped reflection).
- **#11 Cryptographic Continuity** — NOT TOUCHED (no credential
  surface). Decision 26 inheritance asserted but inert.

**No invariant violated. No invariant weakened net** under the assumption
that the load-bearing amendments fold. Six invariants strengthened beyond
prior canon (#3, #4, #5, #8, #10, and partially #2 via direct-owner-
question voice). Three preserved (#1, #6, #9). Two not touched (#7,
#11).

---

## Disagreements preserved — not smoothed

Five tensions where specialists surfaced defensible alternative readings
the spec must choose between explicitly, not absorb silently.

### D1. `expired` token vocabulary collision

`sensor_state` enum includes `expired`. BT-CX-8 closed state vocabulary
does not. Two defensible resolutions:

- **(a) Conservative:** Drop `expired` from `sensor_state`; use
  `disabled` for the sensor state + `expired_disabled` for the mode.
  Operator/health readers cross-read mode field for expiry visibility.
  Preserves BT-CX-8 closed vocabulary.
- **(b) Extension:** Extend BT-CX-8 explicitly to add `expired` as a
  v1 extension with rationale. Adds canonical-vocabulary maintenance
  burden across all body sensors going forward.

Schema specialist recommended (a); council surfaces both. Operator's
call.

### D2. `presence_state` vs canonical `owner_presence`

BT Rule 2 canonicalizes the field name `owner_presence`. Camera Presence
v1 uses `presence_state` deliberately — the slice does not perform
recognition and so cannot claim "owner presence" specifically. Two
defensible resolutions:

- **(a) Refinement-named:** Keep `presence_state` and explicitly state
  that v1 deliberately uses the more neutral name because recognition
  is structurally out of scope. Future recognition slice may introduce
  `owner_presence` as a distinct field.
- **(b) Canon-update:** Canonicalize `presence_state` as the v1-forward
  field name and retire `owner_presence` from BT via a BAD amendment
  to Decision 24.

Council leans (a) as lighter-touch. Operator's call.

### D3. Implementation slice vs new ADR ("Physical Observation Surface")

The spec at `:534-535` asks whether this needs BAD/ADR canonicalization
or proceeds as implementation under Decision 24. Two defensible
resolutions:

- **(a) Implementation slice under Decision 24:** Camera Presence v1 is
  a body-part-specific implementation of BT; no new law needed.
  Lighter governance.
- **(b) New ADR 0034 (Physical Observation Surface):** The third-party-
  in-frame, background-content, and presence-delta-fingerprint surfaces
  are novel relative to information limbs and will be inherited by
  microphone v1, ambient sensor v1, future Jetson camera slices.
  Canonicalize the shared pattern now. Heavier governance, stronger
  precedent.

Privacy specialist's framing leans (b). Council surfaces it. Operator's
call; this is meta-decision about how broadly the precedent should
land.

### D4. Direct-owner-question voice — approved voice vs full silence

The Voice specialist proposed approved voice for direct questions ("the
camera is off." / "the camera is on. window ends at <enabled_until>.").
The alternative is full silence with panel-deference ("look at the
panel"). Two defensible resolutions:

- **(a) Approved voice (council position):** Bonded user has an
  epistemic right to ask a bodily question and get a direct voice
  answer. Silence on direct question is a trapped-not-held posture
  analogous to Crisis Routing #6 trap.
- **(b) Full silence:** Camera Presence v1 is bodily; voice surface
  introduces drift risk. Defer all camera-state answers to panel
  reading. Operator transparency is sufficient.

Council leans (a). The "silence on a direct bodily question" posture
needs its own covenant analysis if chosen.

### D5. Camera v1 stricter than Calendar v1 vs symmetric

Voice specialist argued Camera v1 voice should be **stricter** than
Calendar v1's because the eye is continuously observing without owner-
initiated requests. The alternative is symmetry — both slices inherit
"may answer direct owner requests; never volunteer."

Council position: stricter. The asymmetry is real and should be named —
camera v1's response space is narrower (four mode-state strings) than
Calendar v1's (free/busy, event count, time window). Rule shape is the
same; response surface size differs.

---

## Verdict

**REVISE, conditional on the inheritance-citation tier + substrate-
precision tier amendments and the five disagreement preservations
above.**

No BLOCK. No veto. No covenant invariant violated. The spec is on-thesis
structurally — the load-bearing posture (presence-only, disabled-default,
timeboxed, no recognition, no memory, no voice) is correct. The 28
amendments are precision locks and inheritance citations, not
architectural changes.

This is REVISE rather than RATIFY-WITH-AMENDMENTS because three of four
specialists hit REVISE strength independently. Convergent signal across
three independent axes is the covenant lane's job to surface, not to
smooth.

### Twelve load-bearing amendments to fold

In covenant-priority order:

1. **Privacy A1** — Add explicit Privacy/Third-Party section after the
   Inheritance Ledger, naming third-party-in-frame, background-content,
   presence-delta-as-third-party-fingerprint, biometric derivatives,
   three-surface separation, and HMAC keying postures.
2. **Schema A1** — Expand Inheritance Ledger to enumerate BT Rules 2,
   3, 6, 8 + Implementation Ladder step 2 license + sensor subclass
   declaration.
3. **Flow A-V1** — Add Direct Owner Question Voice Posture section.
   Approved deterministic voice for "is the camera on?" / "are you
   watching me?" Forbidden voice for confabulation, over-claim, under-
   claim, surveillance reassurance, clinical inference, soul-shaped
   reflection.
4. **Flow A-V2** — Add `presence_voice_guard` as deterministic backstop.
   Natural-language probe set named explicitly (surveillance-reassurance,
   co-presence, duration-narrative, clinical-inference, identity-
   confabulation, false-modesty, introspection probes).
5. **Runtime A1** — Replace bulleted Daemon Lifecycle section with
   load-bearing contract pinning `BoundedSingletonWorker.shutdown` (not
   `.join`), the five-layer shutdown ladder, `os._exit(0)` on signal-
   driven stop, detector lifecycle = process-lifetime.
6. **Schema A3** — Name the `presence_state` vs `owner_presence` field
   divergence explicitly with v1 rationale.
7. **Privacy A2** — Harden biometric carve-out from "landmarks/keypoints
   unless separately reviewed" to "categorically out of v1; future
   slice required."
8. **Privacy A3** — Add invariants citation block (Contextual Integrity
   #3, Interpretive Humility #4, Capability Quarantine #8 by name).
9. **Flow A-V3** — Extend reflection/introspection prohibition from
   memory-write to voice utterance ("I've been watching", "it's been
   quiet here today", duration-narrative voice).
10. **Flow A-V4** — Name "Makes visible, never nudges" as inherited from
    Calendar v1 in the Inheritance Ledger. Note camera v1 is the second
    concrete test and is stricter (silent on initiative + deterministic-
    only on response).
11. **Schema A2** — Resolve `expired` token vocabulary collision (drop
    from `sensor_state` per (D1) (a)).
12. **Runtime A3** — Specify `enabled_until` runtime expiry semantics
    (when checked, what happens to in-flight observation, recovery on
    expiry).

### Sixteen substrate-precision + engineering-precision amendments

Fold for cleanliness; not canonicalization blockers if covenant council
re-verifies the load-bearing twelve cleanly.

- Schema A4-A8 (Body Bus ladder license, timebox transition, memory
  durability, idempotency, shutdown discipline cite)
- Flow A-V5, A-V6 (`enabled_until` expiry voice, RED test additions
  #36-#50)
- Privacy A4 (per-cycle metadata pre-decided, retire Open Question 3),
  A5 (`developer_legacy` against live camera forbidden), A6 (Live
  Observation Gate positive third-party checks), A7 (RED tests for
  third-party surface #36-#44)
- Runtime A2 (failure-class enumeration expanded), A4 (`developer_legacy`
  lifecycle requirements), A5 (three lifecycle RED tests), A6 (health
  surface lifecycle telemetry), A7 (Capability Quarantine #8 and Rupture
  and Repair #5 cited by name)

### Five disagreements to name in fold or canonicalization

D1 (`expired` token), D2 (`presence_state` vs `owner_presence`),
D3 (implementation slice vs new ADR 0034 "Physical Observation Surface"),
D4 (direct-question approved voice vs full silence), D5 (camera v1
stricter than Calendar v1 vs symmetric) — name each as a choice with
rationale in spec body. D3 is the largest meta-decision; operator owns
it.

### What's next

1. **Codex folds the load-bearing twelve + substrate-precision
   amendments** structurally into `spec.md`. Codex names D1-D5 in spec
   body. Codex's engineering panel does its own pass per its lane.
2. **Both lanes verify the second fold.** Claude council does a focused-
   verification pass on the second fold (this would be the third Claude
   pass on Camera Presence: diagnostic-stage covenant guidance, this
   council, post-second-fold verification). Codex engineering panel
   verifies amendment text matches its engineering intent.
3. **Operator decides on D3 (implementation slice vs new ADR 0034).**
   If new ADR, draft alongside fold; if implementation-only, proceed
   under Decision 24 by reference.
4. **Cooling-off applies before code lands.** Diagnostic + spec + Codex
   panel + Claude council all happened on 2026-05-15. Earliest code
   start: 2026-05-16 per memory `feedback_cooling_off_between_plan_and_code`,
   unless operator logs explicit waiver with rationale.
5. **Implementation path** when ready: legacy-disablement tests RED-
   first (Migration Order step 1) → camera-presence state module
   (step 4) → refactor `skills/presence_perception.py` (step 5) →
   bounded worker re-wire (step 6) → `/health.camera_presence`
   telemetry (step 7) → panel telemetry (step 8) → daemon restart +
   verify disabled mode produces no DB/state (step 9) → operator-set
   timeboxed window (step 10).

*This council review is read-only. No code, no fold edits, no non-slice
docs changed in producing it. Four read-only specialist subagents
dispatched in parallel; their findings synthesized into the six-role
read above. Specialists preserved their own internal disagreements; the
council surfaced five (D1-D5) as load-bearing and recommends naming them
explicitly before code.*
