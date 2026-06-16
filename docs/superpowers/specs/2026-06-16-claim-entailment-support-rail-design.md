# Claim-Level Entailment Support Rail (design) — content-honesty Thread A

**Date:** 2026-06-16. Co-designed with Rohit.
**Status:** cruxes resolved; awaiting spec re-review before plan (focused-path re-scope folded after
the audit-path empty-`claimable` discovery; uncited-fallback must-fix +
spec-review HOLD corrections folded).
**Arc:** content-honesty Thread A. Threads B (fresh-vs-memory conflict) and C (self-web-claim
recall hygiene — LIVE) are separate. **NOT** this slice: repairing the `grounding_judge.py`
overclaim/self-history rail (broken: heavy carve-out prompt + thinking-overflow + strict JSON
parse → fail-open) — that is its own "overclaim judge protocol repair" slice.

## Why this exists (the wound + the right rail shape)

Maez can cite `[E1]` and assert what `[E1]` never says. `check_groundedness`
(`core/routing/focused_cognition.py:1446`) only checks cited labels **exist** — never that the
claim is **supported** by the cited evidence's content — and its verdict is **recorded, never
acted on** (`daemon/maez_daemon.py:6590`). The wound is **claim→evidence entailment**, not a
whole-reply judge: *for each important claim, prove the cited evidence actually supports it*
(`evidence + claim → SUPPORTED / UNSUPPORTED / ABSTAIN`).

## What already exists (the embryo — verified)

- **`SupportVerifier` ABC** (`core/cognition/support_verifier.py:20`): `.support(evidence, claim,
  timeout_s) → (label, score, latency_s)`; verdicts `SUPPORTED` / `UNSUPPORTED` / `UNAVAILABLE`.
  `HttpSupportVerifier` posts `{evidence, claim}` to `http://127.0.0.1:8083/support` (0.25s
  timeout, returns `UNAVAILABLE` on any transport/parse failure). The swappable abstraction is
  already there.
- **`grounding_shadow.py`** is **wired to the live audit path** (`core/safety/audited_output.py:253`
  `_observe_grounding_shadow(...)`), non-blocking, **observation-only — gates nothing**. Flag
  `MAEZ_GROUNDING_SHADOW_ENABLED` (**default OFF**). It splits the reply into sentences, calls the
  verifier per sentence, budget-bounded, writes JSONL telemetry. Deterministic floor exists
  (no-evidence / no-sentences / budget-stop).
- **MiniCheck won the audition** (`scripts/grounding_bench/results_grounding.md`): MiniCheck-DeBERTa
  equals the 4B LLM on dangerous false-negatives (0/5 cited-but-unsupported, 0/5
  fabricated-false-specific, 1/4 stale) at **~16× the speed (0.12s vs 1.9s p50) and 0 GPU VRAM**;
  its only cost is 2 false-positives — erring toward over-rejection, the **safe** direction.
- **Deployment gap (service written, not installed):** the MiniCheck service **artifact already
  exists** — `scripts/minicheck_verifier_service.py`, `scripts/maez-minicheck-verifier.template.service`,
  `tests/test_minicheck_verifier_service.py` — but there is **no installed/running `:8083` unit**.
  The live shadow instantiates `HttpSupportVerifier()` → `:8083`, so enabling the shadow today →
  every call `UNAVAILABLE`. v0 **installs/starts/witnesses the existing artifact**, not a new build.
- **WRONG-SEAM defect (the load-bearing discovery):** the shadow is wired to the **audit path**
  (`core/safety/audited_output.py:253` → `shadow_observe(result, (evidence_envelope or {}).get("claimable"), …)`),
  but **`evidence_envelope.claimable` is EMPTY on every live path** — **no `build_envelope(...)` call
  anywhere passes `claimable=`** (`_normalize_claimable(claimable or [])` → `[]`; `ledger_db_path`
  feeds `self_history`, not claimable). So the shadow, even enabled, returns `no_claimable` and
  checks **nothing**. The `[E#]` cited evidence (fresh web block, recalled memory) lives in the
  focused **`WorkingSet`** (`EvidenceItem.local_label` + text, `core/routing/focused_cognition.py:236-246`,
  `:353`), a **separate object the audit-path hook never sees**. Cited-only entailment is impossible
  from `evidence_envelope.claimable`.

