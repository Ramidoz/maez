# S7.3 Spec v21 Fold Delta-Plan Addendum - Whole-Family Vocabulary Restore

**Subject:** correction to `reviews/spec-v21-fold-plan.md`.

**Sources:**

- v21 fold plan: `aa55fcb / reviews/spec-v21-fold-plan.md`
- v20 spec: `ee580b7 / spec.md`
- pre-cut baseline: `0c3215e / spec.md`
- Claude fresh-reader gate v20:
  `ec11071 / reviews/spec-fresh-reader-gate-v20.md`

**Verdict:** v21 fold plan Section 1 is incomplete. Lines 73-74 of the plan
("Do not alter the already-matching non-credential ids unless...") are
superseded by this addendum.

The correct v21 approach is a whole-family restore of the execution-consumer
vocabulary family from the pre-cut baseline, with only credential-only members
removed and the v20 `NON_MINTABLE_EXECUTION_CONSUMER_IDS` split preserved.

## 1. What The Plan Missed

The v20 cut damaged `S7_EXECUTION_CONSUMER_IDS` beyond the four `guarded_*`
renames named in Section 1 of the fold plan.

Pre-cut `S7_EXECUTION_CONSUMER_IDS` had 23 values. The correct post-cut target
has 20 values:

- remove `s7_credential_register_backup`;
- remove `s7_credential_disable`;
- move/keep `action_engine_final_mutate` in `NON_MINTABLE_EXECUTION_CONSUMER_IDS`
  only.

Live v20 has 28 values and includes 12 wrong mintable entries:

```text
guarded_dream_apply
guarded_section_edit_apply
guarded_candidate_apply
guarded_workshop_apply
self_mod_dialog_terminal_execute
reviewed_substrate_adapter_execute
action_engine_run_shell
action_engine_execute_script
action_engine_run_script
action_engine_sudo_command
cli_helper_guarded_execution
cockpit_guarded_execution
```

The first four are orphan spellings not emitted by the derivation table. The
next six belong in `REVIEWED_FUTURE_EXECUTION_CONSUMER_IDS`, not the mintable
set. `cli_helper_guarded_execution` is emitted by no retained row.
`cockpit_guarded_execution` is a surface-class token, not an execution-consumer
id.

If the v21 author follows Section 1 literally and leaves "already-matching"
non-credential ids untouched, the addendum's cross-vocabulary tests and the
fold plan's own Sections 3 and 7 will go RED.

## 2. Correct Target Lists

### `S7_EXECUTION_CONSUMER_IDS`

Replace the entire live v20 block with this exact credential-free target:

```text
dream_apply_proposal
dream_apply_section_edit_proposal
evolution_apply_candidate
workshop_apply_diff
guarded_card_execute
action_engine_write_soul_note
action_engine_edit_soul_section
action_engine_write_any_file
action_engine_append_to_file
action_engine_capability_acquire
action_engine_modify_config
action_engine_register_new_skill
action_engine_delete_file
action_engine_write_file
action_engine_promote_to_core_memory
action_engine_update_baseline
action_engine_git_commit
action_engine_integration_review_plan
brain_swap_model_routing_execute
model_routing_env_write_restart
```

### `NON_MINTABLE_EXECUTION_CONSUMER_IDS`

Keep the v20 split:

```text
NON_MINTABLE_EXECUTION_CONSUMER_IDS = {
    "action_engine_final_mutate",
}
```

`action_engine_final_mutate` must not appear in `S7_EXECUTION_CONSUMER_IDS`.

### `REVIEWED_FUTURE_EXECUTION_CONSUMER_IDS`

Restore the pre-cut reserved-id vocabulary, credential-free:

