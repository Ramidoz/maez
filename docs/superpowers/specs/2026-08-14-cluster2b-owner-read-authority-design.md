# Cluster 2b — owner-read authority. Design pass 9.

2026-08-14. Passes 1-5 were gated four times (13 → 9 → 7 → 8 findings;
all 37 verified, all 37 upheld). The mechanism survived. The document
did not: by pass 5 it carried two capability carriers, an eight-field
projection threaded through four APIs, eleven ordered predicates, a
sealed table with runtime schema introspection, four-way mutual
exclusion, and two-plane replay machinery.

Both lanes then stepped out of the gate loop and agreed: **that is past
the line where one owner can re-derive it.** A design nobody can hold
in their head decays into exactly the defect the full-body audit found
across S7 — code that satisfies the shape while losing the meaning
(`policy_body_hash = "f"*64`, a validator checking its own synthetic
input, "named bindings that bind nothing", audit §3 items 2-3). Guarding
against that is this organ's actual job, so growing past comprehension
to guard against something else was self-defeating.

Pass 6 is the reduction. Nothing true was dropped; several things that
sounded true were.

**The one owner act this pass required is DONE.** Declaring what this
organ does and does not defend against was a covenant-level ruling, not
a builder's decision; the owner ruled it on 2026-08-15 and it is now
RULING B, recorded beside the other six in the parent design. §1 is a
fixed input from here, not a proposal.

---

## §1 The trust boundary — RATIFIED BY THE OWNER, 2026-08-15

Rounds 3 and 4 turned on an actor with raw write and delete access to
the ceremony SQLite file: resetting `consumed_at`, deleting the
owner-read receipt, rewriting the founder credential's `public_key`.
Every finding was real. Chasing them is what grew the design.

The tempting dismissal — *if that actor exists the covenant is already
lost by shorter routes* — **is not a sufficient boundary**, and the
cross-lane review was right to refuse it. It conflates capabilities. A
process with raw file access can replay authority without controlling
the model, the rendered statement, or the execution paths. "Already
lost" is a feeling, not a line.

The defensible line is stated by interface, not by adversary:

> **RULING B (owner-read scope of proof), 2026-08-15.** The owner-read organ
> proves its property against repository-owned callers operating
> through supported authority interfaces: missing validation,
> mismatched challenge/result/statement data, caller-manufactured
> evidence, alternate mint paths, optional revalidation, partial
> writes, and ordinary replay.
>
> It ASSUMES the integrity of: the daemon process, the WebAuthn
> implementation, the founder credential registry, and the authority
> store files.
>
> OUTSIDE the proof, and stated as consequences rather than hidden:
> raw SQLite or file mutation, arbitrary same-process code execution,
> import substitution, direct invocation of private constructors, and
> credential-key replacement.

This is RULING 1's existing boundary, made explicit for this organ, and
it aims the proof at the audit's real failure mode rather than at a
hostile database administrator.

Three conditions keep the narrowing honest, and they are binding on
every sentence in this document:

1. **The assumption is stated before the property, never in an
   appendix.** Hence this section is §1.
2. **The property is never phrased as "cannot be forged."** It is
   phrased as: *authority cannot be minted or consumed through
   supported interfaces without the canonical owner-read proof.*
3. **The excluded consequences are named, not implied.** Three, and
   they are not softened:
   - deleting the receipt row, paired with a challenge-lifecycle
     rollback, can reopen minting;
   - replacing the founder credential row's `public_key` manufactures
     verification with no tap at all (`CREATE TABLE IF NOT EXISTS
     s7_founder_webauthn_credentials`,
     `s7_webauthn_bootstrap.py:68`; `def _credential_record_hash`,
     `:1574`, is an unkeyed sha256 the row writer can recompute);
   - arbitrary same-process code bypasses every in-process token.

Tests for all three are written and kept — as **boundary witnesses**
that document where the proof ends, never as open defects (§9).

