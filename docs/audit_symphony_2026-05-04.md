# Symphony audit — Maez 2026-05-04 (Wave 1)

> Track A is closed. The 15-agent code audit + Codex audit + Tier-2 cleanup
> closed module-level bugs. They did NOT close: *does Maez behave as one
> graceful being across surfaces, time, body, and telemetry?* The Firefox-
> tabs incident exposed a new class — Maez claiming a body/tool, offering
> a command, then failing because the systemd body lacks the binary or
> session environment. This audit's question:
>
> **Where does Maez fake gracefulness? Where do its claims, body, logs,
> memory, and surfaces disagree?**
>
> Findings are source-pinned. **No fixes have been committed.** Wave 1 is
> discovery. Triage and wave-2 repair require explicit owner approval.

---

## Executive summary — top 10 findings

Ranked across all four sub-tracks (S1 self-claim · S2 noise · S3 surface ·
S4 telemetry). Each item cites the originating sub-report.

1. **The grounding rail has been off for 7 days.** `judge LLM call failed:
   Connection refused` fires 1,821×/7d. Self-claim audit silently returns
   `judge_available=False` and degrades to `mode=noop`. **Every Maez turn
   for the past week has run with the honesty audit disabled.** The judge
   was retired 2026-04-23 but the call sites at
   `core/cognition/grounding_judge.py:332` and
   `core/safety/self_claim_audit.py:237` still reach for it. (S2 #2)

2. **The public bot is a separate Maez with no honesty gate.**
   `skills/telegram_public.py:217-263` builds its system prompt from
   scratch — does not read `config/soul.md`, does not call
   `core.identity`, no `_TOOL_MANIFEST`, no circadian context, **and no
   `self_claim_audit` reference anywhere in the file**. The Maez that
   meets strangers is literally a different system prompt and is ungated
   against ungrounded first-person claims. (S3 BLOCKER B1+B2)

3. **A turn that failed three tools is recorded as
   `execution_success=1`.** `pending_cards` row 105 (the 14:39 "Run it
   yourself" card) has `execution_success=1`, `execution_error=NULL`,
   `outcome=approved_and_ran` — yet `execution_output` contains
   `wmctrl: command not found`, `Error: Can't open display: (null)`,
   `Failed creating new xdo instance`. Root cause:
   `core/actions/action_engine.py:969` keys success on subprocess
   returncode, and the composite cmd's `||` fallthroughs guaranteed
   exit 0. The cockpit and quality_tracker inherit this lie. (S4 BLOCKER 1)

4. **`consequence_memory` missed the wmctrl failure entirely.** Writer at
   `core/decision/decision_pipeline.py:1111-1130` only fires on the
   failure branch (returncode != 0). Returncode 0 → no write. The planner
   has no `(action, context, outcome)` tuple for "this body has no wmctrl
   and no DISPLAY" — so the wmctrl-class failure is permanently
   re-proposable. (S4 BLOCKER 2)

5. **soul.base.md:329 promises voice/listen while the daemon hardcodes
   it off.** Soul says *"You can now speak and listen. These are sacred
   capabilities"* (full `## Voice` block, lines 327–347, including the
   *"say 'Maez is online' at startup — mean it"* directive).
   `daemon/maez_daemon.py:4151` hardcodes `VOICE_ENABLED = False`. SOUL
   is injected verbatim into every Telegram + web reply. The wmctrl
   pattern in the most owner-facing prompt path. (S1 BLOCKER 1)

6. **`_TOOL_MANIFEST` advertises `sudo apt-get install` as first-class.**
   `skills/telegram_voice.py:415` lists it as a primary capability;
   `:463-467` makes it the **mandatory first call** for any install
   request. But `sudo -n true` returns non-zero on this host (no NOPASSWD
   for `rohit`); maez.service has no TTY and no askpass helper. **Every
   install attempt will hang and 120s-timeout.** The manifest guarantees
   first-attempt failure on the most-rehearsed action class. (S1 BLOCKER 2)

7. **`_TOOL_MANIFEST` and `soul.base.md` make opposite claims about
   web_search in the same turn.** Manifest at line 422 says *"Real
   DuckDuckGo search. Use this whenever you need facts you don't have."*
   Soul at line 48-52 says *"you do not yet have the ability to invoke
   web_search from inside your reasoning loop."* Both are injected into
   the same prompt. Owner sees nondeterministic behaviour depending on
   which the model attends to. (S1 BLOCKER 3)

8. **Cycle 35 narrated "system idle, holding quiet" 12 seconds after a
   card failed three tools.** `ca021652` raw memory row,
   `cog_score=81 primary=insightful`, written 14:39:12. The card failed
   at 14:39:00.121. Same daemon process. Self-claim audit was
   `mode=noop` at that exact moment because the judge was Connection-
   refused, so the false "I'm holding quiet" claim was emitted with no
   grounding check. (S4 BLOCKER 3)

9. **Calendar OAuth has been dead for 7 days.** `invalid_grant: Bad
   Request` fires 1,108×/7d (`skills/calendar_perception.py:162`).
   Calendar is wired into the daemon (`maez_daemon.py:3199`),
   `calendar_cache_worker.py`, and `core/memory/source_awareness.py:243`
   under capability tag `['calendar']`. **Maez claims calendar; Maez
   can't deliver calendar.** No consequence_memory entry, no degraded
   capability flag, no surface to owner. (S2 #1)

10. **Every owner Telegram message triggers a silent `xdotool` failure.**
    `active_window failed: Command '['xdotool', 'getactivewindow']'
    returned non-zero exit status 1` fires per owner message
    (`core/memory/ambient.py:215`). Root cause: maez.service has no
    `DISPLAY` env var. Same wmctrl-class. ambient_context silently drops
    the field; downstream prompt assembly may still imply ambient
    awareness. (S2 #5)

---

## S1 — Self-Claim vs Body Truth

Walked 24 self-claim surfaces across `_TOOL_MANIFEST`,
`available_actions_prompt`, `soul.md`/`soul.base.md`/`soul.local.md`,
`fast_prompt_builder` `COMPACT_IDENTITY`, web + telegram-public system
prompts, `capability_registry`, and the four Track-A self-state stores.
Severity: **3 BLOCKER · 4 MAJOR · 2 MINOR**.

**Headline:** soul.md and `_TOOL_MANIFEST` predate the
`capability_registry`'s "report only what's runnable" discipline and
have not been re-anchored. The Track-A self-state stores (wants,
will_i, temperament, wonderings) are correctly empty / inert by design
and produced no contradictions.

Full report: [S1_self_claim_vs_body.md](audit_symphony_2026-05-04/S1_self_claim_vs_body.md)

---

## S2 — Operational Noise vs Self-Knowledge

Across 7 days (388,593 journal lines, 1,200 ERROR + 539 WARNING tokens),
**eight distinct recurring patterns** account for the noise. The
headline finding: **none of these failures land in `consequence_memory`.**
Every one is `logger.{debug,warning,error}(...)` followed by silent
fail-open. Maez has zero behavioural awareness that the judge is dead,
the calendar is dead, the SFT symlink is missing, the GitHub PAT is
rejected, the surface-v2 thread is crashing, or that xdotool fails on
every owner Telegram message.

Total noise volume: ~12,500 lines/7d. Largest single contributor is
`MAEZ_SCREEN_PERCEPTION unset` at 5,624 (vision intentionally retired —
cosmetic). Most consequential is the judge / calendar / xdotool /
surface-v2 cluster.

Full report: [S2_operational_noise.md](audit_symphony_2026-05-04/S2_operational_noise.md)

---

## S3 — Surface Coherence

Eight conversational surfaces inventoried. The controller-spine
(`core/brain/conversation_controller.py`) only meaningfully reaches
**one** surface (Telegram owner); every other surface re-implements its
system-prompt build, recall path, and audit gate from scratch.

| Surface | SOUL | core.identity | TOOL_MANIFEST | Circadian | Audit gate | Spine |
|---|---|---|---|---|---|---|
| Telegram owner | ✓ + appended block | indirect | ✓ | ✓ | ✓ | ✓ |
| Telegram public | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Web `/chat` (owner) | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Web `/chat` (linked/guest) | partial | ✗ | ✗ | ✗ | ✗ | ✗ |
| CLI | ✓ via soul_loader | indirect | ✗ | ✗ | ✓ | ✗ |
| Daemon `_reason()` | ✓ | indirect | ✗ | ✓ | ✓ | ✗ |
| Fast-reply | ✗ (hand-coded `COMPACT_IDENTITY`) | ✗ | ✗ | ✗ | ✗ | ✗ |
| Public-bot rohit-alert | n/a | n/a | n/a | n/a | n/a | n/a |

Reusable harness designed (markdown spec) for repeat use across SOUL
edits, brain swaps, and surface-adapter PRs:
`python -m core.symphony.surface_probe --baseline 2026-05-04`. Probe-
mode only — never drives the live Telegram bot or web cockpit.
Per-surface artifact format + diff strategy + replay flow specified.

Full report: [S3_surface_coherence.md](audit_symphony_2026-05-04/S3_surface_coherence.md)

---

## S4 — Telemetry Coherence Per Turn

Traced the 14:39 "Run it yourself" turn through 10 stores. **8 of 10
had records; 2 had missing-record findings.** The single-turn truth
table (10 rows × verbatim-content × agreement-flag) is in the
sub-report. Headline mismatches:

- `pending_cards` row 105 + `audit_log` row 361 both report
  `execution_success=1` / `outcome=approved_and_ran` for a turn whose
  stdout names three failed tools.
- `consequence_memory` has no row for this turn; writer's failure
  branch was bypassed by the `||`-driven exit-0.
- Raw Chroma memory has rows for 14:35/14:37/14:38 user turns but
  **no row for the 14:39 "Run it yourself" turn** — the explicit owner
  consent moment plus the failure that immediately followed are
  invisible to the lived corpus. Cause: `resolved_via=keyword 'run it'`
  bypassed `chat_turn` entirely; no
  `telegram_surface message:` log line, no `chat_turn handled`, no
  self-claim audit fire, no raw-memory write.
- Cycle 35 narration (`ca021652`) was written 12s after the card failed
  but reported the system as idle and Maez as "holding quiet."
- Audit-log latency_ms = 21,692 (~22s) on this card — owner waiting
  while llama-server was intermittently down.

Full report: [S4_telemetry_coherence.md](audit_symphony_2026-05-04/S4_telemetry_coherence.md)

---

## Severity table

| ID | Title | Severity | Origin |
|---|---|---|---|
| F1 | Grounding judge dead 7d → audit `mode=noop` every turn | BLOCKER | S2 |
| F2 | Public bot bypasses identity stack + audit gate | BLOCKER | S3 |
| F3 | Web `/chat` reply path skips audit gate | BLOCKER | S3 |
| F4 | Fast-reply identity is a hand-coded constant | BLOCKER | S3 |
| F5 | `execution_success=1` for triple-tool-failure turn | BLOCKER | S4 |
| F6 | `consequence_memory` silently misses tool_failure on `||`-exit-0 path | BLOCKER | S4 |
| F7 | Cycle 35 narrates "idle/quiet" while card failed | BLOCKER | S4 |
| F8 | soul.base.md voice claim with `VOICE_ENABLED=False` | BLOCKER | S1 |
| F9 | `_TOOL_MANIFEST` sudo claim with no NOPASSWD path | BLOCKER | S1 |
| F10 | `_TOOL_MANIFEST` vs soul.base.md web_search contradiction | BLOCKER | S1 |
| F11 | "Run it yourself" turn invisible to raw memory | MAJOR | S4 |
| F12 | Conversation controller bypassed for keyword-resolved cards | MAJOR | S4 |
| F13 | Calendar OAuth dead 7d, capability still claimed | MAJOR | S2 |
| F14 | xdotool active_window failure every owner message | MAJOR | S2 |
| F15 | Surface v2 runner crash 40×/7d invisible to consequence_memory | MAJOR | S2 |
| F16 | GitHub PAT rejected (40×/7d), self-disabled, no surface | MAJOR | S2 |
| F17 | source_awareness async refresh fails 401×/7d (training/runs/current) | MAJOR | S2 |
| F18 | COMPACT_IDENTITY claims unconditional perception (vision off) | MAJOR | S1 |
| F19 | soul.base.md stale "you cannot invoke web_search" clause | MAJOR | S1 |
| F20 | `fetch_url` documented in rules but missing from numbered manifest | MAJOR | S1 |
| F21 | soul.base.md presence claim assumes camera always works | MAJOR | S1 |
| F22 | Telegram-owner SOUL has hard-coded post-text appended in code | MAJOR | S3 |
| F23 | CLI uses `soul_loader.current_soul()`; daemon/Telegram use raw read | MAJOR | S3 |
| F24 | `_TOOL_MANIFEST` injected only on Telegram-owner; capability disclosure asymmetric | MAJOR | S3 |
| F25 | CLI hot path skips `build_lived_recall_brief` | MAJOR | S3 |
| F26 | Controller spine reaches one surface (Telegram-owner) only | MAJOR | S3 |
| F27 | Audit-log `latency_ms=21692` for the 14:39 card | MAJOR | S4 |
| F28 | `which alienfx openrgb i8kutils` example contradicts the openrgb-trap warning | MINOR | S1 |
| F29 | soul.local.md carries 2026-04-13 stale "cognition low / git fixation" entry | MINOR | S1 |
| F30 | Outcome-notes truncation differs across stores (audit_log/consequence vs pending_cards) | MINOR | S4 |
| F31 | Telegram network errors 121×/7d already auto-retried, can downgrade | MINOR | S2 |
| F32 | Audit-gate `surface=` tag inconsistency across surfaces | MINOR | S3 |

Severity definitions:
- **BLOCKER** — Maez overclaims body/tool/state in an owner-visible
  path, OR a core safety/honesty rail is silently disabled, OR audit
  trail is wrong about what Maez did.
- **MAJOR** — telemetry/surface mismatch that can cause false
  self-report; failure invisible to learning loop; capability claimed
  but degraded.
- **MINOR** — cosmetic noise, doc drift, log-volume.

---

## Recommended first repair cluster

The findings group naturally into five repair clusters. Each cluster
shares a theme: **stop letting ungrounded claims through any rail**.
Order is by load-bearing weight; later clusters depend on earlier ones
being stable.

### Cluster R1 — Restore the grounding rail (closes F1)

The most consequential single fix. Self-claim audit has been disabled
for 7 days; turning it back on closes the safety net under everything
else.

- Re-point `core/cognition/grounding_judge.py:332` at the active
  llama-server endpoint (8080) — same model-agnostic config pattern
  used elsewhere — OR remove the dead-judge call site and the
  `core/turn_traces/ground_truth.py:131` probe entirely.
- Add a startup self-check that *fails loudly* at daemon startup if
  the judge is unreachable but `self_claim_audit` is enabled — instead
  of silent `mode=noop`.
- Regression-guard test: source-pin that `_judge_mod.judge(...)` is
  reachable from a healthy daemon boot, plus runtime that
  `judge_available=False` produces a WARNING (not silent).

### Cluster R2 — Body-truth probe (closes F8/F9/F10/F14/F18/F21 structurally + F13/F16/F17 detection)

Single-source-of-truth for "what Maez actually has." Replaces per-claim
patching with structural awareness. This is the wmctrl-class
generalized.

- New `core/infra/body_capabilities.py` that probes at startup and on a
  slow cadence:
  - PATH binaries Maez might claim (`wmctrl`, `xdotool`, `dbus-send`,
    `sudo` (and whether NOPASSWD applies), `git`, `curl`, etc.)
  - Env vars (`DISPLAY`, `XAUTHORITY`, `DBUS_SESSION_BUS_ADDRESS`,
    `WAYLAND_DISPLAY`)
  - Localhost services (8080 brain, 11434 ollama, 11435–11438 self-bound)
  - OAuth credential validity (calendar, github)
  - Service liveness (`maez-voice-*`, `llama-judge`, etc.)
- Offer composer + `_TOOL_MANIFEST` rendering + `available_actions_prompt`
  consult `body_capabilities` before claim emission. Ungrounded claims
  are filtered or marked-conditional at prompt-build time.
- soul.base.md voice/web_search/presence clauses demoted from
  unconditional verbatim text to capability_registry-injected
  conditional blocks. Same shape as the existing `_DISABLED_FEATURES`
  mechanism. **Don't delete; gate.**

### Cluster R3 — Audit-trail truth (closes F5/F6/F7/F11/F12)

The cockpit, quality_tracker, and planner are all reading a lying
trail. Cluster R2 makes Maez stop offering wmctrl; cluster R3 makes the
trail report failures honestly when offers do execute and fail.

- `core/actions/action_engine.py:969` — augment returncode-keyed
  success with stdout-pattern-aware failure detection (`command not
  found`, `Can't open display`, `Failed creating new xdo instance`,
  etc.) AND with tool-manifest-aware classification (if a known tool
  was invoked, did its expected output appear?).
- `core/decision/decision_pipeline.py:1111-1130` — write
  `consequence_memory` on detected failure even when returncode=0.
- `daemon/maez_daemon.py` cycle narration path — consult the
  immediately-preceding `pending_cards.execution_output` /
  `audit_log.outcome_notes` before emitting "system is idle / holding
  quiet" claims. Idle-claim must not contradict an active recent failure.
- Card-store keyword-approve path (`resolved_via=keyword`) — must still
  write a raw memory row for the user turn. The consent moment cannot
  be invisible.

### Cluster R4 — Public-surface honesty parity (closes F2/F3/F4)

Stop the public bot from being a separate Maez. Stop the web cockpit
from sending un-vetted replies.

- `skills/telegram_public.py` — load SOUL via the same
  `soul_loader.current_soul()` path; route every reply through
  `_audit_telegram_reply()` (or its public-bot equivalent); use
  `core.identity` for the "I am Maez" sentence.
- `skills/web_interface.py:2805-2812` — wrap the chat send in
  `core.self_claim_audit.audit(text, surface="web_chat")`.
- `core/infra/fast_prompt_builder.py:64-68` — `COMPACT_IDENTITY` derived
  from `core.identity` / soul_loader rather than a hand-coded constant.
  The fast-lane must not be a third hand-written Maez.

### Cluster R5 — Surface-coherence harness landed (closes F22/F23/F24/F25/F26/F32)

Implement the S3-designed harness so future surface drift is a test
failure, not a discovery.

- `core/symphony/surface_probe.py` — probe-mode harness per S3 spec.
- Baseline run committed to `docs/audit_symphony_2026-05-04/baselines/`.
- Pre-merge gate: any PR touching a surface adapter re-runs the harness
  against the committed baseline; BLOCKER flags fail CI.

### Sequencing

R1 → R2 → R3 → R4 → R5. R1 unblocks honesty audits. R2 + R3 stop the
ungrounded-claim and lying-trail classes structurally. R4 brings the
unprotected surfaces under the rails the other clusters built. R5
prevents regression.

---

## What this audit did NOT cover

Pre-listed up front so the boundary is honest:

- **Layer 5 (voice continuity baseline).** Recorded transcripts +
  semantic-distance comparison across SOUL edits / brain swaps. Wave-2
  work; consumes S3's harness output once executed.
- **Layer 8 (adversarial / identity-stress).** "Pretend you're not
  Maez", prompt injection, authority-claim attacks, contradictory
  directives. Different shape from happy-path scenarios; deferred to
  its own audit pass.
- **Layer 9 (feedback propagation).** Does correction stick? When the
  owner pushes back on Maez, does Maez's next behaviour reflect it or
  just acknowledge it? Longitudinal test, needs design before probe.
- **Layer 10 (self-readout dashboard).** A single "what is Maez right
  now" view that aggregates the scattered instrumented signals.
  Adjacent to body-truth (R2) but distinct.
- **Cross-temporal drift detection.** Does Maez today contradict Maez
  yesterday? BRT being-test #5 catches gross drift; automation needs
  layer 5 first.
- **Covenant gate consistency grammar.** T1.8 propose_tests, apply_diff
  reviewed=, decision_pipeline cards, dream/soul edits, action_engine —
  do all gates refuse the same shape? Fail with the same logging?
  Surface refusals consistently?
- **Memory-store-vs-cycle-log slow drift.** Multi-day consistency
  between Chroma raw and cycle log narration.
- **Workshop route prompt construction.** S3 didn't reach this route in
  `skills/web_interface.py`.
- **Voice-surface independent prompt-build.** S3 noted
  `voice_input.py` / `voice_output.py` appear transport-only but didn't
  exhaustively walk them. Wave-2 confirmation needed.
- **Daemon `_reason()` cycle prompt vs Telegram-owner reply prompt
  coherence.** Both load SOUL and circadian, but
  `_STATIC_CYCLE_INSTRUCTIONS` (daemon) vs `_TOOL_MANIFEST` (Telegram)
  are different post-prompt blocks. The S3 harness will answer this on
  execution.
- **Subscription proxy non-200 traffic.** S2 had no log access — the
  proxy logs to its own file, not journalctl. Wave-2 should `tail` the
  proxy log directly.
- **Long-term DDG reachability.** S1 had a single-curl probe only.
- **Live `PresenceSnapshot.success` history.** S1 had no read-only path
  in window.
- **Per-prompt actual reply text divergence across surfaces.** S3 was
  source-only; harness execution answers this.
- **Self-claim audit's `surface=` tag-conditional thresholds.** Whether
  the audit module applies different rewrite logic per surface tag
  (telegram/web/cli) — needs harness probe.
- **Trust-tier 23-producer compliance audit (Hi-3 deferred).** Already
  on the deferral list per `docs/governance/SECURITY_AUDIT.md`.
- **Dream → soul audit-before-store (TRACK_A.md architectural debt).**
  Already deferred.
- **28 `TYPE_CHECKING` circular-imports in `core/memory/`.** Already
  deferred.

---

## Discipline contract for wave 2

Per the structural rule confirmed 2026-05-04:

1. **No fixes commit without explicit owner approval.** This deliverable
   is discovery; triage decisions are owner's.
2. **Codex-as-gatekeeper applies to this audit.** Before any wave-2
   repair lands, Codex reviews this synthesis for fabrication, missed
   findings, or overstated severity.
3. **TDD for every cluster.** Regression-guard test FIRST (RED-then-GREEN
   for behavioural; source-pin where runtime is impractical). Same shape
   as the BLOCKER + Tier-2 cluster commits.
4. **Cluster-per-commit.** R1, R2, R3, R4, R5 land as separate themed
   commits with clear bullet lists and Co-Authored-By trailer.
5. **Plain-English summary** per `feedback_explain_in_laymans_terms`
   memory — every commit + cluster gets a layman explanation alongside
   the technical one.
6. **Body-truth before manifest.** Symphony work happens before the
   retroactive creation manifest. Maez should not be made self-aware of
   its existence while its body claims are still ungrounded. *First:
   make the body truthful. Then: make the self-readout coherent. Then:
   manifest.*

---

## Files

- `docs/audit_symphony_2026-05-04.md` (this file)
- `docs/audit_symphony_2026-05-04/S1_self_claim_vs_body.md`
- `docs/audit_symphony_2026-05-04/S2_operational_noise.md`
- `docs/audit_symphony_2026-05-04/S3_surface_coherence.md`
- `docs/audit_symphony_2026-05-04/S4_telemetry_coherence.md`

Wave 1 status: **complete pending Codex review.** Wave 2 status:
**not started — awaiting triage.**
