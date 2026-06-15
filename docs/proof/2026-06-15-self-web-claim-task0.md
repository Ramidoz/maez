# Task 0 — self-web-claim hygiene feasibility gate (DOCS/PROOF ONLY)

Branch: `self-web-claim-hygiene`
Date: 2026-06-15
Scope: prove (or refute) two seam assumptions before any wiring. No behavior
change, no production `.py` edits. All citations are `file:line` against the
tree at the time of writing.

---

## PROOF 0a — the web-grounded signal at the turn-store site

### The store site

`daemon/maez_daemon.py:7230-7234` (inside `handle_message`):

```python
_m1_raw_memory_id = self.memory.store_telegram(
    f"the owner ({source}): {text}\nMaez: {reply}",
    provenance_source="user_utterance",
    trust_tier="lived",
)
```

Method boundary confirmed: `handle_message` is defined at `daemon/maez_daemon.py:5295`
and the next method (`_get_public_context`) begins at `daemon/maez_daemon.py:7357`.
So line 7230 is inside `handle_message`; locals assigned anywhere in 5295-7356
are in scope at 7230 (no early `return` sits between the web-search block and the
store).

### `web_context` is in scope — but it is NOT a complete web-grounded signal

Every `web_context` assignment inside `handle_message`:

- `daemon/maez_daemon.py:5659` — `web_context = ""` (unconditional initialisation;
  guarantees the name is always bound at 7230).
- `daemon/maez_daemon.py:5683` — `web_context = web_format(sr)` (LEGACY in-daemon
  web/RSS search path, guarded by `not authoritative_tool_reply and
  _daemon_parallel_web_search_enabled(...) and needs_web_search(text)`).
- `daemon/maez_daemon.py:5773` — `web_context = web_format(sr)` (PHOTO freshness
  search path).

So `web_context` is reliably bound (`""` or web text) on every path, and
`bool((web_context or "").strip())` is true exactly when the **legacy / photo**
in-daemon search ran.

**The hole: the dispatcher (Search-as-a-Sense) web path does NOT set `web_context`.**
`transcript` and `tool_calls` are *parameters* of `handle_message`
(`daemon/maez_daemon.py:5300, 5307`), produced by the dispatcher tool loop that
runs *before* `handle_message`. When the dispatcher fetches fresh web evidence,
that evidence arrives as the `[fresh evidence]` block in `transcript`
(emitted by `core/dispatcher/provenance_renderer.py:234`) and/or as the
per-turn evidence stash drained at `daemon/maez_daemon.py:7055`
via `pop_turn_evidence(chat_id)` (`_turn_ev["web_present"]`,
set in `core/routing/attribution_render.py:85-89`). On those turns `web_context`
stays `""`. Therefore `bool(web_context.strip())` would FALSE-NEGATIVE the
dispatcher web turns — the exact turns the hygiene feature most needs to tag.

`_turn_ev` is NOT a usable substitute at 7230: it is bound only inside
`if sense_enabled() or page_read_enabled():` (`daemon/maez_daemon.py:7054-7055`),
inside a bare `try/except` that swallows everything (7046/7092), and it is
**popped** (consumed/destroyed) at 7055 — well before the store at 7230.
Reusing it would NameError on flag-off and read empty after the pop.

### The reliable in-scope signal

`daemon/maez_daemon.py:6090-6093` already computes, unconditionally and as a
plain local that is in scope at 7230:

```python
_evidence_state = turn_evidence_state(
    transcript=transcript,
    web_context=web_context,
)
```

`turn_evidence_state` (`core/routing/evidence_state.py:53`) unions BOTH web paths:
- the dispatcher `[fresh evidence]` transcript marker → label `"fresh evidence"`
  (`core/routing/evidence_state.py:17-21, 67-72`), and
- the legacy/photo `web_context` → label `"web search results"`
  (`core/routing/evidence_state.py:74-79`).

Its `marker_labels` ALSO contains substrate-recall labels (`[memory evidence]`,
`[memory context]` → `"memory evidence"` / `"memory context"`,
`core/routing/evidence_state.py:18-19`), so `_evidence_state.evidence_present`
alone is NOT web-specific. The web-specific test is on the labels:

```python
web_grounded = bool(
    {"fresh evidence", "web search results"}
    & set(_evidence_state.marker_labels)
)
```

This needs no cross-layer threading — `_evidence_state` is already built at 6090
on the path that reaches 7230.

### 0a VERDICT: HELD (with correction)

- Bare `web_grounded = bool((web_context or "").strip())` is REJECTED: it misses
  the dispatcher fresh-evidence path (false negative on dispatcher web turns).
- The confirmed reliable signal is web-specific labels from the already-in-scope
  `_evidence_state` (`daemon/maez_daemon.py:6090`):

  **`web_grounded = bool({"fresh evidence", "web search results"} & set(_evidence_state.marker_labels))`**

  No new value needs threading across layers — proof 0a is HELD.

---

## PROOF 0b — `provenance_source` threading reachability

Goal: confirm `provenance_source` can travel
`stored-row metadata -> RecallItem -> EvidenceItem`.

### Hop 1 — store writes it into row metadata

`memory/memory_manager.py:1114-1145` (`store_telegram`) calls
`_provenance_metadata(provenance_source, trust_tier)` (line 1121) and
`meta.update(provenance_extra)` (line 1136) into the row metadata written to
`self.raw.add(..., metadatas=[meta])` (line 1139-1143).

`_provenance_metadata` (`memory/memory_manager.py:251-267`) persists the key
verbatim:

