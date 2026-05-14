# Slice 3.0d — Evidence Envelope Token Budget Memo

**Status:** RATIFIED 2026-05-07 (commit ae179e9). Decisions in §8 are locked; departures require a memo amendment.
**Author:** Claude (drafted 2026-05-07)
**Companion docs:** [docs/ledger/envelope-schema.md](../../ledger/envelope-schema.md) §3, [docs/ledger/2-5c-acceptance.md](../../ledger/2-5c-acceptance.md)
**Anchor in code (not yet edited):** `daemon/maez_daemon.py` ~L1711–1780 (memory recall cap + sys-prompt construction)

---

## 0. Why this memo exists

Slice 3 will inject a structured evidence envelope into the daemon's reply prompt. Today's prompt already crowds the 32K llama.cpp context: `memory_block` is hard-capped at 60_000 chars (~15K tokens) precisely to leave headroom for soul, capability snippet, public bot context, web results, chat history, the user turn, and the response budget. A verbose envelope dropped on top of that stack will push past ctx and trigger silent truncation or generation failure.

This memo fixes envelope size discipline **before** the builder is written, so we don't retrofit caps after the first OOM.

---

## 1. Total budget

**Hard cap: 3_000 tokens for the rendered envelope.** (Configurable via env var; see §7.)

Budget arithmetic on a 32K context — **the 4K version overflowed** (see correction note below):

| Slot | Tokens |
|---|---|
| Soul / system prompt | ~3_000 |
| Capability snippet | ~1_500 |
| Public bot context | ~1_500 |
| Memory recall block (dynamic cap; see below) | ~13_000 |
| Web results (when present) | ~1_500 |
| Chat history + user turn | ~2_000 |
| **Evidence envelope (new)** | **~3_000** |
| Reply space (model output) | ~4_000 |
| Slack | ~500 |
| **Total worst case** | **~30_000** (fits in 32K) |

**Correction (2026-05-07 review):** the original draft proposed 4K envelope + 15K recall + everything else, which summed to ~33K — overshooting the 32K context. The fix has two coordinated changes:

1. **Envelope hard cap reduced to 3K** (was 4K). Operating envelope per §2 is still ~1.9K, so the cap remains a safety ceiling.
2. **Recall cap dynamically reduces to 13K (~52_000 chars) when an envelope is present.** The slice-3-proper recall builder must enforce `MAEZ_RECALL_CAP_WITH_ENVELOPE_CHARS` (default 52_000); the existing 60K-char cap stays as the no-envelope fallback. Reduces recall headroom by ~2K tokens to make room for the envelope without squeezing reply space.

Without one of these changes, the prompt overflows in the worst case. Chose the smaller envelope cap because: (a) the operating envelope already fits comfortably in 3K; (b) recall is the older, more entrenched system; (c) reply space is sacred and can't be reduced.

Budget is enforced even when recall is at its 13K-with-envelope cap. **Truncation order matters more than the maximum** — see §3.

---

## 2. Per-section caps

Caps are stated in **char** (O(1) length checks) with token estimates at ~4 chars/token. Token-accurate counting is rejected at this layer; see §8.

| Section | Max entries | Per-entry char cap | Section char cap | Section token est. |
|---|---|---|---|---|
| `tool_results.summary` | 8 | 200 | 1_600 | ~400 |
| `claimable` | 15 | 100 | 1_500 | ~375 |
| `forbidden` | 8 | 80 | 640 | ~160 |
| `self_history` | 5 | 200 | 1_000 | ~250 |
| `signals_present` | 12 | 30 | 360 | ~90 |
| `signals_absent` | 12 | 30 | 360 | ~90 |
| `perception` brief | — | — | ~2_000 | ~500 |
| **Total** | | | **~7_460** | **~1_865** |

Budgeted total is well under 3K, intentionally. The 3K cap is the **safety ceiling**; the per-section caps are the **operating envelope**. Headroom absorbs: schema framing tokens, JSON delimiters, future fields, and per-entry variance.

Numbers are calibrated against today's prompt slots: capability snippets are ~1.5K tokens, web-search summaries are ~1.5K tokens, so the envelope at ~1.9K tokens sits in the same weight class as existing structured blocks — visible to the model, not dominant.

---

## 3. Truncation order

When a turn produces more evidence than fits, sections are truncated in this order. Stop as soon as the envelope fits the 3K cap.

