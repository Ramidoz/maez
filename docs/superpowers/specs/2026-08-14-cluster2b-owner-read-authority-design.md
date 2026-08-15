# Cluster 2b — owner-read authority. Design pass 1.

2026-08-14. Written after reading code, before writing any assertion
about it. Every structural claim below carries a file:line I opened in
this session. Where the cluster 2b handoff or design v3.2 §7b asserted
something the tree does not support, the correction is stated in §0
rather than quietly repaired — the four dead gate rounds were all
unverified assertions, and an unverified *correction* would be the
fifth.

Companion documents: design v3.2
(`docs/superpowers/specs/2026-08-14-bonded-consultation-organ-design-v3.md`),
handoff (`docs/superpowers/plans/2026-08-14-cluster2b-handoff.md`),
canon (`docs/slices/s7.3-guarded-self-modification-execution/spec.md`).

---

## §0 Three corrections to the inherited ground truth

**C1 — "there is no seal for new fields to sit inside" is FALSE.**
The handoff correctly found that `S7AuthorizationArtifactBinding` is
not a class in `core/governance/` (re-verified: repo-wide grep returns
only canon and review documents, never Python). It then inferred that
no sealed durable binding exists at that seat. It does. Two, both live:

* `s7_consultation_exemption_evidence_v1` — a per-artifact side table
  (DDL `s7_guarded_execution.py:73-91`) carrying
  `artifact_binding_sha256 TEXT NOT NULL UNIQUE` (`:88`), computed at
  insert as `canonical_hash(_r11_artifact_projection(artifact, ...))`
  (`:275-279`; projection at `:212-240`), guarded by a DDL-contract
  fingerprint compared before every insert and every use
  (`_r11_exemption_evidence_contract` `:94-119`,
  `_expected_r11_exemption_evidence_contract` `:121-127`), and
  **re-derived and compared column-by-column inside the consuming
  transaction on a descriptor-verified held connection**
  (`revalidate_r11_exemption_for_consumption`, `:307-455`).
* `s7_voice_bundle_uses` (`:2796-2807`) whose `bundle_use_hash` is
  recomputed in `S7VoiceBundleUse.__post_init__` and raises on drift
  (`:2760-2766`, domain at `:524-536`) — so a tampered row cannot be
  loaded into an object at all.

Construction 2 is therefore not an invention. It is the R11 evidence
shape applied to a second ruling, at the same seat, in the same
transaction.

**C2 — "A copied column is not a binding; a fingerprint member is" is
FALSE against this tree.** Design v3.2 §7b(1) rests the owner-read
binding on membership in the challenge fingerprint preimage. The
fingerprint (`challenge_hash`) is **write-only**: it is computed at
challenge creation (`s7_webauthn_bootstrap.py:942`, `:1034` — the
authorize variant folds `consultation_exemption_projection_hash` into
`d12_parts` at `:1022-1033`), stored (`:963-972`, `:1056-1069`), and
SELECTed back (`:1127`, `:1163`, `:1197`) — and **never recomputed or
compared anywhere**. Repo-wide grep for `challenge_hash` outside the
dormant v1 stack in `operator_user_boundary.py` returns only those
sites plus one test asserting two challenges differ
(`tests/test_s7_1_ceremony_service.py:1936`).

What actually enforces R11's binding at finish is the ordinary column
comparison: `challenge["consultation_exemption_projection_hash"] !=
presented_exemption_projection_hash` → refuse
(`s7_webauthn_ceremony.py:582-592`), preceded by the nine-column D12
comparison in `_challenge_matches_rendered_d12` (`:558-563`, defined
`:1478-1499`). Both run **before** the verifier is called (`:814`) —
that part of §7b(1) is true and is the load-bearing part.

So the correct sentence is inverted: *in this codebase the column
comparison IS the binding, and fingerprint membership is a
write-only defence that becomes load-bearing only if a recompute is
added.* §10 names that recompute as separately-witnessed hardening H1;
2b does not depend on it.

**C3 — the response bytes are already transitively bound to the tap,
and that changes what 2b must build.** `RenderedRequestStatement`
self-validates `rendered_text_hash == rendered_text_hash(rendered_text)`
in `__post_init__` (`operator_user_boundary.py:4861-4862`, function at
`:4920-4921`), and `rendered_text_hash` is one of the nine D12 columns
compared at finish (`s7_webauthn_ceremony.py:1487`). So any bytes
inside the rendered text are already committed to by the challenge row
the authenticator signs against. The new `maez_response_sha256` carrier
does not create that binding — it makes it **machine-checkable without
parsing prose**, and joins it to the staging plane. Claiming otherwise
would be the same overstatement that killed rounds 3 and 4.

