# Cluster 2b — owner-read authority. Design pass 3.

2026-08-14. Pass 1 failed its gate with 13 findings (3 CRITICAL);
pass 2 failed with 9 (0 CRITICAL — the criticals closed). All 22 were
independently re-verified against the tree; all 22 stood. This is the
third whole rewrite, not a patch.

**Method change, forced by pass 2's finding 9.** Pass 2 corrected its
citations from the gate's numbers rather than from a fresh read, and
thirteen were still wrong. Line *ranges* are where this document keeps
failing — they drift, they are hand-drawn, and they are unverifiable at
a glance. Every citation below is therefore a **single anchor line**
carrying a named construct (`def`, `class`, an exact statement),
derived mechanically by string match, never a range. A reader can check
any one of them with a single grep.

Companion documents: design v3.2
(`docs/superpowers/specs/2026-08-14-bonded-consultation-organ-design-v3.md`),
handoff (`docs/superpowers/plans/2026-08-14-cluster2b-handoff.md`),
canon (`docs/slices/s7.3-guarded-self-modification-execution/spec.md`).

---

## §0 Corrections to the inherited ground truth

**C1 — "there is no seal for new fields to sit inside" is FALSE; the
precedent is one table.** `S7AuthorizationArtifactBinding` is not a
class in `core/governance/` (repo-wide grep returns only canon and
review documents). But `s7_consultation_exemption_evidence_v1` is a
live, sealed, per-artifact side table: DDL at
`s7_guarded_execution.py:73` (`_R11_EXEMPTION_EVIDENCE_DDL`), binding
hash computed at insert (`artifact_binding_sha256 = s7.canonical_hash`,
`:275`) over a projection (`def _r11_artifact_projection`, `:212`),
guarded by a DDL-contract fingerprint (`def
_r11_exemption_evidence_contract`, `:94`) compared before insert and
before use, and **re-derived and compared column-by-column inside the
consuming transaction on a descriptor-verified held connection** (`def
revalidate_r11_exemption_for_consumption`, `:307`).

Pass 1 cited `s7_voice_bundle_uses` as a second sealed precedent; that
was overstated. `def _voice_bundle_use_hash` (`:524`) covers four
immutable provenance fields and not the per-artifact reservation state.
The R11 precedent stands alone.

**C2 — "A copied column is not a binding; a fingerprint member is" is
FALSE, and pass 1's replacement claim was also wrong.** The narrow
census is right and the gate confirmed it: no code path recomputes or
compares `challenge_hash` for `s7_ceremony_challenges` at finish. But
pass 1 then concluded "the column comparison IS the binding." **A
column comparison is only as strong as the row it reads.** The
authenticator signs `challenge_b64` alone
(`expected_challenge=_b64url_decode`,
`s7_webauthn_verifier.py:128`), which is independent random bytes
(`challenge_b64 = base64.urlsafe`, `s7_webauthn_bootstrap.py:1019`),
while the D12 fields are ordinary mutable columns beside them (`CREATE
TABLE IF NOT EXISTS s7_ceremony_challenges`, `:102`). The code says so
in its own docstring: *"The browser signs `challenge_b64`. The server's
durable challenge row binds those random bytes to D12's
rendered-statement fields"* (`s7_webauthn_ceremony.py:1511`). The row
is the binding, and nothing signs the row. §4 replaces that condition
for content; §4b states exactly what it does **not** replace.

**C3 — the response bytes are bound to the tap only through an
untampered row.** `class RenderedRequestStatement`
(`operator_user_boundary.py:4791`) self-validates its `rendered_text_hash`
(`def rendered_text_hash`, `:4920`), and that hash is one of the nine
D12 columns compared at finish (`def _challenge_matches_rendered_d12`,
`s7_webauthn_ceremony.py:1478`). Pass 1 called this "already committed
to by the challenge row the authenticator signs against" — true of the
row, false of the signature. Under §4 the content commitment moves into
the signed bytes for RULING-O classes.

---

## §1 Verified ground truth

**V1.** `def verify_authentication_response`
(`s7_webauthn_verifier.py:106`) returns a plain dict — `ok`,
`credential_ref`, `sign_count`, `user_presence`, `user_verification`,
`library_name`, `library_version` — and **no challenge id**. Confirms
the handoff.

**V2.** The same method receives the challenge row and passes
`expected_challenge=_b64url_decode(str(challenge["challenge_b64"]))`
(`:128`) to the library. A successful return already means *the
authenticator signed the nonce in the dict it was given* — a fact the
current return value discards.

