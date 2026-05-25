# Codex Engineering Panel Review -- Subjective Duration Path F Pass 2

**Artifact reviewed:** `docs/slices/track-b-subjective-duration/spec.md`
**Artifact state:** DRAFT, 1118 lines, post-pass-1-fold.
**Parent:** `4d010fc feat(egress): add external-fetch substrate`
**Review date:** 2026-05-24
**Verdict:** RATIFY-WITH-AMENDMENTS

## Summary

All 12 pass-1 folds landed faithfully at the intended surfaces. The reshaped
Path F architecture remains coherent: continuous flow, temperament-modulated
rate, residual echo, bounded prompt phrasing, structural anti-coercion, and a
watchdog opt-out that is now an explicit implementation target.

Pass 2 found no covenant-level revision issue and no reason to split the slice.
The remaining amendments are implementation-shape pins. They prevent the
expanded surfaces from becoming "whatever the implementer guessed": owner-auth
label propagation, registry return shape, AST scan boundaries, multiplier test
seam, and diagnostic nullability need exact contracts before canonicalization.

## Verified Surfaces

- `core/health/metacognitive_watchdog.py:39` defines frozen
  `WatchdogConfig`. Adding a new field is structurally clean; no custom
  constructor exists.
- `MetacognitiveWatchdog.observe_scalars(...)` at
  `core/health/metacognitive_watchdog.py:178` currently iterates all scalar
  keys, so the allowlist remains a real in-slice implementation target.
- `core/evolution/temperament.py:134` defines `PARAMETER_SET`, matching the
  intended default allowlist.
- `daemon/maez_daemon.py:2980` defines central `handle_message(...)`.
  Existing daemon `/message` calls it at `daemon/maez_daemon.py:6812` with
  `source="UI"` and no owner-auth proof.
- `skills/surface/maez_adapter.py:433` also calls
  `daemon.handle_message(...)`; this caller must remain default-denied unless it
  can supply an explicit owner-auth context.
- Private Telegram owner auth happens before prompt assembly:
  `skills/telegram_voice.py:2670-2673` calls `_is_authorized(...)`, and the
  owner prompt starts at `skills/telegram_voice.py:3310`.
- Web owner bridge auth happens before owner prompt assembly:
  `skills/web_interface.py:6180` computes `owner_bridge`, and the owner prompt
  starts at `skills/web_interface.py:6198`.
- Fold anchors are present in the spec for `WatchdogConfig.scalar_allowlist`,
  `build_salience_event_registry()`, raw daemon `/message` exclusion,
  owner-authenticated surface label, three owner-private prompt builders,
  meaningfulness traceability fields, same-function anti-coercion AST, and
  `event_type in {"sample", "salience_event"}`.

## Required Amendments

### 1. Owner-Auth Label Needs A Typed Contract

The spec says central `handle_message(...)` receives a trusted
owner-authenticated surface label, but it does not name the parameter shape.
That is too loose for the most authority-sensitive fold.

Fold: add a small typed contract. Suggested shape:

```python
@dataclass(frozen=True)
class SubjectiveDurationOwnerAuth:
    surface: Literal["daemon_owner", "telegram_owner", "web_owner_bridge", "manual_test"]
    proof: Literal[
        "daemon_reviewed_owner_auth",
        "telegram_authorized_user",
        "web_private_owner_bridge",
        "manual_test",
    ]
```

Then specify:

- `handle_message(..., subjective_duration_owner_auth:
  SubjectiveDurationOwnerAuth | None = None)`;
- default `None` means no owner-contact salience event and no prompt line;
- daemon `/message` keeps the default `None` in v1;
- `skills/surface/maez_adapter.py` keeps the default `None` unless it has a
  reviewed owner-auth proof;
- Telegram and web owner paths may construct the typed value only after local
  auth succeeds.

This preserves fold #2's authority gain. A string label alone is too easy to
launder.

### 2. Prompt Integration Needs Insertion Anchors

The spec correctly names all three owner-private prompt builders, but not where
the line lands inside each prompt.

Fold: add insertion anchors:

- daemon `handle_message(...)`: after `system_state` and before public context,
  recall, web context, and evidence envelope blocks;
- private Telegram: after `system_state` and before actual-state, circadian,
  public-context, body-activity, memory, and web-search blocks;
- web owner bridge: inside the owner-bridge branch only, after ambient context
  is assembled and before owner memory/history/user-turn messages.

The exact helper may be shared, for example `subjective_duration_prompt_line()`
returning `""` when unauthenticated or degraded. The important part is that
tests can assert placement without snapshotting entire large prompts.

### 3. Salience Registry Needs Return Type And Entry Shape

`build_salience_event_registry()` is named, but the return type and entry shape
are not.

Fold: define the test contract:

