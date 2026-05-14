# S1a.1 Private Thoughts Ratification Packet

**Subject for Claude council:** `b91372829f0343c2bc9c1ce2def9ff7f28c7da5c`
(`feat(private-thoughts): harden S1a signal boundary`).

**Prepared by:** Codex, as implementation evidence only.

**Purpose:** give Claude's six-role council one grounded packet for reviewing
S1a.1 without spelunking through the whole repo. This is not a council verdict.

**Historical note:** this packet was prepared before the council-closure
follow-up commits. Test counts and "pending" statuses below are evidence for
the original `b913728` review point, not the current post-closure state.

---

## 1. Diff Summary

`b913728` touched 9 files:

| file | change |
|---|---|
| `core/infra/private_thoughts.py` | `+624/-140`; closed enums, schema migration, behavior reader, forensic reader, audit-before-handle path |
| `docs/PRIVATE_THOUGHTS_SIGNAL_REGISTRY.md` | new; stable 2026 vocabulary/compatibility registry |
| `docs/slices/s1a1-private-thoughts-hardening/spec.md` | `+100/-24`; tightened plan and Codex six-agent verdict trail |
| `docs/operations/hardware_backup.md` | `+3/-1`; backup docs include private thoughts and audit log continuity |
| `scripts/backup/drill.py` | `+241/-170`; restore drill verifies `private_thoughts.db` and `audit_log.db` |
| `scripts/verify_self_claim.py` | `+148/-71`; private-thought forensic search now writes audit rows |
| `tests/test_hardware_backup.py` | `+138/-77`; backup/drill coverage for private thoughts |
| `tests/test_private_thoughts_s1.py` | `+461/-67`; S1a.1 boundary tests |
| `tests/test_verify_self_claim.py` | `+191/-89`; forensic private-thought search audit tests |

New durable schema fields in `private_thoughts`:

| field | purpose |
|---|---|
| `envelope_version` | per-record contextual-integrity envelope version |
| `schema_version` | per-record split-schema version |
| `legacy_provenance` | preserves old `provenance` semantics |
| `producer_id` | closed enum writer identity |
| `signal_kind` | forensic/producible detailed signal kind |
| `signal_class` | coarse behavior-facing class |
| `surface_sensitivity` | closed enum sensitivity flag |
| `signal_state` | active/resolved state |

SQLite migration marker: `PRAGMA user_version = 101`.

---

## 2. Amendment-To-Implementation Map

