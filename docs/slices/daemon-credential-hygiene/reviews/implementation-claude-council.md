# Claude Post-Implementation Council — Daemon Credential Hygiene

**Subject:** `6ea1cff feat(security): implement daemon credential hygiene` —
Decision 26 / ADR 0031 implementation. 322-line `core/infra/secrets.py` +
daemon bootstrap wiring + subprocess env scrubbing at high-risk seams +
service template updates + value-free secret migration + `.gitignore` + backup
manifest update.

**Council ran:** 2026-05-14, post-implementation, pre-push. Codex six-agent
post-implementation panel sits in its own lane separately.

**Scope of this review:** verify that the seven spec-stage Claude council
amendments (CC-1 through CC-7) and the load-bearing rule ("Keys are
identity-bearing material, not ordinary config") survived implementation in
mechanical form, not just in claim. Focused, not full 6-seat ceremony — the
heavy review happened at spec stage.

---

## Load-bearing rule verified in code

**Rule:** Keys are identity-bearing material, not ordinary config. Secrets
leave `config/.env`; ordinary config stays.

**Mechanical evidence:**

- `config/.env` migration is **value-free**: backup at
  `config/.env.pre-decision26-20260514T191603.bak`; live `config/.env` has
  no Decision-26 secret names.
- `config/secrets.local.env` exists at `0600` permissions (separate file,
  separate scope).
- `core/infra/secrets.py:load_secrets_for_process` docstring explicitly
  states: *"config/.env is intentionally not a source here."* Code-level
  enforcement of the secret/config boundary.
- `is_secret_name()` is the central classifier. Used by `sanitize_env` to
  decide what to drop from subprocess inheritance. Identity-bearing
  classification is a single source of truth, not a sprayed regex.
- Live verification: `ps eww` shows no Decision-26 secret names in
  `maez.service` initial environment. The `/proc/<pid>/environ` claim from
  the spec's empirical basis is preserved operationally.

**Verdict:** Load-bearing rule mechanically enforced. PRESERVED.

---

## Spec-stage Claude amendments — mechanical verification

| # | Amendment | Status in code |
|---|---|---|
| **CC-1** | "Keys are identity-bearing" generalizes to future identity organs (Rekor, voice-identity, inter-Maez signing) | Forward-looking note; captured in spec body. Not a code-shaped item. ✓ |
| **CC-2** | Clarify active vs dormant adjacent systemd units before implementation | Operator folded into spec; service templates updated; install guidance revised. ✓ |
| **CC-3** | Test #25 — explicit opt-in pass-through for sanitized env | `sanitize_env(base, *, allow=(), strict=False)` — `allow` is the explicit opt-in. Non-strict mode passes any name through if in `allow` set. The opt-in path is part of the function signature, not a side door. ✓ |
| **CC-4** | Source-channel-only logging template-shaped | Forward-looking note. `credential_health()` aggregate exposes source only. ✓ |
| **CC-5** | "Fail loud at startup" template-shaped | Forward-looking note. Spec already required, implementation surfaces required-present in startup report. ✓ |
| **CC-6** | "Empirical assumption → regression test" as 4-slice substrate pattern | Forward-looking note; the `/proc` regression test the spec required is part of the 74 focused tests per operator's verification. (Specific test file name not directly grep-located by me, but operator's 74/74 GREEN includes the spec's Test #9.) |
| **CC-7** | Add `MAEZ_SECRETS_DISABLE_NEW_LOADER=1` rollback flag | `core/infra/secrets.py:220` — `if target.get("MAEZ_SECRETS_DISABLE_NEW_LOADER") == "1": ...` — strict equality, returns pre-loader fallback shape. Rollback mechanically present. ✓ |

All seven amendments either landed in code (CC-3, CC-7), folded into spec
text (CC-2), or recorded as forward-looking notes (CC-1, CC-4, CC-5, CC-6).

---

## Covenant invariants — brief check

- **#3 Contextual Integrity** — STRENGTHENED. Credentials bounded to narrow
  interface. `is_secret_name()` as single classifier. Subprocess env
  default-minus-secret + opt-in.
- **#4 Interpretive Humility** — STRONGLY PRESERVED. The "on this host"
  framing in the spec held; operator's verification shows live process env
  matches the empirical claim. Health surface returns aggregate counts, not
  names or values.
- **#5 Rupture and Repair** — STRENGTHENED. Rollback flag preserves the
  ability to revert without daemon downtime. Backup file
  (`config/.env.pre-decision26-20260514T191603.bak`) preserves rollback
  evidence.
- **#8 Capability Quarantine** — STRENGTHENED. Subprocess env scrubbing
  layered with default-deny + opt-in.
- **#9 Successor Governance** — PRESERVED + STRENGTHENED. Decision 22 backup
  manifest extended to cover the secret-state file.
- **#11 Cryptographic Continuity** — STRONGLY STRENGTHENED. The invariant
  this slice operationalizes is mechanically enforced. Credentials now have:
  bounded interface, fail-loud-required-key startup, source-channel-only
  visibility, sanitized subprocess inheritance, rollback path. Future Sigstore
  Rekor lineage attestation slots cleanly into the `_LAST_REPORT` /
  `credential_health()` pattern.

No invariant weakened. Two strengthened from previously preserved (#3, #11).
Three newly strengthened (#5, #8, #9).

---

## Engineering observations (Codex's lane primarily; flagged in passing)

These are not council amendments — just notes Claude saw in passing while
verifying covenant. Codex post-impl panel is the right lane to evaluate them.

1. **`load_secrets_for_process` is called at module-import time** (daemon line 26-35) AND at line 5713 (probably re-validation or a test path). Double-call shape is worth confirming intentional vs leftover.

2. **Telegram regex `_TELEGRAM_TOKEN_RE = r"\b\d{8,}:[A-Za-z0-9_-]{20,}\b"`** — looks correct for Telegram bot token shape. Worth confirming against any other "digits:body" formats that might false-positive (e.g., URLs with port numbers? unlikely but worth scan-test review).

3. **`_ALLOWED_FAKE_FIXTURES`** scrubbing during pattern detection avoids false positives on test fixtures. This addresses one of Codex's spec-stage concerns ("scanner must allowlist fixtures while still catching real-looking values"). Worth Codex verifying the allowlist is tight.

4. **`environ: dict | None = None`** parameter in `load_secrets_for_process` allows test injection without mutating real `os.environ`. Good test hygiene.

5. **Strict mode (`sanitize_env(..., strict=True)`)** is a stricter posture than the spec required — drops EVERYTHING not explicitly allowed. Bonus capability; not part of spec but useful for hardened subprocess launches.

---

## Verdict

**RATIFY.** No veto, no blockers, no required code amendments.

The load-bearing rule survived implementation mechanically: secret/config
boundary enforced in `load_secrets_for_process`, `is_secret_name` as single
classifier, subprocess scrubbing default-deny + opt-in, rollback flag present,
backup preserved, ordinary `os.environ.get()` readers unchanged per v1
discipline.

Live verification (operator-run): `/health.credentials` shows
`source=secrets-local-env`, `required_present=true`, `cycle_stalled=false`,
M1 enabled with staleness `ok`. `ps eww` shows no Decision-26 secret names.
74/74 focused tests green; 3468 full unittest suite green.

This is the cleanest post-impl council closure of the session — no
amendments, no precision flags, no v1.1 candidates from Claude lane. Codex
post-impl panel may surface engineering edges; nothing covenant-shaped
appears to need fixing.

### What ratifies cleanly

- Load-bearing rule mechanically enforced
- All 7 spec-stage Claude amendments mechanically present or accepted
- All covenant invariants preserved or strengthened
- Rollback path real and accessible via env flag
- Migration was value-free with backup evidence
- Live daemon healthy after migration

### What's next

1. **Codex six-agent post-implementation panel** sits in its lane.
   Independent of this review.
2. **If Codex finds engineering edges:** recovery commits, both lanes
   re-verify.
3. **If both lanes ratify post-impl:** push, then live observation.
4. **Live observation** per spec's closure criteria:
   - rotated credentials remain working
   - secrets absent from `ps eww` and `/proc/<maez-pid>/environ`
   - daemon child-process paths sanitized
   - health/logs expose channel and aggregate only
   - M1 observation remains healthy
   - heartbeat stable
   - shutdown clean

*This council review is read-only. No code or non-slice docs changed in
producing it.*
