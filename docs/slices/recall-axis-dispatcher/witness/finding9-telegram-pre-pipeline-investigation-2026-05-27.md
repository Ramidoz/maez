# Finding 9 Investigation — Telegram Pre-Pipeline Web-Search Trigger

**Status:** diagnostic witness, no code change. Decision required before fix.
**Date:** 2026-05-27
**Predecessor witness:** `docs/slices/recall-axis-dispatcher/witness/external-source-observation-2026-05-27-telegram.md` (commit 5de8739)
**Investigation method:** static code trace (grep + read), no live reproduction needed — the cause is structurally apparent from the source.

## Headline Finding

**The "Web search triggered" log lines do not come from a post-dispatcher fallthrough. They come from Telegram's own parallel recall+tool pipeline at `skills/telegram_voice.py:3362-3370`, which runs INDEPENDENTLY of `run_brain_loop`'s dispatcher path.**

Telegram has **two recall+tool pipelines** that both fire for the same owner message:

- **Pipeline A — Telegram's surface pre-pipeline** (`skills/telegram_voice.py:3344-3370`): builds its own perception snapshot, calls `recall_for_telegram()` directly, calls `format_for_prompt()` for the memory block, then checks `needs_web_search(user_text)` and directly invokes `web_search()` or `search_rss()` if the trigger fires. This is the source of the "Web search triggered" log line at line 3364.

- **Pipeline B — Dispatcher path via `_run_jarvis_loop`** (`skills/telegram_voice.py:3030-3081`): delegates to `core.brain_loop.run_brain_loop(...)` which, when `MAEZ_DISPATCHER_ENABLED=1`, fires Layer 0 → Layer 2 → Layer 1 + ExternalFanout → merge → render. This is the path the dispatcher witnesses have been exercising.

Both pipelines run for the same Telegram message. The dispatcher's external-source authority is not honored by Pipeline A — `needs_web_search` makes its own substring-trigger decision independent of Layer 0's emission and ExternalFanout's audited egress route.

## Code Evidence

**Pipeline A — pre-pipeline web_search trigger** (`skills/telegram_voice.py:3362-3370`):

```python
web_context = ""
if needs_web_search(user_text):
    logger.info("Web search triggered for: %s", user_text[:80])
    if is_news_query(user_text):
        sr = search_rss(user_text, max_results=5)
    else:
        sr = web_search(user_text, max_results=3)
    if sr.get("success"):
        web_context = web_format(sr)
```

**`needs_web_search` trigger list** (`skills/web_search.py:296-311`): substring match against the owner utterance for `news`, `latest`, `current`, `today`, `now`, `recent`, `weather`, `price`, `stock`, `search`, `look up`, `find out`, currency words, etc. The witness's probe utterance ("Check r/LocalLLaMA right now for recent local LLM posts...") matched `now`, `recent`, and `search` — triggered.

**Pipeline B — dispatcher delegation** (`skills/telegram_voice.py:3070-3081`):

```python
return _brain_loop.run_brain_loop(
    user_text,
    action_engine=self.actions,
    get_pipeline=self._get_pipeline,
    user_id="rohit",
    chat_id=str(self.authorized_user),
    surface="telegram",
    ...
)
```

This is the path that emits `dispatcher_path_entry surface=adapter` in the witnesses.

## Why `actions.log` Delta Was Zero Bytes

`actions.log` is written by `action_engine` for tool calls routed through that engine. Pipeline A's `web_search()` call at `skills/telegram_voice.py:3368` is a **direct call into `skills.web_search.search(...)`** — it bypasses `action_engine` entirely. The diagnostics land in `external_fetch_diagnostics.jsonl` (since `web_search` goes through `external_fetch`) but never in `actions.log`. That's why the witness saw zero action-log delta despite "Web search triggered" appearing.

This is also why the prior "no-JARVIS-fallthrough" verdicts (all three daemon witnesses) held cleanly on `actions.log` delta — that signal correctly measures the action-engine tool path. It just doesn't measure Pipeline A's separate direct-call path.

## Classification

Per Rohit's investigation framing (carried from Finding 7 framing):

| Hypothesis | Result |
|---|---|
| Adapter construction issue | NO |
| Missing store/config | NO |
| Schema drift | NO |
| Timeout/deadline bug | NO |
| Caller-shape mismatch | PARTIAL — but the deeper shape is **two-pipeline architectural residue** |
| **Architectural residue** | **YES** — Telegram's pre-pipeline predates the dispatcher's external-source authority |

