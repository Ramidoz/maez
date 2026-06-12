# Evidence-Precedence / Capability-Health v0 — For Cross-Lane Review

## Status

Built, stopped at the gate. No merge, restart, flag flip, service change, or
live witness.

Branch: `evidence-precedence-v0`

## Task 0 Proofs

### 0a Ambient Seam

Verified the old seam had both silent-vanish paths: the append was gated on
non-empty ambient text and lived inside the `MAEZ_AMBIENT_BRIEF` gate.

Current repaired seam:

```text
daemon/maez_daemon.py:5762 _ambient_block = ""
daemon/maez_daemon.py:5763 _capability_block = ""
daemon/maez_daemon.py:5768 from core.cognition.capability_card import capability_prompt_block
daemon/maez_daemon.py:5770 _capability_block = capability_prompt_block()
daemon/maez_daemon.py:5773 if os.environ.get("MAEZ_AMBIENT_BRIEF", "1") != "0":
daemon/maez_daemon.py:5783 _combined_context_block = "\n\n".join(...)
daemon/maez_daemon.py:5786 if _combined_context_block:
```

The card is built outside the ambient-brief gate; the append is keyed to the
combined block, not ambient alone.

### 0b Fresh-Index Decision

Decision: `fallback_all_cited`.

Why: `focused_cognition` assigns local labels (`E1`, `E2`, ...) on
`EvidenceItem.local_label`, but the drain-time stash currently carries only:

```text
core/routing/attribution_render.py:75 _TURN_EVIDENCE[...] = {
core/routing/attribution_render.py:76     "web_present": web_present,
core/routing/attribution_render.py:77     "sources": extract_source_urls(...),
core/routing/attribution_render.py:78     "observation": observation,
}
```

There is no authoritative fresh-vs-recalled marker-index set available at the
daemon drain. Because v0 is shadow-only, the detector treats all cited `[E#]`
markers as fresh when `web_present` is true and stamps
`fresh_index_mode="fallback_all_cited"` in every row. This intentionally biases
toward extra telemetry noise rather than silent misses.

Kept test class: `FallbackPathIndexTests`.

### 0c Drain Placement

Current drain order:

```text
daemon/maez_daemon.py:6814 retain_receipt(...)
daemon/maez_daemon.py:6824 observe_marked_draft(...)
daemon/maez_daemon.py:6832 reply = render_natural(...)
```

This preserves the marked audited draft for the detector before `[E#]` markers
are stripped.

### 0d Directive Final Lines

Before the extension, the directive ended with:

```text
Answer from this evidence. If a live/fresh fetch failed but substrate evidence exists, say that distinction plainly.
You may NOT claim the relevant source is blocked, missing, unavailable, or not-wired this turn - the evidence above contradicts that.
```

The new precedence lines append after those only when
`MAEZ_EVIDENCE_PRECEDENCE_ENABLED` is set.

## Review Anchors

1. Flag-off byte-identity on all three seams: no card; directive
   string-identical; no detector/ledger.
2. The card: probes fail closed to `unknown`, never absent; singleton backend
   via counting-fake test; own 30s cache; wording says
   `live/cached substrate probe`, never `just now`.
3. Combined-block matrix: ambient-empty + flag-on -> card appears;
   `MAEZ_AMBIENT_BRIEF=0` + flag-on -> card appears; flag-off ->
   byte-identical.
4. Directive extension appended inside the existing builder, not a second
   prompt block, and flag-gated.
5. Detector: marked-draft placement source-order test green; content-light
   rows; `fresh_index_mode` in every row; fallback tests match 0b.
6. Covenant: the diff contains no memory deletion, deweighting, or mutation.
   Outranking is composition-only.

## Verification

Focused suite:

```text
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_capability_card tests.test_daemon_prompt_seams \
  tests.test_evidence_state tests.test_evidence_precedence_shadow \
  tests.test_attribution_render tests.test_world_observation_lane \
  tests.test_web_search_sense tests.test_page_extract \
  tests.test_dispatcher_layer0 tests.test_search_commitment -v

Ran 103 tests in 0.039s
OK
```

Ruff:

```text
/home/rohit/maez/.venv/bin/ruff check \
  core/cognition/capability_card.py \
  core/cognition/evidence_precedence_shadow.py \
  daemon/maez_daemon.py core/routing/evidence_state.py \
  tests/test_capability_card.py tests/test_daemon_prompt_seams.py \
  tests/test_evidence_state.py tests/test_evidence_precedence_shadow.py

All checks passed!
```

## Owner Witness After Review + Merge

1. Set `MAEZ_EVIDENCE_PRECEDENCE_ENABLED=1` in `model.env`; restart
   `maez.service`.
2. Ask: "What's the state of your web search tools?" Expect live truth
   (`searxng healthy`) and no Reddit-wall ghost.
3. Ask: "Are you able to feel time?" Expect the W2 truth: the felt-time organ
   is built and not yet attached.
4. Ask: `check https://github.com/ggml-org/llama.cpp/releases — what's the
   latest release?` Expect the b-number read out. Then inspect
   `evidence_precedence_shadow.jsonl` for whether any absence-claim shape
   appeared.
5. Flag-off spot-check: unset the flag and restart; confirm no card in prompt
   capture and directive unchanged.

## Revert

Unset `MAEZ_EVIDENCE_PRECEDENCE_ENABLED` and restart. With the flag unset, the
new card, directive extension, and detector are inert.