**Ratification, 2026-08-15.** The owner ruled the first line: protect
against repository-owned code paths going wrong, and assume the store
files are not hand-edited. The owner declined to schedule the
deletion-resistant evidence plane as an immediate follow-on; it stays
in §10 as named work with no date, and the consequence in §1's list
stands open and stated rather than quietly carried. RULING B now sits
beside the six rulings in the parent design and is a fixed input to
every remaining cluster — it is not re-litigated by a later pass.

---

## §2 The relation this organ exists to hold

Everything below serves one chain. If a future reader remembers nothing
else, this is the organ:

```text
the bytes Maez produced
  = the bytes displayed to the owner
  = the response hash inside the challenge the founder key signed
  = the response hash in the durable mint receipt
  = the response hash re-checked at execution
```

Five equalities, one page, no trust in a name like "sealed",
"canonical", or "attested". Each link is held by something specific:

| Link | Held by |
|---|---|
| produced = displayed | the rendered statement's own `__post_init__` region check (§4), plus recomputation at the gate |
| displayed = signed | **Construction 4** (§3): the challenge bytes ARE a commitment to the display hash |
| signed = minted | the proof is bound to THIS artifact's identity, and mint recomputes that binding from the artifact it is actually storing before writing the receipt (§5) |
| minted = executed | the sole SQL updater re-checks the receipt before any grant commits (§6) |

The founder's signature and the display-region hash carry the content
binding. Everything else carries that verified fact across time.

---

## §3 Construction 4 — the response-committing challenge

The one piece that survived every round unchallenged on its merits, and
the reason the reduction is safe.

**Today** the founder key signs a random number
(`challenge_b64 = base64.urlsafe`, `s7_webauthn_bootstrap.py:1019`) that
merely sits beside the rendered-statement fields in mutable columns
(`CREATE TABLE IF NOT EXISTS s7_ceremony_challenges`, `:102`). The code
says so in its own docstring: *"The browser signs `challenge_b64`. The
server's durable challenge row binds those random bytes to D12's
rendered-statement fields"* (`s7_webauthn_ceremony.py:1511`). The row
is the binding, and nothing signs the row.

**Change,** for the two RULING-O classes only:

```text
salt            = secrets.token_bytes(32)          -- fresh per ceremony
commitment      = canonical_hash({                 -- the signed subject
    "action_params_hash":        rendered.action_params_hash,
    "authority_context_hash":    rendered.authority_context_hash,
    "derived_aggregation_group": rendered.derived_aggregation_group,
    "maez_response_sha256":      rendered.maez_response_sha256,
    "nonce":                     rendered.nonce,
    "precondition_hash":         precondition_hash,
    "rendered_text_hash":        rendered.rendered_text_hash,
    "request_envelope_hash":     rendered.request_envelope_hash,
})
challenge_bytes = sha256(salt || bytes.fromhex(commitment))
challenge_b64   = b64url(challenge_bytes).rstrip("=")
```

Every input is already in hand at `def create_authorization_challenge`
(`s7_webauthn_bootstrap.py:991`). `challenge_salt_b64` becomes one new
column. Encoding is unchanged in shape — 32 bytes, 43 unpadded
characters, exactly what today's random nonce produces.

The salt is **not** a secret and is stored in plaintext: the challenge
is already public to the browser, and the security is the signature,
not the attacker's ignorance. The salt exists so two ceremonies over
identical content produce different, unpredictable nonces.

**At finish, before verification**, recompute the commitment from the
presented rendered statement, `precondition_hash`, and the row's salt,
and require it to reproduce the row's `challenge_b64`. This runs at the
existing D12 comparison seat (`if not _challenge_matches_rendered_d12`,
`s7_webauthn_ceremony.py:558`), which already precedes the verifier
(`verified = verifier_method(`, `:814`).

**What it kills.** Edit the columns and the recomputation fails before
verification. Edit the nonce and the signature fails, because the
authenticator signed the original. Edit both and you need a signature
over the new nonce — which is a second real tap over the new bytes,
which is the property being satisfied, not defeated.