The dispatcher was built to be the single authority for fresh-source decisions (closed vocabulary, audited egress, subject-boundary preflight, no LLM-invented URLs, etc.). Telegram's `_handle_private_text` (or equivalent entry point) was built before the dispatcher existed and uses a substring-trigger that has none of those disciplines. Both pipelines now fire in parallel for every Telegram message.

## Why the Witness Saw "Web search triggered" AFTER `dispatcher_path_exit`

The observation log showed:

```text
dispatcher_path_exit surface=adapter ... turn_seal_state=clean ...
telegram_surface message: Check r/LocalLLaMA right now ...
Web search triggered for: Check r/LocalLLaMA right now ...
Web search: 0 results for ...
```

This means the dispatcher path (`_run_jarvis_loop` → `run_brain_loop`) fired BEFORE the Telegram surface's pre-pipeline section (lines 3344-3370). The exact entry-point ordering depends on which Telegram handler is dispatching — could be that `_run_jarvis_loop` is called early in `_handle_private_text`, then the pre-pipeline section runs after, OR there are separate entry points with different orderings.

Either way, the structural finding is the same: **two parallel pipelines, both running, both producing recall and tool calls, with no mutual awareness.**

## What This Means Operationally

For dispatcher-enabled Telegram turns:

- **Pipeline B (dispatcher) emits `[memory evidence]` or `[memory context]` substrate-only transcripts** (correctly, per v1.3 + Finding 8 fix once Finding 8 lands live).
- **Pipeline A then ALSO runs** `needs_web_search` trigger and directly calls `web_search`/`search_rss` whenever the owner utterance contains trigger substrings.
- Pipeline A's web result feeds into the larger Telegram reply-construction path (via `web_context` variable at line 3362).
- The dispatcher's transcript and Pipeline A's web_context likely get composed downstream into a single owner-facing reply.
- The "no-JARVIS-fallthrough" verdict held in past witnesses because we measured `actions.log`; Pipeline A's direct `web_search()` call doesn't write there.

This means the dispatcher closures (Reddit substrate-bypass, no-JARVIS-fallthrough, hybrid rendering) are honest at the dispatcher layer but **Pipeline A is silently doing its own external-source work** outside the audited dispatcher pipeline — including the subject-boundary preflight, closed-vocab failure taxonomy, and producer-causality discipline that the dispatcher invested in.

## Decision Options

### Option A — Make Pipeline A conditional on dispatcher-disabled

When `MAEZ_DISPATCHER_ENABLED=1`, skip the pre-pipeline `needs_web_search` block (lines 3362-3370). Dispatcher's external-source fan-out becomes the sole authority for fresh evidence. When disabled, Pipeline A keeps current behavior as the legacy fallback. Smallest patch, preserves rollback path.

**Pros:**
- Honors the dispatcher's external-source authority when flag is on.
- Mirrors the existing `should_run_jarvis=False` discipline from seam 7.
- No change to disabled-flag behavior; rollback is safe.
- Smallest code surface.

**Cons:**
- Pipeline A still exists as a parallel architecture path; future code touching Telegram's surface may add new tool calls there without dispatcher awareness.
- The flag-gated bypass doesn't fix the root architectural duality.

**Symmetric to:** seam 7's `should_run_jarvis=False` under dispatcher-enabled — the same shape applied to a different parallel pipeline.

### Option B — Fold Pipeline A into the dispatcher contract

Migrate `needs_web_search` logic into Layer 0 as a content-trigger selector (similar to the subreddit-anchor selector in seam 6). Remove Pipeline A's direct `web_search()` call entirely. The dispatcher's ExternalFanout becomes the single owner of all fresh-evidence retrieval.

**Pros:**
- Closes the architectural duality permanently. Single pipeline, single authority.
- All fresh-evidence retrieval gets the dispatcher's discipline (subject-boundary, closed vocabulary, producer-causality, audit envelope).
- Removes Telegram-specific code surface.

**Cons:**
- Larger change. `needs_web_search` trigger list has news/currency/weather/etc. categories that may need Layer 0 selector additions.
- Risk of behavioral regression — Pipeline A's `web_context` feeds into larger Telegram reply construction; removing it changes the downstream prompt shape.
- Needs review-ladder treatment as a slice, not a small seam.