1. **`tool_results[i].summary` body.** Keep `name` and `status` (ok/empty/timeout/error). Truncate body content first. Status is the load-bearing field; the body is contextual.
2. **`claimable`.** Drop oldest entries first; keep the most recent N. Recency proxies relevance for a single-turn envelope.
3. **`self_history`.** Drop oldest turns first. Recent self-history dominates for continuity.
4. **`forbidden`.** Preserve all. Forbidden facts are smallest per byte and have the highest signal-per-byte (they prevent hallucination — the failure mode this whole stack exists to suppress).
5. **`signals_present` / `signals_absent`.** Preserve all. Compact, load-bearing for audit Pass 2.

Rationale: drop **bulk first, signal last**. tool_result bodies are bulk; forbidden + signals are signal.

### 3a. Emergency minimal-envelope fallback

If steps 1-5 still leave the envelope over cap (pathological case: hundreds of forbidden entries + maximum signals from a heavy-recall turn), the builder MUST construct a **minimal envelope** rather than emit something that blows the prompt. The minimal envelope itself enforces hard caps on every section so it is provably under budget:

```
{
  "schema_version": <int>,
  "_truncated": true,
  "_truncation_reason": "preserved-sections exceeded cap",
  "tool_results": [{name, status} for first MAX_FALLBACK_TOOLS that fit],   # capped: status-only
  "forbidden":    [{topic, reason} for first MAX_FALLBACK_FORBIDDEN that fit],
  "signals_present": [...first MAX_FALLBACK_SIGNALS chars worth that fit...],
  "signals_absent":  [...first MAX_FALLBACK_SIGNALS chars worth that fit...]
}
```

Suggested floor caps (subject to slice-3-proper tuning):
- `MAX_FALLBACK_TOOLS = 8` (status-only, no summary; ~30 chars per entry)
- `MAX_FALLBACK_FORBIDDEN = 8` (newest first; per-entry cap unchanged at 80 chars)
- `MAX_FALLBACK_SIGNALS = 480 chars total per signals_present + signals_absent` (combined)

These floor caps total roughly 2K chars (~500 tokens) — comfortably under any plausible envelope cap including a 3K token budget. The "ALWAYS under cap" claim is enforced by THESE floor caps, not by the structural shape alone — emitting unbounded `[for each tool_result]` could still overflow if a pathological turn produced thousands of tool calls.

If even the floor caps can't fit the configured `char_cap` (env-var override below practical minimum, e.g. `MAEZ_EVIDENCE_ENVELOPE_BUDGET_TOKENS=10`), the builder logs ERROR and emits an empty `{"schema_version": N, "_truncated": true, "_truncation_reason": "envelope unrenderable"}` so the daemon's prompt-builder has a deterministic shape to consume.

Telemetry on the minimal-envelope path is WARNING-level (see §4) — but with `truncation_kind="minimal_fallback"` so operators can grep for it specifically.

---

## 4. Telemetry on truncation

Every cap that bites emits a structured WARNING log line. Silent truncation is the "stuff disappeared mysteriously" failure mode. Operators must see when caps bite to tune them.

**Required fields per log** (consolidated with §7 — operators tuning the budget see both axes; if real-world token counts diverge from the chars/4 approximation, the discrepancy is visible):

- `turn_id`
- `section` (e.g. `tool_results`, `claimable`)
- `truncation_kind` — one of: `per_section_cap`, `total_cap`, `minimal_fallback`. Lets operators grep specifically for the emergency fallback path (§3a).
- `dropped_entries` (count) and `dropped_chars`
- `envelope_chars_before` and `envelope_chars_after`
- `envelope_tokens_estimated_before` and `envelope_tokens_estimated_after` (chars / 4, rounded)
- `char_cap` and `token_cap` — both the resolved char_cap (after env override + conversion) and the source `token_cap` it was derived from
- `cap_hit` — which limit triggered: per-section, total, minimal-fallback

Pseudocode:

```
WARNING maez.envelope envelope_truncated
  turn_id=... section=tool_results
  truncation_kind=total_cap
  dropped_entries=3 dropped_chars=1840
  envelope_chars_before=18204 envelope_chars_after=16364
  envelope_tokens_estimated_before=4551 envelope_tokens_estimated_after=4091
  char_cap=12000 token_cap=3000
  cap_hit=total
```

Decided (§8): logger name is **`maez.envelope`** — new purpose-specific logger, precedent set by slice 1.2's `core.cognition.grounding_judge`.

---

## 5. Compression rule for `tool_results.summary`

Tool outputs (web search, calendar, file read) routinely exceed 200 chars. The compressor:

