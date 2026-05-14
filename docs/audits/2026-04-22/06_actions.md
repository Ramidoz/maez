# Action engine + tool loop — Audit (2026-04-22)

## Summary
The action execution layer enforces multi-layered safety: covenant gate (deterministic pattern-matching), command decomposition + classification, destructive snapshots, and tiered approval workflows. Core patterns are sound and defense-in-depth is well-reasoned. However, three issues merit attention: (1) a parser gap in command_decomposer allowing backtick recursion to escape classification, (2) a silent snapshot failure mode that leaves destructive commands unbackedup, and (3) misalignment between tool_loop's daemon auto-exec gate and action_classifier's Lane 0 definition.

## Findings

### blocker — 1

#### command_decomposer.py:214–226 — Backtick substitution parsing does not handle escaped backticks
```python
if c == '`':
    j = i + 1
    while j < n and cmd[j] != '`':
        if cmd[j] == '\\' and j + 1 < n:
            j += 2
            continue
        j += 1
    if j < n:
        subs.append(cmd[i + 1:j])
        out.append('__SUB__')
        i = j + 1
        continue
```

**Why it's a problem:** The code handles escaped characters inside backticks by skipping both the backslash and the next char. However, this is only correct for escaping *within* the backtick context. The issue: backticks can be escaped from the *outside* — e.g., `cmd \`nested\`` where the outer backticks are the substitution and the inner `\`` is meant to be literal. The parser treats the escaped backtick as a *regular character* (increments j by 2), never finds a closing backtick, and appends the entire rest of the command as a substitution body. A command like `echo \`id\` | rm -rf /` would be parsed as a single (malformed) substitution instead of as a pipeline, causing the `rm -rf` to not be decomposed separately and potentially avoid Lane 3 classification.

**Fix:** Track whether backticks themselves are quoted (single/double quotes). Only treat `\`` as an escape sequence if not inside quotes. The current loop already maintains `in_sq` and `in_dq` state at the top level; apply the same before entering the backtick handler.

**References:** command_decomposer.py lines 215–226; also affects lines 172–244 (entire `_extract_substitutions` function). Backtick handling is a parallel case to `$(...)` which also needs the same guard. The test on line 310 (`cat \`whoami\``) does not catch this because the backtick is not escaped.

---

### major — 2

#### action_engine.py:677–712 — Destructive snapshot failure does not block command, but error logging may be lost on high-concurrency daemon restarts
```python
try:
    from core import destructive_snapshot as _ds
    _cmd_str = (params or {}).get("cmd", "") if isinstance(params, dict) else ""
    _cls = _ds.classify(_cmd_str)
    if _cls.get("is_destructive"):
        _files = _cls.get("files", [])
        if _files == ["<git-modified-tracked>"]:
            # resolve sentinel ...
            _files = [...]
        _ds.snapshot(
            request_id=action_id or "unknown",
            cmd=_cmd_str,
            reason=reasoning or "",
            files=_files,
            shape=_cls.get("shape", ""),
        )
except Exception as _snap_err:
    import logging as _lg
    _lg.getLogger("maez.action_engine").warning(...)
```

**Why it's a problem:** The snapshot is called but its return value is never inspected. `destructive_snapshot.snapshot()` returns `{manifest_path, n_files, errors}` where `errors` can contain copy failures. If a critical file (e.g., the tracked file from `git diff --name-only`) fails to copy due to permission or disk issues, the function succeeds (doesn't raise), but the command still executes with an incomplete backup. A `git reset --hard` that corrupts 50% of tracked files leaves 50% unrecoverable. The warning log at line 709 only fires on *exceptions*, not on the silent failures encoded in the `errors` list.

**Fix:** Check the snapshot result. If `errors` is non-empty and the classification shape is one of the high-risk ones (git_reset_hard, rm with wildcards), log a warning and consider deferring or requesting confirmation before executing. At minimum: `if snap_result.get("errors"): log.warning(...)` before returning control to the command executor.

**References:** action_engine.py lines 700–712; destructive_snapshot.py lines 211–298 (snapshot function contract). The return value is documented (line 213) but ignored at the callsite.