---

## §1 Verified ground truth

Each line was read in this session at the cited location.

**V1. The verifier returns a plain dict with no challenge id.**
`S7ProductionWebAuthnVerifier.verify_authentication_response`
(`s7_webauthn_verifier.py:106-151`) returns on success
`{ok, credential_ref, sign_count, user_presence, user_verification,
library_name, library_version}` (`:143-151`). Confirms the handoff.

**V2. But the verifier IS handed the challenge row, and the library
binds the signature to that row's nonce.** The method takes
`challenge: dict[str, Any]` and passes
`expected_challenge=_b64url_decode(str(challenge["challenge_b64"]))`
into the library (`:126-134`). A successful return therefore already
means *the authenticator signed the nonce that was in the dict it was
given* — a cryptographic fact the current return value simply throws
away. This is new relative to the handoff and it is what makes
construction 1 cheap and honest rather than ceremonial.

**V3. `authorize_finish`'s exact order** (`s7_webauthn_ceremony.py:514-900`):

1. verifier dependency check (`:533-535`)
2. `challenge_id`, `credential_ref`, `authentication_response` parsed
   from caller-supplied request JSON (`:536-545`) — confirms the handoff
3. challenge row fetched by `(challenge_id, session_binding,
   internal_channel_binding, consumed_at IS NULL, invalidated_at IS
   NULL, expires_at > now)` (`:546-556`; SQL at
   `s7_webauthn_bootstrap.py:1115-1147`)
4. `_challenge_matches_rendered_d12` — nine columns (`:558-563`)
5. R11 projection hash re-derived and compared (`:565-592`)
6. voice-seat branch: source-bundle revalidated at finish, store type
   closed-set checked (`:595-780`)
7. `authorization_voice_seat_recheck`, aggregation recheck (`:780-796`)
8. **verifier called** (`:808-820`)
9. ok / user_presence / user_verification / credential_ref equality
   checks (`:822-846`)
10. sign count advanced (`:854-859`), challenge consumed (`:861-866`)
11. artifact minted via `mint_authorization_artifact` (`:868-900`;
    `s7_guarded_execution.py:3541-3608`)

Consequence worth recording: **challenge-id substitution already fails
closed.** Present row A's id with an assertion signed over row B's
nonce and step 8 fails, because `expected_challenge` comes from row A.
The "cross-ceremony hole" A13 was written to close is narrower than
v3.2 states — *within `authorize_finish`*, `challenge` and `verified`
share one lexical frame and cannot disagree. The hole is real only
when a `verified_assertion` crosses a function boundary into a
validator that fetches its own challenge row — which is exactly the
D16 signature v3.2 proposes. Construction 1 exists to make that
crossing safe, not to fix `authorize_finish`.

**V4. RULING-O's two classes are voice-seat classes**, so they route
through the guarded mint: `VOICE_SEAT_WORK_CLASSES` =
`{self_modification, covenant_touching_change, capability_acquisition,
autonomy_lowering_or_protection_reducing}`
(`operator_user_boundary.py:395-400`).

**V5. RULING-O's two classes are exactly the code's existing
highest-risk set.** `_highest_risk_ceremony_required` returns True for
`{covenant_touching_change, autonomy_lowering_or_protection_reducing}`
and nothing else (`operator_user_boundary.py:2270-2275`). Owner-read
lands beside an identically-shaped covenant gate at the same seat, not
in new territory.

**V6. Those two classes are structurally unauthorizable today.**
`covenant_ceremony_satisfies_request` refuses unless a
`CovenantCeremonyEvidence` instance is presented (`:2278-2301`), and
repo-wide grep finds **no non-test producer** of that class. This
confirms the full-body audit §2. It is 2b's principal witness
dependency (§9).

**V7. The voice-seat mint seat is one anchored transaction.**
`S7GuardedStateStore.put_artifact_with_bundle_reservation`
(`s7_guarded_execution.py:3501-3538`) reserves the bundle use and puts
the artifact inside `self.authorization_store.anchored_transaction()`,
with a one-database check (`:3519-3520`). The R11 sibling
`put_artifact_under_consultation_exemption` is the precedent for
inserting evidence in that same transaction
(`mint_authorization_artifact:3568-3603`).

