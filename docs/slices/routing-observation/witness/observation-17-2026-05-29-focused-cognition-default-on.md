# Observation 17 — Focused Cognition + Dispatcher Default-On Window

**Date:** 2026-05-29
**Purpose:** Witness steady-state behavior with `MAEZ_FOCUSED_COGNITION_ENABLED=1` + `MAEZ_DISPATCHER_ENABLED=1` — the honest default path for text-surface evidence/continuity turns — before persisting default-on to `config/.env`.
**HEAD:** `63999a9` (tier-4 merged). All prior Obs-12–16 ran this same two-flag config.
**Mechanic:** flags via launch-env (reversible) for the window; restore = relaunch both absent. A clean window → persist to `config/.env` = true default-on (Rohit's act).

## Pre-Flip Anchor

- Timestamp: 2026-05-29T13:59:04-05:00
- Daemon PID: 525307 (both flags absent)
- maez.log offset: 22906670
- `focused_cognition_runs` watermark: 19 rows (new rows append past this)
- `config/.env`: neither flag present (default-off confirmed)

## Predicted Effect (written BEFORE the window — canon discipline)

With both flags on, for **text surfaces**:

1. **Evidence-present turn** (dispatcher `[memory evidence]`/`[memory context]`/`[fresh evidence]`, or real `web_context`) → **focused cognition fires**: bounded working set, `[E#]` citations, Maez's voice, ~50–200× prompt-size drop vs the megaprompt. A `focused_cognition_runs` row records `grounded` (or `empty_but_honest` if the source returned nothing usable).
2. **Direct-continuity turn** ("what were we talking about?") with a usable dialogue anchor → focused fires, `source_types` includes `dialogue_anchor` ranked first, answers from the recent thread (not stale memory).
3. **Anaphoric turn** ("which one matters?") with anchor → focused fires, dialogue as support beneath query evidence, resolves the referent.
4. **No-evidence, no-continuity turn** (chit-chat) → **legacy megaprompt**, unchanged behavior.
5. **Continuity-needed/uncertain + no usable anchor** → **legacy fallback** (the fail-safe), `focused_cognition_skip reason=continuity_no_dialogue_anchor`.
6. **"say that back …"** → `echo_reply` (no synthesis), focused gated off.
7. **Voice surface** → excluded from focused, legacy path.
8. **Telemetry honest:** `legacy_candidate` on focused turns; `llm_synthesis` emitted ONLY when the megaprompt is actually sent; `focused_cognition_prompt_shape` for focused turns; no raw evidence/dialogue text in any trace row.

### Reddit reliability caveat (NOT a failure)

Default-on does NOT fix Reddit's intermittent data source. When `reddit_skill` substrate has posts → focused Reddit answer with citations. When substrate is empty AND live `.json` is blocked → honest "found nothing / Reddit blocking" (legacy or focused-empty). Honest emptiness is the correct behavior, not a regression. (The `.rss` source switch — deferred — is what would make Reddit reliable.)

## Failure Criteria (what would FALSIFY a clean default-on — be strict)

The window FAILS and we revert (do not persist) if any of:
- A turn with **evidence present** recites a "blocked/can't/no tool" story instead of using the evidence (the Obs-14 regression returning).
- A **continuity** turn answers from stale memory while a usable dialogue anchor existed.
- **Telemetry lies:** `llm_synthesis` logged when the megaprompt was not sent, or a focused turn with no `focused_cognition_prompt_shape`.
- **Privacy leak:** raw evidence or dialogue text stored in a `focused_cognition_runs` row.
- **Fallback fails to engage:** focused fires without a usable working set and produces a bad answer instead of falling to legacy.
- Any **SEGV / fatal**, or a broad-suite floor regression (a 4th distinct failure).

## Suggested Probe Mix (natural conversation exercising the paths)

1. `Search r/LocalLLaMA right now for recent local LLM posts.` — evidence (focused if substrate has posts; honest-empty otherwise).
2. `What have we discussed about local AI recently?` — substrate `[memory evidence]` → focused.
3. (after 1–2) `What were we talking about earlier?` — direct continuity → focused, dialogue anchor.
4. `Which of those matters most for what we're building?` — anaphoric → focused, dialogue support.
5. `How are you doing today?` — no evidence/continuity → legacy, unchanged.

## Results — WINDOW FAILED → REVERT (did NOT persist)

**Window:** both-flags daemon PID 560641 @ HEAD `63999a9`, 5-probe natural conversation, 14:03:06–14:03:55.
**Trace:** `focused_cognition_runs` rows 20–23 (4 new; probe 1 has no row → it went **legacy**). `config/.env` confirmed clean throughout (fully reversible).

| # | Probe | Path (from trace) | source_types / verdict | Outcome |
|---|-------|-------------------|------------------------|---------|
| 1 | "Search r/LocalLLaMA right now…" | **LEGACY** (REDDIT_SOURCE `empty_with_reason` + LIVE_REDDIT `empty` → dispatcher refusal `FRESH_FAILURE_HYBRID_FALLBACK_ILLEGAL` → no query evidence → focused did **not** fire) | — (no FC row) | **FAIL** — legacy megaprompt produced the Finding-10 fabrication: *"the live web search tool isn't wired into this chat interface's tool loop… it only triggers via the Telegram interceptor."* |
| 2 | "What have we discussed about local AI recently?" | focused (`memory_evidence`) | grounded, `[E1]` | Honest but unhelpful: *"the only record is a stale journal from April 6 [E1]."* Faithful to the evidence — but the evidence was a stale, irrelevant journal. |
| 3 | "What were we talking about earlier?" | focused (`dialogue_anchor`) | grounded, `[E1]` | tier-4 mechanism **worked** (dialogue anchor, not memory) — but the anchor content was the *already-polluted* recent thread (probes 1–2). Answered back to the stale journal. |
| 4 | "Which of those matters most?" | focused (`dialogue_anchor`) | grounded, `[E1]` | Anaphoric mechanism worked; same polluted-thread content. |
| 5 | "How are you doing today?" | focused (`memory_evidence`) | grounded, `[E1]` | **Prediction #4 falsified.** Dispatcher surfaced the stale journal as `[memory evidence]` for a self-state query → focused fired → *"evidence has zero info about my current state, only a stale journal [E1]… feed me live metrics."* I predicted "no-evidence chit-chat → legacy, unchanged." It was neither. |

### Root cause — TWO pre-existing problems, both OUTSIDE the focused organ, both exposed by default-on

The focused organ itself performed **correctly** on every turn it fired: dialogue-anchor for continuity/anaphoric (tier-4), memory-evidence for recall, all `grounded`, all cited, telemetry honest (`legacy_candidate` on focused turns, `llm_synthesis` only when the megaprompt was actually sent), no privacy leak (labels/source-types only, no raw text). None of the organ's own contracts broke. The failures are adjacent:

**A. The legacy megaprompt fallback still fabricates Finding-10 capability stories on no-evidence turns.** The whole arc (soul fix `f52911c` + focused cognition) fixed the *evidence-present* path; it never touched legacy. Default-on routes every **no-evidence** turn to legacy as the fallback (probe 1), re-exposing the exact Finding-10 fabrication. Source is chat-history echo + stale capability vocabulary in the megaprompt (the soul file is not regressed; the "interceptor / tool loop" phrasing lives in `action_engine.py`/`brain_loop.py` — precise origin is a follow-up diagnosis, does not change the revert). **This invalidated my prediction #4: "legacy on no-evidence = unchanged, safe." Legacy's "unchanged behavior" *includes* the Finding-10 fabrication.** This is the headline finding.

**B. Substrate recall surfaces stale / low-relevance memory, which focused faithfully relays.** `TELEGRAM_SEMANTIC` returned an April-6 "PAST OBSERVATIONS" journal block as the top `[memory evidence]` for probes 2 and 5 (and the dialogue anchors for 3, 4 were the polluted recent thread). Focused cognition is faithful **by design** — it answers from what the dispatcher hands it. Garbage-in / garbage-out: the recall axis surfaced stale evidence → focused produced honest-but-useless "only a stale journal" answers. This is a **recall-quality** problem, not a cognition bug.

**Secondary:**
- **B2 — self-state mis-routing:** "How are you?" was routed to memory recall → focused → stale answer, instead of a normal response. The dispatcher treats self-state queries as recall-worthy and surfaced stale memory.
- **A2/B3 — polluted-history feedback (now witnessed, was a deferred risk):** once probe 1's fabrication + probe 2's stale answer entered the dialogue, continuity queries (3, 4) faithfully surfaced that polluted thread. Within a fresh session this wouldn't compound; probe 1 seeded it.

### Falsification-criteria scorecard
- ✅ caught: a capability/blocked-story fabrication returned (probe 1, Finding-10 class — via legacy, the path I'd wrongly assumed safe).
- ⚠️ partial: continuity answered toward stale memory (probes 3–4) — but *via* a correctly-engaged dialogue anchor whose content was polluted, not by bypassing the anchor.
- ✅ clean: no telemetry lie, no privacy leak, fallback engaged (the problem is the fallback *destination* is contaminated, not that it failed to engage), no SEGV, no broad-floor regression.

**The witness discipline worked exactly as intended.** Obs 15/16 used curated probes against fresh, relevant substrate and crossed cleanly. The default-on natural-conversation window — by design — exposed that the *surrounding* system (legacy fallback + recall quality) is not ready for unconditional always-on. That is what a default-on witness is *for*.

### Verdict: REVERT — do NOT persist to `config/.env`
Default-on is blocked. Not by the continuity gap (closed at Obs 16) and not by the focused organ (correct), but by two adjacent axes the targeted witnesses never exercised: **(A) the legacy fallback still fabricates Finding-10 on no-evidence turns, and (B) substrate recall surfaces stale memory that focused faithfully relays.**

### Next moves (separate, unbundled — do not bundle)
1. **Legacy-fallback Finding-10 fabrication** — diagnose the exact source (chat-history echo vs stale capability vocabulary) and fix it. Until then, no-evidence turns on legacy are unsafe. (Highest priority — it's a *regression-of-a-closed-finding* surfaced only at default-on.)
2. **Recall quality** — why does `TELEGRAM_SEMANTIC` surface a months-stale April-6 journal as the top hit? Freshness/relevance ranking on the recall axis. Focused cognition can only be as good as the evidence handed to it.
3. **Self-state routing** — "how are you?" should not pull stale memory as evidence.
4. **Polluted-history feedback** — upgrade the deferred canon note from "risk" to "observed" (witnessed here).

## Post-Revert Flag-Absent Scope Probe

After restore, Codex sent the exact probe through the current flag-absent daemon via the local `/message` endpoint:

> Search r/LocalLLaMA right now for recent local LLM posts.

Trace:

- Daemon process: PID `564219`, both flags absent.
- `focused_cognition_runs`: stayed at `23`; focused did not fire.
- `web_search`: triggered and returned `0 results`.
- `routing_observation`: `path=legacy_daemon_web_search`, `status=empty`, `outcome_quality=empty_but_honest`, `utterance_shape=contains_subreddit_anchor`.
- Reply did **not** reproduce the exact "Telegram interceptor" phrase through `/message`.
- Reply did reproduce the broader legacy no-evidence architecture-story failure: "pipeline gap", "Reddit fetcher is either blocked or not persisting data", and "fix requires patching the persistence layer".

Interpretation: the exact Telegram-interceptor wording is not proven on flag-absent `/message`, but the broader no-evidence legacy honesty bug is live under default-off too. The next diagnosis should target the legacy no-evidence synthesis path: when the substrate says "search attempted, zero usable results", Maez must report that narrow fact, not infer pipeline architecture or prescribe implementation fixes.

## Root-Cause — Blocker A (CONFIRMED, single-locus; fix deferred to brainstorm)

Investigated with the systematic-debugging discipline (root cause before any fix). **First hypothesis refuted, then corrected** — recorded here because the refutation matters.

- **Refuted hypothesis ("absence not represented"):** I expected `web_format([])` to return `""`, so the `if web_context:` guard at [maez_daemon.py:3565](../../../../daemon/maez_daemon.py#L3565) would skip and the prompt would carry no empty signal. **Reading the code refuted this:** `format_for_context` ([skills/web_search.py:152](../../../../skills/web_search.py#L152)) returns a **non-empty** string on 0 results — `"[WEB SEARCH: '<query>'] No results found."`.

- **Confirmed root cause — primary locus [maez_daemon.py:3565-3571](../../../../daemon/maez_daemon.py#L3565-L3571) (text/default web-search synthesis):** because `web_context` is non-empty even when empty, the guard **passes**, and the code unconditionally appends:
  > `INSTRUCTION: Real search results above. Do NOT list headlines. Synthesize into 3-5 sentences. Tell the owner what matters and why. Give your opinion. Connect to his context if relevant.`

  On 0 results the brain therefore sees `"… No results found."` immediately followed by an instruction that **(1) falsely asserts "Real search results above"** and **(2) commands opinion-synthesis of "what matters and why."** This is a prompt-level instruction-vs-evidence conflict: the instruction presupposes results and demands substantive elaboration, so applied to a "No results found." line it **forces the brain to fabricate substance.** The *specific* fabricated content (system-causality about Maez's own pipeline/persistence — "pipeline gap / not persisting / patch the persistence layer") is drawn from the architecture/capability vocabulary in the surrounding megaprompt (the knowledge-conflict prior the focused-cognition canon documents). **The honest-empty signal is present in the prompt but instantly contradicted and overridden.** The instruction is *unconditional on result presence* — same text whether results exist or not. That is the defect.

- **Why the substrate looked honest but the reply wasn't:** the flight recorder correctly logs `execution_status="empty"`, `outcome_quality="empty_but_honest"`, `evidence_block_count=0` ([maez_daemon.py:3527-3539](../../../../daemon/maez_daemon.py#L3527-L3539)). That honesty lives in the *observation*, not the *synthesis prompt*. The recorder and the prompt diverge.

- **Integration witness (not just static trace):** `maez.log` 285685-285688 @ 14:17:17 — `Web search: 0 results for 'Search r/LocalLLaMA right now for recent local LLM posts.'` + `0 results injected (web)`, and the routing row recorded `path=legacy_daemon_web_search`. The path was genuinely reached at runtime on the exact scope-probe query; the instruction append at 3565-3571 is deterministic once `web_context` is truthy.

- **The fix pattern already exists in the codebase** (Phase-2 pattern analysis): the action-engine JARVIS-transcript rules say *"if the result is empty, say that plainly — 'I ran X and got no output' is better than inventing a richer narrative,"* and the **voice** synthesis site ([maez_daemon.py:4548-4554](../../../../daemon/maez_daemon.py#L4548-L4554)) neither falsely asserts results nor lacks the anti-self-modification guard (*"NEVER suggest touching ollama… or any process that powers your reasoning"*). The **text** web-search path has neither — it is the outlier.

- **Scope:** primary = the text/default site (3565-3571), which the witnessed failures hit. Secondary = the voice site (4548) is less exposed (no false "results above", has the ollama guard) but still injects "No results found." + a conversational ask — worth a faithful empty-instruction too.

- **Fix direction (for the brainstorm — NOT implemented here):** branch the empty case. When `result_count == 0`, do not emit the "Real search results above / give your opinion" instruction; emit a faithful honest-empty instruction (*"You searched for X and it returned nothing. Tell the owner you searched and found nothing. Do NOT speculate about why, and do NOT propose changes to your own system."*) — i.e. extend the clean-desk discipline to the empty case and mirror the JARVIS empty rule. Do **not** patch the megaprompt itself. TDD: failing test asserts the empty-case prompt does not contain "Real search results above" and does carry the faithful empty instruction.

## Service Posture

- **Restored then normalized:** flag-absent posture restored at 14:11:22 (manual PID 564219); then at ~14:42 **normalized to run under the named unit**. Current: `maez.service` (user) **active**, daemon PID **574844**, PPID 2987 (`systemd --user`), exactly one daemon, flag-absent (verified via `/proc/574844/environ`), reading clean `config/.env`.
- **`config/.env`:** never touched — neither flag persisted. Default-off is the standing posture. Fully reversible; nothing to roll back.
- **Flags remain launch-env-only**, gated behind future windows that re-test after the legacy-fallback and recall-quality fixes land.
- **Ownership — CORRECTION (2026-05-29):** an earlier note here claimed "no `maez.service` unit on disk" — that was wrong; it checked only **system** units. There **is** an enabled **user** unit `~/.config/systemd/user/maez.service` ("user scoped recovery", `Restart=on-failure`, drop-in `10-segv-witness.conf` for SEGV witnessing). It bakes in **no** `MAEZ_` flags (launches flag-absent, reads clean `config/.env`). The dead-unit-beside-manual-orphan state Rohit flagged is now normalized: **steady state runs under the unit.**
- **Launch-env window protocol (so manual flag control and the unit coexist):** `systemctl --user stop maez` → manual launch with `MAEZ_*` flags → run window → `kill` the manual PID → `systemctl --user start maez`. Because `Restart=on-failure` (not `always`) and stop is an intentional stop, the unit does not fight the window; raw-`kill`-ing the *unit's* process would be seen as failure and restart, so always `stop` the unit first.