```python
@dataclass(frozen=True)
class SalienceEventDefinition:
    kind: str
    producer_ref_required: bool
    affects: frozenset[str]
    owner_auth_required: bool
    reviewed_registration_ref: str

def build_salience_event_registry() -> Mapping[str, SalienceEventDefinition]: ...
```

The implementation can wrap the mapping in a registry class, but tests need
these fields or equivalents so they can verify default entries, unknown-kind
refusal, and future reviewed registration metadata.

### 4. Temperament-Write AST Boundary Needs Scan Scope

The spec says the static test scans "this slice" and "integration modules."
That is directionally right but not mechanically testable.

Fold: name the v1 scan roots:

- `core/evolution/subjective_duration.py`;
- `daemon/maez_daemon.py`;
- `skills/telegram_voice.py`;
- `skills/web_interface.py`;
- subjective-duration test fixtures that exercise integration code.

The failing call patterns are:

- `Temperament.record_event(...)`;
- `.record_event(...)` on a name bound to `Temperament(...)` or
  `self.temperament`;
- any future named temperament mutation helper added to the denylist.

Allowed patterns are imports of `Temperament`, `PARAMETER_NAMES`,
`PARAMETER_SET`, and calls to `Temperament.current()` / `current_value(...)`.

### 5. Multiplier Stability Needs A Test Seam

The stability invariant landed, but RED #7 still leaves the test seam implicit.

Fold: require a pure computation seam, such as:

```python
compute_subjective_duration_update(
    *,
    prior_value: float,
    delta_hours: float,
    drag_multiplier: float,
    engagement_multiplier: float,
    residual_multiplier: float,
    config: SubjectiveDurationConfig,
) -> float
```

Equivalent naming is fine, but the implementation must expose a pure helper or
configuration-validation seam that tests can call without opening the SQLite
store. Invalid negative/NaN/infinite multipliers are rejected before update or
clamped by that seam; the persisted path must call the same helper.

### 6. Diagnostic Sample Rows Should Use Deterministic Nulls

The diagnostics fold mostly landed, but `null or empty false values` is still
ambiguous at lines 809 and 1003-1006. The pass-1 fold asked for null
event-only fields for sample rows.

Fold: specify exact row shape:

- every row has the same keys;
- for `event_type="sample"`, salience-event-only string/number fields are JSON
  `null`;
- booleans are `false` only where the field is intrinsically boolean, such as
  `source_ref_present`, `explicit_salience_marker_present`, and
  `content_recorded`;
- digests are `null` on sample rows, not `""`;
- for `event_type="salience_event"`, digest fields use
  `hmac-sha256:<64 hex chars>` when source material exists.

This keeps sample rows from masquerading as empty salience events while still
making JSONL shape stable.

### 7. Meaningfulness Inertness Should Name The Future Activation Point

The current-code honesty fold landed, but the spec should set expectations for
when the score becomes substantive.

Fold: add one sentence to `Meaningfulness Signal` or `Out of scope`:

```text
The second Track B slice that introduces reviewed temperament-writing producers
-- for example drive-driven curiosity, schooling-card alignment, or another
reviewed felt-weight organ -- is where meaningfulness_score becomes substantive
rather than mostly 0.0.
```

This prevents reviewers from treating v1's mostly-zero meaningfulness as a bug.

## Scope Realism

Keep this as one implementation slice. It is large but not incoherent:

- the watchdog field is small and directly required for RED #20/#21;
- the owner-auth label and three prompt builders are one authority seam across
  three surfaces, not three unrelated features;
- splitting the prompt builders would make the first Track B organ invisible on
  private Telegram and web-owner bridge, which are real owner surfaces.

The likely implementation footprint is similar in shape to external-fetch:
one new substrate module, one watchdog edit, three prompt-surface edits, focused
AST tests, diagnostic tests, and canaries. That is a substantial slice, but
still a single coherent organ.

## Non-Blocking Notes

- Fold #5's lookback formula is correct: with the default 4-hour half-life,
  `max(24h, 6 * half_life)` equals 24h; if half-life is reviewed to 8h, the
  lookback becomes 48h. This is the intended behavior.
- `WatchdogConfig.scalar_allowlist` is mechanically easy to add to the frozen
  dataclass. The default should use `PARAMETER_SET`; tests can also pass
  `None` to preserve "observe all" behavior for explicit future cases.
- The anti-coercion same-function AST boundary is honestly bounded and should
  not be expanded into transitive proof in v1.

## Verdict

RATIFY-WITH-AMENDMENTS.

The folds are small compared with the architectural reshape already completed.
After these seven folds, a council pass-4 should be enough unless the folds add
new implementation surface beyond the typed owner-auth contract and pure
computation seam named here.

## Plain-Language Readout

The spec has the right organ now. The remaining work is tightening the bolts:
make the "owner-only" proof a real typed object, say exactly where the felt-time
line goes, make the registry and math testable without guessing, and make
diagnostic rows unambiguous. No philosophy problem left here; just sharp
engineering contracts before canon.