**V2b.** `class S7ProductionWebAuthnVerifier`
(`s7_webauthn_verifier.py:26`) is a frozen dataclass whose first field
is `import_module: ImportModule` (`:29`), and the repo's own tests
construct the **exact class** with a fake module that returns success
(`tests/test_s7_1_verifier_adapter.py:253`). Exact-type checks exclude
subclasses and duck types, not a fake-library instance of the real
class.

**V3. `authorize_finish`'s order.** The method spans lines 514-936
(`def authorize_finish`, `s7_webauthn_ceremony.py:514`); each step
below is anchored on its own statement:

| Step | Anchor |
|---|---|
| challenge_id parsed from caller JSON | `challenge_id = _require_text` `:539` |
| challenge row fetched | `challenge = store.authorization_challenge_for_finish` `:547` |
| nine-column D12 comparison | `if not _challenge_matches_rendered_d12` `:558` |
| R11 projection hash compared | `presented_exemption_projection_hash = _r11_challenge_projection_hash` `:565` |
| **verifier called** | `verified = verifier_method(` `:814` |
| verified credential taken | `credential_ref = str(verified` `:843` |
| credential authorized | `if not store.credential_can_authorize` `:849` |
| sign count advanced | `sign_count = store.advance_sign_count` `:854` |
| **challenge consumed** | `if not store.consume_challenge` `:861` |
| artifact constructed | `artifact_id = f"s7authz_` `:867` |
| artifact minted | `mint_authorization_artifact(` `:892` |

The row fetch (`def authorization_challenge_for_finish`,
`s7_webauthn_bootstrap.py:1113`) requires
`challenge_kind='authorize_guarded_request'`, matching session and
internal-channel binding hashes, `consumed_at IS NULL`,
`invalidated_at IS NULL`, `expires_at > now`.

Three consequences, all load-bearing:

*Challenge-id substitution already fails closed.* Present row A's id
with an assertion signed over row B's nonce and the verifier fails,
because `expected_challenge` comes from row A. The cross-ceremony hole
A13 closes is real only when an assertion crosses a function boundary
into a validator that fetches its own row — the D16 signature v3.2
proposes.

*A13 has exactly one lawful seat:* after `:849` and before `:861` —
after verification (it needs the assertion), before challenge
consumption (so it can require an unconsumed row), and before `:867`
(so it cannot compare against an artifact that does not exist).

*`authorize_finish` holds no staging dependency.* Its signature takes
no attempt, result, or staging store. Anything the pre-verification
seat checks must be derivable from the challenge row, the rendered
statement, and `precondition_hash` alone. §4 obeys this; pass 2 did
not.

**V4.** `VOICE_SEAT_WORK_CLASSES = frozenset`
(`operator_user_boundary.py:395`) contains both RULING-O classes, so
they route through the guarded mint.

**V5.** `def _highest_risk_ceremony_required` (`:2270`) returns True for
exactly `{covenant_touching_change,
autonomy_lowering_or_protection_reducing}` — the RULING-O set. The
consume implementation already consults it, which is why §7 can make
revalidation mandatory there rather than caller-supplied.

**V6.** `class CovenantCeremonyEvidence` (`:2228`) is an ordinary frozen
dataclass accepted directly from the caller at consume, and repo-wide
grep finds no non-test construction. So the path is not structurally
incapable of accepting a caller-built value; what is missing is an
honest producer. **A truthful unmocked RULING-O witness is blocked**
(§10).

**V7.** `def put_artifact_with_bundle_reservation`
(`s7_guarded_execution.py:3501`) reserves the bundle use and puts the
artifact inside one `anchored_transaction()`; `def
mint_authorization_artifact` (`:3541`) routes RULING-O work into it.
This is where the sealed evidence row is written, atomic with the
artifact.

**V8. The Gate-B seat** is `def consume_for_execution_on_connection`
(`operator_user_boundary.py:2966`): held-connection verification
(`_require_verified_held_connection(connection)`, `:2982`),
`connection.execute("BEGIN IMMEDIATE")` (`:3026`), one CAS `UPDATE …
RETURNING` over the v2 artifact table, `grant = _mint_s7_execution_grant`
(`:3082`), then `callback_result = (` (`:3097`).

**`after_consume_before_commit` is optional** — declared
`after_consume_before_commit: Callable` with default `None` (`:2979`),
run only when supplied (`:3097`), forwarded unchanged by the public
facade (`:3431`), and the live decision-pipeline caller supplies its
own card-transition callback
(`core/decision/decision_pipeline.py:1588`). Canon D21's
`consume_artifact_for_execution` wrapper **does not exist in code**.
The gate independently confirmed that every repository-owned V2
artifact-consumption SQL mutation delegates to this one function —
there is no second SQL updater — which is why §7 can make the check
mandatory here and have that be sufficient for reachability.

