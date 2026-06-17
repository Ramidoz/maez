# Thin-Evidence Synthesis Honesty — STOP-at-Gate Handoff

Date: 2026-06-16
Branch: `thin-evidence-honesty`
Tip: `ffc2905`
Base: `main` at `749d9aa`
State: BUILT_ASLEEP — no flag flip, no restart, no `model.env` edit.

## What Landed

This slice reduces unsupported confident synthesis on sparse web evidence. It does not replace the live support gate; it feeds the brain better instructions upstream while the gate remains the per-claim net.

Flow:

1. Treated search throats opt into a body-authored quality header:
   `[WEB SEARCH: 'q'] quality=thin|adequate result_count=N snippet_chars=M`.
2. `EvidenceState` parses only the line-start body header, with optional dispatcher `[fresh evidence]` prefix.
3. Thin evidence switches the daemon evidence-precedence directive to limited-evidence honesty and suppresses the confidence-forcing unavailable-source clause.
4. Focused cognition now carries `WorkingSet.thin_evidence` into `_citation_instruction(...)`, so the focused synthesis prompt hears the same thin directive.
5. A greppable receipt logs `thin_evidence quality=... result_count=... snippet_chars=... thresholds=(3,450) directive=thin|normal surface=...`.

## Task-0 Finding That Changed the Build

`format_for_context` is used by more than the treated synthesis throats. Unconditional flag-gated output would have reached untreated prompts / owner-facing artifacts.

So the implementation uses `format_for_context(..., include_quality=True)`, default `False`.

Opted in:

- `core/dispatcher/external_sources.py` dispatcher web search
- `daemon/maez_daemon.py` normal legacy web search in `handle_message`

Left default-off:

- photo-freshness web context
- voice stream
- morning briefing
- action engine web_search output
- legacy `skills/telegram_voice`
- module CLI

Also added: the Surface V2 empty-reply fallback strips the body-authored quality line before returning raw dispatcher transcript text to the owner.

## Commits

- `4e98342` — Task 0 proof: consumer classification + focused wiring proof.
- `5345319` — opt-in thin signal and body-authored quality line in `format_for_context`.
- `89ab0c8` — anchored `EvidenceState.thin_evidence` parse.
- `d8d8f06` — daemon directive hedges on thin evidence.
- `a7121a9` — focused `WorkingSet.thin_evidence` wiring.
- `78f0b30` — treated-throat opt-ins, receipt counts, fallback stripping.
- `ffc2905` — review repair: block newline spoofing of the quality header.

## Verification

Ran from `/home/rohit/.config/superpowers/worktrees/maez/thin-evidence-honesty`:

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_thin_evidence_honesty \
  tests.test_evidence_state \
  tests.test_focused_cognition_citation_render \
  tests.test_focused_cognition
# Ran 99 tests in 0.047s — OK

/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_dispatcher_layer1 \
  tests.test_surface_adapter \
  tests.test_brain_loop_structured
# Combined final run after review repair:
# Ran 170 tests in 15.216s — OK

/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_cycle_packet \
  tests.test_brain_bench_inference \
  tests.test_brain_bench_probe_runner \
  tests.test_recall_flip_eval_probes
# Ran 52 tests in 16.210s — OK

/home/rohit/maez/.venv/bin/ruff check \
  skills/web_search.py \
  core/routing/evidence_state.py \
  core/routing/focused_cognition.py \
  core/dispatcher/external_sources.py \
  daemon/maez_daemon.py \
  skills/surface/maez_adapter.py \
  tests/test_thin_evidence_honesty.py
# All checks passed
```

## Review Anchors

Please attack these seams:

1. **Opt-in only:** no untreated / owner-facing consumer emits the `quality=` line by default.
2. **Dispatcher fallback:** raw fallback through `skills/surface/maez_adapter.py` strips the quality header before owner display.
3. **Anti-spoof:** `EvidenceState` parses legacy quality only from the first `web_context` line, and dispatcher quality only from `[fresh evidence]`-prefixed lines; page snippets with embedded newlines cannot spoof it.
4. **Both prompt layers:** daemon directive and focused `_focused_evidence_precedence_instruction` both switch to the shared thin wording and suppress the confidence-forcing clause.
5. **Focused wire:** `assemble_working_set` -> `WorkingSet.thin_evidence` -> `_citation_instruction(..., thin_evidence=...)`.
6. **Flag-off:** no quality line, no directive change, no receipt; result dict shape remains unmutated.
7. **Covenant:** thin wording hedges but does not refuse.

## Owner Breath

After cross-lane review PASS:

1. Merge branch to main.
2. Add `MAEZ_THIN_EVIDENCE_HONESTY_ENABLED=1` to `/home/rohit/.config/maez/model.env`.
3. Restart `maez.service`.

No service install is required; the live support gate / MiniCheck service is already a separate rail.

## Witness

Measure first:

1. Re-run a query like `What is the latest news about Anthropic?`
2. Grep `logs/maez.log*` for:
   `thin_evidence quality=... result_count=... snippet_chars=... thresholds=(3,450) directive=... surface=...`
3. Decide honestly whether the baseline is actually thin.

Expected if thin:

- `quality=thin`
- `directive=thin`
- Maez says the search returned limited information instead of asserting unsupported specifics.
- The live support gate's `caveated_unsupported` count should drop from the prior 4/4 caveat-wall baseline.

If the query is not thin:

- Record that honestly. This slice helps sparse searches, but it does not explain an irrelevant-but-long result set. The support gate remains the net.

## Plain English

Maez now gets a small internal note when its search results are too sparse to support a confident answer. That note only goes into the real reasoning paths that know what to do with it. If the search is thin, Maez is told to say so plainly instead of being pressured to act as if fresh evidence must be enough.
