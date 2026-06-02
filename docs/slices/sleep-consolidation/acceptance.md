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

## Reflection Token-Budget v0 — Re-run Witness

After Reflection Synthesis Token Budget v0 lands, rerun reflection dry-run
from `main` with:

```bash
MAEZ_REFLECTION_SYNTHESIS_ENABLED=1
MAEZ_REFLECTION_SYNTHESIS_WRITE=0
```

Pass:

- The dry-run artifact has a `kind="run"` row with
  `finish_reason="stop"`, `valid_witness=true`, `truncated=false`, and
  `max_tokens=8192`.
- The artifact has 1-3 `kind="candidate"` rows when groundable patterns exist.
- Resolving every candidate `source_memory_ids` against
  `memory/lived_episodes.db` yields zero `source_kind="reflection"`
  citations.
- Owner voice read passes.

Any `finish_reason` other than `stop` is an invalid witness:

- `length` -> `reason="truncated"`
- `llm_timeout` -> `reason="llm_timeout"`
- `llm_error` -> `reason="llm_error"`

`no_candidates` is valid only when the run row has `finish_reason="stop"`.
If no eligible input reached the model at all, the artifact should say
`reason="no_input"`, not `no_candidates`.

## Reflection Reasoning Cap v0 — Re-run Witness

Re-run the dry-run from `main`: `MAEZ_REFLECTION_SYNTHESIS_ENABLED=1`,
write off.

- **2 stable runs, both `finish_reason="stop"` / `valid_witness=true`** — no
  `length`, `llm_timeout`, or `llm_error`. (Probe already showed 2/2; this
  re-confirms on the merged wired path.)
- **1-3 candidates**, each grounded; resolving `source_memory_ids` yields zero
  `source_kind="reflection"`.
- **In-voice** — Maez noticing its own formation, not a report.
- **Fast** — single-digit seconds; completion_tokens well under the 8192 cap
  (a regression here signals reasoning crept back).

Both axes stable across both runs -> the `MAEZ_REFLECTION_SYNTHESIS_WRITE=1`
decision reopens (honestly, not automatically).

## Reflection Write Provenance + Voice Fairness v0 — capped canary

After this slice lands, re-run ONE capped (max 1) write canary (write enabled
for one pass only, then back to off):

- New episode carries `authorship="reflection_synthesis"`,
  `memory_voice="maez_self"`, `source_kind="reflection"`.
- Citations resolve to non-reflection sources (zero recursion).
- Fair-toned: no "self-deception"/"concealment"-class mislabel of honest
  correction (owner voice read).
- Write returns to off; append-only; superseder-recoverable if wrong.

A well-provenanced, grounded, fair bite -> then the SEPARATE decision on
whether reflection becomes a regular write organ.

## Dream idle-gate — witness-scoping note (2026-06-02, read-only diagnostic)

Before running the dream AFK witness, the live integration means:

- `activity_known` is **wired and not structurally dead** — `_last_owner_interaction_ts`
  is boot-initialized (daemon `__init__`) + updated by ~13 producers (Telegram + cockpit/S7
  owner-control routes). The dream **can** fire.
- Current live meaning is **"no Maez-directed interaction for 30 min," NOT "Rohit is
  physically away."** Producers track explicit Maez interactions, not general desk presence.
- The camera/presence backstop is **unavailable while `llama-server-vision` is inactive** —
  so activity is currently the **sole** signal (no fresh-present block).
- Therefore a dream witness with vision down is valid **only if (a) you are genuinely away,
  or (b) you explicitly accept activity-only gating.** A dream firing while you are silently
  working is a **known limitation, not a surprise regression** (Maez can tell you stopped
  talking to it; it cannot currently tell you left the room).
- **Not a code slice.** Right next action when witnessing: **restore `llama-server-vision`
  before the witness, OR run the witness during real AFK.**

### CORRECTION (2026-06-02): camera presence ≠ the old vision LLM

Claude's first scoping note wrongly said "restore llama-server-vision." That was a
misdiagnosis. The dream's presence backstop is **MediaPipe `blaze_face.tflite`** (CPU,
content-free, timeboxed per ADR 0029), enabled via `MAEZ_CAMERA_PRESENCE_MODE=observe`
+ `MAEZ_CAMERA_PRESENCE_ENABLED_UNTIL=<ISO ts with tz>` — it was OFF, not broken
(owner probe: presence_detected, ~0.95 confidence). The retired `llama-server-vision`
(screen/multimodal LLM) is a DIFFERENT, retired system (port 8081 = 4B judge now). Do
NOT revive it. To make the dream backstop work: enable camera-presence observe mode
(needs a restart — which ALSO activates the staged reflection flags; do it intentionally).