**V9. Canon D9 and the code disagree about where the artifact plane
lives, and the divergence predates this campaign.** Canon D9 pins
cross-store atomicity to a single SQLite file,
`memory/s7_3_guarded_self_modification/state.sqlite3` (canon L1532-1538),
and lists `s7_authorization_artifacts_*` and
`s7_authorization_artifact_bindings` among the tables in it (canon
L1546-1547). In code, the artifact plane lives in the S7.1 ceremony
database (`DEFAULT_STORE_ROOT`, `s7_webauthn_bootstrap.py:38`; `self.db_path
= self.root / "ceremony.sqlite3"`, `:256`), and repo-wide grep finds
**no code reference to `s7_3_guarded_self_modification` at all** — the
canon state file is unbuilt. §7 states what follows; §9 records the
amendment canon needs. This document does not unfreeze cluster 1 to
chase it.

**V10.** The repo's own answer to "a plain dataclass anyone can
construct proves nothing" is a module-private sentinel:
`_VALIDATOR_TOKEN = object()` (`s7_guarded_execution.py:504`) with
`raise ValueError("s7_validation_result_forged")` (`:916`), carrying its
own honest caveat in comment form — *an ordinary-caller guard, not a
same-process security boundary*. Construction 1 copies the idiom and
the caveat.

**V11.** Canon defines `S7AuthorizationArtifactBinding` with ten fields,
none a digest of itself (canon L1664-1675). v3.2's "existing canonical
row-hash domain" was wrong twice: the class is unbuilt, and the
specified class has no such domain.

---

## §2 The property, as a chain of custody

For `covenant_touching_change` and
`autonomy_lowering_or_protection_reducing`, no authority is minted or
consumed unless a founder-key assertion covered the exact bytes of
Maez's answer that the owner read.

| # | Link | Held by | Strength |
|---|---|---|---|
| L1 | The staged bytes are the bytes Maez produced | `AttestedConsultationResult.assistant_text_sha256` (cluster 3) | in-process attestation, RULING 1 |
| L2 | The displayed bytes hash to the declared value | `__post_init__` region check, plus gate recomputation | normal construction cannot violate it; gates recompute anyway |
| L3 | The signed nonce commits to the rendered text and response hashes | §4 — `challenge_b64` IS the commitment | **cryptographic, for content** |
| L4 | The authenticator signed that nonce | library verifies against the row's `challenge_b64` (V2) | cryptographic |
| L5 | One tap yields at most one authority | §4b — uniqueness on the sealed row, plus the existing `consumed_at` | structural, database-enforced |
| L6 | The gate reads the verifier's own assertion for that row | §3 — token carrier + nonce digest checked against the store | ordinary-caller guard + store check |
| L7 | Minting records the association durably and immutably | §5 — sealed evidence row in the mint transaction | R11 shape, live-proven |
| L8 | Consumption re-proves it with no verifier present | §7 — mandatory revalidation inside the consume implementation | single SQL updater, no caller opt-out |

The ceiling, unchanged: L1, L6, L7, L8 sit inside RULING 1's trusted
boundary. Nothing claims proof against compromised daemon code. And
nothing here claims the owner's *eyes* moved — what is proven is that
the tap occurred in a ceremony whose signed challenge commits to those
bytes, and that it can be spent once.

---

## §3 Construction 1 — `S7VerifiedAssertion`

**Seat:** `core/governance/s7_webauthn_verifier.py` — the only module
that may mint it.

```text
@dataclass(frozen=True)
S7VerifiedAssertion(
    ok: bool                       -- always True; a failed verification
                                   -- yields no carrier at all
    challenge_id: str              -- id of the row the verifier was handed
    challenge_b64_sha256: str      -- sha256 of the nonce actually verified against
    credential_ref: str
    sign_count: int
    user_presence: bool
    user_verification: bool
    library_name: str
    library_version: str | None
    loader_is_canonical: bool      -- see below; NOT a provenance proof
)
```

Module-private `_ASSERTION_TOKEN` sentinel; `__init__` raises
`s7_verified_assertion_forged` without it. Same idiom, same caveat as
V10.

**`challenge_b64_sha256` is the load-bearing field, not the token.**
The token says *who built this*. The nonce digest says something the
store can check: A13 re-fetches the row **by
`assertion.challenge_id` and no other key**, then requires
`sha256(row.challenge_b64) == assertion.challenge_b64_sha256`. A forged
carrier then needs a digest matching a live, unconsumed, unexpired
authorization row — and holding that row still leaves the signature to
produce.