## The hook seam (re-scoped to the focused path)

The entailment observation is **re-homed to the focused path**, where the reply and its cited
evidence are both in hand — **NOT** the audit-path `claimable` envelope. Concrete seam: where
`check_groundedness(_focused_result, _focused_working_set)` already runs
(`daemon/maez_daemon.py:6590`), **both** objects are in scope:
- `_focused_result` (`FocusedResult.reply` + `cited_ids`, `focused_cognition.py:389`), and
- `_focused_working_set` (`WorkingSet.items: list[EvidenceItem]`, each with `local_label` + text).

A new non-blocking observation (sibling to `check_groundedness`) enqueues `(reply, label→text map
of the working-set evidence)` to the **reused `GroundingShadow` worker/queue/verifier/telemetry/flag**.
The audit-path hook (which only ever sees empty `claimable`) is **superseded** — left dormant
(emits `no_claimable`) or removed in v0; it is not the entailment seam. Per-sentence citations come
from the same `_CITE_RE = \[E(\d+)\]` (`focused_cognition.py:97`) run per sentence.

**So v0 is "re-home the hook + complete the receipt + wake the instrument," not "build from
scratch":** move the observation to the focused seam, do honest cited-only mapping, install + start
the existing MiniCheck `/support` service, and watch it judge Maez's real cited sentences in shadow.

## The honest-mapping law (crux — resolved, with the must-fix)

A claim is checked against **only the evidence it cites** — never the whole pile. An uncited
sentence must **never** be blessed by evidence it didn't cite (that smuggles the
labels-prove-shape wound into the new rail, [[feedback_labels_prove_shape_not_support]]).

**Mechanism (focused seam):** build a `{local_label → text}` map from `_focused_working_set.items`
(`EvidenceItem.local_label`, text). Split `_focused_result.reply` into sentences; per sentence,
`_CITE_RE` (`\[E(\d+)\]`) gives that sentence's cited labels; look each up in the map; MiniCheck
runs on **only** those cited evidence texts. "in working set" / "resolvable" both mean "the cited
`[E#]` is a key in that label→text map with non-empty text."

Per reply sentence:

| condition | `mode` | verdict | model called? |
|---|---|---|---|
| cites `[E#]`, all present + non-empty | `cited_support` | MiniCheck → `SUPPORTED`/`UNSUPPORTED` | yes (per cited-evidence only) |
| cites `[E#]` not in working set | `unmatched_citation` | `UNSUPPORTED` (deterministic) | no |
| cites `[E#]` but evidence text empty | `empty_evidence` | `ABSTAIN` (deterministic) | no |
| no `[E#]` citation | `no_citation` | `ABSTAIN` (deterministic — **NO support blessing**) | no |
| verifier down/timeout on a `cited_support` sentence | `verifier_unavailable` | `UNAVAILABLE` | attempted |
| (optional, diagnostic) uncited sentence, all working-set evidence | `uncited_all_evidence_diagnostic` | records would-be label **but NEVER counts as grounded** | yes (diagnostic only) |

`unmatched_citation` is exactly `check_groundedness`'s dropped signal, now **acted on** as
`UNSUPPORTED`.

## The receipt invariant (build FIRST — the swappable constant)

One content-light record per checked sentence (verifiers swap behind it;
[[feedback_verifier_swappable_receipt_invariant]], [[feedback_visible_substrate_state_not_chain_of_thought]]):
```
{ claim_hash (+ snippet only under MAEZ_GROUNDING_SHADOW_DEBUG),
  cited_evidence_ids: [E#…],
  support_verdict: SUPPORTED|UNSUPPORTED|ABSTAIN|UNAVAILABLE,
  mode: cited_support|unmatched_citation|empty_evidence|no_citation|verifier_unavailable|uncited_all_evidence_diagnostic,
  verifier: "<name>@<version>" | "deterministic",
  score: float|null,
  latency_ms: int }
```
Plus the existing per-job header (shadow_id, ts, surface, boot_id, counts, status). The
`mode` taxonomy above is **required** in the receipt — it is what makes
"supported-vs-uncited-vs-unmatched" legible and prevents an uncited diagnostic from reading as
grounded.