**V8. The Gate-B seat is `consume_for_execution_on_connection`**
(`operator_user_boundary.py:2966-3110`): descriptor-verified held RW
connection (`:2983`), refuses a connection already in a transaction
(`:2984-2985`), `BEGIN IMMEDIATE` (`:3025`), held-store activation
re-verified inside the transaction (`:3026-3028`), one CAS `UPDATE …
RETURNING` over the v2 artifact table with a twenty-predicate WHERE
(`:3029-3072`), grant minted (`:3080-3094`), then
`after_consume_before_commit(grant)` (`:3095-3099`), then commit.
**Canon D21's `consume_artifact_for_execution` wrapper does not exist
in code** — repo-wide grep finds the name only in canon. The live
precedent for a ruling-scoped revalidation at this seat is the
cutover's callback (`scripts/cuda_cutover.py:3369-3387`), the only
production caller of `revalidate_r11_exemption_for_consumption`.

**V9. The repo's own answer to "a plain dataclass anyone can construct
proves nothing"** is a module-private token sentinel:
`if _validator_token is not _VALIDATOR_TOKEN: raise
ValueError("s7_validation_result_forged")` with
`_token_verified` set inside the guarded constructor
(`s7_guarded_execution.py:913-927`, sentinel at `:504`), checked at the
mint seam (`:3428-3446`) and at the ceremony
(`s7_webauthn_ceremony.py:718`) —
carrying its own honest caveat in comment form: *"This token is an
ordinary-caller guard, not a same-process security boundary"*
(`:3424-3427`). Construction 1 copies this idiom **and its caveat**.

**V10. Canon's `S7AuthorizationArtifactBinding` has no row hash.**
Canon defines it with ten fields, none a digest of itself
(canon L1664-1675); its store API is `…BindingStore.get(artifact_id,
*, conn)` (canon L1898); and canon L1867-1872 states S7.3 persists
`challenge_expires_at` on it and "binds it into artifact-binding
replay". So v3.2's phrase "its existing canonical row-hash domain" was
wrong twice over: the class is unbuilt, and the specified class has no
such domain.

---

## §2 The property, restated as a chain of custody

For `covenant_touching_change` and
`autonomy_lowering_or_protection_reducing`, no authority is minted or
consumed unless a founder-key assertion covered the exact bytes of
Maez's answer that the owner read.

Decomposed into links that code can hold, each with the strongest
honest statement available:

| # | Link | Held by | Strength |
|---|---|---|---|
| L1 | The staged bytes are the bytes Maez produced | `AttestedConsultationResult.assistant_text_sha256` over `normalized_assistant_text` (cluster 3) | in-process attestation, RULING 1 boundary |
| L2 | The displayed bytes ARE the staged bytes | delimited display region inside `rendered_text`, hash recomputed in `__post_init__` | true-by-construction: the object cannot exist otherwise |
| L3 | The rendered bytes are what the challenge commits to | `rendered_text_hash` is a D12 challenge column compared at finish (V3 step 4, C3) | already live and cutover-proven |
| L4 | The authenticator signed *that* challenge | library verifies against `challenge["challenge_b64"]` (V2) | cryptographic |
| L5 | The gate can check L2-L4 without parsing prose | `maez_response_sha256` as a challenge column + a carrier field | new, this cluster |
| L6 | Consumption re-proves L1-L5 without a verifier present | sealed owner-read evidence row, re-derived inside the consuming transaction | R11 shape, live-proven |

The honest ceiling: L1 and L5's daemon-side joins are inside RULING 1's
trusted boundary. Nothing here claims cryptographic proof against
compromised daemon code, and no sentence in the build may say
otherwise. What it does claim — and can hold — is that **no path
mints or consumes RULING-O authority without a founder tap in a
ceremony whose row commits to those exact response bytes**, and that
any post-mint edit of the durable carriers fails an integrity check
before any join runs.

---

## §3 Construction 1 — `S7VerifiedAssertion`

**Seat:** `core/governance/s7_webauthn_verifier.py` (the only module
that may mint it).

```text
@dataclass(frozen=True)
S7VerifiedAssertion(
    ok: bool                      -- always True; a failed verification
                                  -- yields no carrier at all
    challenge_id: str             -- id of the row the verifier was handed
    challenge_b64_sha256: str     -- sha256 of the nonce actually verified
                                  -- against, i.e. of challenge["challenge_b64"]
    credential_ref: str
    sign_count: int
    user_presence: bool
    user_verification: bool
    library_name: str
    library_version: str | None
)
```