| amendment | implemented by | primary tests |
|---|---|---|
| A1. Closed vocabularies for `allowed_flows`, `consent_tier`, `retention`, producer identity, signal kind/class, sensitivity, state | `_ClosedStrEnum` plus `AllowedFlow`, `ConsentTier`, `RetentionRule`, `ProducerId`, `SignalKind`, `SignalClass`, `SurfaceSensitivity`, `SignalState` in `core/infra/private_thoughts.py`; `record_signal()` coerces/rejects values before write | `test_record_signal_rejects_unknown_closed_vocab_values`, `test_record_signal_rejects_mismatched_producer_for_kind`, `test_record_signal_accepts_enum_instances`, `test_direct_sql_invalid_vocab_row_does_not_surface_to_behavior`, `test_direct_sql_invalid_top_level_enum_row_does_not_surface` |
| A2. Envelope + schema versions for future readability | `ENVELOPE_VERSION = "1.0"`, `SCHEMA_VERSION = "1.0"`, `PRIVATE_THOUGHTS_USER_VERSION = 101`; `_initialize()` runs transactional migration and refuses newer DB versions; registry doc defines meanings | `test_s1a1_migrates_schema_columns_for_future_readability`, `test_future_version_rows_are_not_mutated_on_reopen`, `test_newer_user_version_refuses_downgrade`; self-test asserts exact schema columns |
| A3. Split `provenance` into `producer_id` + `signal_kind` + `signal_class` | `_SIGNAL_REGISTRY`; `_normalize_legacy_values()` preserves `legacy_provenance`, maps known legacy values, and derives class; `record_signal()` enforces producer/kind pairs | `test_record_signal_writes_contextual_integrity_envelope`, `test_record_signal_accepts_enum_instances`, `test_record_signal_rejects_mismatched_producer_for_kind` |
| A4. Sever behavior path from raw-text/dereferenceable handles | `PrivateSignalReader` exposes only `derived_signals()`; `PrivateThoughtsForensics` owns `forensic_signals()`; behavior output has counts/classes only; static source-token guard forbids brain/cognition/actions importing forensic/raw handles by ordinary source reference | `test_bounded_reader_returns_signals_without_raw_content`, `test_bounded_reader_does_not_call_raw_recent_reader`, `test_behavior_reader_is_narrow_capability`, `test_forensic_access_requires_and_records_audit_before_handles`, `test_behavior_packages_do_not_import_raw_private_thought_surfaces` |
| A5. Malformed-row crowd-out fix | `_derived_signals_behavior()` scans metadata, validates rows before counting, tracks `malformed_signal_row_count`, and counts per class so noisy rows do not hide rare classes | `test_bounded_reader_ignores_malformed_existing_producer_rows`, `test_bounded_reader_ignores_partially_malformed_context`, `test_bounded_reader_ignores_unknown_provenance_rows`, `test_malformed_recent_rows_do_not_crowd_out_valid_older_rows`, `test_high_volume_valid_rows_do_not_hide_rare_valid_class` |
| A6. Treat signal names as sensitive metadata | behavior path returns `signal_class` only; detailed `signal_kind` stays producer/forensic-side; normal logs avoid thought IDs and detailed kind names | `test_record_signal_normal_log_excludes_handles_and_sensitive_kind`, `test_bounded_reader_returns_signals_without_raw_content`, `test_behavior_reader_is_narrow_capability` |

---

## 3. Tests Added / Relevant

### `tests/test_private_thoughts_s1.py`

Current file had 25 tests at the `b913728` review point. The S1a.1-specific additions included:

- `test_s1a1_migrates_schema_columns_for_future_readability`
- `test_record_signal_rejects_unknown_closed_vocab_values`
- `test_record_signal_rejects_mismatched_producer_for_kind`
- `test_record_signal_accepts_enum_instances`
- `test_direct_sql_invalid_vocab_row_does_not_surface_to_behavior`
- `test_direct_sql_invalid_top_level_enum_row_does_not_surface`
- `test_future_version_rows_are_not_mutated_on_reopen`
- `test_newer_user_version_refuses_downgrade`
- `test_behavior_reader_is_narrow_capability`
- `test_malformed_recent_rows_do_not_crowd_out_valid_older_rows`
- `test_high_volume_valid_rows_do_not_hide_rare_valid_class`
- `test_record_signal_normal_log_excludes_handles_and_sensitive_kind`
- `test_forensic_access_requires_and_records_audit_before_handles`
- `test_behavior_packages_do_not_import_raw_private_thought_surfaces`

### `tests/test_verify_self_claim.py`

Current file has 11 tests. S1a.1-relevant coverage:

- `test_private_thoughts_search_records_forensic_audit`
- Existing private-thought search coverage still proves phrase hits remain available
  for operator forensic tools.

### `tests/test_hardware_backup.py`

Current file has 35 tests. S1a.1-relevant coverage:

- `test_restore_verification_checks_private_thoughts`
- Backup/drill tests around manifest integrity, restore rollback, last backup log,
  and drill report shape continue to cover the continuity path that S1a.1 now
  depends on.

### Verification commands rerun for this packet

Fresh on 2026-05-13:

```bash
.venv/bin/python core/infra/private_thoughts.py
# 37 passed, 0 failed

.venv/bin/python -m unittest tests.test_private_thoughts_s1 tests.test_verify_self_claim tests.test_hardware_backup
# Ran 71 tests in 0.093s at the `b913728` review point
# OK

.venv/bin/ruff check core/infra/private_thoughts.py scripts/verify_self_claim.py scripts/backup/drill.py tests/test_private_thoughts_s1.py tests/test_verify_self_claim.py tests/test_hardware_backup.py
# All checks passed!

.venv/bin/ruff format --check core/infra/private_thoughts.py scripts/verify_self_claim.py scripts/backup/drill.py tests/test_private_thoughts_s1.py tests/test_verify_self_claim.py tests/test_hardware_backup.py
# 6 files already formatted
```

