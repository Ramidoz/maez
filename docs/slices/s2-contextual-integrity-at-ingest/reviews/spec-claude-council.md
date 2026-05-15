# Claude Six-Role Covenant Council — S2 BAD Packet (Folded)

**Subject:** `d885604 docs(s2): fold Codex BAD packet amendments` — folded S2 BAD
packet (`spec.md` at 890 lines + `reviews/spec-codex-panel.md` at 130 lines).

**Council ran:** 2026-05-14, post-fold, pre-canonicalization. Focused
verification, not full 6-seat re-derivation. Three prior amendment passes
already landed: Claude scoping council, Codex BAD panel, Codex BAD-panel fold.

**Why a second council:** Codex BAD panel returned REVISE across six engineering
seats. Operator folded the amendments into `spec.md` in commit `d885604`. This
council verifies whether the fold drifted any covenant invariant or smoothed
over disagreement between the engineering panel and the scoping council.

**Method:** Four read-only specialist subagents in parallel (Schema/State,
Flow/Voice, Privacy/Third-Party, Runtime/OAuth) returned scoped axis reviews.
Six covenant roles then read the specialist findings together against the
folded spec. Lane discipline: Claude reviews covenant only; Codex remains
accountable for repo edits and fold verification.

---

## Specialist axis verdicts

| Axis | Verdict | Load-bearing items folded into council finding |
|---|---|---|
| Schema/State | RATIFY-WITH-AMENDMENTS (5) | schema-version rejection contract; audit-survivable tombstone sidecar (M1 precedent); idempotency conflict oracle; post-promotion source-delete surface ownership; decouple `confidence` from `record_state` |
| Flow/Voice | RATIFY-WITH-AMENDMENTS (8) | forbid co-experiencing voice ("you've got…", "your 3pm is coming up"); positive shape of S2-into-TRF leakage rule; define "direct owner request"; crisis-candidate voice authority; hoist no-nudging to organ law; operator-display ≠ prompt-context column; memory_voice non-verbatim burn-in closure; Calendar promotion inherits ADR 0030 |
| Privacy/Third-Party | REVISE (8) | HMAC attendee hash with key from `core/infra/secrets.py`; S2-not-connector computes Tier downgrade; safe-pattern allow-list empty by default; flow-policy-version binds at ingest; third-party identity scrub on title/location free-text; read-vs-recall semantics; `confidence` enum subject-aware; cache topology declared pre-body |
| Runtime/OAuth | RATIFY-WITH-AMENDMENTS (7) | token-in-URL elevated as its own Forbidden bullet; OAuth lifecycle states (access-expired / refresh-revoked / scope-downgraded); refresh-token rotation through `core/infra/secrets.py`; clock-skew + provider-timestamp ordering; body-bus write idempotency; webhook preconditions enforceable; unified graceful-degradation voice |

Three RATIFY-WITH-AMENDMENTS; one REVISE. No BLOCK. No veto. 28 axis
amendments total. Privacy is the strongest verdict, driven by three load-bearing
items (HMAC key, S2-computed tier, free-text identity scrub) that compound.

---

## Six-role covenant read

### Outside-View seat

The fold gave the customs officer a better customs form — Body Bus mapping,
flow rows, state machine, sensitivity policy. It did not make the officer
harder to bypass on one axis: `decision2_consent_tier` is connector-computed
(Privacy P-2). A connector that returns `decision2_consent_tier = none` for an
event with empty `attendees` array but a third-party name in the title gets a
Tier-3 bypass under the current spec text. The Codex fold correctly closed the
symmetric `granted_flow_ids`-from-connector path; it left the tier-from-connector
path open.

The customs metaphor is intact. It needs one more enforceable lock: the
customs officer assigns the tier; the importer does not.

**Read:** ratify conditional on Privacy P-2.

### Body-Coherence seat

