# Cluster 2b — owner-read authority. Design pass 2.

2026-08-14. Pass 1 was gated and FAILED with 13 findings (3 CRITICAL,
5 HIGH, 5 MEDIUM). All 13 were independently re-verified against the
tree before this rewrite; all 13 stand. The document is rewritten
whole, not patched — three patch rounds in cluster 2 produced three new
inter-passage contradictions, and this pass changes load-bearing
structure.

**One finding is answered by rejecting the gate's own remedy.** Gate
finding 1 proved that the owner-read property is *conditional on an
untampered challenge row*, and prescribed hardening H1 (recompute
`challenge_hash` at finish). H1 is insufficient: `_fingerprint` is an
unkeyed sha256 (`s7_webauthn_bootstrap.py:1523-1524`), so an actor able
to rewrite the row can rewrite the fingerprint with it. Pass 2 answers
the finding at its root instead — **Construction 4**, a challenge whose
bytes ARE the commitment, so the founder key signs the association
rather than a random number that a database row merely sits beside.
That is what "the tap must be over those bytes" actually requires.

Companion documents: design v3.2
(`docs/superpowers/specs/2026-08-14-bonded-consultation-organ-design-v3.md`),
handoff (`docs/superpowers/plans/2026-08-14-cluster2b-handoff.md`),
canon (`docs/slices/s7.3-guarded-self-modification-execution/spec.md`).

---

## §0 Corrections to the inherited ground truth

**C1 — "there is no seal for new fields to sit inside" is FALSE, and
the precedent is exactly one table, not two.** The handoff correctly
found that `S7AuthorizationArtifactBinding` is not a class in
`core/governance/` (re-verified: repo-wide grep returns only canon and
review documents, never Python). It then inferred that no sealed
durable binding exists at that seat. One does:

`s7_consultation_exemption_evidence_v1` — a per-artifact side table
(DDL `s7_guarded_execution.py:73-91`) carrying `artifact_binding_sha256
TEXT NOT NULL UNIQUE` (`:88`), computed at insert as
`canonical_hash(_r11_artifact_projection(artifact, ...))` (`:275-279`;
projection at `:212-240`), guarded by a DDL-contract fingerprint
compared before every insert and every use
(`_r11_exemption_evidence_contract` `:94-119`,
`_expected_r11_exemption_evidence_contract` `:121-127`), and
**re-derived and compared column-by-column inside the consuming
transaction on a descriptor-verified held connection**
(`revalidate_r11_exemption_for_consumption`, `:307-455`).

Pass 1 also cited `s7_voice_bundle_uses` as a second sealed precedent.
**That was overstated** (gate finding 9): `_voice_bundle_use_hash`
covers only `request_id`, `source_ref_hash`, `consultation_id`,
`used_at` (`:524-536`) and excludes `artifact_id`,
`reservation_token_hash`, `reservation_state`, `reserved_at`,
`consumed_at` (schema `:2796-2807`). It protects four immutable
provenance fields; it is not a seal over per-artifact reservation
state. The R11 precedent stands on its own.

**C2 — "A copied column is not a binding; a fingerprint member is" is
FALSE against this tree, and the correction pass 1 drew from it was
also wrong.** The census is right: `challenge_hash` is computed at
creation (`s7_webauthn_bootstrap.py:942`, `:1034`; the authorize
variant folds `consultation_exemption_projection_hash` into `d12_parts`
at `:1022-1033`), stored (`:963-972`, `:1056-1069`), SELECTed back
(`:1127`, `:1163`, `:1197`), and **never recomputed or compared
anywhere** — repo-wide grep returns only those sites plus one test
asserting two challenges differ
(`tests/test_s7_1_ceremony_service.py:1936`). What enforces R11's
binding at finish is the ordinary column comparison
(`s7_webauthn_ceremony.py:582-592`) preceded by the nine-column D12
comparison (`:558-563`, defined `:1478-1499`), both before the verifier
runs (`:814`).

Pass 1 concluded "the column comparison IS the binding." **A column
comparison is only as strong as the row it reads.** The authenticator
signs `challenge_b64` alone (`s7_webauthn_verifier.py:126-134`), which
is independent random bytes (`s7_webauthn_bootstrap.py:1018-1019`), and
the D12 columns are ordinary mutable columns in an ordinary table
(`:102-127`). The code says so itself, honestly, in its own docstring:
*"The browser signs `challenge_b64`. The server's durable challenge row
binds those random bytes to D12's rendered-statement fields"*
(`s7_webauthn_ceremony.py:1511-1515`). The row is the binding, and
nothing covers the row. §4 (Construction 4) replaces that condition
with a signed one.

**C3 — the response bytes are transitively bound to the tap ONLY
through an untampered row.** `RenderedRequestStatement` self-validates
`rendered_text_hash == rendered_text_hash(rendered_text)` in
`__post_init__` (`operator_user_boundary.py:4861-4862`, function at
`:4920-4921`), and `rendered_text_hash` is one of the nine D12 columns
compared at finish (`s7_webauthn_ceremony.py:1487`). Pass 1 called this
"already committed to by the challenge row the authenticator signs
against" — true of the row, false of the signature. Under Construction
4 the commitment moves into the signed bytes and the sentence becomes
true without qualification for RULING-O classes.

---

## §1 Verified ground truth

