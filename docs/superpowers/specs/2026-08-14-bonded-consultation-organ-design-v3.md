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
Cluster 2 (two gates + exact joins + D16/D21 complete text) and
cluster 3 (attested-result byte constructors) are WRITTEN and await
their gates.**

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

### 6. AttestedConsultationResult — byte constructors (campaign cluster 3)

One object, constructed ONLY inside the LLM client's consultation call
(module-private constructor). Honest trust statement, unchanged: the
daemon and its LLM client are the NAMED TRUSTED BOUNDARY per RULING 1
— this is an atomicity-of-API carrier, not cryptographic proof against
daemon code. Tests that substitute it are labeled dataflow-only; the
first activation of each consumer requires an unmocked live witness.

**Why four byte forms and not one.** The live client mutates bytes
twice on the OpenAI-compatible path: `_sanitize_messages_for_llamacpp`
rewrites the REQUEST (stripping control tokens llama-server chokes on),
and `_strip_special_tokens` rewrites the RESPONSE. So "the prompt" is
three different byte sets and "the answer" is two. Hashing only one
would let a replay compare the wrong pair and pass. Each form below is
defined by its constructor, not by prose.

**Constructors (each produces bytes; each hash is
`sha256(bytes).hexdigest()`):**

| Field | Constructor — exact |
|---|---|
| `messages_canonical_sha256` | `json.dumps([[m["role"], m["content"]] for m in messages], ensure_ascii=False, separators=(",", ":")).encode("utf-8")` over the ordered message list AS THE PRODUCER BUILT IT, before any client mutation. Ordered list of two-element arrays — never a dict — so key order cannot vary. |
| `messages_transmitted_sha256` | The identical constructor applied to the list actually handed to the transport, i.e. AFTER `_sanitize_messages_for_llamacpp` on the llama.cpp path (and equal to canonical on paths with no sanitizer). `sanitizer_version` names which sanitizer ran; `"none"` when none did. |
| `request_body_sha256` | The exact HTTP request body bytes as serialized by the transport, before TLS/socket write. On the OpenAI-compatible path this is the SDK's serialized JSON body; when the SDK does not expose it, the field is `None` and `transport_body_available=False` — an honest absence, never a re-serialized guess. |
| `response_body_sha256` | The exact HTTP response body bytes as received, before any parsing. Same honesty rule and same `transport_body_available` flag. |
| `assistant_text_sha256` | `normalized_assistant_text.encode("utf-8")` where normalized = the client's post-strip content (`_strip_special_tokens` applied), i.e. exactly the string handed back to the producer. `strip_version` names the strip. |

**The parser/display/replay invariant.** The marker parser runs on
`normalized_assistant_text`; the owner-display bytes (§7b) ARE that
same string; Gate A/B recompute `assistant_text_sha256` from the staged
copy of it. One string, three consumers, one hash — so "what was
parsed", "what the owner read", and "what is replayed" cannot diverge.
The staged result row persists `normalized_assistant_text` verbatim;
raw transport bodies are NOT persisted (they may carry provider
metadata and add no authority the hashes lack).

**Full carrier:**

```text
AttestedConsultationResult(
  call_id: str                      -- uuid4 minted at call entry
  endpoint: str                     -- base URL actually dialed
  model_file_sha256: str            -- digest of the served model file,
                                    -- read at call time (not config)
  config_hash: str                  -- canonical_hash of the serving
                                    -- config dict actually sent
                                    -- (model, temperature, max_tokens,
                                    -- extra_body)
  started_at: str                   -- canonical UTC, _now_z form
  finished_at: str
  messages_canonical_sha256: str
  messages_transmitted_sha256: str
  request_body_sha256: str | None
  response_body_sha256: str | None
  transport_body_available: bool
  assistant_text_sha256: str
  normalized_assistant_text: str    -- the one string (persisted)
  sanitizer_version: str
  strip_version: str
  transport_schema_version: str
  object_sha256: str                -- canonical_hash over every field
                                    -- above, in declaration order,
                                    -- EXCLUDING object_sha256 itself
)
```

