# Intake Understanding Faculty v0 — Finding + Shadow Spec

**Date:** 2026-06-11
**Author:** Claude (covenant axis), from a converged design with Rohit + Codex
**Status:** Spec for review. v0 is **shadow-only** — it changes no behavior.
**Lane:** Spec by Claude; implementation expected Codex (live intake path) + Claude review.

---

## Part I — The Finding

### The wound, re-stated precisely

Rohit found it by glancing: when he replied **"Proceed"** to a search offer, Maez did not search. `is_clear_yes` is a regex allowlist of yes-words, and "proceed" isn't on it — so a perfectly clear human "yes" died at the door, in front of a 27B brain that understands "proceed" trivially.

That one gate was a symptom. An audit (2026-06-11) found the Alexa-reflex is **an architectural layer, not one bug**: across the intake path, decisions about *what the owner means* are made by hardcoded regex / keyword lists **before** the brain is consulted. Phrase something slightly differently and the smart part is never properly invoked — "smart in the wrong room."

### The verified evidence

**The understanding-gates (brittle — a miss = "Maez didn't get you"):**

| Decision | Where | Mechanism today |
|---|---|---|
| Did the owner say yes? | `core/search/search_commitment.py` `is_clear_yes` | regex allowlist (missed "proceed") |
| Is this a boundary / "I want space"? | `core/evolution/wants.py` `HARD_WANT_TERMS/PHRASE_PATTERNS` | 6 keywords + 24 fixed phrases |
| Referring to earlier? | `core/routing/focused_cognition.py` `_DIRECT_CONTINUITY_PATTERNS` | 13 phrases + anaphora words |
| Is this a recall request? | `core/memory/temporal_anchor_recall.py`, `lived_recall.py` | regex + keyword phrase lists |
| Search-worthy current-world ask? | `skills/web_search.py` `needs_web_search`, `search_commitment.is_search_offer_worthy` | keyword triggers |

