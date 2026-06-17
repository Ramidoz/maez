# Thin-Evidence Honesty Task 0 Proofs

Date: 2026-06-16
Branch: thin-evidence-honesty
Plan: docs/superpowers/plans/2026-06-16-thin-evidence-synthesis-honesty.md

## 0a — format_for_context consumer classification

Command:

```bash
grep -rn 'format_for_context\b' daemon/ core/ skills/ \
  | grep -viE 'def format_for_context|git_awareness|screen_obs|quality_tracker|reflection|calendar_perception'
```

Findings:

| Consumer | Site | Verdict | Reason |
| --- | --- | --- | --- |
| Dispatcher adapter | `core/dispatcher/external_sources.py:519` | treated synthesis | The rendered block becomes `FreshBlock.text`, then dispatcher transcript, then `turn_evidence_state(...)`; focused/daemon evidence directives can consume the quality line. |
| Legacy `handle_message` web search | `daemon/maez_daemon.py:5719` via `web_format` import at `:5445` | treated synthesis | The rendered `web_context` is consumed by `turn_evidence_state(...)` at `:6127` and by focused assembly. |
| Photo-freshness search inside `handle_message` | `daemon/maez_daemon.py:5809` via the same `web_format` import | mixed / untreated | The normal legacy path would be treated by `turn_evidence_state(...)`, but the photo-focused path passes the same `web_context` as `fresh_context` into `synthesize_photo_turn(...)` (`daemon/maez_daemon.py:6483-6491`, `core/routing/focused_cognition.py:1315-1321`) without the thin directive. Do not opt this call site into the quality line in v0. |
| Voice stream | `daemon/maez_daemon.py:7611` via `web_format` import at `:7548` | untreated prompt | It feeds the voice-stream prompt directly with only "Real search results above. Synthesize, don't list." No `EvidenceState` thin directive is built here. |
| Morning briefing | `daemon/maez_daemon.py:7743` via `web_fmt` import at `:7740` | untreated prompt | `news_text` is inserted into `briefing_prompt`; no thin directive consumes the quality line. |
| Action engine web_search | `core/actions/action_engine.py:1583` | untreated / tool output | Returns the formatted search string from an action. It is not the handled synthesis seam that builds `EvidenceState`. |
| Legacy `skills.telegram_voice` | `skills/telegram_voice.py:3676` | untreated prompt / dead inbound | It appends `web_context` to its own prompt with a generic synthesis instruction. Surface parity work says this module is outbound/legacy, but it still must not receive the body line by default. |
| Module CLI | `skills/web_search.py:435` | owner-facing debug artifact | `python skills/web_search.py ...` prints the formatter output directly to stdout. |
| Surface adapter empty-reply fallback | `skills/surface/maez_adapter.py:1219-1221` | owner-facing fallback risk | If daemon synthesis returns empty, the adapter returns `jarvis_transcript` raw. Dispatcher transcripts can contain the quality line once the dispatcher opts in. The fallback must strip the body-authored quality line before returning raw transcript text to the owner. |

Conclusion: the spec's original unconditional flag-gated line in `format_for_context` would reach untreated prompt paths and a debug owner-facing artifact. The implementation must scope emission to treated synthesis call sites.

Implementation adjustment for Task 1:

- Add an explicit keyword such as `include_quality: bool = False` to `format_for_context`.
- Emit the body-authored `quality=...` line only when both `MAEZ_THIN_EVIDENCE_HONESTY_ENABLED` is true and `include_quality=True`.
- Pass `include_quality=True` only at the treated synthesis sites:
  - `core/dispatcher/external_sources.py:519`
  - `daemon/maez_daemon.py:5719`
  - not `daemon/maez_daemon.py:5809` in v0, because the photo-focused path is not thin-directive-aware.
- Leave voice stream, morning briefing, photo-freshness, action engine, legacy TelegramVoice, and CLI at the default `False`.
- Add a narrow owner-facing fallback guard in `skills/surface/maez_adapter.py`: if the empty-reply fallback returns raw `jarvis_transcript`, strip the body-authored quality line first. This prevents the dispatcher opt-in from becoming owner-visible on the rare empty-reply fallback path.

## 0b — focused-wiring reachability

Commands:

```bash
sed -n '353,390p' core/routing/focused_cognition.py
sed -n '184,215p' core/routing/focused_cognition.py
grep -n 'state = turn_evidence_state\|return WorkingSet\|WorkingSet(' core/routing/focused_cognition.py
sed -n '996,1002p' core/routing/focused_cognition.py
```

Findings:

- `WorkingSet` has no `thin_evidence` field.
- `_citation_instruction(render_version)` takes only `render_version`.
- `_focused_evidence_precedence_instruction()` is argless/static.
- `assemble_working_set(...)` computes `state = turn_evidence_state(...)` at `core/routing/focused_cognition.py:796`, but the `return WorkingSet(...)` at `:959` drops the state.
- There are three `WorkingSet(...)` construction sites:
  - `:959` in `assemble_working_set(...)` — should pass `thin_evidence=state.thin_evidence`.
  - `:1061` in `synthesize_empty_search_reply(...)` — should keep the default `False`.
  - `:1277` in `synthesize_photo_turn(...)` — should keep the default `False` unless a later photo-specific slice decides otherwise.
- Additional direct constructors outside the original plan (`core/cognition/cycle_packet.py:219` and `core/evolution/brain_audition/adapter.py:53`) must remain compatible through the default `False` field.
- Direct test constructors must also remain compatible; keep both `WorkingSet.thin_evidence` and `EvidenceState.thin_evidence` as trailing defaulted fields.
- The focused prompt currently calls `_citation_instruction(working_set.citation_render_version)` at `:1000`, so it cannot receive per-turn thin state without an explicit new keyword argument.

Conclusion: the focused-path wiring is buildable exactly as specified:

`turn_evidence_state(...)` -> `WorkingSet.thin_evidence` -> `_citation_instruction(..., thin_evidence=...)` -> `_focused_evidence_precedence_instruction(thin_evidence)`.

## SEAM ASSUMPTIONS HELD

YES, with two Task-1 adjustments:

1. The body-authored line must be explicitly scoped to treated synthesis call sites using an opt-in formatter parameter.
2. The surface-adapter empty-reply fallback must strip the body-authored quality line before returning a raw dispatcher transcript to the owner.

The focused-state wiring assumption holds.
