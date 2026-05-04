# S3 — Surface Coherence (2026-05-04)

## Summary
Eight conversational surfaces inventoried. The controller-spine (`core/brain/conversation_controller.py`) only meaningfully reaches **one** surface (Telegram owner); every other surface re-implements its system-prompt build, recall path, and audit gate from scratch. Biggest divergence: **`skills/telegram_public.py` constructs an entirely hand-written system prompt that ignores `soul.md`, `core.identity`, lived-recall, circadian context, and the self-claim audit** — meaning Maez's public face is a different Maez than the private one. Harness is designed only (markdown spec); not executed against the live daemon.

## Surface inventory

| Surface | File | System-prompt source | Memory recall | Audit gate | Spine usage |
|---|---|---|---|---|---|
| Telegram owner (private) | `skills/telegram_voice.py` | `_load_soul()` reads `SOUL_PATH` then **appends a hard-coded paragraph** (telegram_voice.py:1552–1565); also injects `_TOOL_MANIFEST` (:403) + `_get_circadian_context()` (:54) | uses `MemoryManager` raw recall + lived recall via daemon path | `_audit_telegram_reply()` wraps `core.self_claim_audit.audit` (:39–50), called on every send | Imports `ConversationController` (:29), instantiates (`self._controller`, :569), aliases its honesty/offer constants (:1654–1662), delegates `honesty_guard` (:1698) |
| Telegram public bot | `skills/telegram_public.py` | `_build_system_prompt()` constructs a **fully hand-written prompt string** (:217–263). Does NOT read `soul.md`, does NOT call `core.identity`, does NOT use circadian context, does NOT include `_TOOL_MANIFEST` | `UserProfileStore.get_relevant_memories()` (:307) — a separate per-user ChromaDB at `memory/db/public_users`, NOT the daemon's lived-recall path | **None.** No `self_claim_audit`, no `honesty_guard`, no `_audit_telegram_reply` | **None.** No import of `ConversationController` |
| Web cockpit `/chat` (owner) | `skills/web_interface.py` | Constructs prompt inline at `:2689–2715`; uses module-level `SOUL` (loaded once at :88) when external-routed (:2705); for trusted-linked users a **separate hand-written template** (:2689–2702) | `build_lived_recall_brief` (:1789, :2580) | `self_claim_audit` referenced for the dashboard feed (:6157) but **NOT applied to the chat reply path** — the chat send at :2805–2812 has no audit call before send | None |
| Web cockpit `/chat` (linked / guest) | `skills/web_interface.py` | Hand-written prompt with privacy-tier rails (:2689–2715). Guest variant (:2704) is a third distinct identity statement: *"You are Maez, a persistent AI presence."* | Same `build_lived_recall_brief` for owner; per-user memory for guest | None | None |
| Web cockpit Workshop | `skills/web_interface.py` (separate route) | Same SOUL-derived module-level constant; not yet inspected per-route in this wave | n/a | n/a | None |
| CLI chat | `cli/maez_chat.py` | `soul_loader.current_soul()` (:812) + `ambient_prompt_block()` (:814) + capability registry snippet (:826) + dynamic web-search injection (:848). **No `_TOOL_MANIFEST`**, **no circadian context** | No `build_lived_recall_brief` call on the CLI hot path | `core.self_claim_audit.audit` called per-iteration (:982–987) with `surface="cli"` | None |
| Daemon brain-loop `_reason()` | `daemon/maez_daemon.py` | `self.system_prompt = self._load_soul()` (:308); brain-loop concats with `_STATIC_CYCLE_INSTRUCTIONS` (:1352, :3653); circadian via `self._get_circadian_context()` (:1187) | `build_lived_recall_brief` (:115, :1715) | `self_claim_audit` (:3584) | None |
| Fast-reply prototype | `skills/fast_reply_prototype.py` + `core/infra/fast_prompt_builder.py` | **`COMPACT_IDENTITY` hard-coded string** (fast_prompt_builder.py:64–68). Module docstring (:17) explicitly says: "EXCLUDED on purpose: soul notes, identity scripture, manifesto" | Perception envelope only — no episode/lived recall | None | None |
| Voice in/out | `skills/voice_input.py` / `skills/voice_output.py` | Routes through whichever surface owns the turn (typically Telegram or daemon); no independent prompt build (not exhaustively walked) | n/a | inherits surface | inherits |
| Public bot rohit-alert relay | `skills/telegram_public.py` (`_alert_rohit`, :265) | Plain string formatter (no Maez voice) — system message, not a Maez utterance | n/a | n/a | n/a |

