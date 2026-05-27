# Layer 1 Adapter Investigation — `ENTITY_INDEX` / `LIVED_EPISODES` Synchronous 0ms Errors

**Status:** diagnostic witness, no code change. Decision required before fix.
**Date:** 2026-05-27
**Predecessor witnesses (Finding 7 across three daemon runs):**
- `docs/slices/recall-axis-dispatcher/witness/finding19-probe-2026-05-27-daemon.md` (probe 5)
- `docs/slices/recall-axis-dispatcher/witness/external-source-probe-2026-05-27-daemon.md` (probe 5)
- `docs/slices/recall-axis-dispatcher/witness/external-source-v1p2-verify-2026-05-27-daemon.md` (probe 5)
- `docs/slices/recall-axis-dispatcher/witness/external-source-v1p3-verify-2026-05-27-daemon.md` (probe 5)

## Headline Finding

**The `ENTITY_INDEX` and `LIVED_EPISODES` "errors" are not crashes, not adapter exceptions, and not store/config failures.** They are **missing adapter implementations**: Layer 0 emits these substrate sources in its default fallback, but `brain_loop._dispatcher_recall_adapters` does not register adapters for them, so Layer 1's `adapters.get(source)` returns `None` and immediately produces a `RecallBranchResult` with `status=ERROR` and `error_class="adapter_missing"`, with zero elapsed time (no execution occurs).

The reason this surfaced as a recurring 0ms error pattern across four daemon witnesses is that the dispatcher contract has an unstated wiring gap: there is no consistent answer for "what happens when Layer 0 emits a source the orchestrator hasn't implemented an adapter for."

## Classification

Per Rohit's investigation framing:

| Hypothesis | Result |
|---|---|
| Adapter construction issue | NO — nothing constructs because no adapter is registered |
| Missing store/config | PARTIAL — the underlying stores may or may not exist; the issue is upstream |
| Schema drift | NO — no schema is consulted |
| Timeout/deadline bug | NO — the error fires synchronously, before any I/O |
| **Caller-shape mismatch** | **YES** — Layer 0's emission set and brain_loop's adapter dict diverge |

## Substrate Source Inventory by Implementation Status

There are 8 `SubstrateSource` enum values declared at `core/dispatcher/spec.py:18-26`. Mapping each to its current wiring state:

| Source | Layer 0 emits? | Inventory status | brain_loop adapter? | Live witness outcome |
|---|---|---|---|---|
| `REDDIT_SOURCE` | yes (Reddit-anchored probes) | EXECUTABLE_PRESENT | `_reddit_source_adapter` | works |
| `TELEGRAM_TEMPORAL` | (not emitted in observed corpora) | EXECUTABLE_PRESENT | `_memory_manager_adapter` | (not exercised) |
| `TELEGRAM_SEMANTIC` | yes (default fallback at layer0.py:76-80) | EXECUTABLE_PRESENT | `_memory_manager_adapter` | works (with B3 truncation) |
| `WEB_FAST_TURNS` | (not emitted) | **RESERVED** at inventory.py:26-32 | (none needed) | (not exercised) |
| **`ENTITY_INDEX`** | **yes (default fallback)** | **EXECUTABLE_PRESENT** (no inventory entry) | **NONE** | **0ms ERROR, error_class="adapter_missing"** |
| **`LIVED_EPISODES`** | **yes (default fallback)** | **EXECUTABLE_PRESENT** (no inventory entry) | **NONE** | **0ms ERROR, error_class="adapter_missing"** |
| `LIVED_GRAPH` | (not emitted) | **RESERVED** at inventory.py:26-32 | (none needed) | (not exercised) |
| `PRIVATE_THOUGHTS` | (not emitted) | EXECUTABLE_PRESENT (no inventory entry) | NONE | (latent — would error if emitted) |

**The two sources in no-man's-land:** `ENTITY_INDEX` and `LIVED_EPISODES`. They are declared in the enum, included in Layer 0's default fallback, treated as "executable" by inventory (no RESERVED entry, no privacy gate, no explicit unavailability), but no adapter implementation exists.

## Code Evidence

**Layer 0 fallback** (`core/dispatcher/layer0.py:76-80`):

```python
_DEFAULT_SUBSTRATE_FALLBACK = [
    SubstrateSource.TELEGRAM_SEMANTIC,
    SubstrateSource.ENTITY_INDEX,
    SubstrateSource.LIVED_EPISODES,
]
```

