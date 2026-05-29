# Observation 18 — Honest-Empty Path Live Witness (Mode A, pre-merge)

**Date:** 2026-05-29
**Purpose:** Behavioral proof (Task 9 of the honest-empty plan) that the daemon actually drinks from the honest-empty pipe — not just that unit tests pass. Witnesses the **Mode A daemon false-premise** fix on branch `honest-empty-evidence-path`, **pre-merge**.
**Spec/plan:** [spec](../../../superpowers/specs/2026-05-29-honest-empty-evidence-path-design.md) · [plan](../../../superpowers/plans/2026-05-29-honest-empty-evidence-path.md)

## Setup

- Daemon restarted onto branch code, **flag-absent, unit-managed**: `maez.service` active, PID **627045** (was 574844, which predated the branch), PPID 2987 (`systemd --user`), clean boot (no traceback), `__main__`-guarded import verified before restart.
- Pre-probe anchors: maez.log offset 24353443; `focused_cognition_runs` watermark 23 rows.

## Probe (single)

> Search r/LocalLLaMA right now for recent local LLM posts.

## Reply (owner-visible)

> I ran a search on r/LocalLLaMA for recent local LLM posts, but it returned no usable results. I can try a different source or rephrase the query if you'd like. Let me know how you'd like to proceed.

## Five gates — all GREEN (from the trace, not the reply)

| Gate | Result |
|------|--------|
| `honest_empty_reply` log line | ✅ `16:00:49 honest_empty_reply surface=telegram_surface source=web_search mode=focused call_purpose=honest_empty` |
| `call_purpose=honest_empty` | ✅ (log line + `daemon_system_part_shape` + `daemon_prompt_payload_shape`) |
| `focused_cognition_runs.groundedness_verdict = empty_but_honest` | ✅ row 24: `verdict=empty_but_honest`, `source_types=["empty_result"]`, `cited=[]`, `fallback=None` |
| no forbidden vocab in reply | ✅ |
| no raw query persisted | ✅ `evidence_map_json = [{"durable_id":"ch_28a802f83584ac49","local_label":"E1","source_type":"empty_result"}]`; raw-query needles `LocalLLaMA` / `r/LocalLLaMA` / `recent local LLM` all absent from every column |

- Path: `routing_observation path=legacy_daemon_web_search ... status=empty ... outcome_quality=empty_but_honest` — the witnessed-bug path. The daemon tried 3 query reformulations (all 0 results) before the honest-empty branch fired.
- `mode=focused`: the tiny clean-desk call produced the voiced reply; the deterministic fallback was not needed.

## The strongest evidence (honest flag)

The `daemon_prompt_payload_shape` log (the **built-but-unsent** megaprompt, logged at the pre-branch telemetry seam) shows an 8-message payload whose chat history contains the **earlier** (14:17) scope probe's confabulation verbatim at message_6 (assistant): *"The search returned no usable results. This confirms the pipeline gap we identified yesterday: the Reddit fetcher…"* — and prior Obs-17 stale-journal turns at messages 2/4.

That megaprompt was **built but never sent**: the `honest_empty_reply` branch short-circuited to the clean focused reply. So the clean-desk path produced an honest answer **despite the polluted history sitting in the assembled prompt.** This is the focused-cognition thesis proven live — the clean desk defeats the competing prior even when the prior is present.

## Flags (neither blocks this fix; both pre-tracked)

1. **Polluted history persists.** The earlier scope probe's "pipeline gap" confabulation lives in the conversation record, and the **legacy megaprompt path remains vulnerable to it for non-empty / continuity turns**. This is the broader-Blocker-A / polluted-history concern (canon `focused-cognition-over-megaprompt` point 10), out of scope for the empty-path fix.
2. **Wasted assembly.** The daemon builds the full megaprompt before the reply-decision branch short-circuits to honest-empty — wasted work on empty turns. Optimization opportunity, not a correctness issue.

## Verdict

**Mode A (daemon, the witnessed bug): live-witnessed GREEN.** Voice + CLI Mode B: source-verified (diff + source-inspection tests) but **not** live-witnessed this window (optional parity; the daemon owner-bridge path is what the owner exercises). Cross-lane diff verification (Claude): all production lines faithful, privacy intact, broad suite 5069 tests failures=2 (both pre-existing floor names, zero new).

**Merge gate satisfied.** Branch `honest-empty-evidence-path` is ready to merge to `main`.

## Service posture (close-out)

- Witness daemon 627045 ran the branch code under the unit, flag-absent. Resting-state decision (merge → run main, vs restore to pre-witness) recorded with the merge action.