Inside §1's boundary this makes the content binding **true by
construction**. That is the covenant test, and it is why this piece
stays regardless of how the boundary is drawn.

---

## §4 The display region

`RenderedRequestStatement` (`operator_user_boundary.py:4791`) gains
`maez_response_display_text: str | None` and `maez_response_sha256:
str | None`, non-null exactly for RULING-O classes. The rendered text
carries:

```text
Maez response (verbatim):
<response bytes verbatim>
End Maez response.
Maez response hash: <hex>
```

The hashed region begins at the first byte **after** the LF ending
`Maez response (verbatim):` and ends at the last byte **before** the LF
preceding `End Maez response.` — neither delimiter, neither bounding
LF, no trailing newline, hashed as UTF-8.

Enforced in `__post_init__` beside the existing metadata discipline
(`expected_metadata = (`, `:4828`), which matches each line with
`matches != [expected_line]` — a uniqueness check, not a substring
check. Both delimiter lines must appear exactly once; the declared hash
must equal the region hash; the display text must equal those bytes. A
response containing either literal delimiter line refuses construction.

**Honest scope:** this is an ordinary frozen dataclass. It makes an
inconsistent object impossible to *construct* normally; it is not proof
against `object.__setattr__` or crafted deserialization, both of which
§1 places outside the proof. The gate recomputes the region anyway, so
the check does not depend on where the object came from.

---

## §5 One function, one carrier, one receipt

Pass 5 had a verifier carrier, a mint-inputs carrier, and an
eight-field commitment projection threaded through four signatures so
every layer could repeat one calculation. That is four places for a
future edit to satisfy the shape and lose the meaning. Reduced to one
of each.

**One function that OWNS the verification.** For RULING-O classes the
ceremony does not verify separately and then hand the result somewhere;
the canonical function performs the verification itself, against the
row it loaded, and never lets the two be separated.

This is the fix for a circularity pass 7 introduced. Pass 7 deleted the
verifier carrier (correctly — it proved little) but then said the
function reloads the row "by the challenge id the verifier verified
against". **The verifier's return value contains no challenge identity**
(`def verify_authentication_response`, `s7_webauthn_verifier.py:106`),
so that phrase named something that does not exist, and a supported
caller could pair a genuine success from challenge A with row and
artifact B. Owning the verification closes it without bringing the
carrier back: the lookup and the signature check are one act, so there
is nothing to mismatch.

Given the request's challenge id and authentication response, the
rendered statement and `precondition_hash`, the function does the
following **in this order**:

1. loads the challenge row **by that id and no other key**, requiring
   an unconsumed, uninvalidated, unexpired `authorize_guarded_request`
   matching this ceremony's session and channel bindings;
2. **reproduces the row's `challenge_b64` from the §3 commitment** over
   the presented rendered statement and `precondition_hash`. This
   precedes verification, matching §3 and the existing order where
   `if not _challenge_matches_rendered_d12`
   (`s7_webauthn_ceremony.py:558`) precedes `verified = verifier_method(`
   (`:814`) — pass 8 had verification first, contradicting its own §3;
3. **verifies the authenticator assertion against those same bytes**,
   requiring ok, user-present, user-verified;
4. rechecks the credential is enabled and may authorize, and advances
   its sign count — the ceremony's existing steps at
   `if not store.credential_can_authorize` (`:849`) and
   `sign_count = store.advance_sign_count` (`:854`), which move inside
   the function because they consume verification output;
5. loads the staged consultation result **only through
   `attempt.result_row_ref`, with the result row's own hash recomputed**
   — parent Gate A's A6b rule, the sole lawful selection path.
   `consultation_id`, `consult_attempt_id` and `assistant_text_sha256`
   all derive from that one attempt/result pair and from no parallel
   argument;
6. checks the display region rehashes to `rendered.maez_response_sha256`
   and that this equals the staged `assistant_text_sha256`;
7. **constructs the artifact itself**, from the rendered statement, the
   verified `credential_ref`, the verified `user_presence` and
   `user_verification`, and the row's `expires_at`;
