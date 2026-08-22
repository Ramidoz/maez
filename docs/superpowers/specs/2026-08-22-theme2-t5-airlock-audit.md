# Theme 2 — T5 pre-execution audit: the replay run STOPS on three findings

Status: **STOP / owner ruling required**, per the S1 session handoff's
Task 1 instruction ("verify every path it touches — env-resolved AND
module-global — lands inside the airlock… If any path cannot be
redirected, STOP and redesign the run with the owner rather than
proceeding") and §Cautions 1.

Nothing was executed against the live tree. No replay was driven. No
store was opened. This file records what the audit found and what the
owner must rule on before T5 can produce a baseline archive.

## 0. Live state verified at audit time

- `memory/ledger.db` — 0 bytes (unborn, as the handoff states).
- No `MAEZ_*` variable set in the session environment.
- Working tree clean at `e923a95`.
- Interpreter `3.14.4`; `sqlite3.sqlite_version` **3.46.1** — matches
  the protocol §0 expectation.
- **`maez.service` is RUNNING**, along with `maez-web`, `llama-server`
  (127.0.0.1:8080), `llama-judge` (8081), `maez-searxng`,
  `minicheck-verifier`, `maez-watchdog`. The live daemon holds the live
  stores open right now.

## 1. Finding A — a store path on the reply path CANNOT be redirected

`scripts/replay_harness.py` is itself well-behaved: it never reads an
env ledger override, it builds each probe DB under
`tempfile.mkdtemp()` (§`_default_probe_db_factory`, line 697), and its
only repo-rooted constants are `_REPO`-relative read paths and
`_DEFAULT_BASELINE_PATH` (line 154), which is written only in the
explicit `--write-baseline` operation.

It is also **not the instrument T5 needs**. It consumes a JSONL *probe
corpus* with six category runners; `theme2-s1-replay.json` is a JSON
object of 20 `{at,id,source,text}` interactions to be driven "through
the reply machinery". The reply machinery is
`daemon/maez_daemon.py:handle_message` (line 7085) and its CLI
analogue `cli/maez_chat.py:_handle_chat` (line 793) — neither is
reachable from the probe harness.

The reply machinery reaches `memory/memory_manager.py`, which pins:

```
memory/memory_manager.py:45   BASE_DB = Path("/home/rohit/maez/memory/db")
```

`BASE_DB` has **no environment override anywhere in the repo**. It is
consumed at `memory_manager.py:597` inside `_make_client()`:

```
path = BASE_DB / subdir
path.mkdir(parents=True, exist_ok=True)
return chromadb.PersistentClient(path=str(path), ...)
```

Constructing a `MemoryManager` therefore **creates directories in and
opens Chroma clients against the live store** at
`/home/rohit/maez/memory/db/{raw,daily,core}` — before any probe logic
runs, regardless of every `MAEZ_*` variable set. It is also consumed
at `memory_manager.py:1435-1440` for the embedding-contract
reconciliation.

This is precisely the scar class recorded in
`feedback_hermetic_sandbox_hardcoded_path_hazard` and
`feedback_my_instrument_destroyed_the_evidence`: env sandboxing does
not redirect module-global absolute paths.

A repo-wide AST sweep of module-level absolute-path constants under
`core/ memory/ daemon/ skills/ cli/ scripts/` (excluding `tests/`)
found **54** such constants. The ones on or adjacent to the reply
path:

| Construct | Literal |
|---|---|
| `memory/memory_manager.py:45` `BASE_DB` | `/home/rohit/maez/memory/db` |
| `memory/memory_manager.py:387` `SOUL_PATH` | `/home/rohit/maez/config/soul.md` |
| `skills/telegram_voice.py:426` `SOUL_PATH` | `/home/rohit/maez/config/soul.md` |
| `skills/web_interface.py:110` `PLANNER_PATH` | `/home/rohit/maez/memory/project_planner.json` |
| `skills/web_interface.py:114` `ANALYTICS_PATH` | `/home/rohit/maez/memory/site_analytics.jsonl` |
| `skills/web_interface.py:1939` `_PENDING_CARDS_DB` | `/home/rohit/maez/memory/pending_cards.db` |
| `skills/web_interface.py:2773-2774` lived episode/graph DBs | `/home/rohit/maez/memory/lived_*.db` |
| `skills/web_interface.py:1937-1938`, `:10515` logs | `/home/rohit/maez/logs/*.log` |
| `core/vision_contract/screen_privacy.py:11-12` | `~/.config/maez/screen_perception.*` |

`core/infra/paths.py` provides `MAEZ_HOME`/`MAEZ_DATA` redirection and
most modern code honors it — but the redirection is **not total**, and
a partial airlock is the exact failure mode that deleted two live
stores. `scripts/dev/worktree_test_airlock.py` (3693 lines) is a
genuine hardening asset but guards **import provenance** (`sys.path`,
loader origins), not data writes; it cannot stop `BASE_DB`.

**Verdict on Finding A: the run cannot be airlocked by environment
redirection. STOP condition met.**

### A remedy exists, and it is stronger than redirection

`bwrap` is installed (`/usr/bin/bwrap`) and unprivileged user
namespaces are enabled (`kernel.unprivileged_userns_clone=1`,
`user.max_user_namespaces=251676`). A containment probe was executed
**inside the scratchpad only** and confirmed:

- `--ro-bind /home/rohit/maez /home/rohit/maez` makes the live tree
  read-only: `echo x > /home/rohit/maez/README_PROBE.txt` failed with
  `Read-only file system`, and the file does not exist in the live
  tree afterwards.
- `--bind <airlock>/memory /home/rohit/maez/memory` makes a write to
  `/home/rohit/maez/memory/probe.txt` land in the airlock directory
  instead.

This converts the problem from *redirection* (which a module-global
literal defeats) to *containment* (which it cannot): the live path
still resolves, the bytes land in the airlock, and any path the
airlock did not anticipate fails **loudly, read-only** rather than
silently writing to the live tree. It is the only mechanism found that
satisfies the handoff's "every path it touches, env-resolved AND
module-global".

## 2. Finding B — the store tree is not byte-reproducible, so protocol §6's byte-compare is unexecutable as written

Protocol §6 requires the manifest "driven twice — flags off, flags off
again — byte-compare of the airlock store tree between runs and
against the baseline archive". Two runs of identical code on identical
input cannot produce identical bytes, because every store on the path
stamps a fresh UUID and a wall clock, and the protocol pins **no clock
or id injection** for this test (§0's clock rule covers the resolver
path only):

| Store | Non-determinism |
|---|---|
| Chroma raw / daily / core | `memory_id = str(uuid.uuid4())` and `datetime.now(timezone.utc).isoformat()` at `memory_manager.py:1499-1500`, `1598-1599`, `2066-2067` |
| `private_thoughts.db` | `ts=time.time()` at `private_thoughts.py:1099` |
| `audit_log.db` | `ts = time.time()` at `audit_log.py:245`, `444`, `513`, `568` |
| `ledger.db` | `turn_id = str(uuid.uuid4())`, `ts = time.time()` at `writer.py:353-354` |

One part of the tree *is* byte-exact and worth keeping as a literal
kill: flags off, `try_write_turn` returns `None` from
`ledger_writes_enabled()` **before** constructing a writer
(`writer.py:576-578`), so `ledger.db` is never opened and never
changes. The latch-directory sentinel is likewise byte-exact
(absence).

The remaining stores can only be compared under a **declared
normalization**. That normalization must be pre-registered in the
protocol — chosen before the run, never tuned to make a run pass.

## 3. Finding C — "the reply machinery, flags off" is underdetermined in three ways

1. **The brain.** `handle_message` calls the LLM
   (`core/routing/llm_client.chat`, backend chosen at call time). There
   is no stub or deterministic backend in the repo. Inside a hermetic
   airlock with no network the call raises `BackendError` and the
   fallback paths run; with `127.0.0.1:8080` reachable the real brain
   answers, non-deterministically, and the run also drives
   `maez-searxng`. Which of these is "the reply machinery" is a ruling,
   not an inference.
2. **The starting state of the airlock stores.** The protocol does not
   say whether the airlock begins with empty stores or a copy of the
   live ones. It must be **empty** — a baseline archive committed to
   git must not contain Maez's real memories — but that has to be
   stated, because it also determines what the replay's recall turns
   ("what did we talk about earlier?") can possibly return.
3. **The concurrent daemon.** `maez.service` is live and holds the
   real stores. Per `reference_sqlite_wal_multiwriter_hazard` the host
   is inside the documented WAL-reset corruption window; the run must
   never share a store with it. Containment (Finding A) satisfies
   this, but the run report must record that the daemon was live and
   untouched — or the owner may prefer it stopped for the run.

## 4. Proposed redesign (for owner ruling; no part executed)

**R1 — containment, not redirection.** Drive the replay under `bwrap`:
`/` read-only; `/home/rohit/maez` read-only; airlock directories bound
over `/home/rohit/maez/memory`, `/home/rohit/maez/logs`,
`~/.config/maez`, `~/.cache`; a private `/tmp`; network namespace per
R3. Publish the exact `bwrap` argv in the protocol amendment and quote
it in the run report. Any write the airlock did not anticipate fails
read-only and is a reported deviation, never a silent live-tree write.

**R2 — a pre-registered invariance projection instead of raw byte
equality.** The archive stores the raw tree (for provenance); the
*comparison* is over a projection frozen in the amendment:
   - byte-exact: `ledger.db` unchanged, no latch directory, no new
     files outside the declared set;
   - structural: per store, the table/collection set, row and record
     counts, and every content-bearing column — with the declared
     non-deterministic columns (`uuid`-shaped ids, `ts`/`timestamp`)
     replaced by their ordinal position in a stable sort;
   - phase-exact: the multiset of `memory_phase` values per store, and
     the exact id set of rows carrying each value.
   The claim T5 then proves is stated honestly: **flags off ⇒ the
   projection is identical**, not "the bytes are identical".

**R3 — the brain, one of two rulings.** Either (a) *hermetic*: no
network namespace, LLM unreachable, the replay exercises the real
ingestion/stamp/store path with fallback replies — deterministic in
shape, and the phase-stamp behavior T5 actually guards is fully
exercised; or (b) *live-brain*: allow `127.0.0.1:8080`, real replies,
richer coverage, more projection noise. **Recommendation: (a).** T5's
subject is the store tree under flags-off, not reply quality, and (a)
removes an entire non-determinism axis and a whole class of egress
risk.

**R4 — the airlock starts empty**, with the ledger created by
`core.ledger.migrate.run` and every other store created by the code
under test on first write. Stated in the amendment.

**R5 — protocol v6 carries all of the above** *and* the archive
digest, in one amendment committed before the first S1 code commit.
Round 11's ordering rule is preserved; the amendment simply also fixes
what round 10 left underdetermined.

## 5. What is NOT proposed

- No change to any of T1, T2, T3, T4, T6.
- No stub, mock, or fake of the storage layer. R3(a) is the absence of
  a network, not a fake brain.
- No edit to `memory/memory_manager.py` to make `BASE_DB`
  env-overridable. That is a real defect and worth its own slice, but
  fixing production code to make a witness runnable inverts the
  discipline — the witness must survive the code as shipped.
- No touch of `config/creation_manifest.md`. Owner-only.