## MiniCheck `/support` service (install the EXISTING artifact — owner-breath)

The service is **already written** — `scripts/minicheck_verifier_service.py` (wraps
`lytang/MiniCheck-DeBERTa-v3-Large`, POST `{evidence, claim}` → **`{"verdict": SUPPORTED|UNSUPPORTED,
"score": …}`**), `scripts/maez-minicheck-verifier.template.service`, and
`tests/test_minicheck_verifier_service.py`. v0 **installs/starts the existing unit on `:8083` and
witnesses it answering**, sibling to `llama-judge.service` (model off the daemon process, isolated,
swappable, matching the wired `HttpSupportVerifier`). **Patch the service only if Task 0 finds it
insufficient** — do NOT duplicate it. Owner breath to install/enable the unit.

**Response contract (load-bearing):** `HttpSupportVerifier` reads `data.get("verdict")`
(`core/cognition/support_verifier.py:85`); the service returns `{"verdict": …, "score": …}`
(`scripts/minicheck_verifier_service.py:51`). The field is **`verdict`**, not `label` — any
client/test must use `verdict`.

## Posture: receipt-complete SHADOW (v0)

Observe-only — the shadow **never changes the served reply**, behind `MAEZ_GROUNDING_SHADOW_ENABLED`
(default off). v0 = make the receipt claim-level + honest, run MiniCheck live in shadow, and
**witness** that it flags the fabricated-false-specific (Mythos-5 / Claude-Corps) class on real
turns. **Gate** (omit/caveat unsupported claims, honoring two-sided pressure —
[[feedback_two_sided_verifier_pressure]]) and the **verifier-UNAVAILABLE fail-posture** are a
**separate later graduation**, not v0.

## House law for the shadow (spec requirements)

- **Bounded + non-blocking (FIX an existing defect):** queue bounded, verifier timeouts short, and
  **`UNAVAILABLE` never changes the reply**. **Existing defect to fix in v0:**
  `GroundingShadow.enqueue()` currently calls `self._emit(...)` (a telemetry **write**) inside its
  `except queue.Full` branch (`core/cognition/grounding_shadow.py:224-225`) — an I/O write on the
  enqueue path under overload, violating the house law (mirrors the intake-bus enqueue-I/O-free
  law). v0 must make the queue-full path **memory-only / I/O-free** (e.g. bump an in-memory dropped
  counter, flushed by the worker thread, not written inline), with a **full-queue regression test**
  in the shape of Rail 2's full-queue test.

## Task-0 proofs (HARD GATE — docs/proof only, committed first)

1. **MiniCheck service health:** prove `:8083/support` (the existing artifact) installs, starts, and
   answers `{"verdict", "score"}` — **or** that the shadow emits content-light `verifier_unavailable`
   rows and never blocks. Either outcome is a valid Task-0 result; the build must handle both.
   **No service → no fake witness:** if MiniCheck is absent, v0 can still test the deterministic floor
   and receipt shape, but **cannot claim verifier witness** — the ledger/handoff must say so honestly.
2. **Focused-seam reachability (load-bearing — re-scoped):** the entailment observation must reach
   the **focused** seam where reply + cited evidence are both in hand — NOT the audit-path
   `claimable` envelope (which is **always empty**, see WRONG-SEAM defect above). Confirmed at
   design time: at `daemon/maez_daemon.py:6590` both `_focused_result` (reply + `cited_ids`) and
   `_focused_working_set` (`WorkingSet.items`, each `EvidenceItem` with `local_label` + text) are in
   scope; a `{local_label → text}` map is buildable and per-sentence `_CITE_RE` extraction works.
   Task 0 must **prove this concretely at runtime** (instrument the seam: confirm a real web turn
   has ≥1 `EvidenceItem` with a `local_label` the reply cites, and the label→text map is non-empty)
   and confirm the new observation can enqueue **non-blocking** from there. If the focused seam
   turns out NOT to carry the cited evidence at runtime (e.g. on the dispatcher surface the reply is
   produced elsewhere), **STOP** and revisit — do **not** fall back to the empty `claimable` envelope
   or to "check against all evidence" (that is the wound the must-fix forbids).

