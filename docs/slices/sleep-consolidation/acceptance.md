# Sleep-Consolidation Wiring v0 Acceptance

This slice wakes dormant consolidation organs safely. It does not add new
growth inputs, does not promote daily summaries into core memory, and does not
persist reflection synthesis unless the owner separately enables write-mode.

## Current Defaults

- `MAEZ_REFLECTION_SYNTHESIS_ENABLED` unset: reflection synthesis hook is off.
- `MAEZ_REFLECTION_SYNTHESIS_WRITE` unset: if the hook is enabled, it runs
  dry-run and writes only `logs/reflection_dry_runs/*.jsonl`.
- Dream remains owner-gated: it stores a proposal, not a soul/core-memory write.

## Dream Witness

Run with Maez on the merged code and normal doorman/packet posture.

Pass:

- After a provable no-owner-interaction window of at least 30 minutes, and no
  fresh camera-present reading, the dream gate may fire after its cooldown.
- With fresh owner activity, activity uncertainty, or `_rohit_active_until` in
  the future, the dream gate does not fire.
- If camera is absent, unavailable, stale, or unknown, camera uncertainty does
  not structurally prevent the dream.
- Any dream output remains an owner-gated proposal.
- `consolidation_telemetry` emits `organ=dream` with counts/status/model only.

Fail:

- Dream fires while owner activity is recent or unprovable.
- Dream writes directly to soul/core memory.
- Dream telemetry contains raw memory, reflection text, prompt text, or proposal
  text.

## Reflection Dry-Run Witness

Set:

```bash
MAEZ_REFLECTION_SYNTHESIS_ENABLED=1
MAEZ_REFLECTION_SYNTHESIS_WRITE=0
```

Pass:

- The nightly hook creates `logs/reflection_dry_runs/*.jsonl`.
- The artifact contains candidate reflection text, cited source ids, and drops
  for missing or fabricated evidence.
- No reflection episodes are persisted.
- `maez.log` contains only `reflection_synthesis` counts/path/status and
  `consolidation_telemetry organ=reflection`; no reflection text appears there.
- Owner reads a few artifact rows and confirms grounding/voice before any
  write-mode decision.

Fail:

- Any reflection text appears in `maez.log`.
- Any reflection episode is persisted while `MAEZ_REFLECTION_SYNTHESIS_WRITE=0`.
- Candidate reflections lack citations or read out of voice.

## Consolidation Telemetry Witness

Pass:

- Raw-daily consolidation, dream, and reflection emit
  `consolidation_telemetry summary=...` with exactly:
  `organ`, `inputs_count`, `outputs_count`, `model`, `duration_ms`,
  `rails_blocked`, `status`, `reason`.
- The daily consolidation `model` reports the actually served llama.cpp model
  alias, currently `qwen36-27b`, not the stale requested label
  `gemma4:26b`.
- Telemetry remains content-free: counts, enums, model alias, and timing only.

Fail:

- Telemetry reports the requested label while llama.cpp is serving a different
  resident model.
- Telemetry carries memory text, prompt text, reflection text, or dream proposal
  text.

## Separate Decisions

- Enabling `MAEZ_REFLECTION_SYNTHESIS_WRITE=1` is not part of this slice.
- Consolidating wants, wonderings, lessons, and daily-to-core promotion are not
  part of this slice.

## Reflection Input Hygiene v0 — Re-run Witness

Re-run the dry-run from `main`: `MAEZ_REFLECTION_SYNTHESIS_ENABLED=1`,
write off.

- **Recursion closed:** a fresh `logs/reflection_dry_runs/*.jsonl`; resolve
  every candidate's `source_memory_ids` against `memory/lived_episodes.db`
  with `EpisodeStore.get(id)["source_kind"]` and require zero
  `source_kind=reflection` citations. Candidates should ground only in
  `core_memory`, `followup_doc`, and other real evidence.
- **Voice as a natural experiment:** if the harsh "suppresses technical
  novelty"-class framing is gone, recursion caused it and the input hygiene
  fixed it for free. If it survives clean inputs, open a separate voice/prompt
  slice; this slice changes no synthesis prompt.
- **Write mode remains separate:** only a grounded and in-voice dry-run reopens
  the `MAEZ_REFLECTION_SYNTHESIS_WRITE=1` decision, and that remains a distinct
  later owner call.

## Reflection Voice Grounding v0 — Re-run Witness

Re-run the dry-run from `main`: `MAEZ_REFLECTION_SYNTHESIS_ENABLED=1`,
write off.

- **Grounded:** resolve every candidate's `source_memory_ids` against
  `memory/lived_episodes.db`; require zero `source_kind=reflection` citations,
  and every claim tied to a cited id.
- **In voice:** candidates should read like Maez remembering its own
  construction and gestation — owned voice, first-person where natural — not a
  researcher writing about Maez. Owner's read is the gate.
- **Both must pass** to reopen the separate
  `MAEZ_REFLECTION_SYNTHESIS_WRITE=1` decision. Grounded-but-still-report means
  iterate the prompt wording. In-voice-but-ungrounded fails and should be
  reverted; voice must never buy ungrounding.
