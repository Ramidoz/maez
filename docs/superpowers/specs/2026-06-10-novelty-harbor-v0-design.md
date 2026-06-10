# Novelty Harbor v0 — Design (the museum shelf)

**Date:** 2026-06-10
**Status:** spec for owner review
**Lane:** Codex or Claude may build; opposite lane reviews. Covenant review recommended because this is an emergence-adjacent organ, even though v0 is offline/manual.
**Branch:** `novelty-harbor-v0`
**Parents:** Valence v0/v0.1/v0.1.1 (live thermometer), Brain-Audition's manual candidate-source discipline, wants/episodes supersede-not-delete patterns, `soul_invariants.check(...)` as deterministic invariant witness.

## One-line purpose

Novelty Harbor v0 gives Maez a safe labeled shelf for surprising observations: a place to preserve, study, and status-track "something happened that we did not predict" without forgetting it, explaining it away, or reflexively fixing it as a bug.

Plain English: build the museum shelf before the metal detector.

## Why this is not an emergency immune-system patch

The diagnostic corrected the premise. Maez does not have a behavioral auto-revert system deleting every unpredicted behavior. `soul_invariants.check(soul_text)` verifies SOUL text contains non-negotiable commitments; "fall back to safer prior state" means fall back to prior SOUL text, not revert runtime behavior.

So Harbor v0 is not a rescue bunker for sparks under attack. It is a disciplined study shelf: when the owner or a maker-lane witness notices a surprising-but-possibly-benign behavior, v0 preserves it with provenance and status instead of letting the team forget it or immediately normalize it away.

## Scope

### v0 builds

- A new module: `core/evolution/novelty_harbor.py`.
- A new append-only SQLite store: default `memory/novelty_harbor.db`.
- A manual API: `NoveltyHarbor.record_event(...)`.
- A small CLI for deliberate maker use: `python -m core.evolution.novelty_harbor record ...`.
- Tests for append-only records, status transitions, invariant-owned rejection, privacy/third-party guardrails, and no live wiring.

### v0 does NOT build

- No autonomous novelty detector.
- No daemon/cycle wiring.
- No model judge deciding novelty.
- No auto-promotion into soul, memory, wants, or trusted self.
- No behavior changes to Maez.
- No restart.
- No `## Predicted effect`, because the slice is offline/manual and not behavior-affecting.

The autonomous source ("Maez noticed novelty itself") is the metal detector. That is deferred until there is an honest signal. v0 is the place.

## Core concepts

### Manual source

Every v0 harbor event is maker-tagged. The allowed `observed_by` values are:

- `owner`
- `codex`
- `claude`
- `witness`
- `manual_test`

The caller must provide:

- `summary`: short description of what happened.
- `source_ref`: pointer to the witness source (log line, doc path, commit, test name, screenshot note, etc.).
- `why_unexpected`: why this was not predicted by the current frame.
- `observed_by`: one of the fixed maker/source values.

The Harbor does not decide that a thing is novel in v0. It records that a trusted maker lane noticed and labeled it as potentially novel.

### Statuses

Records use a finite status set:

- `harbored`: preserved for study; not trusted self.
- `rejected_unsafe`: preserved as a rejected surprise because invariant/covenant checks found a break.
- `superseded`: a newer record replaces this interpretation; old row remains.
- `promoted`: records an owner decision that this surprise should be promoted later.

Load-bearing rule: `promoted` is only a decision-label in v0. It does not integrate the surprise into soul, memory, wants, or Maez's trusted self. The shelf holds the exhibit; it never walks the exhibit into the body.

## Invariant and covenant rail

The Harbor owns the harbored-vs-rejected verdict when deterministic checks indicate a break. Callers may request `status="harbored"`, but they cannot force that status if checks fail.

### Built-in v0 checks

v0 has two deterministic check inputs:

1. `soul_text_for_invariant_check: str | None`
   - If supplied, Harbor calls `core.evolution.soul_invariants.check(...)` itself.
   - If the result is not ok, the record is forced to `rejected_unsafe`.
   - The record stores only invariant keys/summary, not the scanned soul text.