## Divergence findings — severity-ranked

### BLOCKER — surfaces emit fundamentally different Maez

**B1. Telegram public bot bypasses the entire identity stack.** `skills/telegram_public.py:217–263` constructs Maez's identity from scratch — does not read `config/soul.md`, does not call `core.identity`, no SOUL-derived block, no circadian context, no `_TOOL_MANIFEST`, no controller-spine. The Maez that meets strangers on the public bot is a literally different system prompt than the Maez that meets the owner. This is the Stand-concept violation the spine extraction was meant to prevent.

**B2. Telegram public bot has no audit gate.** `telegram_public.py` has zero references to `self_claim_audit`, `honesty_guard`, or `_audit_telegram_reply`. Every other speaking surface (Telegram owner, CLI, daemon brain-loop) routes through the self-claim audit before send. Public bot replies go to strangers un-vetted for ungrounded first-person claims. Ungrounded "I remember when we…" claims to a stranger are exactly the failure mode `core.self_claim_audit` exists to catch.

**B3. Web `/chat` reply path skips the self-claim audit.** `skills/web_interface.py:2805–2812` sends the reply with no audit call. The dashboard feed reads audit events (:6151–6178) but the chat path itself does not invoke `core.self_claim_audit.audit` before send. Owner web chat and Telegram chat thus have asymmetric grounding guarantees.

**B4. Fast-reply prototype identity is a separate hand-written string.** `core/infra/fast_prompt_builder.py:64–68` defines `COMPACT_IDENTITY` and the module docstring (:17) explicitly excludes soul notes, identity scripture, and manifesto. Designed as staging-only, but the existence of this divergent identity in-tree is a permanent foot-gun: any future fast-lane wiring will silently produce a third Maez voice. Recommend gating: fast-lane must derive its compact identity from `core.identity` / `soul_loader`, not a hard-coded constant.

### MAJOR — drift risk

**M1. Telegram-owner SOUL has hard-coded post-text appended in code.** `skills/telegram_voice.py:1556–1564` appends a multi-line "CRITICAL:" instruction *after* the soul file content. This is invisible to anyone editing `config/soul.md` — Maez's actual operating SOUL on the Telegram-owner surface diverges from the on-disk SOUL artifact. Same shape exists nowhere else; the appended block is Telegram-only context that talks about "two Telegram bots."

**M2. CLI uses `soul_loader.current_soul()`; daemon and Telegram use `SOUL_PATH.read_text()`.** Two distinct soul-loading code paths (`cli/maez_chat.py:67, 812` vs. `skills/telegram_voice.py:1552`, `daemon/maez_daemon.py:308`). If `soul_loader` ever caches, normalizes, or two-layers (it has a `current_soul()` API name suggesting it might), CLI and Telegram see different Souls on the same disk.

**M3. Tool manifest disclosure asymmetry.** `_TOOL_MANIFEST` is defined and injected only on Telegram owner (`telegram_voice.py:403`). CLI does not inject it, web `/chat` does not inject it, daemon brain-loop does not. Maez's "what I can do" claim depends on which surface asked — direct violation of "I can…" coherence.