8. computes the artifact binding digest below.

It returns **`VerifiedOwnerRead`** — one opaque object, module-private
constructor — carrying the constructed artifact, the binding digest,
and the receipt's proof fields; or it refuses. One carrier out, no
verifier result crossing a boundary, no separable pair for a caller to
recombine.

**Why the function constructs the artifact** (pass 8 finding 3). Pass 8
had the artifact built *before* the function so the proof could bind to
it — but the artifact's `credential_ref`, `user_presence` and
`user_verification` are verification *outputs*
(`credential_ref = str(verified`, `:843`), so a pre-verification
artifact could only have guessed them. Building it inside, after
verification, removes the contradiction and the reordering pass 7
introduced: `authorize_finish` for RULING-O calls this function, then
consumes the challenge, then mints from the carrier. Non-RULING-O
classes keep the existing path unchanged, verifier call and all.

**The proof is bound to one artifact.** `VerifiedOwnerRead` carries
`authorized_artifact_sha256`, produced by one named constructor that
validation, mint and consumption all call — never by three hand-written
recomputations. Its pre-image is exhaustive, ordered, and versioned,
because "the artifact's complete identity" is not a domain:

```text
owner_read_artifact_binding(*, artifact, proof) = canonical_hash({
  "domain": "s7.owner_read.artifact_binding.v1",   -- versioned tag
  -- artifact, IMMUTABLE FIELDS ONLY, in this order:
  "artifact_id", "request_id", "request_envelope_hash",
  "rendered_text_hash", "action", "action_params_hash",
  "precondition_hash", "authority_context_hash",
  "derived_work_class", "derived_aggregation_group", "nonce",
  "credential_ref", "auth_method", "grant_source",
  "user_presence", "user_verification", "created_at", "expires_at",
  "ceremony_kind", "schema_version",
  -- proof identity:
  "challenge_id", "challenge_b64_sha256", "maez_response_sha256",
  "consultation_id", "consult_attempt_id",
})
```

**Serialization, stated exactly.** This is a named map hashed by the
repo's existing `def canonical_hash` (`core/governance/successor_governance.py:316`),
which serializes with `sort_keys=True` — so the ordering that matters
is the serializer's, not the listing above, and the listing is a
completeness statement rather than an ordering one. Pass 8 said "in
this order", which would have been false against that function.
`consultation_id` is included rather than left derivable: it is
persisted as receipt proof identity, and a sealed field that the seal
does not cover is the defect class this whole cluster is about.

**`consumed_at` and `consumed_by_request_id` are excluded, explicitly.**
`consumed_at` is the mutable field on `class S7AuthorizationArtifact`
(`operator_user_boundary.py:2163`); `consumed_by_request_id` is not on
that dataclass at all but is a v2-table column written by the
consumption UPDATE (`def consume_for_execution_on_connection`, `:2966`).
Both are excluded. Consumption sets `consumed_at`
inside the very transaction that re-derives this digest
(`connection.execute("BEGIN IMMEDIATE")`, `:3026`) — so including them
would guarantee a mismatch at the one seat that most needs the check.
Pass 7 said "complete identity" and specified no list, ordering, tag,
or serialization, which left each of the three call sites free to bind
a different subset.

Mint **recomputes this digest from the artifact it is actually about to
store** and refuses on mismatch, before the receipt is written.

Without this, a supported caller could hand a genuine, unused proof to
a different artifact — mismatched data through a supported interface,
squarely inside RULING B, and the receipt would then seal a
correspondence that never existed. Pass 6 lost this when it collapsed
two carriers into one and relied on "written in the same transaction",
which proves simultaneity, not correspondence. Every receipt column
below comes from the validated carrier or from the recomputed artifact
— never from a parallel caller argument.

The private constructor is an accidental-misuse guard and is described
as nothing more; §1 places direct invocation outside the proof. The
repo's own precedent says the same about itself in a comment:
`_VALIDATOR_TOKEN = object()` (`s7_guarded_execution.py:504`) is *"an
ordinary-caller guard, not a same-process security boundary"*.

