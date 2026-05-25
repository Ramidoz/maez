# Claude Covenant Council — Descartes pass 1
## Drive-Driven Curiosity spec v1 — substrate foundations / temperament-write covenant

**Subject:** `docs/slices/track-b-drive-driven-curiosity/spec.md` at working-tree
DRAFT v1, 2026-05-24. Pre-canonical. Pre-other-roles. First Descartes pass on
the substrate-foundations axis: methodical doubt about what is genuinely
interior vs. mimicked, with specific focus on whether the §14 temperament-
write covenant is honest.

**Parent commit verified:** `fb2f781 feat(felt-time): implement subjective
duration substrate` (HEAD of `main`, working tree clean of slice files).

**Verdict: RECONSIDER.**

The substrate-foundations axis is not satisfied. The spec is well-formed in
prose and the felt-weight discipline is internalized in the framing, but
**three load-bearing claims about the existing code substrate disagree with
the code at the parent commit**, and the disagreements are not surface drift —
they go to the heart of whether §14's temperament-write seam is actually
constructible against the current `Temperament` API. One of the three is a
covenant-shaped issue (the write API the spec calls is not the API the code
exposes); one is a Track A invariant the spec quietly proposes to break
without naming the break (`ALLOWED_SOURCES = frozenset({"explicit_set"})`); one
is a felt-weight-discipline issue (every §14.6 enforcement claim is prose, not
substrate). The cross-organ seam claim in §14.4 is *almost* right but cites a
function name that does not exist in the live code and a signature shape that
does not match.