**Constructor discipline.** Module-private `_ASSERTION_TOKEN` sentinel;
`__init__` raises `s7_verified_assertion_forged` unless the caller
passes it; only `S7ProductionWebAuthnVerifier`'s success path holds it.
Identical idiom and identical honesty caveat as V9 — the token is an
ordinary-caller guard, not a same-process security boundary.

**Why `challenge_b64_sha256` is the load-bearing field, not the token.**
The token answers *who constructed this*. The nonce hash answers a
question the store can check: A13 re-fetches the challenge row **by
`assertion.challenge_id` and by no other key**, then requires
`sha256(row["challenge_b64"]) == assertion.challenge_b64_sha256`. A
forged carrier now needs a nonce digest matching a live, unconsumed,
unexpired row — and if it had that row it would still need the
authenticator's signature, which the library checked (V2). This
converts "trust the carrier" into "check the carrier against the
store", which is the difference between the two failed rounds and this
one.

**Compatibility — no second door.** The existing dict-returning
`verify_authentication_response` has exactly one production caller
(`s7_webauthn_ceremony.py:808`) and ten definitions across six test
modules (`test_s7_1_ceremony_service.py` ×3,
`test_s7_1_daemon_internal_channel.py` ×2,
`test_s7_1_verifier_adapter.py` ×2 — those two stub the library, not
the verifier — plus `test_s7_1_dream_execution.py`,
`test_s7_dialog_soulwrite_liveproof.py`, `test_decision_pipeline_s7.py`
×1 each). Changing its return type would break the cutover-proven path
and every double, so:

* add `verify_authorization_assertion(...) -> S7VerifiedAssertion | dict`
  on the production verifier, performing the verification **once** and
  returning the carrier on success / the existing error dict on failure;
* re-express `verify_authentication_response` as a thin projection of
  that single implementation (`assertion.as_legacy_dict()`), so there
  is one verification path and one set of facts, with the legacy shape
  derived rather than duplicated;
* the ceremony calls the assertion method **only** on the RULING-O
  branch, keeping the non-RULING-O path byte-identical to what the
  cutover proved.

**Fail-closed against test doubles.** For RULING-O classes the ceremony
requires `type(self.verifier) is S7ProductionWebAuthnVerifier` — the
closed-set exact-type idiom already used for stores at
`s7_webauthn_ceremony.py:670-676`. A duck-typed double therefore cannot
authorize a covenant-grade change. Consequence, stated rather than
discovered later: RULING-O tests need either the real library or a
labelled dataflow-only path that cannot reach mint; an environment
without the library returns the existing 503 (`:533-535`), which is
correct fail-closed behaviour.

---

## §4 Construction 2 — the sealed durable binding

**Not** a new `S7AuthorizationArtifactBinding` class. Canon's binding
is unbuilt and hashless (V10); building it now would mean authoring an
entire unbuilt canon object to hold two fields. Instead 2b applies the
shape that is live, sealed, and cutover-proven (C1): a ruling-scoped
per-artifact evidence table.