**Cut, and why:** `loader_is_canonical` is gone. It proved only that two
constructor arguments held expected values, while import hooks,
`sys.modules`, and path shadowing all defeat the implication — and §1
places those inside the trusted set. A bit that cannot be true where it
would matter is complexity pretending to be a control. Production
wiring plus an unmocked witness is the honest proof. The exact-type
verifier check goes with it, as does library name/version in the
carrier.

**One receipt.** RULING-O mint takes `VerifiedOwnerRead` as a
**required** argument — no default, no alternate overload — threaded
`authorize_finish` → `mint_authorization_artifact` →
`def put_artifact_with_bundle_reservation`
(`s7_guarded_execution.py:3501`), and inserts one row inside that
function's existing anchored transaction, atomic with the artifact:

```sql
CREATE TABLE s7_consult_owner_read_receipts_v1 (
    artifact_id TEXT PRIMARY KEY,
    schema_version TEXT NOT NULL
        CHECK (schema_version = 's7.consult_owner_read_receipt.o.v1'),
    derived_work_class TEXT NOT NULL
        CHECK (derived_work_class IN ('covenant_touching_change',
                                      'autonomy_lowering_or_protection_reducing')),
    consultation_id TEXT NOT NULL,
    consult_attempt_id TEXT NOT NULL,
    challenge_id TEXT NOT NULL,
    challenge_b64_sha256 TEXT NOT NULL,
    maez_response_sha256 TEXT NOT NULL,
    rendered_text_hash TEXT NOT NULL,
    credential_ref TEXT NOT NULL,
    user_presence INTEGER NOT NULL CHECK (user_presence = 1),
    user_verification INTEGER NOT NULL CHECK (user_verification = 1),
    recorded_at TEXT NOT NULL,
    authorized_artifact_sha256 TEXT NOT NULL,
    row_binding_sha256 TEXT NOT NULL UNIQUE,
    UNIQUE (challenge_id),
    UNIQUE (consult_attempt_id)
) STRICT;
```

