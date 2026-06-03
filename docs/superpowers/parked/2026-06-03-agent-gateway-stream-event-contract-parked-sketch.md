# Agent→Gateway Typed Stream-Event Contract (PARKED sketch)

**Date:** 2026-06-03
**Status:** PARKED — for **Codex review**, batched with [the self-extending-senses / MCP sketch](2026-06-03-self-extending-senses-personal-data-ingestion-parked-sketch.md). Discussion-only. NOT specced, NO build until brainstorm → spec.
**Trigger:** Owner (Rohit) flagged an external PR as "better streaming for Maez." Captured so the pattern isn't lost.

---

## 1. Source (verified real)

**NousResearch/hermes-agent PR #37250** — `feat(gateway): structured stream-event protocol + Telegram draft formatting parity`. Author **teknium1** (Nous founder). **Merged 2026-06-02**, MIT license, 740+ lines / 8 files / with tests. (Verified via GitHub API — repo + PR exist; the WebFetch summary that first surfaced it was accurate, not confabulated. Skepticism was warranted given the PR number and Maez-shaped summary, but cleared.)

Repo context: `hermes-agent` = "**the agent that grows with you**", **~177k stars**, Python, MIT — one of the most-starred repos on GitHub, building Maez's *exact* vision (grows-with-you, self-evolution, plugin layer) at massive scale. Sibling repos: `hermes-agent-self-evolution`, `hermes-example-plugins` (MIT connector-pattern borrow-source — relevant to the senses sketch), `hermes-paperclip-adapter`.

## 2. What the PR actually does

A typed **agent→gateway event contract** ("smart-agent / smart-gateway split"):
- **`stream_events.py`** — typed vocabulary: `MessageChunk`/`MessageStop`, `Commentary`, `ToolCallChunk`/`ToolCallFinished`, `LongToolHint`, `GatewayNotice`.
- **`stream_dispatch.py`** — `GatewayEventDispatcher` routes events through a platform adapter onto the stream sink + tool-progress queue. Adapters can return `None` to **eat events they can't render** (e.g. tool chrome on plain-text platforms).
- **`platforms/base.py`** — default render hooks reproduce existing behavior **1:1** (no behavior change out of the box).
- **`platforms/telegram.py`** — `send_draft` applies MarkdownV2 with a plain-text fallback on `BadRequest`, so the animated draft renders identically to the final message (fixes "raw text then snaps to MarkdownV2").
- **`config.py`** — default streaming transport `edit` → `auto` (prefer native draft over edit).

Principle: **the gateway owns per-platform rendering; the agent only emits semantic events.** Native per-platform rendering is opt-in for follow-up; the base reproduces today's output exactly.

## 3. Owner read + honest calibration

Owner: "better streaming for Maez." **Calibration:** it's better streaming *presentation/rendering* + a cleaner brain↔surface boundary — NOT faster token throughput. The headline value is the **typed agent→gateway boundary**; the Telegram draft-formatting fix is a *consequence* of that boundary, not the core.

## 4. Why it's relevant to Maez (3 mappings)

1. **It's [[feedback_brain_is_one_part_tool_calling_substrate_side]] formalized as a typed contract.** "Agent emits semantic events; gateway owns surface rendering" = brain stays swappable, substrate owns the surface. Maez already has both halves (`core/routing/brain_gateway.py` + `skills/telegram_voice.py`) but the **boundary is not a clean typed event vocabulary** — this is a borrowable *shape* that hardens exactly that seam.
2. **Maez is in the same surface space.** `telegram_voice.py` already uses MarkdownV2 + chunking; there's a `brain_gateway`. Patterns transfer directly. **OPEN ITEM (not yet verified):** does Maez's Telegram draft path actually have the "raw-then-snaps-to-MarkdownV2" defect their `telegram.py` fixes? Worth a check before assuming.
3. **Their typed vocab ≈ Maez's visible-substrate-state receipts** ([[feedback_visible_substrate_state_not_chain_of_thought]]). `Commentary` / `ToolCallChunk` / `LongToolHint` / `GatewayNotice` are a parallel formalization of "show real substrate STATE, not performed thought." Maez's receipts must stay true-by-construction if this is adopted.

## 5. Borrow rule + covenant caution

[[project_external_borrow_rule]] — **borrow the shape, not the philosophy.** The repo's topics include `openclaw`, `clawdbot`, `moltbot` — the *full-access personal agent* lineage the safety-analysis genre ("your agent, their asset") forms around. The typed gateway event-contract is genuinely excellent and borrowable; the broad-access agent philosophy is NOT Maez's. Maez stays honest-ingestion / scoped / refusable / sovereign. Convergent evolution here is *validating* (the most popular OSS agent independently arrived at the same gateway-split + grows-with-you architecture), not a signal to copy wholesale.

## 6. Open questions for Codex

- Should Maez adopt a typed agent→gateway event contract for `brain_gateway` ↔ surfaces (Telegram/UI/voice)? What's the minimal vocabulary for Maez's actual surfaces?
- Does Maez's Telegram draft path share the raw-then-snaps defect? (verify before building)
- Does the event contract compose cleanly with Maez's existing visible-substrate-state receipts + content-free telemetry, without smuggling performed-thought back in?
- Is `hermes-example-plugins` (MIT) worth studying as a connector-pattern borrow-source for the senses sketch?
- Priority vs the existing organ roadmap ([[project_organ_roadmap]]) — surface polish vs deeper organs.

---

**Next action:** Owner runs this by Codex once, alongside the senses/MCP sketch. Review the *thinking + the borrowable pattern*, not a plan to execute.