```python
extra["provenance_source"] = src.value     # memory/memory_manager.py:262
```

**Persisted metadata key: `provenance_source`** (string value from the
`ProvenanceSource` enum, `memory/memory_manager.py:76-87`). The same `meta` dict
also carries `trust_tier` (line 264/266), so the two ride together.

NOTE for the later task: a new `self_web_claim` value is NOT yet in the
`ProvenanceSource` enum (`memory/memory_manager.py:82-87`) and
`_coerce_provenance_source` (`memory/memory_manager.py:112-122`) raises on
unknown values. Adding the enum member is part of the wiring, not a blocker.

### Hop 2 — recall reads metadata into RecallItem

`core/brain/brain_loop.py:117-159` (`recall_partitions_to_items`) reads
`meta = row.get("metadata") or {}` (line 130) — the SAME metadata dict that
round-trips through recall — and today extracts `trust_tier=meta.get("trust_tier")`
(line 156) but does NOT read `provenance_source`. Because `trust_tier` round-trips
from the same `meta`, `meta.get("provenance_source")` is available at the same
site. WIRING: add `provenance_source=meta.get("provenance_source")` to the
`RecallItem(...)` construction (lines 150-157).

### Hop 3 — RecallItem dataclass field

`core/dispatcher/layer1.py:63-69`: `RecallItem` is a frozen dataclass with
`trust_tier: str | None = None` (line 69) but NO `provenance_source` field.
WIRING: add `provenance_source: str | None = None`. (Note: `RecallItem.to_dict`
or similar at lines 104 also maps `trust_tier` — any serialiser that lists fields
should add the new one; verify at wire time.)

### Hop 4 — EvidenceItem dataclass field + raw_items tuple

`core/routing/focused_cognition.py:235-242`: `EvidenceItem` is a frozen dataclass
with `origin_trust: str | None = None` (line 242) but NO `origin_provenance`.
WIRING: add `origin_provenance: str | None = None`.

`assemble_working_set` (`core/routing/focused_cognition.py:761`) takes
`recall_items` (line 767), which becomes `structured_recall_items` at line 799.
The `raw_items` list is a **5-element** tuple
`(source_type, text, durable_id, temporal_provenance, origin_trust)`
(type annotation `core/routing/focused_cognition.py:808`). It is constructed /
consumed at these sites, ALL of which must move 5 -> 6 elements:

- `core/routing/focused_cognition.py:808` — `raw_items` type annotation.
- `core/routing/focused_cognition.py:818-829` — structured-recall branch reads
  `origin_trust = getattr(item, "trust_tier", None)` (line 820) and appends the
  5-tuple (821-829). Here is where `getattr(item, "provenance_source", None)`
  would be read from the `RecallItem` and added as the 6th element.
- `core/routing/focused_cognition.py:835` — transcript non-recall branch appends
  `(source_type, item_text, None, None, None)`.
- `core/routing/focused_cognition.py:841, 844` — legacy (no structured items)
  transcript branches.
- `core/routing/focused_cognition.py:849` — `web_context` items.
- `core/routing/focused_cognition.py:852` — anchors.
- `core/routing/focused_cognition.py:860-867` — `temporal_recall_status` filler.
- `core/routing/focused_cognition.py:856-857` — the `date_cue` unpack
  `for _source_type, _text, _durable_id, provenance, _origin_trust in raw_items`.
- `core/routing/focused_cognition.py:874-889` — the `EvidenceItem` build loop
  unpacks the 5-tuple (883-889); add `origin_provenance` here.
- `core/routing/focused_cognition.py:679-711` — `_ranked_items_for_state`
  (type annotations lines 680/683 and the `rank()` unpack at line 685) consumes
  and re-emits the tuple; it must accept the 6-tuple too.

All sites are in one module (`focused_cognition.py`) plus the one `RecallItem`
read in `brain_loop.py` and the two dataclass field adds. No metadata is stripped
between store and recall (`meta` round-trips), and `RecallItem` is constructed in
exactly one place that already sees the metadata dict
(`core/brain/brain_loop.py:130, 150-157`).

### 0b VERDICT: HELD

Persisted key is **`provenance_source`**. Every hop is wireable with field-adds
and metadata reads; no hop is blocked. Wiring list:

1. `RecallItem` field add — `core/dispatcher/layer1.py:69`.
2. recall read — `core/brain/brain_loop.py:130, 150-157`
   (`provenance_source=meta.get("provenance_source")`).
3. `EvidenceItem` field add (`origin_provenance`) — `core/routing/focused_cognition.py:242`.
4. `raw_items` 5 -> 6 tuple at ALL sites above
   (`core/routing/focused_cognition.py:808, 818-852, 856-868, 874-889`) AND
   `_ranked_items_for_state` (`core/routing/focused_cognition.py:679-711`).
5. (later-task dependency) add `self_web_claim` to `ProvenanceSource`
   (`memory/memory_manager.py:82-87`).

---

## SEAM ASSUMPTIONS HELD: YES

Both signals are reachable without invasive cross-layer threading.

Caveat carried forward (not a blocker, a correction to the plan): the
web-grounded signal at the store site is NOT bare `web_context`. `web_context`
false-negatives on the dispatcher (Search-as-a-Sense) web path. The correct,
already-in-scope signal is the web-specific labels of `_evidence_state`
(`daemon/maez_daemon.py:6090`):
`bool({"fresh evidence", "web search results"} & set(_evidence_state.marker_labels))`.
