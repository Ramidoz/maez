# Cutover slice step 2 — the consumer primitive, design v2

Status: **DRAFT — awaiting ratification. No REDs, no code until ratified.**

Parent: `docs/superpowers/specs/2026-08-04-cutover-bundle-antibypass-design.md`
(step 1, merged at `348332b`).

v1 → v2: cross-lane review found v1 overclaiming five security properties
and under-specifying a sixth. Every one is conceded below. The three v1
"open questions" are now answered — two against my stated position.

---

## The central falsifiable claim

> No cutover mutation is reachable except through a consumer that
> revalidates the real stage-2 receipt and authorization, atomically burns
> the nonce at the last no-mutation point, durably records consumption,
> then hands control directly to the closed mutation executor.

Unchanged. What changed is the set of things v1 claimed to have proven.

## What v1 got wrong

| v1 claim | reality |
|---|---|
| the receipt's own hashes authenticate it | they do not — see A1 |
| a required `root` parameter is anchoring | it is an override — see A2 |
| burn and record are one act | `O_EXCL`→write→fsync publishes a name before content — see A3 |
| `Callable[[Doc], Outcome]` is a closed executor | it forces post-burn preparation — see A4 |
| AST assertion suffices for adjacency | syntax cannot prove the marker was published — see A5 |
| the refusal list was closed | it classified maybe half the failures — see A6 |

---

## A1. The stage-2 bundle must be reverified (Q1 — ruled AGAINST my position)

