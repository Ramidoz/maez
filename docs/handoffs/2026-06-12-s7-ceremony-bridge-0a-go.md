# S7 Ceremony Bridge v0 — Task 0a GO after Task 0.5

Date: 2026-06-12
Branch: `s7-ceremony-bridge-v0`
Tip at handoff: pending commit after `0a948f2`
Base: `main@115142c`

## Verdict

GO. After Task 0.5, the existing self-mod-dialog live soul-write path executes
end to end in a hermetic sandbox for both soul actions:

- `write_soul_note`
- `edit_soul_section`

The original 0a NO-GO was real: S7 could not build a request envelope for these
actions because they had no affected refs and therefore no derived aggregation
group. Task 0.5 fixes that by making both actions derive the same canonical soul
ref:

```text
file:<core.infra.paths.soul_combined_path()>
```

This is intentionally shared-soul-ref semantics: the soul is one authority
surface, so separate pending soul modifications aggregate together instead of
being authorized in ignorance of each other.

## What changed

`core/governance/operator_user_boundary.py`

- `derive_affected_refs(...)` now special-cases `write_soul_note` and
  `edit_soul_section`.
- It imports `core.infra.paths` and returns the canonical
  `soul_combined_path()` ref.
- It does not add executable params to the card/action payload, so nothing leaks
  into `_do_write_soul_note(...)` or `_do_edit_soul_section(...)`.

`tests/test_operator_user_boundary_s7.py`

- Adds a focused S7 governance test that both actions derive the same canonical
  soul ref and therefore the same aggregation group.

`tests/test_s7_dialog_soulwrite_liveproof.py`

- Keeps the 0a proof as a standing regression.
- The proof redirects all discovered soul write paths into a temporary config:
  `paths.soul_base_path`, `paths.soul_local_path`, `paths.soul_combined_path`,
  `action_engine.SOUL_PATH`, `soul_editor.SOUL_PATH`, and
  `soul_editor.BACKUP_DIR`.
- It hash-guards the real soul/base/local files.

## Verification

Focused RED before the fix:

```text
test_025b_soul_write_actions_share_canonical_soul_ref_for_aggregation ... FAIL
AssertionError: () != ('file:/.../config/soul.md',)
```

Focused GREEN after the fix:

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_operator_user_boundary_s7.S7WorkClassAndEnvelopeTests.test_025b_soul_write_actions_share_canonical_soul_ref_for_aggregation -v
```

Result:

```text
Ran 1 test ... OK
```

0a proof after the fix:

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_s7_dialog_soulwrite_liveproof -v
```

Result:

```text
test_edit_soul_section_executes_end_to_end ... ok
test_write_soul_note_executes_end_to_end ... ok

Ran 2 tests ... OK
```

Meaning: the real dialog path built the S7 envelope, minted/consumed the S7
artifact, called `DecisionPipeline._handle_pending_dialog_input(...)`, executed
the real `ActionEngine` soul handlers, mutated only the sandbox soul files, and
left the real soul hashes unchanged.

## Bridge plan status

Task 0a is now GO. The original bridge plan may proceed to Task 1+.

Review anchors for the next pass:

- Shared soul ref is intentional and covenant-shaped.
- Canonical path helper, not literal string.
- No executable-param leak into action handlers.
- 0a proof remains in the suite and must stay green.
