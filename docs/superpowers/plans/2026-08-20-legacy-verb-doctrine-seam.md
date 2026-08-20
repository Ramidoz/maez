# Ledger: legacy-verb inline bypass vs decision-pipeline doctrine

2026-08-20 (Phase 2 gate round 1/2 finding). `run_brain_loop`'s tool
loop routes only `run_shell`/`write_any_file` through the decision
pipeline (`brain_loop.py:2540`); legacy allowed verbs fall through to
direct `_execute_action` (`:2642`, `:2655`), conflicting with
TRACK_A.md:140 doctrine that every chat-path action flows through the
pipeline. Phase 2 does NOT widen or fix this; the conflict is owned
here. Resolution options (route all verbs through pipeline vs amend
doctrine with a named inline-tier) need their own design pass with the
8-step second-order-contradiction trace. Non-guarded classes involved:
routine_custody reads, currency/stock. S7 guarded classes are NOT
affected (independent revalidation at action_engine.py:599/895).
