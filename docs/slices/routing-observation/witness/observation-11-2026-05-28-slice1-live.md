# Routing Observation Slice 1 — Live Witness (Observation 11)

**Slice:** Routing Observation / Slice 1 of adaptive substrate-side routing
**Window opened:** 2026-05-28T18:50:01-05:00
**Daemon restarted:** 2026-05-28T18:51:19, PID 72580
**Probe sent:** 2026-05-28T18:52:38
**Window closed:** 2026-05-28T18:53:38-05:00
**Git HEAD:** b437866 (`fix(routing): close observation sqlite connections`)
**Flag:** `MAEZ_DISPATCHER_ENABLED` absent (legacy path witness)
**Witness watermark:** routing rows with `created_at > 1780011930.962515` are live post-restart

## Verdict

**Slice 1 live witness PASSES.** The flight recorder fired on a real Telegram turn, recorded the correct legacy-path observation, and changed nothing about the owner-visible reply. All three non-behavioral proof criteria satisfied.

## The Live Row

Single row past watermark (`created_at 2026-05-28 18:52:38.404840`):

| Field | Value |
|---|---|
| surface | `telegram_surface` |
| path | `legacy_daemon_web_search` |
| chosen_tool | `web_search` |
| chosen_source | `None` |
| execution_status | `empty` |
| outcome_quality | `empty_but_honest` |
| evidence_block_count | `1` |
| spec_match_score | `0.0` |
| spec_match_reason | `no_spec_available` |
| utterance_shape | `contains_subreddit_anchor` |
| latency_ms | `341.2` |
| utterance_hash | `2133cca588fb8252…` |
| chat_id_hash | `None` |
| composition_hint | `None` |
| provenance_framing | `None` |

Compact log line emitted (matches spec §3.2):

```
routing_observation path=legacy_daemon_web_search source= tool=web_search status=empty spec_match_score=0.000 outcome_quality=empty_but_honest utterance_shape=contains_subreddit_anchor
```

## Three-Way Non-Behavioral Proof

1. **Fresh legacy row, correct closed vocab.** Exactly one row past the watermark: `path=legacy_daemon_web_search`, `spec_match_reason=no_spec_available`, `spec_match_score=0.0`. Correct for the flag-absent legacy path where no `CompositionSpec` exists. ✓

2. **Owner reply unchanged / non-behavioral.** The reply was the honest "The search ran and returned nothing… DuckDuckGo is indexing a version of Reddit that is either blocked by the login wall or too stale… The tool is working correctly (it didn't fabricate results)." Same shape as Observation 10 — no Telegram-interceptor regression, no behavior change from the flight recorder. ✓

3. **No raw owner text stored.** `utterance_hash` is sha256 (verified: `sha256("Search r/LocalLLaMA right now for recent local LLM posts.")[:16] == 2133cca588fb8252`, matching the row). `utterance_shape` is the coarse category `contains_subreddit_anchor`. No raw text anywhere in the row. ✓

## Cross-Checks

- **Hash determinism confirmed:** the row's `utterance_hash` matches the independently computed sha256 of the exact probe text, AND matches the same utterance's hash seen in obs 8/10 `daemon_prompt_payload_shape` message_hashes. Hashing is consistent across subsystems.
- **web_search actually ran:** 2 `web_search` entries in actions.log delta. The recorder observed real execution, not a stub.
- **evidence_block_count=1:** the zero-result `[WEB SEARCH: …] No results found.` block from f52911c was injected (1 block), and the recorder counted it correctly.
- **Service posture clean:** no SEGV / fatal / traceback in log delta (a `grep -i fault` produced 2 hits, both the substring "de**fault**" in benign `ambient_block` telemetry — false positives).
- **utterance_shape = contains_subreddit_anchor:** this is precisely the signal Slice 2 will route on. The recorder already classifies r/LocalLLaMA asks correctly; Slice 2 only needs to act on that classification.

## Findings Carried Forward

1. **Test pollution into production DB (for Codex).** 25 pre-witness rows (created 18:32–18:45, surfaces web/telegram/telegram_surface) were written to the real `memory/routing_observation.db` by the test suite — some test instantiated `RoutingObservationStore()` against `DEFAULT_DB_PATH` instead of a temp path. Not a behavior/correctness defect, but tests must use `tmp_path` so they never touch the production store. Worth a follow-up commit before Slice 2 so the learning substrate isn't seeded with test fixtures.

2. **chat_id not wired on the legacy daemon hook (note for Slice 2).** `chat_id_hash=None` because `record_legacy_web_search_observation` is not passed `chat_id` from `daemon.handle_message`. Nullable by design, fine for Slice 1. Slice 2 may want it populated for per-conversation routing analysis.

## What Slice 1 Now Enables

Maez chooses tools exactly as before. The difference: every legacy web-search turn (and, under the flag, every dispatcher turn) leaves a structured, hashed, privacy-safe row. The question "what did Maez think this ask needed, what route did it take, what came back, did it honor the spec?" now answers from a database row instead of a vibe.

Slice 2 (subreddit-shape → LIVE_REDDIT) is now safe to build: the recorder can prove whether the new route fires and whether it improves the evidence surface, by comparing pre/post rows for `utterance_shape=contains_subreddit_anchor`.

## Service Posture After Witness

| Surface | State |
|---|---|
| Flag | absent (unchanged) |
| Daemon PID | 72580 (HEAD b437866) |
| SEGV trap | armed |
| Routing recorder | active, firing correctly on legacy path |
| Owner-visible behavior | unchanged from obs 10 |
| Routing DB | 26 rows (25 test-pollution + 1 live witness) |