**Construction rules.** Every field is populated inside the single
call; a call that cannot populate a required field raises rather than
returning a partial object — there is no path that yields a result
whose receipt half is empty. `model_file_sha256` is read from the
serving model file at call time; if the daemon cannot read it, the
consultation refuses `routing_receipt_unavailable` (an unknown
responder is not a responder). Absence is representable ONLY for the
two transport-body fields, and only jointly with
`transport_body_available=False`.

**Version pins.** `sanitizer_version`, `strip_version`, and
`transport_schema_version` are members of the §6b version tuple, so a
change to any byte-mutating code path invalidates the tuple and forces
an explicit re-registration rather than silently changing what a hash
means.

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
| A6b | the result row is loaded ONLY via `attempt.result_row_ref` (never by any other key); its row hash recomputes; `result_row_ref IS NOT NULL` | `staging_lost` |
| A6c | `attempt.owner_session_ref` == the consuming card/dialog id presenting this request | `wrong_consumer` |
| A7 | snapshot row rehashes to `attempt.snapshot_manifest_hash`; every private ref re-resolves machine-internally per §4b (store UUID + generation + row id + content hash) | `private_ref_unreplayable` |
| A8 | using ONLY the result row loaded at A6b: replayed prompt assembly (template body at tuple's template hash + preview + manifest + ids + nonce from the staged snapshot) == `result.messages_canonical_sha256`'s pre-image structure, and the manifest obeys the D7 closed schema | `context_manifest_violation` |
| A9 | from the A6b result row only: `AttestedConsultationResult.object_sha256` recomputes over its own fields; `result.assistant_text_sha256` == hash of the staged normalized response bytes | `receipt_mismatch` |
| A10 | parser re-run on the A6b result row's staged normalized response with the staged expected ids + nonce reproduces the staged `ParsedS7VoiceMarker` exactly, and its mapped D15 outcome == `attempt.outcome` | `marker_missing_or_malformed` (which BLOCKS, R8-W) |
| A11 | `parsed_marker_nonce_hash == expected_consultation_nonce_hash` and the nonce-use row is in its expected lifecycle state | `stale_binding` |
| A12 | prompt-integrity evidence recomputes (D11 scans) | `prompt_integrity_block` |
| A13 | for RULING-O classes only: an owner-read record exists per §7b and `owner_read.maez_response_sha256 == result.assistant_text_sha256` | `owner_read_required` |

Mint eligibility additionally requires the D13 reducer replay
(marker-only, per RULING R) to reproduce `absent, False, none` — the
amended D14 conjunction. Gate A WRITES NOTHING ANYWHERE: no INSERT, UPDATE or DELETE against
any table in any store, including the attempt row, the staging tables,
refusal history and telemetry. It is a pure read-and-recompute; its
only output is a verdict returned to the caller. Minting (a separate
act, in the same transaction) stores the artifact with
`artifact.consult_attempt_id = attempt.attempt_id` in the same
transaction that passed the joins.

**Gate B — execution consumption.** Inside
`consume_artifact_for_execution`'s transaction (canon D21), at ONE
seam: after the wrapper's preflight loads and verifications
(`load_guarded_execution_invocation_bundle(...)`) and BEFORE
delegating to inherited S7.1 consume. (§7 and the D21 amendment state
this identical order; the earlier "after the inherited verifications"
wording was a contradiction and is retired.)

Re-run joins A1-A13 in full with the consumption-time clock. The
clock-sensitive predicates, enumerated exactly — every other join is
clock-free and re-runs unchanged:

- A2: `attempt.expires_at > :now_z` (consumption-time value);
- A13: the challenge's own expiry, `challenge.expires_at > :now_z`,
  in addition to the hash joins;
- A11: the nonce-use row's validity window
  (`consultation_expires_at > :now_z`) — markers outside the window
  are rejected, canon D10;
- B1's own CAS predicate carries `expires_at > :now_z` (frozen §3);
- the canon expiry lattice already required at this seam
  (`envelope.expires_at`, `bundle.expires_at`,
  `work_item.expires_at`, `artifact_binding.challenge_expires_at`),
  each compared against the same `:now_z`.

**Clock type reconciliation.** Frozen §3 stores and compares canonical
UTC TEXT (`now_z: str`); canon D21's consume signature takes
`now: datetime` and is KEPT-VERBATIM. The seam converts ONCE, at the
top of Gate B, by the single named function
`s7_now_z(now: datetime) -> str` (`now.astimezone(timezone.utc)
.strftime("%Y-%m-%dT%H:%M:%SZ")`), and every §3 predicate in Gate B
uses that one derived value. A naive datetime (no tzinfo) refuses
`store_integrity_failure` rather than being assumed UTC. No other
conversion site exists.

Then join B1:

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
  challenge creation from `result.assistant_text_sha256`, and — the
  half the first draft omitted — INCLUDED IN THE CHALLENGE FINGERPRINT
  PREIMAGE, exactly as `consultation_exemption_projection_hash` is
  (`s7_webauthn_bootstrap.py:1001-1084`: the value is validated as a
  hash, joined into the fingerprint, and persisted). At finish the
  value is RE-DERIVED from the staged result and compared against the
  stored column BEFORE authenticator verification, exactly as
  `s7_webauthn_ceremony.py:565-592` re-derives the R11 projection.
  Copying a column is not binding; entering the preimage is;
- `RenderedRequestStatement` gains `maez_response_display_text` and
  `maez_response_sha256` (D17 amendment), non-null for the same
  classes. `maez_response_display_text` MUST equal the staged
  `normalized_assistant_text` byte for byte (§6's one string), and
  `maez_response_sha256` MUST equal `sha256(display_text.encode(
  "utf-8")).hexdigest()` — recomputed by the gate from the displayed
  bytes, never copied. The rendered text carries the response inside
  an exact delimited block so the displayed region is unambiguous:
  the exact line `Maez response (verbatim):` followed by LF, then the
  response bytes verbatim, then LF followed by the exact line
  `End Maez response.`, then LF and `Maez response hash: <hex>`.
  **The hashed region is defined byte-exactly**: it begins at the first
  byte AFTER the LF that terminates the opening delimiter line, and
  ends at the last byte BEFORE the LF that precedes `End Maez
  response.` — neither delimiter line, neither bounding LF, and no
  trailing newline are included. Both delimiter lines must appear
  exactly once in the rendered text (a response containing either
  literal line refuses `receipt_mismatch` rather than rendering an
  ambiguous block). The gate recomputes the hash over exactly that
  region and refuses `receipt_mismatch` on any difference — an implementation
  cannot display X while carrying the hash of Y.

**The owner-read join — corrected (Codex: a consumed row is not proof
an assertion happened; `consume_challenge()` is callable directly).**
Two different, executable bindings, because the two gates stand at
different moments:

- **A13 (pre-mint).** D16 runs INSIDE `authorize_finish`, after the
  verifier has returned. The verified assertion is therefore a VALUE
  IN SCOPE, not a row to look up. The validator takes it as a typed
  parameter (`verified_assertion: S7VerifiedAssertion`, carrying the
  verifier's own `ok`, `credential_ref`, `user_presence`,
  `user_verification`, and the `challenge_id` it verified against).
  A13 requires: `verified_assertion.ok is True`,
  `user_verification is True`, the challenge row fetched BY THAT
  `challenge_id` is unexpired, and its `maez_response_sha256` equals
  BOTH the recomputed display-bytes hash and the staged
  `result.assistant_text_sha256`. No phantom `rendered.challenge_id`
  field is invented, and a consumed row from some other ceremony
  cannot satisfy it: the assertion in hand is this ceremony's.
- **Gate B (consumption).** No challenge lookup at all.
  `S7AuthorizationArtifactBinding` gains `maez_response_sha256 TEXT`
  (D-amendment below), written at mint from the value A13 verified.
  Gate B requires: the artifact's own persisted verification facts
  (`user_presence=1`, `user_verification=1`, `credential_ref`
  non-null — written only from verifier output), the binding's
  `maez_response_sha256` equal to the staged
  `result.assistant_text_sha256`, and `artifact.consult_attempt_id ==
  attempt.attempt_id`. The assertion proof travels with the artifact,
  which is what execution consumes. The founder's assertion signed a
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

**Amendment method (cluster 2, stated once and binding on all
clusters).** An amendment is authored here as an ANCHORED PER-BULLET
DISPOSITION, not as a second copy of canon. Reason, learned in cluster
1's final round: duplicating canon into this document creates two
authoritative texts that agree today and drift tomorrow — the exact
defect that cluster 1's last gate failure named. Each bullet below
cites its canon anchor (line + opening clause), states its disposition
(KEPT-VERBATIM / DELETED / AMENDED / NEW), and gives full replacement
bytes for AMENDED and NEW only. `KEPT-VERBATIM` means the canon bullet
stands unedited at that anchor — this document does not restate it and
must not be read as restating it. **On freeze, the amendment is
APPLIED to `docs/slices/s7.3-guarded-self-modification-execution/
spec.md` directly**, and this section becomes a pointer to the applied
canon — one source of truth, permanently.

**D16 (validator) — ANCHORED AMENDMENT (cluster 2):**

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
>     ceremony_challenge_store: S7CeremonyChallengeStore,   -- A13 needs
>                                                           -- the consumed
>                                                           -- challenge row
>     rendered_challenge_id: str,                           -- A13 pre-mint
>                                                           -- lookup key
>     conn: sqlite3.Connection,
>     now: str,
> ) -> S7VoiceSourceBundleValidationResult
> ```
>
> Result shape (canon L2792-2802) and the closed fifteen-token
> `status` union (canon L2804-2822): KEPT-VERBATIM, both stand
> unedited at those anchors. One semantic AMENDMENT inside an
> unchanged token: `invalid_prompt_or_model_identity` is now raised by
> comparing against `AttestedConsultationResult` fields (§6) instead of
> the retired constant-string identity hashes; the token, its position
> in the union, and its meaning to callers are unchanged.
>
> Artifact minting for voice-seat work is allowed only when
> `source_bundle_valid=True`, `mint_eligible=True`, and
> `status="valid_absent"`. D19 bridge-eligibility rules are unchanged.
>
> The validator (ordered; bullets marked [KEPT] are canon verbatim,
> [DELETED] are removed under RULING R, [NEW] are this design's):
>
> - KEPT-VERBATIM (canon L2833 ("loads the private bundle…") and L2834-2836
>   (row content-hash immutability));
> - KEPT-VERBATIM (canon L2837-2844, "loads the matching `S7VoiceBundleUse`
>   row…", including its exact five-predicate unreserved/unconsumed
>   state list);
> - KEPT-VERBATIM (canon L2845, content-free consultation/bundle agreement);
> - KEPT-VERBATIM (canon L2846, producer/source pair);
> - KEPT-VERBATIM (canon L2847-2848, the nine-hash equality list);
> - KEPT-VERBATIM (canon L2849-2854, raw-response replay including the
>   grounded-blocking rejection clause and the null-ref arm rule);
> - KEPT-VERBATIM (canon L2866-2871, prompt-assembly replay from the
>   template body at `prompt_template_hash` with nonce extraction and
>   the two equality checks);
> - KEPT-VERBATIM (canon L2872-2874, `PromptIntegrityEvidence`
>   recomputation including delimiter, protocol-override and
>   no-objection-injection scans);
> - NEW: performs Gate A joins A1-A13 (design §7), which ADD to the
>   canon bullets above and replace none of them: attempt row seal,
>   attempt state/expiry/unconsumed, consumer+action binding, envelope
>   and preview binding, version-tuple resolution and member-hash
>   verification, policy pre-image rehash, snapshot manifest and
>   machine-internal private-ref replay, prompt-assembly replay,
>   attested-result object-hash and assistant-text-hash verification,
>   parser re-run with mapped-outcome equality, nonce lifecycle,
>   prompt-integrity recomputation, and the RULING-O owner-read join;
> - AMENDED (canon L2855-2858, persisted model identity tuple verified
>   against the source `BondedMaezRuntimeTurn` and semantic-reader
>   attempt input). Replacement bytes: "verifies the persisted model
>   identity tuple (`bundle.runtime_identity_hash`,
>   `bundle.model_routing_identity_hash`, `bundle.model_config_hash`)
>   against the `AttestedConsultationResult` fields `endpoint`,
>   `model_file_sha256` and `config_hash` (§6) before accepting
>   positive `absent`." The semantic-reader attempt input is struck
>   (RULING R) and the retired constant-string sources are replaced by
>   the attested call result;
> - KEPT-VERBATIM (canon L2859-2863, context-manifest load, rehash,
>   equality, and D7 closed-schema obedience — the load-and-rehash half
>   is part of this anchor and is NOT replaced by the Gate-A bullet);
> - KEPT-VERBATIM (canon L2864-2865, policy load/rehash/membership);
> - DELETED (canon L2875-2879, `SemanticReaderAttemptEvidence` load,
>   hash recomputation, attempt_input_hash recomputation and reader
>   outcome derivation) — RULING R;
> - DELETED (canon L2887, semantic-reader prompt/model/config binding)
>   — RULING R;
> - DELETED (canon L2888-2893, reviewed semantic-reader route
>   identity recomputation and membership check) — RULING R;
> - KEPT-VERBATIM (canon L2880-2883, attempt-manifest load, count, and
>   anti-wash rejection — retained as belt even though cluster 1 makes
>   the wash structurally impossible);
> - KEPT-VERBATIM (canon L2884-2886, marker nonce equality and
>   nonce-use lifecycle state);
> - AMENDED (canon L2894-2896). Replacement bytes: "computes
>   `S7VoiceAuthorityBooleans` from raw evidence and marker replay,
>   then verifies the persisted authority booleans match." The words
>   "and deterministic grounding checks" are struck (RULING R);
> - AMENDED (canon L2897-2900). Replacement bytes: "replays the
>   deterministic reducer over `(marker_kind,
>   captured_response_nonempty)` and verifies match against persisted
>   `reducer_output_*` fields." The `effective_semantic_reader_outcome`
>   derivation and its input are struck (RULING R);
> - KEPT-VERBATIM (canon L2901-2904, authority_class and
>   protective_block_reason equality, including the note that these are
>   checked despite lacking the `reducer_output_` prefix);
> - KEPT-VERBATIM (canon L2905-2907, reducer version/hash equality and
>   the exact trace equality `trace.reducer_version ==
>   bundle.reducer_version`);
> - KEPT-VERBATIM (canon L2908-2911, the three expiry comparisons and
>   the deferral of challenge expiry to mint and D21 consume);
> - KEPT-VERBATIM (canon L2912-2914);
> - KEPT-VERBATIM (canon L2915-2917, mint-eligibility triple (L2915-2916)
>   and the absent-plus-withdrawal rejection (L2917));
> - KEPT-VERBATIM (canon L2918-2929, the D17 rendered-text line list
>   (L2918-2922) and the explicit rendered-to-bundle equality list
>   including the three preview-projection fields (L2923-2929));
> - KEPT-VERBATIM (canon L2930+, `RollbackPlanEvidence` load, rehash,
>   target and blocking checks — omitted from the first draft, restored
>   here);
> - NEW: for RULING-O classes, `rendered.maez_response_sha256` equals
>   both the hash recomputed over the delimited display bytes and
>   `result.assistant_text_sha256` (§7b); null == null for all other
>   classes.

**D-amendment (artifact binding, cluster 2):**
`S7AuthorizationArtifactBinding` gains `maez_response_sha256 TEXT`
(nullable; non-null exactly for RULING-O classes), written at mint
from the value A13 verified, read by Gate B. This is the durable
carrier that lets consumption prove owner-read without re-reading the
challenge plane.

**D17 (rendered projection):** `RenderedRequestStatement` gains
`maez_response_display_text: str | None` and
`maez_response_sha256: str | None` (non-null exactly for RULING-O
classes); the rendered text gains an exact line for the response hash.

**D21 (consumption) — ANCHORED AMENDMENT (cluster 2):**

> KEPT-VERBATIM (canon L3521-3536): the no-direct-execution rule and
> the complete `consume_artifact_for_execution(...)` signature stand
> unedited at that anchor.
>
> AMENDED (canon L3537-3542, the wrapper's load-and-verify sentence).
> Replacement bytes: the wrapper loads the persisted
> `S7GuardedExecutionInvocation`, calls
> `load_guarded_execution_invocation_bundle(...)`, verifies the
> rendered statement, authority context, artifact binding, voice bundle
> use, source manifest, action params, preconditions, expiry lattice,
> and reservation token, THEN re-runs Gate A joins A1-A13 in full with
> the consumption-time clock (§7's enumerated clock-sensitive
> predicates), performs join B1 — `artifact.consult_attempt_id ==
> attempt.attempt_id` and the `completed → consumed` CAS from the
> design's §3 transition table succeeding IN THIS TRANSACTION — and
> only then delegates to inherited S7.1 consume. The attempt CAS and
> the grant consume commit or roll back together.
>
> KEPT-VERBATIM, each at its anchor and unedited by this amendment:
> the live-possession check and raw-token non-persistence (canon
> L3543-3552); the consume-time reserved-branch predicates (canon
> L3553-3557); `S7ExecutionAuthorization` as a non-authoritative
> compatibility carrier (canon L3558-3562); the
> `unpack_guarded_execution_invocation(...)` complete signature and
> its verification list (canon L3563-3598); the consume failure-code
> partition (canon L3600-3624); the `after_consume_before_commit`
> callback restrictions (canon L3626-3630); and the wrapper/deferred-
> flow obligations (canon L3632-3639). This amendment changes NONE of
> them — it inserts Gate B at one seam and nothing else.

## Refusal vocabulary — layer-mapped (Codex edit 8)

| Layer | Closed set |
|---|---|
| Attempt outcome (durable, canon D15 verbatim) | canon's list, unchanged |
| Producer refusal (pre-attempt) | `snapshot_component_unavailable`, `prompt_integrity_block`, `template_not_canon`, `store_integrity_failure` |
| Gate cause (validation, durable) | `stale_binding`, `wrong_consumer`, `attempt_replayed`, `attempt_expired`, `staging_lost`, `private_ref_unreplayable`, `receipt_mismatch`, `owner_read_required`, `context_manifest_violation`, `retry_exhausted`, and the three SHARED causes below |

Three causes are legitimately detectable at more than one layer and
therefore appear in more than one row: `store_integrity_failure`
(a seal or policy pre-image fails, at production or at replay),
`prompt_integrity_block` (D11 scan fails pre-inference, or its
evidence fails to recompute at replay), and
`marker_missing_or_malformed` (the parser's verdict at production, or
the same verdict reproduced at replay). Durable evidence ALWAYS
records the layer beside the cause, so the two occurrences are never
conflated — and Gate A/B rows use exactly these tokens, matching the
join tables above.

**Layer carrier (Codex: a rule with no carrier is not a rule).** The
closed layer vocabulary is `producer | attempt | gate_a | gate_b`.
Gates A and B WRITE NOTHING (§7); they RETURN `(cause, layer)`. The
CALLER persists it: the ceremony service writes the pair into the
existing refusal-history row via `_voice_seat_block(...)`, whose
schema gains `cause_layer TEXT NOT NULL` alongside its existing
`denial_reason`; the producer writes the same pair on its own
refusals. A refusal row whose `cause_layer` is absent or outside the
closed vocabulary is itself a `store_integrity_failure` at read time —
so the layer cannot quietly go missing.

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
