# S7 Ceremony Bridge v0 — Task 0a NO-GO

Date: 2026-06-12T17:44:56-05:00
Branch: `s7-ceremony-bridge-v0`
Base: `main@115142c`

> Superseded by `2026-06-12-s7-ceremony-bridge-0a-go.md` after Task 0.5
> taught S7 that `write_soul_note` and `edit_soul_section` share the
> canonical soul ref from `core.infra.paths.soul_combined_path()`.

## Verdict

NO-GO. The existing self-mod-dialog live soul-write path cannot yet be proven
because it fails before the ceremony/execution leg: `DecisionPipeline._s7_request_envelope_for_card`
cannot build an S7 envelope for `write_soul_note` or `edit_soul_section`.

## Exact failing leg

The hermetic proof creates a real lane-3 card with action `write_soul_note` or
`edit_soul_section`, then calls:

`DecisionPipeline._s7_request_envelope_for_card(card)`

Both actions fail with:

```text
ValueError: guarded S7 work requires derived_aggregation_group
```

Root cause:

- `operator_user_boundary.derive_work_class(...)` correctly classifies
  `write_soul_note` and `edit_soul_section` as `self_modification`.
- `operator_user_boundary.derive_affected_refs(...)` derives refs only from
  `path`, `file`, `target`, some service commands, and backup operations.
- `write_soul_note` params are `{note}` and `edit_soul_section` params are
  `{target_name, new_body, rationale}`, so both produce empty `affected_refs`.
- `derive_aggregation_group(...)` returns empty when both affected refs and
  target service are empty.
- `WorkRequestEnvelope.__post_init__` refuses guarded S7 work without a
  `derived_aggregation_group`.

So the path is dormant one layer earlier than expected: not at action execution,
but at request-envelope construction for the two soul-write action names.

## Hermetic proof artifact

Created: `tests/test_s7_dialog_soulwrite_liveproof.py`

The proof redirects all discovered soul write paths before constructing the
pipeline/action engine:

- `core.infra.paths.soul_base_path`
- `core.infra.paths.soul_local_path`
- `core.infra.paths.soul_combined_path`
- `core.actions.action_engine.SOUL_PATH`
- `core.evolution.soul_editor.SOUL_PATH`
- `core.evolution.soul_editor.BACKUP_DIR`

It also hash-guards the real `soul.base.md`, `soul.local.md`, and `soul.md` via
`core.infra.paths`.

Command run:

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_s7_dialog_soulwrite_liveproof -v
```

Result:

```text
FAILED (errors=2)
```

Both tests fail at `_s7_request_envelope_for_card(...)` with the same missing
aggregation group error. No real soul file was modified.

## Implication for the bridge plan

Do not proceed to Task 1+ yet. The bridge must not wrap a ceremony around this
path until the action-envelope geometry for `write_soul_note` and
`edit_soul_section` is repaired and the 0a proof reaches the real execution leg.

The repair is to make S7's affected-ref derivation recognize the two explicit
soul-write actions as touching the canonical `core.infra.paths.soul_combined_path()`
ref, without requiring extra executable params that would leak into
`_do_write_soul_note(...)` / `_do_edit_soul_section(...)`.

After that, rerun the same proof. Only if both tests execute against the
sandbox soul and leave the real soul hashes unchanged should 0a become GO.