**brain_loop adapter registration** (`core/brain/brain_loop.py:272-276`):

```python
return {
    SubstrateSource.REDDIT_SOURCE: _reddit_source_adapter,
    SubstrateSource.TELEGRAM_TEMPORAL: _memory_manager_adapter,
    SubstrateSource.TELEGRAM_SEMANTIC: _memory_manager_adapter,
}
```

**Layer 1 missing-adapter handling** (`core/dispatcher/layer1.py:203-212`):

```python
adapter = self.adapters.get(source)
if adapter is None:
    results[source] = RecallBranchResult(
        branch_id=branch_id,
        fanout_generation_id=generation_id,
        source=source,
        status=RecallBranchStatus.ERROR,
        error_class="adapter_missing",
    )
    continue
```

**Inventory's reserved set** (`core/dispatcher/inventory.py:26-32`):

```python
RESERVED_SOURCES: frozenset[SourceLabel] = frozenset(
    {
        SubstrateSource.LIVED_GRAPH,
        SubstrateSource.WEB_FAST_TURNS,
        ExternalSource.FRONTIER_CONSULT,
    }
)
```

`ENTITY_INDEX` and `LIVED_EPISODES` are not in `RESERVED_SOURCES`. Inventory's source-availability classifier at line 137-170 routes them through the standard `EXECUTABLE_PRESENT` path, so Layer 0's preflight accepts them, Layer 0 includes them in fallback, Layer 1 looks up adapter, finds None, emits 0ms ERROR.

## Why the v1.2 / v1.3 Witnesses Didn't Catch This as a Functional Bug

The recurring 0ms error pattern was visible in every daemon witness, but didn't block headline closure because:

1. **In seam-8 and v1.2-verify witnesses:** the v1.1 merge refused with `FRESH_FAILURE_HYBRID_FALLBACK_ILLEGAL` *before* the renderer saw the asymmetric source list — the substrate row was dropped by `_budget_blocks`, `recall_blocks` was empty, refusal fired at merge. The renderer never got a chance to surface the deeper issue.

2. **In v1.2-verify (Finding 6 surfaced) witness:** B3+B1 preserved the truncated row, the merge accepted it, and the renderer's `_validate_source_roles` refused — exposing the source-list asymmetry. But the root cause was visible only as `error_class="adapter_missing"` in cognition.log, which was easy to misread as "the adapter raised an error" rather than "no adapter exists."

3. **In v1.3-verify witness:** the merge filter dropped the unimplemented sources from `effective_spec.substrate_sources`, the renderer accepted, and the transcript rendered. The error became invisible to user-facing output. Behavior is now operationally correct, but the substrate landscape is **partially blind** — every default-fallback substrate-only query consults only TELEGRAM_SEMANTIC, not the three sources Layer 0 declared.

This is what Rohit's "partially blind in the same way" intuition pointed at: the dispatcher contract is clean, but two of three declared substrate sources for memory queries do not actually execute.

## Decision Options

### Option A — Mark `ENTITY_INDEX` and `LIVED_EPISODES` as RESERVED in `inventory.py`

Add both to the `RESERVED_SOURCES` frozenset, symmetric with `LIVED_GRAPH` and `WEB_FAST_TURNS`. Layer 1's preflight then resolves them to `RecallBranchStatus.RESERVED_UNAVAILABLE` with `RESERVED_SOURCE_UNAVAILABLE` limitation (per the existing `_preflight_result` path), without calling the missing adapter. The audit envelope honestly records "this source is registered but not yet implemented" rather than the misleading "adapter_missing" pseudo-error.

**Pros:**
- Smallest patch (one frozenset addition + RED test).
- Honest substrate landscape — declares the gap rather than hiding behind a fake error.
- Aligns with how `LIVED_GRAPH` and `WEB_FAST_TURNS` are already treated.
- The `error_class="adapter_missing"` free-form string is replaced by a closed-vocab status, removing one open-string surface from substrate telemetry (small Theme A debt cleanup).
- v1.3's merge filter continues to drop them from rendered output — operational behavior unchanged.

**Cons:**
- Records intent ("not yet implemented") rather than the actual long-term plan (presumably they should eventually have adapters).
- If a future slice implements an adapter, the RESERVED entry must be removed in the same commit.

### Option B — Implement adapters for `ENTITY_INDEX` and `LIVED_EPISODES`