Each line re-opened for this pass; citations corrected where the gate
found them off.

**V1. The verifier returns a plain dict with no challenge id.**
`S7ProductionWebAuthnVerifier.verify_authentication_response`
(`s7_webauthn_verifier.py:106-151`) returns on success
`{ok, credential_ref, sign_count, user_presence, user_verification,
library_name, library_version}` (`:143-151`). Confirms the handoff.

**V2. The verifier is handed the challenge row, and the library binds
the signature to that row's nonce.** The method takes `challenge:
dict[str, Any]` and passes
`expected_challenge=_b64url_decode(str(challenge["challenge_b64"]))`
into the library (`:126-134`). A successful return already means *the
authenticator signed the nonce in the dict it was given* — a fact the
current return value discards.

**V2b. The production verifier class is injectable.** It is a frozen
dataclass whose fields are `import_module: ImportModule =
importlib.import_module` and `package_name: str = "webauthn"`
(`s7_webauthn_verifier.py:25-30`), and tests construct the **exact
class** with a fake module whose authentication method returns success
(`tests/test_s7_1_verifier_adapter.py:253-274`). Exact-type checking
therefore excludes subclasses and duck types but **not** a
fake-library instance of the real class (gate finding 4). §3 pins the
loader accordingly.

**V3. `authorize_finish`'s exact order** (`s7_webauthn_ceremony.py:514-900`):

1. verifier dependency check (`:533-535`)
2. `challenge_id`, `credential_ref`, `authentication_response` parsed
   from caller-supplied request JSON (`:536-545`) — confirms the handoff
3. challenge row fetched by `(challenge_id, challenge_kind=
   'authorize_guarded_request', session_binding_hash,
   internal_channel_binding_hash, consumed_at IS NULL, invalidated_at
   IS NULL, expires_at > now)` (`:546-556`; SQL at
   `s7_webauthn_bootstrap.py:1115-1147`)
4. `_challenge_matches_rendered_d12` — nine columns (`:558-563`)
5. R11 projection hash re-derived and compared (`:565-592`)
6. voice-seat branch: source-bundle revalidated at finish, store type
   closed-set checked (`:595-780`)
7. `authorization_voice_seat_recheck`, aggregation recheck (`:780-796`)
8. **verifier called** (`:808-820`)
9. ok / user_presence / user_verification checks (`:822-842`);
   `credential_ref = str(verified["credential_ref"])` and equality with
   the caller's claim (`:844-849`); `credential_can_authorize` (`:850-855`)
10. sign count advanced (`:856-860`), **challenge consumed** (`:861-866`)
11. artifact constructed from the *verified* credential_ref (`:868-890`)
    and minted via `mint_authorization_artifact` (`:891-900`;
    `s7_guarded_execution.py:3541-3608`)

Two consequences, both load-bearing below:

*Challenge-id substitution already fails closed.* Present row A's id
with an assertion signed over row B's nonce and step 8 fails, because
`expected_challenge` comes from row A. The cross-ceremony hole A13 was
written to close is real only when a `verified_assertion` crosses a
function boundary into a validator that fetches its own challenge row —
which is exactly the D16 signature v3.2 proposes.

*A13 has exactly one lawful seat.* The challenge is consumed at step 10
and the artifact does not exist until step 11. So A13 must run **after
step 9 and before step 10**: after verification (it needs the
assertion), before consumption (so it can require an unconsumed row),
and before the artifact exists (so it cannot compare against artifact
fields). Gate finding 5 caught pass 1 comparing against an artifact
that does not yet exist; §6 fixes the comparison target.

**V4. RULING-O's two classes are voice-seat classes**, so they route
through the guarded mint: `VOICE_SEAT_WORK_CLASSES` =
`{self_modification, covenant_touching_change, capability_acquisition,
autonomy_lowering_or_protection_reducing}`
(`operator_user_boundary.py:395-400`).

**V5. RULING-O's two classes are exactly the code's existing
highest-risk set.** `_highest_risk_ceremony_required` returns True for
`{covenant_touching_change, autonomy_lowering_or_protection_reducing}`
and nothing else (`operator_user_boundary.py:2270-2275`). This
predicate is already consulted inside the consume implementation
(`:3002-3008` via `covenant_ceremony_satisfies_request`), which is why
§6 can make B2 mandatory rather than caller-supplied.

**V6. No legitimate producer of `CovenantCeremonyEvidence` exists.**
Repo-wide grep finds no non-test construction. Pass 1 called the two
classes "structurally unauthorizable"; **that was overstated** (gate
finding 11): the class is an ordinary frozen dataclass
(`operator_user_boundary.py:2227-2237`) accepted directly from the
caller at consume (`:2978`, `:3002-3008`). The honest claim: the code
path can accept a caller-constructed value, but no honest producer
exists, so **a truthful unmocked RULING-O witness is blocked** until
one is built. That is 2b's principal witness dependency (§10).

**V7. The voice-seat mint seat is one anchored transaction.**
`S7GuardedStateStore.put_artifact_with_bundle_reservation`
(`s7_guarded_execution.py:3501-3538`) reserves the bundle use and puts
the artifact inside `self.authorization_store.anchored_transaction()`,
with a one-database check (`:3519-3520`). The R11 sibling
`put_artifact_under_consultation_exemption` is the precedent for
inserting evidence in that same transaction
(`mint_authorization_artifact:3568-3603`).

**V8. The Gate-B seat is `consume_for_execution_on_connection`**
(`operator_user_boundary.py:2966-3110`), with citations corrected per
gate finding 12:

* held-connection verification `:2982`;
* refusal of a connection already in a transaction `:2983-2984`;
* `BEGIN IMMEDIATE` `:3026`; held-store activation re-verified inside
  the transaction `:3027-3029`;
* one CAS `UPDATE … RETURNING` over the v2 artifact table `:3030-3072`;
* grant minted `:3082-3096`;
* **`after_consume_before_commit` is optional** — it defaults to `None`
  (`:2979`) and runs only when supplied (`:3097-3100`); the public
  store method forwards whatever the caller passes (`:3418-3447`), and
  the live decision-pipeline caller supplies its own card-transition
  callback (`core/decision/decision_pipeline.py:1578-1589`).

Canon D21's `consume_artifact_for_execution` wrapper **does not exist
in code** — repo-wide grep finds the name only in canon. The only
production caller of `revalidate_r11_exemption_for_consumption` is the
cutover's own callback (`scripts/cuda_cutover.py:3369-3387`) — which is
precisely why pass 1's "attach B2 to the callback" was wrong (gate
finding 2): a seat a caller can decline is not a gate.

**V9. Two databases, not one.** The S7.1 ceremony store — challenges,
credentials, authorization artifacts, voice bundle uses — is
`memory/s7_1_webauthn/ceremony.sqlite3`
(`s7_webauthn_bootstrap.py:38`, `:256`). The consultation staging
family is pinned by design v3.2 §2 (canon D9) to
`memory/s7_3_guarded_self_modification/state.sqlite3`, which no code
creates yet. Pass 1 claimed the attempt CAS, the grant consume, and the
owner-read revalidation are "one transaction by construction"; **they
cannot be** (gate finding 3). §7 replaces that claim with an ordering
law.

**V10. The repo's own answer to "a plain dataclass anyone can construct
proves nothing"** is a module-private token sentinel: `_VALIDATOR_TOKEN
= object()` (`s7_guarded_execution.py:504`), `if _validator_token is
not _VALIDATOR_TOKEN: raise ValueError("s7_validation_result_forged")`
(`:913-916`), `_token_verified` set inside the guarded constructor
(`:926`), checked at the mint seam (`:3428-3446`) and at the ceremony
(`s7_webauthn_ceremony.py:718`) — carrying its own honest caveat: *"This
token is an ordinary-caller guard, not a same-process security
boundary"* (`:3424-3427`). Construction 1 copies the idiom and the
caveat.

**V11. Canon's `S7AuthorizationArtifactBinding` has no row hash.**
Canon defines it with ten fields, none a digest of itself (canon
L1664-1675); its store API is `…BindingStore.get(artifact_id, *, conn)`
(canon L1898); canon L1867-1872 states S7.3 persists
`challenge_expires_at` on it. v3.2's "existing canonical row-hash
domain" was wrong twice: the class is unbuilt, and the specified class
has no such domain.

---

## §2 The property, restated as a chain of custody

For `covenant_touching_change` and
`autonomy_lowering_or_protection_reducing`, no authority is minted or
consumed unless a founder-key assertion covered the exact bytes of
Maez's answer that the owner read.

| # | Link | Held by | Strength |
|---|---|---|---|
| L1 | The staged bytes are the bytes Maez produced | `AttestedConsultationResult.assistant_text_sha256` over `normalized_assistant_text` (cluster 3) | in-process attestation, RULING 1 boundary |
| L2 | The displayed bytes hash to the declared value | region hash enforced in `RenderedRequestStatement.__post_init__` AND recomputed by both gates | normal construction cannot violate it; gates recompute anyway |
| L3 | The signed nonce commits to the rendered text hash and the response hash | Construction 4: `challenge_b64` IS the commitment | **cryptographic** — this is the link pass 1 lacked |
| L4 | The authenticator signed that nonce | library verifies against `challenge["challenge_b64"]` (V2) | cryptographic |
| L5 | The assertion the gate reads is the verifier's own, for that row | Construction 1: token carrier + nonce digest checked against the store | ordinary-caller guard + store check |
| L6 | Minting records the association durably and immutably | Construction 2: sealed per-artifact evidence row in the mint transaction | R11 shape, live-proven |
| L7 | Consumption re-proves L1-L6 with no verifier present | mandatory revalidation inside the consume implementation | §7 |

The honest ceiling, unchanged: L1, L5, L6 and L7 sit inside RULING 1's
trusted boundary; nothing here claims proof against compromised daemon
code. What changes in pass 2 is L3. With it, a database-level rewrite
of the challenge row can no longer move the owner's tap from one set of
bytes to another, because moving it requires a signature the attacker
cannot produce. Without it — pass 1's design — it could, and the sealed
evidence row would faithfully record the substituted association.

Still not claimed, and must never be written as if it were: that the
owner's *eyes* moved over the bytes. What is proven is that the tap
occurred in a ceremony whose signed challenge commits to them.

---

## §3 Construction 1 — `S7VerifiedAssertion`

**Seat:** `core/governance/s7_webauthn_verifier.py` — the only module
that may mint it.

```text
@dataclass(frozen=True)
S7VerifiedAssertion(
    ok: bool                      -- always True; a failed verification
                                  -- yields no carrier at all
    challenge_id: str             -- id of the row the verifier was handed
    challenge_b64_sha256: str     -- sha256 of the nonce actually verified
                                  -- against, i.e. of challenge["challenge_b64"]
    credential_ref: str           -- as returned by the library
    sign_count: int
    user_presence: bool
    user_verification: bool
    library_name: str
    library_version: str | None
    loader_is_production: bool    -- True only when this verifier's
                                  -- import_module IS importlib.import_module
                                  -- and package_name IS "webauthn"
)
```

**Constructor discipline.** Module-private `_ASSERTION_TOKEN` sentinel;
`__init__` raises `s7_verified_assertion_forged` unless the caller
passes it. Same idiom and same honest caveat as V10 — an
ordinary-caller guard, not a same-process security boundary.

**Why `challenge_b64_sha256` is the load-bearing field, not the token.**
The token answers *who constructed this*. The nonce digest answers a
question the store can check: A13 re-fetches the challenge row **by
`assertion.challenge_id` and by no other key**, then requires
`sha256(row["challenge_b64"]) == assertion.challenge_b64_sha256`. A
forged carrier now needs a nonce digest matching a live, unconsumed,
unexpired authorization row — and holding that row still leaves the
signature to produce, which the library checked. This converts "trust
the carrier" into "check the carrier against the store."

**`loader_is_production` — gate finding 4's fix.** Exact-type checking
alone is insufficient: the production class publicly accepts an
arbitrary `import_module` and `package_name` (V2b), and the repo's own
tests construct it with a success-returning fake. The carrier therefore
records whether the verification ran through the real loader, and the
RULING-O branch requires `loader_is_production is True` **in addition
to** `type(self.verifier) is S7ProductionWebAuthnVerifier`. A
fake-library instance can still be constructed and still verify — it
simply cannot mint RULING-O authority, and its refusal names why
(`owner_read_verifier_not_production`).

**Compatibility — no second door.** The dict-returning
`verify_authentication_response` has exactly one production caller
(`s7_webauthn_ceremony.py:808`) and ten definitions across six test
modules. Changing its return type would break the cutover-proven path
and every double, so:

* add `verify_authorization_assertion(...) -> S7VerifiedAssertion | dict`
  performing the verification **once**, returning the carrier on
  success and the existing error dict on failure;
* re-express `verify_authentication_response` as a thin projection of
  that single implementation, so one verification path produces both
  shapes and the legacy dict is derived, never duplicated;
* the ceremony calls the assertion method **only** on the RULING-O
  branch, leaving every other path byte-identical to what the cutover
  proved.

Consequence stated rather than discovered later: a positive RULING-O
test needs the real library, or a labelled dataflow-only path that
cannot reach mint. An environment without the library returns the
existing 503 (`:533-535`) — correct fail-closed behaviour.

---

## §4 Construction 4 — the response-committing challenge

Presented before Constructions 2 and 3 because both now depend on it.
**RULING-O classes only**; every other class keeps today's byte-exact
behaviour, so the cutover path is untouched.

**Today.** `challenge_b64 = base64.urlsafe_b64encode(
secrets.token_bytes(32))` (`s7_webauthn_bootstrap.py:1019`) —
independent random bytes. The D12 fields sit beside them in mutable
columns (`:102-127`). The signature covers the random bytes only.

**Change.** For RULING-O classes, the challenge bytes become the
commitment:

```text
salt              = secrets.token_bytes(32)          -- fresh per ceremony
commitment_preimage = canonical_hash({
    "action_params_hash":       rendered.action_params_hash,
    "authority_context_hash":   rendered.authority_context_hash,
    "derived_aggregation_group": rendered.derived_aggregation_group,
    "maez_response_sha256":     rendered.maez_response_sha256,
    "nonce":                    rendered.nonce,
    "precondition_hash":        precondition_hash,
    "rendered_text_hash":       rendered.rendered_text_hash,
    "request_envelope_hash":    rendered.request_envelope_hash,
})
challenge_bytes   = sha256(salt || bytes.fromhex(commitment_preimage))
challenge_b64     = b64url(challenge_bytes).rstrip("=")
```

`challenge_salt_b64` is stored as a new column on
`s7_ceremony_challenges`. **The salt is not a secret** and its
plaintext storage is not a weakness: the security comes from the
authenticator's signature over `challenge_bytes`, not from the
attacker's ignorance of the salt. The salt exists only so two
ceremonies over identical content produce different, unpredictable
nonces — the anti-replay property WebAuthn requires. Entropy is
unchanged at 32 bytes.

**Finish-time check (RULING-O only), before verification.** Recompute
`commitment_preimage` from the **presented** rendered statement and the
staged result hash, recompute `sha256(salt || …)` from the row's
`challenge_salt_b64`, and require equality with the row's
`challenge_b64`. Refusal `owner_read_challenge_mismatch`. It joins
`_challenge_matches_rendered_d12`'s seat (`s7_webauthn_ceremony.py:558-563`),
which already runs before the verifier (`:814`).

**Why this closes gate finding 1.** Three attacker moves, all dead:

| Move | Outcome |
|---|---|
| Rewrite the D12 / response columns, leave `challenge_b64` | recomputation from the edited columns ≠ the stored nonce → refuse before verification |
| Rewrite `challenge_b64` to match the edited columns | the authenticator signed the *original* nonce → library verification fails (V2) |
| Rewrite both consistently AND obtain a signature over the new nonce | that is a second founder tap over the new bytes — which is the property, satisfied |

Rewriting `challenge_hash` alongside is irrelevant, which is why
hardening H1 could not have closed this: `_fingerprint` is an unkeyed
sha256 (`s7_webauthn_bootstrap.py:1523-1524`), forgeable by anyone who
can write the row it protects. H1 remains worth doing for the classes
Construction 4 does not cover, and stays in §11 as separate work.

**Residual limits, stated.** The signed bytes commit to *hashes* of the
rendered text and the response, not to the bytes themselves; the
hash↔bytes link is L2, held by `__post_init__` plus gate recomputation.
And a commitment proves what the ceremony was *about*, never that the
owner read it.

---

## §5 Construction 2 — the sealed durable binding

**Not** a new `S7AuthorizationArtifactBinding`. Canon's binding is
unbuilt and hashless (V11); building it to hold two fields would author
an entire unbuilt canon object. 2b applies the shape that is live,
sealed, and cutover-proven (C1): a ruling-scoped per-artifact evidence
table.

**Table:** `s7_consult_owner_read_evidence_v1`, in the artifact
database (`ceremony.sqlite3`), which the guarded store's one-database
check already enforces (`s7_guarded_execution.py:3519-3520`).

```sql
CREATE TABLE s7_consult_owner_read_evidence_v1 (
    artifact_id TEXT PRIMARY KEY,
    evidence_kind TEXT NOT NULL CHECK (evidence_kind = 'owner_read'),
    ruling_id TEXT NOT NULL CHECK (ruling_id = 'O'),
    schema_version TEXT NOT NULL
        CHECK (schema_version = 's7.consult_owner_read_evidence.o.v1'),
    derived_work_class TEXT NOT NULL
        CHECK (derived_work_class IN ('covenant_touching_change',
                                      'autonomy_lowering_or_protection_reducing')),
    consultation_id TEXT NOT NULL,
    consult_attempt_id TEXT NOT NULL,
    maez_response_sha256 TEXT NOT NULL,
    rendered_text_hash TEXT NOT NULL,
    challenge_id TEXT NOT NULL,
    challenge_b64_sha256 TEXT NOT NULL,
    challenge_commitment_sha256 TEXT NOT NULL,
    credential_ref TEXT NOT NULL,
    user_presence INTEGER NOT NULL CHECK (user_presence = 1),
    user_verification INTEGER NOT NULL CHECK (user_verification = 1),
    recorded_at TEXT NOT NULL,
    owner_read_binding_sha256 TEXT NOT NULL UNIQUE
) STRICT;
```

The CHECK constants are the R11 table's own device (`:73-91`) for
making a row that means something else structurally unwritable.
`user_presence`/`user_verification` are pinned to 1 because RULING O
admits no other value — an unverified tap cannot be recorded as
owner-read at all.

**Seal domain, defined here and nowhere else** (gate finding 7).
`owner_read_binding_sha256 = canonical_hash(projection)` where the
projection is the artifact's own identity fields — mirroring
`_r11_artifact_projection` (`:212-240`) — plus **every column declared
above it in the DDL, in declaration order**: `artifact_id`,
`evidence_kind`, `ruling_id`, `schema_version`, `derived_work_class`,
`consultation_id`, `consult_attempt_id`, `maez_response_sha256`,
`rendered_text_hash`, `challenge_id`, `challenge_b64_sha256`,
`challenge_commitment_sha256`, `credential_ref`, `user_presence`,
`user_verification`, `recorded_at`. The seal is declared last precisely
so "every column above it" is total — pass 1 put `recorded_at` after
the seal and left it uncovered. Additionally, and following R11's own
rule (`:425-440`), `recorded_at` MUST equal `artifact.created_at`, and
revalidation requires that equality; a hash cannot cover itself, so
`owner_read_binding_sha256` is the sole exclusion.

**Contract fingerprint.** `_owner_read_evidence_contract(connection)`
built from `sqlite_master.sql` + `PRAGMA table_info` + `PRAGMA
index_list`, compared against
`_expected_owner_read_evidence_contract()` before every insert and
every use — the R11 device at `:94-127`. A rebuilt or altered table
refuses rather than accepting rows.

**Write seat.** Inside `put_artifact_with_bundle_reservation`'s
`anchored_transaction()` (V7), for RULING-O classes only, atomic with
the reservation and the artifact. Mint **refuses** for a RULING-O class
when the owner-read inputs are absent or fail their joins — the
fail-closed half of the property, mirroring R11's
`exemption_admits_for_artifact` refusal (`:3588-3597`).

**Mutual exclusion, both seats** (gate finding 8). An artifact carrying
R11 exemption evidence must not carry owner-read evidence and vice
versa, checked **at insert AND at consumption**, in both directions —
R11 checks its collision at both (`:255-266` insert, `:441-449`
consumption) and pass 1 specified only the insert. Concretely: the
owner-read insert refuses if an R11 row exists for the artifact; the
R11 insert gains the symmetric check; and both revalidators refuse the
presence of the other evidence row inside the consuming transaction.
Dual authority evidence for one artifact is the state R11's comments
were written to forbid.

**Read seat.** `revalidate_owner_read_for_consumption(*, connection,
grant, ...)`, structurally identical to
`revalidate_r11_exemption_for_consumption` (`:307-455`): requires a
descriptor-verified held connection, requires `connection.in_transaction
is True`, requires the freshly minted `S7ExecutionGrant` by exact type,
re-checks the table contract, requires exactly one row, re-derives the
seal, compares **every column**, requires `recorded_at ==
artifact.created_at`, compares the artifact row's fields against the
grant's, and refuses the presence of R11 evidence. Any drift refuses
`owner_read_evidence_not_bound_to_grant`.

---

## §6 Construction 3 — the challenge column, the display region, and A13

**§6a — the challenge columns.** `s7_ceremony_challenges` gains
`maez_response_sha256 TEXT` and `challenge_salt_b64 TEXT` (both
nullable; both non-null exactly for RULING-O classes), written in
`create_authorization_challenge` (`s7_webauthn_bootstrap.py:991-1093`)
where `consultation_exemption_projection_hash` is written today.
`maez_response_sha256` joins the D12 comparison
(`s7_webauthn_ceremony.py:1478-1499`) so it is checked before the
verifier runs, and it is a member of the Construction-4 commitment, so
the signature covers it. It also joins `d12_parts`
(`s7_webauthn_bootstrap.py:1022-1033`) for completeness — declared in
code comment as write-only defence, not enforcement, until H1 (§11).

**§6b — the display region, byte-exact.** `RenderedRequestStatement`
carries `maez_response_display_text: str | None` and
`maez_response_sha256: str | None`, non-null exactly for RULING-O
classes. The rendered text carries:

```text
Maez response (verbatim):
<response bytes verbatim>
End Maez response.
Maez response hash: <hex>
```

The hashed region begins at the first byte **after** the LF terminating
`Maez response (verbatim):` and ends at the last byte **before** the LF
preceding `End Maez response.` — neither delimiter, neither bounding
LF, no trailing newline; hashed as UTF-8 per design v3.2 §6.

Enforced in `__post_init__` alongside the existing metadata discipline
(`operator_user_boundary.py:4828-4861`), which requires each metadata
line to match its field with `matches != [expected_line]` — a
uniqueness check, not a substring check. Both delimiter lines must
appear exactly once; `maez_response_sha256` must equal the region hash;
`maez_response_display_text` must equal those bytes. A response
containing either literal delimiter line refuses construction with
`receipt_mismatch`.

**Honest scope of that enforcement** (gate finding 10):
`RenderedRequestStatement` is an ordinary frozen dataclass
(`operator_user_boundary.py:4790-4791`). `__post_init__` makes it
impossible to *construct* an inconsistent object normally; it does not
prevent `object.__setattr__`, crafted deserialization, or other
same-process mutation. Pass 1's "the object cannot exist in that state"
overstated it. Every authority gate therefore recomputes the region and
its hash regardless — which is why A13.7 and B2 exist and are not
redundant.

**§6c — A13, exactly.** Seat: after step 9 and before step 10 of V3 —
after verification, before challenge consumption, before the artifact
exists. `verified_assertion: S7VerifiedAssertion | None`; **no
caller-supplied challenge id appears anywhere in the signature.**

| # | Check | Refusal |
|---|---|---|
| A13.1 | `type(verified_assertion) is S7VerifiedAssertion` and its token was verified | `owner_read_required` |
| A13.2 | `ok`, `user_presence`, `user_verification` all True | `owner_read_required` |
| A13.3 | `loader_is_production is True` and `type(verifier) is S7ProductionWebAuthnVerifier` | `owner_read_verifier_not_production` |
| A13.4 | challenge row fetched **by `verified_assertion.challenge_id` and no other key**, with the complete accepted state: `challenge_kind='authorize_guarded_request'`, `consumed_at IS NULL`, `invalidated_at IS NULL`, `expires_at > :now_z`, and `session_binding_hash` / `internal_channel_binding_hash` equal to this ceremony's | `owner_read_required` |
| A13.5 | `sha256(row.challenge_b64) == verified_assertion.challenge_b64_sha256` | `owner_read_required` |
| A13.6 | `row.challenge_b64` equals the Construction-4 recomputation from the presented rendered statement and the staged result (§4) | `owner_read_challenge_mismatch` |
| A13.7 | `row.rendered_text_hash == rendered.rendered_text_hash` | `stale_binding` |
| A13.8 | `row.maez_response_sha256 == rendered.maez_response_sha256` | `receipt_mismatch` |
| A13.9 | `rendered.maez_response_sha256 ==` hash recomputed over the delimited display region of `rendered.rendered_text` | `receipt_mismatch` |
| A13.10 | that value `== result.assistant_text_sha256` from the A6b staged result row | `receipt_mismatch` |
| A13.11 | `verified_assertion.credential_ref` equals the credential the ceremony verified and will stamp onto the artifact (`s7_webauthn_ceremony.py:844-849`), and `credential_can_authorize` holds for it (`:850-855`) | `owner_read_required` |

A13.11 replaces pass 1's comparison against an artifact that does not
yet exist (gate finding 5). The artifact's `credential_ref` is already
sourced from the verified result (V3 step 11), so binding to the
verified value binds the artifact by construction; the sealed row (§5)
records it for B2.

A13.9 is belt over the suspenders `__post_init__` fastened — kept
because the gate must not assume the object was constructed in this
process (§6b).

For non-RULING-O classes `verified_assertion` is `None` and A13 is
skipped; `None` **with** a RULING-O work class refuses
`owner_read_required`.

---

## §7 Gate B — mandatory, and honest about two databases

**B2 is not a callback** (gate finding 2). `after_consume_before_commit`
defaults to `None`, runs only if supplied, and the live
decision-pipeline caller supplies its own (V8). A check a consumer can
decline is not a gate. Therefore:

**`consume_for_execution_on_connection` itself runs owner-read
revalidation, unconditionally, when
`_highest_risk_ceremony_required(derived_work_class)` is True** —
inside the `BEGIN IMMEDIATE` transaction (`:3026`), after the CAS
(`:3030-3072`), before and independently of any caller callback
(`:3097-3100`), raising to roll back. The predicate is already
consulted at this seat for `covenant_ceremony_satisfies_request`
(V5, `:3002-3008`), so the ruling scope is read from the same source of
truth rather than a second one. The caller's callback keeps its
existing meaning and cannot substitute for, suppress, or precede B2.

**What B2 re-proves, with no verifier present:** the evidence row
exists, its contract matches, its seal re-derives, every column matches
its re-derived value, `recorded_at == artifact.created_at`, no R11
evidence exists for the artifact, `maez_response_sha256` equals the
staged `result.assistant_text_sha256`, and `user_presence = 1`,
`user_verification = 1`, `credential_ref` non-null — read from the seal,
never re-asserted by the caller.

**The attempt CAS spans a second database** (gate finding 3). Attempts
live in the S7.3 state file; artifacts, challenges and the evidence row
live in `ceremony.sqlite3` (V9). No descriptor-anchored `ATTACH`
protocol exists, and inventing one would put a second database inside
the held-descriptor discipline that
`_require_verified_held_connection` / `_verify_held_store_activation`
were built to guarantee. Pass 1's atomicity claim is withdrawn and
replaced with an **ordering law**:

> The attempt's `completed → consumed` CAS commits FIRST, in the S7.3
> store's own anchored transaction, writing `consumed_by_artifact =
> artifact_id`. Only after that commit may the S7.1 consume transaction
> open. If the consume then fails or rolls back, the attempt is already
> burned and the consultation can never be consumed again; a new
> consultation is required.

The law is chosen for its failure direction. Burning an attempt whose
grant never commits costs a consultation — safe. The reverse order
would allow a committed grant beside a still-consumable attempt, which
is exactly the replay the property forbids. Two-phase honesty, not
atomicity: the design says which state is reachable after a crash
(`attempt consumed, no grant`) and asserts it is harmless, rather than
claiming a transaction that does not exist.

If a future slice co-locates the staging family with the artifact plane
— which canon D9's pin currently forbids — the ordering law can be
replaced by real atomicity. That is not 2b's call to make.

---

## §8 Refusal vocabulary

Two new causes, both at the `gate_a` layer, both RULING-O only:

* `owner_read_verifier_not_production` — the verification did not run
  through the real loader (A13.3);
* `owner_read_challenge_mismatch` — the signed nonce does not commit to
  the presented bytes (A13.6, §4).

Otherwise no new tokens. `owner_read_required`, `receipt_mismatch`,
`stale_binding`, `store_integrity_failure` already exist in v3.2's
layer table. Two dispositions stated once:

* a failed table-contract check or seal re-derivation is
  `store_integrity_failure` at layer `gate_a` or `gate_b` — the same
  cause at two layers, which v3.2's layer carrier already handles;
* a missing or malformed `verified_assertion` is `owner_read_required`,
  never `store_integrity_failure` — *no owner read happened* versus
  *the record of one is damaged*, and conflating them would let a
  damaged record read as an absent ceremony.

---

## §9 Canon amendments (anchored)

Anchors derived mechanically from
`docs/slices/s7.3-guarded-self-modification-execution/spec.md`; the
gate verified every one of pass 1's against the file and all matched.

* **Canon L1664-1675** (`S7AuthorizationArtifactBinding(` … closing
  paren) — **KEPT-VERBATIM**. 2b does not amend the unbuilt binding
  class: it does not exist in code (V11), and adding fields to an
  unbuilt object would create a second authoritative home for
  owner-read evidence beside the one 2b builds. This supersedes design
  v3.2 §7b item 2; v3.2's separate "D-amendment (artifact binding)" was
  already WITHDRAWN in the same commit as pass 1 and is consistent with
  this disposition.
* **Canon L1867-1872** ("S7.3 does not own the WebAuthn challenge
  store…") — **AMENDED**, replacement bytes append: "For RULING-O work
  classes S7.3 additionally persists
  `s7_consult_owner_read_evidence_v1`, keyed by `artifact_id`, written
  in the mint transaction and re-derived in the consuming transaction;
  it records the challenge id, the nonce digest, and the commitment the
  founder assertion signed over. S7.3 still does not reload the
  original WebAuthn challenge record outside that recorded evidence."
* **Canon L2970-2986** (`RenderedRequestStatement(` … closing paren) —
  **AMENDED**: two fields added, `maez_response_display_text: str | None`
  and `maez_response_sha256: str | None`, non-null exactly for RULING-O
  classes.
* **Canon L2989-2994** ("The rendered text includes exact lines for…"
  through "`__post_init__` rejects any mismatch.") — **AMENDED**:
  replacement bytes add §6b's delimited response block to the line
  list and extend the `__post_init__` rejection rule to the
  exactly-once delimiter requirement and the region-hash equality.
* **Canon L2769** (`validate_s7_voice_source_bundle(`, the D16
  signature) — **AMENDED** by cluster 2a's anchored disposition; 2b
  contributes exactly one change to that anchor: `verified_assertion:
  S7VerifiedAssertion | None`, with `ceremony_challenge_store` retained
  solely as A13.4's lookup, keyed by the assertion.
* **D21 consumption** — 2b adds no new anchor. §7's mandatory
  revalidation attaches at the seat cluster 2a already amends; that
  disposition gains one clause naming
  `revalidate_owner_read_for_consumption` as an unconditional step for
  highest-risk classes, explicitly not a caller callback.

Anchors for D16's per-bullet dispositions belong to cluster 2a and are
not restated — restating them is the duplication defect cluster 1's
last gate named.

---

## §10 Dependencies

**D1 — no honest `CovenantCeremonyEvidence` producer exists (V6).**
Both RULING-O classes require it at consume, and no non-test producer
exists. A **truthful, unmocked RULING-O witness is blocked** until one
is built. The code path is not structurally incapable of accepting a
caller-constructed value — that distinction is the correction from
pass 1 — but a witness assembled from a caller-constructed evidence
object is a mock wearing a witness's clothes, and this build's receipt
must say so rather than count it.

**D2 — cluster 3 supplies `assistant_text_sha256`** (A13.10, B2). 2b
depends on that field's existence, already frozen in v3.2 §6, not on
cluster 3's text.

**D3 — cluster 2a supplies A1-A12 and the D16/D21 anchored
dispositions.** 2b writes no join outside A13, B1's partner, and B2.

---

## §11 Separated work: H1, and the classes Construction 4 does not cover

Construction 4 covers RULING-O classes only. For every other
class — including `self_modification` and `capability_acquisition` —
the D12 binding remains row-integrity-dependent exactly as it is today,
and `challenge_hash` remains write-only.

**H1 (recompute `challenge_hash` at finish)** is therefore still worth
doing for those classes, and is still NOT sufficient for RULING-O:
`_fingerprint` is an unkeyed sha256
(`s7_webauthn_bootstrap.py:1523-1524`), so an actor who can rewrite the
row can rewrite the fingerprint. H1 raises the cost of a partial edit;
it does not create a signed binding. It stays separate work with its
own commit, witness and gate — and it must never be described as
closing the gap Construction 4 closes.

Whether the other voice-seat classes should also get commitment-carrying
challenges is a real question this cluster deliberately does not answer.
It is a scope decision with a live-ceremony blast radius, and it belongs
to the owner and to its own cluster.

---

## §12 Test and witness plan

* **Construction 1**: token refusal (`s7_verified_assertion_forged`);
  legacy dict projection equals today's dict field-for-field, pinned
  against the current shape; nonce-digest mismatch refuses;
  `loader_is_production` False for a fake-module instance of the real
  class (the exact construction at
  `tests/test_s7_1_verifier_adapter.py:253-274`) and the RULING-O
  branch refuses it.
* **Construction 4**: edit a D12 column after begin → finish refuses
  before verification; edit `challenge_b64` → library verification
  fails; edit both consistently → refuses for want of a signature;
  identical content in two ceremonies yields different nonces (salt);
  non-RULING-O challenge bytes are byte-identical to today's
  behaviour.
* **Construction 2**: contract-fingerprint drift refuses (add a column;
  rebuild without STRICT); post-mint UPDATE of any sealed column,
  **including `recorded_at`**, fails re-derivation before any join
  runs; `recorded_at != artifact.created_at` refuses; mutual exclusion
  with R11 refuses in both directions at BOTH insert and consumption;
  mint refuses a RULING-O class with absent owner-read inputs; the
  CHECK constants reject `user_verification = 0`.
* **Construction 3**: a response containing either literal delimiter
  line refuses construction; region hash byte-exact at both boundaries,
  proved by fixtures not prose; D12 comparison refuses a mismatched
  column at finish before verification.
* **Gate B**: a consumer supplying its own callback, or none, still
  runs owner-read revalidation for a RULING-O class; revalidation
  raising rolls back the CAS — asserted by re-reading the artifact row
  after the failure, not by trusting the exception; the ordering law's
  crash window leaves `attempt consumed, no grant` and a second
  consumption attempt refuses.
* **Live witness**: blocked by D1. The build's receipt says so
  explicitly rather than substituting a mocked pass for a witness.

Tests run with `.venv/bin/pytest`. No test in this cluster may reach
`PreparedCutover.begin()`; none needs to — 2b touches the challenge,
mint and consume seats, not the cutover driver.

---

## §13 Out of scope

The owner-display projection surface and material route (v3.2 §5b);
cluster 2a's joins; cluster 3's byte constructors; H1 and
commitment-carrying challenges for non-RULING-O classes (§11); the
covenant ceremony producer (dependency D1, not built here); any change
to what Maez answers.