## Corpus extension (before or alongside shadow — don't block on a rebuild)

Add the witnessed class to `scripts/grounding_bench` corpus: Anthropic/Mythos-5/Claude-Corps-style
items (current-events + version/release fabrication, cited-but-unsupported and fabricated-false-
specific). Re-confirm MiniCheck on the literal wound. This may land **before or alongside** the
live shadow — do **not** gate live shadow on a large corpus rebuild.

## Testing (TDD, fakes)

- **Mapping law (the must-fix):** a `no_citation` sentence → `ABSTAIN`/`no_citation`, **never**
  `SUPPORTED`, even when the whole working set would entail it; the `uncited_all_evidence_diagnostic`
  record (if enabled) carries its would-be label but the sentence's support_verdict stays ABSTAIN.
- **Deterministic floor:** `unmatched_citation` → `UNSUPPORTED` (no model call); `empty_evidence` →
  `ABSTAIN`; no-evidence (empty working set) → ABSTAIN. Use `FakeSupportVerifier` to assert the model is NOT called on
  floor cases.
- **cited_support routing:** a sentence citing `[E1]` is checked against **only** E1's text (assert
  the verifier received E1's evidence, not E2's).
- **Receipt completeness:** every record carries the required fields + a valid `mode`; content-light
  by default (hash, no snippet unless debug).
- **House law:** the **queue-full path is memory-only / I/O-free** — a full-queue regression test
  (Rail 2 full-queue shape) asserts `enqueue()` performs **no `_emit`/telemetry write** when the
  queue is full (only an in-memory dropped-counter bump); `UNAVAILABLE` → reply unchanged.
- **Cited-label mapping (phrase sharply):** with the working-set `{local_label→text}` map, a
  sentence citing `[E1]` maps to E1's text and the verifier receives **only** E1's evidence (not E2's). A sentence with **no `[E#]`**
  → `no_citation` (ABSTAIN). A sentence that **cites `[E1]` but it cannot be resolved** to evidence
  text → `unmatched_citation` (deterministic `UNSUPPORTED`) — **never** `no_citation`, **never** a
  silent all-evidence check. (`no_citation` = the sentence cited nothing; `unmatched_citation` = it
  cited something unresolvable.)
- **Flag off → byte-identical:** shadow disabled → no enqueue, no telemetry, reply untouched.
- **Corpus:** the new Anthropic-class items classify as expected under MiniCheck in `grounding_bench`.

## Scope (explicit)

- **IN:** **re-home the entailment observation to the focused seam** (where `_focused_result` +
  `_focused_working_set` are in hand) + fix the queue-full I/O defect; claim-level receipt (the
  invariant + `mode` taxonomy); honest cited-only mapping (working-set `label→text` + per-sentence
  `_CITE_RE`) + deterministic floor + optional uncited diagnostic; install the MiniCheck `/support`
  service; receipt-complete **shadow** wiring (claim→cited-evidence, verifier-name, latency); corpus
  extension; flag-gated off=byte-identical; tests.
- **OUT (separate slices):**
  - **Gate graduation** (omit/caveat unsupported claims) + the **verifier-UNAVAILABLE fail-posture**
    decision — the next slice after shadow is witnessed.
  - **`grounding_judge.py` overclaim-rail repair** (the thinking-overflow / fail-open bug) — its own
    slice.
  - **Atomic-claim extraction** (sub-sentence) — v0 is sentence-level.
  - Generalizing beyond cited-evidence entailment (e.g. cross-checking against fresh fetch the reply
    didn't cite).

## Covenant rail

The shadow changes nothing Maez says — it only **measures**, witnessably. The honest-mapping law
keeps an uncited claim from borrowing credit it didn't earn. MiniCheck errs toward over-rejection
(safe). The future gate will omit/caveat, never silence (two-sided pressure). The receipt makes the
rail's verdicts true-by-construction, never merely asserted.