**`loader_is_canonical` — honestly named, per pass 2 finding 5.** It is
True only when this verifier's `import_module` *is*
`importlib.import_module` and `package_name` *is* `"webauthn"`. That
proves **canonical loader arguments, not library provenance**: a
substituted `sys.modules` entry, an import hook, or a shadow module on
`sys.path` all still resolve through the canonical loader. Pass 2 named
this bit `loader_is_production` and claimed a fake-library instance
"simply cannot mint RULING-O authority"; that was false and the name
carried the falsehood. What the bit actually buys: it excludes the
repo's own in-test construction pattern
(`tests/test_s7_1_verifier_adapter.py:253`, which passes a custom
`import_module`) from minting RULING-O authority. Module-resolution
substitution remains inside RULING 1's trusted boundary, exactly like
every other same-process substitution this system does not claim to
resist. A distribution-metadata check is available as later hardening
and is named in §11, not asserted here.

**Compatibility — no second door.** `verify_authentication_response`
has one production caller (`verified = verifier_method(`,
`s7_webauthn_ceremony.py:814`) and ten definitions across six test
modules. So: add `verify_authorization_assertion(...)` performing the
verification **once** and returning the carrier on success or the
existing error dict on failure; re-express the legacy method as a thin
projection of that one implementation; call the assertion method **only**
on the RULING-O branch. Because the shared implementation moves, every
non-RULING-O path — including the cutover's — needs an explicit
regression witness that its observable challenge and result shapes are
unchanged (§12). Pass 2 called those paths "byte-identical" and
"untouched"; the branch is untouched, the implementation beneath it is
not.

---

## §4 Construction 4 — the response-committing challenge

RULING-O classes only. Every other class keeps today's behaviour.

**Today.** `challenge_b64 = base64.urlsafe_b64encode(secrets.token_bytes(32))`
(`s7_webauthn_bootstrap.py:1019`) — independent random bytes; the D12
fields sit beside them in mutable columns (`:102`).

**Change.** For RULING-O classes the challenge bytes become the
commitment:

```text
salt                = secrets.token_bytes(32)        -- fresh per ceremony
commitment_preimage = canonical_hash({
    "action_params_hash":        rendered.action_params_hash,
    "authority_context_hash":    rendered.authority_context_hash,
    "derived_aggregation_group": rendered.derived_aggregation_group,
    "maez_response_sha256":      rendered.maez_response_sha256,
    "nonce":                     rendered.nonce,
    "precondition_hash":         precondition_hash,
    "rendered_text_hash":        rendered.rendered_text_hash,
    "request_envelope_hash":     rendered.request_envelope_hash,
})
challenge_bytes     = sha256(salt || bytes.fromhex(commitment_preimage))
challenge_b64       = b64url(challenge_bytes).rstrip("=")
```

Every input is available at `def create_authorization_challenge`
(`s7_webauthn_bootstrap.py:991`), which already receives
`rendered_statement` and `precondition_hash`. `challenge_salt_b64`
becomes a new column. Encoding is unchanged in shape: sha256 gives 32
bytes, 43 unpadded base64url characters, the same length today's random
nonce produces — the gate independently confirmed browser and verifier
round-trip it identically.

**The salt is not a secret** and its plaintext storage costs nothing:
the challenge is already public to the browser, and knowing the salt
does not permit retargeting without a sha256 second preimage or a new
signature. It exists so two ceremonies over identical content produce
different, unpredictable nonces.

**Finish-time recomputation — pre-verification, and from the rendered
statement only** (pass 2 finding 2). `authorize_finish` holds no
staging dependency (V3), so the pre-verification check recomputes
`commitment_preimage` from the **presented rendered statement**,
`precondition_hash`, and the row's salt, and requires equality with the
row's `challenge_b64`. Refusal `owner_read_challenge_mismatch`. It sits
at the D12 seat (`if not _challenge_matches_rendered_d12`,
`s7_webauthn_ceremony.py:558`), before the verifier at `:814`. The join
to the *staged* result happens later, once A6b has loaded it, at A13.10.
Pass 2 specified both stages as one and named a store the seat does not
have.

Begin/finish skew is fail-closed in both halves: rendered drift refuses
before verification; staged-result drift refuses at A13.10.

**§4a — what the commitment kills.** Three attacker moves against
*content*:

| Move | Outcome |
|---|---|
| Rewrite the D12 / response columns, keep `challenge_b64` | recomputation ≠ stored nonce → refuse before verification |
| Rewrite `challenge_b64` to match edited columns | the authenticator signed the original nonce → verification fails |
| Rewrite both AND obtain a signature over the new nonce | that is a second founder tap over the new bytes — the property, satisfied |

Rewriting `challenge_hash` alongside is irrelevant, which is why
hardening H1 could not have closed this: `def _fingerprint`
(`s7_webauthn_bootstrap.py:1523`) is an unkeyed sha256, forgeable by
anyone able to write the row it protects.

