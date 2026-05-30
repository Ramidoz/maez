# Recall-Stack Bundle Resolver + Carrier-Consulted Denial Gate — Design

> 2026-05-30. The default-on pre-req, in the shape the design switchboard converged on (6 roles, every
> claim verified against code). Two composed moves:
> 1. **Bundle resolver** — stop treating the recall triad as three independent flags; make it ONE named
>    capability bundle `MAEZ_RECALL_TRIAD_ENABLED`, resolved to a single `RecallMode` enum. The raw
>    per-flag path is **cut**, so a dangerous partial config is *unrepresentable*, not runtime-rejected.
> 2. **Carrier-consulted denial gate** — the deterministic dated-denial may say "I don't have a dated
>    memory" *only when the recall carrier was actually consulted*. When the carrier was not active
>    (legacy / off), Maez says the *path* was unavailable, never that the memory doesn't exist.
>
> The covenant law behind move 2 (Rohit, 2026-05-30): **absence of consulted evidence is not evidence of
> absence.** "Maez should not say 'I checked the shelf and it isn't there' when the shelf was locked."
> Research-grounded: LaunchDarkly prerequisite/dependent flags + Unleash feature dependencies (parent
> gates children); OpenFeature (flag evaluation carries a *reason/status*, not just a boolean); Fowler
> (constrain toggle count, expose toggle state, keep kill switches); Mahdavi-Hezaveh et al. (toggle
> defaults/metadata/logging). Internal siblings this copies: `resolve_calendar_mode`
> (`core/information_limb/calendar_v1_config.py`) and `resolve_camera_presence_state`
> (`core/body/camera_presence_state.py`) — same shape (env-injection, frozen result, single mode enum,
> fail-closed). This is the third instance of a converging internal pattern, not a one-off.

## Why this shape (what the switchboard corrected from the first draft)

- **The first draft's safety guarantee was false.** The deterministic dated-denial lives at
  `daemon/maez_daemon.py:4054`, a *sibling* of the FOCUSED block, gated only by
  `_date_addressed_turn ∧ ¬_focused_used ∧ reply is None`. `_date_addressed_turn` is computed purely
  from the question text (`absolute_recall_cue`), independent of every recall flag. So *legacy* mode
  emits the denial too — failing closed to legacy does **not** make it "impossible." Both legacy and the
  dangerous partial land at the **same** 4054 floor. Verified by reading the code, not asserted.
- The honest fix is therefore not "prevent the denial" but: (a) make the unsafe *partial* path
  impossible (bundle resolver + cut raw flags), and (b) make the denial *wording honest* about whether
  the carrier was consulted (carrier-consulted gate).
- **Five raw read-sites, not three.** The draft missed `daemon/maez_daemon.py:984`
  (`_daemon_parallel_web_search_enabled`) and `skills/telegram_voice.py:68`
  (`_telegram_pipeline_a_web_search_enabled`, *inverted*). Both read `MAEZ_DISPATCHER_ENABLED` raw.
- **Four divergent truthiness parses** across those sites (`.strip().lower() in {…}` vs `== "1"` vs
  `in (…)` no-strip vs `!= "1"`). The resolver unifies to one canonical parse.

## Guarantee (the corrected, honest statement)

> The bundle resolver makes unsafe partial recall paths impossible. Dated-memory **absence** language may
> only be emitted when the dated recall carrier was actually **consulted**. If the carrier was
> unavailable (legacy / off / not active on this path), Maez says the capability/path was unavailable —
> never that the memory does not exist.

## Architecture