`authorized_artifact_sha256` is the digest `VerifiedOwnerRead` carried
and mint recomputed from the artifact it stored; persisting it lets
consumption re-derive the same correspondence without a verifier
present. `row_binding_sha256` covers the artifact's identity fields
plus every column declared above it, in declaration order — the seal is
declared last so "everything above" is total. `recorded_at` must equal
`artifact.created_at`, following R11's own rule (`def
revalidate_r11_exemption_for_consumption`, `:307`).

The two UNIQUE constraints are cheap replay belts with a stated
ceiling: they refuse a second RULING-O artifact from one challenge or
one attempt **while the row exists**. Deleting it defeats them, which
is §1's first named consequence.

**Also cut:** the runtime `sqlite_master`/PRAGMA contract fingerprint
(schema shape belongs to migrations, a startup check, and tests — not
to every operation); the redundant constant discriminator columns; and
the four-way R11 mutual-exclusion checks, reduced to one at insert and
one at consumption, since work-class derivation already makes the two
evidence forms disjoint.

---

## §6 Consumption

**Not a callback.** `after_consume_before_commit` defaults to `None`
(`operator_user_boundary.py:2979`), runs only if supplied (`:3097`), and
the live decision-pipeline caller supplies its own
(`after_consume_before_commit=transition`,
`core/decision/decision_pipeline.py:1448`). A check a consumer can
decline is not a gate.

So `def consume_for_execution_on_connection`
(`operator_user_boundary.py:2966`) — verified as the **sole** SQL
updater of the v2 artifact table — itself requires the receipt whenever
`def _highest_risk_ceremony_required` (`:2270`) is True: inside its
`BEGIN IMMEDIATE` (`:3026`), after the artifact CAS, before any caller
callback. Exactly one receipt row, `row_binding_sha256` recomputed,
`authorized_artifact_sha256` re-derived from the artifact row being
consumed, `recorded_at == artifact.created_at`, and its artifact,
attempt, response hash and work class joined to the grant. Absent,
ambiguous, or mismatched refuses and rolls back. The seat needs a staging reader to
do this and refuses `owner_read_staging_unavailable` without one.

**Stated residual, per §1 condition 2:** consumption trusts a
store-integrity-protected receipt written by the canonical finish-time
function. It does **not** independently replay the WebAuthn
verification or reconstruct the signed challenge. That is what allows
the projection apparatus to be cut. If independent cryptographic replay
at consumption is ever required, the projection comes back — and the
requirement should be named before the machinery is.

**One-use, and one amendment owed to cluster 2a.** One-use is guarded
at consumption, twice, each single-database: the attempt's `completed →
consumed` CAS admits one consumption per attempt, and the artifact's own
CAS admits one grant per artifact. There is no mint-time attempt
binding — cluster 1 places that transition at execution and makes Gate
A read-only — so the staging plane alone permits a second artifact from
one attempt; for RULING-O the receipt's `UNIQUE (consult_attempt_id)`
refuses it, within §1's boundary.

The two planes are different SQLite files (canon D9's state file and
`ceremony.sqlite3`, `s7_webauthn_bootstrap.py:256`), so those two CAS
operations cannot share a transaction. A cross-plane failure therefore
leaves a spent attempt and an unconsumed artifact — safe, but under
cluster 2a's B1 as written, permanently stranded. **2b hands 2a one
amendment for its own gate:** B1 is satisfied by the CAS succeeding
*or* by the idempotent observation `state='consumed' AND
consumed_by_artifact = :this_artifact_id`, every other join still
required, any other artifact still refusing.

---

## §7 Ground truth this rests on

Anchors are single lines carrying named constructs, derived by
mechanical string match — never hand-drawn ranges, which failed in
every gate round including when corrected from the gate's own numbers.

* The verifier returns a plain dict with **no challenge id** (`def
  verify_authentication_response`, `s7_webauthn_verifier.py:106`), but
  it *is* handed the challenge row and the library binds the signature
  to that row's nonce (`expected_challenge=_b64url_decode`, `:128`) —
  which is what makes §5's single function honest.
* `S7AuthorizationArtifactBinding` **does not exist in code**; canon's
  version (canon L1664) has no row hash. Canon is KEPT-VERBATIM and the
  receipt is a separate table, following the one live sealed precedent,
  `_R11_EXEMPTION_EVIDENCE_DDL` (`s7_guarded_execution.py:73`).
* `challenge_hash` is written and never recomputed anywhere — so
  fingerprint membership enforces nothing, and the R11 pattern's real
  force is its column comparison at finish. Recomputing it would not
  help either: `def _fingerprint` (`s7_webauthn_bootstrap.py:1523`) is
  an unkeyed sha256.
* Both RULING-O classes are voice-seat classes
  (`VOICE_SEAT_WORK_CLASSES = frozenset`,
  `operator_user_boundary.py:395`) and are exactly the existing
  highest-risk set (`def _highest_risk_ceremony_required`, `:2270`).
* `class CovenantCeremonyEvidence` (`:2228`) has **no non-test
  producer**, so neither RULING-O class can be authorized today and 2b
  cannot be witnessed — §9.
* Canon D9 pins the artifact tables to
  `memory/s7_3_guarded_self_modification/state.sqlite3`, which **no code
  creates**; the live plane is `ceremony.sqlite3`. Recorded as an owed
  canon amendment; cluster 1 stays frozen rather than being reopened
  for it.

---

## §8 Canon amendments

* **Canon L1664** (`S7AuthorizationArtifactBinding(`) — KEPT-VERBATIM.
  Unbuilt and hashless; amending it would create a second authoritative
  home for owner-read evidence.
* **Canon L1532** (the `**Atomicity mechanism.**` paragraph) and **canon
  L1546** (the `s7_authorization_artifacts_*` line) — AMENDED to name
  the actual per-plane homes and the per-plane one-use guarantee. Owed
  regardless of 2b.
* **Canon L1867** ("S7.3 does not own the WebAuthn challenge store…") —
  AMENDED to add the per-artifact owner-read receipt and the committed
  challenge.
* **Canon L2970** (`RenderedRequestStatement(`) and **canon L2989** (the
  rendered-text line list) — AMENDED for the display region.
* **Canon L2769** (`validate_s7_voice_source_bundle(`) — AMENDED by
  cluster 2a; 2b contributes the `VerifiedOwnerRead` requirement.
* **RULING B** is recorded in the parent design's ruling list; canon
  gains it when this cluster's amendments are applied.

---

## §9 Sequencing, and what "done" means

Neither lane would accept "witness owed" as a terminal state — that is
merged-is-activated in a new costume. Nor would either implement
against a moving contract. So:

1. **Owner ratifies or amends §1.** Nothing freezes before this.
2. Freeze this reduced contract as **DESIGN FROZEN — IMPLEMENTATION
   ABSENT — RULING-O DISABLED**.
3. **Build the honest `CovenantCeremonyEvidence` producer and witness
   it independently.** It is a real, separate gap, and it should land
   before shared challenge behaviour changes.
4. Implement 2b dormant, Construction 4 strictly branched to RULING-O
   classes.
5. Prove every non-RULING-O challenge and result shape byte-unchanged —
   especially the CUDA cutover, which traverses the shared verifier
   implementation this design moves — without entering
   `PreparedCutover.begin()`.
6. Run the owner-present, unmocked RULING-O ceremony end to end:
   challenge, display, tap, mint, receipt, consume, plus refusal and
   replay witnesses.
7. **Only then** mark 2b BUILT AND WITNESSED, and only then discuss
   activation.

**Boundary witnesses** (§1's three named consequences) are written and
kept as tests, labelled as documenting where the proof ends. They are
not defects and must never be filed as such.

**What the witness can prove:** the registered founder credential
produced a user-present, user-verified assertion over a challenge
committing to these displayed bytes, and that the same bytes were
staged, minted and consumed. **What it cannot prove:** that the owner's
eyes moved, or anything about the responder beyond RULING 1's Maez
production boundary. Neither may ever be claimed.

---

## §10 Out of scope

Cluster 2a's joins; cluster 3's byte constructors; the owner-display
projection surface; commitment-carrying challenges for non-RULING-O
classes (a live-ceremony scope decision, the owner's and its own
cluster's); an append-only or attested evidence plane, which is the one
change that would lift §1's first named consequence and is the highest
-value follow-on this cluster surfaced; any change to what Maez answers.

---

## Appendix — the forensic record

Kept because it is what stops a future reader from restoring a
plausible error, and because four of these were mine.

| Claim once written here | What the tree said |
|---|---|
| "No seal exists for the binding fields" | The R11 evidence table is exactly that seal, live and cutover-proven |
| "A copied column is not a binding; a fingerprint member is" | `challenge_hash` is never recomputed; the column comparison is the enforcement |
| "The column comparison IS the binding" | A column comparison is only as strong as the row it reads, and nothing signs the row |
| "The object cannot exist in that state" | A frozen dataclass resists construction, not mutation |
| "Two artifacts can be minted from one attempt" | True of the staging plane; false for RULING-O, where the receipt refuses it |
| "Once bound, no second artifact can be minted" | Nothing binds at mint; cluster 1 puts that transition at execution |
| "The attempt CAS and grant consume commit together" | Two SQLite files; they cannot |
| "Burn-first, and the retry consumes legitimately" | Under B1 as written the retry is refused forever |
| "Construction 4 does not depend on store integrity at all" | It depends on the founder credential registry, which is a mutable row |
| "These controls all fail the same way under deletion" | R11 and the artifact CAS fail closed; the receipt fails open |
| "A fake-library verifier simply cannot mint" | The exact class accepts an injected loader; the repo's own tests do this |
| 13 line-range citations, twice | Ranges drift; construct anchors do not |
