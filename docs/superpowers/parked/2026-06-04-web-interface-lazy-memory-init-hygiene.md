# Parked follow-up: `skills.web_interface` live-MemoryManager import side-effect (lazy-init hygiene debt)

**Date:** 2026-06-04
**Status:** PARKED follow-up — non-blocking. Flagged by Codex during GitHub v1 S2 ingest review; owner-confirmed (Rohit) to name as a follow-up, NOT fold into the v1 slice.
**Severity:** hygiene debt, not a correctness bug.

## The debt

Importing `skills.web_interface` initializes a **live `MemoryManager` as a module-level side-effect**. The egress canaries (`tests/test_owner_account_memory_taint_rail.py`, `tests/test_github_v1_egress_canary.py`) import `build_claude_router_cloud_payload` from `skills.web_interface`, which therefore touches live memory (chromadb / sqlite) **at import time**, even though each test stores its actual fact on an isolated/fake `MemoryManager`.

## Why it matters (and why it's not urgent)

- **Not a correctness bug:** the canary facts are stored on fake/isolated memory; the witnesses are logically sound and the covenant assertions hold.
- **But:** a "hermetic" witness that inits live memory on import is **less hermetic than it looks** — it's slower, can touch live state, and can leak sqlite handles (the ResourceWarnings that prompted the `0a29123` `with closing(...)` cleanup are a symptom). As more hermetic witnesses import `web_interface`, the debt compounds.

## Fix (when done deliberately)

- Make `web_interface`'s `MemoryManager` construction **lazy** — build on first request handling, not at module import — OR
- Extract `build_claude_router_cloud_payload` (and the pure payload-assembly helpers) into a module with **no** live-memory side-effect, so witnesses can import the assembler without booting memory.
- Acceptance: importing the payload-assembly path in a test does not construct a live `MemoryManager`; the existing canaries pass unchanged.

## Provenance

GitHub v1 S2-bounded ingest review (2026-06-04). Codex implemented + flagged; Claude verified the canary logic is sound + the fact isolated; Rohit: "not a blocker for this branch… the kind of debt that can make future hermetic witnesses less hermetic than they look. Name it as a follow-up, not fold it into this slice."