**§4b — what the commitment does NOT kill** (pass 2 finding 1). A
fourth move exists and the commitment does not touch it: after a
genuine tap, reset `consumed_at` to NULL while the row is still
unexpired and replay the captured authentication response. The
commitment still recomputes, the signature still verifies over the same
bytes, and constant-zero authenticators are accepted so sign-count is
not a universal barrier. **Anti-replay rests on `consumed_at`, which is
unsigned mutable state — for every class, today, and 2b neither worsens
nor repairs that in general.** Any sentence claiming the salt provides
anti-replay is false and pass 2 contained one.

What 2b *can* do, and does, is make the replay yield no second
authority for RULING-O classes. The sealed evidence row (§5) carries
`UNIQUE (challenge_id)` and `UNIQUE (consult_attempt_id)`. A replayed
challenge therefore collides at insert inside the mint transaction and
the mint rolls back: one challenge authorizes at most one RULING-O
artifact, one attempt authorizes at most one RULING-O artifact,
enforced by the database rather than by a lifecycle column an attacker
is already assumed to be writing. The honest statement of L5 is that
uniqueness, not the salt.

---

## §5 Construction 2 — the sealed durable binding

Not a new `S7AuthorizationArtifactBinding`: canon's binding is unbuilt
and hashless (V11). 2b applies the shape that is live and cutover-proven
(C1).