### 1. The resolver — `core/routing/recall_stack_config.py`
```python
class RecallMode(Enum):
    LEGACY = "legacy"
    TRIAD  = "recall_triad"

@dataclass(frozen=True)
class RecallStackConfig:
    mode: RecallMode
    reason: str                       # "bundle_enabled" | "off" | "legacy_raw_flags_ignored:<which>"
    @property
    def triad_on(self) -> bool:
        return self.mode is RecallMode.TRIAD
    @property
    def carrier_available(self) -> bool:   # the recall carrier is available iff the triad is on
        return self.triad_on

_TRUTHY = {"1", "true", "yes"}
BUNDLE_FLAG = "MAEZ_RECALL_TRIAD_ENABLED"
RAW_RECALL_FLAG_NAMES = (
    "MAEZ_DISPATCHER_ENABLED",
    "MAEZ_FOCUSED_COGNITION_ENABLED",
    "MAEZ_LIVING_RECALL_ENABLED",
)

def _truthy(v: str | None) -> bool:
    return (v or "").strip().lower() in _TRUTHY

def resolve_recall_stack(env: Mapping[str, str] | None = None) -> RecallStackConfig:
    env = os.environ if env is None else env
    if _truthy(env.get(BUNDLE_FLAG)):
        return RecallStackConfig(RecallMode.TRIAD, "bundle_enabled")
    raw = [n for n in RAW_RECALL_FLAG_NAMES if _truthy(env.get(n))]
    if raw:
        return RecallStackConfig(RecallMode.LEGACY, "legacy_raw_flags_ignored:" + ",".join(raw))
    return RecallStackConfig(RecallMode.LEGACY, "off")
```

**Why there is no `invalid_partial` mode and no derived booleans.** The bundle flag is the *only* input
that turns the triad on. The raw three flags are **cut** — they no longer enable anything; they only
affect the WARN `reason`. So there is exactly one valid "on" syntax and no partial joint state to detect:
the dangerous config is unrepresentable in `RecallMode`, not runtime-rejected. Every call site reads the
*same* `triad_on` — four bools that could disagree cannot exist (Creative + Future-Rohit). This also
means **no second source of truth** — the back-compat `D∧F∧L → triad` rule is gone (cut now, per Rohit:
`config/.env` does not pin the raw three; they are default-absent).

**Resolution / no module-level cache.** `resolve_recall_stack` is a pure function of `env`. It is called
**once per turn** at the top of the recall region and the result threaded to every consumer in that turn
(no mid-turn divergence). It is **not** memoized at import (that would freeze the first read and break the
existing test suites that mutate `os.environ`, and break the kill-switch). Tests inject `env=`.

**Availability is not consultation.** `RecallStackConfig.carrier_available` only says the recall stack is
enabled for the process/turn. It does **not** prove the carrier was consulted on this specific path. A
turn can have `triad_on=True` while a separate gate still prevents focused recall from running (for
example, the current daemon excludes `source == "voice"` from focused cognition). The denial wording
therefore must use a **turn-local execution fact** (`_recall_carrier_consulted`), not the config property.
This is the same locked-shelf rule one layer deeper.