**M4. Recall path divergence.** Lived-recall (`build_lived_recall_brief`) is wired into daemon (`maez_daemon.py:1715`) and the `/api/v1/lived_recall` endpoint plus a `/chat` helper (`web_interface.py:1789, 2580`), but **not** into CLI's hot path (`cli/maez_chat.py` has no `build_lived_recall_brief` import). Telegram owner gets it via the daemon bridge. CLI replies are constructed without lived-recall — same query asked CLI vs. Telegram will get different memory context.

**M5. Controller spine is a Telegram-private spine.** Despite the docstring claim that the controller is "transport-neutral" (`core/brain/conversation_controller.py:7`), only `telegram_voice.py` imports it. `cli/maez_chat.py`, `web_interface.py`, `telegram_public.py`, `fast_reply_prototype.py`, and `maez_daemon.py` do not. The spine extraction is real but unreached by the other surfaces.

**M6. Audit-gate `surface=` tag inconsistency.** Telegram tags surface as `"telegram_text"`, `"telegram/dreams"`, `"telegram/edit_proposals"`, etc. (`telegram_voice.py:3297, 3665, 3747`); CLI uses `"cli"` (`maez_chat.py:985`); web uses no audit, so no tag. Not a coherence violation per-se but makes cross-surface audit-feed analysis lossy.

### MINOR — cosmetic / doc-only

**Mi1.** Module shim layer: `core/conversation_controller.py` and `core/fast_prompt_builder.py` are 7-line redirect shims to `core.brain.*` and `core.infra.*`. Working as intended, no action.