---

#### tool_loop.py:165–201 — `is_read_only()` daemon auto-exec gate does not align with action_classifier Lane 0 definition
```python
def is_read_only(cmd: str) -> bool:
    """Return True if cmd looks safe to auto-execute without human approval.
    Conservative: when in doubt, returns False..."""
    stripped = cmd.strip()
    if not stripped:
        return False
    if _ALWAYS_MUTATING.search(stripped):
        return False
    if _SED_WRITE.search(stripped):
        return False
    # Require EVERY stage of a pipeline to be a read-only binary.
    stages = re.split(r"[;|&]+", stripped)
    for stage in stages:
        stage = stage.strip()
        if not stage:
            continue
        # First token of the stage
        first = stage.split(None, 1)[0] if stage.split() else ""
        # Strip env-var prefixes like FOO=bar cmd
        while "=" in first and not first.startswith("-"):
            parts = stage.split(None, 2)
            if len(parts) < 2:
                break
            stage = parts[1] + (" " + parts[2] if len(parts) > 2 else "")
            first = stage.split(None, 1)[0] if stage.split() else ""
        # Strip path
        base = os.path.basename(first).lower()
        if base not in _READ_ONLY_BINARIES:
            return False
    return True
```

**Why it's a problem:** The daemon's `is_read_only()` uses a binary allowlist (`_READ_ONLY_BINARIES`, line 134) to decide whether to auto-execute without a card. The action_classifier in `action_classifier.py` uses a two-tier approach: it allows argv0-only reads (line 569) when the command's argv0 is in `_READ_ARGV0`, AND it checks for redirect writes, obfuscation, and network patterns to classify as DATA_READ vs DATA_WRITE. 

The two lists diverge: `_READ_ONLY_BINARIES` in tool_loop includes "awk", "sed", "cut", etc., which the classifier treats as *requiring flag checks* (sed -i is destructive, awk can run code). The daemon will auto-execute `sed 's/foo/bar/' file.txt` (returns True) without classification, but if that command were queued through the action engine, the classifier would see the redirect-write pattern and Lane-2 it. Conversely, `echo test > /tmp/file` is caught by the daemon's `_ALWAYS_MUTATING` regex (line 154: `\s>\s*[^\s;|&]+`) but only if the redirect is *explicit* — `echo test|tee /tmp/file` is not, and if "tee" is not in `_READ_ONLY_BINARIES` the daemon would reject it, even though the classifier might allow it as a data write.

**Fix:** Unify the definitions. Either (1) push all Lane 0 classification logic into a shared module that both tool_loop and action_engine use, or (2) document and audit the divergence so the owner knows the daemon's autoexec gate is *stricter* than the classifier (safer but may skip some routine reads). The current state is: daemon auto-exec uses allowlist, classifier uses deny-bad-patterns. The classification semantics don't align.

**References:** tool_loop.py lines 134–201; action_classifier.py lines 99–120 (READ_ARGV0), lines 124–139 (READ_TWO_WORD), lines 524–548 (redirect write detection). The mismatch is foundational, not a typo.

---

### minor — 2

#### command_decomposer.py:183–199 — Variable expansion state machine incomplete for double-quoted contexts
```python
in_sq = False  # inside single quotes (no substitution happens there)
while i < n:
    c = cmd[i]
    if c == "'" and not in_sq:
        in_sq = True
        out.append(c)
        i += 1
        continue
    if c == "'" and in_sq:
        in_sq = False
        out.append(c)
        i += 1
        continue
    if in_sq:
        out.append(c)
        i += 1
        continue
    # $(...)
    if c == '$' and i + 1 < n and cmd[i + 1] == '(':
        ...
```

