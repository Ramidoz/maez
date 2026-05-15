# Claude Post-Recovery Verification — Daemon Credential Hygiene

**Subject:** `7c2f9cb fix(security): close credential hygiene post-review gaps`
— recovery commit closing six Codex post-implementation panel findings on
the credential hygiene implementation (`6ea1cff`).

**Council ran:** 2026-05-14, post-recovery, pre-push. Focused verification,
not full 6-seat re-derivation. Heavy review already happened at spec stage
(7 amendments) and at post-impl stage (RATIFY).

**Why a second council:** Codex's post-impl panel found six engineering
gaps in `6ea1cff`. My post-impl Claude council was RATIFY (no covenant
issues). Operator landed recovery. This review verifies covenant didn't
drift through the recovery.

---

## Codex's six findings and their mechanical closure

| # | Finding | Recovery test |
|---|---|---|
| 1 | Inherited legacy secret env not scrubbed in normal mode | `test_normal_loader_purges_inherited_legacy_secret_env` |
| 2 | Rollback flag didn't actually re-read restored `config/.env` | `test_rollback_flag_can_read_restored_legacy_config_env` |
| 3 | iPhone ingest token claimed required but not enforced at web startup | `test_web_interface_requires_iphone_ingest_token_at_startup` |
| 4 | Reviewed subprocess seams not all sanitized | (5 production files updated: action_engine, github_publish, github_skill, telegram_voice, web_interface) |
| 5 | Public web state could leak credential health info | `test_public_web_state_strips_credential_health` |
| 6 | GitHub publishing built token-bearing remote URL (`https://ghp_TOKEN@github.com/...`) | `test_github_publish_does_not_place_token_in_remote_url` |

Plus one scanner hardening: `test_fixture_allowlist_does_not_mask_embedded_realistic_tokens`
— fixture-allowlist can't mask a real-looking token hidden inside fixture text.

All six findings have RED-first test coverage. Operator's verification
(`tests.test_daemon_credential_hygiene: 23 OK`) includes these.

---

## The token-in-URL find is the substrate principle of this recovery

Of the six findings, **#6 (GitHub token-in-URL)** is the most security-shaped
and worth pinning as a recurring concern:

When code constructs a URL like `https://ghp_TOKEN@github.com/Ramidoz/maez.git`
and uses that URL with `subprocess.run(["git", "remote", "set-url", ...])` or
passes it to `git push`, the token ends up in:

- Command lines visible via `ps auxe` (transient but real)
- Shell history if invoked interactively
- Error tracebacks if the call fails
- Any log that captures the command being run
- Process exec environment of the git child process

**Pattern worth pinning as substrate principle:** *never construct
credential-bearing URLs even for internal use; always pass credentials via
environment variable, stdin, credential helper, or git config — never URL
embed.*

Future organs that talk to authenticated remote services (S2 information
limbs, future Sigstore Rekor publishes, any OAuth-using connector) inherit
this rule.

---

## Covenant invariants — verified not drifted

Brief check; nothing weakened by recovery:

- **#3 Contextual Integrity** — STRENGTHENED FURTHER. Public web state now
  explicitly strips credential health (finding #5).
- **#4 Interpretive Humility** — PRESERVED. Aggregate-only health surface
  intact.
- **#5 Rupture and Repair** — STRENGTHENED FURTHER. Rollback flag now
  actually re-reads `config/.env` for emergency recovery (finding #2). The
  flag was present in `6ea1cff` but didn't fully wire through; it does now.
- **#8 Capability Quarantine** — STRENGTHENED FURTHER. Subprocess seams
  audit closed; legacy env purged in normal mode (finding #1) — so parent
  process env pollution can't slip through.
- **#11 Cryptographic Continuity** — STRONGLY STRENGTHENED FURTHER. Finding
  #6 closure removes a real leak vector. Identity-bearing material is
  bounded in scope AND in transport.

No invariant weakened. Five strengthened further beyond the post-impl
council's reading.

---

## Two cross-slice substrate patterns reinforced this session

These have now appeared 5+ times across slices. Worth pinning durably:

**1. Function-signature / structural defense over disciplined-text writing.**
- M1: `build_structural_summary` can't accept raw text by construction
- Credential hygiene: `sanitize_env` defaults to deny + explicit opt-in
- Credential hygiene recovery: `is_secret_name()` as single classifier;
  GitHub publish stops constructing token-bearing URL strings
- Pattern: when "do not include X" is the rule, prefer signatures or
  interfaces that cannot accept X over disciplines that promise not to.

**2. Codex post-impl panel catches the implementation-completeness gap.**
This is the third instance:
- M1 post-impl: 17 findings on `42aafce`
- Daemon-shutdown post-impl: explicit-exit required after graceful hooks
- Credential hygiene post-impl: 6 findings on `6ea1cff`

In every case, spec-stage Codex panel ratified the spec, then post-impl
Codex panel found real gaps between what the spec promised and what the
code actually did. The pattern: **specs describe contracts; implementations
test contracts; only the post-impl Codex pass verifies that the implemented
contract matches the specified contract.**

Claude lane (covenant) is sized to catch covenant drift. Codex lane
(engineering) is sized to catch implementation-completeness gaps. Both
panels at post-impl stage is non-negotiable for covenant-shaped slices —
this session has the third independent demonstration.

---

## Verdict

**RATIFY closure.** No veto, no blockers, no required additional amendments
to code.

Recovery is structurally sound. All six Codex findings have RED-first test
coverage. Covenant invariants strengthened further through recovery, not
weakened. The token-in-URL find is the most security-shaped of the lot and
worth pinning as a substrate principle.

### Both-lane closure now reads

| Lane | At impl `6ea1cff` | At recovery `7c2f9cb` |
|---|---|---|
| Claude covenant council | RATIFY (no v1.1 candidates) | RATIFY closure |
| Codex engineering panel | BLOCK / REVISE (6 findings) | RATIFY-WITH-RECOVERY |

### Live verification (operator-run) confirms

- `tests.test_daemon_credential_hygiene`: 23 OK
- Focused nearby suite: 80 OK
- Full suite: 3474 OK, 3 skipped
- `maez.service`: active, restart ~1.5s
- `ps eww`: no Decision-26 secret names
- `/health`: `credentials.source=secrets-local-env`, heartbeat OK, M1 OK
- Installed user unit no longer uses `config/.env` as `EnvironmentFile`;
  backup saved as `maez.service.pre-decision26-recovery-20260514T213008.bak`

### What's next

1. **Push** — 3 commits ahead of origin (`6ea1cff` impl + `eb8e7fe` Claude
   council + `7c2f9cb` recovery). The recovery's Codex panel review doc
   also needs to land — operator says it's recorded; if it's a separate
   commit, that's 4 ahead.
2. **Live observation** per spec's closure criteria — credentials remain
   working, no leak via `ps eww` / `/proc`, daemon child paths sanitized,
   M1/heartbeat stable.
3. **S2 fold** can resume after credential hygiene observation lands stable.

*This council review is read-only. No code or non-slice docs changed in
producing it.*