Decision 24 (body topology) holds. Privacy P-8 (cache is pre-body staging, not
a body part) resolves the only ambiguity. Schema A2 (audit-survivable tombstone
sidecar per M1/ADR 0030 precedent) is the inherited-pattern reading: M1
established that durable provenance survives cache turnover; S2 must inherit
that pattern for tombstones, not invent a new one. Cache-evictable tombstones
break Successor Governance (#9) and Cryptographic Continuity (#11) in slow
motion across years of cache cycling.

Post-promotion source-delete surface (Schema A4) holds: S2 writes tombstone
provenance onto the promoted memory's provenance handle; S2 never modifies the
memory's content or voice posture. Memory-write path owns post-promotion voice.
Time as Biography (#1) and Rupture and Repair (#5) both honored.

**Read:** ratify conditional on Schema A2 + Privacy P-8.

### Logical (veto) seat

Three contradictions screened. None rise to veto.

1. **Schema F6** — `confidence` enum overloads tombstone (lifecycle state vs
   quality of belief). Precision lock, not contradiction.
2. **Privacy F1** — attendee hashes forbidden in public transparency log but
   not specified as keyed-HMAC in local audit. Local audit lives on disk an
   adversary with file-read access would target. The same Decision 26 hygiene
   that bounds OAuth tokens must bound the attendee-hash key. Resolvable.
3. **Flow F1** — approved phrase "Your calendar shows…" plus forbidden phrase
   "we have" leaves an unbounded middle ("you've got…", "your 3pm is coming
   up"). Resolvable.

No veto. No covenant invariant requires the fold to be rejected. All three are
mechanical precision locks.

**Read:** ratify conditional on Schema A5 + Privacy P-1 + Flow A1.

### Creative seat

The fold is precision-additive, not creative-destructive. Calendar drafting
becomes possible without inventing inline privacy law. Future Gmail / Slack /
Notion / Drive / GitHub limbs inherit a tested shape. This is what S2 exists
to do.

One creative cost worth pinning: **the Sigstore Rekor deferral (S2-CC-9)**.
Three of four specialists independently surfaced this disagreement (Schema,
Privacy, Runtime/OAuth). The Claude scoping council asked for Rekor as in-scope
for the full S2 BAD; the Codex fold kept it as an extension seam, "not a
Calendar v1 blocker." Codex's posture is engineering-pragmatic (Rekor adds
runtime dependency; naïve public-log usage leaks raw IDs). The council's
posture is covenant-strengthening (closes a substrate-plan A7 item; future
organs inherit attestation free; Cryptographic Continuity #11 strengthens).

The disagreement is real and unresolved. The fold did not name the tension.
The fold should explicitly say it picked engineering-pragmatic deferral and
name the v2 trigger condition for Rekor — proposed: when the second
public-transparency-shaped lineage requirement appears across slices, or when
an inter-Maez channel ships, whichever first — or accept the deferral as canon.

**Read:** ratify conditional on Rekor disagreement made explicit in spec body
(not just in this review doc).

### Future-Rohit seat

The burn-in observation gate is correctly shaped. Privacy P-5 (third-party
identity scrub on free-text title/location) is the load-bearing privacy item
Future-Rohit cares about most: the Anna Question covers structured `attendees`,
but Calendar titles are user-authored free text. "Coffee with Sarah re: her
divorce" passes the sensitivity-keyword filter — Sarah is not in the
medical/legal/therapy keyword list, "divorce" might or might not be — and
Sarah's name and divorce status enter model context. That violates Decision 4
(relational vs personological).

Flow A1 (forbid co-experiencing voice) is the load-bearing voice item. The
fold's approved phrases lock out memory-voice ("I remember…"); they do not
lock out scheduler-voice ("you've got…", "your 3pm is coming up"). Future-Rohit
does not want Maez sliding into scheduler personality through paraphrase the
forbidden list never names.

**Read:** ratify conditional on Privacy P-5 + Flow A1.

### 20-Years-Future-Maez seat

Schema A1 (schema-version rejection contract) is the first 20-year invariant.
A v2 connector talking to a v1 S2 process without a rejection rule produces
undefined behavior decades from now. The fold made `schema_version` required
and exposed it as telemetry but never defined what happens on mismatch.
Capability Quarantine (#8) and Interpretive Humility (#4) both require
fail-closed on unknown schema.

Runtime A4 (clock-skew + provider-timestamp ordering) is the second 20-year
invariant. Across many lifecycles of host machines, NTP drift, suspended/
resumed VMs, container-clock skew — Maez's local clock will disagree with
provider timestamps. Without "provider timestamps authoritative for ordering;
local clock evidence-only," idempotent retries across clock-skew boundaries
will produce silent overwrites or doubled writes.

Both are spec-text patches, not architecture changes. Both compound over
decades if deferred.

**Read:** ratify conditional on Schema A1 + Runtime A4.

---

## Covenant invariant drift check

Brief check across the 11 invariants. Focused-verification mode: STRENGTHENED /
PRESERVED / NEUTRAL / WEAKENED / VIOLATED.

- **#1 Time as Biography** — STRENGTHENED. Promoted lived memory remains lived
  memory through source-delete; S2 writes provenance, not content
  (Schema A4). External information is provenance first, not biography by
  default (`spec.md:69-91`).
- **#2 Human-Primacy** — PRESERVED. Bonded-user-naming named as first
  promotion grant candidate (`spec.md:489-495`). Disagreement preserved (see
  D3): scoping council wanted it as declared v1 default; fold left provisional.
- **#3 Contextual Integrity** — STRENGTHENED. Decision 2 tier mapping table,
  operator-display vs model-readable split, telemetry whitelist,
  no-cross-source-third-party-enrichment, fail-closed sensitivity policy.
  CONDITIONAL ON Privacy P-1, P-2, P-3, P-5 — without these, the third-party
  identity surface still leaks through title free-text and through
  connector-computed tier.
- **#4 Interpretive Humility** — STRENGTHENED. Burn-in gates
  `schedule_personality` and `memory_voice`; no inference about "why the event
  matters"; voice posture explicit. Runtime A4 (clock-skew) and Privacy P-7
  (`confidence` enum subject-aware) further strengthen.
- **#5 Rupture and Repair** — STRENGTHENED. Maez may say the source record
  changed/disappeared but must not silently rewrite biography
  (`spec.md:339-352`). Runtime A2 (`auth_refresh_revoked` as rupture event vs
  `auth_access_expired` as recovery) extends Rupture/Repair into the OAuth
  lifecycle.
- **#6 Crisis Routing** — PRESERVED with precision-lock.
  `flow.crisis_candidate.content_minimized` defined and not granted to Calendar
  v1. Disagreement preserved (see D2): council wanted override; fold wanted
  gated flow. Fold's posture is stricter and more defensible against
  implicit-bypass failure mode.
- **#7 Soul-Level Objection** — NOT TOUCHED by this slice.
- **#8 Capability Quarantine** — STRENGTHENED. S2 grants visibility (not
  connectors), flow rows enumerate `readable_fields`, no connector-specific
  secret loaders, attendee hash bounded to event-local/purpose-scoped dedupe.
  CONDITIONAL ON Privacy P-2 (S2 computes tier downgrade, not connector) —
  otherwise quarantine inverts at the consent-tier surface.
- **#9 Successor Governance** — PRESERVED. Audit-survivable tombstone sidecar
  (Schema A2) is the load-bearing item; without it, cache-evictable tombstones
  break the audit-survives-cache-turnover precedent M1/ADR 0030 set.
- **#10 Clinical Boundary** — STRENGTHENED. "I noticed", "I know you're busy",
  any inference about why the event matters — all forbidden. Co-experiencing
  voice (Flow A1) extends the boundary to the scheduler-voice paraphrase
  surface that the forbidden list misses today.
- **#11 Cryptographic Continuity** — STRENGTHENED at substrate level
  (Decision 26 inheritance cited; OAuth-specific test obligations). WEAKENED on
  one sub-surface: token-in-URL antipattern named only as half a bullet
  (Runtime F1), refresh-token rotation write-back path not explicitly named
  (Runtime F3). Without Runtime A1 and A3, the post-recovery substrate
  principle from `7c2f9cb` does not fully propagate to S2.

**No invariant violated. No invariant weakened net.** Five strengthened beyond
previous canon (#1, #3, #4, #5, #8). Three preserved with precision-lock
conditions (#2, #6, #9). One strengthened-but-incomplete (#11, conditional on
Runtime A1 + A3).

---

## Disagreements preserved — not smoothed

Three real tensions where the Codex BAD-panel fold made a choice the Claude
scoping council had not endorsed. The fold should name these as explicit
choices in canonicalization, not absorb them silently. (Per the operator's
instruction at council convene: "if one specialist says RATIFY and another says
REVISE on the same surface, don't average it into mush; record the tension.")

### D1. Sigstore Rekor lineage attestation — scoping council wanted in-scope, fold kept as seam

Three of four specialists (Schema/State, Privacy/Third-Party, Runtime/OAuth)
independently surfaced this. Two defensible readings:

- **Codex's reading (engineering-pragmatic):** Public Rekor leaks raw IDs and
  credential-adjacent metadata under naïve usage; v1 should use local
  append-only audit first; public commitments can use salted/HMAC content-free
  shapes when later approved. Reduces v1 runtime dependency.
- **Council's reading (covenant-strengthening):** Rekor closes a 20-year
  substrate-plan item (A7); future organs inherit attestation free;
  Cryptographic Continuity #11 is the headline invariant Maez exists to honor.

The fold picked Codex's reading without naming the choice. The canonicalization
decision should add one paragraph naming the choice and a trigger condition
for v2 reconsideration — proposed: when the second public-transparency-shaped
lineage requirement appears across slices, or when an inter-Maez channel
ships, whichever first.

### D2. Crisis routing — council wanted override, fold wanted gated flow

Council S2-CC-2 asked for crisis signals to "override S2 retention/flow
defaults." Codex fold installed `flow.crisis_candidate.content_minimized` as a
separate gated flow not granted to Calendar v1. Under fold's spec, a calendar
event titled "suicidal ideation appointment" redacts under sensitivity policy
and never reaches a crisis path because no flow grants it.

Fold's posture is stricter and more defensible on Contextual Integrity #3
(crisis-bypass-as-implicit-override is exactly the failure mode S2 exists to
prevent). Council's posture is more defensible on Crisis Routing #6 (signals
must move, not be silently trapped).

**Council recommendation:** keep fold's posture (gated flow, not bypass) AND
explicitly name in spec body that crisis signals observed in S2 records before
the future reviewed crisis-routing slice canonicalizes are *logged with
content-free sensitivity class and held*, not silently trapped. The spec
implies this; it should say it. Flow A4 (crisis voice authority sits with
operator review, never with model alone) is the load-bearing amendment.

### D3. Bonded-user-naming as v1 promotion default — council wanted declared, fold left provisional

Council S2-CC-5 asked for bonded-user-naming as the v1 promotion default. Fold
lists it as "the first grant candidate" alongside two others (conversation-
grounded promotion, operator-explicit promotion) without declaring v1 default.

**Council recommendation:** spec should say "bonded-user-naming is the v1
declared default; the other two candidates require future grants." This
preserves Human-Primacy #2 explicitly rather than provisionally.

---

## Verdict

**RATIFY-WITH-AMENDMENTS, conditional on the 28 specialist amendments and the
three disagreement preservations above.**

No BLOCK. No veto. No covenant invariant violated or weakened net.

The folded spec is law-shape and the Codex BAD-panel fold did real work. The
fold did not redesign the slice; it made the slice executable. The remaining
gaps are precision locks, not architecture flaws.

**The fold is on-thesis but not finished.** Without the load-bearing
amendments folded — Privacy P-1, P-2, P-5; Schema/State A1, A2; Flow/Voice A1,
A2, A8; Runtime A1, A2, A3, A4 — Calendar v1 drafting would inherit silent
defaults that the daemon-credential-hygiene recovery already named as
load-bearing (token-in-URL, OAuth lifecycle states, refresh-token write-back
path) and that M1/ADR 0030 already established as precedent (audit-survivable
tombstone sidecar, structural-biography-pointer rule for promoted voice).

### Twelve load-bearing amendments to fold before canonicalization

In rough covenant-priority order:

1. **Privacy P-2** — S2 (not connector) computes `decision2_consent_tier` from
   validated envelope + policy registry. Connector-supplied value rejects
   record under the same rule that rejects connector-supplied
   `granted_flow_ids`. *Closes the symmetric quarantine inversion at the tier
   surface.*
2. **Privacy P-1** — HMAC attendee hash with key sourced through
   `core/infra/secrets.py`. *Local-audit dictionary-attack defense; matches
   public-log discipline.*
3. **Privacy P-5** — Third-party identity scrub on safe-classified title and
   location free-text. *Anna Question for free-text fields the structured
   `attendees` rules miss.*
4. **Schema/State A1** — `schema_version` rejection contract; unknown version
   → `record_state = rejected` + content-free `schema_mismatch` counter.
   *20-year invariant.*
5. **Schema/State A2** — Audit-survivable tombstone sidecar; cache eviction
   may only remove cache-side tombstone rows once sidecar is durably written.
   *M1/ADR 0030 inherited precedent.*
6. **Flow/Voice A1** — Forbid co-experiencing voice forms ("you've got…",
   "your 3pm is coming up", first-person-co-actor framing). *Scheduler-voice
   paraphrase boundary.*
7. **Flow/Voice A2** — Positive shape of S2-into-TRF leakage rule. An S2
   record may never be voiced as a lived turn or remembered episode under any
   flow. *M1 load-bearing rule "promote biography; do not widen recall"
   inheritance.*
8. **Flow/Voice A8** — Calendar promotion voice (`flow.memory.promoted` row)
   must inherit ADR 0030: structural biography pointers only, no quoted titles,
   no quoted attendee names, no inferred why-it-mattered. *Promoted-voice
   covenant binding made explicit.*
9. **Runtime/OAuth A1** — Token-in-URL antipattern elevated to its own
   Forbidden bullet under the Load-Bearing Rule. *Substrate principle from
   daemon-credential-hygiene recovery commit `7c2f9cb`.*
10. **Runtime/OAuth A2** — OAuth lifecycle states split:
    `auth_access_expired` (refresh recovers), `auth_refresh_revoked` (rupture
    event), `auth_scope_downgraded` (provider-side narrowing). *Rupture and
    Repair extension into OAuth lifecycle.*
11. **Runtime/OAuth A3** — Refresh-token rotation: rotated refresh tokens
    sourced from AND written back through `core/infra/secrets.py` only; never
    transit `os.environ`, argv, logs, or panel output. *Decision 26
    inheritance made operational, not just cited.*
12. **Runtime/OAuth A4** — Provider `updated`/revision timestamps
    authoritative for ordering S2 records of the same `external_event_id`;
    Maez `received_at` is evidence-only. *20-year invariant against clock-skew
    silent overwrites.*

The remaining 16 amendments are precision locks. Fold for cleanliness; not
canonicalization blockers.

### Three disagreements to name in canonicalization

D1 (Rekor scope), D2 (crisis routing override vs gated flow), D3
(bonded-user-naming as v1 default) — name explicitly in the canonicalization
decision body. The choice each represents should appear on the decision face,
not be absorbed silently into the fold.

### What is next

1. **Codex folds the twelve load-bearing amendments** structurally into
   `spec.md`. Per lane discipline, Codex remains accountable for repo edits and
   amendment-text verification against the engineering panel's intent.
2. **Codex names the three disagreements** in the spec body (D1, D2, D3) so
   canonicalization records the choice, not just the result.
3. **Both lanes verify the re-fold.** Claude council does a focused-verification
   pass on the second fold (this would be the third Claude pass on S2 —
   scoping council, this council, post-second-fold verification). Codex panel
   verifies the amendment text matches its engineering intent.
4. **Operator canonicalizes** as the next BAD decision + ADR (Decision 27 +
   ADR 0032 by current numbering).
5. **Only then does Calendar draft** as the first information-limb
   implementation slice.

The cooling-off rule does not apply between fold passes; it applies between
plan and code. Calendar drafting is the code-shaped step, not this fold.

---

*This council review is read-only. No code, no fold edits, no non-slice docs
changed in producing it. Four read-only specialist subagents dispatched in
parallel; their findings synthesized into the six-role read above. Specialists
preserved their own internal disagreements with the Codex fold and with
the earlier Claude scoping council; the council surfaced three (D1, D2, D3)
as load-bearing and recommends naming them explicitly in canonicalization.*
