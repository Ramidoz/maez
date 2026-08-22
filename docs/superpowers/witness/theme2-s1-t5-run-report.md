# T5 run report — the pre-S1 baseline (protocol §8, §12.9)

Executed 2026-08-22T09:46:21-05:00 at repo HEAD `db0d65e2c5a71905a95a37a3c61a758000567709`.
Orchestrator exit **0**. Gate verdict **PASS**.

Every figure below is copied from the run's own artifacts. Where a
number is uncomfortable it is still here.

## Verdict

```json
{"clauses": {"K1_ledger_unchanged": "PASS", "K2_no_latch_artifact": "PASS",
             "K3_positive_controls": "PASS", "K4_no_stray_store": "PASS"},
 "D_discriminator": "NOT-APPLICABLE",
 "failures": {}, "verdict": "PASS"}
```

`D_discriminator: NOT-APPLICABLE` is the correct pre-S1 answer and the
gate refuses it the moment `birth_phase.resolve` exists. **This run does
not prove the guard is dormant. It pins the baseline the forced-on run
will be measured against.**

## Published artifacts

| Artifact | sha256 | bytes |
|---|---|---|
| `theme2-s1-baseline.tar.zst` | `328f98d4d9cb222e437e97a74b22cee46a4cac9114d7f3875bb56def0b445216` | 63544 |
| `theme2-s1-baseline-census.json` | `9e4c145b07fc6d000f8ed9c6c1739c71c711e99b3409dc198e2a03ea78eef21b` | 566 |

The census carries `bound_archive_sha256` so the pair cannot drift.

## The pinned census — what the discriminator will compare

Both fixtures, flags off:

```
current_phase: gestation
chroma::raw       {"gestation": 20}
chroma::daily     {}     chroma::core   {}
private_thoughts  {}     audit_log      {}
```

The empty stores are **honest**: `store_telegram` writes `raw` only, and
T5 reaches one of the thirteen census consumers. A gate that rejected
this shape was gate round 18's finding.

The partial fixture reading `gestation` is the point. Legacy
`current_phase()` answers `gestation` for every ledger without a
readable anchor — absent, empty, half-built, corrupt alike — which is
the defect S1 exists to fix. Flags off must keep answering that; a
forced-on S1 must answer `unknown` and refuse.

## Containment, from inside the namespace

```
repo_readonly              PASS (OSError: Read-only file system)
memory_writable_and_empty  PASS
network_unreachable        PASS (ConnectionRefusedError)
no_maez_env_at_entry       PASS
```

Self-test, before the daemon was touched: 8/8 — repo write `EROFS`,
memory write succeeds, empty TCP table, **zero socket pathnames on the
root device**, `memory.memory_manager` imports with `BASE_DB` resolving
into the overlay, entry environment exactly the nine declared names,
probe visible only in the airlock, live tree unmarked afterwards.

Entry environment (9): `HOME LANG LC_ALL PATH PWD
PYTHONDONTWRITEBYTECODE PYTHONHASHSEED TZ VIRTUAL_ENV`.

**After the daemon import**, the shipped secrets loader repopulated
`config/.env` exactly as in production — 12 `MAEZ_*` names including
`MAEZ_GITHUB_TOKEN`. That is correct behavior, not a leak, and it is
why T5 asserts the narrower true thing: no phase/S1 flag set. Values
are recorded only for a declared non-secret allowlist.

Effective store paths, asserted by exact equality **on both sides of
the import**: `home`, `data_dir` → the repo; `memory_dir`,
`memory_db_dir`, `audit_log_db`, `ledger` → the projected tree;
`config_dir`, `cache_dir`, `logs_dir` → their pinned locations. The
census asked each module where its store is: `private_thoughts` →
`memory/private_thoughts.db`, `audit_log` → `memory/audit_log.db`.

## Gate clause evidence

- **K1** — ledger sha256 `2d7fef22…` post-migration and post-replay,
  identical. File set `['ledger.db', 'ledger.db-shm', 'ledger.db-wal']`:
  the sidecars are expected, created by the read-only opens at
  `envelope_builder.py:268` / `recent_turns.py:97`.
- **K2** — `latch_artifacts_in_store_tree: []`, from a sweep of the whole
  store tree.
- **K3** — 20/20 returned, 0 raised, 0 without a tail passage, 20 tail
  invocations, collections grew. Underlying numbers re-derived, not the
  label trusted.
- **K4** — pre-run inventory 0, post-run strays `[]`.

## What was exercised, honestly

`brain_reachable: false`. Every reply came from the hermetic fallback,
e.g. verbatim: *"My local brain is still waking or restarting. Try me
again in a moment."* Twenty returned fallbacks are the expected shape
here — **they are not healthy synthesis** and must never be reported as
such.

`sqlite3.sqlite_version` **3.46.1**, as §0 expects. Daemon construct
0.376 s. The manifest's `at` is ordinal, not a clock: nothing on the
path accepts an injected time, so the calls ran back-to-back.

§6's frozen selector suite ran **inside the airlock**: 46 passed.

## Forensic instruments — recorded, never deciding

| Instrument | rc |
|---|---|
| gate self-test (authority) | 0 — 30/30 |
| projection self-test | 0 — 19/19 |
| Chroma extract (a, b, p) | 1 |
| byte projection (a, b, p) | 0 |
| volatile derivation | 1 |
| byte comparison a vs b | 1 |

The three non-zero forensic results are **open items, not failures of
this run** — the extract did not produce collections, and the volatile
derivation and byte comparison therefore had findings. They are
recorded here rather than resolved, because the owner ruled the byte
machinery forensic after gate round 16 showed it was measuring physical
layout rather than the invariant of interest.

## Deviations and defects found by running

Seven attempts. Every failure was mine, and none was found by reading:

1. `--work` parent required ownership, refusing a sticky `/tmp`.
2. The sticky test stripped four characters from `1777`, not three.
3. `local tag=… A="$W/airlock-$tag"` — bash 5.3 expands every word of a
   `local` before assigning any, so `$tag` was unbound under `set -u`.
4. K4 refused 68 **pre-existing** databases in the read-only repo. It is
   now a before/after difference, which is what the clause always meant.
5. The K4 rewrite deleted the K2 latch sweep; the gate's fail-closed
   schema check caught it — *"missing key
   `latch_artifacts_in_store_tree`"* — refusing absent evidence rather
   than reading it as absence of artifacts.
6. **Six stop/start cycles tripped systemd's start-rate limiter and
   `maez.service` entered `failed (start-limit-hit)`. Maez was down for
   roughly two minutes until cleared by hand.** Not a Maez fault and not
   the airlock — a witness that stops the owner's daemon repeatedly
   without clearing the counter. `reset-failed` now precedes every start.
7. That same attempt showed the design holding where it mattered: the
   gate had passed and the archive was built, but **publication is
   contingent on restoration**, so nothing was written into the repo
   while Maez was down. That clause came from gate round 15.

Attempts 1–5 refused before the daemon was stopped. In every attempt
the live tree was untouched: no store outside the airlock was opened,
and `git status` was clean throughout.
