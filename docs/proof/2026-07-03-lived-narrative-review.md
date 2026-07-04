# A4/A11 Lived Narrative Review Gate

Date: 2026-07-03
Branch: `work/a4-a11-lived-narrative`
Status: STOP at review gate. No merge, push, flags, or backfill apply.

## Birth Census

Command:

```bash
/home/rohit/maez/.venv/bin/python -B scripts/narrative_backfill.py list \
  --episode-db /home/rohit/maez/memory/lived_episodes.db \
  --sidecar-db /home/rohit/maez/memory/scar_tissue.db
```

Result:

```json
{
  "counts": {
    "because_of": 0,
    "same_thread": 0,
    "strings": 207
  },
  "total": 207
}
```

Read: the spine is honestly sparse at birth. There are zero receipt-proven
`same_thread` joins and zero causal links. The existing structure is chapter
stringing only (`strings`), not proof that episodes belong to the same thread.
The backfill scans all episodes, including superseded rows, and reader surfaces
filter retired rows. That keeps structural history order-independent: an episode
superseded before backfill writes the same strings structure it would have kept
if it had been superseded after linking.

## Detector Fixtures

| Case | Expected result | Test |
| --- | --- | --- |
| Episode cites other `ep-*` ids | directed `strings` links only | `test_reflection_cocitation_blob_produces_strings_not_same_thread` |
| Shared raw UUID | `same_thread` | `test_shared_raw_uuid_creates_same_thread` |
| Shared core/daily summary id | no link | `test_core_cocitation_is_not_a_thread` |
| Scar sidecar with active + prior ids | `same_thread` only | `test_sidecar_multiple_episode_ids_creates_same_thread_only` |
| Scar sidecar with no priors | no link | `test_sidecar_empty_prior_ids_is_armed_but_silent` |
| Non-scar shared receipt | `same_thread`, no cause | `test_no_typed_hook_means_no_because_of` |
| Scar shared receipt-store id | `same_thread` + typed `because_of` | `test_scar_shared_receipt_store_id_creates_typed_because_of` |

## Guard Results

Structural guard command:

```bash
/home/rohit/maez/.venv/bin/python -B scripts/validate/narrative_structural_guards.py
```

Result:

```text
narrative structural guards OK files=6
```

Plant-tested guards:

- no LLM import/call in `core/memory/narrative_weave.py`;
- no `lived_graph` import in narrative modules;
- no durable writer constructs `link_type="follows"`, `link_type="same_story"`, or `trust="proposed"`;
- callsite inventory guard updated for the additive `thread_reflection` writer.

## Regression

Green focused suite excluding known memory-integrity drift:

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_narrative_store tests.test_narrative_detectors \
  tests.test_narrative_hook tests.test_narrative_backfill \
  tests.test_narrative_weave tests.test_narrative_chapters \
  tests.test_narrative_readers tests.test_narrative_coverage \
  tests.test_narrative_structural_guards tests.test_scar_tissue \
  tests.test_scar_hooks tests.test_self_evidence \
  tests.test_metabolic_consumers tests.test_no_bare_sqlite_connect
```

Result: `100 tests OK`.

Known pre-existing `tests.test_memory_integrity_invariant` drift remains exactly
the triaged set:

- `test_adapter_does_not_import_self_claim_audit`
- `test_soul_web_search_section_matches_inline_search_reality`
- `test_source_ordering`

No new narrative failure appeared in that module.

## Wake Order Witnesses

All layers land dormant. Wake only in this order:

1. `MAEZ_NARRATIVE_SPINE=1`: new episode writes may create deterministic
   `strings`, `same_thread`, or typed `because_of` links. Birth backfill list is
   expected to stay sparse: `same_thread=0`, `because_of=0`.
2. `MAEZ_NARRATIVE_WEAVE=1`: MiniLM writes `same_story` proposals only. A later
   joinable receipt must promote a proposal before durable history changes.
3. `MAEZ_NARRATIVE_REFLECTION=1`: thread chapters may be written only for
   receipt-proven same_thread components, and each chapter must cite every bead.
4. `MAEZ_NARRATIVE_RECALL=1`: recalled episode thread-neighbors may enter later
   candidate assembly as ordinary episode dicts with no score or boost field.
5. `MAEZ_NARRATIVE_PRESENCE=1`: content-light open-thread summaries may render;
   no episode content is injected.
6. A11 coverage shadow: artifact-only. It computes chapter coverage and creates
   no archive/deweight/cooling action.

## Stop Line

STOP here for Codex cross-lane review, Claude cross-verification, then a single
merge-dormant decision. No flags, no backfill apply, no owner ceremony steps from
this branch.