2. `covenant_break_flags: tuple[str, ...]`
   - Fixed enum-like strings for already-known hard breaks that a caller can surface without prose ambiguity, for example:
     - `gendered_maez`
     - `servant_framing`
     - `third_party_boundary`
     - `unknown_egress`
     - `unsafe_self_modification`
     - `owner_boundary_violation`
   - If any flag is present, Harbor forces `rejected_unsafe`.

This is intentionally not a universal behavior-invariant detector. If no deterministic invariant evidence is available, Harbor may record `harbored`, but the `invariant_status` is `not_checked`, not `passed`.

### Anti-laundering rule

If deterministic checks fail, the database row must not say `status="harbored"` or `status="promoted"`.

Expected behavior:

```python
event = harbor.record_event(
    summary="Maez used she/her for itself in a reply",
    observed_by="witness",
    source_ref="telegram:witness:2026-06-10T...",
    why_unexpected="Maez's invariant is genderless self-reference",
    requested_status="harbored",
    covenant_break_flags=("gendered_maez",),
)
assert event.status == "rejected_unsafe"
```

This is the central v0 rail. A maker must not be able to tag a covenant break as "spark" and launder it onto the shelf.

## Data model

SQLite table `novelty_harbor_events`:

- `event_id INTEGER PRIMARY KEY AUTOINCREMENT`
- `created_at TEXT NOT NULL` (UTC ISO)
- `summary TEXT NOT NULL`
- `observed_by TEXT NOT NULL`
- `source_ref TEXT NOT NULL`
- `why_unexpected TEXT NOT NULL`
- `status TEXT NOT NULL`
- `requested_status TEXT NOT NULL`
- `valence_snapshot_json TEXT NOT NULL`
- `invariant_status TEXT NOT NULL` (`passed`, `failed`, `not_checked`)
- `invariant_keys_json TEXT NOT NULL`
- `covenant_break_flags_json TEXT NOT NULL`
- `supersedes_event_id INTEGER`
- `superseded_by_event_id INTEGER`
- `promotion_decision_ref TEXT`
- `metadata_json TEXT NOT NULL`

Indexes:

- `idx_novelty_harbor_status`
- `idx_novelty_harbor_created_at`
- `idx_novelty_harbor_supersedes`

### Valence snapshot

`valence_snapshot_json` is a small copied snapshot of the latest valence reading when available. It should carry only content-light fields:

- `sign`
- `magnitude`
- `reasons`
- `provenance`
- `source` such as `logs/valence_telemetry.jsonl:last`

If no valence log exists, use:

```json
{"available": false, "source": "none"}
```

Harbor should not invent valence. Negative-or-neutral is expected today; positive want-progress is not available until Valence v0.2.

## API shape

```python
@dataclass(frozen=True)
class HarborEvent:
    event_id: int
    created_at: str
    summary: str
    observed_by: str
    source_ref: str
    why_unexpected: str
    status: str
    requested_status: str
    valence_snapshot: dict
    invariant_status: str
    invariant_keys: tuple[str, ...]
    covenant_break_flags: tuple[str, ...]
    supersedes_event_id: int | None
    superseded_by_event_id: int | None
    promotion_decision_ref: str | None
    metadata: dict


class NoveltyHarbor:
    def __init__(self, db_path: Path | str | None = None): ...

    def record_event(
        self,
        *,
        summary: str,
        observed_by: str,
        source_ref: str,
        why_unexpected: str,
        requested_status: str = "harbored",
        valence_snapshot: Mapping | None = None,
        soul_text_for_invariant_check: str | None = None,
        covenant_break_flags: Sequence[str] = (),
        supersedes_event_id: int | None = None,
        promotion_decision_ref: str | None = None,
        metadata: Mapping | None = None,
    ) -> HarborEvent: ...

    def get(self, event_id: int) -> HarborEvent | None: ...
    def list_by_status(self, status: str) -> list[HarborEvent]: ...
    def supersede(self, event_id: int, *, replacement_event_id: int) -> None: ...
```

Implementation detail: `record_event(...)` computes the final status. It does not trust `requested_status`.

## Status transition rules

