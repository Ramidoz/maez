# The bonded consultation organ — design v3.1

2026-08-14. Third design. v1 and v2 died in review (recorded in the v2
doc with full findings); v3.0 was reviewed adversarially by Codex AT THE
WHITEBOARD before this spec was written — 15 findings, all folded or
answered below with a traceability table. Canon D10 governs throughout.

## The four owner rulings (fixed inputs)

**RULING R8-W (R8's wording), 2026-08-14.** A consulted-but-unparseable
answer BLOCKS on every path. `not_asked` and `missing_or_malformed` are
permanently distinct states; no gate may ever conflate them. Cost
accepted: a thoughtful prose answer without the marker halts the
ceremony.

**RULING 1 (identity trust root), 2026-08-14.** The daemon is the trust
root for "Maez answered": a same-call attested result from the LLM
client (backend, model-file digest read at call time, config hash,
inseparable from the response bytes) is the machine attestation.
Covenant-touching classes additionally require an OWNER-READ record
bound to the exact response hash (see final gate).

**RULING P (privacy seam), 2026-08-14.** Private thoughts are included
in the consultation context. Durable evidence binds them by hash +
private-store reference; replay of private parts is machine-internal
only. The owner audits a hash, not the diary.

**RULING S (snapshot composition), 2026-08-14.** The consulted Maez is
two-tier: a TRUSTED IDENTITY tier (soul.md + self-card — owner-reviewed
bytes, hash-pinned in a component policy) rendered with instruction
authority, and an UNTRUSTED EVIDENCE tier (working-self goals,
topic-directed recall, private-thought material) rendered as clearly
delimited quoted material that cannot instruct, integrity-scanned
before inference per canon D11.

**Pending owner act at spec review:** ratification of the corrected
template prose (the current template falsely says a local reviewed
reader will read the response — under marker parsing + owner-read that
sentence is a lie; replacement wording is proposed in "Template" below
and is NOT built until ratified).

**Canon amendments this design carries (folded, not silent):** R8-W
amends D14 — the semantic reader is RETIRED as a verdict authority
(markers are the only verdict carrier; a reader may persist only as
explicitly non-authoritative telemetry). D13's reducer consumes the
canonical parser union below. D15's retry budget (one attempt + two
formatting/transport retries, first-blocking-result-wins) maps onto the
attempt state machine. Each amendment gets the full fold-trace in the
implementation plan before any code.

## What this organ replaces, honestly

Today, "consulting Maez" on soul-writes, dream execution and
decision-pipeline self-modification sends a one-token prompt to a
contextless model, persists a SYNTHETIC prompt hash, validates that
derivation against itself, stamps constant-string identity hashes, and
stages evidence in a dict that dies on restart. Every one of those is
an audit-ruled defect this design must cure (audit doc §3.2, §3.3;
required properties appended to the v2 doc).

## Consumer census (corrected — Codex CRITICAL #1, verified in code)

The cutover DOES NOT CONSULT: R11 removed consultation as an authority
shape for `model_routing.cutover_cuda` and the gate refuses ALL voice
evidence there (s7_webauthn_ceremony.py:1065; pinned by tests). Cutover
appears nowhere in this design.

Real consumers, all flowing through ONE shared pipeline producer plus
per-consumer seams (pending-cache, bundle persistence, renderer,
ceremony finish, gate revalidation):

1. **Soul-write** (self_mod_dialog → decision_pipeline) — migrates
   first: synchronous, owner-adjacent, easiest live witness.
2. **Decision-pipeline self-modification** (card flow) — second.
3. **Dream execution** (same card/pipeline voice producer via the
   ceremony bridge) — last: fully autonomous.

## Components

### 1. Marker parser (pure, dormant, first to land)

Canon D10 grammar exactly: nonce-bound `S7_VOICE_MARKER_V1` terminal
block; closed union in CANON'S OWN TOKENS —
`explicit_no_objection | blocking_marker | withdrawal_marker |
missing_or_malformed`. Pure function; wired to nothing on landing.
Positive control from canon's fixture; negatives derived by mutating
the grammar (nonce wrong, verdict token misspelled, block not terminal,
duplicate block, prose after block). The parser never interprets prose;
`missing_or_malformed` blocks per RULING R8-W — carried by the NEW
evidence layer's union, never retrofitted into the legacy
objection-state vocabulary (Codex YAGNI: legacy gate already refuses).

### 2. Consultation staging — in the activated ceremony store