**Why it's a problem:** The code correctly skips substitution extraction inside single quotes. However, it does not track double quotes (`in_dq`). In bash, `echo "$(curl attacker.com)"` is a substitution (the `$(...)` is evaluated), but `echo '$(curl attacker.com)'` is literal. The current code parses both the same way — extracts the inner `curl attacker.com` as a substitution in both cases. For the single-quoted version, the inner `curl` would later be classified as a network command, and if the whole command is classified at the top level (after decomposition), the classifier would see the `curl` and flag it as DATA_EXFILTRATION if any sensitive paths appear elsewhere. This is a false positive in the single-quote case, but conservative (safe side). The real issue: if the substitution extraction creates a `__SUB__` placeholder inside single quotes, the parsing of the outer command breaks. Example: `echo 'test$(id)test'` — the inner `$(id)` is extracted (malformed, since it's not actually a substitution), `__SUB__` is inserted inside the single quotes, the remaining `echo '...__SUB__...'` is split, and the classifier sees a malformed command.

**Fix:** Add `in_dq` state tracking. Skip substitution extraction when inside double quotes (they are evaluated, so the extraction is correct) but NOT inside single quotes. Alternatively, simplify: only extract substitutions when not inside any quotes.

**References:** command_decomposer.py lines 172–244 (_extract_substitutions). Line 185–198 handles only single quotes; double-quote handling is missing.

---

#### action_engine.py:810–825 — Shell command execution does not validate the covenant_check result before proceeding
```python
def _do_run_shell(self, cmd: str, reason: str = "") -> str:
    if not cmd or not cmd.strip():
        return "Empty command"
    # Quick covenant check on the command string itself
    self._check_covenant_command(cmd)
    _timeout = self._shell_timeout_for(cmd)
    result = subprocess.run(
        ["bash", "-c", cmd],
        capture_output=True, text=True, timeout=_timeout,
    )
    out = result.stdout.strip()[:4000]
    err = result.stderr.strip()[:1500]
    if result.returncode != 0:
        raise ShellCommandError(...)
```

**Why it's a problem:** On line 811, `_check_covenant_command(cmd)` is called. It raises `ForbiddenActionError` if the command violates the covenant. However, the caller of `_do_run_shell` is `_execute_action`, which wraps the method call in a try/except at line 714. If `_check_covenant_command` raises, the exception is caught, and a non-successful ActionResult is returned. This is correct behavior. But the issue is subtle: `_do_run_shell` is also called directly from `run_shell()` (line 756), which delegates to `_execute_action`. The covenant gate is redundant here — it already ran at line 668 in `_execute_action._covenant_gate()`. The secondary check at line 811 is defense-in-depth, which is good. However, `_check_covenant_command` is defined at line 827 and is a *different implementation* from the main `_covenant_violation` gate. It only checks `_covenant_violation()` + path patterns, NOT the obfuscation patterns. This means a command like `bash <<< rm -rf /` would pass `_check_covenant_command` (line 827) but should fail at the main gate. Inspection of the code shows the main gate at line 668 calls `_covenant_gate()` which does check obfuscation (line 497), so the secondary gate at line 811 is weaker. This isn't a bypass because the primary gate runs first, but it's a consistency issue: if `_do_run_shell` is called from a legacy path or refactored in the future, the secondary gate would fail to catch obfuscation.

**Fix:** Make `_check_covenant_command()` a true alias or consolidate the two gates. Either call the main `_covenant_violation()` function and obfuscation patterns in line 827, or remove the secondary check as redundant.

**References:** action_engine.py lines 827–842 (_check_covenant_command definition), lines 811 (call site), lines 495–501 (main obfuscation gate in _covenant_gate).

---

### nit — 1

