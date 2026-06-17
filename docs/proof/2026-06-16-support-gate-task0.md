# Support Gate Graduation Task 0 Proof

Date: 2026-06-16
Branch: `support-gate-graduation`

## Marked-Draft Seam

Verified against `daemon/maez_daemon.py` before feature code:

- The current focused support hook runs at the post-audit/post-fragment-guard seam:
  `reply` and `_focused_support_evidence_map` are both in scope, and the hook
  currently calls `observe_focused_support(reply, _focused_support_evidence_map,
  ...)`.
- This seam runs before `retain_receipt(marked=reply, ...)`, so replacing
  `reply` with a gated marked draft at this point makes `/receipts` retain the
  gated marked draft.
- This seam runs before `reply = render_natural(reply, ...)`, so the owner-facing
  reply receives the gated marked draft after natural rendering.

## Natural Render

Verified against `core/routing/attribution_render.py`:

- `render_natural` is mechanical: it removes citation markers with
  `_CITE_RE.sub("", marked_draft)`, cleans whitespace, and optionally appends the
  web-evidence suffix.
- It does not call a model and does not paraphrase.
- A plain inline caveat inserted into the marked draft survives marker stripping.

## Flag Matrix

The implementation must keep the gate flag independent of the existing shadow
flag. Intended branch:

```python
_path = decide_support_path(
    gate_enabled=strict_env_flag("MAEZ_SUPPORT_GATE_ENABLED"),
    shadow_enabled=strict_env_flag("MAEZ_GROUNDING_SHADOW_ENABLED"),
)
```

Matrix to enforce in tests:

| `MAEZ_SUPPORT_GATE_ENABLED` | `MAEZ_GROUNDING_SHADOW_ENABLED` | path |
|---|---|---|
| off | off | `none` |
| off | on | `async_shadow` |
| on | off | `sync_gate` |
| on | on | `sync_gate` |

The gate flag alone must be sufficient; the shadow flag must not become a hidden
second switch. The outer daemon readiness guard remains separate: focused reply
used, post-audit ready, and non-empty focused support evidence map.

## SEAM ASSUMPTIONS HELD

YES. The gate can run at the final marked-draft seam and remain observable in
both `/receipts` and the owner-facing natural reply.
