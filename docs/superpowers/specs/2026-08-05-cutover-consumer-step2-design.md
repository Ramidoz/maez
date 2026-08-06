# Cutover slice step 2 — stage-2 producer + consumer primitive, design v12

Status: **R1 RULED 2026-08-06 on true state — the tap is REQUIRED.
v11 binds the S7 path; that binding needs a review round before REDs.**

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
| **v12** | **arming authority ruled EXPLICITLY by the owner; v11's inferred scope replaced with a recorded one** |

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
| completion | the single owner-supplied relative locator |
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

### The completion locator (v5)

Command records carry **runtime-allocated ordinals**, so their filenames
cannot be constants known before the producer runs. The v4 authority
(then called `Stage2ArtifactPaths`, superseded by `Stage2InputPaths`
above) therefore could not name them as literals, and v4 was wrong to
imply it could.

Resolution: the consumer accepts **exactly one owner-supplied relative
completion locator** under the canonical root.

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
auth.issued_at
  <= boot witness
  <= command admission
  <= receipt timestamp == stage-2 bundle timestamp
  <= command completion
  <= consumer now
  < auth.expires_at
```

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

```
decided_at = clock()                       # the burn-decision moment
receipt = CutoverConsumptionReceipt(...)   # complete, consumed_at = decided_at
payload = canonical_encode(receipt)        # canonical bytes
typed_roundtrip(payload)                   # decode back and compare — pre-burn
begin = prepared.begin                     # METHOD PRE-BOUND, pre-burn
O_TMPFILE                                  # no name exists yet
write_all + validate                       # short writes handled, content verified
fsync(file)                                # STILL PRE-BURN: failure leaves nonce reusable

    publish_and_validate_burn():           # ONE closed helper
        recheck expiry at clock()          #   LAST pre-burn act
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

### R1 — RULED IN TWO PARTS

**Part 1 — is a tap required?** Owner, 2026-08-06: *"Yes it is Maez's
brain we are changing."* The cutover is a tier-2 body/code/**model**
change and requires a founder key tap.

**Part 2 — which authority arms it?** Owner, 2026-08-06, asked
explicitly: **the existing founder credentials arm cutover.** Any enrolled
founder credential authorizes a cutover, including the backup and any
enrolled later.

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
requires one**. `procedural` remains a defined mode in the receipt
vocabulary, but it is **unreachable on this machine** while any credential
is enrolled — and that is the correct relationship between the two.

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
| work class | a **new non-voice-seat** class for cutover execution |
| binding | `action_params_hash` binds the **cutover authorization's nonce**, so a tap for one cutover cannot authorize another |
| presence | `user_presence` **true** |
| verification | `user_verification` **true** |
| freshness | not expired at the pre-link recheck |
| single use | `consumed_at` is null when verified |
| credential | `credential_ref` names an **enabled** founder credential |

`presence_mode` becomes `founder_webauthn` and
`presence_evidence_sha256` cites the canonical hash of that artifact —
the proof, not the label.

Note the work class must be **non-voice-seat**: voice-seat classes are
forced through the guarded store with source-bundle validation
([s7_guarded_execution.py:2291](/home/rohit/maez/core/governance/s7_guarded_execution.py#L2291)).
Cutover execution is founder custody, not voice seat. **Flagged for
review** — if review reads cutover as voice-seat-adjacent, the guarded
path applies instead and this section changes.

#### TWO single-use resources — the new ordering question

This is the substantive new seam, and it did not exist before the ruling.
There are now **two** one-use tokens:

1. the **cutover nonce**, spent by the exclusive link;
2. the **S7 artifact**, spent by `consumed_at`.

Their order decides what a partial failure means:

| order | failure between them | verdict |
|---|---|---|
| consume S7 **after** the link | burn published, tap still unconsumed | **UNSAFE** — a mutation proceeded on a replayable tap |
| consume S7 **before** the link | tap spent, cutover nonce reusable | **SAFE** — owner re-taps; nothing mutated |

**Frozen: consume the S7 artifact as the LAST pre-burn act**, immediately
before the eligibility recheck and the link. The failure mode is a spent
tap on a burn that never happened — an inconvenience, requiring a fresh
tap — and never a mutation authorized by a tap that could be replayed.

#### The one deliberate pre-burn write, named

Consuming the artifact is a **write**, on a path this design otherwise
forbids writes on. That is not an oversight and it is not in tension with
v10's ruling: **inspection** is read-only (the collector never
instantiates the bootstrap store, never migrates, never commits);
**consumption** is a deliberate one-use state transition that must happen
before the thing it authorizes.

It is called out explicitly here because "no mutation before the burn" is
a rule this design has enforced for eleven revisions, and an exception
that is not named is an exception that later gets forgotten. The
exception is exactly one write, to exactly one row, as the last pre-burn
act, and its failure is a pre-burn refusal.

**Carried for review (R4):** is a spent tap on a failed burn the
acceptable cost, or should the artifact instead be consumed *inside*
`publish_and_validate_burn()` after the link, accepting a replay window
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

#### The tap slot — specified now, unarmed now

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
| `presence_mode` | exact closed value: `procedural` \| `founder_webauthn` |
| `presence_evidence_sha256` | `None` **iff** `procedural`; the canonical S7 authorization-artifact hash when WebAuthn-attested |

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

**Only a successful canonical query proving zero rows may yield
`procedural`.** Every other condition refuses:

| condition | verdict |
|---|---|
| query succeeds, zero enabled rows | `procedural` |
| query succeeds, ≥1 enabled row, valid assertion | `founder_webauthn` |
| query succeeds, ≥1 enabled row, no valid assertion | refuse `owner_presence_unattested` |
| database missing or unreadable | refuse `presence_store_unavailable` |
| table missing | refuse `presence_store_unavailable` |
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

**Until R1 is ruled, step 2 stops at `prepare()` and exposes NO production
consumer entrypoint.** The burn, publication and `begin()` are specified
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

Families are not closed sets. Every concrete emitted code, each assigned a
side of the linearization point:

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
| 30 | `prepare()` failure | pre | reusable | no | `preparation_failed` |
| 29b | founder credential enrolled, no valid assertion | pre | reusable | **zero** | `owner_presence_unattested` |
| 29c | presence store missing/unreadable | pre | reusable | **zero** | `presence_store_unavailable` |
| 29d | presence store schema drift | pre | reusable | **zero** | `presence_store_schema_drift` |
| 29e | presence store corrupt | pre | reusable | **zero** | `presence_store_corrupt` |
| 29f | credential `record_hash` invalid | pre | reusable | **zero** | `presence_record_invalid` |
| 29g | S7 artifact missing/expired/already consumed | pre | reusable | **zero** | `presence_assertion_invalid` |
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
prove live ordering, and it does not expose a production consumer
entrypoint while R1 is open.

## Carried

* **R1 — OPEN, owner-only.** Does an owner-typed ceremony satisfy "the
  owner types every mutating command", and if so, is procedural (not
  technically authenticated) owner presence acceptable?
* **R2 — RULED.** Reconstruct, do not sign.
* **R3 — RULED.** Absorb stage 2 narrowly; step 5 amended to stages 3–5.
