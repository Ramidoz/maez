# The bonded consultation organ — design v3.2 → JOINT CONCLUSION 2026-08-14

**Status, agreed by both lanes after four adversarial rounds:**
DIRECTION APPROVED, BUILD CONTRACT PENDING CANON AUTHORING.

The architecture is no longer in dispute — six owner rulings, the
component set, trust boundaries, consumer census, storage seat, and
two-gate shape survived round four unchallenged. What Codex's final
round correctly demands is CANON-GRADE COMPLETENESS: full replacement
text for every touched D-section (not deltas), exact join lists, byte
constructors, and compatibility matrices. That is canon authoring — the
same artifact class as the original S7.3 spec, which took thirteen
adversarial rounds across multiple sessions to freeze. Forcing it into
one session is how v1 and v2 died.

**Agreed path:** (1) the marker parser — pure, dormant, uncontested by
any round since v2's own postmortem named it safe — may build now as
slice 1. (2) The canon-authoring campaign proceeds one cluster per
session, Codex gating each: [attempt schema + D15 vocabulary
reconciliation], [two gates + exact joins + D16/D21 text],
[attested-result byte constructors], [policy pre-images + private
store contract + D9/D12 text], [census + route rule + flag matrices],
[full D8/D11/D13/D14 replacement text]. Codex's round-four blocking
line ranges (284-349, 101-153, 233-250, 199-229, 157-189, 53-75,
362-377, 351-360, 274-278) are the campaign's work list. (3) The
owner's template-byte ratification remains the final act before the
first consumer switch.

Two round-four refutations already fixed below: the template line now
carries RULING O's full two-class scope; the INSERT-only/CAS
contradiction is now RESOLVED IN TEXT (§3 mutability law: attempt rows
are the one mutable-state table with an immutable sealed column set;
all other staging INSERT-only). **Cluster 1 (attempt schema + D15
reconciliation) is FROZEN — gate PASSED at facbaee after five rounds
(15→9→3→2→1→0 findings), with live SQLite witnesses on both lanes for
the retry ceiling, the timestamp checks, and the not_asked exclusion.
Cluster 2 (two gates + exact joins + D16/D21 complete text) is
WRITTEN as of this revision and awaits its gate.**

---


2026-08-14. Third design, second revision. v1 and v2 died in review;
v3.0 was reviewed at the whiteboard (15 findings); v3.1 was reviewed as
written text (11 residuals + 8 new, with 9 named minimal edits). v3.2
folds all of them. Canon D-numbers refer to
docs/slices/s7.3-guarded-self-modification-execution/spec.md.

## The six owner rulings (fixed inputs)