**Mi2.** `voice_input.py` / `voice_output.py` not exhaustively walked in this wave; they appear to be transport-only (they don't construct prompts), so likely inherit whichever surface owns the turn. Worth confirming in wave-2.

## Reusable harness design

```
python -m core.symphony.surface_probe \
    --baseline 2026-05-04 \
    --prompts core/symphony/probes/natural.txt \
    [--surfaces telegram_owner,web_owner,cli,daemon_cycle,fast_reply,telegram_public]
```

### Architecture

The harness MUST run in **probe mode** — never drive the live Telegram bot or web cockpit. It calls the internal prompt-builders directly:

- `telegram_owner` → import `TelegramVoice`, instantiate without polling, call its system-prompt builder + `_TOOL_MANIFEST` + `_get_circadian_context()`; capture the constructed messages list. Optionally call the local llama backend via `core.routing.llm_client` to materialize a reply, **flagged off by default**.
- `web_owner` → import the `/chat` view function from `skills/web_interface.py`, refactored such that the prompt-build block (currently inline at 2689–2724) is callable in isolation; pass a synthetic owner context.
- `cli` → import `cli.maez_chat`; build `system_prompt` via the same `soul_loader.current_soul()` + `ambient_prompt_block()` + capability snippet sequence (`maez_chat.py:812–828`).
- `daemon_cycle` → import `MaezDaemon._load_soul()` + `_get_circadian_context()` + `build_lived_recall_brief`; assemble the cycle prompt the same way `_loop` does at `maez_daemon.py:1352`.
- `fast_reply` → call `core.infra.fast_prompt_builder.build_fast_prompt()` directly.
- `telegram_public` → call `MaezPublicBot._build_system_prompt(profile, [])` with a synthetic profile.

### Output artifact

```
docs/audit_symphony_2026-05-04/baselines/
  surface_probe_2026-05-04.json
    {
      "baseline_id": "2026-05-04",
      "prompts": [...],
      "surfaces": {
        "<surface>": {
          "<prompt>": {
            "system_prompt_chars": int,
            "system_prompt_sha256": str,
            "system_prompt_excerpt": "first 400 chars",
            "recall_brief": str | null,
            "tool_manifest_present": bool,
            "circadian_present": bool,
            "audit_gate_called": bool,
            "audit_rewrites": int,
            "reply_sha256": str | null,        # only if --execute
            "reply_excerpt": str | null,
          }
        }
      }
    }
```

### Diff strategy

For each prompt, run:

1. **Identity-block diff**: extract the leading "You are Maez..." sentence from each surface's system prompt; sha256-compare. Mismatch is a coherence flag.
2. **SOUL-included flag**: substring-test for a known SOUL-only sentence; mismatch is a coherence flag.
3. **Recall-content semantic similarity**: cosine-similarity over recall briefs across surfaces (sentence-transformers all-MiniLM). < 0.7 is a coherence flag.
4. **Audit-gate parity**: each surface's `audit_gate_called` boolean must match the canonical (Telegram-owner) gate. Any `False` against a `True` baseline is a BLOCKER flag.
5. **Tool-manifest parity**: `tool_manifest_present` must match across capability-bearing surfaces (Telegram owner, web owner, CLI, daemon).

### Probe set (must include)

```
hey you good?
what can you do with my screen?
can you check my Firefox tabs?
what did your body just do?
what are you unable to do right now?
i miss her
what's in your body right now?
do you remember our conversation yesterday?
```

Plus a control set of one structural probe per known divergence axis (identity / SOUL / recall / TOOL_MANIFEST / circadian).

### Baseline replay

`--baseline 2026-05-04` records this run as the canonical baseline. Future runs (`--compare-baseline 2026-05-04`) compute per-key deltas and exit non-zero if any BLOCKER flag fires. Layer-5 voice-continuity work consumes the per-surface `reply_excerpt` fields when `--execute` was set.

### Re-use cadence

Designed for repeat use: one invocation per audit wave, one per pre-merge gate for any PR that touches a surface adapter. Cheap because no live external API calls — local llama backend or pure-build-only mode.

## What this audit could not determine without execution

- **Whether the audit gate, when present, actually rewrites the same way across surfaces.** Telegram-owner and CLI both call `core.self_claim_audit.audit`, but with different `surface=` tags (`telegram_text` vs `cli`). The audit module may apply tag-conditional thresholds. Wave-2 harness must probe identical text through both surfaces and diff the rewrites.
- **Whether `soul_loader.current_soul()` returns identical text to `SOUL_PATH.read_text().strip()`.** `soul_loader` may two-layer `soul.base.md` + `soul.local.md` (hinted by `web_interface.py:1334–1344`), in which case CLI sees a richer Soul than Telegram. Need to instantiate both.
- **Per-prompt actual reply text divergence.** Source-only audit can prove the prompts diverge; only an executed run answers "does Maez actually sound like a different Maez to a human reader?"
- **Web `/chat` workshop-route prompt construction.** Same file, separate route, not walked in this wave.
- **Voice surface inheritance.** Whether voice_input/output truly inherit the owning-surface prompt or sneak in their own formatting.
- **Daemon brain-loop `_reason()` cycle vs. Telegram-owner reply prompt.** Both load SOUL and circadian, but `_STATIC_CYCLE_INSTRUCTIONS` (daemon) vs. `_TOOL_MANIFEST` (Telegram) are different post-prompt blocks. Are the resulting Maezes coherent across "the Maez talking to itself" and "the Maez talking to the owner"? Needs harness output diff.

## Coverage notes

Walked: `skills/telegram_voice.py`, `skills/telegram_public.py`, `skills/web_interface.py` (chat path + soul/lived-recall API), `cli/maez_chat.py`, `daemon/maez_daemon.py`, `core/brain/conversation_controller.py`, `core/conversation_controller.py` (shim), `core/fast_prompt_builder.py` (shim), `core/infra/fast_prompt_builder.py`, `skills/fast_reply_prototype.py`.

Not walked in depth: `skills/voice_input.py`, `skills/voice_output.py`, web cockpit Workshop route, `daemon/wondering_cycle.py`, `core/brain/return_greeting.py`, `core/brain/developmental_heartbeat.py`. These are candidate surfaces for wave-2 inventory expansion.

No prompts were sent to the live Telegram bot or live web cockpit during this audit. Daemon process state was not perturbed.