- **Structured (JSON / dict):** keep keys, truncate each value past ~80 chars with `…`.
- **List of items** (search results, calendar events): keep `N=3` items, append `(+M more dropped)`.
- **Free-form text:** head-truncate to 200 chars + `…`.
- **Always preserved:** `tool_results[i].status`, `tool_results[i].name`, `tool_call_id`. The body summary is best-effort; the metadata is contractual (audit Pass 2 reads `status` to weight provenance).

---

## 6. Where enforcement lives

The **envelope BUILDER** owns caps and telemetry. The prompt formatter renders what the builder hands it — no additional truncation downstream.

Spec:

- A single `BoundedEnvelopeBuilder` class.
- Class-level `MAX_*` constants (one per cap above) so audit can read them.
- Single `build(...)` entry point: collects raw evidence → applies §3 truncation in order → emits §4 telemetry → returns a serializable `EvidenceEnvelope` (per LEDGER_ENVELOPE_SCHEMA §3.1).
- Builder also stamps `envelope_chars_final` into the returned object so the ledger row records actual delivered size, not just the cap.

This separates "what was decided" (builder) from "what was rendered" (formatter), which the ledger wants to record distinctly.

---

## 7. Off-switches and char↔token conversion rule

Two env vars, both honored by Slice 3 proper:

- `MAEZ_EVIDENCE_ENVELOPE_BUDGET_TOKENS` — overrides the 3K total cap (default `3000`). The env var is named in **tokens** for operator clarity; internal enforcement converts to chars (see below).
- `MAEZ_EVIDENCE_ENVELOPE_DISABLED=1` — skip envelope construction entirely. Bypass for emergencies (model regressing under envelope pressure, builder bug discovered in production). Slice 3.0d's job is to **declare** these knobs; Slice 3 proper implements them.

### Conversion rule: tokens → chars

The env var is a token budget; the builder enforces in chars (O(1), no tokenizer round-trip per build). The conversion factor is fixed:

```
chars_per_token = 4    # rough approximation for the
                       # llama-cpp Qwen tokenizer; tighter
                       # estimates available via tokenizer
                       # round-trip but that latency is not
                       # justified at this layer.
char_cap = token_budget * chars_per_token
```

So `MAEZ_EVIDENCE_ENVELOPE_BUDGET_TOKENS=3000` → `char_cap = 12_000`.

Telemetry on truncation must log BOTH chars and estimated tokens — full field list is consolidated in §4 above (single source of truth for the log shape).

If a future slice introduces tokenizer-backed counting (real round-trip per build), this conversion rule becomes the fallback for cold-start / no-tokenizer cases.

---

## 8. Decisions (ratified 2026-05-07)

The four open questions from the prior draft are decided as follows.
Slice 3 proper builds against these answers; departures require a new
memo amendment.

1. **Total envelope budget → 3K.** Original 4K draft overflowed the
   32K llama.cpp context (~33K total). 3K with a 13K-token recall cap
   keeps worst-case prompts at ~30K, preserving reply space and slack.
   Operating envelope per §2 is still ~1.9K, so 3K remains a safety
   ceiling, not an operating target.

2. **Char approximation → ACCEPTED.** Memo uses `chars / 4` per §7
   for the token estimate. Telemetry logs both axes (§4). Revisit if
   real-world telemetry shows divergence >25% between estimated and
   actual token counts (would indicate the Qwen tokenizer is producing
   a meaningfully different ratio than `*4`). No tokenizer round-trip
   in the per-build path until that signal appears.

3. **Logger name → `maez.envelope`** (new logger). Slice 1.2's
   `core.cognition.grounding_judge` set the precedent for adding
   purpose-specific loggers when there's a distinct operator-grep
   signal. Envelope truncation telemetry has its own grep needs
   (audit-team operators tuning caps) and shouldn't dilute
   `maez.cognition`'s broader signal.

4. **Recall cap with envelope present → 52K chars (13K tokens),
   ACCEPTED.** Reduction of 8K chars (~2K tokens) from the existing
   60K cap is the smallest change that makes the budget math fit a
   3K envelope without squeezing reply space. (Earlier draft of this
   bullet said "~3K chars" — that was wrong; 60K − 52K = 8K chars.
   The §1 budget table is correct.) The existing 60K cap stays as the
   no-envelope fallback (i.e. when `MAEZ_EVIDENCE_ENVELOPE_DISABLED=1`
   the recall builder uses 60K). Slice 3 proper implements the
   conditional; the env var to override is
   `MAEZ_RECALL_CAP_WITH_ENVELOPE_CHARS` (default 52_000).