I argued the consumer should not hold the bundle. That was wrong, and the
reason is a comment I wrote myself at
[cuda_migration.py:1260](/home/rohit/maez/scripts/cuda_migration.py#L1260):
the receipt's `binding_sha256` **is** its claimed `bundle_binding_sha256`.
It does not authenticate the receipt's contents.

So the two hashes v1 leaned on prove nothing about provenance:

* `file_sha256` identifies the bytes the consumer read — bytes the caller
  supplied. It answers "which bytes", never "whose".
* `binding_sha256` is a field the forger chooses, and canonical decode
  only checks it equals the field it was copied from. Self-consistent by
  construction.

A canonically-encoded forged receipt, paired with a **genuine**
authorization, therefore impersonates a scorer-issued permit. Under the
current evidence model the only trusted expected value is the one
recomputed from the real stage-2 bundle. The consumer must carry or
reconstruct it.

I am recording this as a design error of the same family as the step-1
`bundle_binding` gap: I treated a hash as evidence because it was
expensive to compute, without asking who chose it.

**Binding RED:** a canonical forged receipt plus a genuine authorization
refuses; only the real bundle/receipt pair passes.

**Consequence for scope:** the consumer's inputs now include the stage-2
bundle, so S3's join set gains the step-1 projection join. This makes the
consumer heavier than v1 imagined. That is the cost of the permit not
being independently verifiable, and it is the honest cost. An
independently verifiable permit — a signed or MAC'd receipt — would remove
it, and is noted as future work rather than smuggled in here.

## A2. Anchoring, properly (concedes the override)

A required parameter is still an override: it makes arbitrary roots
reachable by construction.

**Production entrypoint hard-binds** the canonical bench root, the live
clock, the boot-id source, and the executor. No parameter reaches it.
Injection exists only behind a seam that is structurally test-only —
a private constructor the production path does not call, asserted by the
same AST instrument as A5.

The filesystem discipline v1 got wrong:

* **`O_NOFOLLOW` protects only the final component.** Every component of
  every path — absolute and relative — is walked with held directory
  descriptors. The driver already implements this:
  `_relative_parts` and `_check_directory_fd`
  ([cuda_bench_driver.py:237](/home/rohit/maez/scripts/cuda_bench_driver.py#L237)).
  Step 2 reuses it. v1 cited `_anchored_exclusive_write`, which is the
  weaker helper; that citation is withdrawn.
* **A second `fstat` on a held fd cannot detect rename or replacement** —
  it re-reads the same inode and always agrees. Identity verification
  requires reopening the *named chain* and comparing it against the held
  capability. Agreement means the name still refers to what we hold;
  disagreement is `root_moved`.
* **Read predicates**, all required: regular file, owner-owned, mode
  `0600`, `st_nlink == 1`, size within a fixed bound, and stable across
  the read (size and inode identical before and after).
* **`auth.owner`** joins to the frozen expected owner identity. v1 omitted
  this entirely — an authorization naming any owner was accepted.
* **Marker names derive only from the already-validated nonce**, after
  validation, never from any other caller-influenced value.

## A3. The burn sequence (Q3 — ruled, and v1's "one act" retracted)

v1 claimed `O_EXCL` create → write → fsync was a single act with no
unrecorded window. It is not: `O_EXCL` publishes the final name *before*
the contents exist. v1 then admitted a truncated marker could survive,
which contradicts its own claim. Conceded.

Frozen sequence — the repository already implements this pattern at
[`_open_anonymous_file`](/home/rohit/maez/scripts/cuda_bench_driver.py#L347)
and
[`_publish_anonymous_file`](/home/rohit/maez/scripts/cuda_bench_driver.py#L375):

```
O_TMPFILE                       # no name exists yet
write_all + validate            # short writes handled, content verified
fsync(file)                     # STILL PRE-BURN: failure leaves nonce reusable
------------------------------- last no-mutation point
exclusive atomic link           # THE burn — the linearization point
fsync(marker directory)         # durability of the publication
revalidate published identity   # nlink, size, inode match what we linked
------------------------------- authorization is spent
prepared.begin()                # exactly one call
```

The linearization point is the `link`, not the create. Before it, no name
exists and every failure is reusable. After it, the nonce is spent.

**Replay vs evidence are separated.** *Any* object at the final nonce name
blocks replay — that is the single-use guarantee and it must be
maximally permissive about what it will treat as blocking. But only the
**exact canonical completed receipt** is admissible as downstream
evidence. Garbage, a truncated file, or an abnormal object means
"**spent, receipt unavailable**" — never evidence, and never a reason to
permit reuse. v1 conflated these into one artifact serving both roles.

**Q3 ruled: fail closed after publication.** A directory-fsync failure
*after* the exclusive link spends the authorization, calls no executor,
and requires owner-audited recovery plus a fresh authorization. A
file-fsync failure occurs *before* publication and leaves the nonce
reusable. The boundary is the link, and that is what makes the fail-closed
cost bounded rather than arbitrary — a transient disk error during the
tmpfile phase costs nothing.

## A4. The executor is a two-phase capability, not a callable

`Callable[[CutoverAuthorizationDoc], CutoverOutcome]` carries no pinned
payloads, no exact argv, no recovery capabilities, no prevalidated
resources. The real executor would therefore have to resolve all of that
*after* the burn — or hide it in a closure, which is the same thing with
better manners. v1's rule 6 ("nothing fallible after the burn") was
unachievable against v1's own interface.

Frozen:

```
prepare(validated authority, validated evidence) -> PreparedCutover
publish burn
prepared.begin()
```

`PreparedCutover` holds **only already-pinned resources**: exact argv
vectors, opened descriptors for recovery artifacts, resolved and verified
unit identities, and the precomputed operation sequence. `begin()`
performs no resolution, no lookup, no allocation that can fail for
preparation reasons. Everything fallible lives in `prepare()`, which runs
pre-burn and may refuse freely.

### The covenant reconciliation this forces

The standing covenant is that **the owner types every mutating command**.
A closed executor that performs the mutation appears to contradict it,
and v1 dodged this by leaving the mutation an unrelated manual
continuation — which would make burn-immediately-before-mutation
unprovable, exactly as review says.

The reconciliation I propose, and which needs **explicit ratification
because it is a covenant-level amendment, not a design detail**:

> The owner-typed act is the invocation of the cutover ceremony itself.
> The owner types one command; that command validates, burns, and mutates
> as one indivisible act it cannot decompose.

This preserves what the covenant protects — no agent, no daemon, and no
background process initiates a mutation; a human decides, at a named
window, with a nonce they authorized. It changes what the covenant
*counts* as the typed command: the ceremony, rather than each systemd
verb inside it.

I am not treating this as settled. If it is refused, then step 2 must
stop at `prepare()` and the burn moves into the later act with the
executor — which is coherent, but means the burn/mutation adjacency is
never proven here and the claim must be narrowed accordingly. **That
choice is the owner's, not mine.**

## A5. AST *plus* runtime (Q2 — ruled AGAINST my position)

I argued the adjacency property is syntactic. It is — but the property
that matters is not adjacency, it is *the marker was published before the
executor ran*, and syntax cannot see that.

**AST proves:** adjacent top-level burn and `prepared.begin()`; exactly
one syntactic executor call; no intervening branch or handler; the exact
prebound argument, with no call, property access, or subscript evaluated
after the burn.

**Runtime REDs prove:** a complete, published, fsync-confirmed marker
exists when the double runs; exactly one call; and **no call at all** on
every pre-publication and post-publication failure path.

**Neither certifies live ordering.** The later real-executor slice must
separately prove the production caller graph and first-mutation ordering.
Step 2 cannot certify those while its target is a double, and will not
claim to.

## A6. Total failure table

v1's list classified roughly half the real failure modes and contradicted
itself on executor exceptions. Total table, every row assigned a side of
the linearization point:

| # | failure | side | nonce | executor | refusal |
|---|---|---|---|---|---|
| 1 | root walk / identity / predicates | pre | reusable | no | `root_*` |
| 2 | authorization read / decode / type | pre | reusable | no | `authorization_*` |
| 3 | stage-2 receipt read / decode / type | pre | reusable | no | `receipt_*` |
| 4 | bundle reconstruction or projection join | pre | reusable | no | `permit_unverified` |
| 5 | any join in S3 | pre | reusable | no | `join_mismatch` |
| 6 | chronology | pre | reusable | no | `chronology_violation` |
| 7 | clock or boot-id read | pre | reusable | no | `edge_state_unreadable` |
| 8 | `prepare()` failure | pre | reusable | no | `preparation_failed` |
| 9 | O_TMPFILE creation | pre | reusable | no | `burn_unstaged` |
| 10 | short write / content validation | pre | reusable | no | `burn_unstaged` |
| 11 | file fsync | pre | reusable | no | `burn_unstaged` |
| 12 | exclusive link collision | **at** | already spent | no | `authorization_consumed` |
| 13 | exclusive link other error | pre | reusable | no | `burn_unstaged` |
| 14 | directory fsync | post | **spent** | no | `burn_unrecorded` |
| 15 | published-identity revalidation | post | **spent** | no | `burn_unrecorded` |
| 16 | executor raises | post | **spent** | called | `executor_failed` |
| 17 | executor returns invalid type | post | **spent** | called | `executor_contract` |
| 18 | unexpected internal, pre-link | pre | reusable | no | `consumer_internal_pre` |
| 19 | unexpected internal, post-link | post | **spent** | unknown | `consumer_internal_post` |

Rows 18–19 replace v1's "no catch-all". A catch-all that *degrades* is a
fallback and remains forbidden; a catch-all that classifies which side of
the boundary it occurred on and refuses terminally is the opposite — it
ensures an unanticipated failure cannot be mistaken for a pre-burn one.
Row 16 also fixes v1's contradiction: executor exceptions **are** caught,
solely to classify them as post-burn terminal, and are never suppressed.

All refusals are content-light: no paths, no prompt or response text, no
environment values, no tracebacks.

## What step 2 does NOT change

* No mutating `systemctl` in the driver.
* No production unit, override, model pointer, or venv file.
* `model_state.json` stays an owner-typed command after a durable
  promotion receipt.
* Cutover remains **forbidden** at `bench_passed`. This builds the
  consumer a future authorized cutover would pass through; it authorizes
  nothing.

## Scope, restated

Step 2 proves the **consumer primitive** and the **final interface**
against a double. It does **not** prove live ordering. That waits for the
act that wires the real executor through structurally, with no other
caller and no other continuation.

## Carried for ratification

* **R1** — the covenant reconciliation in A4. Does the owner-typed
  ceremony satisfy "the owner types every mutating command", or must step
  2 stop at `prepare()` and surrender the adjacency proof to the later
  act?
* **R2** — A1 makes the consumer carry the stage-2 bundle. Accepted as
  the cost of a permit that is not independently verifiable, or is a
  signed/MAC'd permit worth designing first?
