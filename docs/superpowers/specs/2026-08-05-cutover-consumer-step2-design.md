# Cutover slice step 2 — the consumer primitive, design v3

Status: **DRAFT — awaiting ratification. No REDs, no code until ratified.**

Parent: `docs/superpowers/specs/2026-08-04-cutover-bundle-antibypass-design.md`
(step 1, merged at `348332b`).

v1 → v2: cross-lane review found v1 overclaiming five security
properties and under-specifying a sixth. All conceded.

v2 → v3: R2 ruled (reconstruct, do not sign) and four precision blockers
amended. **R1 remains unresolved and is Rohit's covenant decision, not
mine and not review's.** Until it lands, step 2 stops at `prepare()` and
exposes **no production consumer entrypoint** — see A4.

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

### R2 ruled: reconstruct, do not sign

A MAC helps only if its key and signer sit behind a *separately protected
authority boundary*. A same-UID key, or a signer any same-UID process can
call, relocates the forgery rather than preventing it. Signing is
therefore not a prerequisite and is not designed here.

**The reconstruction seam, frozen:**

1. The consumer loads the **frozen artifact selection itself** under the
   canonical root. The selection is a constant of the consumer, not an
   argument.
2. It constructs and revalidates the stage-2 bundle **through the public
   evaluator** — the same path the scorer uses, no private shortcut.
3. It regenerates the **expected canonical stage-2 receipt bytes** through
   the real producer (`build_receipt` + the production encoder).
4. It requires **exact byte equality** with the receipt read from disk.

The consumer **never accepts a caller-supplied `BenchEvidenceBundle`**.
There is no parameter for one. This is what converts "the receipt is
self-consistent" into "the receipt is the one the scorer would have
produced from evidence anchored under our own root".