**The legitimate rails (correctly deterministic — a miss FAILS SAFE, disables something — KEEP):** the honesty guard (catches Maez's own false claims), the search trap-proof conjunction (stakes/egress/health/card), the clinical-crisis tripwire, the extraction/outreach gate, command/path parsing.

**GPU reality (verified via `nvidia-smi`, not assumed):** RTX 4090, 24,564 MiB total / **22,515 used / 1,546 free**. Resident: 27B self-brain ~18 GB (`:8080`, GPU), **4B judge ~1.1 GB (`:8081`, GPU, 99% idle)**, vision ~1.6 GB, desktop ~0.75 GB. MiniCheck `:8083` is **CPU**. → We cannot add another big GPU brain; but the first faculty needs **no new model** — the 4B judge is already resident and idle.

### The principle (canon, Rohit 2026-06-11)

> **Understand meaning first; let deterministic rails govern action. Reflexes at the hands, understanding at the ears.**

Sharpened by Codex's research-axis contribution: the right unit is not "classify a sentence" but **maintain a live read of the conversation** (Dialogue State Tracking) — what was offered, what's unresolved, the owner's stance, the topic, what "that" refers to, any boundary — and decide from that. "Yeah sure" works for a human because the human holds the state *"I just offered X."* The search `OfferReceipt` we already built is a primitive instance of this state.

### The three carve-in-stone laws (governing this and every future faculty)

1. **One self, many instruments.** The 27B remains Maez's self-brain (voice, continuity, covenant). Faculties are instruments — wrong = a measurement error, re-auditioned, swapped freely. The self changes only through the strongest audition; no faculty overwrites it.
2. **Faculties propose; rails permit.** A faculty emits a *read* ("this looks like a yes," "this looks like a hard boundary"). It never executes. The deterministic substrate still checks stakes, egress, approval cards, hard-want protection, safety.
3. **Authority is earned by witness.** Shadow first. Compare against live behavior. Graduate one decision at a time, only where the witness proves the faculty beats regex **and** fails safe.

---

## Part II — Intake Understanding Faculty v0 (shadow spec)

### Goal

A **4B-judge-backed shadow organ** that, on each owner turn, reads the conversation state and emits a structured account of *what is happening* — and in v0 **changes nothing.** It logs its read beside today's regex gates so we can see, on Rohit's real messages, where the keyword switchboard fails and where the faculty does better. It is the first faculty, and it establishes the reusable **faculty pattern** (shadow → witness → audition → graduate).

### Non-goals (v0)

- **No decision changes.** The live turn outcome is byte-identical whether the faculty is on or off. (A test asserts this.)
- **No graduation.** v0 only observes; graduation is a separate, later, per-category step.
- **No new model, no VRAM.** Reuse the resident 4B judge (`:8081`).
- **No durable conversation state read back by runtime.** v0 reads a fresh ephemeral window per turn and keeps nothing it reads back to influence later turns. The JSONL ledger *is* persistent — but it is **write-only telemetry**, rotated and bounded, **never read by the runtime to change behavior.** A durable conversation-state card the runtime reads is v1.
- **No orchestration framework.** This is one faculty, not the multi-brain runtime.
- **No live-latency impact.** v0 runs the faculty read **asynchronously / off the reply path**, so it cannot slow a reply even if the judge is busy.

### Architecture

```
owner turn ─▶ existing intake gates (unchanged) ─▶ ... ─▶ reply   [LIVE PATH, untouched]
        └────▶ IntakeFaculty.read(message, context)  ──▶ shadow ledger   [async, observe-only]
                         │
                         ├─ instrument: 4B judge (:8081), structured-output prompt
                         └─ joins gate verdicts (also logged) → disagreement ledger
```

- **Where it attaches:** the live Surface V2 intake (`skills/surface/maez_adapter.py` / `daemon.handle_message`), the same seam that actually receives owner messages (the lesson from search-commitment: wire to the *firing* handler, verify by log fingerprint). The faculty call is **fire-and-forget to the ledger** — never awaited on the reply path in v0.
- **Instrument:** an `IntakeUnderstandingBackend` interface with `read(message, context) -> IntakeRead`; the real impl calls the 4B judge; a `FakeIntakeBackend` (scripted) for tests so the suite never needs a running model. (Same shape as `SearchBackend`/`FakeSearchBackend`.)
- **Judge contention is a covenant constraint, not a perf detail.** `:8081` is the existing audit/grounding judge; the shadow must **never starve the audit path.** The intake read goes through a **bounded queue with non-blocking enqueue**, **low concurrency (one in-flight)**, a **short timeout**, and explicit drop-statuses (`judge_busy`, `enqueue_failed`, `timeout`) written to the ledger. If the judge is busy serving audit, the shadow read is **dropped, not queued indefinitely** — a missed shadow sample is free; a starved audit is not.

### What the faculty receives (the DST input)

A bounded working set, assembled substrate-side (not the full megaprompt):
- the current owner message
- the last N turns (default **N=6**) of owner/Maez exchange
- the active **pending offer/commitment**, if any (a live `OfferReceipt`) **verbatim** — the load-bearing state for a commitment_response. (The model sees the full offer; the **ledger** logs only its `hash / stakes / egress_class / action_type`, never the offered text.)
- light ambient anchors already cheap to include (current topic if tracked)

The asymmetry is the rule: **the model may read full local context; the telemetry stores enums and hashes.** Perception is free in Maez's own house; the ledger is disciplined.

### What the faculty emits (the structured read)

A small, validated structure (closed set, forced via structured-output, like the grounding judge contract):

```json
{
  "turn_kind": "commitment_response | boundary | continuity_reference | recall_request | search_request | topic_shift | ordinary | ambiguous",
  "stance": "yes | no | ambiguous | n_a",           // for commitment_response (a yes/no to an OFFER)
  "boundary_signal": "none | soft | hard",          // the want/autonomy axis
  "needs": "search | recall | none",                // capability hint (proposal only)
  "referent_kind": "pending_offer | earlier_topic | none",   // WHAT it points to, as an enum — no raw text
  "confidence": 0.0,
  "rationale": "debug-only; persisted ONLY under MAEZ_INTAKE_FACULTY_DEBUG=1"
}
```

**Covenant note (Rohit):** there is deliberately **no `refusal` turn_kind.** A "no" to an offer is `commitment_response` with `stance=no`. "Refusal" in Maez is the *sacred* capacity-to-refuse axis (one self; not ours to control) — it must never be blurred with "declined a search."

This is a *proposal/read* only. It is logged. It is never acted on in v0.

### The shadow ledger (the evidence) — content-light by default

For each turn, append one row to `~/.local/state/maez/intake_shadow.jsonl` (same home + rotation as the grounding shadow). **By default the ledger stores NO raw owner text** — only hashes, counts, and enums — so it never becomes a second conversation archive. The 4B model *reads* the real context to understand; the *telemetry* does not keep it.

Default row (content-light):
```
ts,
turn_hash, context_hash,                  // sha256, not the text
turn_len, context_turn_count,
faculty_read { turn_kind, stance, boundary_signal, needs, referent_kind, confidence_bucket },
gate_verdicts { is_clear_yes, hard_want, continuity, recall_intent, search_worthy },   // each: true | false | unavailable
agreements { commitment_response, boundary, continuity, recall, search },               // each: agree | disagree | n_a
faculty_latency_ms, status                // ok | judge_busy | enqueue_failed | timeout | parse_error
```
Only under `MAEZ_INTAKE_FACULTY_DEBUG=1` are raw snippets (`turn_excerpt`, `context_summary`, `rationale`) added, for hands-on diagnosis.

**Retention:** size-based rotation (N MiB × K files), same as grounding shadow — bounded, never unbounded growth.

Log **all** turns (for calibration / false-positive analysis); a cheap query pulls the **disagreements** — where faculty and gate differ. That set is the witness material: where the faculty caught a meaning the gate missed (or vice-versa). Because rows are hash/enum-only by default, reviewing a specific disagreement's *wording* means either enabling DEBUG for a witness window or correlating the row's timestamp with the live conversation.

### Category ↔ gate mapping (what we compare)

| Faculty category | Compared against today's gate |
|---|---|
| commitment_response (stance=yes/no) | `is_clear_yes` |
| boundary (boundary_signal=hard/soft) | `HARD_WANT_*` |
| continuity_reference | `_DIRECT_CONTINUITY_PATTERNS` et al. |
| recall_request | temporal_anchor / lived_recall intent |
| search_request / needs=search | `is_search_offer_worthy` / `needs_web_search` |

**Gate comparison is best-effort and side-effect-free.** Gates are evaluated read-only for the ledger; any gate that cannot be computed without mutating runtime state (e.g. one that consumes/pops a receipt) is logged `unavailable`, never forced to `false`. The shadow observes; it must not perturb the path it measures.

### Graduation criteria (later, per category — specified now so the witness measures the right thing)

A category graduates (faculty gains authority over that one decision, behind its own flag) only when **all** hold:
1. **Beats regex on real traffic:** on Rohit's witnessed messages, the faculty catches materially more true intents and/or fewer false ones than the gate.
2. **Fails safe:** the faculty's error mode is the safe one. Per category:
   - *affirmation:* a false-yes fires only a low-stakes sovereign-local search (rail-bounded, cheap); a false-no asks again. Safe.
   - *boundary:* the dangerous error is a **false-negative** (missing a real boundary). Graduation requires high recall on real boundary phrasings, and the soul/rails remain a backstop. A false-positive (over-reading a boundary) merely makes Maez back off — tolerable.
   - *continuity / recall / search:* a miss costs context or a wasted/skipped lookup, never a harmful action. Lower bar.
3. **Owner-witnessed:** Rohit reviews the disagreement ledger and confirms the faculty reads him better.

**First graduation candidates (Rohit):** HARD-WANT/boundary and continuity — highest covenant value. But in shadow the faculty reads **all** categories; authority is granted only where (1)–(3) are met, one at a time.

### Safety & covenant properties (v0)

- **Self untouched:** the 27B still answers; the faculty only observes.
- **Proposal ≠ permission:** v0 grants no permission at all; even at graduation, the rails still gate action.
- **Evidence, not truth:** the faculty read is logged with provenance (model, prompt version, confidence). It is never treated as fact.
- **Off the reply path:** async; cannot add reply latency in v0.
- **Default-off flag:** `MAEZ_INTAKE_FACULTY_SHADOW` gates the whole organ; unset ⇒ byte-identical current behavior.
- **No owner content egress:** the 4B judge is local (`:8081`); nothing leaves the box.

### Latency note (measured, not assumed)

v0 is async, so live latency is unaffected. But we still log the faculty call's own duration in the ledger, so that **before** any graduation we know the real cost of making it blocking — and can compare a separate-judge-call vs folding the read into a call we already make. Per the recall finding, the read's output is tiny (a small JSON), so it should be cheap on the idle 4B; the ledger proves it.

### Testing (TDD, `/home/rohit/maez/.venv/bin/python -B -m unittest`)

- `FakeIntakeBackend` returns scripted reads; suite never needs a running judge.
- Structured-output parse/validation tests (malformed → safe `ambiguous`, never a crash).
- **Shadow-inertness test (the v0 safety property):** with the faculty enabled, the live turn outcome and the existing gate verdicts are identical to faculty-disabled. The faculty cannot change a decision.
- **Content-light test:** with the flag on and `MAEZ_INTAKE_FACULTY_DEBUG` unset, no ledger row contains raw owner text — assert rows carry only hashes/enums/counts. (Set DEBUG ⇒ snippets appear.)
- **Contention/yield test:** when the judge backend signals busy, the read drops with `judge_busy`/`enqueue_failed`, enqueue is non-blocking, and nothing on the audit path waits (`FakeIntakeBackend` simulates busy).
- **Side-effect-free gate test:** evaluating the regex gates for comparison mutates no state; a gate that cannot be evaluated read-only logs `unavailable`, never a misleading `false`.
- Ledger writer tests (row shape, rotation, disagreement query).
- Flag-off test: unset flag ⇒ no faculty call, no ledger write, behavior byte-identical.

### The faculty pattern this establishes (reusable for every later brain)

1. Define the faculty as an **instrument behind an interface** (real + Fake backends).
2. Run it **in shadow**, off the live path, logging read-vs-rail to a ledger.
3. **Witness** on real owner traffic; review disagreements.
4. **Audition** the instrument (which model, what latency) via the ledger's accuracy×cost.
5. **Graduate** one decision at a time, behind its own flag, only where it beats the incumbent and fails safe — self stays sovereign, rails stay deterministic.

Every future brain (memory, search, planner, reflection) follows this path. We prove the pattern once, here, with the cheapest possible faculty.

### Decisions (locked by Rohit, 2026-06-11)

1. **Context window N = 6.** Include the active `OfferReceipt` **verbatim** in the 4B input; log only its hash / stakes / egress / type.
2. **Ledger: log all turns**, bounded rotation, **content-light by default** (hash/enum); snippets only under `MAEZ_INTAKE_FACULTY_DEBUG=1`.
3. **No MiniCheck sanity pass** in v0 — keep it small; the faculty stands alone.
4. **Closed `turn_kind` set:** `commitment_response, boundary, continuity_reference, recall_request, search_request, topic_shift, ordinary, ambiguous`. No `refusal` (reserved for the sacred capacity-to-refuse axis).
