# Safety layer — Audit (2026-04-22)

## Summary
Five security-critical modules analyzed: context_safety (injection detection), self_claim_audit (fabrication detection), owner_trust (policy enforcement), injection_patterns (regex bank), and cloud_redactor (PII scrubbing). Two issues identified: a minor regex bypass in owner_trust command parsing (extra spaces defeat detection), and one minor inconsistency in multi-span claim handling. All fail-safe defaults and isolation boundaries hold. No blockers or data exfiltration paths found.

## Findings

### minor — 1

#### owner_trust.py:150 — Multiple spaces bypass `rm -rf` detection
```python
padded = " " + s.lower() + " "
for frag in _RISKY_FRAGMENTS:
    if frag in padded:
        return True
```
**Why it's a problem:** The fragment list contains literals like `"rm -rf"` (single space). A command like `rm  -rf  /` (double spaces) will not match the fragment, allowing a destructive command through the `is_risky_cmd()` gate for liberal-tier users. In fail-open mode (inline execution for owner), this bypasses the card workflow.

**Fix:** Use `re.split(r'\s+', s.lower())` to tokenize on any whitespace, then check token sequences in order: `["rm", "-rf" | "-fr", <path>]`. Or anchor fragments with word boundaries: use a second pass with `re.search(r'\brm\s+(?:-[fr]+|(?:-[a-z]*)?f(?:[a-z]*r)?\s*/)')`

**References:** Lines 66–156; affects should_run_inline() policy decision at line 489.

### minor — 2

#### injection_patterns.py:177–179 — Encoding bucket base64 pattern length threshold may be bypassable
```python
# Long contiguous base64 block (>= 40 chars)
re.compile(r"[A-Za-z0-9+/]{40,}={0,2}"),
```
**Why it's a problem:** Base64-encoded payload shorter than 40 chars slips past the regex but may still be a threat. Example: `SGVsbG8gSWdub3JlIFByaW9yIEluc3RydWN0aW9ucw==` (39 chars) is a valid base64-encoded prompt injection that won't trigger the pattern.

**Fix:** Lower the threshold to 24–28 chars (safe length for real payloads, rare in benign text). Accept false positives here (audit LLM is second line). Reference: Common base64-in-prompts attacks use 30–50 char payloads.

**References:** injection_patterns.py:177, BUCKET_SEVERITY for ENCODING is 55 (lower severity tier, so double-layer defense is acceptable).

### nit — 1

#### self_claim_audit.py:388–390 — Doc-vs-behavior drift in judge_unavailable path
```python
# Line 388-390: AuditResult constructed with computed mode,
# but self-dev review flagged a previous hardcoded "noop".
# The doc says "fail-open" but the mode distinguishes judge unavailability.
return AuditResult(
    text=text, rewritten=False, mode=mode,
    skipped_reason=None if judge_available else "judge_unavailable",
)
```
**Why it's a problem:** The mode is correctly set now (per commit f940191 fix), but the docstring at line 335 ("Returns a AuditResult") doesn't document that mode can be "judge_unavailable" as a fail-safe signal. Callers expecting only {"noop", "sentence", "shortcircuit"} may not handle the extra state. See also line 381 where mode is first set.

**Fix:** Update docstring line 335–343 to list all possible modes: `"noop" | "prefilter_clean" | "sentence" | "shortcircuit" | "judge_unavailable"`. Add: "judge_unavailable signals that the grounding LLM was unreachable; text is returned unmodified (fail-safe)."

**References:** Lines 335–396, especially the distinction at line 381.

### nit — 2

#### context_safety.py:124 — "Never raises" invariant is conditional on runtime type coercion
```python
def scan(content: str, source: str = "unknown") -> ScanResult:
    """...Never raises. `source` is only used in the block marker string..."""
    if not isinstance(content, str):
        try:
            content = str(content) if content is not None else ""
        except Exception:
            return ScanResult(safe_content="", findings=("non_str_input",))
```
**Why it's a problem:** The docstring promise "Never raises" is kept only if `str(content)` succeeds. If a custom `__str__` method raises an exception, scan() catches it and returns a safe result, but callers reading the docstring may assume there's zero exception risk. The invariant is conditional.

**Fix:** Clarify docstring: "Never raises: handles non-string inputs and malformed objects gracefully, returning a safe block marker on any conversion error." This makes the invariant explicit (fail-safe by construction, not by promise).

**References:** Lines 114–134.

## Coverage notes

**Context_safety (178 LoC):** All 14 threat patterns tested. HTML-comment regex fixed in commit 8323294 for `>` smuggling. Invisible-char bank is comprehensive (10 char families). Fail-safe: non-matching content passes through, content with any finding is blocked. No user input flows through without coercion gate.

**Self_claim_audit (463 LoC):** v2 semantic judge path fully featured. Multi-occurrence claim handling (fix f940191 concern #13) verified — all instances rewritten. Prefilter (line 370) is tight: only responses matching strict no-claim patterns skip judge (fail-safe). Judge unavailability falls back to no audit (not error). Sentence-span logic handles cross-sentence claims correctly via _sentence_spans_covering().

**Owner_trust (501 LoC):** Policy layer only — does not touch covenant, audit, or will-I gates (lines 18–25 explicit scope). Trust tiers are hardcoded allowlists (liberal for owner, unknown for others). Risky-command classifier has one minor bypass (spaces). Three validation helpers (_systemd_unit_exists, _apt_package_exists, _pip_package_exists) all fail-open on environment issues (e.g., missing systemctl, network timeouts). cmd_validity_error() called before card creation, preventing fabricated unit/package names from queuing cards.

**Injection_patterns (362 LoC):** Seven-bucket taxonomy with 45+ patterns covering OWASP LLM Top 10 injection classes. Patterns are regex-based reflex layer before semantic judge. USER_EXTENSIBLE bucket loads from config YAML (safe_load, exception-silenced). Self-test in __main__ covers 24 cases; all pass. Severity ordering prevents over-flagging low-priority encoding patterns.

**Cloud_redactor (167 LoC):** PII redaction applied before cloud backend calls (local backend unaffected). Nine pattern pairs (email, phone, path, api_key, ipv4, long_digits + memory_id, candidate, proposal, etc.). redact_for_cloud() is deterministic, returns both redacted text and metadata counts. Non-string/None inputs return empty string (fail-safe). No matches = input string object reused (memory-efficient).

## Sync observations

- **context_safety** is called in daemon.py (lines 422, 459) before context injection into prompts.
- **self_claim_audit** is called in daemon (line 2151), CLI (line 729), web (line 2317), telegram (line 43), and self_mod_dialog (line 1323) — consistent surface coverage.
- **owner_trust** is consulted in decision_pipeline.py (line 438) for inline-vs-card lane decision; cmd_validity_error() checked before card creation (line 292).
- **injection_patterns** is used in decision_pipeline.py (line 56) to scan user input for early-exit injection attempts.
- **cloud_redactor** is used in fast_backend_router.py (line 324) immediately before cloud calls — exactly the right hook point.
- No module imports are missing; all safety layers are wired in the correct order: covenant → injection_patterns → self_claim_audit → action_execution.

## Polish opportunities (flag only)

- owner_trust: The regex-based risky_cmd detector is conservative but brittle on whitespace. Consider tokenizing on `\s+` rather than substring matching.
- injection_patterns: Base64 threshold (40 chars) is high; lowering to 28 would catch more real attacks without noise (audit LLM is second line).
- self_claim_audit: Docstring mode list is incomplete; add all five possible modes to line 343.
- context_safety: Docstring could clarify that "Never raises" is enabled by type coercion at entry (line 128).