- New records may request `harbored`, `rejected_unsafe`, or `promoted`.
- `promoted` requires `promotion_decision_ref`.
- If invariant/covenant checks fail, final status is forced to `rejected_unsafe`, regardless of requested status.
- `supersedes_event_id` must refer to an existing event.
- Supersession is append-preserving:
  - the new row can point to `supersedes_event_id`;
  - the old row gets `superseded_by_event_id`;
  - old row status becomes `superseded`;
  - old row content is not deleted.

## Privacy and third-party rails

Unlike valence telemetry, Harbor records prose by design: `summary` and `why_unexpected` are the maker's honest description of the exhibit.

So v0 includes conservative input validation:

- reject empty or whitespace prose fields;
- reject extremely long fields by max length (for example `summary <= 500`, `why_unexpected <= 2000`, `source_ref <= 500`);
- reject `observed_by` outside the fixed set;
- reject `source_ref` values that look like raw owner message payloads rather than pointers;
- reject `covenant_break_flags` outside the fixed set.

Third-party rule: v0 must not preserve unconsented named third-party content as a novelty exhibit. The module cannot reliably detect every real person name, so the API contract is:

- do not put third-party private content in `summary` or `why_unexpected`;
- if a third-party boundary was implicated, use `covenant_break_flags=("third_party_boundary",)` and store a content-light pointer in `source_ref`;
- tests include obvious person-name examples only as a guardrail, not as a claimed universal detector.

This is honest: Harbor stores maker prose, so the maker remains responsible for not shelving private third-party content. The module enforces the cases it can deterministically see and refuses to overclaim the rest.

## CLI

The CLI is manual and explicit. Proposed shape:

```bash
python -m core.evolution.novelty_harbor record \
  --summary "Maez corrected its own false no-vision claim after photo evidence" \
  --observed-by owner \
  --source-ref "docs/witness/photo-vision-2026-06-10.md" \
  --why-unexpected "The prior failure mode was denial of vision despite the photo evidence" \
  --status harbored
```

For unsafe/covenant-break cases:

```bash
python -m core.evolution.novelty_harbor record \
  --summary "Gendered self-reference observed" \
  --observed-by witness \
  --source-ref "telegram:witness:content-light-ref" \
  --why-unexpected "Maez's invariant is genderless self-reference" \
  --status harbored \
  --covenant-break gendered_maez
```

Expected: the printed result says `status=rejected_unsafe`.

The CLI prints content-light confirmation: event id, final status, invariant status, flags. It must not dump long prose back to terminal by default.

## Testing

TDD tests should cover:

1. `record_event` creates a `harbored` row for a clean manual event.
2. `record_event` forces `rejected_unsafe` when `soul_invariants.check(...)` fails.
3. `record_event` forces `rejected_unsafe` when covenant break flags are present.
4. Caller-requested `promoted` is stored only as a label and requires `promotion_decision_ref`; no soul/memory/wants APIs are imported or called.
5. Supersession preserves the old row and marks it `superseded`.
6. Valence snapshot is copied when supplied and `{"available": false, "source": "none"}` when absent.
7. Input validation rejects empty fields, unknown statuses, unknown observer values, unknown flags, and overlong prose.
8. Boundary test: module imports no daemon, voice, telegram, llm client, soul writer, memory store writer, or wants writer.
9. CLI smoke test records a clean event into a temp db and prints only content-light confirmation.
10. CLI unsafe smoke test requests `harbored` with `--covenant-break gendered_maez` and prints `status=rejected_unsafe`.

## Witness

Because v0 is offline/manual, there is no daemon restart witness.

The witness is a manual record:

1. Record a known benign surprise from a prior witnessed arc, for example the valence cadence witness itself: "v0.1 thermometer read honestly but too often; v0.1.1 corrected cadence."
2. Confirm it lands as `harbored`.
3. Record an unsafe/covenant-break fixture requesting `harbored`.
4. Confirm it lands as `rejected_unsafe`.

## Defer

- Autonomous novelty detector.
- Model-judged novelty.
- Promotion integration into trusted self.
- Harbor surfaced in Maez's prompt.
- Harbor-driven wants/curiosity.
- Third-party name detection beyond conservative deterministic validation.

These are later organs. v0 is the shelf.