**Table:** `s7_consult_owner_read_evidence_v1`, in the database where
the artifact plane actually lives (V9) — the same database the guarded
store already requires for artifacts and bundle uses.

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
    owner_read_binding_sha256 TEXT NOT NULL UNIQUE,
    UNIQUE (challenge_id),
    UNIQUE (consult_attempt_id)
) STRICT;
```

The CHECK constants are the R11 table's device (`:73`) for making a row
that means something else structurally unwritable; `user_presence` and
`user_verification` are pinned to 1 because RULING O admits no other
value. The two UNIQUE constraints are §4b's one-tap-one-authority
guarantee.

**Seal domain, defined here and nowhere else.**
`owner_read_binding_sha256 = canonical_hash(projection)` where the
projection is the artifact's identity fields — mirroring `def
_r11_artifact_projection` (`:212`) — plus **every column declared above
the seal in the DDL, in declaration order**, ending with `recorded_at`.
The seal is declared last precisely so "every column above it" is
total; pass 1 put `recorded_at` after the seal and left it uncovered.
Following R11's own rule, `recorded_at` MUST equal
`artifact.created_at` and revalidation requires that equality. A hash
cannot cover itself, so the seal is the single exclusion.

**Contract fingerprint.** `_owner_read_evidence_contract(connection)`
from `sqlite_master.sql` + `PRAGMA table_info` + `PRAGMA index_list`,
compared before every insert and every use — the R11 device (`def
_r11_exemption_evidence_contract`, `:94`). A rebuilt or altered table
refuses.

**Write seat.** Inside `def put_artifact_with_bundle_reservation`'s
anchored transaction (`:3501`), for RULING-O classes only, atomic with
the reservation and the artifact. Mint **refuses** for a RULING-O class
when the owner-read inputs are absent or fail their joins.

**Mutual exclusion, four ways.** R11 exemption evidence and owner-read
evidence must never coexist for one artifact: checked at the owner-read
insert, at the R11 insert, and inside **both** revalidators at
consumption — R11 already checks its collision at both seats, and pass 1
specified only the insert.

**Read seat.** `revalidate_owner_read_for_consumption(*, connection,
grant, staging_reader, ...)`, structurally identical to `def
revalidate_r11_exemption_for_consumption` (`:307`): descriptor-verified
held connection, `connection.in_transaction is True`, exact-typed
freshly minted grant, contract re-check, exactly one row, seal
re-derived, every column compared, `recorded_at == artifact.created_at`,
no R11 row present, and the grant-binding equalities. Any drift refuses
`owner_read_evidence_not_bound_to_grant`.

---

## §6 Construction 3 — challenge columns, display region, and A13

**§6a — challenge columns.** `s7_ceremony_challenges` gains
`maez_response_sha256 TEXT` and `challenge_salt_b64 TEXT`, both
nullable, both non-null exactly for RULING-O classes, written at `def
create_authorization_challenge` (`s7_webauthn_bootstrap.py:991`) where
`consultation_exemption_projection_hash` is written today.
`maez_response_sha256` joins the D12 comparison (`:1478` in the
ceremony) and is a member of the §4 commitment, so the signature covers
it. It also joins `d12_parts` (`s7_webauthn_bootstrap.py:1022`) for
completeness — declared **in the code comment** as write-only defence,
not enforcement, until H1 (§11).

**§6b — the display region, byte-exact.** `RenderedRequestStatement`
(`operator_user_boundary.py:4791`) carries
`maez_response_display_text: str | None` and `maez_response_sha256: str
| None`, non-null exactly for RULING-O classes. The rendered text
carries:

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

Enforced in `__post_init__` beside the existing metadata discipline
(`expected_metadata = (`, `:4828`), which matches each line with
`matches != [expected_line]` — a uniqueness check, not a substring
check. Both delimiter lines must appear exactly once; the declared hash
must equal the region hash; the display text must equal those bytes. A
response containing either literal delimiter line refuses construction
with `receipt_mismatch`.

**Honest scope.** `RenderedRequestStatement` is an ordinary frozen
dataclass. `__post_init__` makes it impossible to *construct* an
inconsistent object normally; it does not prevent `object.__setattr__`,
crafted deserialization, or other same-process mutation. Pass 1's "the
object cannot exist in that state" overstated it, and the parent v3.2
still carries that overstatement (§9 corrects it). Every authority gate
recomputes the region and its hash regardless — which is why A13.9 and
B2 are not redundant.

**§6c — A13.** Seat: after `if not store.credential_can_authorize`
(`:849`) and before `if not store.consume_challenge` (`:861`).
`verified_assertion: S7VerifiedAssertion | None`; **no caller-supplied
challenge id appears in the signature.**

| # | Check | Refusal |
|---|---|---|
| A13.1 | `type(verified_assertion) is S7VerifiedAssertion`, token verified | `owner_read_required` |
| A13.2 | `ok`, `user_presence`, `user_verification` all True | `owner_read_required` |
| A13.3 | `loader_is_canonical is True` and `type(verifier) is S7ProductionWebAuthnVerifier` (§3's honest scope applies) | `owner_read_verifier_not_canonical` |
| A13.4 | challenge row fetched **by `verified_assertion.challenge_id` and no other key**, with the complete state the finish fetch already requires (`challenge_kind='authorize_guarded_request'`, `consumed_at IS NULL`, `invalidated_at IS NULL`, `expires_at > :now_z`, matching session and internal-channel binding hashes) | `owner_read_required` |
| A13.5 | `sha256(row.challenge_b64) == verified_assertion.challenge_b64_sha256` | `owner_read_required` |
| A13.6 | `row.challenge_b64` equals the §4 recomputation from the presented rendered statement, `precondition_hash` and `row.challenge_salt_b64` | `owner_read_challenge_mismatch` |
| A13.7 | `row.rendered_text_hash == rendered.rendered_text_hash` | `stale_binding` |
| A13.8 | `row.maez_response_sha256 == rendered.maez_response_sha256` | `receipt_mismatch` |
| A13.9 | `rendered.maez_response_sha256 ==` hash recomputed over the delimited display region of `rendered.rendered_text` | `receipt_mismatch` |
| A13.10 | that value `== result.assistant_text_sha256` from the A6b staged result row — the staged join, at the first seat that has the staging store | `receipt_mismatch` |
| A13.11 | `verified_assertion.credential_ref` equals the credential the ceremony verified at `:843` and authorized at `:849` — the value that becomes the artifact's `credential_ref` at `:867` | `owner_read_required` |

A13.11 replaces pass 1's comparison against a not-yet-existing
artifact. For non-RULING-O classes `verified_assertion` is `None` and
A13 is skipped; `None` **with** a RULING-O class refuses
`owner_read_required`.

---

## §7 Gate B — mandatory, and the two-plane truth

**B2 is not a callback.** `after_consume_before_commit` defaults to
`None` (`:2979`), runs only if supplied (`:3097`), and the live
decision-pipeline caller supplies its own
(`core/decision/decision_pipeline.py:1588`). A check a consumer can
decline is not a gate. Therefore **`def
consume_for_execution_on_connection` (`:2966`) itself runs owner-read
revalidation, unconditionally, when `def
_highest_risk_ceremony_required` (`:2270`) is True** — inside the
`BEGIN IMMEDIATE` transaction (`:3026`), after the CAS, before and
independently of any caller callback (`:3097`), raising to roll back.
Reachability is sufficient because that function is the sole SQL
updater of the v2 artifact table (V8). The caller's callback keeps its
existing meaning and cannot substitute for, suppress, or precede B2.

**The seat must be given a staging reader, or refuse.** Its signature
holds no attempt or result store today, and B2 must read both. The
mandatory path therefore takes a staging reader dependency and refuses
`owner_read_staging_unavailable` when it is absent — an unreadable
consultation is not a consulted one. Pass 2 asserted B2's checks
without giving the seat the ability to perform them.

**Two planes, and why atomicity was never the guard** (pass 2 finding
3, and V9). The consultation staging family is pinned by design v3.2 §2
to canon D9's state file; the artifact plane lives in the ceremony
database; canon D9 believes both live in one file and names a path no
code creates (V9). Pass 1 claimed the attempt CAS and the grant consume
are "one transaction by construction"; they are not, and pass 2's
"burn-first" repair claimed a safety it could not deliver either.

The correct statement is that **one-use is guarded twice, and each
guard is single-database:**

* **Mint side, staging plane:** an attempt authorizes an artifact only
  while `state='completed' AND consumed_by_artifact IS NULL` (cluster
  1's transition table). Once bound, no second artifact can be minted
  from that consultation. Plus §4b's `UNIQUE (consult_attempt_id)` on
  the evidence row, in the artifact plane, which makes the same
  guarantee a second time from the other side.
* **Consume side, artifact plane:** the artifact's own CAS
  (`consumed_at IS NULL`, inside `BEGIN IMMEDIATE` at `:3026`) admits
  exactly one grant.

Neither guard depends on the other plane, so no cross-database
transaction is required for one-use. What a cross-plane failure can
produce is a *spent attempt with no grant* — the artifact remains
unconsumed and a retry consumes it legitimately, since the attempt is
already bound to that same artifact and B2 requires
`attempt.consumed_by_artifact == artifact_id`. The unsafe direction —
a committed grant beside a re-mintable consultation — is closed on the
mint side, not by ordering.

Pass 2's ordering law is therefore **withdrawn** as a safety argument.
It remains as an operational preference only: burn before consume, so
the durable trail reads in causal order.

---

## §8 Refusal vocabulary

Three new causes, all `gate_a` layer except the last, all RULING-O only:

* `owner_read_verifier_not_canonical` — verification did not run through
  the canonical loader (A13.3);
* `owner_read_challenge_mismatch` — the signed nonce does not commit to
  the presented bytes (A13.6, §4);
* `owner_read_staging_unavailable` — layer `gate_b`; the consume seat
  cannot read the staging plane (§7).

Otherwise no new tokens. Two dispositions stated once: a failed
contract check or seal re-derivation is `store_integrity_failure` at
`gate_a` or `gate_b`; a missing or malformed `verified_assertion` is
`owner_read_required`, never `store_integrity_failure` — *no owner read
happened* versus *the record of one is damaged*.

---

## §9 Canon and parent amendments

Canon anchors were verified mechanically and the gate confirmed all of
them match the current file.

* **Canon L1664-1675** (`S7AuthorizationArtifactBinding(`) —
  **KEPT-VERBATIM**. The class is unbuilt (V11); amending it would
  create a second authoritative home for owner-read evidence.
* **Canon L1532-1560 (D9's atomicity mechanism and table list)** —
  **AMENDED, and the amendment is owed regardless of 2b.** Canon places
  `s7_authorization_artifacts_*` and `s7_authorization_artifact_bindings`
  in a state file the code never creates, while the live artifact plane
  is the ceremony database (V9). Replacement bytes must name the actual
  per-plane homes and state the one-use guarantee per plane, since
  cross-plane atomicity is neither implemented nor required (§7). This
  divergence predates the campaign and is recorded here rather than
  silently designed around.
* **Canon L1867-1872** ("S7.3 does not own the WebAuthn challenge
  store…") — **AMENDED**, appending: "For RULING-O work classes S7.3
  additionally persists `s7_consult_owner_read_evidence_v1`, keyed by
  `artifact_id` and unique per challenge and per consult attempt,
  written in the mint transaction and re-derived in the consuming
  transaction; it records the challenge id, the nonce digest, and the
  commitment the founder assertion signed over."
* **Canon L2970-2986** (`RenderedRequestStatement(`) — **AMENDED**:
  `maez_response_display_text: str | None` and `maez_response_sha256:
  str | None`.
* **Canon L2989-2994** ("The rendered text includes exact lines for…") —
  **AMENDED**: §6b's block joins the line list; the `__post_init__`
  rejection rule extends to the exactly-once delimiters and the region
  hash.
* **Canon L2769** (`validate_s7_voice_source_bundle(`) — **AMENDED** by
  cluster 2a; 2b contributes `verified_assertion: S7VerifiedAssertion |
  None`, with `ceremony_challenge_store` retained solely as A13.4's
  lookup.

**Parent v3.2 corrections owed in the same commit as this pass** (pass
2 findings 6 and 8; leaving them standing is the two-texts defect
cluster 1's last gate named):

1. v3.2's D16 hash-routing amendment still adds
   `binding.maez_response_sha256 -> sha256(delimited display region)`.
   The binding does not exist and will not gain the field; the routing
   target is the owner-read evidence row.
2. v3.2's D16 NEW bullet still cites "§7b" for the RULING-O equality;
   §7b is superseded and the pointer must name this document.
3. v3.2 §7b item 3 still says the inconsistent rendered object "cannot
   exist" and calls that stronger than a gate. §6b's honest scope
   replaces it.
4. v3.2 §7b's pointer to "§5b" and the withdrawn D-amendment's pointer
   to "§4" must name this document's current sections.
5. v3.2's D21 disposition still requires the attempt CAS and the
   inherited consume to succeed in the same transaction. §7 shows that
   transaction does not exist and is not needed; those bytes must be
   replaced with the two-plane one-use statement.

---

## §10 Dependencies

**D1 — no honest `CovenantCeremonyEvidence` producer exists (V6).** A
truthful, unmocked RULING-O witness is blocked until one is built. The
path can accept a caller-constructed value; a witness assembled from
one is a mock wearing a witness's clothes, and this build's receipt
must say so rather than count it.

**D2 — cluster 3 supplies `assistant_text_sha256`** (A13.10, B2). 2b
depends on the field's existence, already frozen in v3.2 §6.

**D3 — cluster 2a supplies A1-A12 and the D16/D21 anchored
dispositions.** 2b writes no join outside A13 and B2.

---

## §11 Separated work

Named, not bundled; each needs its own commit, witness and gate.

* **H1 — recompute `challenge_hash` at finish.** Worth doing for the
  classes §4 does not cover; **not** sufficient for RULING-O, because
  `def _fingerprint` (`s7_webauthn_bootstrap.py:1523`) is unkeyed and
  forgeable by whoever can write the row it protects. It must never be
  described as closing the gap §4 closes.
* **Lifecycle anti-replay.** §4b shows `consumed_at` is unsigned
  mutable state for every class. 2b bounds the damage for RULING-O via
  uniqueness; a general repair is a separate question about the
  challenge plane itself.
* **Library provenance.** §3's `loader_is_canonical` proves loader
  arguments, not that the resolved module is the installed
  `webauthn` distribution. A distribution-metadata check is available
  and unclaimed here.
* **Commitment-carrying challenges for non-RULING-O classes.** A scope
  decision with a live-ceremony blast radius; the owner's, and its own
  cluster's.

---

## §12 Test and witness plan

* **Construction 1**: token refusal; legacy dict projection equals
  today's dict field-for-field, pinned; nonce-digest mismatch refuses;
  `loader_is_canonical` False for the exact construction at
  `tests/test_s7_1_verifier_adapter.py:253`, and the RULING-O branch
  refuses it.
* **Construction 4**: edit a D12 column after begin → refuse before
  verification; edit `challenge_b64` → verification fails; edit both →
  refuse for want of a signature; **replay after resetting
  `consumed_at` → the second mint collides on `UNIQUE (challenge_id)`
  and rolls back**; identical content in two ceremonies yields
  different nonces; challenge encoding (32 bytes, 43 unpadded
  characters) unchanged.
* **Construction 2**: contract-fingerprint drift refuses; post-mint
  UPDATE of any sealed column **including `recorded_at`** fails
  re-derivation before any join runs; `recorded_at !=
  artifact.created_at` refuses; R11 mutual exclusion refuses in both
  directions at both insert and consumption; mint refuses a RULING-O
  class with absent owner-read inputs; CHECK rejects
  `user_verification = 0`; `UNIQUE (consult_attempt_id)` refuses a
  second artifact from one attempt.
* **Construction 3**: a response containing either delimiter line
  refuses construction; region hash byte-exact at both boundaries by
  fixture; D12 comparison refuses a mismatched column before
  verification.
* **Gate B**: a consumer supplying its own callback, or none, still
  runs revalidation for a RULING-O class; an absent staging reader
  refuses `owner_read_staging_unavailable`; revalidation raising rolls
  back the CAS, asserted by re-reading the artifact row after the
  failure; the cross-plane crash window leaves a spent attempt and an
  unconsumed artifact, and the retry consumes exactly once.
* **Non-RULING-O regression witness** (§3): the cutover's and every
  other class's challenge bytes and finish result are unchanged after
  the verifier implementation moves — the one live path this cluster
  can genuinely witness today.
* **Live RULING-O witness**: blocked by D1. The receipt says so rather
  than substituting a mocked pass.

Tests run with `.venv/bin/pytest`. No test in this cluster may reach
`PreparedCutover.begin()`; none needs to.

---

## §13 Out of scope

The owner-display projection surface and material route (v3.2 §5b);
cluster 2a's joins; cluster 3's byte constructors; everything in §11;
the covenant ceremony producer (D1); any change to what Maez answers.