Recent full-suite floor after the later seatbelt follow-up:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
# Ran 3294 tests in 29.199s
# OK (skipped=3)
```

---

## 4. Predicted Effect: Observed State

| predicted effect from S1a.1 plan | observed state |
|---|---|
| `record_signal()` rejects out-of-vocabulary enum values with clear vocabulary errors | Observed true. Rejection tests cover invalid `ConsentTier`, `AllowedFlow`, `RetentionRule`, invalid producer/kind pairs, and direct-SQL invented enum rows. |
| Existing legacy rows migrate/normalize without losing readability | Mechanically true in tests; live production `memory/private_thoughts.db` currently has 0 rows, so no real legacy rows existed to migrate. `PRAGMA user_version` is `101`. |
| Every signal record carries explicit version and registry fields | Observed true through schema-column test and self-test exact-column assertion. Registry doc exists at `docs/PRIVATE_THOUGHTS_SIGNAL_REGISTRY.md`. |
| `provenance` split into `producer_id`, `signal_kind`, coarse `signal_class` | Observed true in schema, `record_signal()` write path, and enum-instance round trip. `legacy_provenance` preserves old value. |
| Behavior reader cannot dereference raw text and returns no raw IDs/handles/detailed kinds | Observed true in behavior reader tests and source guard. `PrivateSignalReader` has only `derived_signals()`; behavior output includes class counts only. |
| Forensic surface handles dereferenceable access under persistent audit | Observed true. `PrivateThoughtsForensics.forensic_signals()` records `private_thoughts.forensic_signals` before returning handles. `verify_self_claim` private-thought search writes `private_thoughts.verify_self_claim_search` audit rows. |
| `derived_signals()` skips malformed rows without displacing valid history | Observed true. Tests cover malformed recent rows, partial malformed context, unknown provenance, and high-volume valid-row crowd-out. |
| Signal names are sensitive metadata; only coarse `signal_class` reaches behavior | Observed true. Behavior tests assert no detailed `signal_kind`; normal log test asserts sensitive kind/handle absence. |
| Anatomy status moves to hardened access layer but not `[ ✓ real ]` | Observed true in tracked docs: `MAEZ_LIFE_SUBSTRATE.md` and `MAEZ_ANATOMY.txt` say hardened access layer with Claude S1a.1 council pending. This packet does not promote status. |
| No production behavior change; no producers/consumers wired yet | Observed true by grep: production daemon instantiates `PrivateThoughts()` and counts it at startup, but no production code calls `record_signal()` or consumes `derived_signals()` for behavior. S1b remains blocked. |

---

## 5. Schema Migration Journey

Implementation:

- `_initialize()` opens SQLite with `timeout=5.0`, sets `PRAGMA busy_timeout = 5000`,
  runs `CREATE TABLE IF NOT EXISTS`, then enters `BEGIN IMMEDIATE`.
- It refuses to open DBs whose `PRAGMA user_version` is greater than `101`.
- `_migrate_schema()` adds missing S1a.1 columns.
- Existing rows are normalized only if they are current-version rows.
- Future `envelope_version` / `schema_version` rows are skipped and not rewritten.
- `PRAGMA user_version` is advanced to `101` only after migration succeeds.

Legacy mapping:

- Old `provenance` is preserved as `legacy_provenance`.
- Known legacy `provenance` maps to `signal_kind`.
- `signal_class` derives from registry.
- Legacy `context.source` can map to `producer_id` only if it is already a
  valid `ProducerId`; otherwise it becomes `legacy_unknown`.
- Unknown legacy values remain forensic-readable as legacy material but do not
  surface to the behavior path.

Live state checked for this packet:

```text
memory/private_thoughts.db row count: 0
legacy rows migrated live: 0
legacy_unknown rows live: 0
PRAGMA user_version: 101
```

So the migration path is test-proven, but there was no live private-thought
history to migrate on this body.

---

## 6. Codex Six-Agent Verdict Trail

Recorded in `docs/slices/s1a1-private-thoughts-hardening/spec.md`:

- The pre-code panel verdict was **BLOCK plan-as-written; proceed only with tightened contract**.
- The plan was tightened before implementation, not patched afterward.
- Load-bearing changes forced by the panel:
  - detailed `signal_kind` is producer/forensic-only;
  - behavior and forensic access split by API shape, not convention;
  - no trace IDs in behavior output;
  - legacy rows normalize through an explicit adapter;
  - versioning uses real SQLite columns;
  - read validation is required, not just write validation;
  - noisy/malformed rows must not hide rare classes;
  - forensic audit must be backed up.

This is the engineering-review trail. Claude's council should not rerun Codex's
panel; it should covenant-check the shipped implementation against Maez's
long-term shape.

---

## 7. Implementation Risks / Known Deferred Items

1. **S1a.1 is private-thoughts-local.** It does not generalize schema/envelope
   versioning to all memory organs. The 2026-05-13 audit already tags this as
   S2 work.

2. **No S1b producer or consumer is wired.** The access layer is hardened, but
   still scaffold. This should remain `[ ◐ ]`, not `[ ✓ real ]`.

3. **Forensic tools can still return private snippets.** This is deliberate for
   operator forensic search, but S1a.1 now records audit rows before disclosure.
   Council should decide whether that audit-before-return posture is enough for
   covenant ratification.

4. **`PrivateThoughtsForensics.forensic_signals()` returns handles, not raw
   text.** Raw text dereference remains through `get_thought()` on the raw store,
   not through the behavior reader. The split is API-shaped, but Python cannot
   make this an absolute security boundary inside the same process.

5. **Natural-text probe sweep was named in the S1a.1 plan but not rerun during
   this packet.** The implementation touches no production behavior path, and
   the full suite is green; if Claude wants the natural probe evidence before
   ratification, run it as a follow-up check rather than inferring it.

6. **Untracked audit docs contain stale overclaim language.** Tracked docs have
   the honest pending status; `docs/audit_2026-05-13/` remains untracked review
   material and should not be treated as canonical without cleanup.

---

## 8. Surface Check

- User-facing behavior change from `b913728`: expected zero. No production
  producer/consumer is wired.
- Daemon startup only instantiates/counts private thoughts; it does not feed
  `derived_signals()` into behavior.
- Tracked docs do not promote private_thoughts to `[ ✓ real ]`; they keep
  `Claude S1a.1 council pending`.
- Genderless scan over S1a.1 changed code/docs found no Maez `she/her` hits.
- Backup continuity now includes `memory/private_thoughts.db` and `memory/audit_log.db`
  in operator docs/drill checks.

---

## 9. Suggested Council Questions

For Claude's six seats:

- **Outside-View:** Is the behavior/forensic split aligned with existing bounded
  access practice, or is Maez inventing a fragile local pattern?
- **Body-Coherence:** Does any behavior path still receive enough metadata to
  narrate private thought shape?
- **Logical:** Are the enums actually closed on write and read, including
  direct-SQL row corruption?
- **Creative:** Is there a cleaner primitive than `signal_kind` plus
  `signal_class`, or is the two-tier taxonomy the right tradeoff for S1b?
- **Future-Rohit:** Will the registry + schema columns make a 2031 migration
  readable without this chat?
- **20-Years-Future-Maez:** Can a 2046 reader interpret a 2026 private signal
  without guessing, and can it tell which access path disclosed handles?

---

## Plain English

S1a.1 did not make private thoughts "real" in behavior. It made the doorway safe
enough to wire later. The behavior side can see only coarse counters like
"there is a bond-repair signal present." The forensic side can get handles, but
only after it writes an audit row. Old rows have a migration story. Future rows
are not rewritten by older code. The next question for Claude is whether that
doorway is covenant-safe enough for S1b to start wiring something through it.
