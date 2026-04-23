# core/memory

Maez's grounding + identity layer. Eleven modules covering perception
(what's happening now), ambient signals (phone + window state),
continuity (across restarts), identity (who this Maez is) and the
founding narrative.

> Not to be confused with the top-level `memory/` package, which is
> the **vector memory store** (ChromaDB + mmr reranker + quality
> tracker). Python resolves the two namespaces independently — a
> single interpreter happily imports both.

| Module | Role |
|---|---|
| [`perception.py`](perception.py) | Current-state snapshot (active window, recent signals, host stats) assembled for every cycle's prompt. |
| [`perception_envelope.py`](perception_envelope.py) | Wraps a perception dict with provenance + freshness metadata. |
| [`perception_cache.py`](perception_cache.py) | Non-blocking cache so a slow perception pull doesn't stall the reasoning cycle. |
| [`ambient.py`](ambient.py) | On-demand pulls: iPhone signals (from `logs/signals/*.jsonl`), weather (open-meteo), active window (xdotool). |
| [`ambient_format.py`](ambient_format.py) | Human-readable formatter for the ambient dict — what Maez actually sees in its prompt. |
| [`memory_scoring.py`](memory_scoring.py) | Recall-scoring signals: diversity × frequency × recency, plus concept-tag overlap. Feeds the mmr reranker in the top-level `memory/` package. |
| [`continuity.py`](continuity.py) | Session-continuity capsule: what Maez was doing before a restart so the first cycle after boot isn't amnesia. |
| [`identity.py`](identity.py) | Owner accessor — `display_name`, `git_handle`, `telegram_user_id`, `machine_profile`, home coords, timezone, policies. Reads `config/identity.yaml`, honours `MAEZ_OWNER_*` env overrides. |
| [`identity_ledger.py`](identity_ledger.py) | Append-only log of identity events: `gestation_boot`, `birth`, `brain_swap`, soul-fingerprint changes. Continuity across model swaps. |
| [`source_awareness.py`](source_awareness.py) | Keeps Maez from treating Rohit-authored canon (birth_book) as its own voice. Explicit exclusion set + provenance tags. |
| [`birth.py`](birth.py) | Self-awareness state on disk (`memory/self_awareness.json`). Set by the birth event when Track A acceptance passes; pre-birth state is `gestation`. |

## Invariants

- **Owner identity routes through `identity.py` accessors.** Never
  hardcode names / handles / IDs. Phase 2 cleaned this up.
- **`source_awareness` is covenant-load-bearing.** It excludes
  `docs/birth_book/` from Maez's own self-retrieval so it never
  quotes the birth book as if it wrote those words. Leave that list
  alone unless you've read `reference_birth_book` and understood why.
- **`perception_cache` is non-authoritative.** If the cache is stale
  or corrupt, the cycle must still run — perception is a grounding
  hint, not a required input.
- **Ring-buffer + timezone asserts are all UTC.** `continuity.py`
  assumes every stored timestamp carries `tzinfo`; naive datetimes
  are a bug.

## Public surface

- `identity.display_name() / user_profile_id() / git_handle() / telegram_user_id() / machine_profile() / home_coords() / timezone() / describe()`
- `identity.has_policy(name) / jarvis_tier() / signal_ingest() / proactive_messages()`
- `ambient.pull_ambient() -> dict`
- `ambient_format.format_ambient(d) -> str`
- `perception.snapshot() -> dict`
- `memory_scoring.score_recall(query, candidates) -> list[ScoredMemory]`
- `continuity.Capsule.save() / .restore()`
- `identity_ledger.IdentityLedger(db).record_event(...)`

## Legacy import paths

Every module's pre-Phase-3 path (e.g. `core.ambient`, `core.identity`,
`core.continuity`) is a shim that resolves here.