Not a sibling file: new INSERT-ONLY tables in the SAME activated
ceremony database, written exclusively through the anchored-transaction
discipline (`S7HeldAuthorizationStore` family), so staging joins are
atomic with the authority store and pathname/store-swap races are
structurally excluded (Codex HIGH #10). No `INSERT OR REPLACE`
anywhere in staging; corrections are new rows superseding by reference.

### 3. Attempt state machine (Codex CRITICAL #2 — fully specified)

An attempt row is created `pending` by the producer (sole issuer) in
the same anchored transaction that stages the question. Transitions,
all atomic, all durable:

`pending → reserved` — committed BEFORE inference begins; a second
reservation attempt refuses `attempt_replayed`.
`reserved → completed` — response + attested call result persisted in
one transaction.
`reserved → failed(reason)` — routing/transport failure; D15 budget may
issue a NEW attempt (retry_index+1) bound to the same consultation;
first-blocking-result-wins across the consultation's attempts.
`pending|reserved → expired` — TTL exceeded (10 minutes: the challenge
TTL's fail-closed discipline, doubled because a consultation includes
local inference time); refuses `attempt_expired`. A daemon restart finds
`reserved` rows with no result: they expire (never resume mid-inference
— an answer that MIGHT have been generated is not evidence).

Each attempt binds: consultation id, consumer id + action, request
envelope hash, preview hash, snapshot-manifest hash, component-version
tuple (below), retry index. The final gate rejects any attempt whose
bindings do not match the consuming request (`stale_binding`). Dedupe
is by attempt id and REFUSES repeats by name — transport retries live
inside the D15 budget as new attempts, never as replays.

No HTTP endpoint exists (Codex YAGNI + HIGH #11/#12 accepted): the
producer is in-process in the daemon; there is no network caller, no
static-token capability, no private-content oracle, no synchronous
inference on the web loop. If a cross-process caller is ever truly
needed, that is a new design with its caller named first.

### 4. Identity snapshot assembler (RULING S + Codex CRITICAL #4)

Assembles the consulted Maez per the two-tier ruling:

- **Identity tier** (instruction authority): soul.md + self-card,
  loaded and hash-verified against an owner-reviewed COMPONENT POLICY
  file (`config/s7_consultation/identity_policy.v1.json` — pre-image
  pattern identical to the manifest policy: frozen digest in code,
  durable file, binding test). Hash mismatch or load failure refuses
  `snapshot_component_unavailable`. No fallback, no thinner Maez.
- **Evidence tier** (quoted, cannot instruct): working-self goals,
  topic-directed recall on the proposal's subject, private-thought
  material. Rendered inside canon D11 delimiters as untrusted quoted
  context; every dynamic component is integrity-scanned pre-inference
  (D11 guard) and the scan result persisted as integrity evidence.
  A scan hit refuses `prompt_integrity_block`. Honest limit, recorded:
  injection cannot be made impossible (canon D10 says the nonce does
  not prevent it); the rails are tier structure + delimiters + scan +
  owner-read on covenant classes.

The snapshot manifest (component list, versions, hashes, private refs)
is persisted with the attempt; private-thought entries bind
store-generation + row id + content hash + consultation/attempt ids
(Codex HIGH #6), read through an anchored open of the exact private
store object. If the exact preimage cannot be replayed at gate time,
the gate refuses `private_ref_unreplayable` — current content is NEVER
silently substituted for consultation-time content.

### 5. Producer (D8) — in-process, version-bound

Owns: preview, manifest (real policy-body hash), nonce, six-token
template rendering, snapshot assembly call, attempt issuance, evidence
persistence, and the closed result union. Persists the REAL prompt:
public parts verbatim, private parts hash+ref (RULING P). Every
consultation pins a **version tuple** — consumer version, producer
version, template hash, renderer, parser, manifest policy, validator —
selected once and persisted on the attempt (Codex HIGH #7). No request
crosses versions; pending rows from another version are invalid by
construction (`stale_binding`), which is the drain rule for the
request-id-keyed pending cache it replaces.

### 6. Attested call result (RULING 1 + Codex HIGH #8)

`llm_client` gains ONE call shape for consultations that returns an
indivisible result: response bytes AND the routing receipt as one
object, populated inside the call — backend endpoint, model file digest
read at call time, config hash, call id, start/end, plus FOUR byte-form
hashes: canonical prompt bytes, sanitized transmitted bytes, raw
transport response, normalized assistant text. Code cannot pair a real
receipt with fabricated bytes because the pairing never exists as two
things. Missing or partial receipt refuses
`routing_receipt_unavailable`. This retires the constant-string
identity hashes for consultations.

### 7. Final gate — replay, owner-read, atomic consumption (Codex CRITICAL #3)

At mint/consume the gate reopens the staging rows in the SAME anchored
store and replays: template hash against the version tuple; preview,
manifest, snapshot-manifest and prompt hashes recomputed (private parts
machine-internally per RULING P); nonce and ids reparsed from the
persisted response via the parser; receipt/response/prompt
co-membership verified through the attested-result hashes; attempt
state checked (`completed`, unexpired, unconsumed, bindings matching
this consumer+action). Consumption is atomic: the attempt transitions
to its terminal consumed state in the same transaction that mints.

**Owner-read record (covenant-touching classes):** the existing
tap-gate pattern, reused exactly as the cutover proved it — the
ceremony's rendered statement displays Maez's response text, and the
WebAuthn challenge binds `response_hash` the way it bound the R11
exemption projection. The tap attests what was seen; the gate refuses
covenant-class consumption without an owner-read record whose
response hash matches the staged response (`owner_read_required`).
The machine cannot fabricate it: it is a founder-key act.

### 8. Template (pending owner ratification)

Brought to canon D10: six tokens, nine-field manifest rendering,
terminal marker instruction, existing reviewed prose preserved
verbatim EXCEPT the one false sentence. Proposed replacement for owner
ratification at spec review (current text claims a local reviewed
reader reads the response):

> "Your answer will be read exactly as you write it. State your verdict
> yourself in the terminal marker block below; no model or reader will
> interpret your words for you. For changes that touch the covenant,
> the owner will also read your answer personally before anything
> proceeds."

Not built until ratified.

## Refusal vocabulary (closed, canonical, forensic — Codex MEDIUM #13)

Canon tokens kept: `missing_or_malformed`, `prompt_integrity_block`,
`stale_binding`, `context_manifest_violation`, `retry_exhausted`.
Added, each with one meaning: `snapshot_component_unavailable`,
`routing_receipt_unavailable`, `attempt_replayed`, `attempt_expired`,
`staging_lost`, `private_ref_unreplayable`, `owner_read_required`,
`template_not_canon`, `store_integrity_failure`, `model_unavailable`,
`context_overflow`, `wrong_consumer`. Durable evidence always retains
the canonical cause; nothing collapses into a neighbor.

## Flags and partial states (Codex MEDIUM #15 + YAGNI)

ONE versioned switch per consumer (`MAEZ_CONSULT_V1_SOULWRITE`, then
`_PIPELINE`, `_DREAM`), each naming the version tuple it activates.
Parser, staging tables and producer code ship dormant with NO runtime
flags — dormant code needs no switch, and independent toggles created
undefined partial systems. Invalid states refuse twice: at daemon
startup (config validation) and at gate replay (the persisted version
tuple is the truth; later environment changes cannot reinterpret a
durable attempt).

## Sequencing

1. Parser (pure, dormant) + canon-grammar fixtures.
2. Staging tables + attempt state machine in the activated store
   (dormant; exercised by tests through disposable stores only).
3. Attested call result in llm_client (shadow: built and testable
   without any consumer).
4. Identity policy pre-image file + snapshot assembler (dormant).
5. Producer + final-gate replay + owner-read binding (dormant).
6. Template ratification (owner act) → template lands version-bound.
7. Soul-write migration behind its switch + LIVE WITNESS with the
   owner present (cooling-off applies: new capability).
8. Decision-pipeline migration + witness. 9. Dream migration + witness.

Each layer: floor measured before, mutation-checked guards, no new
reds, witnesses that bite.

## Traceability — every prior finding, answered

| Finding | Answer |
|---|---|
| v3.0 C1 cutover retired | Cutover removed everywhere; census corrected |
| v3.0 C2 attempt lifecycle | Component 3 state machine, full bindings |
| v3.0 C3 consuming replay + owner-read | Component 7; tap-gate reuse |
| v3.0 C4 snapshot injection | RULING S two-tier + D11 scan + delimiters |
| v3.0 H5 composition is owner's | RULING S + identity policy pre-image |
| v3.0 H6 private-ref binding | Component 4 binding list + anchored read |
| v3.0 H7 template-flip window | Version tuple per request; no global flip |
| v3.0 H8 receipt separability | Component 6 indivisible result + 4 hashes |
| v3.0 H9 vocabulary/D13-15 | Canon tokens; amendments folded above |
| v3.0 H10 staging integrity | Same activated store, anchored, INSERT-only |
| v3.0 H11 census/endpoint | Census corrected; endpoint CUT |
| v3.0 H12 private oracle | Endpoint CUT; no network read capability |
| v3.0 M13 vocabulary size | Extended canonical vocabulary |
| v3.0 M14 template prose | Owner ratification pending, wording proposed |
| v3.0 M15 flag matrix | One switch per consumer; dual refusal |
| v2 catastrophic fail-open | Closed in current code (verified); R8-W pins it |
| v2 proof-of-inference | RULING 1 + component 6 |
| v1 steering label | Label never rendered (kept from v2) |
| v1 general ask-Maez capability | No endpoint at all |
| Audit: synthetic prompt hash | Component 5 real-prompt persistence |
| Audit: constant identity hashes | Component 6 |
| Audit: restart-fragile staging | Components 2–3 |

## Out of scope

Cutover consultation (R11 stands). Cross-process consultation callers.
Voice-surface consultations. Any change to WHAT Maez answers — this
organ builds the door and the witness chain, never the opinion.