```text
self_mod_dialog_terminal_execute
cli_helper_execute
cockpit_helper_execute
reviewed_substrate_adapter_execute
action_engine_run_shell
action_engine_execute_script
action_engine_run_script
action_engine_sudo_command
action_engine_git_push
action_engine_install_package
action_engine_kill_process
action_engine_restart_service
action_engine_write_outside_maez
action_engine_restart_critical_service
action_engine_modify_firewall
action_engine_system_reboot
action_engine_free_disk_space
action_engine_delete_temp_file
action_engine_clean_temp_files
action_engine_run_safe_command
action_engine_install_package_t2
telegram_rollback_adapter_execute
```

These ids are not artifact-mint ids in S7.3 v1. Artifact mint and consume reject
them before mutation.

### `SURFACE_CLASSES`

Section 2 of the fold plan remains correct: restore the pre-cut surface-class
family minus `credential_management_execution`.

## 3. Covenant Safety Check

The wrong v20 mintable-list entries did not create a live shell/sudo mint path.
The derivation table and adapter matrix still route `run_shell`,
`execute_script`, `run_script`, `sudo_command`, and similar dangerous surfaces
to fail-closed exclusions with no mintable consumer id.

So this addendum is not a covenant-reopen and not an exploitable-path finding.
It is a vocabulary-integrity and honesty-clarity fix: a reader must not see
`action_engine_run_shell` in the mintable set and infer that shell execution is
live guarded in S7.3 v1.

## 4. Cross-Vocabulary Audit Required

v21 author verification must include one family-level audit, not per-item spot
checks:

```text
S7_EXECUTION_CONSUMER_IDS
NON_MINTABLE_EXECUTION_CONSUMER_IDS
REVIEWED_FUTURE_EXECUTION_CONSUMER_IDS
SURFACE_CLASSES
```

Required assertions:

```text
S7_EXECUTION_CONSUMER_IDS has exactly the 20 target values in this addendum.
NON_MINTABLE_EXECUTION_CONSUMER_IDS has exactly action_engine_final_mutate.
REVIEWED_FUTURE_EXECUTION_CONSUMER_IDS has exactly the 22 target values above.
SURFACE_CLASSES has exactly the 11 credential-free pre-cut surface-class values.

S7_EXECUTION_CONSUMER_IDS and NON_MINTABLE_EXECUTION_CONSUMER_IDS are disjoint.
S7_EXECUTION_CONSUMER_IDS and REVIEWED_FUTURE_EXECUTION_CONSUMER_IDS are disjoint.
NON_MINTABLE_EXECUTION_CONSUMER_IDS and REVIEWED_FUTURE_EXECUTION_CONSUMER_IDS are disjoint.

Every live_guarded manifest row's execution_consumer_id is in S7_EXECUTION_CONSUMER_IDS.
Every S7_EXECUTION_CONSUMER_IDS value is emitted by at least one live_guarded
manifest row or reviewed derivation row.
Every retained manifest row's surface_class is in SURFACE_CLASSES.
Every SURFACE_CLASSES value is emitted by at least one retained manifest row or
reviewed coverage rule.
```

This audit is the addendum's core correction. It prevents the v21 author from
fixing only the four obvious route ids while leaving the eight broader
mintable-set contaminations behind.

## 5. How This Changes The Fold Plan

This addendum modifies only the approach to Sections 1, 3, and 7:

- Section 1 becomes a whole-block restore of `S7_EXECUTION_CONSUMER_IDS`, not a
  four-token replacement.
- Section 3 must restore the reserved future set and prove pairwise
  disjointness against mintable and non-mintable sets.
- Section 7 must run reverse-direction coverage on the whole vocabulary family.

Sections 2, 4, 5, 6, 8, and 9 remain valid, subject to this addendum's broader
acceptance checklist.

## Plain English

The v21 plan found the right kind of problem but counted too few broken labels.
The v20 cut did not just rename four main route ids; it also let shell-like and
future-only ids drift into the mintable list. No route can actually mint those
dangerous ids, so the covenant is still safe, but the live vocabulary now says
something misleading.

v21 should restore the whole family of labels from the version before the cut,
remove only the credential entries, and run one audit proving the mintable,
non-mintable, reserved-future, and surface-class sets do not overlap or orphan
their values.