**Implementability gate.** `cuda_bench_assemble` currently constructs
stage 1 only and explicitly defers stage-2+ entrypoints to step 5
([cuda_bench_assemble.py:275](/home/rohit/maez/scripts/cuda_bench_assemble.py#L275)).
So v2's "carry or reconstruct" was not an implementable contract: there is
no production path that builds a stage-2 bundle. **Step 2 must therefore
either build that anchored stage-2 assembly entrypoint as part of its own
scope, or declare a dependency on step 5 and stop.** I flag this as a
sequencing consequence review's ruling creates, not an objection to it —
but it must be decided before REDs, because it changes what step 2 is.

## A2. Anchoring, properly (concedes the override)

A required parameter is still an override: it makes arbitrary roots
reachable by construction.

**Production entrypoint hard-binds** the canonical bench root, the live
clock, the boot-id source, and the executor. No parameter reaches it.
Injection exists only behind a seam that is structurally test-only —
a private constructor the production path does not call, asserted by the
same AST instrument as A5.

The filesystem discipline v1 got wrong:

**Absolute-root acquisition.** `O_NOFOLLOW` protects only the final
component, so the root is walked component-by-component from `/` with
held directory descriptors. The precedent is `_open_release_directory`
([cuda_bench_driver.py:1665](/home/rohit/maez/scripts/cuda_bench_driver.py#L1665)),
which walks an *absolute* path exactly this way; v2 cited `_relative_parts`
and `_check_directory_fd`, which handle the relative leg only. That
citation is corrected — both are needed, at their respective legs.

```
open("/", O_RDONLY|O_CLOEXEC|O_DIRECTORY|O_NOFOLLOW)
for component in root.parts[1:]:      # reject "", ".", "..", NUL
    openat(component, O_RDONLY|O_CLOEXEC|O_DIRECTORY|O_NOFOLLOW)
```

**Named-chain comparison** happens twice, not once: immediately **before**
publication, and again **after** publication and before `begin()`. A second
`fstat` on a held fd re-reads the same inode and always agrees, so it can
never detect rename or replacement; only reopening the named chain and
comparing it against the held capability can.

**File reads** use `O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC` and require:

* regular file;
* exact expected UID, mode `0600`, `st_nlink == 1`;
* byte count within a fixed bound;
* `st_dev`, `st_ino`, `st_size`, `st_mtime`, `st_ctime` all identical
  before and after the read;
* the final named leaf joined back to the held descriptor.

**`auth.owner`** joins to the frozen expected owner identity — v1 omitted
this entirely, so an authorization naming any owner was accepted.

**Marker names derive only from the already-validated nonce**, after
validation, never from any other caller-influenced value.

**Honest threat statement.** This defeats path races, symlink
substitution, and accidental replacement. It does **not** defeat a hostile
same-UID process able to unlink owner-writable entries after the last
check. Nothing at this privilege level can, and the design does not
pretend otherwise.

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
exists and every failure is reusable.

### Publication is three-state, not two

v2 assumed a non-`EEXIST` link exception meant "not published". It does
not: a signal may arrive after the kernel linked the file but before
Python records success. Frozen result type:

```
not_published | published | uncertain
```

Catchable signals are masked across the link **and** the state
publication, so the window is not merely narrow but closed to everything
maskable. The state is then resolved by **inspecting the final leaf**:

| leaf | verdict |
|---|---|
| absent, and that absence verified through the named chain | `not_published` → reusable |
| present — the staged inode **or any other object** | `published` → spent |
| inspection itself ambiguous | `uncertain` → terminal fail-stop, **no executor** |

**Spent ≠ eligible.** The nonce becomes **spent at the link**. Only after
directory fsync *and* identity verification does it become **eligible to
execute**. Those later failures do not "spend it again" — it was already
spent; they withhold eligibility. v2's wording implied a second
transition and that was wrong.

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

### R1 — UNRESOLVED. Rohit's decision, and nobody else's.

Review agrees the single-command topology is technically stronger, because
it makes validation → burn → first mutation structurally contiguous. It
also correctly declines to amend the covenant on Rohit's behalf. So does
this design.

**Until R1 is ruled, step 2 stops at `prepare()` and exposes NO
production consumer entrypoint.** The burn, the publication, and
`begin()` are designed and specified here, but nothing production-reachable
invokes them.

If Rohit **ratifies** the owner-typed ceremony, two corrections apply to
how I described it:

1. Call it a **single authorization-bound invocation**, not an
   "indivisible act". My word was wrong. The systemd operations are
   sequential and can partially fail; a partial failure must enter the
   frozen recovery path, which an "indivisible act" framing would have
   quietly denied existed.
2. **"No agent or daemon can initiate it" needs an enforceable
   owner-presence boundary.** A CLI *intended* for owner use is not one:
   any same-UID process can invoke it while the authorization is valid.
   Either an actual presence boundary is added, or the design must state
   honestly that **owner invocation is procedural, not technically
   authenticated** — the nonce and window bound the blast radius, they do
   not prove a human typed anything.

I would rather state (2) honestly than claim a guarantee the process
boundary cannot deliver.

If Rohit **refuses**, the burn moves into the later executor act, step 2's
claim narrows to validation plus `prepare()`, and burn/mutation adjacency
is never proven here. That is coherent — just weaker, and it must then be
said plainly rather than implied.

## A5. AST *plus* runtime (Q2 — ruled AGAINST my position)

I argued the adjacency property is syntactic. It is — but the property
that matters is not adjacency, it is *the marker was published before the
executor ran*, and syntax cannot see that.

**AST proves:** adjacent top-level burn and `prepared.begin()`; exactly
one syntactic executor call; no intervening branch or handler; the exact
prebound argument, with no call, property access, or subscript evaluated
after the burn.

**Runtime REDs prove:** a complete, published, fsync-confirmed marker
exists when the double runs, and exactly one call.

v2 also claimed "no call on every post-publication failure", which
contradicts its own failure table — rows 16 and 17 are post-publication
failures where the executor *was* called. Split correctly:

| failure class | executor calls | outcome |
|---|---|---|
| any pre-publication failure | **zero** | reusable |
| post-publication, pre-`begin()` (dir fsync, identity, `uncertain`) | **zero** | spent, not eligible |
| executor raises | **exactly one** | spent, terminal |
| executor returns invalid type | **exactly one** | spent, terminal |

**Neither certifies live ordering.** The later real-executor slice must
separately prove the production caller graph and first-mutation ordering.
Step 2 cannot certify those while its target is a double, and will not
claim to.

## A6. Total failure table — exact codes, not families

v2 wrote `root_*`, `authorization_*`, `receipt_*`. Those are families, and
a family is not a closed set. Every concrete emitted code, each assigned a
side of the linearization point:

| # | failure | side | nonce | executor | exact code |
|---|---|---|---|---|---|
| 1 | root component walk | pre | reusable | no | `root_walk_failed` |
| 2 | root not a directory | pre | reusable | no | `root_not_directory` |
| 3 | root uid mismatch | pre | reusable | no | `root_ownership` |
| 4 | root mode not 0700 | pre | reusable | no | `root_mode` |
| 5 | named-chain disagreement | pre | reusable | no | `root_moved` |
| 6 | marker dir acquisition | pre | reusable | no | `marker_dir_unavailable` |
| 7 | marker dir predicates | pre | reusable | no | `marker_dir_predicate` |
| 8 | authorization unreadable | pre | reusable | no | `authorization_missing` |
| 9 | authorization predicates | pre | reusable | no | `authorization_predicate` |
| 10 | authorization not canonical | pre | reusable | no | `authorization_noncanonical` |
| 11 | authorization wrong type | pre | reusable | no | `authorization_wrong_type` |
| 12 | authorization expired | pre | reusable | no | `authorization_expired` |
| 13 | boot-id mismatch | pre | reusable | no | `authorization_boot_mismatch` |
| 14 | owner mismatch | pre | reusable | no | `authorization_owner_mismatch` |
| 15 | receipt unreadable | pre | reusable | no | `receipt_missing` |
| 16 | receipt predicates | pre | reusable | no | `receipt_predicate` |
| 17 | receipt not canonical | pre | reusable | no | `receipt_noncanonical` |
| 18 | receipt wrong type | pre | reusable | no | `receipt_wrong_type` |
| 19 | stage-2 reconstruction failed | pre | reusable | no | `permit_unreconstructible` |
| 20 | regenerated bytes ≠ disk bytes | pre | reusable | no | `permit_unverified` |
| 21 | any S3 join | pre | reusable | no | `join_mismatch` |
| 22 | chronology | pre | reusable | no | `chronology_violation` |
| 23 | clock or boot read | pre | reusable | no | `edge_state_unreadable` |
| 24 | `prepare()` failure | pre | reusable | no | `preparation_failed` |
| 25 | O_TMPFILE creation | pre | reusable | no | `burn_unstaged` |
| 26 | short write | pre | reusable | no | `burn_write_incomplete` |
| 27 | staged content validation | pre | reusable | no | `burn_content_invalid` |
| 28 | file fsync | pre | reusable | no | `burn_unstaged_fsync` |
| 29 | link collision (EEXIST) | at | already spent | no | `authorization_consumed` |
| 30 | link other error, leaf absent | pre | reusable | no | `burn_unstaged_link` |
| 31 | link outcome unresolvable | **uncertain** | **treat as spent** | no | `publication_uncertain` |
| 32 | marker directory fsync | post | spent | no | `burn_unrecorded_fsync` |
| 33 | published identity revalidation | post | spent | no | `burn_unrecorded_identity` |
| 34 | post-publication chain recheck | post | spent | no | `root_moved_post_publication` |
| 35 | executor raises | post | spent | **called** | `executor_failed` |
| 36 | executor returns invalid type | post | spent | **called** | `executor_contract` |
| 37 | unexpected internal, pre-link | pre | reusable | no | `consumer_internal_pre` |
| 38 | unexpected internal, post-link | post | spent | unknown | `consumer_internal_post` |

Rows 37–38 replace v1's "no catch-all". A catch-all that *degrades* is a
fallback and stays forbidden; one that classifies which side of the
boundary it occurred on and refuses terminally is the opposite — it
ensures an unanticipated failure cannot be mistaken for a pre-burn one.
Row 35 fixes v1's contradiction: executor exceptions **are** caught,
solely to classify them as post-burn terminal, and are never suppressed.

**Cleanup never unlinks a published marker.** Not on any failure path, not
on `publication_uncertain`, not on `consumer_internal_post`. A published
marker is the single-use record; removing it would restore replay.
Recovery is always a fresh owner-typed authorization with a fresh nonce,
never repair of the old one.

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

* **R1 — OPEN, owner-only.** The covenant reconciliation in A4. Does an
  owner-typed ceremony satisfy "the owner types every mutating command",
  and if so, is procedural (not technically authenticated) owner presence
  acceptable? Until ruled, step 2 stops at `prepare()`.
* **R2 — RULED.** Reconstruct, do not sign. Seam frozen in A1.
* **R3 — NEW, created by R2's ruling.** Reconstruction needs an anchored
  stage-2 assembly entrypoint, which does not exist: the production
  assembler builds stage 1 only and defers stage-2+ to step 5. Does step 2
  absorb that entrypoint into its scope, or declare a dependency on step 5
  and stop at validation? This changes what step 2 *is*, so it must be
  ruled before REDs.