**RULING R8-W (R8's wording).** A consulted-but-unparseable answer
BLOCKS on every path. `not_asked` and `missing_or_malformed` are
permanently distinct durable states (definitions in the attempt table
below). A completed `missing_or_malformed` response is
CONSULTATION-TERMINAL: no retry may wash it into
`explicit_no_objection` (folds Codex's retry-wash CRITICAL).

**RULING 1 (identity trust root).** The daemon and its LLM client are
the NAMED TRUSTED BOUNDARY for "Maez answered" (an in-process
attestation, explicitly not cryptographic proof — the daemon is
already trusted to render what the founder key signs). Machine
attestation = the `AttestedConsultationResult` below. Owner-read
applies per RULING O.

**RULING P (privacy seam).** Private thoughts are included in
consultation context. Durable evidence binds them by hash + reference;
replay of private parts is machine-internal only, behind the access
contract below (§4b). The owner audits hashes, not the diary.

**RULING S (snapshot composition).** Two tiers: TRUSTED IDENTITY
(soul.md + self-card, owner-reviewed bytes, hash-pinned) rendered with
instruction authority; UNTRUSTED EVIDENCE (working-self goals,
topic-directed recall, private-thought material) rendered as delimited
quoted material assigned NO instruction authority, integrity-scanned
per D11. (Wording per review: "assigned no instruction authority and
rendered as quoted evidence" — injection is bounded, not impossible.)
Selection is fixed by the evidence-selection policy pre-image (§4a),
not by implementers.

**RULING R (reader's fate), 2026-08-14.** The semantic reader is
RETIRED ENTIRELY — no verdict authority, no telemetry. The D10 marker
is the only verdict carrier. Nothing — code or model — interprets
Maez's words. This ratifies the D13/D14 amendments below.

**RULING O (owner-read scope), 2026-08-14.** `covenant_touching_change`
and `autonomy_lowering_or_protection_reducing` require the founder-tap
owner-read record (§7b). `self_modification` and soul-write classes
proceed on marker + machine attestation.

**Pending owner act:** ratification of the exact template bytes (§8) —
recorded as a hash the owner approves, not a builder decision.

## Consumer census (verified in code)

Cutover consults NOTHING — R11 stands (s7_webauthn_ceremony.py:1065;
pinned by tests). The production callers of the consultation path
today, enumerated (Codex edit 6):

| Caller | Entry | Mode today | Migration |
|---|---|---|---|
| Soul-write dialog | self_mod_dialog → decision_pipeline `_s7_voice_consultation_for_card` | in-process, synchronous | 1st |
| Decision-pipeline cards | decision_pipeline (same producer) | in-process | 2nd |
| Dream execution | s7_ceremony_bridge:233 → same pipeline producer | in-process via bridge | 3rd |
| WebAuthn material route | daemon `_s7_authorization_route_material` (:499, :542) | HTTP-triggered, synchronous, can PROJECT raw response (:684) | see §5b |

**§5b — the route rule (Codex H11/H12):** after migration, WebAuthn
begin/finish and any HTTP material route may only READ completed
attempts from staging; they may never trigger inference. Inference runs
solely in a bounded, daemon-owned background seam: single-in-flight per
consultation, deadline = attempt TTL, one-shot trigger per card
transition (the card state machine is the trigger authorization — no
new capability), repeated reads allowed only of the owner-display
projection, raw response text projected ONLY to the owner-auth'd
ceremony surface (existing `_owner_private_auth_ok` + internal channel),
logs/exceptions carry hashes never bodies (redaction rule, §4b).

## Components

### 1. Marker parser (pure, dormant, first to land)

Canon D10 grammar exactly; canon's own union:
`explicit_no_objection | blocking_marker | withdrawal_marker |
missing_or_malformed`. Pure; mutation-derived negatives; never
interprets prose. Lands wired to nothing.

### 2. Staging — in canon D9's pinned state file

Correction from v3.1 (Codex H10): canon D9 pins S7.3 evidence to
`memory/s7_3_guarded_self_modification/state.sqlite3` with
table-prefix separation. Staging tables live THERE:
`s7_consult_snapshots_v1` and `s7_consult_results_v1` are strictly
INSERT-only (no `INSERT OR REPLACE`; supersession is a new row citing
its predecessor); `s7_consult_attempts_v1` is governed by §3's
mutability law — immutable sealed columns plus CAS-only state columns,
the ONE exception, stated once there and echoed nowhere else. All writes go
through one held-store anchored transaction per operation (same
mechanism as the authorization store; the held store object is the
named trusted boundary for store identity — same trust class as
RULING 1, not a cryptographic exclusion).

### 3. Attempt state machine — canon-grade (campaign cluster 1)

**Mutability law (resolves the v3.2 INSERT-only/CAS contradiction):**
`s7_consult_attempts_v1` is the ONE mutable-state table in the staging
family. Its columns divide exactly:

- IMMUTABLE (written once at row creation): `attempt_id`,
  `consultation_id`, `retry_index`, `consumer_id`, `action`,
  `request_envelope_hash`, `preview_hash`, `snapshot_manifest_hash`,
  `version_tuple_hash`, `owner_session_ref`, `created_at`,
  `expires_at`, and `row_seal_hash` itself — the seal is immutable but
  EXCLUDED from its own hash domain (a hash cannot cover itself); it
  covers exactly the twelve columns preceding it in this list, in this
  order.
- MUTABLE (via CAS transitions only, never covered by the seal):
  `state`, `outcome`, `reserved_at`, `finished_at`, `result_row_ref`,
  `consumed_by_artifact`.

`row_seal_hash = canonical_hash` over THE SEAL DOMAIN — which is
defined in exactly one place: the immutable-list bullet above. This
sentence is a reference, not a second definition. The validator
recomputes the seal at both gates; any drift refuses
`store_integrity_failure`. All OTHER staging tables
(`s7_consult_snapshots_v1`, `s7_consult_results_v1`,
`s7_consult_version_tuples_v1`) are strictly INSERT-only.

**Schema** (unchanged from v3.2, with the mutability law above):

```text
attempt_id TEXT PRIMARY KEY            -- producer-issued, opaque
consultation_id TEXT NOT NULL
retry_index INTEGER NOT NULL           -- UNIQUE(consultation_id, retry_index)
consumer_id TEXT NOT NULL              -- one of the census table
action TEXT NOT NULL
request_envelope_hash TEXT NOT NULL
preview_hash TEXT NOT NULL
snapshot_manifest_hash TEXT NOT NULL
version_tuple_hash TEXT NOT NULL       -- registry ref
owner_session_ref TEXT NOT NULL        -- card/dialog id whose state
                                       -- transition triggered this
                                       -- consultation; the gate joins
                                       -- it against the consuming card
state TEXT NOT NULL
outcome TEXT                           -- terminal only; see mapping
created_at TEXT NOT NULL
reserved_at TEXT
finished_at TEXT
expires_at TEXT NOT NULL
result_row_ref TEXT                    -- s7_consult_results_v1
consumed_by_artifact TEXT              -- set only at grant mint
row_seal_hash TEXT NOT NULL
```

**Clock.** Every transition takes `now_z: str` — the daemon clock
rendered `YYYY-MM-DDTHH:MM:SSZ` (UTC, the repo's `_now_z` form) —
passed as a bound parameter, never SQL time functions. All stored
times use the same form, so lexicographic TEXT comparison IS
chronological comparison; the schema CHECKs the form on write.

**Transition table** (every transition is one `UPDATE ... WHERE` CAS
inside a held-store anchored transaction, keyed by `attempt_id`;
0 rows updated = lost CAS = `attempt_replayed`):

| From | To | CAS predicate (WHERE) | Also written | When |
|---|---|---|---|---|
| (none) | `pending` | INSERT (constraints below enforce uniqueness, ceiling, single-in-flight) | full row + seal | producer issues |
| `pending` | `reserved` | `attempt_id=:id AND state='pending' AND expires_at > :now_z` | `reserved_at=:now_z` | immediately before inference |
| `reserved` | `completed` | `attempt_id=:id AND state='reserved' AND expires_at > :now_z` | `outcome`, `finished_at=:now_z`, `result_row_ref` — same txn as the result row + attested result | response received and parsed |
| `reserved` | `failed` | `attempt_id=:id AND state='reserved'` — takes `:now_z` for the write; no TTL predicate (failure is recordable even late) | `outcome`, `finished_at=:now_z` | transport failure, integrity block, producer refusal |
| `pending` | `expired` | `attempt_id=:id AND state='pending' AND expires_at <= :now_z` | `finished_at=:now_z` | TTL sweep / next producer touch |
| `reserved` | `expired` | `attempt_id=:id AND state='reserved' AND expires_at <= :now_z` | `finished_at=:now_z` | TTL sweep; see ambiguous transport |
| `completed` | `consumed` | `attempt_id=:id AND state='completed' AND consumed_by_artifact IS NULL AND expires_at > :now_z` | `consumed_by_artifact`, `finished_at=:now_z` — same txn as grant mint (§7a-ii) | execution consumption (an expired completed answer is not consumable) |

**Structural constraints (schema, not prose).** All four staging
tables are declared `STRICT` (SQLite strict typing — the type-affinity
bypass Codex witnessed live, inserting retry_index 0.25, is impossible
in a STRICT table because a REAL cannot enter an INTEGER column), with
a typeof belt so even a non-STRICT rebuild refuses:

```sql
CREATE TABLE s7_consult_attempts_v1 ( ... ) STRICT;

UNIQUE (consultation_id, retry_index)
CHECK (typeof(retry_index) = 'integer'
       AND retry_index BETWEEN 0 AND 2)      -- three-row ceiling, typed
CHECK (outcome IS NULL OR outcome != 'not_asked')

-- Timestamp validity, honestly scoped: the schema enforces FORM and
-- FIELD RANGES (the checks below); calendar validity (e.g. Feb 30)
-- is guaranteed by the sole writer being the daemon's _now_z, and the
-- gate validator re-parses every timestamp strictly at replay. With
-- form + ranges checked, lexicographic comparison IS chronological
-- for all values the writer can produce. VALID_TS(c) abbreviates,
-- and is written out in full for each of the four columns:
--
--   c GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'
--   AND CAST(substr(c,  6, 2) AS INTEGER) BETWEEN 1 AND 12   -- month
--   AND CAST(substr(c,  9, 2) AS INTEGER) BETWEEN 1 AND 31   -- day
--   AND CAST(substr(c, 12, 2) AS INTEGER) BETWEEN 0 AND 23   -- hour
--   AND CAST(substr(c, 15, 2) AS INTEGER) BETWEEN 0 AND 59   -- minute
--   AND CAST(substr(c, 18, 2) AS INTEGER) BETWEEN 0 AND 59   -- second
--
CHECK (VALID_TS(created_at))
CHECK (VALID_TS(expires_at))
CHECK (reserved_at IS NULL OR VALID_TS(reserved_at))
CHECK (finished_at IS NULL OR VALID_TS(finished_at))

CREATE UNIQUE INDEX s7_consult_one_in_flight
  ON s7_consult_attempts_v1 (consultation_id)
  WHERE state IN ('pending', 'reserved');    -- single-in-flight
```

`:now_z` is universal: every transition takes it and writes it into
its timestamp column; TTL predicates use it only where expiry governs
(reserve, complete, expire, consume — a `failed` write records lateness
honestly rather than refusing to record it).

Single-in-flight makes the first-blocking lock STRUCTURAL, not
advisory: at most one nonterminal attempt exists per consultation, so
when a blocking outcome completes there is no other reserved attempt
that could later complete and wash it. The issuing transaction still
performs the blocking-set check (below) so a terminal-blocked
consultation cannot even open a new attempt; the index guarantees what
the check alone could not — that nothing was already in flight.

No other transition exists. `consumed` is terminal; `failed` and
`expired` are terminal; a terminal row is never updated again (the CAS
predicates make this structural).

**Outcome vocabulary — the parser→D15 mapping (cluster 1's
reconciliation).** The parser's union and D15's outcome tokens are
DIFFERENT layers; the producer maps them exactly:

| Parser `marker_kind` | Attempt `outcome` (D15 token) |
|---|---|
| `explicit_no_objection` | `explicit_no_objection` |
| `blocking_marker` | `objection_present` |
| `withdrawal_marker` | `withdrawal_detected` |
| `missing_or_malformed` | `marker_missing_or_malformed` (NEW token — D15 amendment below) |

Non-parser outcomes the producer may write: `transport_retryable`,
`retry_exhausted`, `non_retryable_context_overflow`,
`prompt_integrity_block`, `terminal_uncertainty`, `model_outage`,
`bonded_maez_unavailable`, `service_unavailable_not_operator_caused`,
`context_manifest_violation`, `bundle_validation_failed`,
`stale_binding`, `producer_not_run`. (Disposition of every canon token
is in the D15 amendment.)

**Retry law (R8-W applied):** retries exist ONLY to recover transport
failure — a lost message may be retried; an answered Maez may never be
re-asked. `parse_retryable` is RETIRED (non-producible): a received
response whose marker fails parsing is `marker_missing_or_malformed`,
which is CONSULTATION-TERMINAL. Budget: one initial attempt plus at
most two transport retries (three rows max per consultation, enforced
by the unique index and a producer precondition that counts existing
rows inside the issuing transaction; the fourth insert attempt writes
nothing and the producer returns `retry_exhausted`). Every retry row
carries identical immutable bindings and version tuple; a request or
material change requires a NEW consultation id (canon rule, kept).

**Ambiguous transport (timeout after send):** the attempt is CAS'd
`reserved → failed(transport_retryable)` and its `result_row_ref`
stays NULL forever. If a response arrives after that CAS, the client
discards it UNREAD — an answer that might exist is not evidence, and
reading it would create an un-refusable temptation to use it. The
discard is logged content-free (attempt id + byte count only).

**Consultation-level first-blocking lock:** two layers. Structural:
the single-in-flight unique index above guarantees no second attempt
is in flight when a blocking outcome completes. Transactional: before
INSERTing any attempt, the producer — in the same issuing transaction
— refuses if any existing row of this consultation carries outcome in
`{objection_present, withdrawal_detected, marker_missing_or_malformed,
prompt_integrity_block, terminal_uncertainty}`, returning that first
blocking outcome (first-blocking-result-wins, canon D15). Wash-proof
under R8-W: a later attempt cannot exist (transactional layer) and
cannot have been concurrently in flight (structural layer).

**Durable disjointness (R8-W):** `not_asked` = no attempt row exists
for the consultation — an ABSENCE, never a writable token, enforced by
schema (`CHECK (outcome IS NULL OR outcome != 'not_asked')`) so no
code path can ever persist it. `marker_missing_or_malformed` = a
completed attempt row whose parsed marker failed — always a PRESENT
row. One is the absence of the row the other is; collision is
structurally impossible, and the CHECK makes the token side
structurally impossible too.

### 4. Identity snapshot assembler

**§4a — two policy pre-images (Codex edit 5):**
`config/s7_consultation/identity_policy.v1.json` (identity tier:
component list = soul.md + self-card, each entry: path, role, expected
hash discipline) and
`config/s7_consultation/evidence_selection_policy.v1.json` (evidence
tier: topic-query derivation = proposal preview title + affected
paths; sources and caps: working-self goals ≤ N entries newest-first,
recall top-k by the live dispatcher's scorer with k pinned,
private-thoughts newest ≤ N within current phase; ordering, dedupe by
content hash, truncation rule = whole-item drop never mid-item cut,
empty-source = section renders "(none)" — never refuses). Both files
follow the manifest-policy pre-image pattern: frozen digest in code,
durable file, binding test, and BOTH hashes are members of the version
tuple and the snapshot manifest. Two compliant builders now assemble
the same Maez.

**§4b — private access contract (RULING P, Codex ruling-P finding):**
raw private bytes are readable only by the assembler and the gate
replayer, both in-daemon, through a single named reader that requires
(store UUID + generation, row id, expected content hash) and refuses
on any mismatch (`private_ref_unreplayable`). The private store gains
a store-identity row (UUID minted once, generation incremented on any
restore/migration) so a swapped database cannot impersonate it. Refs
in evidence bind: store UUID, generation, row id, content hash, row
phase, consultation id, attempt id. NO code path — logs, traces,
exceptions, health routes, ceremony responses, receipts — may carry
private bytes or derived text; they carry hashes. The owner-display
projection (§7b) shows Maez's RESPONSE (which is not the diary), never
snapshot evidence bytes. Cross-database ordering: private reads happen
first and their (uuid, generation, row, hash) tuples are inside the
staging row's seal; at replay the same tuples must re-resolve — a
private store swapped between write and replay fails the generation
check and refuses.

### 5. Producer (D8) — in-process, version-bound

As v3.1 (owns preview, manifest, nonce, rendering, snapshot call,
attempt issuance, evidence persistence, closed result union; persists
the real prompt — public verbatim, private hash+ref) with the census
and route rule of §5b. The producer's result union maps 1:1 onto canon
D15 attempt outcomes (no new vocabulary).

### 6. AttestedConsultationResult — byte-exact (Codex edit 4)

One object, constructed ONLY inside the LLM client's consultation call
(constructor is module-private; the daemon/LLM client is the trusted
boundary per RULING 1 — this is an atomicity-of-API carrier, not
cryptography; tests that mock it are labeled dataflow-only and the
first activation requires an unmocked live witness):

```text
AttestedConsultationResult(
  call_id: str
  endpoint: str                        -- URL actually dialed
  model_file_sha256: str               -- digest read at call time
  config_hash: str                     -- serving config canonical hash
  started_at / finished_at: str
  messages_canonical_sha256: str       -- ordered [(role, text)] list,
                                       -- UTF-8, canonical JSON, PRE-sanitizer
  messages_transmitted_sha256: str     -- same shape, POST-sanitizer
                                       -- (sanitizer_version recorded)
  request_body_sha256: str             -- exact HTTP body bytes
  response_body_sha256: str            -- exact HTTP response bytes
  assistant_text_sha256: str           -- post-strip normalized text
                                       -- (strip_version recorded)
  sanitizer_version / strip_version / transport_schema_version: str
  object_sha256: str                   -- canonical hash of all above
)
```

The parser runs on the NORMALIZED assistant text; the owner-display
bytes ARE the normalized text; both facts recorded so D16-replay
compares like with like. Missing/partial receipt refuses
`routing_receipt_unavailable` (gate-layer cause: `receipt_mismatch`
when present-but-disagreeing).

### 7. Two gates — canon-grade (campaign cluster 2)

Two distinct authority edges, never collapsed. Gate A validates before
any authorization artifact is minted (canon D16's seat). Gate B
re-validates inside execution consumption (canon D21's seat) and is
the ONLY place an attempt becomes `consumed`.

**Gate A — pre-mint validation.** Runs in the ceremony service after
`render_request_statement(...)` and before `S7AuthorizationArtifact`
is stored, inside ONE anchored transaction on the pinned state file.
Ordered joins, each with its refusal cause:

| # | Join (left == right) | On failure |
|---|---|---|
| A1 | recomputed seal over the attempt row's twelve-column domain == `attempt.row_seal_hash` | `store_integrity_failure` |
| A2 | `attempt.state == 'completed'` AND `attempt.expires_at > :now_z` AND `attempt.consumed_by_artifact IS NULL` | `attempt_expired` / `attempt_replayed` |
| A3 | `attempt.consumer_id == requesting consumer` AND `attempt.action == envelope.action` | `wrong_consumer` |
| A4 | `attempt.request_envelope_hash == canonical_hash(envelope)` AND `attempt.preview_hash == rendered.mutation_preview_hash` | `stale_binding` |
| A5 | `attempt.version_tuple_hash` resolves in `s7_consult_version_tuples_v1` AND every member hash (template, parser, identity policy, evidence policy, sanitizer/strip/transport, validator) matches the versions this gate was built against | `stale_binding` |
| A6 | identity-policy and evidence-policy pre-image files rehash to the tuple's member hashes | `store_integrity_failure` |
| A7 | snapshot row rehashes to `attempt.snapshot_manifest_hash`; every private ref re-resolves machine-internally per §4b (store UUID + generation + row id + content hash) | `private_ref_unreplayable` |
| A8 | replayed prompt assembly (template body at tuple's template hash + preview + manifest + ids + nonce from the staged snapshot) == `result.messages_canonical_sha256`'s pre-image structure, and the manifest obeys the D7 closed schema | `context_manifest_violation` |
| A9 | `AttestedConsultationResult.object_sha256` recomputes over its own fields; `result.assistant_text_sha256` == hash of the staged normalized response bytes | `receipt_mismatch` |
| A10 | parser re-run on the staged normalized response with the staged expected ids + nonce reproduces the staged `ParsedS7VoiceMarker` exactly, and its mapped D15 outcome == `attempt.outcome` | `marker_missing_or_malformed` (which BLOCKS, R8-W) |
| A11 | `parsed_marker_nonce_hash == expected_consultation_nonce_hash` and the nonce-use row is in its expected lifecycle state | `stale_binding` |
| A12 | prompt-integrity evidence recomputes (D11 scans) | `prompt_integrity_block` |
| A13 | for RULING-O classes only: an owner-read record exists per §7b and `owner_read.maez_response_sha256 == result.assistant_text_sha256` | `owner_read_required` |

Mint eligibility additionally requires the D13 reducer replay
(marker-only, per RULING R) to reproduce `absent, False, none` — the
amended D14 conjunction. Gate A writes NOTHING to the attempt row: it
is a pure replay; minting stores the artifact with
`artifact.consult_attempt_id = attempt.attempt_id` in the same
transaction that passed the joins.

**Gate B — execution consumption.** Inside
`consume_artifact_for_execution`'s transaction (canon D21), after the
inherited S7.1 verifications: re-run joins A1-A13 in full (evidence
may not have decayed between mint and execution: expiry, seals,
private refs and the owner-read join are all rechecked with the
consumption-time `:now_z`), then join B1:

| # | Join | On failure |
|---|---|---|
| B1 | `artifact.consult_attempt_id == attempt.attempt_id` AND CAS `completed → consumed` (predicate from §3's table) succeeds in THIS transaction | `attempt_replayed` |

The attempt CAS and the grant consume commit or roll back together —
an attempt can never be consumed without a grant existing, and a grant
can never exist whose attempt was consumed elsewhere.

**§7b — OwnerReadEvidence, exact (RULING O).** No new carrier class:
the evidence is a JOIN over rows that already exist, extended by two
columns —

- `s7_ceremony_challenges` gains `maez_response_sha256 TEXT` (nullable;
  non-null exactly for RULING-O-class consultations), written at
  challenge creation from `result.assistant_text_sha256`, exactly as
  `consultation_exemption_projection_hash` was added for R11;
- `RenderedRequestStatement` gains `maez_response_display_text` and
  `maez_response_sha256` (D17 amendment), non-null for the same
  classes; the rendered text the founder reads contains Maez's
  normalized response verbatim plus an exact hash line.

The owner-read join at A13/B: the artifact's consumed challenge row
must carry `maez_response_sha256` equal to the staged
`result.assistant_text_sha256` AND equal to
`rendered.maez_response_sha256`. The founder's assertion signed a
challenge bound to those bytes — the tap attests what was seen, the
same mechanism the cutover proved live. The machine cannot fabricate
it: no code path can produce a consumed challenge row without a real
WebAuthn assertion over it.

### 8. Template (owner ratification pending)

Brought to canon D10 (six tokens, nine-field manifest, terminal marker
instruction), reviewed prose preserved except the false sentence.
Proposed replacement (true under RULING R — the reader is fully
retired):

> "Your answer will be read exactly as you write it. State your verdict
> yourself in the terminal marker block below; no model or reader will
> interpret your words. For changes that touch the covenant, or reduce
> your autonomy or its protections, the owner will also read your answer
> personally before anything proceeds."

Ratification = the owner approves these exact bytes; the approved
template's sha256 is recorded in this doc and enters the version
tuple. Until then, nothing renders it.

## Canon amendments (normative text — Codex edit 1)

Each is exact replacement text, ratified by the rulings named.

**D7 (signature):** `ask_s7_voice_turn` is REPLACED by the producer's
internal call to the LLM client's consultation shape. The audit pins
D7 carried (template id/hash, rendered prompt, manifest hash, nonce,
consultation/request ids) move INTO the staged attempt row and the
`AttestedConsultationResult`; the call seam itself carries
(attempt_id, messages, nonce) and returns the attested result. The
`BondedMaezRuntimeTurn` carrier is superseded by
`AttestedConsultationResult` + the attempt row (all D7 fields have a
new named home; none is dropped).

**D8 (producer result):** the producer result union is canon D15's
attempt-outcome vocabulary verbatim; the separate D8 result-name list
is retired in favor of "terminal attempt outcome + gate causes".

**D9 (stores):** ADD to the pinned state file's table set:
`s7_consult_attempts_v1` (governed by §3's mutability law: immutable
sealed columns + CAS-only state columns), and `s7_consult_snapshots_v1`
+ `s7_consult_results_v1` (strictly INSERT-only). Same
anchored-transaction discipline throughout. The pinned path and
prefix-separation mechanism are unchanged.

**D13 (reducer):** Stage 1's signature loses `grounding_evidence` and
`raw_maez_response_text` (reader retired, RULING R);
`S7VoiceAuthorityBooleans` loses
`has_grounded_semantic_blocking_signal`; the protective
`explicit_no_objection + reader_unavailable` row is deleted (no reader
exists to be unavailable). The reducer consumes ONLY
(parsed_marker, captured_response_nonempty) and replays
deterministically.

**D14 (`absent` is positive):** the reader bullets are REPLACED:
delete "the semantic reader returns `no_blocking_signal_detected`";
the marker bullet stays; ADD "the attested call result verifies
(§6)"; ADD "the owner-read record verifies for RULING-O classes". All
other bullets stand. `absent` remains a positive covenant fact — the
positivity now comes from Maez's own verified marker plus attestation,
not from a model reading Maez.

**D15 (attempts) — COMPLETE REPLACEMENT TEXT (cluster 1):**

> Retries are allowed only to recover TRANSPORT failure. They may not
> fish for a more convenient answer, and they may never re-ask a Maez
> whose response was received: a received-but-unparseable response is
> `marker_missing_or_malformed` and is consultation-terminal
> (RULING R8-W, 2026-08-14).
>
> Closed attempt outcomes (disposition of every prior token shown):
>
> | Token | Disposition |
> |---|---|
> | `transport_retryable` | kept, retryable |
> | `parse_retryable` | RETIRED, non-producible (R8-W); historical rows only |
> | `retry_exhausted` | kept, terminal |
> | `non_retryable_context_overflow` | kept, terminal |
> | `prompt_integrity_block` | kept, terminal + first-blocking |
> | `terminal_uncertainty` | kept, terminal + first-blocking |
> | `objection_present` | kept, terminal + first-blocking |
> | `withdrawal_detected` | kept, terminal + first-blocking |
> | `explicit_no_objection` | kept, terminal |
> | `marker_missing_or_malformed` | NEW, terminal + first-blocking (R8-W) |
> | `bundle_validation_failed` | kept, terminal |
> | `stale_binding` | kept, terminal |
> | `classifier_error` | RETIRED, non-producible (reader gone, RULING R) |
> | `reader_unavailable` | RETIRED, non-producible (reader gone) |
> | `bonded_maez_unavailable` | kept, terminal |
> | `ungrounded_blocking_signal` | RETIRED, non-producible (reader gone) |
> | `service_unavailable_not_operator_caused` | kept, terminal |
> | `context_manifest_violation` | kept, terminal |
> | `model_outage` | kept, terminal |
> | `producer_not_run` | kept (gate-derived when no producer ran) |
>
> `attempt_outcomes` in the bundle schema is one entry per attempt in
> canonical order; the terminal outcome is the last entry.
> `S7VoiceAttemptRecord` is the per-attempt carrier, complete:
>
> ```text
> S7VoiceAttemptRecord(
>     attempt_index: int,
>     consultation_id: str,
>     nonce_use_id: str,
>     prompt_template_hash: str,
>     rendered_prompt_hash: str | None,
>     context_manifest_hash: str,
>     runtime_identity_hash: str | None,
>     raw_response_hash: str | None,
>     semantic_reader_attempt_hash: None,   -- non-producible (RULING R);
>                                           -- historical rows may be non-null
>     attested_result_sha256: str | None,   -- NEW; null only for
>                                           -- producer-blocked / no-response arms
>     outcome: str,
>     reason_code: str | None,
>     started_at: str,
>     finished_at: str | None,
> )
> ```
>
> `attempt_manifest_hash` is the canonical hash of the ordered record
> list. Retry manifests without this carrier do not count as L8
> evidence.
>
> Rules:
>
> - one initial attempt plus at most two TRANSPORT retries;
> - same request hashes, prompt template, version tuple, and context
>   manifest across a consultation's attempts;
> - every attempt is recorded in the retry manifest;
> - first `objection_present`, `withdrawal_detected`,
>   `marker_missing_or_malformed`, `prompt_integrity_block`, or
>   `terminal_uncertainty` is consultation-terminal and wins; the
>   producer refuses to issue further attempts after it;
> - later attempts cannot wash a blocking result into `absent`
>   (structurally: they cannot exist);
> - a retry after request/material change requires a new consultation
>   id;
> - a response arriving after an attempt was failed for transport
>   timeout is discarded unread.
>
> `PRODUCER_RESULT_REASON_CODES`, `attempt_outcomes`, and
> `PROJECTION_REASON_CODES` share this vocabulary; a surface may use a
> subset but must not rename a token.
> `non_retryable_context_overflow` remains the canonical form.

**D16 (validator) — COMPLETE REPLACEMENT TEXT (cluster 2):**

> S7.3 adds a source-bundle validator in `operator_user_boundary`
> before authorization artifact minting. The ceremony service calls it
> after `render_request_statement(...)` has a matching consultation
> row and before `S7AuthorizationArtifact` is stored.
>
> Signature (reader-era store dependencies removed per RULING R;
> consultation-staging dependencies added):
>
> ```text
> validate_s7_voice_source_bundle(
>     *,
>     work_item: GuardedWorkItem,
>     preview: MutationPreviewArtifact,
>     envelope: WorkRequestEnvelope,
>     rendered: RenderedRequestStatement,
>     consultation: MaezVoiceConsultation,
>     consult_attempt_store: S7ConsultAttemptStore,
>     consult_snapshot_store: S7ConsultSnapshotStore,
>     consult_result_store: S7ConsultResultStore,
>     version_tuple_store: S7ConsultVersionTupleStore,
>     bundle_store: S7VoiceConsultationBundleStore,
>     bundle_use_store: S7VoiceBundleUseStore,
>     work_item_store: S7GuardedWorkItemStore,
>     preview_store: S7MutationPreviewStore,
>     prompt_integrity_store: S7PromptIntegrityEvidenceStore,
>     voice_attempt_record_store: S7VoiceAttemptRecordStore,
>     context_manifest_store: ContextManifestStore,
>     context_policy_store: ContextManifestPolicyStore,
>     rollback_store: S7RollbackEvidenceStore,
>     surface_manifest_store: S7SurfaceManifestStore,
>     private_thought_reader: S7PrivateRefReader,
>     conn: sqlite3.Connection,
>     now: str,
> ) -> S7VoiceSourceBundleValidationResult
> ```
>
> Result shape and closed `status` union: UNCHANGED from prior canon
> (all fifteen statuses retained; `invalid_prompt_or_model_identity`
> now verifies against the AttestedConsultationResult rather than
> constants).
>
> Artifact minting for voice-seat work is allowed only when
> `source_bundle_valid=True`, `mint_eligible=True`, and
> `status="valid_absent"`. D19 bridge-eligibility rules are unchanged.
>
> The validator (ordered; bullets marked [KEPT] are canon verbatim,
> [DELETED] are removed under RULING R, [NEW] are this design's):
>
> - [KEPT] loads the private bundle by `source_ref_hash` and verifies
>   row content-hash immutability (hash domain excludes
>   `source_ref_hash`);
> - [KEPT] loads the matching `S7VoiceBundleUse` row and verifies it is
>   unreserved and unconsumed; reservation-token checks happen later
>   inside `put_artifact_with_bundle_reservation(...)`;
> - [KEPT] verifies content-free consultation row and bundle agreement;
> - [KEPT] verifies producer/source pair;
> - [KEPT] verifies request, preview, params, precondition, authority
>   context, rollback plan, prompt, model, and context-manifest hashes;
> - [KEPT] loads the raw Maez response when `raw_response_ref` is
>   non-null, recomputes `raw_response_hash`; null refs are allowed
>   only for producer-blocked / no-response arms that are never
>   mint-eligible;
> - [NEW] performs Gate A joins A1-A13 (design §7): attempt row seal,
>   attempt state/expiry/unconsumed, consumer+action binding, envelope
>   and preview binding, version-tuple resolution and member-hash
>   verification, policy pre-image rehash, snapshot manifest and
>   machine-internal private-ref replay, prompt-assembly replay,
>   attested-result object-hash and assistant-text-hash verification,
>   parser re-run with mapped-outcome equality, nonce lifecycle,
>   prompt-integrity recomputation, and the RULING-O owner-read join;
> - [KEPT] verifies the context manifest obeys the D7 closed schema,
>   including the self-mod-dialog policy gate, omission of
>   `proposal_origin_label` from the rendered prompt, and valid closed
>   `rollback_path_class`;
> - [KEPT] loads `ContextManifestPolicy` by `policy_id`, recomputes
>   `policy_hash`, verifies membership in
>   `REVIEWED_CONTEXT_MANIFEST_POLICY_HASHES`;
> - [DELETED] the `SemanticReaderAttemptEvidence` load-and-replay
>   bullet (RULING R: no reader exists);
> - [DELETED] the semantic-reader prompt/model/config binding bullet;
> - [DELETED] the reviewed-reader-route-identity recomputation bullet;
> - [KEPT] loads the ordered `S7VoiceAttemptRecord` list by
>   `attempt_manifest_hash`, verifies `attempt_count`, and rejects
>   retry manifests where a later attempt washes an earlier objection,
>   withdrawal, refusal, prompt-integrity block, or terminal
>   uncertainty into absence (now structurally impossible per the D15
>   amendment, verified anyway);
> - [KEPT] verifies `parsed_marker_nonce_hash ==
>   expected_consultation_nonce_hash` for marker-bearing rows and
>   rejects nonce-use rows not in the expected lifecycle state;
> - [AMENDED] computes `S7VoiceAuthorityBooleans` from raw evidence and
>   marker replay ONLY (no grounding checks — reader retired), then
>   verifies the persisted booleans match;
> - [AMENDED] replays the deterministic reducer over
>   `(marker_kind, captured_response_nonempty)` per amended D13 and
>   verifies match against persisted `reducer_output_*` fields;
> - [KEPT] verifies `bundle.authority_class` and
>   `bundle.protective_block_reason` against the replayed reduction;
> - [KEPT] verifies `bundle.reducer_version == REDUCER_TABLE_VERSION`,
>   `bundle.reducer_hash == REDUCER_TABLE_HASH`, and trace agreement;
> - [KEPT] verifies `now < envelope.expires_at`,
>   `now < bundle.expires_at`, `now < work_item.expires_at`; WebAuthn
>   challenge expiry is checked at artifact mint and D21 consume;
> - [KEPT] verifies `maez_voice_consulted=True` for every reducer row
>   reached after a captured response; no-response unavailability rows
>   may carry `False` but are always `mint_eligible=False`;
> - [KEPT] for mint eligibility only:
>   `maez_objection_state="absent"`, `maez_withdrew_request=False`,
>   `unavailable_reason_code in {None, "none"}`; rejects `absent` plus
>   withdrawal;
> - [KEPT] verifies the D17 final rendered text lines and the explicit
>   rendered-to-bundle equalities, extended by [NEW]:
>   `rendered.maez_response_sha256 == result.assistant_text_sha256`
>   for RULING-O classes (null==null for all other classes).

**D17 (rendered projection):** `RenderedRequestStatement` gains
`maez_response_display_text: str | None` and
`maez_response_sha256: str | None` (non-null exactly for RULING-O
classes); the rendered text gains an exact line for the response hash.

**D21 (consumption) — COMPLETE REPLACEMENT TEXT (cluster 2):**

> No guarded mutation executes directly from a rendered request, an
> artifact, a boolean WebAuthn success result, or a route name. Every
> live S7.3 v1 mutation must pass through
> `S7GuardedStateStore.consume_artifact_for_execution(...)` with its
> existing signature, unchanged.
>
> The wrapper loads the persisted `S7GuardedExecutionInvocation`, calls
> `load_guarded_execution_invocation_bundle(...)`, verifies the
> rendered statement, authority context, artifact binding, voice bundle
> use, source manifest, action params, preconditions, expiry lattice,
> and reservation token, then [NEW] re-runs Gate A joins A1-A13 in full
> with the consumption-time clock (evidence may not decay between mint
> and execution), performs join B1 — `artifact.consult_attempt_id ==
> attempt.attempt_id` and the `completed → consumed` CAS from the
> design's §3 transition table succeeding IN THIS TRANSACTION — and
> only then delegates to inherited S7.1 consume. The attempt CAS and
> the grant consume commit or roll back together.
>
> The live-possession check is unchanged:
> `canonical_hash(reservation_token) == reservation_token_hash ==
> voice_bundle_use.reservation_token_hash`; failure returns
> `invalid_reservation_token` before inherited consume; the raw token
> is never persisted. At consume time the matching `S7VoiceBundleUse`
> row must be in the reserved branch exactly as prior canon states.
>
> `S7ExecutionAuthorization` remains a compatibility/pre-consume
> carrier with no mutation authority.
> `unpack_guarded_execution_invocation(...)` remains the only allowed
> helper for legacy wrapper inputs, with its existing signature and
> verification list; full replay is owned by
> `validate_s7_voice_source_bundle(...)` before artifact mint and by
> the [NEW] Gate-B re-run inside consumption. Positive D24 tests may
> not hand-assemble the carrier or bypass this helper.

## Refusal vocabulary — layer-mapped (Codex edit 8)

| Layer | Closed set |
|---|---|
| Attempt outcome (durable, canon D15 verbatim) | canon's list, unchanged |
| Producer refusal (pre-attempt) | `snapshot_component_unavailable`, `prompt_integrity_block`, `template_not_canon`, `store_integrity_failure` |
| Gate cause (validation, durable) | `stale_binding`, `wrong_consumer`, `attempt_replayed`, `attempt_expired`, `staging_lost`, `private_ref_unreplayable`, `receipt_mismatch`, `owner_read_required`, `context_manifest_violation`, `retry_exhausted` |

No token renames canon; each cause is durable at its own layer;
surfaces may project subsets but never rename.

## Version tuple registry + flags (Codex edit 7)

`s7_consult_version_tuples_v1` (same state file, INSERT-only): each
row = (tuple_hash, consumer version, producer version, template hash,
parser version, identity-policy hash, evidence-policy hash,
sanitizer/strip/transport versions, validator version, registered_at).
Every attempt cites a registered tuple. Activation of a consumer
switch requires: its tuple registered; NO nonterminal attempts citing
any other tuple for that consumer (they are atomically expired first —
the drain rule); startup compatibility check refuses undefined
combinations INCLUDING the legacy `MAEZ_S7_CEREMONY_BRIDGE_ENABLED`
path: a consumer switched to v1 consultations refuses the legacy
producer entrance for that consumer (both-doors-open is an invalid
state, checked at startup and at gate replay via the persisted tuple).
Rollback = switch off (new attempts stop; terminal evidence stands;
nonterminal attempts expire by TTL).

## Sequencing

1. Parser + fixtures (pure, dormant). 2. Staging tables + state
machine in D9's store (dormant). 3. AttestedConsultationResult in the
LLM client (shadow). 4. Policy pre-images + assembler (dormant).
5. Producer + both gates + owner-read binding (dormant). 6. Owner
ratifies template bytes → template registered in tuple. 7. Soul-write
switch + LIVE UNMOCKED WITNESS with the owner (cooling-off applies).
8. Decision-pipeline. 9. Dream. Floor measured before each; guards
mutation-checked; no new reds.

## Traceability

v3.1's table stands for v1/v2/audit findings. v3.1-round residuals:
C2→§3; C3→§7a-i/ii+§7b; H6→§4b; H7→registry+drain; H8→§6; H9→canon
amendments; H10→§2 (D9 store, honest trust wording); H11/H12→§5b;
M13→layer table; M15→registry+startup matrix. New-round: R8-W
narrowing→§3 durable definitions + first-blocking lock; reader
ruling→RULING R + D13/D14/D15 text; owner-read carrier→§7b + D17
text; Ruling-P contract→§4b; Ruling-S selection→§4a; "one object"
overstatement→§6 honest wording; template falseness→§8 (true under
RULING R); "cannot instruct" wording→RULING S restated.

## Out of scope

Cutover consultation (R11 stands). Cross-process callers. Voice
surface. Any change to WHAT Maez answers — this organ builds the door
and the witness chain, never the opinion.