Add adapter functions in `brain_loop._dispatcher_recall_adapters`. Requires owner-level design input:
- What is `ENTITY_INDEX` supposed to query? (Entity-keyed substrate? Named-span index over conversation?)
- What is `LIVED_EPISODES` supposed to query? (Episodic memory? Consolidated diary entries? Day-bounded conversation groups?)
- Do the underlying stores exist?

**Pros:**
- Closes the substrate-quality gap fully — memory queries consult all three declared sources.
- Resolves Finding 7 at the implementation level, not just the contract level.

**Cons:**
- Not a dispatcher contract decision — substrate design.
- Substantial surface area; requires understanding the substrate architecture beyond what's in this slice's scope.
- Risk of building adapters that produce poor-quality recall if the underlying stores are immature.

### Option C — Remove `ENTITY_INDEX` and `LIVED_EPISODES` from Layer 0's `_DEFAULT_SUBSTRATE_FALLBACK`

Trim the fallback list to `[SubstrateSource.TELEGRAM_SEMANTIC]`. Layer 0 stops emitting the unimplemented sources. Layer 1's adapter lookup never sees them. The substrate landscape collapses to what's actually executable.

**Pros:**
- Removes the divergence between Layer 0 emission and brain_loop wiring.
- Smallest user-facing impact (Layer 0 already produces SUBSTRATE_ONLY for memory queries; trimming the fallback to one source doesn't change the framing).

**Cons:**
- Erases the future-substrate signal from the dispatcher contract. Anyone reading Layer 0's fallback would no longer know these sources are intended-but-unimplemented.
- Information loss vs Option A, which makes the intent explicit via RESERVED status.

### Option D — Status quo (accept the 0ms adapter_missing error as canonical)

What every witness so far has tolerated. v1.3's merge filter handles the user-facing rendering; the audit envelope's `NO_RELEVANT_SUBSTRATE` limitation records the dropped axis.

**Pros:**
- No code change.

**Cons:**
- Substrate landscape stays partially blind without being declared blind.
- `error_class="adapter_missing"` is a free-form string and a misleading error name.
- Future maintainers will keep rediscovering this pattern through new witnesses.
- Observation window will continue to surface the same recurring noise.

## Recommended Path

**Option A (mark as RESERVED).** Smallest honest patch, symmetric with existing reserved-source discipline, closed-vocab cleanup, and operationally invisible (v1.3 filter already drops them).

This is also the most reversible: when a future slice implements `ENTITY_INDEX` or `LIVED_EPISODES` adapters, the RESERVED entry can be removed in the same commit that registers the adapter. The contract gracefully evolves from "reserved" → "implemented" without a flag-day.

If Option A is picked, the patch shape is:

```python
# core/dispatcher/inventory.py:26-32 (3 lines added)
RESERVED_SOURCES: frozenset[SourceLabel] = frozenset(
    {
        SubstrateSource.LIVED_GRAPH,
        SubstrateSource.WEB_FAST_TURNS,
        SubstrateSource.ENTITY_INDEX,          # new
        SubstrateSource.LIVED_EPISODES,        # new
        ExternalSource.FRONTIER_CONSULT,
    }
)
```

RED test: a SUBSTRATE_ONLY spec with TELEGRAM_SEMANTIC + ENTITY_INDEX + LIVED_EPISODES should produce a Layer 1 fanout where the latter two have `status=RESERVED_UNAVAILABLE`, not `status=ERROR`. The merge then drops them from `effective_spec.substrate_sources` per v1.3 (since they have no rows), and the audit envelope records `RESERVED_SOURCE_UNAVAILABLE` limitation alongside `NO_RELEVANT_SUBSTRATE`.

## What Stays Out of This Patch

- **Designing actual ENTITY_INDEX and LIVED_EPISODES adapters** (Option B) — substrate-design work, not in dispatcher contract scope. If/when owners decide to build these, that's a separate slice.
- **Substrate error_class closed-vocab cleanup** — `RecallBranchResult.error_class` is still `str | None`; the seam-1 closed-vocab cleanup applied to external sources but not substrate. Worth a future dispatcher-v2 item but out of this investigation's scope.
- **Layer 0 fallback redesign** — Option C is technically smaller code but loses signal; not recommended.

## Verdict

Finding 7 (Layer 1 ENTITY_INDEX / LIVED_EPISODES synchronous 0ms errors) is **not** a runtime bug. It is a dispatcher-wiring caller-shape mismatch. The error class string is misleading; the actual condition is "Layer 0 declared a source the orchestrator has not implemented yet."

Rohit's decision on Options A/B/C/D drives the next move. Option A is recommended.
