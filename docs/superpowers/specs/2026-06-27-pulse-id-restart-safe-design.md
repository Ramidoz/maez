# Restart-Safe Pulse Identity — Salience Ledger Hygiene — Design & Covenant Brief

**Date:** 2026-06-27. **Lane:** Claude drafts + covenant-reviews; Codex specs → plans → builds; owner witnesses. **Origin:** the salience ledger (Maez's idle-loop notebook, treated as evidence by the gate/report) keys each pulse with `pulse_id = f"seq{n}"` where `n` is a **per-process counter that resets to 0 on every daemon start** ([daemon/maez_daemon.py:3459](../../../daemon/maez_daemon.py), [:5166-5167](../../../daemon/maez_daemon.py)). So restart 2's `seq1` is written with the **same `pulse_id`** as restart 1's `seq1` — two different days share a page number.

## The governing sentence (the law of this slice)
**A pulse_id is a page number in Maez's notebook; two different runs must never share one.** This is hygiene, not behavior: nothing about how Maez thinks, speaks, routes, or steers changes. We are labeling pages so downstream evidence can trust that a `pulse_id` (and the `proposal_hash` that embeds it) names exactly one pulse, ever.

## Root cause (verified in code)
- `__init__`: `self._salience_pulse_seq = 0` ([:3459](../../../daemon/maez_daemon.py)) — reset on every construction.
- pulse mint: `self._salience_pulse_seq += 1; pulse_id = f"seq{self._salience_pulse_seq}"` ([:5166-5167](../../../daemon/maez_daemon.py)).
- `proposal_hash` embeds `pulse_id` ([:5190-5201](../../../daemon/maez_daemon.py)) → with a colliding `pulse_id` + same `(strategy, arm, fact_key, change_kind)`, two genuinely different pulses hash **identically**.

## Impact (verified — bounded, forward-looking)
- **The gate/report are NOT corrupted today.** `gate_report` reads `SELECT arm, fact_key, thought_formed, non_duplicate_stored, …` and `evaluate_gate` counts rows by arm/coherence — **it never selects, GROUPs by, or keys on `pulse_id`** ([salience_gate.py:235-241](../../../core/cognition/salience_gate.py)). No reader in the repo dedups or joins on `pulse_id`/`proposal_hash`.
- **The prior/current pairing is process-local** (`self._salience_pending` in memory), not a ledger query on `pulse_id` — so the collision never affected pairing, and the fix cannot break it.
- The cost is **future evidence integrity**: the moment any reader treats `pulse_id` or `proposal_hash` as a unique key (dedup, join, per-pulse rollup), colliding ids would silently conflate two restarts. We close that trapdoor before it is opened.

## The fix (surgical, no history rewrite)
1. **Per-process run-id, captured once at construction.** Add `self._salience_run_id = new_run_id(now_ms=<process start ms>, pid=<os.getpid()>)` beside `self._salience_pulse_seq = 0`. The run-id is **stable within a process** (all pulses in one run share it) and **distinct across restarts** (a later start time and/or a different pid).
2. **Pure id helpers in `core/cognition/salience_ledger.py`:**
   - `new_run_id(*, now_ms: int, pid: int) -> str` → `f"r{now_ms}_{pid}"` (injectable args → deterministically testable; real values captured once in the daemon).
   - `make_pulse_id(run_id: str, seq: int) -> str` → `f"{run_id}.seq{seq}"`.
3. **Mint via the helper:** `self._salience_pulse_seq += 1; pulse_id = make_pulse_id(self._salience_run_id, self._salience_pulse_seq)`. `proposal_hash` then becomes genuinely unique per pulse with no other change.
4. **No migration, no rewrite.** Legacy `seqN` rows stay exactly as written. New rows carry `r<ms>_<pid>.seqN`. `pulse_id` is `TEXT`; both formats coexist.

### Why run-id = start-time(ms) + pid (not a random token)
"Cannot collide" is provable to a reviewer: a pid is never reused while its process lives, and a systemd restart always yields a strictly-later start time and a fresh pid — so `(now_ms, pid)` is unique per run, with ms making even same-second restarts safe. It is also **traceable** (a `pulse_id` maps back to which daemon run, and when) — valuable because the notebook is evidence. A random token would be unique-in-practice but neither deterministically provable nor forensically traceable.

## Tests (the witness set)
- **Namespacing (the core guarantee):** for two distinct run-ids `a = new_run_id(now_ms=1000, pid=100)`, `b = new_run_id(now_ms=2000, pid=200)`, the sets `{make_pulse_id(a, s) for s in 1..50}` and `{make_pulse_id(b, s) for s in 1..50}` are **disjoint**. Deterministic proof that two restarts cannot collide.
- **Same-second, different pid:** `new_run_id(now_ms=1000, pid=100) != new_run_id(now_ms=1000, pid=200)` (pid disambiguates a same-ms restart).
- **Within-run stability:** a fixed run-id + seq 1..N yields ids sharing the run prefix, differing only in `.seqN` (one process = one page-number namespace, monotonic).
- **Binding follows the page number (owner watch-item):** `make_proposal_hash` (extracted from the daemon's inline computation, output-preserving) is bound to the **full** `pulse_id` — same seq + same `(strategy, arm, fact_key, change_kind)` but different run-ids ⇒ **different** `proposal_hash`; and the run-stamped hash ≠ the bare-`seq1` hash. So a restart-safe row id can never sit atop a muddy binding string.
- **Real per-process distinctness:** constructing the run-id from two successive real captures (or asserting the daemon captures it once at `__init__`, not per-pulse) yields different run-ids across constructions.
- **Legacy coexistence (reader compat):** a ledger seeded with a legacy `seq1` row **and** a new `r1000_100.seq1` row → `gate_report` reads both, counts 2 rows, does not crash or dedup. Proves the readers handle mixed formats.

## Scope
**IN:** the two pure helpers; the daemon run-id captured once at construction; mint `pulse_id` via the helper; the witness tests above. **`pulse_id` stays `TEXT`; the schema is unchanged.**
**OUT (named, deferred):** rewriting/migrating legacy `seqN` rows (explicitly NOT done — preserve history); any change to `gate_report`/`evaluate_gate` (they already ignore `pulse_id`); any steering/prompt/voice/routing behavior; adding a uniqueness constraint to the schema (a future slice, once all-new rows are unique — would falsely reject legacy collisions today).

## Covenant compliance
- **Honest notebook, no rewritten history** ([[feedback_canon_governs_canon_witness_before_claim]]): we relabel future pages; we never alter what past pulses recorded.
- **Visible substrate state, true-by-construction** ([[feedback_visible_substrate_state_not_chain_of_thought]]): the run-id is real process identity, not a fabricated token — a `pulse_id` traces to an actual daemon run.
- **No steering, no behavior change** ([[feedback_hardcode_organs_not_opinions]]): a pure identity-format change behind the existing shadow flag; the gate stays read-only at BASELINE_ONLY.
- **Verify before encode** ([[feedback_verify_before_you_encode]]): readers confirmed `pulse_id`-agnostic before claiming backward-compatibility.

## Predicted effect
New idle-loop ledger rows carry globally-unique, restart-safe `pulse_id`s (`r<ms>_<pid>.seqN`) and correspondingly-unique `proposal_hash`es. Legacy `seqN` rows are untouched and still read. The gate/report produce identical verdicts (they ignore `pulse_id`). Two daemon restarts can no longer write the same page number — so when a future reader does key on pulse identity, it will be telling the truth.
