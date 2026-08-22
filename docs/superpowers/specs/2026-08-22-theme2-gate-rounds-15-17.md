# Gate rounds 15–17 on Theme 2 — the T5 execution model, from over-built to discriminating

Three rounds, all Codex `--effort xhigh`, review-only, all ruling **FIX
FIRST / HOLD**. Recorded together because they tell one story: a witness
that was being hardened in the wrong direction, and the round that said
so.

| Round | Commit | Closed | Open |
|---|---|---|---|
| 15 | `e2edb51` | I | B, D, E, J |
| 16 | `b2a3188` | E | B, D, J + **finding L** |
| 17 | `15f456e` | **D, J** | B, M, N |

## Round 16's finding L — the one that mattered

I asked round 16 a question beyond the re-check: *is T5 worth what it
costs, and is it measuring the thing S1 needs measured?* The answer was
that it was **over-specified and under-discriminating**. Verified on
this host before acting:

```
legacy current_phase() per fixture
  F-G healthy    -> gestation
  F-P partial    -> gestation      ← S1 must say unknown
  F-E 0-byte     -> gestation
  F-D2 corrupt   -> gestation      ← S1 must say unknown
  F-A absent     -> gestation
```

`birth_phase.py:38-66` answers `gestation` for every ledger lacking a
readable anchor — which is the defect S1 exists to fix — and T5's
fixture was a **healthy** ledger, exactly where legacy and S1 agree. Two
runs would match, the projection would report identity, and the witness
would pass **without ever proving the guard exists**. Five rounds had
gone into hardening a comparator measuring physical layout, which was
never the invariant of interest.

Owner ruling: adopt the simplification plus a discriminator, and keep
producing and digesting the archive as forensic evidence so round 11's
ordering rule is honored exactly. v6.5 and v6.6 implement it.

## What the three rounds found, in one list

Each was reproduced by the reviewer, not merely asserted.

- **A sentinel that compared equal** (15/16 lineage): the collision
  guard returned a *string*, so when both sides collided the sentinels
  matched and the whole row relationship vanished with `kills=[]`. Same
  shape as P2 being optional — two projections that both omitted the
  extract passed.
- **A digest absorbed as an identifier**: the uuid class admitted any
  12–64 char hex, then any prefix plus 8–32 hex. `digest-<32a> →
  <32b>` went straight through as identical. Excluding bare 64-hex
  protects nothing against prefixed, MD5-shaped or truncated hashes.
  The class is now an exact allowlist of the three forms the codebase
  mints, each pinned to its construction site.
- **A guard placed after the first open**: the store-path check ran
  after the daemon import, which already opens `quality.db` and
  `action_trust.db`. And the import calls the config loader a *second*
  time, so the environment checked before it is not the final one. The
  guard now runs on both sides.
- **A proxy check instead of the real one**: raw env values were tested
  against "somewhere under the repo". `MAEZ_DATA=/home/rohit/maez/logs`
  passes that while moving every store to `logs/memory` — writable but
  excluded from the projection, so the baseline would have captured
  nothing. Now the effective resolved paths are pinned by exact
  equality, and a catch-all sweep refuses any database that lands
  outside the projected tree, whatever selector produced it.
- **A hash whose failure was invisible**: `say "$(sha256sum …)"` — `say`
  succeeded, `set -e` saw nothing, publication proceeded with an empty
  digest. Now a checked statement, published via temp plus atomic
  rename.
- **Publication before restoration**: the archive was copied into the
  repo and only then did the trap run, where a failed `systemctl start`
  was a warning. A baseline could be published while Maez stayed down.
  Restoration now runs first, polls to active, and gates the copy.
- **Aggregate proof standing in for per-item proof**: "tail invoked at
  least once" passes on 19 returned-before-tail interactions plus one
  stored one. Now every interaction is bound to its own passage.

## Round 17 — the split that existed only in prose

D and J closed. Three remained, and two of them were structural rather
than local:

- **N**: v6.5 *declared* G1–G6 the only gate and demoted the byte
  projection — but the executable still ran the projection under
  `set -e`, so a physical HNSW difference still blocked publication,
  while the clauses that mattered decided nothing. The split was
  prose-only. `theme2_s1_t5_gate.py` is now the single executable
  authority; the projection's status is captured, not propagated. Round
  17 also asked for one clause back in the gate — **logical P2 content**
  (documents, non-volatile metadata, embeddings), since recall can
  regress while phase stamps and counts hold still. That is G7.
- **M(iii)**: G5 had no mechanism. §9 pinned a parameterless resolver
  and nothing said how to force it on, so the discriminator was
  unspecifiable. v6.6 pins `MAEZ_S1_PHASE_TRUTH=1` — *before* the code
  that implements it — and gives the forced-on run **its own success
  contract**, because refusal is the correct outcome there and G6 would
  otherwise mark a correct run as failed.
- **M(ii)/M(iv)**: the census was fail-open (`absent` and `error`
  became facts) and the shell check accepted "any dictionary contains a
  gestation stamp", which raw Chroma alone satisfies. And the partial
  fixture's census was never durably archived, so G3 had nothing exact
  to match. The gate is now fail-closed, and the pinned census is
  published beside the archive with its digest committed in v7.
- **B**: enumerating store selectors will always miss one. The
  catch-all sweep replaces the enumeration as the load-bearing check.

## Standing

- T5 may not run on round 17's ruling; round 18 decides whether v6.6
  closes B, M and N.
- S1 code remains barred until the v7 digest amendment and until
  §12.13's multi-writer latch gap closes.
- Across rounds 15–17 no T5 run, production import, live-store open,
  daemon action or archive occurred. Every execution was inside a
  `bwrap` airlock or on synthetic fixtures in the scratchpad.
