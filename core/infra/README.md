# core/infra

Cross-cutting utilities. Twelve modules that everything else imports:
paths, owner identity shim, builder-mode perception, and the
fast-reply plumbing.

| Module | Role |
|---|---|
| [`paths.py`](paths.py) | Single source of truth for filesystem layout. `home()`, `config_dir()`, `memory_dir()`, `logs_dir()`, `identity_file()`, `soul_base_path()`, `soul_local_path()`, `soul_combined_path()`. Overridable via `MAEZ_HOME` / `MAEZ_CONFIG` / `MAEZ_DATA` / `MAEZ_CACHE`. |
| [`capability_registry.py`](capability_registry.py) | What Maez can do / has done — introspection for the audit prompt and for `maez doctor`-style diagnostics. |
| [`self_model.py`](self_model.py) | Maez's structured self-description — a dict of its current modules, schedules, and known capabilities. Fed into some prompts so replies don't fabricate architecture. |
| [`public_user_shaping.py`](public_user_shaping.py) | Policy shaper for non-owner surfaces: trim verbose audit metadata, scrub owner-private references, cap response length. |
| [`private_thoughts.py`](private_thoughts.py) | Separate SQLite DB for thoughts marked private. Track A landed as zero-producer/zero-reader; S1 adds an explicit producer API and a bounded derived-signal reader, still unwired from production behavior. |
| [`install_recipes.py`](install_recipes.py) | Recipes for classes of install tasks (apt package install, pip install, systemd-enable) with their expected shape so classifier + audit can reason about them without re-parsing every time. |
| [`builder_mode_capture.py`](builder_mode_capture.py) | Detects when the owner is in focused building work (long editor session, no chat turns) and captures a perception snapshot for context-restore on return. |
| [`builder_mode_perception.py`](builder_mode_perception.py) | Consumes the capture → synthesises a "where were you" summary for the next chat turn. |
| [`fast_prompt_builder.py`](fast_prompt_builder.py) | Builds the prompt for the fast-reply adapter (ambient turn between heavy cycles). Keeps the token budget tight. |
| [`fast_reply_audit.py`](fast_reply_audit.py) | Append-only audit log of fast-reply turns with defence-in-depth key-stripping. |
| [`fast_reply_schema.py`](fast_reply_schema.py) | Pydantic / dataclass shapes for fast-reply requests + responses. |
| [`fast_conversation_log.py`](fast_conversation_log.py) | Append-only per-trust-scope conversation log. Thread-safe SQLite. |

## Invariants

- **Everything resolves through `paths.py`.** If you find a hardcoded
  `/home/rohit/maez` in the codebase, route it through `paths.home()`
  (or `memory_dir` / `config_dir`). Phase 2 cleaned this up. The
  Phase 5 smoke suite would catch a regression.
- **`paths.py` never does I/O at import time.** All helpers are pure
  functions of the env + repo layout. Directory creation happens
  in `ensure_dirs()`, called deliberately by the daemon on boot.
- **`private_thoughts.py` has no production behavior surface.**
  Raw inspection is limited to explicit forensic/operator tools.
  The S1 bounded reader may return only derived signals from rows
  whose context envelope allows `private_reader`; it must not select
  or return raw thought content.
- **`fast_reply_audit` is defence-in-depth.** Callers are supposed to
  strip secrets; this layer rejects records containing any of the
  known-sensitive keys as a backstop.

## Public surface

- `paths.{home, config_dir, data_dir, cache_dir, memory_dir, logs_dir, identity_file, soul_base_path, soul_local_path, soul_combined_path, describe, ensure_dirs}`
- `capability_registry.snapshot() -> dict`
- `self_model.build() -> dict`
- `public_user_shaping.shape_for_public(text, trust_scope) -> str`
- `private_thoughts.record_thought(...)` — explicit/manual raw writer
- `private_thoughts.record_signal(...)` — S1 producer writer with contextual-integrity envelope
- `private_thoughts.derived_signals(...)` — S1 bounded metadata reader; no production behavior wiring yet
- `fast_prompt_builder.build(...) -> PromptPayload`
- `fast_reply_audit.record(entry)` / `.recent(limit)`
- `fast_conversation_log.FastConversationLog(...).append(scope, role, content)`

## Legacy import paths

Every module's pre-Phase-3 path is a shim that resolves here.