### 2. Single source of truth — migrate all five raw read-sites
| Site | Today | After |
|---|---|---|
| `core/brain/brain_loop.py` `_dispatcher_enabled` | raw `MAEZ_DISPATCHER_ENABLED` | `resolve_recall_stack().triad_on` |
| `core/brain/brain_loop.py` `_living_recall_enabled` | raw `MAEZ_LIVING_RECALL_ENABLED` | `resolve_recall_stack().triad_on` |
| `daemon/maez_daemon.py` `_focused_cognition_enabled` | raw `MAEZ_FOCUSED_COGNITION_ENABLED` | `resolve_recall_stack().triad_on` |
| `daemon/maez_daemon.py:984` `_daemon_parallel_web_search_enabled(transcript)` | raw `MAEZ_DISPATCHER_ENABLED == "1"` with transcript-sensitive gate | `not (resolve_recall_stack().triad_on and bool(transcript.strip()))` (preserve today's nuance: triad transcript present ⇒ no legacy web side-path; empty transcript ⇒ legacy web fallback may still run) |
| `skills/telegram_voice.py:68` `_telegram_pipeline_a_web_search_enabled` | raw `!= "1"` (inverted) | `not resolve_recall_stack().triad_on` |

After migration **no production module reads the three raw flag names** except the resolver. (A CI guard
test enforces this — see Testing.)

### 3. Carrier-consulted denial gate — `daemon/maez_daemon.py:4054`
Thread the resolved bundle config into the turn, then compute `_recall_carrier_consulted` from the
selected execution path; replace the two-way dated-denial branch with a three-way one:
```python
if _date_addressed_turn and not _focused_used and reply is None:
    if not _recall_carrier_consulted:          # legacy / carrier not active on this path
        reply = ("I can't check my dated recall from this path right now — that capability "
                 "isn't active. I won't answer it from recent chat or guesswork.")
    elif _had_confirmed:                         # carrier found a dated item, synthesis failed
        reply = ("I have a dated memory for that, but I couldn't pull it together just now. "
                 "Ask me again in a moment.")
    else:                                        # carrier consulted, no dated match
        reply = ("I don't have a dated memory for that window. I'm not going to answer it "
                 "from recent chat or guesswork.")
    _focused_used = True
```
`_recall_carrier_consulted` is a turn-local execution fact, not a config alias. Set it true only when the
dated turn actually entered the focused/dated recall path; the simplest structural predicate is
`_reply_decision.mode is ReplyMode.FOCUSED` (or an equivalent `_focused_attempted=True` set immediately
before the focused assemble call). This matters because `triad_on=True` can still be prevented from
consulting the carrier by other gates (`source == "voice"` today, and any future source-specific
exclusion). This is the move-2 scope expansion Rohit authorized: the denial site is no longer config-only
territory — it must tell the truth about *why* it has no dated item.

### 4. Telemetry (Fowler "expose toggle state" + OpenFeature reason + the toggle paper)
- **Startup line** (once, at daemon start, like calendar/camera): `recall_stack mode=<…> reason=<…>
  raw_flags=[bundle=<set|unset> dispatcher=<…> focused=<…> living=<…>]` — all four inputs shown
  including unset, so "I thought I set the bundle but set two raw flags" is legible from the boot log.
- **Per-resolve / per-turn** the same `mode`/`reason` is available for witness assertion.
- When `reason` starts with `legacy_raw_flags_ignored:`, log at **WARNING** ("deprecated raw recall
  flags set but ignored; use MAEZ_RECALL_TRIAD_ENABLED") — loud, never silent.

### 5. Kill switch (single, documented)
`MAEZ_RECALL_TRIAD_ENABLED=0` (or unset) reverts the whole organ to LEGACY. No multi-var scramble.
Document it as THE revert.

## Non-goals
- **The monitored flip + soak are the rollout, after this lands** — flipping the bundle flag on in
  `config/.env` (owner-authorized), latency p50/p95, the long-tail probes, ordinary-turn feel-witness,
  and the coverage-novelty observability field are the *experiment*, not this slice. This slice makes the
  bundle + honest denial wording exist so the flip is safe and self-witnessing.
- No new recall *capability* (ranking, temporal v2, living-recall internals untouched).
- No generic `BundleResolver` base class / framework (YAGNI — three concrete lookalike resolvers is the
  right abstraction level; calendar/camera deliberately share a shape, not an inheritance tree). New
  future bundles (intake bus onward) ship **bundle-only with no raw-flag path** — this slice's raw-flag
  deprecation is a one-time tax for already-live flags, not a pattern to copy.
- No Personal Data Intake Bus.

## Testing
**Truth-table test** `tests/test_recall_stack_config.py` — enumerate `(bundle, dispatcher, focused,
living)` and assert `(mode, reason)`:
- bundle truthy (any raw combo) → `(TRIAD, "bundle_enabled")`.
- bundle falsy, no raw → `(LEGACY, "off")`.
- bundle falsy, each raw subset (`D`, `F`, `L`, `D∧F`, `D∧L`, `F∧L`, `D∧F∧L`) → `(LEGACY,
  "legacy_raw_flags_ignored:<which>")`. (These are the cells the first draft left undefined — now all
  defined and benign-legacy.)
- truthiness: `" 1"`, `"TRUE"`, `"yes"` all parse truthy for the bundle; confirm `config/.env`'s
  intended value parses identically.
- `triad_on`/`carrier_available` equal `mode is TRIAD` in every row.

**Carrier-consulted denial test** (daemon/focused) — three rows for a dated query:
- LEGACY (`_recall_carrier_consulted=False`) → "can't check my dated recall from this path" reply; assert it does
  **not** say "I don't have a dated memory".
- TRIAD available but focused not selected for this path (for example `source="voice"` or a direct unit
  fixture with `_reply_decision.mode=LEGACY`) → same path-unavailable wording; assert it does **not** say
  "I don't have a dated memory". This pins the availability-vs-consultation distinction.
- TRIAD + working set with a `confirmed` item but empty synthesis (`_had_confirmed=True`) → "I have a
  dated memory … couldn't pull it together".
- TRIAD + consulted, no dated match (`_had_confirmed=False`) → "I don't have a dated memory for that
  window".

**Web-search gate preservation tests** — migrate the flags without silently changing behavior:
- Daemon: bundle on + non-empty dispatcher transcript → `_daemon_parallel_web_search_enabled(...)` is
  false; bundle on + empty transcript → true (preserves current fallback); bundle off → true.
- Telegram voice: bundle on → Pipeline-A web search disabled; bundle off/unset → enabled.

**Migration guard test** `tests/test_recall_flag_single_source.py` — grep the production tree
(`core/`, `daemon/`, `skills/`) for raw reads of the three flag names; fail if any occur outside
`core/routing/recall_stack_config.py`. (Prevents future re-fragmentation — 20yr-Maez's ask.)

**Regression:** existing triad tests still green; existing witnessed launch-env invocations updated to set
`MAEZ_RECALL_TRIAD_ENABLED=1` instead of the three raw flags (the raw three are now inert + WARN).
Production code outside `core/routing/recall_stack_config.py` must not spell the three raw flag-name
strings directly; telemetry imports resolver-owned constants so the single-source guard remains true.

## Files
- Create `core/routing/recall_stack_config.py` (resolver, `RecallMode`, `RecallStackConfig`).
- Modify `core/brain/brain_loop.py` (`_dispatcher_enabled` / `_living_recall_enabled` → resolver).
- Modify `daemon/maez_daemon.py` (`_focused_cognition_enabled` + `_daemon_parallel_web_search_enabled`
  → resolver; capture `carrier_available` once per turn for mode checks; compute turn-local
  `_recall_carrier_consulted` from the selected reply path; three-way denial gate at 4054; startup +
  WARN telemetry).
- Modify `skills/telegram_voice.py` (`_telegram_pipeline_a_web_search_enabled` → resolver, inverted).
- Tests: `tests/test_recall_stack_config.py`, `tests/test_recall_flag_single_source.py`, and the
  carrier-consulted denial test on the daemon path.
- Update launch-env / witness invocation docs to the single bundle flag.

## Self-review
- **Placeholders:** none — resolver contract, the three resolution branches, the five-site migration
  table, the three-way denial wording, telemetry, and every truth-table case are concrete.
- **Consistency:** one `RecallMode` enum; `triad_on`/`carrier_available` derive from it; all five
  config-read sites use the same resolver; no second source of truth (raw-flag path cut). The denial
  gate intentionally uses a turn-local `_recall_carrier_consulted` execution fact, because availability
  is not the same thing as consultation.
- **Scope:** config resolution + single-source migration + honest denial wording + telemetry. The flip,
  soak, coverage-novelty field, and Intake Bus are explicitly out. Move 2 (denial site) is the one
  authorized expansion beyond config-only.
- **Ambiguity:** "carrier available" is `triad_on`; "carrier consulted" is a turn-local fact that the
  focused/dated recall path was actually selected or attempted. Raw flags with bundle off are defined as
  inert-but-WARN legacy, never a partial behavior path.