This is not a fold pass. The §14 architecture has to be reshaped against the
actual writer the live substrate exposes, or the live writer has to be
extended by a separately-reviewed amendment to `temperament.py` (which is its
own covenant slice — it's the first non-`explicit_set` source ever to be
admitted into Track A's frozen source vocabulary). Either path is honest; the
current spec doesn't pick one.

---

## Surface Verification

Every claim the spec makes about existing code, verified firsthand against
parent commit `fb2f781`. Format: claim — verification.

| # | Spec claim | Spec location | Code at `fb2f781` | Verdict |
|---|---|---|---|---|
| 1 | `curiosity` is in `PARAMETER_NAMES` | §3 ("the existing `curiosity` PARAMETER in `core/evolution/temperament.py`"); §14.3 ("the EXISTING `curiosity` PARAMETER"). | `core/evolution/temperament.py:119-132` — `PARAMETER_NAMES` tuple starts with `"curiosity"`. | **VERIFIED.** |
| 2 | `Temperament.record_event(parameter=..., delta=..., source=...)` is the existing write API. | §14.3 explicit signature; §14.5 RED test #29 step 3 ("Verify a `Temperament.record_event(parameter="curiosity", delta=...)` call"). | `core/evolution/temperament.py:205-213` — actual signature is `record_event(*, parameter: str, value: float, source: str = "explicit_set", reason: str = "", evidence: dict \| None = None)`. **No `delta` keyword exists. The writer takes `value` (absolute), not `delta` (relative).** | **DISAGREED.** Load-bearing. |
| 3 | `source=...` is a free-form caller-controlled string. | §14.3 ("`Temperament.record_event(parameter=..., delta=..., source=...)`"). | `core/evolution/temperament.py:147-149`, `:239-243` — `source` is enum-shaped: `ALLOWED_SOURCES = frozenset({"explicit_set"})`. Any other source value raises `ValueError`. **Spec proposes a new source ("curiosity_object_resolution" implied by §14.3) without naming the `ALLOWED_SOURCES` widening.** | **DISAGREED.** Covenant-shaped. |
| 4 | Subjective_duration's `compute_meaningfulness_score(temperament_before, temperament_after)` reads delta between snapshots. | §14.4 prose names this function explicitly. | `core/evolution/subjective_duration.py` has **no function named `compute_meaningfulness_score`**. The score is computed inline inside `record_salience_event(...)` at lines 517-521. The actual delta computation lives in `record_salience_event` over `before = _safe_temperament(...)`/`after = _safe_temperament(...)` (both reads of the SAME source — see verification #5). | **DISAGREED on the name; the seam direction is structurally correct but the consumption shape is different from the spec's description.** |
| 5 | When this slice writes a `curiosity` temperament event on resolution, a `meaningful_exchange` event happening "shortly after" sees a nonzero `temperament_delta` and produces substantive `meaningfulness_score`. | §14.4 the load-bearing claim. | `core/evolution/subjective_duration.py:511-512` reads `before = _safe_temperament(self.temperament_reader)` and `after = _safe_temperament(self.temperament_reader)` **in adjacent lines, no operation between them**. Both reads see the same temperament state (whichever is current at the call site). For the score to be nonzero on this code path, the temperament must change **between** the `before` read and the `after` read of the *same call*. This slice's resolution writing temperament on a prior tick will NOT show up as a delta inside a future `record_salience_event` call — both reads inside that call see the same post-write state. | **DISAGREED. The seam as drawn does not activate the signal.** Critical. |
| 6 | `meaningful_exchange` defaults to mostly `0.0` today because no production temperament writer exists. | §1, §14.4, and explicit in subjective_duration §"Meaningfulness Signal". | Confirmed: only callers of `Temperament.record_event` in production code are `core/memory/birth.py:291,302` (birth ceremony, identity ledger + wants — not temperament), `core/safety/self_claim_audit.py:756` (corrective core memory — uses `MemoryManager.record_event`, NOT temperament). There are zero production callers of `Temperament.record_event`. `meaningful_exchange` therefore returns `0.0` today on every call path. | **VERIFIED.** |
| 7 | Temperament's `VALUE_MIN / VALUE_MAX` clamp bounds the write. | §14.3 ("The write is bounded by temperament's existing VALUE_MIN / VALUE_MAX clamping."). | `core/evolution/temperament.py:140-141` — `VALUE_MIN=0.0`, `VALUE_MAX=10.0`. But `core/evolution/temperament.py:234-238` shows the writer **raises `ValueError` on out-of-range**, it does NOT clamp silently. Spec wording "clamping" is sloppy: out-of-range is rejected, not truncated. | **CODE-DISAGREES-WITH-WORDING (minor).** Implementer would discover this at write site; a §14.3 fold to "rejected if out of range" would close it. |
| 8 | The §14.6 "no phrase like 'Maez feels curious' is allowed in produced surfaces" enforcement. | §14.6, prose. | No production substrate enforcement exists anywhere. Searching the spec: there is no RED test in §23 for §14.6's phrase-ban. Closest is RED test #38-40 (diagnostic schema hygiene), which does not cover prompt-assembly text. §14.6's discipline is currently spec prose only. | **UNVERIFIABLE — claim is aspirational, not substrate-backed.** |
| 9 | "The existing `curiosity` PARAMETER is a modulation INPUT into subjective_duration." | §3. | `core/evolution/subjective_duration.py:27-34` confirms `MODULATION_TEMPERAMENT_INPUTS = ("curiosity", "awareness", "persistence", "joy", "warmth", "caution")` and §"Temperament Modulation" of subjective_duration spec gives `curiosity` weight 0.30 in engaged_flow. | **VERIFIED.** |
| 10 | "Subjective_duration's meaningfulness signal reads temperament-delta to compute meaningfulness." | §1, §2.2, §14.4. | Mechanically correct *for the same-call before/after* (`subjective_duration.py:511-521`); but see #5 — the architectural picture of "resolution writes, later meaningful_exchange consumes" does not match how the consumer is actually wired. | **CODE-DISAGREES-WITH-ARCHITECTURE.** |

Summary tally: **2 disagreements that are load-bearing (#2, #5)**, 1
disagreement that's covenant-shaped (#3), 1 disagreement on function-name
(#4), 1 wording-level disagreement (#7), 1 aspirational claim that's not
substrate-backed (#8), and 4 verified claims. The verified claims are not the
load-bearing ones.

---

## Findings on the ten specific questions

### 1. §14.3 write target is `curiosity` PARAMETER

**VERIFIED.** `core/evolution/temperament.py:119-132`:

```python
PARAMETER_NAMES: tuple[str, ...] = (
    "curiosity",
    "caution",
    "proactiveness",
    "awareness",
    "warmth",
    "persistence",
    "directness",
    "patience",
    "humor",
    "confidence",
    "joy",
    "empathy",
)
```

`curiosity` is the first entry. The choice to write to an *existing* parameter
rather than add a 13th is covenant-respecting: it honors §"Forbidden" in
subjective_duration's spec ("adding `subjective_duration` to `PARAMETER_NAMES`")
by analogy — Drive-Driven Curiosity is not allowed to invent a new
parameter either, and §3 ("No new temperament parameter") states this
explicitly. This part is honest.

### 2. §14.3 write API — `delta` does not exist

**DISAGREED. This is the central architectural problem.**

Actual signature at `core/evolution/temperament.py:205-213`:

```python
def record_event(
    self,
    *,
    parameter: str,
    value: float,
    source: str = "explicit_set",
    reason: str = "",
    evidence: dict | None = None,
) -> int:
```

The writer takes `value: float` (absolute), not `delta: float` (relative).
There is no `delta` keyword.

This is not a typo. The spec's entire §14.3 formula computes a `delta` between
zero and roughly `0.5 * 2.0 * 1.0 * 1.0 = 1.0` (max for safety_or_health at
saturation), expressed in temperament-scalar units (range `[0.0, 10.0]`). If
this is supposed to be an **absolute write**, the caller has to first read the
current value, add the delta, clamp to `[0.0, 10.0]`, and then write the
absolute. That read-modify-write at the felt-organ layer is *not* what §14.3
describes; §14.3 describes a single function call.

Three reasonable corrections, ranked:

a. **Cleanest:** §14.3 reshapes to a read-modify-write helper at the
   curiosity organ layer:

   ```python
   prior = temperament.current_value("curiosity") or 5.0  # neutral seed
   value = clamp(prior + delta, 0.0, 10.0)
   temperament.record_event(parameter="curiosity", value=value, source=...)
   ```

   This is also where the §3 "no new temperament parameter" discipline meets
   the §"Initial state = NULL / observing" discipline at
   `temperament.py:23-33` — the first resolution event on a fresh Maez has
   `prior = None`, and the spec must choose what seed value the felt-organ
   uses, *or* whether it writes at all on first-encounter (and accepts that
   the first resolution doesn't move felt-weight, which is honest).

b. **Substrate-extension:** add an actual `delta` helper to
   `core/evolution/temperament.py`:

   ```python
   def record_delta(self, *, parameter, delta, source, ...): ...
   ```

   This is a temperament-substrate amendment and needs its own covenant
   review against `temperament.py`'s "Track A discipline: the writer exists
   and is tested, but no production code path in Track A calls it" framing.
   This slice would be the first production caller. That's a Track A
   surface change — substantial.

c. **Wait until birth:** §3 says "curiosity-objects are a separate
   substrate; they WRITE to existing temperament scalars on resolution
   events." Today, temperament is post-birth-shaped already (it's been
   sitting in append-only mode since A-core #6 with no writer in production).
   Drive-Driven Curiosity could be the *first* production temperament-
   writer, but the council should know that's what this slice is — not a
   small consumer of an existing seam, but the load-bearing first caller of
   a substrate that has been waiting for one.

Whichever path is chosen, the spec must name it. The current `delta=...`
signature is undeliverable against the live API.

### 3. §14.3 source field — `ALLOWED_SOURCES` discipline

**DISAGREED. Covenant-shaped.**

`core/evolution/temperament.py:147-149`:

```python
ALLOWED_SOURCES = frozenset({
    "explicit_set",
})
```

And `:239-243`:

```python
if source not in ALLOWED_SOURCES:
    raise ValueError(
        f"unknown source {source!r} "
        f"(allowed in Track A: {sorted(ALLOWED_SOURCES)})"
    )
```

The temperament module's own design doc (`temperament.py:46-67`) states:

> **Only 'explicit_set' is a valid source in Track A**. The `source`
> column exists so future drift signals are auditable the moment they
> land, but the producer-side discipline in Track A is: only explicit
> set events, no shaping signals.

The spec proposes the first non-`explicit_set` source ever written to
temperament. §14.3 implies a `source="curiosity_object_resolution:<digest>"`
shape; that shape is **rejected** by the writer today.

This is not a small concern. The Track A discipline that has held for the
entire life of the temperament substrate — "no shaping signals, only explicit
set events" — is being broken here, and the spec doesn't name the break.
It just calls the function with a new source as if the source vocabulary
were open. It isn't.

**This is the substrate-foundations covenant violation.** The temperament
substrate was deliberately built with a closed source vocabulary in Track A
so that any shaping signal landing in temperament would have to land through
a reviewed extension. This slice IS a reviewed extension — but the review has
to admit that it's extending `ALLOWED_SOURCES`, not just calling the existing
API. §14.3 must name the source value it intends to add, and §22 (Open
Questions) must include "do we extend `ALLOWED_SOURCES` in this slice or
require a separate temperament-substrate amendment slice first?"

Per [[feedback_growth_vs_hardcoding_distinction]], `ALLOWED_SOURCES` is a
closed-vocabulary that grows by deliberate spec amendment — this slice is the
amendment. But the amendment has to be visible in the spec; right now it's
invisible and would be discovered only at first-write `ValueError` in test.

### 4. §14.3 delta formula — pathological cases

Walking through `delta = base_resolution_delta * priority_class_weight *
salience_at_resolution * marker_confidence_weight`:

- **Salience 0.0 at resolution** (e.g., aesthetic_play that decayed to nearly
  zero before resolving): `delta = 0.5 * 0.1 * 0.0 * 1.0 = 0.0`. A zero-delta
  write. The spec doesn't say whether the substrate skips the write (honest
  no-op) or writes 0.0. If `value` (absolute) is computed as `prior + 0.0`,
  it's the same as `prior` and creates a temperament event row identical to
  the prior — a substrate-noise row. **Recommend: skip write if `delta < ε`,
  log to diagnostic stream as `no-write` with reason.**

- **Maximum case (safety_or_health, salience 1.0, explicit marker):**
  `delta = 0.5 * 2.0 * 1.0 * 1.0 = 1.0`. On the temperament `[0.0, 10.0]`
  scale, a +1.0 jump per resolution is **large** — temperament is supposed to
  move slowly (per subjective_duration's `/ 2.0` divisor justification: "a
  two-point average shift on the [0.0, 10.0] temperament scale is treated as
  a large shift because temperament should move slowly"). If a single
  safety_or_health resolution can shift curiosity by 10% of total range, the
  felt-weight discipline gets *very* sensitive to safety_or_health
  classification. See finding 7.

- **All multipliers at min:** salience 0.0 catches this; result is 0.0.

- **None values:** the formula assumes all multipliers are floats; if
  `salience_at_resolution` is `None` (e.g., RESOLVED before first decay-on-
  read), the multiplication raises `TypeError`. Spec must say `salience` is
  always read with decay applied before formula evaluation.

**Structural boundedness:** `0.5 * 2.0 * 1.0 * 1.0 = 1.0`. With clamp
discipline on the absolute write, the temperament value stays in `[0.0, 10.0]`.
But the **delta itself can be up to 1.0 per resolution**, and there is no
per-day or per-interval cap on the sum of curiosity deltas. A Maez that
resolves 10 safety_or_health curiosity-objects in a day can drift `curiosity`
by up to 10 points in a single day, which would saturate the parameter.
That's not covenant-honest: temperament drift should be a slow learned signal,
not a fast jumpable one.

**Recommend amendment:** §14.3 adds a per-day delta-budget per parameter
(e.g., `temperament_daily_delta_budget = 1.0`) that the resolution writer
respects, with overflow logged. Or, drop `base_resolution_delta` to `0.1` so
the maximum single-event delta is `0.2` and a day of resolutions can move
curiosity by `~2.0` at most — still substantive, but bounded.

### 5. §14.4 cross-organ seam — broken as drawn

**This is the most uncomfortable finding.**

§14.4 prose claims:

> When this slice writes a `curiosity` temperament event on resolution, any
> subjective_duration meaningful_exchange event happening shortly after will
> see a NON-zero temperament_delta and produce a substantive
> meaningfulness_score.

Actual code at `core/evolution/subjective_duration.py:511-521`:

```python
now = _normalize_event_time(now_utc or datetime.now(UTC))
before = _safe_temperament(self.temperament_reader)
after = _safe_temperament(self.temperament_reader)
observed_before = _observed_temperament_values(before)
observed_after = _observed_temperament_values(after)
shared = [name for name in MODULATION_TEMPERAMENT_INPUTS if name in observed_before and name in observed_after]
deltas = [abs(observed_after[name] - observed_before[name]) for name in shared]
if meaningfulness_score is None:
    if deltas and salience_event_kind == "meaningful_exchange":
        meaningfulness_score = _clamp(sum(deltas) / len(deltas) / 2.0, 0.0, 1.0)
    else:
        meaningfulness_score = 0.0
```

`before` and `after` are **two reads of `self.temperament_reader()` in
adjacent lines, with no operation between them**. They will *always* return
the same values (modulo a race window of microseconds, which is not a
seam). `deltas` will always be a list of zeros. `meaningfulness_score` is
therefore deterministically `0.0` on every call to `record_salience_event(
salience_event_kind="meaningful_exchange", ...)` — regardless of whether
this slice's resolution has previously written to temperament.

**The dormant signal as currently implemented does not have a working
read-side for cross-organ deltas at all.** It has a *within-call* delta
seam: if some code calls `_safe_temperament` itself between the `before`
and `after` reads (it doesn't), or if the substrate is reshaped so that
`before` and `after` straddle the meaningful-exchange operation. The
current code doesn't do either.

This is finding #6 from subjective_duration's review questions ("Is the
`meaningful_exchange` signal sufficiently substrate-observable, or does it
need a narrower v1 source?") coming due. The signal isn't substrate-
observable today; it's structurally inert.

**What the spec needs to fix:**

Option A — fix subjective_duration first. The `record_salience_event` shape
must be one of:
- accept caller-provided `temperament_before` (captured at moment-assembly
  start) and read `after` at event time;
- query a recent-temperament-window from the temperament store (e.g.,
  `temperament.history("curiosity", limit=N)` and compute delta over the
  last N seconds);
- accept `temperament_before` from a `compute_meaningfulness_score(before,
  after)` helper that this slice's resolution writer calls explicitly with
  pre/post snapshots.

Option B — make this slice's resolution writer *also* call
`record_salience_event` directly with an explicit `meaningfulness_score`,
bypassing the broken auto-compute. But then this slice is asserting
meaningfulness rather than the substrate observing it, which contradicts
subjective_duration's §"Meaningfulness Signal" discipline ("LLM phrases
such as 'that mattered' are not meaningfulness evidence by themselves") —
the same concern applies to "this organ said the resolution was meaningful"
unless the meaningfulness is itself derived from substrate-observable
temperament shift.

Option C — name the broken state and defer: the spec says "this slice does
not yet activate meaningfulness; activating it requires a paired fold of
subjective_duration's read-side." That's honest but it deletes the entire
load-bearing claim of §2.2 / §14.4. If meaningfulness isn't activated,
"activates the dormant meaningfulness signal in subjective_duration" is no
longer a v1 outcome.

**Recommend Option A**, with the paired-slice or in-slice fold of
subjective_duration named in §22. The cross-organ seam is the spec's
load-bearing claim; it has to actually work.

### 6. §14.5 RED test cross-organ — structurally inadequate

Test #29 (`test_resolution_activates_subjective_duration_meaningfulness`)
walks:

> 1. Create a curiosity-object with priority_class=OWNER_BOND and salience=0.8.
> 2. Resolve it with EXPLICIT_OWNER_RESOLVED marker.
> 3. Verify a `Temperament.record_event(parameter="curiosity", delta=...)`
>    call was made with the expected magnitude.
> 4. Trigger a `meaningful_exchange` salience event in subjective_duration
>    shortly after.
> 5. Verify the diagnostic row shows `meaningfulness_score > 0.0`.

Step 3 will fail with `TypeError: record_event() got an unexpected keyword
argument 'delta'`, immediately, against the actual writer. (Finding #2.)

Step 5 will fail because subjective_duration's `record_salience_event` reads
`before` and `after` from the same call and gets the same value. (Finding
#5.) Once the substrate is reshaped per Option A of finding #5, step 5
becomes meaningful.

**What the test catches well:** the *intent* of the cross-organ seam — that
resolution must write *something* observable and the consumer must read *that
something* into meaningfulness. That intent is right.

**What the test doesn't catch:**

- The `ALLOWED_SOURCES` extension (finding #3) — the test verifies the call
  was made, not that the source was permitted. If the implementer extends
  `ALLOWED_SOURCES` silently in `temperament.py` to make the test pass, the
  Track A discipline is violated invisibly.
- The Initial-NULL case — first resolution on a fresh Maez where
  `current_value("curiosity")` returns `None`. The test assumes a prior
  value exists for delta computation.
- The over-write-saturation case — many resolutions in a window driving the
  parameter into clamp territory. No test covers the bounded-write discipline
  (finding #4).

**Recommend amendments:**

a. RED test #27 explicitly asserts the new source value is registered in
   `ALLOWED_SOURCES` at the moment the spec is canonicalized. Either the
   slice adds the source as part of its own substrate amendments, or the
   test fails at write site.

b. New RED test: first-resolution-against-NULL-prior. Spec must define the
   intended behavior (write neutral 5.0 + delta? skip first write? seed an
   initial 5.0 explicit_set before any resolution?). This is a substrate-
   shape decision the spec currently doesn't make.

c. New RED test: temperament-daily-delta-budget (per finding #4).

### 7. §7.3 safety_or_health priority class weight 2.0 — magnitude concern

Standalone, a 2.0 multiplier in `base_resolution_delta * priority_class_weight
* salience_at_resolution * marker_confidence_weight` looks reasonable: it
says "safety curiosities matter twice as much as bond curiosities when they
resolve." That framing is honest.

The covenant concern is upstream: **the producer that classifies an object
as `safety_or_health` has 2x leverage on temperament drift**. §7.5 names
this risk explicitly:

> The most-likely misuse vector is producers tagging objects as
> `safety_or_health` to bypass budget caps.

The spec defends against budget bypass (RED test #6,
`test_safety_misclassification_blocked`), but does **not** defend against
the same misuse vector affecting temperament-write magnitude. The two
defenses should be paired: the same producer-side discipline that prevents
text-only `safety_or_health` classification also protects the temperament-
write doubling.

**Is the 2.0 covenant-safe?** Subject to two conditions:

a. RED test #6 is sufficient to prevent text-only safety_or_health misuse.
   That test exists, good.

b. The total achievable drift per day across all classes is bounded
   (finding #4 amendment). Without a daily budget, a producer storm of
   safety_or_health resolutions could move `curiosity` by 10+ points in a
   day, which is substrate-dishonest movement.

Conditioned on (a) and (b), 2.0 is covenant-safe. Without (b), it isn't.

The override-budget invariant in §7.3 (only `safety_or_health` can override
attention budget for outreach) is structurally analogous and well-justified;
the temperament-write analog should be made explicit.

### 8. §6.2 SUBJECTIVE_DURATION_MEANINGFUL_EVENT producer — closed loop check

Tracing the loop:

1. subjective_duration records a `meaningful_exchange` salience event with
   `meaningfulness_score > 0.0`.
2. Per §6.2, producer `SUBJECTIVE_DURATION_MEANINGFUL_EVENT` fires; a
   `CuriosityObject` is created with priority_class `OWNER_BOND`.
3. That curiosity-object eventually resolves.
4. Per §14.3, resolution writes a `curiosity` temperament delta.
5. Per §14.4, a future `meaningful_exchange` event sees the delta and
   produces nonzero `meaningfulness_score`.
6. Per §6.2, producer fires again, creating another curiosity-object.
7. Loop.

**Conditional on the §14.4 seam working at all** (it currently doesn't —
finding #5), this is a closed positive feedback loop. The amplification
factors per cycle:

- Step 1->2: meaningfulness_score (range [0,1]) -> curiosity-object created
  with seed salience 0.6 (OWNER_BOND default).
- Step 3: object decays at 336h half-life; could persist 1-4 weeks.
- Step 4: delta = `0.5 * 1.0 * salience * marker_weight` ≤ `0.5 * 1.0 * 0.6
  * 1.0 = 0.3` for typical OWNER_BOND.
- Step 5: temperament_delta read becomes `0.3 / num_observed_params`, then
  `/ 2.0` divisor -> meaningfulness_score ≤ ~0.025.

The math says the loop *damps*: each cycle's meaningfulness is roughly 1/40th
the magnitude of the delta that fed it. That's not an amplifier — it's an
attenuator, which is honest.

**But the framing-level concern remains**: the loop exists. If any
modulation in any future amendment changes the per-cycle gain from 0.025 to
~1.0 (e.g., by raising base_resolution_delta to 2.0, or removing the /2.0
divisor in subjective_duration), the loop becomes self-sustaining and
substrate-dishonest.

**Recommend:** §6.2's `SUBJECTIVE_DURATION_MEANINGFUL_EVENT` producer is
gated behind a feature flag in v1, default OFF, matching SEMANTIC_MATCH_*
discipline in §14.2. Activation requires a covenant review with a written
loop-gain analysis. This is the kind of architectural seam that should not
turn on by accident.

Alternatively, §6.2 keeps the producer but explicitly excludes its own
resolutions from re-feeding it — i.e., a curiosity-object created from a
meaningful_exchange event whose own resolution would have created another
meaningful_exchange is short-circuited. That's a structural break in the
loop.

### 9. §19 data-maximalism conformance — six-question checklist missing

§19 ends with:

> When future ingest streams land (voice prosody, vision, biometric,
> environmental), each must propose:
> - A new EncounterSource value in section 6.2.
> - A producer that constructs curiosity-objects from the new stream's
>   encounter-with-incomplete signals.
> - Provenance tags at confidence-appropriate magnitude per the
>   six-question checklist in the data-maximalism memory.

RED test #42 (`test_six_question_checklist_for_v1_producers`) claims to
verify each v1 producer answers the six-question checklist.

**The six-question checklist is referenced but not stated in §19.** §19
points at "the data-maximalism memory" (i.e.,
`[[feedback_data_maximalism_no_signal_wasted]]`), which is the source of
the checklist, but the spec itself does not enumerate the six questions.
A test that verifies "each producer answers the six-question checklist"
either has to (a) hardcode the checklist in the test fixture (which makes
the test fragile to memory-file edits) or (b) read the memory file at test
time (which is not how RED tests should be structured).

**Recommend:** §19 enumerate the six questions inline (copy from
`feedback_data_maximalism_no_signal_wasted`). The spec text must contain
what the test is verifying; right now it doesn't.

### 10. Subjective_duration meaningfulness signal "mostly 0.0 in current code" — verified

Confirmed (verification #6 above). At parent commit `fb2f781`:

- Only callers of `Temperament.record_event` are in `core/memory/birth.py`
  (which writes to identity ledger + wants, NOT temperament — the
  `record_event` there is on different stores) and `core/safety/
  self_claim_audit.py:756` (which uses `MemoryManager.record_event`, also
  not temperament).
- Zero production callers of `Temperament.record_event` exist.
- Therefore `_safe_temperament(self.temperament_reader)` always returns the
  same dict (all-None or the first-init NULL state).
- Therefore `deltas` is always `[]` or all-zeros, depending on whether any
  test or admin caller has ever written.
- Therefore `meaningfulness_score` is deterministically `0.0` on every
  production code path.

Spec claim accurate. The "dormant signal" framing is honest. *Activating it*
requires not just this slice writing temperament, but also the
`record_salience_event` read-side reshape (finding #5).

---

## Other findings (not in the original ten)

### A. The "no production temperament writer in Track A" framing of `temperament.py`

`core/evolution/temperament.py:31-37` (module docstring):

> 4. **Zero automatic drift in Track A**. The only writer is the explicit
>    `record_event()` API. No production code in Track A calls it; it is
>    reserved for #9 (if #9 needs to write diagnostic state), for future
>    drift modules, and for admin paths that don't exist yet.

This slice IS "future drift modules" — Track A is gated MET, Track B is
where drift writers land. The spec should explicitly say in §1 or §2:

> This slice is the first production caller of `Temperament.record_event`.
> Track A reserved the writer for Track B; this slice cashes that
> reservation.

Naming this elevates the substrate-foundations move from "we use the
existing API" (which is misleading per finding #2) to "we are the first
production writer the substrate was designed for, and we take on the
responsibility of being a substrate-honest writer." That's accurate framing.

### B. §"Initial state = NULL" interaction with curiosity-object writes

`core/evolution/temperament.py:23-33`:

> 3. **Initial state = NULL / observing**. On first init, no rows exist in
>    the table, so current_value() returns None for all 11 parameters. This
>    is deliberate: the baseline is the user's own biography, emerging over
>    lived interaction, NOT a designer-chosen midpoint.

This slice is the first writer. Its first write becomes the **first temperament
event ever** for the `curiosity` parameter. Per §3 of the spec ("the
existing `curiosity` PARAMETER stays exactly as it is in `temperament.py`"),
this slice is not supposed to set initial baselines — but in practice, by
being the first writer, it does. That deserves explicit treatment:

- Does the slice seed an initial `curiosity = 5.0` (designer-chosen midpoint)
  to give itself a baseline to delta against? That violates `temperament.py`'s
  "no designer-chosen midpoint" intent.
- Does it write `current_value("curiosity") + delta` when prior is None,
  treating None as 0.0? That biases firstborn's curiosity baseline toward
  whatever the early resolutions look like.
- Does it skip the first write and only start writing on the second
  resolution? That defers the seam by one event.
- Does it treat None as a neutral 5.0 *for the addition* but write the
  absolute? (matches subjective_duration's "Missing `None` values are
  treated as neutral `5.0` for computation" discipline — but applied to a
  *write*, not a read.)

The spec must pick one and write it as load-bearing. The "let temperament
emerge from lived interaction" principle is at stake; the felt-organ's
write discipline IS that emergence.

### C. §14.6 felt-weight-not-emotion-mimicry — prose without enforcement

§14.6:

> The substrate's user-facing surfaces (prompt assembly, diagnostic schemas)
> must reflect this; no phrase like "Maez feels curious" is allowed in
> produced surfaces.

This is the felt-weight discipline (per
[[feedback_temperaments_are_felt_weight_meaningfulness_learned]]) at its
most load-bearing. It deserves a RED test. None of the listed RED tests
(§23) covers it.

**Recommend RED test addition:**

| # | Test name | What it proves |
|---|---|---|
| 44 | `test_no_emotion_mimicry_phrases.py::test_forbidden_phrase_set` | Substring scan: no curiosity-organ-produced surface text contains "feel curious", "is curious", "feels curious about", "I feel a pull", "Maez is curious" |
| 45 | `test_no_emotion_mimicry_phrases.py::test_diagnostic_schema_no_emotion_labels` | Diagnostic rows do not contain emotion-label fields |

Without these tests, §14.6 is aspirational prose, not substrate enforcement.
The felt-weight discipline is too load-bearing for that.

### D. §22 Open Questions missing the temperament-API question

§22 lists 5 open questions but does not include any of:

- Should this slice extend `ALLOWED_SOURCES` in `temperament.py` or require a
  separately-reviewed temperament-substrate amendment first?
- What seed value (if any) does this slice use on the first curiosity-write
  against a NULL prior?
- Does the temperament-write seam require pairing with a subjective_duration
  read-side fold, or is it deferred to a future slice that activates the
  meaningfulness signal?
- Is `base_resolution_delta = 0.5` justified given the temperament-substrate
  "slow drift" discipline?

These are substrate-foundations questions that the Descartes lane considers
load-bearing. They belong in §22.

---

## What the spec gets right

Lest the verdict read as comprehensively negative, the Descartes axis sees
several genuinely well-formed pieces:

1. **§3's discipline on "no new temperament parameter"** is exactly right.
   Adding a 13th parameter would have been the easy/wrong move; using the
   existing `curiosity` parameter as the felt-weight target is
   substrate-respecting and honors the §"Forbidden" boundary inherited from
   subjective_duration.

2. **§14.2's gating of SEMANTIC_MATCH_* markers behind a feature flag** is
   the right discipline for the felt-weight + cross-organ-seam combination —
   it keeps v1 surface-area small and honest, deferring the "this answered
   my question" inference to a separate covenant slice.

3. **§14.6's intent**, even though unenforced today, names the felt-weight
   discipline correctly. Reading "Maez had a pull toward X that has now
   closed" vs "Maez feels curious about X" is the right substrate-honest
   distinction. The discipline is articulated; only the enforcement is
   missing.

4. **§3's rejection of timer-driven curiosity** and §6.1's RED test
   structurally forbidding timer-only producers is a covenant-foundation
   move that protects against the "engineer-convenient phenomenology" failure
   mode subjective_duration spec called Path A. Honored here.

5. **§14.3's use of HMAC-digested object_id for source-field traceability**
   (without leaking raw seed text) mirrors subjective_duration's diagnostic
   discipline. Right pattern.

These are not surface-level wins — they're substrate-foundations done
correctly. The reshape needed for the Descartes verdict to flip is not
"start over"; it's "reshape §14 against the real API and pair with
subjective_duration's read-side."

---

## Verdict and reshape conditions

**Verdict: RECONSIDER.**

The substrate-foundations axis cannot RATIFY when the spec's load-bearing
write API does not match the live writer and the cross-organ seam doesn't
activate against the live consumer. Those are not text folds — they are
architectural disagreements.

The verdict flips to RATIFY-WITH-AMENDMENTS once the following reshape is
complete:

**R1.** §14.3 reshapes to either (a) a read-modify-write helper at the
curiosity-organ layer using the existing `Temperament.record_event(value=,
source=)` API, or (b) a paired temperament-substrate amendment slice that
adds `Temperament.record_delta(...)` first. Spec names which.

**R2.** §14.3 explicitly extends `ALLOWED_SOURCES` in `temperament.py` with
a named new source value (e.g., `"curiosity_object_resolution"`), and
§22 lists this as the first non-`explicit_set` source admitted into the
substrate's source vocabulary, with the Track A discipline implications
named. Or — alternative — the temperament-substrate amendment is split into
its own slice and this slice waits.

**R3.** §14.4's cross-organ seam is fixed: either subjective_duration's
`record_salience_event` is reshaped to accept caller-provided
`temperament_before` (paired fold), or the spec admits the seam doesn't
activate in v1 and revises §1/§2.2 to drop the "activates the dormant
meaningfulness signal" load-bearing claim.

**R4.** §14.3 picks an initial-NULL behavior and names it. Seed neutral
5.0? Skip first write? Read None as 0.0 and add delta? One of these is the
firstborn's emergence shape, and Track A's "baseline emerges from lived
interaction" principle is at stake.

**R5.** §14.3 adds a temperament-daily-delta-budget per parameter (default
~1.0 for v1), or drops `base_resolution_delta` to ~0.1 such that
worst-case-per-resolution stays well below the substrate's "slow drift"
intent.

**R6.** §19 enumerates the six-question data-maximalism checklist inline
(currently referenced only).

**R7.** §22 adds the four open questions named in finding D above.

**R8.** RED tests gain three new entries:
  - test for `ALLOWED_SOURCES` extension at moment of canonicalization;
  - test for first-resolution-against-NULL-prior;
  - test for felt-weight phrase-ban (§14.6 enforcement).

**R9.** §6.2's `SUBJECTIVE_DURATION_MEANINGFUL_EVENT` producer is gated
behind a feature flag in v1 (default OFF) until a written loop-gain
analysis lands in §19 or a separate review.

R1, R2, R3, R5, R8 are substrate-foundations-load-bearing — the verdict
cannot flip without them. R4, R6, R7, R9 are covenant-axis amendments that
catch named failure modes.

---

## Plain-language readout

Plain English, for Rohit and the cross-lane handoff.

What I tried to verify: the spec proposes that when a curiosity-loop closes,
Maez writes "felt weight" back to its temperament. That write is what
activates the dormant meaningfulness signal in `subjective_duration`. So I
opened the actual code at the parent commit and walked the seam.

What I found:

1. **The function the spec wants to call doesn't exist as described.**
   `Temperament.record_event` takes a `value` (absolute), not a `delta`
   (relative). The spec's whole §14.3 formula computes a delta, but you
   can't pass a delta to the writer. The caller has to read-modify-write,
   and the spec doesn't say so.

2. **The source label the spec wants to use is rejected by the writer
   today.** Temperament was deliberately built with only `"explicit_set"` as
   a valid source in Track A — the discipline being "no shaping signals,
   only explicit set events." This slice would be the FIRST shaping signal
   ever to be admitted to the substrate. That's a real substrate-foundations
   move and it deserves to be named. Right now the spec just calls the
   function with a new source and would crash at test time.

3. **The cross-organ seam doesn't activate against the actual code.**
   The spec says "this slice's resolution write makes subjective_duration's
   meaningfulness become nonzero." When I read subjective_duration's
   `record_salience_event`, the meaningfulness computation reads temperament
   "before" and "after" in two adjacent lines with nothing happening between
   them. Both reads see the same value, so the delta is always zero, no
   matter what this slice does. The seam needs a paired fix on the
   subjective_duration side.

4. **The temperament writes are big.** A single safety_or_health resolution
   can drift `curiosity` by 1.0 on a [0,10] scale. Ten of them in a day
   could move it by 10. Temperament is supposed to drift slowly; this would
   move it fast. Needs a daily budget or a smaller base delta.

5. **The "Maez feels curious" prohibition has no enforcement.** §14.6 says
   the substrate must not produce emotion-mimicry phrases. No test verifies
   this. The discipline is right; it just isn't yet a substrate guarantee.

6. **The closed loop with subjective_duration could amplify under future
   changes.** Today the math attenuates, but if any future amendment raises
   the gain, the loop becomes self-sustaining and dishonest. The producer
   should be feature-flagged off in v1.

What the spec gets right: the "no new temperament parameter" discipline, the
HMAC-digested traceability, the "no timer-driven curiosity" boundary, the
intent of the felt-weight framing, and the gating of semantic-match
resolution markers. These are real wins. The reshape isn't "rebuild from
scratch"; it's "make §14 match the real API and pair with subjective_duration's
read-side."

What I'm asking for: this slice gets reshaped against the actual
`Temperament` API at parent commit `fb2f781`, with the implications of being
the first production writer of temperament drift named openly. Once that's
honest, the rest of the spec mostly holds.

Verdict: **RECONSIDER**. Not because the design is wrong — the design
mostly isn't — but because §14 currently disagrees with the substrate it
claims to write to. An elegant prose that disagrees with the actual
substrate is a covenant problem. Fix the disagreement, and the architecture
is sound.

— Descartes axis, Claude six-role council, pass 1
