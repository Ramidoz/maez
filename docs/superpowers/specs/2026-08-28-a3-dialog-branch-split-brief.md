# A3 final slice — the dialog branch split (BRIEF, pre-implementation)

Owner-ruled 2026-08-28. The last open A3 mouth. **Do not classify on
`DialogTurnResult(kind)`** — that kind mixes two semantically different
outputs. The split happens at the PROVENANCE/GENERATION boundary.

## 1. Exactly where canned and generated text diverge

Inside `generate_response_turn` (`skills/self_mod_dialog.py:1091`),
which returns `tuple[str, bool]` — a shape that **erases** the
distinction. Three exits:

| Exit | Line region | Provenance |
|---|---|---|
| `llm_fn(context)` returns non-blank | ~1135 | **MODEL** (injected client) |
| `llm_client.chat(...)` returns non-blank | ~1141-1156 | **MODEL** |
| deterministic `fallback` after `except` | ~1158-1168 | **CANNED** |

The canned exit is reached when the LLM raises, returns blank, or is
unavailable. Two *further* canned acks live in the driver and never
enter this function at all: the CANCEL ack ("Cancelled. I won't make
the change.") and the DEFER ack ("Okay, I'll hold this open…"), both of
which return `DialogTurnResult` directly — which is precisely why
`kind=="clarified"` cannot discriminate.

**The seam is the return of `generate_response_turn`.** Nothing
downstream can recover the provenance, so it must be exported here.

## 2. The five values the generation path must export

`persist_model_reply` requires them as mandatory parameters:

1. `model_id` — the resolved responder model
   (`MAEZ_SELF_MOD_RESPONDER_MODEL` or `_PRIMARY_MODEL`); for the
   `llm_fn` exit, the injected client's identity.
2. `prompt_material` — the exact messages sent
   (`_RESPONSE_SYSTEM` + the composed `context`).
3. `soul_material` — the soul text bound to this generation.
4. `evidence_envelope` — **hard requirement**: `persist_model_reply`
   returns `None` immediately when it is absent, so a missing envelope
   is a silent no-record. It must be constructed, never defaulted.
5. `audit_verdict` — the verdict for this reply.

The writer additionally FORBIDS `event_origin` on `model_reply` (same
structural shape that forced the `approval_decision` amendment), which
independently proves `record_organ_event` cannot carry this branch.

Export as a typed result — the ruled pattern, reusing `ProducedReply`'s
shape rather than a new mechanism: text + provenance + the generation
material when provenance is MODEL. **No generic recorder widening.**

## 3. Which recorder each branch uses

| Branch | Recorder | Kind |
|---|---|---|
| MODEL-generated clarification | `persist_model_reply` | `model_reply` |
| Deterministic fallback, CANCEL ack, DEFER ack | `record_organ_event` | `system_event`, `event_origin=self_mod_dialog_ack` |

Recording canned text as `model_reply` would cost six false claims
(taint singleton, model_id, prompt_hash, soul_hash, envelope, verdict).
Recording model text as `system_event` would ERASE real generation
provenance — the eighteenth round's sin in reverse.

## 4. How both branches stay linked

- **Dialog linkage:** `self_mod_dialog_id` (INTEGER). The seam already
  carries it as a named optional on `record_organ_event`; the TEXT
  dialog id rides as typed debt inside `audit_verdict`, never as a type
  lie (twenty-second round).
- **Owner turn:** both branches parent to the SAME owner
  `user_message` recorded for the turn — `parent=` for the seam,
  `parent_turn_id`/`parent_submission_id` for `persist_model_reply`
  (chosen by PROCESS identity, not surface name).

So a dialog turn is always: owner input → exactly one reply row, of the
honest kind, carrying the same dialog id and the same parent edge.

## 5. Dead-lettering if recording fails

Unchanged from every other closure, and asymmetric by design:

- `record_organ_event` never raises; it returns a typed result and
  dead-letters durably. Loss is loud and reconcilable.
- `persist_model_reply` is best-effort by contract and returns `None`
  on failure — including the silent `None` when `evidence_envelope` is
  absent. **That silent path is the risk this slice must not create**,
  so the envelope is constructed explicitly and its absence is treated
  as a build error, not a runtime skip.
- Both call sites sit in their own `try/except`; the dialog reply
  ships regardless. Half-exchange rule: record what you have, thread
  what you can, never withhold one row because the other failed.

## Scope

ONLY this slice. No generic recorder widening, no new turn kind, no
change to `DialogTurnResult.kind` semantics for existing consumers.

## Carried forward — `approval_decision` reader obligation

`approval_decision` admits only `{owner_utterance}` while its bytes are
substrate-RENDERED (`format_resolution_text`). The label is the
schema's claim about whose ACT this is. **A reader must never render
those bytes as a verbatim quote of what the owner typed.** Recorded
here as a standing contract; not reopening A3.
