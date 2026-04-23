# New stack (self-dev + subscription proxy + workshop) — Audit (2026-04-22)

## Summary
The new self-dev review pipeline (with hooks, persistence, scheduling), subscription proxy HTTP routing, and workshop agentic surface have accumulated zero security/correctness blockers in fresh examination. All earlier self-dev review corrections were applied correctly. Strong error handling, path safety, and resource cleanup throughout.

## Findings

(Zero blockers, majors, minors, nits identified.)

## Coverage notes

**self_dev.py** (993 LoC): Review primitive correctly catches timeout via Popen.kill() and waits for process death rather than orphaning (line 225-228). JSON parsing is forgiving with _extract_json_block() that respects string escaping (254-277). Never raises on empty diffs or empty concerns — returns result with overall="(empty diff)" (367-371). Mock-friendly imports (claude_tier, self_dev_persistence) deferred to runtime so tests can patch.

**self_dev_hooks.py** (452 LoC): Post-commit hook yield logic is correct — _PERSISTENCE_UNAVAILABLE sentinel prevents "all modules look never-reviewed" bypass when DB is down (192-212), and policy decision is fail-closed on budget probe (199-204). Diff size accounting correctly initializes keep_block=False so commit headers don't count (135-140, flagged in code comment). Concern notification filters empty tokens from env string (248-250).

**self_dev_persistence.py** (411 LoC): SQLite connection pattern uses context manager (139, 188, 212, etc.), commits after inserts (160, 303), and handles missing review gracefully with None return (264). Concern status state machine is strict — only {open, resolved, wont_fix, rejected} allowed (284-287). Severity filtering by threshold is correct (228-232). Never corrupts on DB error — logs warning and returns empty list.

**self_dev_scheduler.py** (369 LoC): Enumerate candidates correctly filters by size (200–40k, guards against stubs), skip patterns, and yield-on-persistence-error (206-212). Age lookup distinguishes "never reviewed" (None) from "unavailable" (_PERSISTENCE_UNAVAILABLE sentinel). Budget check is fail-closed (269). Always returns 0 — no exit code signalling to systemd (227).

**workshop.py** (816 LoC): Path safety via _resolve_path_safely() is strict — symlink resolution is honored, path-escape detection uses prefix check AND != equality guard (406-408, prevents root-bypass). @mention regex requires at least one / OR extension to avoid email address collisions (96-98). Apply diff correctly extracts target from '+++' header and passes proper -p strip flag to `patch` based on git-prefix detection (508-529, 613). User turn is persisted BEFORE assistant call so failure doesn't leave session corrupted (695-705). Get_turns(tail=N) semantic is honest — fetches newest N then reverses for return, not oldest N (298-305).

**claude_tier.py** (289 LoC): Exception hierarchy is careful — ClaudeTierError subclasses are transient, ClaudeTierBadRequest inherits from ValueError to prevent silent swallowing in except ClaudeTierError (100-106). Timeout handling uses `is not None` identity check to avoid falsy trap (218). Null content is explicitly raised, not silently converted (261-265). Budget() helper is fail-closed (145).

**subscription_proxy/server.py** (~330 LoC): Request parsing validates messages not empty, system parts separate from user parts. Budget gates check both hourly and daily (271, 277), cap is "remaining > cap" not "used >= cap" (271-276). Adapter routing is deterministic — first match wins, Claude is fallback. Trajectory logging is fail-safe (169-170). Adapter call failure is caught and logged (287-301), result shape checked for KeyError/IndexError/TypeError (250-253).

**adapters/base.py** (93 LoC): Abstract interface is minimal — name, call, handles_model, health are required. No unused params.

**adapters/claude_cli.py** (150+ LoC, partial read): Process timeout uses asyncio.wait_for with proper kill() + wait() (118-124). JSON parsing is strict (132-136). is_error flag check is explicit (138-141). Subprocess args are list, no shell injection. Binary search uses shutil.which().

**web_interface.py** routes (/api/v1/workshop, /api/v1/self_dev): All endpoints validate input (request.get_json, body.get with default, strip/truncate). Apply-diff checks session exists before operating (573-576). Model update validates model not empty (571-573). Path parameters are passed directly to workshop module (no manual validation, module does it). Status codes are appropriate (200 success, 400 bad input, 404 not found, 500 errors).

## Sync observations

- claude_tier ↔ proxy: contract is OpenAI format in/out; claude_tier.call() accepts system+user, proxy accepts full messages array. Asymmetry is by design — claude_tier is a thin primitive, workshop/self_dev flatten history for single-turn interface.
- self_dev ↔ persistence: concern status states are validated on both sides (self_dev_persistence._VALID_STATES, web_interface validation).
- workshop ↔ evolution_engine: apply_diff backs up file before patching, backup path is returned. No reversibility contract yet (evolution_engine integration is future phase); current backup-only strategy is safe.
- subscription_proxy adapters: each implements handles_model() and call(); server doesn't assume adapter state. Routing order is static (most-specific first, Claude fallback).

## Polish opportunities (flag only)

- claude_tier.py line 214: `timeout_s or CALL_TIMEOUT_S` → changed to `if timeout_s is not None` per review; pattern is now correct but slightly verbose compared to `timeout_s if timeout_s is not None else CALL_TIMEOUT_S`.
- workshop.py expand_mentions: notes payload mixes string status + dict fields (no validation on caller side), but UI receives it as-is. Asymmetric schema works in practice, not a bug.
- self_dev_hooks.py: policy decision logged with hourly/daily_remaining as Optional[int] — logs gracefully but None is not as clear as "N/A" string. Informational, no functional impact.
- subscription_proxy/server.py budget endpoint: _count_calls filters status='ok' — failed calls don't count against the cap. Intentional and correct (only successful calls should tax quota). Worth documenting in a comment.

## Correctness verification (spot checks)

**Resource leaks:**
- sqlite3 connections: all use `with _connect()/with _db()` context managers that call .commit() and close on exit. ✓
- subprocess.Popen: self_dev.py kills child on timeout and waits (225-229). claude_cli.py uses asyncio.create_subprocess_exec with wait_for timeout guard (118-124). ✓
- HTTP requests: claude_tier uses urllib context manager (220-222, 130-133). FastAPI request handling is implicit. ✓

**Fail-mode matching:**
- review() claims "never raises on empty diff" — returns ReviewResult with overall="(empty diff)" (367-371). ✓
- run_post_commit() claims "always returns 0" — confirmed, all branches return 0 (317, 331, 344). ✓
- apply_diff() claims "rollback on failure" — restores backup if target differs after failed patch (635-640). ✓
- expand_mentions() claims "quiet on failure" — unresolvable mentions stay intact in message, logged in notes (449-450). ✓

**Token handling:**
- claude_tier uses urllib, not requests; no persistent session object. Each call is fresh. ✓
- All token counts are int() casts with fallback to 0 (272-273, 312-313). ✓
- Trajectory log truncates prompt/reply preview to 400 chars (121, 164-165). ✓

## Disallowed
No new features, speculative refactors, or bikeshedding attempted. Every finding cites file:line + code context.
