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
Cluster 2 SPLIT (§7): 2a (gate replay) is WRITTEN and awaits re-gate;
2b (owner-read authority) has its own design pass at
`docs/superpowers/specs/2026-08-14-cluster2b-owner-read-authority-design.md`,
which supersedes §7b and withdraws the artifact-binding amendment.
Cluster 3 (attested-result byte constructors) is WRITTEN and awaits
its gate.**

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

### 7. Two gates — SPLIT 2a / 2b (round-5 architectural finding)

**Finding, recorded rather than patched a fifth time.** Four gate
rounds failed on ONE property — *owner-read cannot be forged* — and
round 4 failed because I twice asserted properties of code structures
that do not exist. Both are now verified against the tree:

- `S7VerifiedAssertion` with a trustworthy `challenge_id` **does not
  exist**. The production verifier returns a plain dict with `ok`,
  `credential_ref`, `sign_count`, `user_presence`, `user_verification`
  and library fields — and **no challenge_id at all**
  (`s7_webauthn_verifier.py:143-151`); `authorize_finish` reads the
  challenge id from caller-supplied request JSON
  (`s7_webauthn_ceremony.py:538`). So a type whose mere existence
  proves "a founder tap covered THIS challenge" is not available to be
  passed — it must be BUILT, with a constructor only the verifier path
  can reach.
- `S7AuthorizationArtifactBinding`'s "existing canonical row-hash
  domain" **does not exist**: the class is not defined in
  `core/governance/` at all. There is no seal for new fields to sit
  inside.

**What this means.** Owner-read is not three bullets in a join table;
it is a SUBSYSTEM with three new constructions — a verifier-result
carrier with provenance, a sealed durable binding, and a challenge
fingerprint member. Specifying it as joins is why four rounds died on
the same property. Cluster 2 therefore SPLITS:

- **Cluster 2a — gate replay (this section below).** Gate A/B join
  logic, ordering, write discipline, clock, vocabulary, and the D16/D21
  anchored dispositions. Rests only on structures verified to exist.
  A13/B2 remain named as REQUIRED but their mechanism is 2b's.
- **Cluster 2b — owner-read authority (its own design pass).** Must
  begin from code verification, not prose: what the verifier can be
  made to return and who may construct it; whether the artifact
  binding exists to be amended or must be created; how the response
  hash enters the challenge fingerprint (the R11 pattern at
  `s7_webauthn_bootstrap.py:1001-1084` is the shape, verified) and is
  re-derived at finish before verification
  (`s7_webauthn_ceremony.py:565-592`). Until 2b freezes, RULING-O
  classes CANNOT be migrated — soul-write and pipeline classes (which
  need no owner-read) are unaffected, so the campaign is not blocked,
  only the two gravest classes are.

Everything below is cluster 2a.

### 7. Two gates — canon-grade (cluster 2a)

Rewritten whole rather than patched again: three rounds of edits left
self-contradictions between passages. Every ruling and every finding
is folded here at once.