### Option C — Refactor Pipeline A to route through `core.egress.external_fetch` AND the dispatcher's discipline

Keep Pipeline A's `needs_web_search` trigger but route the actual fetch through the dispatcher's adapter contract — subject-boundary preflight, closed-vocab failure mapping, producer-causality witnessing. Pipeline A still exists as a separate code path but produces dispatcher-honest results.

**Pros:**
- Preserves Pipeline A's current callers without changing the downstream reply-construction shape.
- Brings dispatcher discipline to Pipeline A without merging the two pipelines.

**Cons:**
- Most complex of the three. Hybrid architecture.
- Doesn't actually close the duality, just makes both pipelines honest about discipline.
- Two recall + two-web-search-checks per turn continues to be wasteful.

### Option D — Status quo with documentation

Accept that Telegram has two parallel pipelines. Document that dispatcher-enabled turns may see Pipeline A's web_search trigger as additional context separate from the dispatcher's audited path. No code change.

**Pros:**
- No code risk.

**Cons:**
- The dispatcher's external-source slice loses its meaning on Telegram. The Reddit substrate-bypass and no-JARVIS-fallthrough closures only hold at the dispatcher layer; the actual user-facing Telegram reply may include Pipeline A's untaudited web_search results.
- Every future Telegram observation will surface this same pattern. Carried-forward forever.

## Recommended Path

**Option A first, possibly Option B later.**

Option A is the smallest patch and is symmetric with seam 7's existing `should_run_jarvis=False` discipline. It immediately honors the dispatcher's authority when the flag is enabled, preserving the disabled-flag fallback. The patch is:

```python
# skills/telegram_voice.py around line 3362
import os
_dispatcher_enabled = os.environ.get("MAEZ_DISPATCHER_ENABLED", "0") == "1"

web_context = ""
if not _dispatcher_enabled and needs_web_search(user_text):
    logger.info("Web search triggered for: %s", user_text[:80])
    # ... existing logic ...
```

RED test: with `MAEZ_DISPATCHER_ENABLED=1` set in the test environment, the pre-pipeline `web_search` call must not fire. With the flag absent, current behavior preserved.

Option B is the right longer-term close (single-pipeline discipline), but it requires a review-ladder slice treatment because:
- `needs_web_search` triggers (news, currency, weather, etc.) may need Layer 0 selector growth, which is contract-level work
- Pipeline A's `web_context` is consumed downstream; removing it without folding into the dispatcher may break Telegram reply shape
- It overlaps with the deferred FRESH_ONLY total-failure deterministic summary path — both should land together

After Option A, the re-opened observation window verifies:
- Pipeline A no longer fires under dispatcher-enabled turns ("Web search triggered" absent from log delta)
- Dispatcher external-source path is the sole authority for fresh evidence
- Disabled-flag path still works as legacy fallback

Option B becomes a v2 or separate slice when the substrate landscape and Layer 0 selector vocabulary are ready to absorb the `needs_web_search` trigger surface.

## What Stays Out of This Investigation

- **Discovery of other Telegram parallel paths beyond Pipeline A.** Lines 3372+ show `_run_jarvis_loop`, `_propose_next_step_from_probe`, and other processing. Each may have its own tool surface; this investigation only traced the "Web search triggered" log line. Further Telegram parallel-pipeline audit may surface adjacent items.
- **`daemon/maez_daemon.py:3310` second occurrence** of the same log statement. The witness saw the Telegram-side occurrence; the daemon-side occurrence is a sibling but separate code path. Worth a follow-on grep if Option A doesn't suppress it.
- **Pipeline A's `recall_for_telegram` call vs dispatcher's Layer 1 substrate fan-out.** Both pipelines call substrate recall independently. This is duplicated work but not a discipline violation per se — substrate reads are read-only and idempotent. Worth noting for future optimization but not blocking.

## Verdict

Finding 9 is **a two-pipeline architectural residue**, not a fallthrough bug. The dispatcher closures from the slice arc hold honestly at the dispatcher layer; Pipeline A's parallel pre-pipeline silently runs unaudited external-source work in parallel. The actions.log was correctly measured but didn't catch this because Pipeline A bypasses action_engine.

Rohit's decision drives the next move. Option A is recommended as the smallest honest patch that immediately honors dispatcher authority. Option B is the right v2-slice shape if the architectural duality is to be closed permanently.
