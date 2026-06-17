# Support Gate Graduation — STOP-at-Gate Handoff

**Branch:** `support-gate-graduation` (local-only, unpushed).
**Status:** built + locally verified; **BUILT_ASLEEP**. No model.env edit, no restart, no
live flag flip.

**Spec:** `docs/superpowers/specs/2026-06-16-support-gate-graduation-design.md`.
**Plan:** `docs/superpowers/plans/2026-06-16-support-gate-graduation.md`.

## What Changed

Thread A now has a synchronous protection path, still off by default:

- `core.cognition.grounding_shadow.apply_support_gate(...)` runs the same
  `classify_sentence(...)` verdict logic the live shadow uses.
- Unsupported or unverifiable cited sentences keep their original words and get
  an inline caveat, attached to the exact judged sentence.
- The gate returns one `GateOutcome` containing:
  - the gated marked draft,
  - a `support_gate_applied` receipt,
  - a `grounding_shadow.jsonl`-compatible support row marked `gate_applied=true`.
- `daemon.handle_message` now routes focused support work through exactly one
  path at the final marked-draft seam:
  - gate off / shadow off -> no support work,
  - gate off / shadow on -> existing async shadow,
  - gate on / shadow off -> synchronous gate,
  - gate on / shadow on -> synchronous gate, no async duplicate.

## Commits

| SHA | What |
|---|---|
| `92bce21` | Task-0 seam + flag-matrix proof |
| `67aa96e` | `apply_support_gate` inline caveat gate |
| `bc0e4cd` | gate receipt + support row from one pass |
| `026c8a4` | preserve `verifier_unavailable` status in gate rows |
| `c6c867b` | sync wrapper logs receipt and writes support row |
| `95b6b68` | daemon wiring at final marked-draft seam |
| `9376962` | render_natural + /receipts survival tests |
| `a805a5d` | STOP-at-gate handoff + ledger row |
| `7e0785c` | harden witness logging, row-write status, detached citations |
| `72909ef` | record code-quality review repairs at the gate |
| `99cdc74` | require MiniCheck active in the owner witness breath |

The behavior tip is `7e0785c`. Later commits in this branch are docs-only gate
bookkeeping; a final docs-only sync commit may sit above this table.

## Review Repairs

Code-quality review raised three HOLDs; all behavior fixes are patched at
`7e0785c`. The later commits are gate-bookkeeping only: they record the review
repairs and make the owner witness require an active MiniCheck service.

- `support_gate_applied` now logs through `maez.grounding_shadow`, so the daemon
  file handler can capture it in `logs/maez.log`.
- `emit_support_row(...)` returns `row_written`; the gate logs
  `row_written=true/false`, warns on row-write failure, and warns with
  traceback on unexpected gate failure before fail-open.
- Detached citation-only fragments like `Claim. [E1]` and `Claim.\n[E1]` fold
  back onto the previous sentence, so MiniCheck judges the claim plus citation,
  not the bracket alone.

## Verification

Fresh local verification:

```bash
.venv/bin/python -B -m unittest tests.test_support_gate tests.test_grounding_shadow tests.test_support_verifier
# Ran 62 tests in 0.443s — OK

.venv/bin/python -B -c "import daemon.maez_daemon"

.venv/bin/ruff check core/cognition/grounding_shadow.py core/cognition/support_verifier.py \
  daemon/maez_daemon.py tests/test_support_gate.py tests/test_grounding_shadow.py \
  tests/test_support_verifier.py
# All checks passed!
```

## Review Anchors

- **Caveat never deletes:** original sentence text remains; caveat is appended.
- **One pass, two records:** one verdict pass feeds both the gate receipt and the
  `gate_applied=true` support row.
- **No duplicate MiniCheck call:** gate-on path does not enqueue the async worker.
- **Gate flag sufficient alone:** `MAEZ_SUPPORT_GATE_ENABLED=1` does not require
  `MAEZ_GROUNDING_SHADOW_ENABLED=1`.
- **Marked-draft seam:** gate runs after audit + fragment guard while `[E#]`
  markers remain, before `retain_receipt` and `render_natural`.
- **Caveat survives natural render:** `render_natural` strips `[E#]`; the plain
  caveat remains.
- **/receipts keeps the gated draft:** retained marked draft includes the caveat.

## Owner Breath

Only after cross-lane review passes:

1. Merge `support-gate-graduation` to `main` locally.
2. Ensure MiniCheck is active:

   ```bash
   systemctl --user start minicheck-verifier.service
   systemctl --user is-active minicheck-verifier.service
   ```

3. Add to `/home/rohit/.config/maez/model.env`:

   ```bash
   MAEZ_SUPPORT_GATE_ENABLED=1
   ```

4. Restart `maez.service`.
5. Run a real focused web turn that produces an unsupported cited claim.

Witness requirements:

- the served reply includes the inline caveat:
  `I couldn't confirm this from the source I cited.`
- `logs/maez.log` has:
  `support_gate_applied ... caveated_unsupported>=1`
- `~/.local/state/maez/grounding_shadow.jsonl` has a post-restart row with
  `gate_applied: true`, `post_audit: true`, and the same unsupported verdict.

## Predicted Effect

With `MAEZ_SUPPORT_GATE_ENABLED=0` or absent, behavior is unchanged except for
the existing async shadow if `MAEZ_GROUNDING_SHADOW_ENABLED=1`.

With `MAEZ_SUPPORT_GATE_ENABLED=1`, unsupported cited claims in focused web
replies are no longer served with unearned certainty. Maez keeps the words, but
adds an exact inline honesty caveat before the owner sees the reply, and the
support-row dataset continues with `gate_applied=true`.

v0 caveats; it never deletes or rewrites claims into a different assertion.