Two distinct authority edges. **Gate A** validates before an
authorization artifact is minted (canon D16's seat) and runs INSIDE
`authorize_finish`, after the verifier has returned. **Gate B**
re-validates inside execution consumption (canon D21's seat) and is
the only place an attempt becomes `consumed`.

**Write discipline, stated exactly (supersedes the earlier blanket
claim).** Gate A performs NO INSERT, UPDATE or DELETE against any
table in any store; it is pure read-and-recompute and returns
`(verdict, cause, layer)`. Gate B performs EXACTLY ONE write — the
`completed → consumed` CAS of join B1 — inside the grant-consume
transaction, and no other. Refusal persistence is the caller's act
(see the layer carrier).

**Gate A joins** (ordered; `:now_z` is finish-time):

| # | Join | Refusal |
|---|---|---|
| A1 | recomputed seal over the attempt row's twelve-column domain == `attempt.row_seal_hash` | `store_integrity_failure` |
| A2 | `attempt.state='completed'` AND `attempt.expires_at > :now_z` AND `attempt.consumed_by_artifact IS NULL` | `attempt_expired` / `attempt_replayed` |
| A3 | `attempt.consumer_id` == requesting consumer AND `attempt.action == envelope.action` | `wrong_consumer` |
| A4 | `attempt.request_envelope_hash == canonical_hash(envelope)` AND `attempt.preview_hash == rendered.mutation_preview_hash` | `stale_binding` |
| A5 | `attempt.version_tuple_hash` resolves in the registry AND every member hash matches this gate's build | `stale_binding` |
| A6 | identity-policy and evidence-policy pre-image files rehash to the tuple's member hashes | `store_integrity_failure` |
| A6b | the result row is loaded ONLY via `attempt.result_row_ref` (never another key), `result_row_ref IS NOT NULL`, its row hash recomputes | `staging_lost` |
| A6c | `attempt.owner_session_ref` == the consuming card/dialog id presenting this request | `wrong_consumer` |
| A7 | snapshot rehashes to `attempt.snapshot_manifest_hash`; every private ref re-resolves machine-internally per §4b | `private_ref_unreplayable` |
| A8 | from the A6b row only: replayed prompt assembly == `result.messages_canonical_sha256`'s pre-image structure; manifest obeys D7's closed schema | `context_manifest_violation` |
| A9 | from the A6b row only: `AttestedConsultationResult.object_sha256` recomputes; `result.assistant_text_sha256` == hash of the staged normalized text | `receipt_mismatch` |
| A10 | parser re-run on the A6b row's normalized text with staged expected ids + nonce reproduces the staged marker exactly; its mapped D15 outcome == `attempt.outcome` | `marker_missing_or_malformed` |
| A11 | `parsed_marker_nonce_hash == expected_consultation_nonce_hash`; nonce-use row in expected lifecycle state AND `consultation_expires_at > :now_z` | `stale_binding` |
| A12 | prompt-integrity evidence recomputes (D11 scans) | `prompt_integrity_block` |
| A13 | owner-read, RULING-O classes only — see below | `owner_read_required` |

**A13 — mechanism owned by cluster 2b §6; the paragraph below states
the requirement, 2b states how it is held.** The validator takes
`verified_assertion: S7VerifiedAssertion` — the verifier's own return
value, in scope because D16 runs after verification — carrying `ok`,
`credential_ref`, `user_presence`, `user_verification`, and
`challenge_id`. **The challenge row is fetched by
`verified_assertion.challenge_id` and by no other key; no caller-
supplied challenge id exists anywhere in the signature.** A13
requires: `ok is True`, `user_verification is True`,
`user_presence is True`, that row unexpired at `:now_z`, and its
`maez_response_sha256` equal to BOTH the hash recomputed over the
delimited display region AND the staged
`result.assistant_text_sha256`. A different ceremony's row cannot be
reached: the only key is the one the authenticator just signed
against.

**Gate B joins** (consumption-time clock throughout):

- **A1-A12 re-run in full**, unchanged, with `:now_z` derived once (below).
- **A13 does NOT re-run at Gate B** (no verifier is present at
  execution and no challenge lookup occurs). It is replaced by B2.
- **B1** — `artifact.consult_attempt_id == attempt.attempt_id` AND the
  `completed → consumed` CAS succeeds in THIS transaction, atomic with
  grant consume. Refusal `attempt_replayed`.
- **B2** (RULING-O classes only) — mechanism owned by cluster 2b §6:
  the sealed owner-read evidence row for this artifact re-derives and
  every column matches, its `maez_response_sha256` == staged
  `result.assistant_text_sha256`, and the sealed row's own
  verifier-written facts hold (`user_presence=1`,
  `user_verification=1`, `credential_ref` non-null) — read from the
  seal, not re-asserted by the caller. Refusal `owner_read_required`.

**Clock.** Canon D21's consume signature takes `now: datetime`
(KEPT-VERBATIM); frozen §3 compares canonical UTC text. Gate B
converts ONCE at its top via `s7_now_z(now) -> str`, and every §3
predicate uses that single value. A datetime whose `tzinfo is None`
**or whose `tzinfo.utcoffset(now) is None`** refuses
`store_integrity_failure` — never assumed UTC. No other conversion
site exists.

**§7b — SUPERSEDED BY CLUSTER 2b.** This section's three amendments
were written before the structures they name were checked in code, and
two of them were wrong. Its replacement is
`docs/superpowers/specs/2026-08-14-cluster2b-owner-read-authority-design.md`,
which carries the verified ground and the three constructions. What
this document said, and what the tree says, recorded so no later reader
restores the error:

1. §7b claimed the binding force comes from membership in the
   challenge fingerprint preimage ("A copied column is not a binding;
   a fingerprint member is"). FALSE against this tree: `challenge_hash`
   is computed at creation and never recomputed or compared. But the
   first correction — "the column comparison IS the binding" — was
   ALSO wrong, because a column comparison is only as strong as the
   row it reads, and nothing signs the row. The answer is 2b §4: for
   RULING-O classes the challenge bytes themselves become the
   commitment, so the founder key signs the association. (2b §0 C2,
   §4; 2b §11 keeps the fingerprint recompute as separate work that
   does NOT close this.)
2. §7b amended `S7AuthorizationArtifactBinding`'s "existing canonical
   row-hash domain". FALSE twice: the class is absent from
   `core/governance/`, and canon's specified version (canon L1664-1675)
   has no row hash. 2b instead applies the live, sealed, cutover-proven
   R11 evidence-table shape at the same seat. (2b §0 C1, §5.)
3. §7b's third amendment — `RenderedRequestStatement` gaining
   `maez_response_display_text` and `maez_response_sha256`, and the
   byte-exact delimited display region — SURVIVES, and is restated
   with its enforcement seat in 2b §6b. The equality is enforced in
   `__post_init__`, so an inconsistent object cannot be CONSTRUCTED
   normally. That is not the same as cannot exist:
   `RenderedRequestStatement` is an ordinary frozen dataclass, and
   `object.__setattr__`, crafted deserialization, or other same-process
   mutation are not excluded. Every authority gate recomputes the
   region and its hash regardless. (An earlier revision of this bullet
   claimed the object "cannot exist" and called that stronger than a
   gate check; corrected here rather than deleted.)

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
>     ceremony_challenge_store: S7CeremonyChallengeStore,   -- A13 reads the
>                                                           -- row keyed BY the
>                                                           -- verified assertion
>     verified_assertion: S7VerifiedAssertion | None,       -- the verifier's own
>                                                           -- return value; its
>                                                           -- challenge_id is the
>                                                           -- ONLY lookup key.
>                                                           -- None for non-RULING-O
>                                                           -- classes
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
> - KEPT-VERBATIM (canon L2930-2934, `RollbackPlanEvidence` load, rehash,
>   target and blocking checks — omitted from the first draft, restored
>   here);
> - NEW: for RULING-O classes, `rendered.maez_response_sha256` equals
>   both the hash recomputed over the delimited display bytes and
>   `result.assistant_text_sha256` (mechanism in cluster 2b §6c, joins
>   A13.9 and A13.10); null == null for all other classes;
> - AMENDED (canon L2936-2954, the explicit hash-routing block).
>   Replacement bytes: the block stands as written EXCEPT the line
>   `semantic_reader_attempt_hash -> canonical_hash(
>   SemanticReaderAttemptEvidence)`, which is STRUCK (RULING R: no
>   reader exists to hash), and three lines are ADDED:
>   `attempt.row_seal_hash -> canonical_hash(twelve immutable columns)`,
>   `result.object_sha256 -> canonical_hash(AttestedConsultationResult
>   minus object_sha256)`, and
>   `owner_read_evidence.maez_response_sha256 -> sha256(delimited
>   display region)`. The third line named `binding.maez_response_sha256`
>   in an earlier revision; `S7AuthorizationArtifactBinding` does not
>   exist in code and is KEPT-VERBATIM in canon, so the routing target
>   is cluster 2b §5's sealed owner-read evidence row;
> - KEPT-VERBATIM (canon L2955-2958, the closing paragraph in full including its final sentence: the same
>   validator serves tests and finish-time recheck; tests may fake Maez
>   transport at the producer port but may not bypass this validator
>   for positive proof).

**D-amendment (artifact binding, cluster 2): WITHDRAWN.**
`S7AuthorizationArtifactBinding` does not exist in `core/governance/`,
and canon's specified version (canon L1664-1675) carries no row hash —
so there is nothing to amend and no seal for the fields to sit inside.
Canon L1664-1675 is KEPT-VERBATIM. The durable carrier that lets
consumption prove owner-read without re-reading the challenge plane is
the sealed per-artifact evidence table designed in cluster 2b §4,
written inside the mint transaction and re-derived inside the
consuming transaction — the R11 evidence shape applied to RULING O.

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
> and reservation token, THEN re-runs Gate A joins A1-A12 in full with
> the consumption-time clock (§7's enumerated clock-sensitive
> predicates; A13 does NOT re-run at this seat — no verifier is present
> and no challenge is read — it is replaced by B2), performs joins B1
> and B2 — `artifact.consult_attempt_id == attempt.attempt_id` and the
> `completed → consumed` CAS from the design's §3 transition table —
> and only then delegates to inherited S7.1 consume.
>
> The attempt CAS and the grant consume do NOT commit or roll back
> together, and an earlier revision of this paragraph said they did.
> They act on two different SQLite files: the consultation staging
> family in canon D9's state file, the artifact plane in the S7.1
> ceremony database (cluster 2b §1 V9). One-use does not depend on
> that transaction, because it is guarded once per plane: on the mint
> side an attempt binds to at most one artifact (`state='completed'
> AND consumed_by_artifact IS NULL`, plus `UNIQUE (consult_attempt_id)`
> on the owner-read evidence row), and on the consume side the
> artifact's own CAS admits at most one grant. A cross-plane failure
> leaves a spent attempt and an unconsumed artifact — the safe
> direction — and the retry consumes exactly once. Full statement in
> cluster 2b §7.
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
| Gate cause (validation, durable) | `stale_binding`, `wrong_consumer`, `attempt_replayed`, `attempt_expired`, `staging_lost`, `private_ref_unreplayable`, `receipt_mismatch`, `owner_read_required`, `context_manifest_violation`, and the three SHARED causes below (`retry_exhausted` is an ATTEMPT-layer outcome, not a gate cause: no Gate A or B join emits it) |

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
Gate A writes nothing and Gate B writes only B1's CAS (§7); both
RETURN `(verdict, cause, layer)`. The
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