#### tool_loop.py:147–159 — `_ALWAYS_MUTATING` regex uses verbose mode but is not well-commented
```python
_ALWAYS_MUTATING = re.compile(
    r"""
    (\bsudo\b)                          # privilege escalation
    | (\bdd\b)                          # raw disk writes
    | (\$\([^)]*\))                     # command substitution (can hide writes)
    | (`[^`]+`)                         # backtick substitution
    | (\|\s*(bash|sh|zsh|python\w*))    # pipe-to-shell pattern
    | (\s>\s*[^\s;|&]+)                 # output redirect
    | (\s>>\s*[^\s;|&]+)                # append redirect
    | (\s2>\s*[^\s;|&]+)                # stderr redirect
    """,
    re.VERBOSE,
)
```

**Why it's a problem:** The pattern `(\s>\s*[^\s;|&]+)` at line 154 matches a space followed by `>` followed by anything that's not a space/semicolon/pipe/ampersand. This is intended to catch output redirects like `> /tmp/file`. However, it does not account for:
1. Redirects without a leading space: `ls>/tmp/file` — the regex requires `\s>` so this is not caught. However, the daemon uses `re.split(r"[;|&]+", ...)` to break the command into stages, and `>` is not a separator, so `ls>/tmp/file` would be treated as a single token (the `ls` part plus the rest), and the basename extraction would get `ls`, which is in the allowlist. The redirect hidden inside the basename would be missed. This is a low-impact nit because most shells require spaces around `>`, but `ls>file` is valid bash.
2. Descriptors: `1> file` (explicit stdout descriptor) would match `\s>\s*`, but `1>file` would not. The regex is inconsistent.

**Fix:** Improve regex to handle `[0-9]*>` (with optional leading descriptor) and anchors better. Or use `shlex`-based parsing instead of regex splitting for more robust extraction of redirects.

**References:** tool_loop.py lines 147–159 (_ALWAYS_MUTATING regex), lines 183 (used in is_read_only).

---

## Coverage notes

- **Recursion bounds:** tool_loop.py has no max-recursion guard on `is_read_only`'s pipeline splitting or env-var loop (lines 183–196). A command like `A=B=C=D=...` (pathological nesting) could cause the env-var-stripping loop to run O(n) times. Low risk in practice, but defensively capping the loop would be prudent.
- **Snapshot completeness:** destructive_snapshot.classify() handles git_checkout, git_restore, git_reset_hard, rm, truncate. Not covered: `mv -f` (can overwrite), `dd of=file` (disk write), redirect write `>` in shell commands (expected — shell commands go through action_classifier instead). The snapshot module is correctly scoped.
- **Subprocess lifecycle:** All subprocess.run() calls use `capture_output=True` and `timeout=`. No zombie processes or FD leaks observed. Good.
- **Inter-module sync:** action_engine imports action_classifier dynamically when needed (not shown in this reading, but expected). Audit trail (action_logger, covenant_logger) is correct — dual-lane logging for actions vs covenant violations.
- **Fail-mode honesty:** Both _covenant_gate and _check_covenant_command are documented as "never raises" except for ForbiddenActionError. Correct.
- **Test coverage:** action_classifier.py has a smoke test (lines 592–646) with 25 test cases. command_decomposer.py has a smoke test (lines 301–332) with 15 cases. Tool_loop.py and destructive_snapshot.py have no embedded tests, but destructive_snapshot has a CLI (lines 376–426). Expected in a production system.

## Sync observations

- **Lane definition drift:** ACTION_TIERS (action_engine.py:215) has default lane 2 for run_shell, but classify_tier() (line 252) is a stub that just reads the static map. The real classifier (action_classifier.py) returns lane 0/2/3 dynamically based on command content. Callers of classify_tier() would get lane 2 for all run_shell, then the action would be dispatched, and the actual tier would be re-computed when the action executes. This is inefficient but not a bug — the approval flow will use the correct tier at execution time.
- **Covenant pattern duplication:** COVENANT_PATTERNS (action_engine.py:123) and _OBFUSCATION_RE (action_classifier.py:226) overlap. Example: both check for `eval`, `base64 -d | sh`, `curl | sh`. The action_engine refuses these at the gate (before the classifier runs), which is correct (deterministic gate first). The classifier also checks, providing defense-in-depth. No conflict, but maintainers should know these lists are related.

## Polish opportunities (flag only)

- `action_engine._check_covenant_command()` line 827 is a weaker reimplementation of the main covenant gate. Consolidate for maintainability.
- `command_decomposer._extract_substitutions()` needs double-quote awareness for correctness.
- `tool_loop._ALWAYS_MUTATING` regex should handle `[0-9]*>` and no-space redirects for robustness.
- Snapshot failure mode (major finding above) should return a warning-level result to the caller.
- Add recursion depth limit to tool_loop's env-var stripping loop as defensive hardening.

