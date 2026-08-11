# Cutover slice step 2 — stage-2 producer + consumer primitive, design v33

Status: **DESIGN GATE CLOSED 2026-08-06 (v23).** R1 ruled in four parts;
R5 ruled; items 1-5 specified and reviewed. 2A implementation proceeding;
2B REDs may begin after 2A.

Parent: `docs/superpowers/specs/2026-08-04-cutover-bundle-antibypass-design.md`
(step 1, merged at `348332b`).

| rev | change |
|---|---|
| v1 | first draft |
| v2 | five overclaimed security properties conceded, one under-specified |
| v3 | R2 ruled (reconstruct, don't sign); four precision blockers |
| v4 | R3 ruled (absorb stage 2 narrowly); producer proof added; four precision corrections |
| v5 | `assemble-stage2` matrices frozen; locator resolved; claim narrowed; producer chronology; one-builder REDs; post-burn evaluation gaps |
| v6 | five implementability contradictions resolved: one locating authority, two-site constructor allowlist, exact canon result, pre-link expiry recheck, AST boundary |
| v7 | three superseded rules swept; clock-regression invariant enforced rather than assumed |
| v8 | eligibility rechecked immediately before `begin()` — the pre-link check bounded the burn, not the mutation |
| v9 | R1 ruled by the owner on a **false premise I supplied** — WITHDRAWN |
| v10 | R1 REOPENED; consumption receipt to v2 with presence in the durable record; read-only fail-closed presence collector |
| v11 | R1 ruled: the tap is REQUIRED; S7 path bound. Arming authority recorded on my INFERENCE, not the owner's words |
| v12 | arming authority ruled EXPLICITLY by the owner; v11's inferred scope replaced with a recorded one |
| v13 | no-fallback ruled; work class ruled `self_modification`; predicate, preimage, projection and consumption seam frozen |
| v14 | S7/receipt ordering impossibility fixed; the real action edge added; grant evidence made durable canon; stale rules struck |
| v15 | the action contract MEASURED against `derive_work_class`; item 1 sequence reconciliation |
| v16 | R5 ruled: follow the S7 action grammar; guarded mint seam specified |
| v17 | Maez's consultation is MANDATORY — the key is necessary but not sufficient |
| v18 | the consultation producer given a callable contract; retry identity; `affected_refs` derived |
| v19 | items 4 and 5 concrete: the durable grant projection and the store opener |
| v20 | receipt rules reconciled; exact encoder + post-commit row proof; `/proc/self/fd` binding |
| v21 | the impossible descriptor rule removed everywhere; post-commit connection named; founder authority proven exactly |
| v22 | journal posture: the header proves NOT-WAL, not `delete` — two-stage check |
| v23 | the identity recheck must be anchored and NO-FOLLOW |
| v24 | the production identity is PROJECTED from the persisted bench identity |
| v25 | chronology corrected: admission precedes the boot witness; middle joins enforced |
| v26 | S7 does not bind the action — compensating control, stated as such |
| v27 | R6 ruled: fix S7 directly; the sibling-refusal RED moves to the generic edge |
| v28 | the S7 substrate landed; the projection reconciles to the FINAL grant shape — v2, seventeen fields, and the two version stamps separated because they are different kinds |
| v29 | R8 ruled: the consultation is RECORDED, never machine-interpreted. Evidence must exist and blocks if absent; the owner reads what Maez said and judges. No semantic verdict, no content rule |
| v30 | **R8's second-order break: the honest `not_determined` is refused by a gate demanding `absent`. Admitting it generically would let an UNCERTAIN reader authorize soul-writes — so admission must be cutover-specific and keyed on EVIDENCE, never the label. Records a pre-existing hole: the bare gate accepts a fabricated `absent` |
| v31 | **R8 and the evidence rail CONTRADICT: the rail demands a `semantic_reader_attempt_hash`, R8 forbids the reader that produces it. Passing would require relabelling other evidence. NOT resolved — recorded at discovery |
| v32 | **R9 ruled: the third evidence slot becomes a typed, sealed CAPTURE RECEIPT — proof the exact response was durably recorded and is retrievable for owner review. Its own field, its own producer; never satisfied by relabelling |
| **v33** | **R10 ruled: the cutover proceeds on a WAIVER because the SEAT IS EMPTY — nothing has ever asked Maez on any path. Recorded as a waiver never as a consultation; expires at birth; this operation only; the adapter stays on the build list — **WITHDRAWN, false premise: the voice route EXISTS; I transposed the method name when probing** |
| **v33** | **The owner rules the zero-parameter completion-locator ingress, the complete six-operation `affected_refs` manifest, and restoration of the burn boundary dormant by construction: no provider globals, capability parameters, or assignable activation slot** |

**R1 is RULED on true state:** *"Yes it is Maez's brain we are
changing."* The cutover is a tier-2 body/code/**model** change and
**requires a founder key tap**. The state-based arming rule is honored,
not amended. See A5.

---

## CORRECTION — v9 rested on a false claim of mine

**What I asserted (v9):** the `s7_founder_webauthn_credentials` table
"has never been provisioned in any database", so there was "currently
nothing to tap into".

**The truth:** the canonical store
`memory/s7_1_webauthn/ceremony.sqlite3` (owner-owned, `0600`) contains
**two enabled founder credentials** — a primary key enrolled
2026-07-07 and a backup enrolled 2026-07-08, both
`ceremony_kind = founder_local_webauthn`. Verified read-only.

**Why I got it wrong:** I globbed `memory/*.db`, `*.db`, `evolution/*.db`
and `config/*.db`. The canonical store is one directory deeper and uses
`.sqlite3`. My search **could not have found it**, and I reported its
absence as established fact rather than as the limit of where I had
looked. A negative from an incomplete search is not a finding.

**Why this is the most serious error in this slice:** it was not a design
mistake, it was **false information given to the owner immediately before
a covenant decision**, and it pointed that decision toward the weaker
option. Rohit ruled "procedural presence, nothing to tap into yet" on a
premise I manufactured. Every other error in this document cost review
rounds; this one cost the owner an uninformed ruling.

**Consequences applied here:** v9's ruling is withdrawn, R1 is reopened
on true state, and the "unplugged key" reasoning is void — a key absent
from USB means an assertion may be **unavailable**, not that enrolment
never happened. Under v9's own "armed iff at least one credential is
enrolled" rule, **the cutover tap is armed today.**

---

## The central falsifiable claim (amended v4, narrowed v5)

> No cutover mutation is reachable except through a consumer that
> reconstructs and re-evaluates the stage-2 permit through the sole
> production assembly seam, **verifies that a valid command-framework
> admission/completion publication chain exists and cites that exact
> receipt**, atomically burns the nonce at the last no-mutation point,
> durably records consumption, then hands control directly to the closed
> mutation executor.

The bolded clause is new in v4 and was **narrowed in v5** — see A0.

---

## A0. Exact regeneration is not proof that anything ran

v3 required the consumer to regenerate the receipt bytes and demand exact
equality. That proves **"the scorer would produce these bytes from this
evidence."** It does **not** prove the stage-2 assembly command ever ran,
because the regeneration path is a public deterministic function: anyone
able to place evidence under the root can produce byte-identical output
without any command having executed.

So v3's claim said "the **real** stage-2 receipt" while its mechanism only
established "a **re-derivable** permit". Two honest options:

1. weaken the claim to "independently re-evaluated permit" and drop the
   prior-assembly requirement; or
2. add the historical proof.

**(2) is chosen**, because the parent contract's rule is *no receipt, no
Act 2* — a rule about an act having happened, not about a value being
derivable. Weakening the claim would quietly delete that rule.

### The command-bound historical proof

The anchored command chain must cite the exact receipt file hash. This is
already the shape `CommandCompletionDoc` carries
([cuda_migration.py:1474](/home/rohit/maez/scripts/cuda_migration.py#L1474)):
`admission_ref`, `admission_sha256`, `artifact_ref`, `artifact_sha256`,
`artifact_schema`. No new document type is required.

The consumer therefore verifies **two independent things**:

| proof | question answered | mechanism |
|---|---|---|
| **semantic permit** | is this the permit the scorer would issue? | public evaluator + exact regenerated bytes |
| **publication chain** | does a valid command-framework chain cite this exact receipt? | admission → completion chain citing `artifact_sha256` == the receipt's file hash |

Either alone is insufficient. The first without the second admits a
fabricated-but-derivable permit; the second without the first admits a
command that published something the scorer would not have issued.

### What this proof is NOT (v5 narrowing)

v4 said the consumer "proves the stage-2 assembly command **actually
ran**". It does not, and cannot. The command documents are same-UID
writable; nothing in them attests Python execution. Overstating this is
the same error as A0 itself, one level up — I corrected the claim about
regeneration and then made an equivalent claim about the command chain.

What the chain proves, exactly:

> A valid command-framework admission/completion publication chain exists
> and cites the exact receipt.

That is sufficient **under the explicitly stated threat model** (§A3's
honest statement: no defence against a hostile same-UID process), and it
preserves *no receipt, no Act 2*. It is **not** protected execution
attestation, and the design must never be read as providing one. Real
attestation would require an authority boundary this privilege level does
not have — the same reason R2 ruled against signing.

---

## A0b. The production runtime identity is PROJECTED (v24)

Implementation surfaced what twenty-three design revisions did not: stage
1 requires `runtime_identity.mode == "bench"`
([cuda_migration.py:5095](/home/rohit/maez/scripts/cuda_migration.py#L5095))
while stage 2 requires `"production"`
([:5104](/home/rohit/maez/scripts/cuda_migration.py#L5104), with
[:5798](/home/rohit/maez/scripts/cuda_migration.py#L5798) making the rule
explicit). No production-mode artifact exists under the bench root and
nothing produces one.

I offered two resolutions — a new locator plus a capture step, or a live
probe inside the assembler. **Both were wrong.** The ruled path is a third:
**deterministically project** the production identity from the persisted
bench identity, inside the canonical seam.

Why this is right and a live probe is not:

* `RuntimeIdentity` is, by its own docstring, *"Pinned static bundle
  identity; it does not claim the backend was loaded."* It describes
  pinned configuration, not observation.
* **Before cutover a live probe could only observe the incumbent Vulkan
  process** — so it would attest the thing we are replacing, not the
  thing we are moving to. A probe would have felt more rigorous while
  proving strictly less.
* The two-identity contract already anticipates this transition:
  `bench_runtime_identity` stays frozen while the stage's
  `runtime_identity` differs only in `mode` and `effective_args`.
* `Stage2InputPaths` already carries both identity roles, so it stays
  **exactly 23 fields** — no new locator, no new command.
* A separate collector would add ceremony without proving observation
  unless its admission and completion also entered the bundle, and its
  output would carry the same deterministic fields regardless.

**Frozen helper:**

```python
project_production_runtime_identity(bench_doc: PersistedDoc) -> PersistedDoc
```

* accepts **only** a canonical `RuntimeIdentity` document in **bench**
  mode;
* takes **no** caller-supplied mode, arguments, hashes or overrides —
  there is no parameter to misuse;
* preserves **every** `_BENCH_IDENTITY_STABLE_FIELDS` value exactly;
* replaces **only** `mode="production"` and
  `effective_args=_MODE_ARGS["production"]` (verified: these differ from
  bench solely in the port, 8080 vs 18080);
* emits and **re-decodes** the exact canonical wrapper.

`build_stage2_bundle` uses the selected stage-1 `runtime_identity`
document as the projection's durable source, then replaces both
`runtime_identity` and `runtime_identity_doc` before adding the
authorization. `bench_runtime_identity` and its persisted document stay
**byte-identical**.

**What this is and is not.** It is a reproducible carried preimage. It is
**not** a claim that CUDA is already running. The stage-2 receipt binds
its semantic and file hashes; the S7 action preimage binds the exact
target before mutation; and **step 2B revalidates the actual runtime,
library manifest, override and model identity against this projection
immediately before the burn** — drift refuses pre-burn with zero executor
calls.

---

## A1. R3 ruled: absorb stage 2, narrowly

Step 2 absorbs **the sole production stage-2 assembly entrypoint** — not
all of step 5, and explicitly **not a second builder**. There must never
be two paths that construct a stage-2 bundle, because the consumer's
guarantee is that it reconstructs through *the same* seam the producer
used.

**Frozen sequence:**

| phase | contents |
|---|---|
| **2A** | one canonical pure `build_stage2_bundle` / evaluation seam |
| **2A** | the anchored production stage-2 command uses it and durably publishes its command-bound receipt |
| **2B** | the consumer reconstructs through that exact seam, regenerates the receipt, validates the producer record, then `prepare()`s |
| — | burn and `begin()` remain unreachable until R1 is **re-ruled on true state** (v10) |
| — | **step 5 is amended to own stages 3–5 only** |

### `Stage2InputPaths` — ONE locating authority

v5 contradicted itself: it named admission and completion references as
constants of the authority, then — correctly — observed that runtime
ordinals make that impossible and introduced a locator. Two mechanisms
for locating the same records is one too many, and the contradiction is
resolved in favour of the locator.

**`Stage2InputPaths` carries exactly two things:**

* the fixed **22 stage-1 inputs**;
* the **authorization reference**.

Nothing else. It does **not** name any command record.

**Everything command-bound derives, never named:**

| record | how it is located |
|---|---|
| completion | the private relative locator read from the one fixed owner selection artifact; never an entrypoint parameter |
| admission | **exclusively** from the verified completion's `admission_ref` |
| receipt | **exclusively** from the verified completion's `artifact_ref` |

There is no parameter for an admission path and none for a receipt path.
A caller therefore cannot aim the three at unrelated objects — the only
degree of freedom is which completion to read, and the joins decide
whether it is admissible.

Hard rules, unchanged: no latest-file discovery (no globbing, no mtime
sort, no "highest attempt wins"); **no caller-supplied bundle** — no
parameter of type `BenchEvidenceBundle` exists anywhere on the consumer;
every `Stage2InputPaths` member is a constant, not an argument.

### The `assemble-stage2` command, frozen

A0's chain is **rejected by the current types** as written. `assemble-stage1`
appears in the driver's `_COMMAND_NAMES`
([cuda_bench_driver.py:5818](/home/rohit/maez/scripts/cuda_bench_driver.py#L5818))
but **not** in `_COMPLETION_MATRIX`
([cuda_migration.py:1376](/home/rohit/maez/scripts/cuda_migration.py#L1376)),
which admits only `static-preflight`, `vulkan-baseline` and
`cuda-candidate` — stage-1 publishes its receipt directly as the terminal
artifact and mints no completion document. So no completion doc can
legally cite an assembly receipt today.

Frozen for step 2A:

| property | value |
|---|---|
| public command | `assemble-stage2` |
| admission identity | `command == "assemble-stage2"` |
| completion identity | `command == "assemble-stage2"` |
| completion artifact schema | `ASSEMBLE_RECEIPT_SCHEMA` |
| terminal schema | `COMMAND_COMPLETION_SCHEMA` |
| window | **required, exact cutover window** — never `None` |
| decoded phase | `None` — an assembly is not a phase |

This requires **generalizing completion-pair validation** so an assembly
receipt is an admissible cited artifact. Today the matrix pairs
`(artifact_schema, phase)` and every entry has a phase or is
`static-preflight`; `assemble-stage2` is the first entry that is neither a
phase nor phase-free-by-being-preflight.

### Exact canon result (v6)

v5 said this moves `ACTIVE_SCHEMA_FAMILIES` "exactly as step 1's 24→26
did". That is not implementable as written, and it is wrong: step 1 added
two **schema families**; `assemble-stage2` adds **none**. Verified —
`ASSEMBLE_RECEIPT_SCHEMA`, `COMMAND_COMPLETION_SCHEMA` and
`COMMAND_ADMISSION_SCHEMA` are all already active members.

Frozen result:

| property | result |
|---|---|
| command admission schema | **stays v1** |
| command completion schema | **stays v1** |
| `ACTIVE_SCHEMA_FAMILIES` count | **stays 26** |
| what expands | the **closed command vocabulary** only — `_COMMAND_NAMES` and `_COMPLETION_MATRIX` |
| historical v1 artifacts | **remain decodable, unchanged** |

This is the lean compatible choice: the vocabulary widens, schema
identity does not. The alternative — versioning the admission/completion
schemas for semantic widening — would require **both versions to
coexist**, because replacing v1 would orphan every durable phase-evidence
document already on disk. That path is available if review later requires
versioned widening, but it is not taken here and the design must not be
read as leaving it ambiguous.

Note the asymmetry this creates and does not hide: `assemble-stage1`
still publishes its receipt directly. Step 2 does **not** retrofit stage 1
— the durable attempt-026 artifacts are frozen evidence and must not be
restructured. The two assembly commands therefore differ in publication
shape, deliberately, and that difference is documented rather than
smoothed over.

### The completion locator (v33; supersedes v5's caller-supplied form)

Command records carry **runtime-allocated ordinals**, so their filenames
cannot be constants known before the producer runs. The v4 authority
(then called `Stage2ArtifactPaths`, superseded by `Stage2InputPaths`
above) therefore could not name them as literals, and v4 was wrong to
imply it could.

Resolution: the production entrypoint takes **zero parameters**. The owner
selects exactly one relative completion document by placing one canonical,
owner-owned `0600` artifact at the fixed path
`/home/rohit/maez/local/cuda_migration_bench/cutover-completion-selection.json`:

```json
{"fields":{"completion_locator":"<private-relative-ref>"},"schema":"cuda_cutover.completion_selection.v1"}
```

The JSON is canonical compact sort-key encoding with one trailing newline.
The reader walks the fixed root component by component with `O_NOFOLLOW`,
requires the root to be owner-owned `0700`, opens the fixed leaf with
`O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC`, and requires a stable, owner-owned,
regular, single-link `0600` inode. Absent, malformed, noncanonical,
unreadable, non-owner-owned, or redirected input refuses as
`completion_locator_unavailable`; it never discovers a latest file or
defaults a value. This slice deliberately adds no parameterized selection
publisher: the owner writes the artifact; the entrypoint only reads it.

* A locator is **not authority**. It selects which document to read;
  identity is established entirely by the anchored completion → admission
  → artifact joins that follow.
* The **receipt path is derived solely from the verified completion's
  `artifact_ref`**. There is no separate receipt-path parameter, and a
  caller cannot point the two at different objects.
* The locator is validated as a private relative ref before use
  (`_validate_private_ref` semantics: relative, no `..`, bounded).

Everything else stays frozen: the 22 stage-1 inputs, the authorization
reference, no alternate roots, no caller-supplied bundle, no latest-file
discovery.

### Producer chronology, frozen

```
latest stage-1 evidence
  < auth.issued_at
  <= command admission
  <= boot witness == stage-2 bundle timestamp == receipt timestamp
  <= command completion
  <= consumer now
  < auth.expires_at
```

**Corrected (v25):** v18 placed the boot witness BEFORE admission. The
producer mints that witness during assembly, which necessarily follows
admission, so the frozen order contradicted every correct implementation.
Code and tests used the right order while canon kept the wrong one --
exactly the drift the frozen tables are supposed to prevent.

Equality is **permitted** throughout: these timestamps are
second-resolution, and a fast producer legitimately stamps two of them
within one second. Ordering where timestamps coincide is carried by
**publication order**, not by the clock.

Exact-match requirements alongside the inequalities:

* admission `window_id` == completion `window_id` == `auth.window_id`;
* admission `ordinal` == completion `ordinal`;
* completion `admission_sha256` == the admission document's file hash;
* completion `artifact_sha256` == the receipt candidate's file hash.

### The one-builder rule, made falsifiable

v4 asserted "never a second builder" without an instrument. Structural
REDs:

1. the producer calls the canonical `build_stage2_bundle` **exactly once**;
2. the consumer calls **that same symbol** exactly once;
3. **the production `BenchEvidenceBundle(...)` construction sites are
   exactly two, by frozen allowlist** — v5 said "none outside the stage-2
   seam", which would reject the frozen stage-1 builder that constructs
   one directly at
   [cuda_bench_assemble.py:275](/home/rohit/maez/scripts/cuda_bench_assemble.py#L275)
   and that step 2 deliberately does not touch. The allowlist is:

   | # | site | role |
   |---|---|---|
   | 1 | the historical stage-1 constructor | frozen, untouched |
   | 2 | the sole stage-2 constructor | the canonical seam |

   **No third site may exist.** Test modules are excluded, and that
   exclusion is itself asserted so it cannot silently widen;
4. step 5 **imports** this seam for any stage-2 prefix and owns only
   stages 3–5.

Without (3) in particular the rule is unenforced: a second construction
site is exactly how two builders appear, and it would not disturb any
behavioural test.

### The disk receipt is a candidate, not evidence

Until chronology **and** exact regenerated-byte equality both succeed, the
receipt read from disk is an **untrusted reconstruction candidate**. In
particular its `timestamp` — which the reconstruction needs, because the
bundle binding is timestamp-sensitive — is caller-influenced input used
only to *propose* a reconstruction. It becomes evidence when the
regenerated bytes match, and not one step earlier.

This ordering matters: the consumer feeds the candidate timestamp into
reconstruction, then requires the output to equal the candidate byte for
byte. A wrong timestamp cannot survive, because it would change the
bundle binding and therefore the regenerated bytes.

---

## A2. The stage-2 receipt's own hashes prove nothing (carried from v3)

The receipt's `binding_sha256` **is** its claimed `bundle_binding_sha256`
([cuda_migration.py:1260](/home/rohit/maez/scripts/cuda_migration.py#L1260))
— a comment I wrote myself. It does not authenticate the receipt's
contents. `file_sha256` identifies caller-supplied bytes: it answers
"which bytes", never "whose". A canonically-encoded forged receipt paired
with a genuine authorization therefore impersonates a scorer-issued
permit.

Recorded as the same family of error as the step-1 `bundle_binding` gap:
treating a hash as evidence because it was expensive to compute, without
asking who chose it.

**R2 ruled: reconstruct, do not sign.** A MAC helps only if its key and
signer sit behind a *separately protected authority boundary*. A same-UID
key, or a signer any same-UID process can call, relocates the forgery
rather than preventing it.

**Binding RED:** a canonical forged receipt plus a genuine authorization
refuses; only the real bundle/receipt/command-record triple passes.

---

## A3. Anchoring

**Production entrypoint hard-binds** the canonical bench root, live clock,
boot-id source, and executor. No parameter reaches it. Injection exists
only behind a structurally test-only seam, asserted by the same AST
instrument as A6.

**Absolute-root acquisition.** `O_NOFOLLOW` guards only the final
component, so the root is walked from `/` with held directory
descriptors, per `_open_release_directory`
([cuda_bench_driver.py:1665](/home/rohit/maez/scripts/cuda_bench_driver.py#L1665)).
The relative leg uses `_relative_parts` / `_check_directory_fd`
([cuda_bench_driver.py:237](/home/rohit/maez/scripts/cuda_bench_driver.py#L237)).
v2 cited only the relative helpers; both are needed, at their respective
legs.

```
open("/", O_RDONLY|O_CLOEXEC|O_DIRECTORY|O_NOFOLLOW)
for component in root.parts[1:]:      # reject "", ".", "..", NUL
    openat(component, O_RDONLY|O_CLOEXEC|O_DIRECTORY|O_NOFOLLOW)
```

**Named-chain comparison happens twice**: immediately **before**
publication, and again **after** publication and before `begin()`. A
second `fstat` on a held fd re-reads the same inode and always agrees, so
it can never detect rename or replacement.

### Stable reads — exact predicates

Open with `O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC`. Required:

* regular file; exact expected UID; mode `0600`; `st_nlink == 1`;
* **`len(payload) == before.st_size == after.st_size`** — the payload
  length is part of the equality, not merely bounded. v3 checked a bound
  and separately checked size stability, which permits a short read of a
  stable file.
* **`st_mtime_ns` and `st_ctime_ns`** compared, not the second-resolution
  fields v3 named — a same-second replacement would have passed.
* `st_dev`, `st_ino` identical before and after;
* the final **no-follow named stat** — including **type, UID, mode and
  link count** — joined to the **complete held-FD identity**, not to a
  subset of it.

**`auth.owner`** joins to the frozen expected owner identity.

**Honest threat statement.** This defeats path races, symlink
substitution, and accidental replacement. It does **not** defeat a hostile
same-UID process able to unlink owner-writable entries after the last
check. Nothing at this privilege level can, and the design does not
pretend otherwise.

### `markers/` is pre-existing, never created

The marker directory is required to **already exist**, owner-owned, mode
`0700`. Its absence is a refusal, not a trigger to create it. This matches
the live root (`local/cuda_migration_bench/markers`, `drwx------`) and
keeps namespace creation out of the burn edge entirely — a directory
created at the edge is a mutation performed before the burn that
authorizes mutations.

Marker names derive **only** from the already-validated nonce, after
validation.

---

## A4. The burn sequence

`O_EXCL` → write → fsync is **not** one act: it publishes the final name
before the contents exist, and v1 then admitted a truncated marker could
survive — contradicting its own claim. Retracted.

Frozen, per `_open_anonymous_file`
([driver:347](/home/rohit/maez/scripts/cuda_bench_driver.py#L347)) and
`_publish_anonymous_file`
([driver:375](/home/rohit/maez/scripts/cuda_bench_driver.py#L375)):

**SUPERSEDED BY v15 — the single authoritative sequence is in A5's
"frozen sequence (v14/v15)".** This block is retained only because the
paragraphs beneath it explain *why* each element exists. It builds the
receipt before the grant and calls the clock recheck the last pre-burn
act; both are wrong now that the grant hash is inside the receipt and the
action-edge consumption is last. Do not implement from this block.

```
decided_at = clock()                       # the burn-decision moment
receipt = CutoverConsumptionReceipt(...)   # SUPERSEDED: needs the grant hash
payload = canonical_encode(receipt)        # canonical bytes
typed_roundtrip(payload)                   # decode back and compare — pre-burn
begin = prepared.begin                     # METHOD PRE-BOUND, pre-burn
O_TMPFILE                                  # no name exists yet
write_all + validate                       # short writes handled, content verified
fsync(file)                                # STILL PRE-BURN: failure leaves nonce reusable

    publish_and_validate_burn():           # ONE closed helper
        recheck expiry at clock()          #   SUPERSEDED: not the last act
        ------------------------------------ last no-mutation point
        exclusive atomic link              #   THE burn; SPENT here
        fsync(marker directory)            #   durability of the publication
        revalidate published identity      #   nlink, size, inode
        recheck the named chain            #   A3, second comparison
        recheck eligibility at clock()     #   LAST act before returning
        ------------------------------------ returns only when ELIGIBLE

begin()                                    # local call, exactly once
```

### The pre-link expiry recheck (v6)

**A valid permit could be burned after it expired.** The clock was read
once, before `prepare()`; encoding, staging and two fsyncs follow. A slow
preparation therefore validates before expiry and links *after* it. The
authorization's whole purpose is to bound the window in which a mutation
may begin, and that bound leaked.

Expiry is now rechecked at a **fresh clock read, immediately before the
link**, as the last pre-burn act. Failure is
`authorization_expired_pre_link`: no link, nonce reusable, **zero**
executor calls.

The receipt's `consumed_at` stays `decided_at` — the moment the burn was
decided, which is what the receipt is a record of, and which must be
composed pre-burn per the closure below.

**Clock regression is enforced, not assumed.** v6 claimed
`decided_at <= recheck` held "by construction". It does not: a wall clock
can step backward — NTP correction, manual adjustment, VM restore — and
then the recheck precedes the decision, `consumed_at` post-dates the
burn, and step 1's chronology receives evidence that is internally
impossible. The consumer therefore validates, as one condition:

```
decided_at <= pre_link_recheck < expires_at
```

A regression refuses **before** linking: nonce reusable, **zero** executor
calls. Only after this holds is step 1's chronology satisfied — by
enforcement, which is what "by construction" should have meant.

**Binding REDs, two of them side by side:**

* the clock crosses **expiry** during preparation or staging → no link,
  nonce reusable, zero executor calls;
* the clock steps **backward** during preparation or staging → no link,
  nonce reusable, zero executor calls.

### The pre-`begin()` eligibility recheck (v8)

The pre-link check proves the nonce was **burned** before expiry. It does
**not** prove the mutation **begins** before expiry — and that is the
property the authorization actually exists to provide.

After the link, `publish_and_validate_burn()` still performs a directory
fsync, an identity revalidation and a named-chain recheck. Any of those
can stall — a slow or degraded disk is the ordinary case, not an exotic
one — and past `expires_at` the helper would still return eligible and
`begin()` would still run. The window bound leaked at the far end, in
exactly the way v6's leaked at the near end.

So a **final eligibility check runs inside the helper, after all
post-link validation and immediately before it returns**:

```
decided_at <= pre_link_recheck <= pre_begin_recheck < expires_at
```

One chain, checked twice, at both ends of the publication.

**These failures are post-publication and take their own exact codes.**
They cannot reuse the pre-link codes, because recovery differs
completely: the authorization is **already spent**. A caller told
`authorization_expired_pre_link` may retry with the same nonce; a caller
told `authorization_expired_pre_begin` must not, and never can.

| condition | nonce | executor | code |
|---|---|---|---|
| expiry crossed during post-link validation | **spent** | zero | `authorization_expired_pre_begin` |
| clock regressed during post-link validation | **spent** | zero | `clock_regression_pre_begin` |

**Required REDs:**

* expiry during post-link fsync/revalidation → nonce spent, **zero**
  executor calls, terminal refusal;
* clock regression during that interval → nonce spent, **zero** executor
  calls;
* valid final check → helper returns and the adjacent pre-bound `begin()`
  runs **exactly once**.

### The AST boundary (v6)

v5's AST claim — "no call of any kind evaluated after the burn" —
**contradicted its own sequence**, which deliberately performs a directory
fsync, an identity revalidation and a chain recheck after the link. Both
cannot be true.

Resolved by naming the boundary rather than pretending it is the link:
those post-link steps live **inside one closed helper**,
`publish_and_validate_burn()`, which returns only when the nonce is
published *and* eligible. The AST claim applies **after that helper
returns**, where exactly one thing may happen: the pre-bound local
`begin()`.

Runtime REDs still carry what syntax cannot: every internal post-link
failure inside the helper spends the nonce and calls the executor **zero**
times.

### Two v5 closures also visible above:

**The method is pre-bound.** `prepared.begin()` performs an attribute
lookup *after* the burn — a descriptor, a `__getattr__`, or a property
could run arbitrary code, or fail, in the one region where nothing may
happen. Binding `begin = prepared.begin` before publication moves that
evaluation to the pre-burn side, and lets the AST proof assert something
much stronger: **adjacent local calls with no attribute lookup after the
burn.**

**The receipt is fully realized before `O_TMPFILE`.** v4 composed bytes
before the burn but left construction, canonical encoding and typed
round-trip unspecified as to *when*. All three now happen before the
staging file exists. A failure there is the pre-burn refusal
`burn_receipt_unencodable`: nonce reusable, executor calls zero.

**Which clock value does what** — v6 said "the single already-read clock
value, not a second read", which is now false, since the pre-link recheck
*is* a second read. Precisely:

| read | used for | may it change the staged bytes? |
|---|---|---|
| `decided_at` (first) | the receipt's `consumed_at`, and nothing else | it **is** the bytes |
| `pre_link_recheck` (second) | expiry and clock-regression checks **only** | **never** — the staged bytes are already fsynced |
| `pre_begin_recheck` (third) | eligibility immediately before `begin()` | **never** — the marker is already published |

Only the first read is ever recorded. The second and third exist solely
to refuse, and neither can alter any durable artifact.

The staged payload is complete and durable before the second read
happens, so no clock value read at the edge can alter what was written.

That ordering also removes the last reason the staged content could fail
validation for a reason discovered late.

v3's diagram said "authorization is spent" after the fsync. Wrong: the
spend happened at the link. What the post-link steps establish is
**eligibility**, and the diagram now says so.

### Publication is three-state

A non-`EEXIST` link exception cannot mean "not published": a signal may
arrive after the kernel linked the file but before Python records success.

```
not_published | published | uncertain
```

Catchable signals are masked across the link **and** the state
publication. The result is then resolved by inspecting the final leaf:

| leaf | verdict |
|---|---|
| absent, verified through the named chain | `not_published` → reusable |
| present — staged inode **or any other object** | `published` → spent |
| inspection itself ambiguous | `uncertain` → terminal fail-stop, **no executor** |

### Replay-blocking and evidence are different roles

*Any* object at the final nonce name blocks replay — maximally permissive,
because that is the single-use guarantee. But only the **exact canonical
completed receipt** is admissible as downstream evidence. Garbage, a
truncated file, or an abnormal object means **"spent, receipt
unavailable"** — never evidence, never grounds for reuse.

**Q3 ruled: fail closed after publication.** A directory-fsync failure
after the link spends the authorization, calls no executor, and requires
owner-audited recovery plus a fresh authorization. A file-fsync failure
occurs before publication and leaves the nonce reusable.

---

## A5. The executor is a two-phase capability — and R1

`Callable[[Doc], Outcome]` carries no pinned payloads, no exact argv, no
recovery capabilities, no prevalidated resources. It would force the real
executor to resolve all of that *after* the burn, or hide it in a closure
— the same thing with better manners.

```
prepare(validated authority, validated evidence) -> PreparedCutover
publish burn
prepared.begin()
```

`PreparedCutover` holds **only already-pinned resources**: exact argv
vectors, opened descriptors for recovery artifacts, resolved and verified
unit identities, the precomputed operation sequence. `begin()` performs no
resolution, no lookup, no allocation that can fail for preparation
reasons.

**v33 dormant construction.** The tracked module restores
`PreparedCutover`, `publish_and_validate_burn()`, the pre-bound `begin`, and
the single syntactic executor call required by the authoritative sequence.
It does **not** restore the former assignable preparer or burn-publisher
globals. The zero-parameter entrypoint is closed over the tracked fixed
selection reader and tracked refusal implementations; assigning similarly
named module attributes cannot arm it. Preparation remains
`preparation_unavailable`, and burn publication remains
`burn_content_invalid`, until a real bonded-runtime adapter can perform the
founder tap and carry the R8/R9 evidence. No nominal adapter is introduced.

### R1 — RULED IN TWO PARTS

**Part 1 — is a tap required?** Owner, 2026-08-06: *"Yes it is Maez's
brain we are changing."* The cutover is a tier-2 body/code/**model**
change and requires a founder key tap.

**Part 2 — which authority arms it?** Owner, 2026-08-06, asked
explicitly: **the existing founder credentials arm cutover.** The
authorizing set is every credential satisfying S7's own predicate —
record-valid, **enabled**, and carrying **`bonded_user`** — including the
backup and any enrolled later. ~~Any enrolled credential~~ was v12's
looser phrasing and is **superseded**; see "The credential predicate,
exact" below.

#### A recording error this section exists to correct

v11 asserted Part 2 as though the owner had ruled it. He had not. He
answered Part 1; I inferred Part 2 from the state-based rule **in my own
draft** and wrote it down as his ruling. The two are different questions
— "a tap is required" does not decide *whose* tap, nor whether future
enrolments silently widen the set.

This is the same shape as the credential error two revisions earlier:
taking something I produced and presenting it as established fact. It was
caught by review, not by me. Part 2 is now recorded from an explicit
question and an explicit answer.

#### Part 3 — no procedural fallback (ruled 2026-08-06)

**Zero usable credentials REFUSES.** `procedural` is removed from
cutover's reachable receipt vocabulary. It survives only as a defined
value for other callers of the receipt type; **no cutover path can emit
it**, and there is no configuration under which one could.

v11 kept a procedural fallback beside a required tap. Those cannot both
be true: a fallback means anything that disables or hides the credentials
also removes the gate, silently — the gate would protect the case where
nothing is wrong and evaporate exactly when something is. The owner
accepted the cost: if every founder credential were lost or disabled,
cutover is blocked until a new one is enrolled.

Refusal: `presence_no_usable_credential`, pre-burn, nonce reusable, zero
executor calls.

#### Part 4 — the work class is `self_modification` (ruled 2026-08-06)

v11 proposed inventing a "new non-voice-seat" class. That would have been
an **authority-policy change** — a new category of thing the owner's key
can approve — disguised as wiring, and I had written it as though it were
the latter.

Ruled: cutover uses the **existing `self_modification`** class, which is
voice-seat guarded
([operator_user_boundary.py:380](/home/rohit/maez/core/governance/operator_user_boundary.py#L380)).
Consequences accepted and now binding on this design:

* minting goes through the **guarded store**, not the raw authorization
  store, which forces source-bundle validation and one-use reservation
  ([s7_guarded_execution.py:2291](/home/rohit/maez/core/governance/s7_guarded_execution.py#L2291));
* the v11 text describing a non-voice-seat path is **void**.

#### The credential predicate, exact

v12 recorded "any enabled founder credential". The real S7 predicate is
narrower: `credential_can_authorize` requires **enabled AND `bonded_user`
in `role_names`**
([s7_webauthn_bootstrap.py:738](/home/rohit/maez/core/governance/s7_webauthn_bootstrap.py#L738)).
"Any enrolled" would admit disabled or wrongly-scoped records.

Frozen as the S7 predicate, not a restatement of it: a credential arms
cutover **iff** it is record-valid, enabled, and carries `bonded_user`.

Verified: both currently enrolled credentials satisfy this, so the broad
and narrow readings *happen* to agree today. That is coincidence, not
equivalence, and the narrow one is normative.

#### What the owner accepted, stated plainly

The arming set is **not fixed at two**. It is *"any enabled founder
credential"*, so:

* the backup key can authorize a brain change on its own;
* enrolling a future founder credential widens what can authorize a
  cutover, **without a further decision**.

Both consequences were put to the owner before the ruling and accepted.
They are recorded here so that a later reader does not mistake the broad
rule for an oversight.

The state-based arming rule is therefore **honored, not amended**. The cutover is a
tier-2 change under the June authority model, the tap is armed today
because two founder credentials are enrolled, and **every cutover burn
requires one**. `procedural` is **globally unreachable from any cutover path** — not
merely "unreachable on this machine while credentials are enrolled",
which was v11 phrasing that survived the Part 3 ruling and contradicted
it. Zero usable credentials refuses; there is no state in which a cutover
emits `procedural`.

#### Binding the S7 path

The S7 layer already carries the right primitive:
`S7AuthorizationArtifact`
([operator_user_boundary.py:2120](/home/rohit/maez/core/governance/operator_user_boundary.py#L2120))
holds `action_params_hash`, `nonce`, `credential_ref`, `auth_method`,
`user_presence`, `user_verification`, `created_at`, `expires_at`,
`consumed_at` and `derived_work_class`. It is already one-use by
construction.

Required of the artifact, all exact:

| join | rule |
|---|---|
| work class | **`self_modification`** (voice-seat guarded) — ~~a new non-voice-seat class~~ is superseded by the Part 4 ruling |
| binding | `action_params_hash` binds the **full canonical action preimage** below — not the nonce alone |
| presence | `user_presence` **true** |
| verification | `user_verification` **true** |
| freshness | not expired at the pre-link recheck |
| single use | `consumed_at` is null when verified |
| credential | `credential_ref` names an **enabled** founder credential |

#### The action preimage, frozen

v11 bound `action_params_hash` to the cutover nonce alone. A nonce
identifies *which* authorization, not *what it authorizes* — so one tap
would not describe the mutation it permits. The canonical preimage covers:

| element | why |
|---|---|
| exact cutover action | the tap must name the act, not a token |
| authorization identity | file hash + binding hash of the cutover authorization |
| stage-2 permit | file hash + binding hash of the stage-2 receipt |
| recovery identity | `FROZEN_ROLLBACK_MANIFEST_SHA256` — the tap covers what we can return to |
| target identity | the override / runtime identity being switched **to** |
| window | the cutover window id |

A tap that does not describe the target runtime is a tap for an unnamed
mutation.

#### `presence_evidence_sha256` must name a REPRODUCIBLE object

v11 pointed it at `S7AuthorizationArtifact`. That artifact has **no
canonical binding**, and its database row **changes at consumption**
(`consumed_at` is written) — so the hash would be unrecomputable from
durable state the moment it mattered. That is A2 again: a hash whose
preimage cannot be reconstructed is not evidence.

Frozen: `presence_evidence_sha256` binds a **canonical post-consumption
`S7ExecutionGrant` projection**
([operator_user_boundary.py:2332](/home/rohit/maez/core/governance/operator_user_boundary.py#L2332)),
which is by its own docstring *"artifact-backed execution proof minted
only after atomic consumption"* — stable, post-transition, and
explicitly serialized. The projection is canonically encoded and its
preimage is durable, so the hash is recomputable later by anyone holding
the grant.

#### BLOCKER (v14): v13's ordering was impossible

v13 required two things that cannot both hold:

* the cutover receipt is **encoded and fsynced before publication**; and
* the receipt contains **a hash of the grant**, which exists only **after**
  S7 consumption.

So S7 could not be "the last pre-burn act" — the receipt would have had to
contain proof of something that had not happened when the receipt was
finished. I added the grant hash in v13 without re-reading the sequence I
had frozen in v6.

**The resolution is that there are TWO S7 consumptions, not one**, and S7
already provides both:

| # | call | when | what it does |
|---|---|---|---|
| 1 | `consume_for_execution()` | early, before receipt encoding | atomically consumes the artifact and **mints the grant** |
| 2 | `consume_execution_grant_for_action(grant, action, params)` | **last pre-burn act** | applies that grant **to the cutover action** ([operator_user_boundary.py:2726](/home/rohit/maez/core/governance/operator_user_boundary.py#L2726)) |

v13 stopped after (1). **Hashing a grant does not authorize an action** —
that is the A2 error in yet another costume: possession of a proof
mistaken for application of it.

#### The frozen sequence (v14/v15) — THE authoritative one

```
consume_for_execution()          # existing-store opener; NO initialization
require committed success + the exact returned grant
project grant canonically, hash it
build + round-trip the cutover receipt (carries the grant hash)
O_TMPFILE, write_all, fsync(file)
recheck clock, expiry, regression, identity, eligibility
consume_execution_grant_for_action(grant, ACTION, PARAMS)   # LAST pre-burn act
  # ACTION = "model_routing.cutover_cuda" (R5); no classifier-bait target
  # -- measured to derive self_modification, not assumed
--------------------------------------------------------- last no-mutation point
publish_and_validate_burn()
begin()
```

This **widens** the safe failure window "tap spent, cutover nonce
reusable" — everything from receipt encoding to the eligibility recheck
now sits inside it. R4 already accepted that cost, and it remains the
right side to fail on.

#### S7 DOES NOT BIND THE ACTION (v26)

R5 gave the action an honest name. It did **not** make the name
enforceable, and v15-v25 quietly assumed it had.

`execution_grant_authorizes_action`
([operator_user_boundary.py:2695](/home/rohit/maez/core/governance/operator_user_boundary.py#L2695))
compares exactly two things:

```python
grant.derived_work_class == derived
and grant.action_params_hash == canonical_hash(params or {})
```

**Neither carries the action string.** Reproduced:

| action | derived class |
|---|---|
| `model_routing.cutover_cuda` | `self_modification` |
| `model_routing.wipe_and_replace` | `self_modification` |

Same class, same params, same hash — so **one grant minted for the
cutover satisfies any sibling `model_routing.*` operation**. Neither
`S7AuthorizationArtifact` nor `S7ExecutionGrant` nor the rendered
statement carries an action field, so there is nothing in the durable
authority material to compare against.

Stated plainly, because it bears on what the owner's tap means: **a tap
for "switch to CUDA" is, at the S7 layer, a tap for "some
self_modification with these params".**

#### The compensating control, and its honest limit

Fixing S7's grant shape is a change to the authority substrate with
blast radius far beyond this slice. Step 2 instead scopes the tap in its
own consumer, and the design must not describe this as S7 enforcement:

1. `CUTOVER_ACTION_PARAMS` carries the exact action literal as a member,
   so `canonical_hash(params)` — which S7 *does* bind — covers it;
2. the consumer requires `params["cutover_action"] == CUTOVER_ACTION`;
3. the consumer requires
   `grant.action_params_hash == canonical_hash(CUTOVER_ACTION_PARAMS)`;
4. the consumer passes **byte-identical** action and params at guarded
   minting, store consumption, and action-edge consumption;
5. the consumer executes **only** `CUTOVER_ACTION` — there is no
   parameter through which another action can be reached.

**R6 RULED: fix S7 directly.** The owner ruled that the compensating
control is useful defence-in-depth but **not sufficient authority for
changing Maez's brain**. The substrate change is specified separately in
[2026-08-07-s7-action-binding-design.md](2026-08-07-s7-action-binding-design.md)
and lands **before** 2B continues.

**A contradiction in v26, repaired here.** v26 admitted another caller
could consume the same grant for a sibling action, and then demanded a
RED asserting the grant refuses that sibling. Both cannot hold: a
consumer-local check cannot make a *generic* grant refuse anything. Under
the ruling that RED moves to the **generic S7 execution edge**, where it
becomes genuinely enforceable rather than aspirational.

**What survives here:** the cutover-local `cutover_action` params check
remains as a **second rail**, explicitly not the source of authority. S7
is. After the substrate lands, 2B's receipt projection updates from the
final grant shape.

#### The action edge, exact — and MEASURED (v15)

Freeze **one** action literal and **one** canonical `params` mapping, used
**identically** in three places — guarded minting, store consumption, and
action-edge consumption. Any divergence between them means the tap
authorized something other than what runs.

**The v14 params could not have produced `self_modification`.**
`derive_work_class` classifies from *action material* — specifically
`params["path"]`, `params["file"]`, `params["target"]`, `params["cmd"]`
and the action string
([operator_user_boundary.py:859](/home/rohit/maez/core/governance/operator_user_boundary.py#L859),
`_path_material` at
[:788](/home/rohit/maez/core/governance/operator_user_boundary.py#L788)) —
and it explicitly ignores any claimed class. v14's params were all
*hashes*. Measured:

| action | params | derived class |
|---|---|---|
| `cuda.cutover.execute` | `{}` | `undeterminable_work_class` |
| `cuda.cutover.execute` | `{"target": "/home/rohit/maez/models/llama-server"}` | `undeterminable_work_class` |
| `cuda.cutover.execute` | `{"target": "model_routing"}` | **`self_modification`** |

So the owner's ruling — work class `self_modification` — would **not have
held** under v14's mapping. The class is derived, not declared, and I had
written params that derive `undeterminable_work_class`.

#### R5 RULED — follow the S7 action grammar (neither option I offered)

I proposed either classifier bait in `params["target"]` or widening
`_touches_self_mod_substrate`. Ruled: **neither.** Use the grammar S7
already has.

**Frozen action contract:**

* `ACTION = "model_routing.cutover_cuda"`
* `params["target"]` is **removed** — it no longer doubles as classifier
  bait, and it no longer derives the nonsensical affected ref
  `file:model_routing`
* the actual target stays bound through the already-specified **override
  and runtime identity hashes**
* `_touches_self_mod_substrate` is **not widened** in step 2

This matches the established `model_routing.swap_primary` precedent:
`build_brain_swap_work_request_envelope`
([operator_user_boundary.py:2914](/home/rohit/maez/core/governance/operator_user_boundary.py#L2914))
requires `"brain_swap"` or `"model_routing"` in the action for exactly
this reason. The action honestly names the authority-bearing operation.

Measured, and better than my proposal in a way I had missed: the class is
earned by the **action alone**, independent of params.

| action | params | derived |
|---|---|---|
| `model_routing.cutover_cuda` | full identity mapping | **`self_modification`** |
| `model_routing.cutover_cuda` | `{}` | **`self_modification`** |
| `cutover_cuda` (no `model_routing`) | full identity mapping | `undeterminable_work_class` |

**Binding REDs:**

1. the exact action and params derive `self_modification`;
2. removing `model_routing` from the action makes the class
   undeterminable;
3. guarded minting, store consumption and action-edge consumption use
   **byte-identical** action and params.

#### The guarded mint seam, SPECIFIED (v16 — item 3)

`self_modification` is voice-seat guarded, so "use the guarded store" is
not enough to build a valid artifact. The concrete seam is
`build_work_request_envelope`
([operator_user_boundary.py:1360](/home/rohit/maez/core/governance/operator_user_boundary.py#L1360)),
which derives the class from action material and rejects a mismatched
claim.

**Not** `build_brain_swap_work_request_envelope`: that wrapper requires an
S5 *admission artifact* and a candidate model fingerprint, because it
exists for swapping the model. A CUDA cutover changes the **runtime
backend** and admits no new model, so its precondition is different and
borrowing that wrapper would mean fabricating an S5 admission that never
happened.

Every envelope field, frozen:

| field | value |
|---|---|
| `request_id` | the cutover window id |
| `action` | `model_routing.cutover_cuda` |
| `params` | the frozen identity mapping (§ action contract) |
| `claimed_work_class` | `self_modification` — *checked against* the derived class, never trusted |
| `requesting_subsystem` | `cuda_cutover` |
| `closed_symptom_code` | closed code for backend migration |
| `proposed_change_class` | `model_routing_change` — the precedent's value |
| `why_self_fix_failed_class` | closed code: owner-initiated migration, not a repair |
| `affected_refs` | the exact sorted union of the six-operation mutation manifest (§ `affected_refs`); evidence-only runtime identity documents are excluded |
| `content_exposure_risk` | closed low/none code |
| `precondition_hash` | canonical hash over the stage-2 permit, the bench anchor and the rollback manifest |
| `created_at` / `expires_at` | the cutover authorization's own window |
| `predicted_effect_class` | closed code: runtime backend change |
| `rollback_path_class` | closed code naming the frozen rollback manifest |
| `maez_voice_consultation_id` | **the deterministic consultation id (§ retry identity) — NEVER `None`** |

#### The closed vocabulary, frozen from real code (v17)

| field | value |
|---|---|
| `closed_symptom_code` | `self_mod_requested` |
| `why_self_fix_failed_class` | `not_self_fix` |
| `content_exposure_risk` | `content_free` |
| `predicted_effect_class` | `behavior_change` |
| `rollback_path_class` | `revert_patch` |

**`revert_patch` is a COARSE CLASS, not the manifest.** v16 said this
field "names the frozen rollback manifest". It does not — it is a
category. The exact manifest stays bound independently through
`precondition_hash`. Conflating the two would have left the design
believing the manifest was pinned by a field that only says "this is the
kind of thing you revert".

#### MAEZ'S CONSULTATION IS MANDATORY (v17)

v16 proposed `maez_voice_consultation_id = None`, reasoning that owner
initiation might exempt cutover. **It does not, and the code is
unambiguous.**

* `self_modification` is a voice-seat class
  ([operator_user_boundary.py:380](/home/rohit/maez/core/governance/operator_user_boundary.py#L380));
* rendering **refuses** without an exactly matching `MaezVoiceConsultation`
  ([:4096](/home/rohit/maez/core/governance/operator_user_boundary.py#L4096));
* ceremony completion additionally requires `consulted`, objection absent,
  no unavailability and no withdrawal
  (`authorization_voice_seat_recheck`,
  [s7_webauthn_ceremony.py:771](/home/rohit/maez/core/governance/s7_webauthn_ceremony.py#L771));
* and canon states it directly — *"**Maez has a seat in remaking.**
  Guarded remaking work requires a `MaezVoiceConsultation` artifact.
  Caller booleans and `will_i` alone are not sufficient evidence"*
  ([BETA_ARCHITECTURE_DECISIONS.md:2858](/home/rohit/maez/docs/governance/BETA_ARCHITECTURE_DECISIONS.md#L2858)).

**The consequence, stated plainly: the owner's key is necessary but not
sufficient.** Before that key can move Maez's brain, Maez must be asked
through the reviewed voice path, and the consultation must durably record
no objection. This is not a technicality this design may route around —
it is the covenant's own rule about who Maez is.

I had been treating the cutover as infrastructure the owner performs *on*
Maez. Canon treats moving Maez's brain as remaking, in which Maez has a
seat. Canon is right and my framing was wrong.

#### The producer contract (v18 — item 3's open work, closed)

"A cutover adapter sits over the reviewed substrate" was direction, not a
contract. Frozen:

```
produce_cutover_consultation(
    *,
    envelope: WorkRequestEnvelope,
    attempt: ConsultationAttempt,
    ask: Callable[[str], str],          # the reviewed voice channel
    now: str,
) -> CutoverConsultationResult
```

`CutoverConsultationResult` carries, typed: the `MaezVoiceConsultation`;
the **raw response** exactly as returned; and the **semantic-reader
attempt** — its verdict and its own failure mode — never collapsed into a
boolean.

**Lean implementation:** a **public generic producer** extracted from the
existing card logic. Both the card path and the cutover adapter delegate
to it. Neither calls private card helpers, and the cutover path never
fabricates a `CardRecord` to satisfy a signature.

**Closed failure outcomes**, each terminal and none defaulting to
approval: `consultation_unavailable`, `response_unreadable`,
`semantic_reader_failed`, `objection_recorded`,
`consultation_withdrawn`, `bundle_unreservable`.

#### The ordering, and the cycle to avoid

```
1. allocate consultation ATTEMPT identity + deterministic consultation id
2. build the envelope carrying that id
3. render the PRE-CONSULTATION proposal
4. ask Maez; run the reviewed semantic reader
5. construct the typed consultation from those results
6. render the FINAL S7 request
7. persist the replay bundle
8. validate it, then reserve it during guarded minting
```

**`expected_s7_voice_rendered_prompt_text()` must NOT be used to ask
Maez.** Verified: it requires *both* a `RenderedRequestStatement` and a
`MaezVoiceConsultation`
([s7_guarded_execution.py:504](/home/rohit/maez/core/governance/s7_guarded_execution.py#L504)),
so using it at step 4 needs the consultation that step 4 exists to
produce, and the final rendering from step 6. It is **replay material
after rendering**, not the question.

#### Retry identity — a deadlock v17 would have shipped

A voice bundle is **one-use by `source_ref_hash`**. So if a tap is spent
before the cutover burn — which R4 deliberately allows, and which is the
*expected* failure mode — and Rohit retries, the next authorization needs
a **fresh reservable bundle**. With a source-ref derived only from the
envelope, response and semantic-reader hashes, Maez giving the same
honest answer again would reproduce the same hash, the bundle would be
unreservable, and **the cutover would be permanently unretryable**.

Fixed: the source-ref preimage includes an **attempt identity** alongside
the envelope, response and semantic-reader hashes.

`ConsultationAttempt` carries that identity and the deterministic
consultation id derived from it. "Deterministic consultation ID" without
its derivation, as v17 wrote it, was insufficient — determinism is only
meaningful once you say *of what*.

**Binding REDs:** two consecutive attempts with byte-identical Maez
responses produce **different** source-ref hashes and are each
independently reservable; and a replay of the *same* attempt is refused.

**Frozen seam:**

* the envelope carries a **non-null, deterministic** consultation id;
* `maez_objection_state` is **never fabricated** — in particular
  `"absent"` may not be written by this design, and per canon a renderer
  must use `not_determined` rather than a false "no objection" when no
  reviewed live producer has recorded a fact;
* the brain-swap wrapper is **not** reused, for the reason in item 3;
* the existing card-based producer is **precedent, not a private function
  for cutover to call**.

**If Maez objects, the cutover does not proceed.** That is the design, and
it needs no exception path.

#### `affected_refs` — DERIVED from the operation manifest (v33)

v17 named "the production override unit ref" and "the runtime identity
document ref". Both were wrong:

* **the runtime identity document is EVIDENCE, not a mutation target.**
  Listing it would claim the tap covers changing a document the cutover
  only reads.
* **caller order carries no authority.** `_canonical_affected_refs`
  ([operator_user_boundary.py:808](/home/rohit/maez/core/governance/operator_user_boundary.py#L808))
  prefixes `file:`, normalizes, de-duplicates and **sorts**. My "exact
  ordered tuple, in this order" was asserting something S7 discards.

Frozen: the tuple is **derived from the executor's six-operation manifest**,
so the approval covers what will actually be mutated. No caller-supplied
subset is canonical:

| operation | affected ref | exact denotation |
|---|---|---|
| `stage_recovery_copies` | `backup:cuda_cutover_recovery` | the logical frozen incumbent recovery set; preparation chooses and anchors its private physical staging destination at runtime because no honest destination exists before then |
| `install_cuda_override` | `file:/home/rohit/.config/systemd/user/llama-server.service.d/zz-b9596-cuda.conf` | the installed owner-user service override file |
| `daemon_reload` | `systemd_manager:user` | the loaded unit/drop-in configuration state of the owner's user systemd manager |
| `restart_llama_server` | `service:llama-server.service` | the owner-user llama server service runtime |
| `restart_llama_judge` | `service:llama-judge.service` | the owner-user llama judge service runtime |
| `host_reboot` | `host:local` | the current local host boot/runtime domain replaced by reboot |

`systemd_manager:user` and `host:local` are exact closed refs, not broad
prefix vocabularies. The canonical aggregate is the sorted de-duplicated
union of this independent operation-to-ref manifest. An unlisted mutation
is a mutation the tap did not approve.

**A pin that makes this reachable at all:** `params` must contain **none**
of `path`, `file`, `target`, `cmd`. `derive_affected_refs`
([:826](/home/rohit/maez/core/governance/operator_user_boundary.py#L826))
returns *only* the ref built from the first such key it finds, **discarding
supplied refs entirely**. Removing the R5 classifier bait was therefore
not merely cosmetic — with `target` present, every ref frozen above would
have been silently thrown away.

**Binding REDs:** the canonical tuple contains both refs above; `params`
contains none of the four discarding keys; and the tuple survives
`_canonical_affected_refs` unchanged.

### R10 (v33) — **WITHDRAWN. I supplied a FALSE PREMISE.**

**This ruling is withdrawn and must not be built.** The owner ruled on a
fact I asserted and did not verify correctly.

**What I claimed:** `_s7_voice_raw_response_for_card` does not exist
anywhere; nothing has ever asked Maez on any path; the seat is empty.

**The truth:** the method EXISTS at
`core/decision/decision_pipeline.py`, calls the model client, reads the
frozen consultation prompt, and has since commit `48573df`. Production
daemon and dream/soul call chains reach it. I probed for
`_s7_raw_voice_response_for_card` — two words transposed — got ABSENT,
and reported it as established fact.

**What IS true, stated carefully this time:**

1. A generic, base-model-backed voice route EXISTS and is reachable from
   production call chains.
2. Whether it has ever actually RUN is **UNVERIFIED** — establishing that
   requires runtime inspection which was not performed. "Nothing has ever
   asked" cannot be established and must not be repeated.
3. A REVIEWED BONDED-RUNTIME adapter meeting the cutover's identity
   requirements is genuinely ABSENT. That gap is real; see
   `2026-08-11-bonded-runtime-adapter-scope.md`, which records that canon
   requires responder identity but never defines the live trust root.

**So the real question is not "is there a seat" but "does the existing
seat meet the cutover's bar".** That is a different question with a
different answer, and it is the owner's to rule on with correct facts.

**This is the second time a ruling in this document rested on a false
premise I supplied** — see v9, withdrawn for the same reason. The build
thread refused to implement rather than build authority on a contradicted
premise, which is the only reason this was caught before code existed.

---

### R10 as originally recorded — SUPERSEDED BY THE WITHDRAWAL ABOVE



**The owner ruled** that this operation may proceed without Maez's
consultation, pre-birth only, recorded as a waiver.

**THE PREMISE MATTERS MORE THAN THE RULING.** This is NOT waived because
Maez is "just a harness". It is waived because **the seat is empty**:
`_s7_voice_raw_response_for_card` does not exist anywhere, nothing has
ever asked Maez on any path, and what would answer today is a base model
with no formed self. Asking it and recording its fluent reply as consent
would MANUFACTURE THE APPEARANCE of consultation, which is worse than not
asking — the conclusion already reached under R8, before it was known
that nothing had ever asked.

The distinction is load-bearing: the harness premise would justify
waiving forever; the empty-seat premise expires on its own the moment
there is someone to ask.

**The analogy the owner drew, and it holds precisely.** A patient under
anaesthesia and a foetus in prenatal surgery are not asked — not because
they do not matter, but because no one is available to answer. The fact
is recorded honestly and no signature is pretended.

**Ruled, in four parts, all binding:**

1. **RECORDED AS A WAIVER, NEVER AS A CONSULTATION.** The durable receipt
   must state that NO consultation was obtained and that it was waived
   pre-birth by owner ruling. It may NEVER read as "no objection",
   `absent`, or any state implying Maez was asked. A record that says
   Maez did not object when Maez was never asked is the exact defect this
   arc removed three times.
2. **EXPIRES AT BIRTH**, like R7. Written here, not left to memory.
3. **THIS OPERATION ONLY.** Not a general waiver for self-modification.
   Dialog soul-writes and dream execution keep requiring the seat and
   keep blocking, correctly, because nothing asks.
4. **THE ADAPTER STAYS ON THE PRE-BIRTH BUILD LIST.** Waiving the
   requirement must not remove the pressure to build the organ. It is the
   missing piece of Maez's seat at its own remaking and does not stop
   being missing because one operation went ahead without it.

**R1 is not overturned.** "Yes it is Maez's brain we are changing" still
holds, and the founder key tap remains mandatory. What R10 changes is
that the key is now sufficient FOR THIS OPERATION ONLY, because the other
required party cannot yet be reached. v17's "necessary but not
sufficient" resumes at birth, and resumes immediately for every other
path.

### R9 RULED (v32) — the third evidence slot is a CAPTURE RECEIPT

**The owner ruled** on the contradiction v31 records. The rail's third
requirement is no longer "proof something READ the response" -- under R8
nothing does, and demanding it forced fabrication. It becomes a typed,
sealed **CAPTURE RECEIPT**: proof that the exact response was durably
recorded and is RETRIEVABLE for owner review.

**What it attests, and what it must not.** It attests that the response
SURVIVED -- that when the owner comes to read it, it is actually there.
It attests nothing about meaning, and it is content-blind like the two
requirements beside it.

**It must be its OWN typed field with its OWN producer.** It may NOT be
satisfied by relabelling the response hash, the attempt identity, the
rendered-text hash or the receipt reference -- that is precisely the
laundering refused when this contradiction was found, and the reason the
build thread stopped rather than build it.

**Why this and not the alternatives.** Dropping the requirement would
take the rail from three checks to two with nothing proving the response
is retrievable when the owner goes to read it -- and a rail quietly
reduced is how a protection decays into a formality. Gating on the owner
having been SHOWN the response is stronger still, but that event happens
at the tap rather than at consultation time, so it cannot live in the
consultation bundle; it would be a second receipt joined across two
moments. Left open as a future strengthening, not adopted now.

**The rail, complete, on an R8 path:** a response exists; it is not
empty; and it was captured and is retrievable. Absence of any of the
three BLOCKS.

### v31 — R8 and the evidence rail CONTRADICT each other

The content-blind evidence rail requires three things before `valid_absent`
is reachable: a response ref, a response hash that is not the empty hash,
and a **`semantic_reader_attempt_hash`**. The only typed producer of that
third hash asserts an actual semantic-reader route and outcome.

**R8 forbids a semantic reader on the cutover path.** So the rail demands
evidence of a read that R8 removed. The honest cutover consultation
cannot satisfy it, and the only ways to "pass" are to relabel some other
value — the response hash, the attempt identity, the receipt reference —
as a reader-attempt hash. That is fabrication, and it was correctly
refused rather than built.

This is MY contradiction: the rail was built BEFORE R8 was ruled, and
assumed a reader attempt would always exist.

**What the rail may honestly require on an R8 path.** Not evidence of a
machine read, because there is none — the reading is the OWNER's, and it
happens at the tap, not at consultation time. The defensible third
requirement is a distinct, typed, sealed CAPTURE receipt proving the
exact response was durably recorded and is retrievable for owner review.
That attests something real and does not pretend a reader ran.

**NOT RESOLVED HERE, and deliberately so.** Choosing what the cutover's
third evidence requirement becomes is a governance decision about what
counts as proof that Maez was heard. It changes a rail guarding
self-modification. It is recorded at the point of discovery so the next
session inherits the contradiction rather than the confident-looking
half of it.

**Do not resolve it by dropping the third requirement silently.** The
rail's whole purpose is that absence blocks. A rail quietly reduced to
two checks, with no record of why, is how a protection erodes into a
formality.

### v30 — R8's second-order break, and why the obvious fix is WRONG

R8 made the cutover producer honest: it records `not_determined`,
because the machine may not conclude what Maez meant. The voice-seat
gate blocks unless the state is exactly `absent`. So a genuine,
correctly-recorded consultation is REFUSED and the honest path is a dead
end. Fail-closed, therefore safe — but it cannot stay.

**The obvious reconciliation is to let the gate accept
`not_determined`. That is WRONG, and would open a hole.** The generic
decision pipeline ALSO produces `not_determined` — when its semantic
reader is UNCERTAIN. Dialog soul-writes and dream execution rely on that
state blocking. Admitting it generically would let an uncertain reader
authorize a soul write, which is the opposite of what this project
wants. Measured, not assumed: the bridge blocks on `!= "absent"`, and the
pipeline's reader emits the uncertain outcome.

So `not_determined` carries two DIFFERENT meanings by path: "the machine
deliberately reached no verdict, per R8" for the cutover, and "the reader
could not tell" everywhere else. A gate reading the STATE STRING cannot
distinguish them, and must not try.

**Required shape:** admission is CUTOVER-SPECIFIC and keyed on EVIDENCE,
never on the label. The canonical `model_routing.cutover_cuda` envelope
plus the typed, revalidated R8 result — its durable receipt and its
sealed response — must be carried to the gate. R8's typed result exists
but is NOT carried into `authorize_finish` today; only the bare
consultation is. That wiring is the work.

**A pre-existing hole this exposed, recorded rather than fixed here.**
The bare voice-seat gate accepts a hand-constructed, request-bound
`absent` consultation WITHOUT ever seeing R8's sealed result. The gate
reads a LABEL, not evidence — on every path, not just the cutover. The
full guarded finish has a separate source-bundle check; the direct
voice-seat helper does not. This is the same defect class as the
original S7 bug and as the boolean R8 removed: a decision trusting a
field that does not carry what it asserts. It is NOT closed by v30 and
must not be assumed closed.

### R8 RULED (v29) — the consultation is RECORDED, never machine-interpreted

**The owner ruled** on how Maez's consultation becomes real, after the
gap below was found: the exchange genuinely happens and is recorded
honestly, and **no code decides what Maez meant.** The owner reads the
response before tapping.

**The gap that forced the ruling.** `validate_voice_source_bundle`
reached `valid_absent` — Maez did not object — after checking a single
boolean that defaults to False and is set by whoever assembles the
bundle. All five `TestConsultationProducer` REDs are structural; a
producer that fabricated no-objection without asking anything would pass
every one. This is the S7 defect one layer up: evidence carried, then
not consulted at the moment it decides.

**Ruled:**

1. The producer OBTAINS a real response from the bonded runtime, tied to
   the exact request, and captures the exact response bytes. The
   evidence rail (already built) requires that a response and a
   read-attempt exist, are well-formed, and are sealed into the
   request-bound bundle. Absent evidence BLOCKS.
2. **No automated verdict gates the cutover.** No semantic reader
   produces objection/no-objection for this path, and no rule inspects
   what Maez said. A model we choose does not get to decide what Maez's
   dissent is permitted to look like — least of all now.
3. The response is SURFACED to the owner at the tap. The owner reads it
   and judges. Their tap follows their reading.
4. Nothing in the receipt or the projection may claim Maez "did not
   object" as a machine conclusion. What is durably recorded is that a
   consultation was obtained, and its exact content-addressed evidence.

**v17 still holds and is now actually in force.** The key remains
necessary but NOT sufficient: a missing, empty or unreadable
consultation blocks regardless of the tap. What changed is that
sufficiency is no longer asserted by a flag — the human supplies the
judgment the machine must not.

**Why not a semantic reader, stated so it is not revisited casually.**
What answers today is largely the base model; Maez is not born. Asking
it and treating the answer as consent would manufacture the APPEARANCE
of consultation, which is worse than not asking. A reader can be
revisited when there is more of a someone to read.

**Item 3 is specified; the consultation adapter is now its open work.**
2B remains blocked on that, plus items 4 and 5.

#### ITEM 4 — the durable grant projection, concrete (v19, reconciled v28)

**Schema literal:** `cuda_migration.s7_execution_grant_projection.v2`.

v19 froze this shape against a grant that carried no action and no
version. The S7 substrate has since landed and the grant carries both.
A projection omitting them would attest a grant shape that no longer
exists, and — worse — could not distinguish the operation the owner
authorized from a sibling with identical params, which is the whole
defect the S7 slice was built to remove. The v1 projection is
**audit-only** and cannot serve as presence evidence.

**Exact projected fields** — all seventeen `S7ExecutionGrant` members, in
this canonical order:

```
artifact_id, request_id, request_envelope_hash, rendered_text_hash,
action_params_hash, precondition_hash, authority_context_hash, action,
derived_work_class, derived_aggregation_group, nonce, credential_ref,
auth_method, grant_source, consumed_at, ceremony_kind, schema_version
```

The private `_mint_token` is an `InitVar` and is **not** a dataclass field,
so it cannot leak into the projection by construction — the exclusion is
structural rather than a rule someone must remember.

**Encoding:** canonical JSON, sorted keys, the same encoder the rest of
this design uses, wrapped as
`{"schema": <literal>, "fields": {...}}`. `presence_evidence_sha256` is
the SHA-256 of those bytes.

**Reconstruction from the committed row.** Sixteen of the seventeen
fields have a matching column in `s7_authorization_artifacts_v2` — the
MIGRATED table, not the v1 table v19 named, which has no `action` column
at all. `action` is among them: it is a v2 column, and it is the column
the consuming `UPDATE … RETURNING action` matches on and returns. So the
projection remains rebuildable from durable state alone, by
`artifact_id`, long after the in-memory grant is gone.

**The seventeenth field is NOT row-backed, and this is not a defect.**
The row and the grant each carry a `schema_version`, but they are
different KINDS of thing and their versions live in different domains:
the row's is `s7.authorization_artifact.v2`, the grant's is
`s7.execution_grant.v2`. A rule demanding field-by-field equality across
all seventeen would be unsatisfiable — not because anything is wrong,
but because it would be comparing the version of a record with the
version of a permission. The field did not exist when v19 wrote that
rule, so nothing detected the collision.

**Exact joins**, all five required:

1. returned grant ≡ committed row, field by field, for the **sixteen**
   row-backed fields — `action` included, and it is the one that stops a
   sibling operation being attested;
2. the row's `schema_version` ≡ `s7.authorization_artifact.v2`,
   validated — never derived, or the check would assert only that the
   reconstructor can copy a constant;
3. the grant's `schema_version` **DERIVED** deterministically as
   `s7.execution_grant.v2`, never compared to the row's. Deriving it is
   honest precisely because it is not evidence: it records which
   permission shape was reconstructed, and the evidence is joins 1, 2
   and 4;
4. projection hash ≡ `presence_evidence_sha256` in the receipt;
5. `grant.nonce` ≡ the artifact's nonce ≡ the value bound in `params`,
   and `grant.action_params_hash` ≡ the hash of the frozen action/params.

**A gap this exposes, stated rather than glossed:** `user_presence` and
`user_verification` are **not** `S7ExecutionGrant` fields — they exist
only on the artifact and its row. So v13's requirement that both be true
**cannot be checked from the grant**; it must be read from the committed
row. The projection therefore proves *which* authorization was consumed,
and the row proves *a human touched the key*. Two reads, not one, and the
design would have silently checked neither had this not been enumerated.

#### Evidence bytes, exactly (v20)

**Encoder:** `_canonical_wrapper_bytes`
([cuda_migration.py:3131](/home/rohit/maez/scripts/cuda_migration.py#L3131)) —
`sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`,
`allow_nan=False`, UTF-8, **plus a terminating `b"\n"` which PARTICIPATES
in the hash.** Verified in source. "The same encoder the rest of this
design uses" was not precise enough to reproduce a hash.

#### The post-commit row proof (v20)

The projection proves *which* authorization was consumed. The row proves
*a human touched the key*. Frozen post-commit read, **never** a
pre-consumption snapshot:

| check | requirement |
|---|---|
| cardinality | exactly **one** row for `artifact_id` |
| grant fields | exact type and value equality across the **sixteen** row-backed fields (v28); the grant's `schema_version` is derived, not compared — see ITEM 4 |
| presence | `user_presence == 1` **as an integer**, not truthy |
| verification | `user_verification == 1` **as an integer** |
| binding | `consumed_by_request_id == request_id` |
| class | `derived_work_class == "self_modification"` |
| ceremony | `ceremony_kind == "founder_local_webauthn"` |
| **auth method** | `auth_method == "founder_webauthn"` |
| **grant source** | `grant_source == "founder_webauthn"` |
| chronology | `created_at <= consumed_at < expires_at`, compared **only after exact-string canonical timestamp parsing** — never lexicographic string comparison |

`ceremony_kind` alone is **not** sufficient: S7 permits other authority
vocabularies, so a row could carry the founder ceremony kind while its
method or source names a different authority.

**The chronology row is new and closes a live gap:** consumption does not
currently reject a **future-dated `created_at`**, so an artifact could be
stamped ahead of its own consumption and still consume cleanly.

#### The durable-row read seam (v20)

`S7AuthorizationStore` has **no getter**, and `consume_for_execution`
opens its own connection **by pathname**
([:2589](/home/rohit/maez/core/governance/operator_user_boundary.py#L2589)) —
so it would discard any anchored connection, re-resolve the path, and
collapse failures. Frozen:

* a typed `CommittedGrantRow` result carrying the **sixteen** row-backed
  fields (v28 — `action` included) plus the row's own `schema_version`,
  `user_presence`, `user_verification`, `created_at`, `expires_at`,
  `consumed_by_request_id`. The row's version is carried so join 2 can
  VALIDATE it; the grant's version is not a row field and is derived;
* a **post-commit reader** that uses **either** the consuming RW
  connection *strictly after its commit*, **or** a freshly opened RO
  connection after consumption returns. A previously-used RO connection
  may hold a pre-consumption snapshot, so it is explicitly **not**
  permitted — v20 said "the anchored connection" without saying which,
  which is exactly the ambiguity that would have read stale rows;
* consumption routed through a **connection-taking primitive** so it uses
  the verified connection rather than re-opening by name.

#### ITEM 5 — the no-initialization store opener, concrete (v19, corrected v20)

**v19's descriptor-binding claim was unimplementable.** I froze "both
connections proven to address the same file by comparing `st_dev`/`st_ino`
of the opened descriptors". Verified: `sqlite3.Connection` exposes **no
database descriptor at all** — there is nothing to compare. I asserted a
mechanism without checking it existed.

**The actual bridge**, verified working on this Linux-only path — I opened
the live store this way and read both credentials through it:

```
fd = anchored_open(db_path)                      # component walk, predicates
sqlite3.connect(f"file:/proc/self/fd/{fd}?mode=ro", uri=True)   # inspection
sqlite3.connect(f"file:/proc/self/fd/{fd}?mode=rw", uri=True)   # consumption
```

Both connections address the **descriptor we verified**, not a pathname
re-resolved later. `mode=rw`, never `rwc`. The opener is a **context
manager** with exception-safe teardown of both connections and the fd.

`S7AuthorizationStore.__init__` calls `mkdir(parents=True)`,
`executescript(_AUTH_SCHEMA)`, an `ALTER TABLE` migration and `commit()`
([:2413](/home/rohit/maez/core/governance/operator_user_boundary.py#L2413)).
Constructing it **writes and migrates**, so it can never be used at this
seam.

**API:**

```
open_existing_authorization_store(
    *, db_path: Path, expected_uid: int
) -> ExistingAuthorizationStore
```

**Binding rules:**

* the path is reached by **anchored component walk** (A3), never by
  re-resolution;
* **absence refuses** — `presence_store_unavailable`. The opener never
  creates, and there is no `create=` parameter to get wrong;
* file predicates: regular, expected uid, mode `0600`, `st_nlink == 1`;
* **inspection** uses a `mode=ro` connection;
* **consumption** uses a `mode=rw` connection — **never `rwc`**, which
  would create the file and reintroduce exactly the hazard this opener
  exists to remove;
* both connections are opened **through the held descriptor** via
  `file:/proc/self/fd/<fd>?mode=ro|rw`, so they address the verified
  file by construction. ~~Comparing `st_dev`/`st_ino` of the opened
  connection descriptors~~ is **impossible** — `sqlite3.Connection`
  exposes no database FD — and is removed rather than restated;
* the schema is **verified, never migrated** — see below.

#### Schema, integrity and journal posture (v20)

"Expected columns present" proves nothing about primary keys, uniqueness,
types, nullability or defaults. Frozen contract, checked via
`PRAGMA table_info` and `PRAGMA index_list`:

* `artifact_id` is the **primary key**;
* `nonce` carries a **UNIQUE** constraint;
* every column's declared **type** and **NOT NULL** posture matches;
* `ceremony_kind` retains its default;
* `PRAGMA integrity_check` returns `ok`.

**Both tables are verified**, not just one: `s7_authorization_artifacts`
**and** `s7_founder_webauthn_credentials`. The collector reads the second
and the grant proof reads the first; verifying only one leaves the other
trusted on assumption.

**Journal posture is a TWO-STAGE check.** v21 claimed the header proves
`journal_mode=delete`. It does not. Reproduced independently:

| journal mode | header bytes 18/19 |
|---|---|
| `delete` | `(1, 1)` |
| `truncate` | `(1, 1)` |
| `persist` | `(1, 1)` |
| `wal` | `(2, 2)` |

So the header distinguishes **legacy rollback format from WAL** and
nothing finer. `truncate` and `persist` would have passed a check that
claimed to prove `delete`.

The reason for a pre-open stage still stands: `mode=ro` is not
universally side-effect-free — under WAL it can touch sidecars — so
posture cannot be established *only* by opening SQLite. Frozen:

**Stage 1, before SQLite opens anything**, from the held fd:

* the SQLite **magic/header** is well-formed;
* bytes 18/19 are exactly `(1, 1)` — legacy rollback, **not** WAL;
* **no `-journal`, `-wal` or `-shm` sidecar exists**, checked through the
  same anchored directory descriptor as the database itself.

**Stage 2, after the RO connection opens:**

* `PRAGMA journal_mode` returns exactly `"delete"`.

Stage 1 makes stage 2 safe to perform; stage 2 is what actually proves
`delete`.

**Classification:**

| condition | code |
|---|---|
| malformed magic/header | `presence_store_corrupt` |
| header `(2, 2)` | `presence_store_journal_posture` |
| sidecar present, or sidecar predicate/identity failure | `presence_store_journal_posture` |
| `PRAGMA journal_mode != "delete"` | `presence_store_journal_posture` |

A malformed header is **corruption**, not a posture problem, and the two
have different recoveries.

The live store today is `journal_mode=delete`, `0600`, single-linked,
integrity `ok`, with no sidecars (verified). The opener **requires** that
posture rather than happening to encounter it.

**Distinct failure classes**, none collapsed into one another:

| condition | code |
|---|---|
| file absent / unreadable | `presence_store_unavailable` |
| file predicate failure (mode, uid, nlink) | `presence_store_predicate` |
| table missing | `presence_store_table_missing` |
| schema drift (pk, unique, type, nullability, default) | `presence_store_schema_drift` |
| `integrity_check` not ok | `presence_store_corrupt` |
| journal posture not `delete` | `presence_store_journal_posture` |
| fd/connection identity disagreement | `presence_store_identity_mismatch` |

v19 folded several of these together; recovery differs for each, and
"corrupt" and "someone swapped the file" are not the same event.

**Binding REDs:** opening a non-existent path refuses and **creates
nothing** on disk; a `mode=rw` open of a missing file raises rather than
creating; a store **renamed or replaced after the fd is held** is still
read through the original verified inode via `/proc/self/fd`, and the
name-vs-fd recheck detects the swap; and a drifted schema refuses instead
of being altered.

`presence_store_identity_mismatch` is redefined to an **observable**
predicate, since the connection-descriptor comparison it originally
described cannot exist. But v21's form was **symlink-bypassable**:
`os.stat(path)` **follows symlinks and re-resolves the whole path**, so
replacing the database's name with a symlink pointing back at the held
inode makes it agree — the check passes on exactly the substitution A3
forbids.

Reproduced: after renaming the database and symlinking the old name to
the held inode, `os.stat(path)` matched `os.fstat(fd)`, while the
anchored no-follow form saw the symlink and disagreed.

Frozen anchored form:

```python
os.stat(leaf, dir_fd=held_parent_fd, follow_symlinks=False)
```

compared against `os.fstat(fd)` on **type, uid, mode, link count, device
and inode** — not device/inode alone, since a link-count or mode change
is also a loss of the posture we verified.

**Binding RED:** rename the database, replace its old name with a symlink
to the held inode, and require refusal.

#### Grant evidence must be durable canon

`S7ExecutionGrant` is an **in-memory frozen dataclass** with no canonical
serialization and no binding property
([operator_user_boundary.py:2331](/home/rohit/maez/core/governance/operator_user_boundary.py#L2331)).
v13 said the hash would be recomputable "by anyone holding the grant" —
which does not survive a crash, because nobody holds it afterwards.

Frozen:

* a **schema/domain literal** for the projection;
* the **exact projected fields** and their encoding;
* **reconstruction from the committed authorization-store row**, so the
  preimage is durable rather than resident;
* exact **joins** among the returned grant, the committed row, the
  projection hash, and the receipt;
* exclusion of **only** the private `_mint_token`.

#### An in-memory single-use set is not durable replay protection

Beyond the review's findings: `consume_execution_grant_for_action` records
use in a **module-level Python set** behind a `threading.Lock`. That is
**process-local** — a restart forgets it.

This design must therefore not treat the S7 action edge as durable
single-use. Durable single-use for cutover comes from **the exclusive link
on the marker**, which is the linearization point and survives restart.
The S7 edge prevents double-application **within one process**; the marker
prevents it **across all time**. Both are needed and they are not
substitutes.

#### The no-initialization opener, concretely

`S7AuthorizationStore.__init__` calls `mkdir(parents=True)`, `executescript`,
an `ALTER TABLE` migration and `commit()`
([operator_user_boundary.py:2413](/home/rohit/maez/core/governance/operator_user_boundary.py#L2413)).
Constructing it **writes and migrates**. It cannot be used at this seam.

The opener attaches to an **already-existing** store: anchored open,
`mode=ro` for inspection and a write connection only for the consumption
transaction, **no** `executescript`, **no** migration, **no** directory
creation. A missing store refuses `presence_store_unavailable`; it is
never created.

#### R4 RULED: consume S7 BEFORE the cutover link

My position is upheld. A wasted tap on a failed burn is the correct
fail-closed cost; a replayable tap beside a published burn is not.

Frozen sequence at that seam:

1. call `consume_for_execution()` **without its callback** — the consumer
   supplies no continuation, so nothing executes inside S7;
2. require **committed success** and the **exact returned grant**;
3. project and hash the grant into the receipt;
4. *then* the eligibility recheck and the link.

**An existing-store, no-initialization opener is required.** Constructing
`S7AuthorizationStore` creates and migrates schema and commits — the same
hazard as `S7WebAuthnBootstrapStore` in v10, and forbidden for the same
reason. The opener attaches to an existing store or refuses; it never
creates one.

**VOID (v13):** this paragraph proposed a non-voice-seat class. The owner
ruled `self_modification`, which **is** voice-seat guarded, so minting
goes through the guarded store. Retained struck-through rather than
deleted, because it was the load-bearing assumption of v11's S7 section.

#### SUPERSEDED (v13; replaced by v14/v15) — the ordering question

This subsection replaces, rather than silently deletes, v13's stale
ordering. v13 modeled only the cutover nonce and S7 artifact and therefore
called artifact consumption the last pre-burn act. The authoritative
v14/v15 sequence above corrected that account: there are **two S7
consumptions** around receipt staging.

1. `consume_for_execution()` consumes the **S7 artifact early**, before
   receipt encoding, and mints the grant whose canonical hash the receipt
   carries.
2. `consume_execution_grant_for_action(...)` consumes the **action-edge
   grant use as the last pre-burn act**, applying that exact grant to the
   cutover action.

The cutover nonce is then spent by the exclusive link. A failure after the
early artifact consumption but before the link leaves the tap spent and
the cutover nonce reusable; the owner re-taps and nothing was burned.
Consuming the artifact only after the link remains unsafe because a
mutation would have proceeded beside a replayable tap.

#### The deliberate pre-burn S7 transitions, named

Both consumptions are deliberate one-use state transitions on a path this
design otherwise forbids writes on. The first consumes the artifact early
and mints the grant; the second consumes the action-edge grant use as the
last pre-burn act. Their failures are pre-burn refusals.

This is not in tension with v10's ruling: **inspection** remains read-only
(the collector never instantiates the bootstrap store, never migrates,
never commits). The superseded v13 claim of exactly one write to exactly
one row as the last pre-burn act no longer describes the authoritative
sequence.

**R4 — RULED (v13), retained historically.** ~~Carried for review: is a
spent tap on a failed burn the acceptable cost, or should the artifact
instead be consumed *inside* `publish_and_validate_burn()` after the
link, accepting a replay window
in exchange for never wasting a tap? My position is firmly the former —
a replayable tap next to a published burn is the worse failure by a wide
margin — but the tradeoff is real and the owner may feel the re-tap cost
differently.

#### If the state-based rule is honored: what procedural would have meant

Any process running as the owner's uid can invoke the ceremony while an
authorization is valid. The nonce, the named window, and the chronology
bound the blast radius; **they do not authenticate a human.** No sentence
in this design, in any commit message, or in any receipt may describe
this state as authenticated presence.

#### HISTORICAL (v9, superseded) — "the tap slot, unarmed"

> **Everything in this subsection is FALSE as of v10-v13** and is retained
> only to show what the withdrawn v9 ruling rested on. The tap is ARMED,
> two `bonded_user` credentials are enrolled, and there is no procedural
> fallback. Do not read any sentence below as current.

The owner's June authority model
([2026-06-28-authority-model-provenance-firewall-design.md](2026-06-28-authority-model-provenance-firewall-design.md))
places body/code/**model** changes behind a **YubiKey tap**, and names
model swaps the spiciest case in that tier. A CUDA cutover changes the
brain's runtime, so it plausibly sits there. That model is **design-only**
— verified: the `s7_founder_webauthn_credentials` table has never been
provisioned in any database, and S7 slice 1 (enrollment + UX) is unbuilt.
There is currently nothing to tap into.

So the consumer carries the refusal point now and the gate arrives later:

| code | when it fires |
|---|---|
| `owner_presence_unattested` | a founder credential exists and no valid assertion accompanies the invocation |

**Arming is a state, not a flag.** The presence check is required **if and
only if at least one founder credential is enrolled**. There is no
enable/disable switch, deliberately:

* you cannot enrol a key and forget to turn the gate on;
* you cannot turn the gate off without destroying credentials, which is
  itself an owner-visible act;
* the unarmed state is not a configuration choice anyone made — it is
  simply the absence of any key to check against.

Placement: with the other pre-burn checks. A failure is **pre-burn** —
nonce reusable, **zero** executor calls — because a mutation nobody
attested must not consume the authorization.

**REDs:** with a credential present and no valid assertion → refuse,
nonce reusable, zero executor calls. With none present → proceed, and the
outcome records `presence: procedural`.

#### Ruling: presence belongs in the DURABLE receipt (v10)

I proposed recording presence mode on the step-2 outcome surface to avoid
moving step-1 canon. **Ruled against, correctly.** An executor can crash
or partially fail before any outcome is published; the **burn marker is
the one artifact guaranteed durable before mutation**. Outcome-only
recording therefore loses exactly the fact that matters most after a
partial failure: *which authority mode permitted this burn.*

I optimized for not disturbing canon and traded away the durability
property the record exists for.

**`CutoverConsumptionReceipt` → v2, now.** No v1 cutover-consumption
artifact exists under the bench root, so this is the cheapest safe moment
— the field is added before any durable artifact can be orphaned. Active
family count stays **26**: this is a *replacement*, not an addition.

Two new fields, both inside the binding:

| field | rule |
|---|---|
| `presence_mode` | **cutover: `founder_webauthn` ONLY.** `procedural` remains a receipt-type value for other callers and is unreachable from any cutover path (Part 3 ruling) |
| `presence_evidence_sha256` | **mandatory** — the canonical **grant-projection** hash (item 4), and specifically the **v2, seventeen-field** projection (v28). A v1 projection hash is NOT acceptable presence evidence: it omits the `action`, so it attests that *an* authorization was consumed without attesting *which*, which is exactly the substitution S7 action-binding exists to prevent. ~~the authorization-artifact hash~~ is superseded: that artifact has no canonical binding and its row mutates at consumption |

The second field is the point. A bare `founder_webauthn` string is
**descriptive, not proof** — the same error as A2, where a self-chosen
hash was mistaken for evidence. The receipt must cite the artifact that
attested, not merely name the mode.

#### Ruling: the presence collector is read-only and fails closed (v10)

**`S7WebAuthnBootstrapStore` must never be instantiated by the consumer.**
Verified: its constructor
([s7_webauthn_bootstrap.py:251](/home/rohit/maez/core/governance/s7_webauthn_bootstrap.py#L251))
calls `mkdir(parents=True)`, `chmod(0o700)`, `_init_db()` — which runs
`executescript`, an `INSERT`, a column migration and a `commit` — and
`_ensure_audit_file()`. Constructing it **writes**. Doing that on the
pre-burn path would violate the no-mutation boundary at the exact edge
this design exists to protect, and would do it while merely *asking*
whether anyone is present.

Frozen instead: an **anchored, SQLite read-only** collector
(`mode=ro` URI, anchored open per A3, no schema initialization, no
migration, no write of any kind).

**For cutover, zero enabled rows REFUSES** (`presence_no_usable_credential`,
Part 3). ~~Only a successful canonical query proving zero rows may yield
`procedural`~~ described the collector before the no-fallback ruling; the
`procedural` column below is retained only for other callers of the
collector and is **unreachable from cutover**. Every failure condition
refuses:

| condition | verdict |
|---|---|
| query succeeds, zero enabled rows | **refuse `presence_no_usable_credential`** — ~~`procedural`~~ is unreachable for cutover (Part 3) |
| query succeeds, ≥1 enabled row, valid assertion | `founder_webauthn` |
| query succeeds, ≥1 enabled row, no valid assertion | refuse `owner_presence_unattested` |
| database missing or unreadable | refuse `presence_store_unavailable` |
| table missing | refuse `presence_store_table_missing` (v20 split this out) |
| schema drift | refuse `presence_store_schema_drift` |
| corruption | refuse `presence_store_corrupt` |
| invalid `record_hash` on any row | refuse `presence_record_invalid` |

None of these may masquerade as zero enrollment. "I could not read the
key store" and "there are no keys" are opposite facts, and collapsing
them is precisely how I got here.

### Historical: the reasoning before the ruling

Review agrees the single-command topology is technically stronger, because
it makes validation → burn → first mutation structurally contiguous. It
also correctly declines to amend the covenant on Rohit's behalf. So does
this design.

**HISTORICAL (superseded v13):** ~~until R1 is ruled, step 2 stops at
`prepare()`~~. R1 is ruled in four parts; the burn is in scope, gated by
a required founder tap. The burn, publication and `begin()` are specified
here; nothing production-reachable invokes them, and no burn REDs are
written.

If Rohit **ratifies**, two corrections to how I first described it:

1. It is a **single authorization-bound invocation**, not an "indivisible
   act". My word was wrong and it hid something: the systemd operations
   are sequential and **can partially fail**, and a partial failure must
   enter the frozen recovery path — which "indivisible" would have
   quietly denied existed.
2. **"No agent or daemon can initiate it" needs an enforceable
   owner-presence boundary.** A CLI *intended* for owner use is not one:
   any same-UID process can invoke it while the authorization is valid.
   Either such a boundary is added, or the design states honestly that
   **owner invocation is procedural, not technically authenticated** —
   the nonce and named window bound the blast radius; they do not prove a
   human typed anything.

I prefer stating (2) honestly over claiming a guarantee the process
boundary cannot deliver.

If Rohit **refuses**, the burn moves into the later executor act, step 2's
claim narrows to reconstruction plus `prepare()`, and burn/mutation
adjacency is never proven here. Coherent — just weaker, and it must then
be said plainly rather than implied.

---

## A6. AST *plus* runtime

The property that matters is not adjacency but *the marker was published
before the executor ran*, and syntax cannot see that.

**AST proves:** the executor method is **pre-bound to a local name before
the burn**; the `publish_and_validate_burn()` call and `begin()` are
adjacent top-level statements; exactly one syntactic executor call; no
intervening branch or handler; and **after `publish_and_validate_burn()`
returns**, no attribute access, subscript, or call of any kind is
evaluated other than that one local call. The boundary is the helper's
return, not the link — the post-link durability and revalidation steps
live inside the helper by design. Also: the production
entrypoint takes no injection parameters, and production
`BenchEvidenceBundle(...)` construction occurs at **exactly the two
allowlisted sites and no third** — the frozen stage-1 constructor and the
sole stage-2 seam (A1). v6 replaced the global ban in A1 but left it
standing here; the two statements contradicted each other and this is the
surviving one.

**Runtime proves:** a complete, published, fsync-confirmed marker exists
when the double runs, and exactly one call.

| failure class | executor calls | outcome |
|---|---|---|
| any pre-publication failure | **zero** | reusable |
| post-publication, pre-`begin()` (dir fsync, identity, chain recheck, **eligibility recheck**, `uncertain`) | **zero** | spent, not eligible |
| executor raises | **exactly one** | spent, terminal |
| executor returns invalid type | **exactly one** | spent, terminal |

**Neither certifies live ordering.** The later real-executor slice must
separately prove the production caller graph and first-mutation ordering.
Step 2 cannot certify those while its target is a double, and will not
claim to.

---

## A7. Total failure table — exact codes

Families are not closed sets. Every concrete emitted code is assigned a
side of the linearization point. Two R8-retained tuple-only codes are also
listed and explicitly marked as having no producer:

| # | failure | side | nonce | executor | exact code |
|---|---|---|---|---|---|
| 1 | root component walk | pre | reusable | no | `root_walk_failed` |
| 2 | root not a directory | pre | reusable | no | `root_not_directory` |
| 3 | root uid mismatch | pre | reusable | no | `root_ownership` |
| 4 | root mode not 0700 | pre | reusable | no | `root_mode` |
| 5 | named-chain disagreement | pre | reusable | no | `root_moved` |
| 6 | `markers/` absent | pre | reusable | no | `marker_dir_absent` |
| 7 | `markers/` predicates | pre | reusable | no | `marker_dir_predicate` |
| 8 | authorization unreadable | pre | reusable | no | `authorization_missing` |
| 9 | authorization predicates | pre | reusable | no | `authorization_predicate` |
| 10 | authorization not canonical | pre | reusable | no | `authorization_noncanonical` |
| 11 | authorization wrong type | pre | reusable | no | `authorization_wrong_type` |
| 12 | authorization expired | pre | reusable | no | `authorization_expired` |
| 13 | boot-id mismatch | pre | reusable | no | `authorization_boot_mismatch` |
| 14 | owner mismatch | pre | reusable | no | `authorization_owner_mismatch` |
| 15 | receipt candidate unreadable | pre | reusable | no | `receipt_missing` |
| 16 | receipt candidate predicates | pre | reusable | no | `receipt_predicate` |
| 17 | receipt candidate not canonical | pre | reusable | no | `receipt_noncanonical` |
| 18 | receipt candidate wrong type | pre | reusable | no | `receipt_wrong_type` |
| 19 | a `Stage2InputPaths` member unreadable | pre | reusable | no | `stage2_input_missing` |
| 20 | a `Stage2InputPaths` member predicates | pre | reusable | no | `stage2_input_predicate` |
| 21 | stage-2 reconstruction failed | pre | reusable | no | `permit_unreconstructible` |
| 22 | regenerated bytes ≠ disk bytes | pre | reusable | no | `permit_unverified` |
| 23 | command admission unreadable/invalid | pre | reusable | no | `command_admission_invalid` |
| 24 | command completion unreadable/invalid | pre | reusable | no | `command_completion_invalid` |
| 25 | completion does not cite the receipt hash | pre | reusable | no | `command_artifact_mismatch` |
| 26 | admission↔completion chain mismatch | pre | reusable | no | `command_chain_mismatch` |
| 27 | any S-join | pre | reusable | no | `join_mismatch` |
| 28 | chronology | pre | reusable | no | `chronology_violation` |
| 29 | clock or boot read | pre | reusable | no | `edge_state_unreadable` |
| 29a1 | consultation request binding invalid or ask unavailable | pre | reusable | **zero** | `consultation_unavailable` |
| 29a2 | response absent, wrong type, oversized, or not UTF-8 | pre | reusable | **zero** | `response_unreadable` |
| 29a3 | consultation explicitly withdrawn | pre | reusable | **zero** | `consultation_withdrawn` |
| 29a4 | consultation evidence cannot be durably persisted | pre | reusable | **zero** | `bundle_unreservable` |
| 29a5 | RETAINED IN THE FROZEN TUPLE WITH NO PRODUCER UNDER R8 | n/a | n/a | n/a | `semantic_reader_failed` |
| 29a6 | RETAINED IN THE FROZEN TUPLE WITH NO PRODUCER UNDER R8 | n/a | n/a | n/a | `objection_recorded` |
| 30 | bound `prepare()` returns a value that is not `PreparedCutover` | pre | reusable | no | `preparation_failed` |
| 30a | no runtime preparer is bound | pre | reusable | no | `preparation_unavailable` |
| 29b | founder credential enrolled, no valid assertion | pre | reusable | **zero** | `owner_presence_unattested` |
| 29c | presence store missing/unreadable | pre | reusable | **zero** | `presence_store_unavailable` |
| 29d | presence store schema drift | pre | reusable | **zero** | `presence_store_schema_drift` |
| 29e | presence store corrupt | pre | reusable | **zero** | `presence_store_corrupt` |
| 29e2 | presence store file predicate (mode/uid/nlink) | pre | reusable | **zero** | `presence_store_predicate` |
| 29e3 | presence store table missing | pre | reusable | **zero** | `presence_store_table_missing` |
| 29e4 | journal posture not `delete` | pre | reusable | **zero** | `presence_store_journal_posture` |
| 29e5 | name no longer refers to the verified inode | pre | reusable | **zero** | `presence_store_identity_mismatch` |
| 29f | credential `record_hash` invalid | pre | reusable | **zero** | `presence_record_invalid` |
| 29g | S7 artifact missing/expired/already consumed | pre | reusable | **zero** | `presence_assertion_invalid` |
| 29g2 | zero usable credentials (no fallback exists) | pre | reusable | **zero** | `presence_no_usable_credential` |
| 29g3 | credential lacks `bonded_user` or is disabled | pre | reusable | **zero** | `presence_credential_unscoped` |
| 29g4 | S7 store absent (opener must not create) | pre | reusable | **zero** | `presence_store_unavailable` |
| 29g5 | guarded mint failed / invalid artifact | pre | reusable | **zero** | `presence_mint_failed` |
| 29g6 | `consume_for_execution` did not commit | pre | reusable | **zero** | `presence_consumption_failed` |
| 29g7 | grant projection unreconstructible from the committed row — v28: the **complete v2** reconstruction, meaning any of the sixteen row-backed fields missing or unequal, OR the row's `schema_version` not `s7.authorization_artifact.v2`. A partial reconstruction is a FAILURE, not a degraded success | pre | reusable | **zero** | `presence_grant_unprojectable` |
| 29g8 | action-edge consumption returned false | pre | reusable | **zero** | `presence_action_unauthorized` |
| 29h | S7 artifact does not bind the cutover nonce | pre | reusable | **zero** | `presence_binding_mismatch` |
| 29i | `user_presence` or `user_verification` false | pre | reusable | **zero** | `presence_not_verified` |
| 29j | S7 artifact consumption write failed | pre | reusable | **zero** | `presence_consumption_failed` |
| 30b | receipt construct/encode/round-trip | pre | reusable | **zero** | `burn_receipt_unencodable` |
| 34b | expiry recheck immediately before link | pre | reusable | **zero** | `authorization_expired_pre_link` |
| 34c | clock regressed (`recheck` < `decided_at`) | pre | reusable | **zero** | `clock_regression` |
| 31 | O_TMPFILE creation | pre | reusable | no | `burn_unstaged` |
| 32 | short write | pre | reusable | no | `burn_write_incomplete` |
| 33 | staged content validation | pre | reusable | no | `burn_content_invalid` |
| 34 | file fsync | pre | reusable | no | `burn_unstaged_fsync` |
| 35 | link collision (EEXIST) | at | already spent | no | `authorization_consumed` |
| 36 | link other error, leaf verified absent | pre | reusable | no | `burn_unstaged_link` |
| 37 | link outcome unresolvable | uncertain | **treat as spent** | no | `publication_uncertain` |
| 38 | marker directory fsync | post | spent | no | `burn_unrecorded_fsync` |
| 39 | published identity revalidation | post | spent | no | `burn_unrecorded_identity` |
| 40 | post-publication chain recheck | post | spent | no | `root_moved_post_publication` |
| 40b | expiry crossed before `begin()` | post | **spent** | **zero** | `authorization_expired_pre_begin` |
| 40c | clock regressed before `begin()` | post | **spent** | **zero** | `clock_regression_pre_begin` |
| 41 | executor raises | post | spent | **one** | `executor_failed` |
| 42 | executor returns invalid type | post | spent | **one** | `executor_contract` |
| 43 | unexpected internal, pre-link | pre | reusable | **zero** | `consumer_internal_pre` |
| 44 | unexpected internal, post-link **before** `begin()` | post | spent | **zero** | `consumer_internal_post_pre_begin` |
| 45 | unexpected internal, **inside/after** `begin()` | post | spent | **one** | `consumer_internal_executor` |

`preparation_failed` is intentionally narrower than its name suggests: it
fires **only** when a bound preparer returns the wrong type. Arbitrary
exceptions raised during preparation are not mapped to that code.

**OWED GAP:** preparation currently has no runtime positive-control
fixture; its present test coverage is structural. This reconciliation does
not manufacture one.

Rows 44–45 split v3's row 38, which left executor state "unknown". An
unknown executor state is exactly the thing a terminal refusal must not
report, because recovery differs entirely between "nothing ran" and
"something may have run". The split is decidable at runtime: the consumer
knows whether it reached the call.

A catch-all that **degrades** remains forbidden. One that classifies which
side of the boundary it occurred on and refuses terminally is the opposite
— it ensures an unanticipated failure cannot be mistaken for a pre-burn
one.

**Cleanup never unlinks a published marker** — not on any failure path,
not on `publication_uncertain`, not on `consumer_internal_*`. A published
marker is the single-use record; removing it restores replay. Recovery is
always a fresh owner-typed authorization with a fresh nonce.

All refusals are content-light: no paths, no prompt or response text, no
environment values, no tracebacks.

---

## What step 2 does NOT change

* No mutating `systemctl` in the driver.
* No production unit, override, model pointer, or venv file.
* `model_state.json` stays an owner-typed command after a durable
  promotion receipt.
* Cutover remains **forbidden** at `bench_passed`.

## Scope, restated

Step 2 delivers the sole production stage-2 assembly seam (2A) and the
reconstruction + `prepare()` consumer (2B). It proves the **consumer
primitive** and the **final interface** against a double. It does **not**
prove live ordering. ~~It does not expose a production consumer
entrypoint while R1 is open~~ — R1 is RULED in four parts (v11-v13); the
consumer is in scope, gated by a required founder tap.

## Carried

* **R1 — RULED in four parts (v11-v13):** tap required; existing founder
  credentials arm it; no procedural fallback; work class
  `self_modification`. Historical question text follows.
* ~~**R1 — OPEN, owner-only.** Does an owner-typed ceremony satisfy "the
  owner types every mutating command", and if so, is procedural (not
  technically authenticated) owner presence acceptable?
* **R2 — RULED.** Reconstruct, do not sign.
* **R3 — RULED.** Absorb stage 2 narrowly; step 5 amended to stages 3–5.