**Table:** `s7_consult_owner_read_evidence_v1`, in the same database as
the authorization artifacts (the one-database check at
`s7_guarded_execution.py:3519-3520` already enforces this).

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
    credential_ref TEXT NOT NULL,
    user_presence INTEGER NOT NULL CHECK (user_presence = 1),
    user_verification INTEGER NOT NULL CHECK (user_verification = 1),
    owner_read_binding_sha256 TEXT NOT NULL UNIQUE,
    recorded_at TEXT NOT NULL
) STRICT;
```

The CHECK constants are not decoration: they are the R11 table's own
device (`s7_guarded_execution.py:73-91`) for making a row that means
something else structurally unwritable. `user_presence`/
`user_verification` are pinned to 1 by CHECK because RULING-O admits no
other value — an unverified tap cannot even be recorded as owner-read.

**Seal.** `owner_read_binding_sha256 = canonical_hash(projection)`
where the projection mirrors `_r11_artifact_projection`
(`s7_guarded_execution.py:212-240`): the artifact's own identity fields
plus every column above except the seal itself. Same rule as cluster
1's row seal — a hash cannot cover itself — and the domain is defined
in exactly one place, this paragraph.

**Contract fingerprint.** A `_owner_read_evidence_contract(connection)`
built from `sqlite_master.sql` + `PRAGMA table_info` + `PRAGMA
index_list`, compared against `_expected_owner_read_evidence_contract()`
before every insert and before every use — the R11 device at `:94-127`.
A rebuilt or altered table refuses rather than silently accepting rows.

**Write seat.** Inside `put_artifact_with_bundle_reservation`'s
`anchored_transaction()` (V7), for RULING-O classes only, atomic with
the reservation and the artifact. Mint **refuses** for a RULING-O class
when the owner-read inputs are absent or fail their joins — the
fail-closed half of the property, and the mirror of R11's
`exemption_admits_for_artifact` refusal at `:3588-3597`.

**Mutual exclusion.** An artifact carrying an R11 exemption must not
carry owner-read evidence and vice versa, checked both directions at
insert — copying R11's own collision check against
`s7_voice_bundle_uses` (`:255-266` at insert, `:441-449` at
consumption). Two evidence shapes
that both claim to authorize one artifact is the state the R11 comments
were written to forbid.

**Read seat.** `revalidate_owner_read_for_consumption(*, connection,
grant, ...)` structurally identical to
`revalidate_r11_exemption_for_consumption` (`:307-455`): requires a
descriptor-verified held connection, requires `connection.in_transaction
is True`, requires the freshly minted `S7ExecutionGrant` by exact type,
re-checks the table contract, requires exactly one row, re-derives the
seal, and compares **every column** — then compares the artifact row's
own fields against the grant's, refusing
`owner_read_evidence_not_bound_to_grant` on any drift.

---

## §5 Construction 3 — the challenge member and the display region

**§5a — the challenge column.** `s7_ceremony_challenges` gains
`maez_response_sha256 TEXT` (nullable; non-null exactly for RULING-O
classes), written in `create_authorization_challenge`
(`s7_webauthn_bootstrap.py:991-1093`) from the rendered statement's own
field, exactly where `consultation_exemption_projection_hash` is
written today.

Enforcement is the mechanism that actually works in this tree (C2):
the column joins the nine-column D12 comparison in
`_challenge_matches_rendered_d12` (`s7_webauthn_ceremony.py:1478-1499`),
so at finish it is compared against the presented rendered statement
**before** the verifier runs. It is *additionally* folded into
`d12_parts` (`s7_webauthn_bootstrap.py:1023-1046`) so that the
fingerprint stays complete — declared as defence-in-depth that becomes
load-bearing only under hardening H1 (§10), and labelled that way in
the code comment so no future reader mistakes it for enforcement.

**§5b — the display region, byte-exact.** Carried by
`RenderedRequestStatement` as `maez_response_display_text: str | None`
and `maez_response_sha256: str | None`, non-null exactly for RULING-O
classes. The rendered text carries:

```text
Maez response (verbatim):
<response bytes verbatim>
End Maez response.
Maez response hash: <hex>
```

The hashed region begins at the first byte **after** the LF that
terminates `Maez response (verbatim):` and ends at the last byte
**before** the LF that precedes `End Maez response.` — neither
delimiter line, neither bounding LF, no trailing newline.

**Enforced in `__post_init__`, not by a gate.** The existing metadata
discipline (`operator_user_boundary.py:4828-4861`) requires each
metadata line to match its field with `matches != [expected_line]` —
a uniqueness check, not a substring check. The response block joins
that discipline: both delimiter lines must appear **exactly once**;
`maez_response_sha256` must equal the hash recomputed over the region;
`maez_response_display_text` must equal those same bytes. A response
containing either literal delimiter line refuses construction with
`receipt_mismatch` rather than rendering an ambiguous block. The object
therefore cannot exist in a state where the displayed bytes and the
declared hash disagree — L2 of §2 is true-by-construction, which is
strictly stronger than any gate check.

---

## §6 A13 and B2, exactly

**A13 (Gate A, mint-time, RULING-O classes only).** The validator takes
`verified_assertion: S7VerifiedAssertion | None` — the verifier's own
return value, in scope because D16 runs after verification. **No
caller-supplied challenge id appears anywhere in the signature.**
Ordered:

| # | Check | Refusal |
|---|---|---|
| A13.1 | `type(verified_assertion) is S7VerifiedAssertion` and its token was verified | `owner_read_required` |
| A13.2 | `ok is True`, `user_presence is True`, `user_verification is True` | `owner_read_required` |
| A13.3 | challenge row fetched **by `verified_assertion.challenge_id` and by no other key**; row exists, not invalidated, `expires_at > :now_z` | `owner_read_required` |
| A13.4 | `sha256(row.challenge_b64) == verified_assertion.challenge_b64_sha256` | `owner_read_required` |
| A13.5 | `row.rendered_text_hash == rendered.rendered_text_hash` | `stale_binding` |
| A13.6 | `row.maez_response_sha256 == rendered.maez_response_sha256` | `receipt_mismatch` |
| A13.7 | `rendered.maez_response_sha256 ==` hash recomputed over the delimited display region of `rendered.rendered_text` | `receipt_mismatch` |
| A13.8 | that value `== result.assistant_text_sha256` from the A6b staged result row | `receipt_mismatch` |
| A13.9 | `verified_assertion.credential_ref` equals the artifact's credential_ref | `owner_read_required` |

A13.7 is belt over a suspenders that `__post_init__` already fastened
(§5b) — kept because the gate must not depend on the object having been
constructed in this process.

For non-RULING-O classes `verified_assertion` is `None` and A13 is
skipped; a `None` assertion **with** a RULING-O work class refuses
`owner_read_required`.

**B2 (Gate B, consumption-time, RULING-O classes only).** A13 does not
re-run: no verifier is present at execution and no challenge is read.
B2 is `revalidate_owner_read_for_consumption` (§4) invoked in the
`after_consume_before_commit` position of
`consume_for_execution_on_connection` (V8) — inside the transaction,
after the CAS, before commit, raising to roll back. It re-proves,
without a verifier:

* the evidence row exists, its contract matches, its seal re-derives;
* every column matches its re-derived value;
* `consult_attempt_id` equals the attempt the artifact was minted
  against (B1's join), and the attempt's `completed → consumed` CAS
  succeeds in this same transaction;
* `maez_response_sha256` equals the staged
  `result.assistant_text_sha256`;
* `user_presence = 1`, `user_verification = 1`, `credential_ref`
  non-null — read from the sealed row, not re-asserted by the caller.

The attempt CAS, the grant consume, and the owner-read revalidation
commit or roll back together, because they are one transaction by
construction (V8), not by convention.

---

## §7 Refusal vocabulary

No new tokens. `owner_read_required`, `receipt_mismatch`,
`stale_binding`, and `store_integrity_failure` already exist in v3.2's
layer table. Two dispositions to state once:

* a failed table-contract check or seal re-derivation is
  `store_integrity_failure` at layer `gate_a` or `gate_b` — the same
  cause at two layers, which v3.2's layer carrier already handles;
* a missing or malformed `verified_assertion` is `owner_read_required`,
  never `store_integrity_failure` — the distinction is *no owner read
  happened* versus *the record of one is damaged*, and conflating them
  would let a damaged record read as an absent ceremony.

---

## §8 Canon amendments (anchored, per the amendment method)

Anchors derived mechanically from
`docs/slices/s7.3-guarded-self-modification-execution/spec.md` in this
session; each cites line + opening clause.

* **Canon L1664-1675** (`S7AuthorizationArtifactBinding(` … through its
  closing paren) — **KEPT-VERBATIM**. 2b does not amend the unbuilt
  binding class. Rationale recorded so a later reader does not
  "restore" v3.2's amendment: the class does not exist in code (V10),
  and adding fields to an unbuilt object would create a second
  authoritative home for owner-read evidence beside the one 2b builds.
  **This supersedes design v3.2's "D-amendment (artifact binding,
  cluster 2)" at v3 lines 930-935 and §7b item 2 at v3 lines 591-597**,
  both of which amend a class that is not there.
* **Canon L1867-1872** ("S7.3 does not own the WebAuthn challenge
  store…") — **AMENDED**. Replacement bytes append one sentence: "For
  RULING-O work classes S7.3 additionally persists
  `s7_consult_owner_read_evidence_v1`, keyed by `artifact_id`, written
  in the mint transaction and re-derived in the consuming transaction;
  it records the challenge id and nonce digest the founder assertion
  verified against, and S7.3 still does not reload the original
  WebAuthn challenge record outside that recorded evidence."
* **Canon L2970-2986** (`RenderedRequestStatement(` … closing paren) —
  **AMENDED**: two fields added, `maez_response_display_text: str | None`
  and `maez_response_sha256: str | None`, non-null exactly for RULING-O
  classes.
* **Canon L2989-2994** ("The rendered text includes exact lines for…"
  through "`__post_init__` rejects any mismatch.") — **AMENDED**:
  replacement bytes add the delimited response block of §5b to the
  line list, and extend the `__post_init__` rejection rule to the
  exactly-once delimiter requirement and the region-hash equality.
* **Canon L2769** (`validate_s7_voice_source_bundle(`, the D16
  signature) — **AMENDED** by cluster 2a's anchored disposition;
  2b contributes exactly one signature change to that same anchor:
  `verified_assertion: S7VerifiedAssertion | None` replaces v3.2's
  formulation, and `ceremony_challenge_store` is retained solely as
  A13.3's lookup, keyed by the assertion.
* **D21 consumption** — 2b adds no new anchor. B2 attaches at the seat
  cluster 2a already amends; the anchored disposition there gains one
  clause naming `revalidate_owner_read_for_consumption` in the
  `after_consume_before_commit` position.

Anchors for D16's per-bullet dispositions belong to cluster 2a and are
not restated here — restating them is the duplication defect cluster
1's last gate named.

---

## §9 Dependencies, and what 2b cannot witness yet

**D1 — the covenant ceremony producer does not exist (V6).** Both
RULING-O classes already refuse at consume for want of
`CovenantCeremonyEvidence`, which has no non-test producer. Owner-read
can be built, unit-tested, and dataflow-tested, but **a live unmocked
RULING-O witness is impossible until that producer exists.** This is
not a defect introduced by 2b; it is the pre-existing fail-closed state
the full-body audit recorded. It must be stated in the build's own
receipt rather than discovered when the witness is attempted.

**D2 — cluster 3 (attested-result byte constructors) supplies
`assistant_text_sha256`** (A13.8, B2). 2b's design does not depend on
cluster 3's *text*, only on that field's existence, which is already
frozen in v3.2 §6.

**D3 — cluster 2a supplies A1-A12 and the D16/D21 anchored
dispositions.** 2b writes no join outside A13/B1/B2.

---

## §10 Named hardening H1 — make the fingerprint load-bearing (separate)

`challenge_hash` is computed and never checked (C2). Recomputing it at
finish and comparing before verification would convert every D12
column, including the two projection hashes, from
individually-compared to collectively-sealed. This is a small change at
a seam the CUDA cutover depends on, so it is **named, not bundled**:
its own commit, its own live witness, its own gate. 2b's correctness
does not rest on it, and no sentence in 2b's build may claim the
fingerprint enforces anything until H1 lands.

Rows live five minutes (`_add_minutes(now, 5)`,
`s7_webauthn_ceremony.py:474`), so no in-flight legacy rows constrain
the change — the only real risk is the seam itself.

---

## §11 Test and witness plan

* **Construction 1**: token refusal (`s7_verified_assertion_forged`);
  legacy dict projection equals today's dict field-for-field, pinned
  against the current shape; nonce-digest mismatch refuses; RULING-O
  branch refuses a duck-typed verifier by exact type.
* **Construction 2**: contract-fingerprint drift refuses (add a column,
  rebuild without STRICT); post-mint UPDATE of any sealed column fails
  re-derivation before any join runs; mutual exclusion with R11
  evidence refuses both directions; mint refuses a RULING-O class with
  absent owner-read inputs; the CHECK constants reject
  `user_verification = 0`.
* **Construction 3**: a response containing either literal delimiter
  line refuses construction; region hash is byte-exact at both
  boundaries (LF handling proved by fixtures, not by prose); D12
  comparison refuses a mismatched column at finish before verification.
* **Gate B**: revalidation raising inside the callback rolls back the
  CAS — asserted by reading the artifact row after the failure, not by
  trusting the exception.
* **Live witness**: blocked by D1. The build's receipt says so
  explicitly rather than substituting a mocked pass for a witness.

Tests run with `.venv/bin/pytest`. No test in this cluster may reach
`PreparedCutover.begin()`; none needs to, since 2b touches the mint and
consume seats, not the cutover driver.

---

## §12 Out of scope

The owner-display projection surface and the material route (v3.2 §5b);
cluster 2a's joins; cluster 3's byte constructors; hardening H1; the
covenant ceremony producer (named as dependency D1, not built here);
any change to what Maez answers.
