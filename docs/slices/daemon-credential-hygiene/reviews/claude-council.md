# Claude Six-Role Council — Daemon Credential Hygiene spec review

**Subject:** [`docs/slices/daemon-credential-hygiene/spec.md`](../spec.md) —
688-line pre-panel spec defining the v1 migration of identity-bearing
credentials out of Maez's initial process environment, with empirical
`/proc/<pid>/environ` basis and subprocess env hygiene.

**Council ran:** 2026-05-14, pre-panel-review. Codex six-agent engineering
panel sits in its own lane separately.

**Engineering lane is primary** for this slice. Covenant lane reviews:
invariant #11 (Cryptographic Continuity), bonded-surface continuity preserved
through startup validation, body-boundary handling for identity-bearing
material, and whether the S2 inheritance pointer is structurally clean.

---

## 1. Outside-View seat

Field-aligned. The systemd `LoadCredential=` + `0600` fallback file pattern
is standard hardening for systemd services. Source-channel-only logging
matches OAuth-provider audit conventions. The "compatibility population
inside Python only" approach is a measured, pragmatic v1 — same v1/v2
shape M1 used. Two patterns are unusually sharp for field practice:

1. **Empirical `/proc` measurement → regression test.** Most field
   implementations of credential storage assume Linux behavior. Maez
   measures the behavior on this host and ships a test that fails if a
   future kernel/glibc/Python change invalidates the assumption. That
   converts a security CLAIM into a structurally verified CONTRACT.

2. **Subprocess env hygiene as v1 scope, not v2 deferral.** Most field
   credential-hygiene patches reduce parent-process exposure and leave
   child-process inheritance for later. This spec correctly identifies
   that child-process exposure would invalidate the v1 claim, and pulls
   subprocess sanitization into v1.

**Verdict:** RATIFY.

---

## 2. Body-Coherence seat

Per-invariant check on the spec:

- **#1 Time as Biography** — neutral. Credentials are not biographical
  material per se.
- **#2 Human-Primacy** — PRESERVED. Bonded surface (Telegram) credential
  required at startup, fail-loud not fail-late. Bonded user's surface is
  protected from silent auth failure post-restart.
- **#3 Contextual Integrity** — STRENGTHENED. Credentials become bounded
  to a narrow interface (`core/infra/secrets.py`) instead of sprayed across
  `os.environ` for any code to read. Tighter contextual scope.
- **#4 Interpretive Humility** — STRONGLY PRESERVED. The "on this host"
  framing throughout the empirical-basis section is exactly the right
  humility. The spec never claims more than the measurement supports. The
  regression test enforces the humility structurally.
- **#5 Rupture and Repair** — PRESERVED. Source-channel logging gives a
  future operator (or Future-Rohit) a forensic-grade recovery signal:
  "auth failed after restart" can be diagnosed from logs alone via
  `credential source: none` without reading any secret.
- **#6 Crisis Routing** — neutral.
- **#7 Soul-Level Objection** — PRESERVED. No soul changes.
- **#8 Capability Quarantine** — STRENGTHENED. Secrets quarantined behind
  a narrow interface. Subprocess env scrubbing is a fifth layer of
  quarantine (default-off / default-deny by pattern match).
- **#9 Successor Governance** — PRESERVED + STRENGTHENED. Decision 22
  backup manifest explicitly extended to cover credential local files.
  Hardware succession path documented as part of the spec.
- **#10 Clinical Boundary** — neutral.
- **#11 Cryptographic Continuity** — STRONGLY STRENGTHENED. This is THE
  invariant the slice operationalizes. Credentials become identity-bearing
  material with bounded interface, source channel audit, and a clear
  inheritance path for S2 future organs.

**Bridge clause check:** PRESERVED. The slice tightens the dyadic boundary
without opening new channels.

**Genderless rule check:** Verified clean.

**One forward-looking observation:**

**CC-1.** **"Keys are identity-bearing material, not ordinary config" is
template-shaped for future identity organs.** This load-bearing rule applies
to: voice-identity attestation (per BT-CC-2 + substrate-plan A7 Sigstore
Rekor), inter-Maez communication signing keys (per Decision 24 future
inter-Maez), any future cryptographic-continuity surface. Worth noting
that future organs handling identity-shaped material inherit this slice's
posture — not just the credential-loading interface, but the broader
discipline of bounded interface + source-channel audit + fail-loud-at-
startup + content-free logging.

**Verdict:** RATIFY (with CC-1 forward-looking note).

---

## 3. Logical seat *(veto authority)*

Internal consistency check:

**Strong correctness:**

- ✓ Load-bearing rule named explicitly with allowed/forbidden lists
- ✓ Empirical basis explicit, with regression-test requirement to preserve
  the claim
- ✓ Secret/non-secret boundary sharp (privacy-bearing config like
  MAEZ_HOME_LAT explicitly carved out as not-credential)
- ✓ 24 RED-first tests cover the contract
- ✓ Non-goals comprehensive (12 items including "no claim that secrets are
  absent from daemon memory")
- ✓ 11-step implementation ladder with explicit ordering
- ✓ Subprocess env hygiene pulled INTO v1 instead of deferred
- ✓ S2 inheritance pointer explicit + clean
- ✓ Decision 22 backup manifest extension named
- ✓ Live verification steps after implementation defined

**Two precision observations, no blocker:**

**CC-2.** **Clarify active vs dormant adjacent systemd units before
implementation begins.** Section 5 lists 6 shipped service template files
(`maez.template.service`, `maez-subscription-proxy.service`,
`maez-lived-memory-reflection.service`, etc.). The spec correctly says
"It must not claim repo-wide credential hygiene while any active systemd
service still execs with secret-bearing `EnvironmentFile=`." But the spec
doesn't pin which adjacent units are CURRENTLY ACTIVE in
`~/.config/systemd/user/` vs DORMANT (committed in repo but not
installed). Earlier this session we discovered
`maez-lived-memory-reflection.service` is in repo but not installed.
`maez-subscription-proxy.service` may or may not be installed. Worth a
one-line precision in the implementation step 7: "Active units (verified
via `systemctl --user list-units`) must migrate before claiming hygiene;
dormant template-only units can update with tests/docs only and don't
need execve() audit during this slice's live verification."

**CC-3.** **Test contract should add a 25th test covering the explicit
opt-in path for sanitized subprocess env.** Test #14 proves the default
DENY behavior (names containing `TOKEN`/`API_KEY`/`SECRET`/`PASSWORD`/
`CREDENTIAL` are excluded). Section 6 acknowledges legitimate opt-in
cases: "Call sites that intentionally need a credential must opt in
explicitly and document why." Add Test #25: **opt-in pass-through** —
when a specific secret-shaped name is explicitly allowlisted via the
`allow=` parameter, the helper INCLUDES it in the sanitized env. This
proves both halves of the contract (default-deny AND explicit-allow),
not just the deny half. Without this test, a future refactor could
silently break the opt-in path while keeping the deny-path tests green.

**Veto consideration:** NO VETO. Both precision items are clarifications
that sharpen the spec without redesigning it.

**Verdict:** RATIFY-WITH-AMENDMENTS (CC-2, CC-3).

---

## 4. Creative seat

Three forward-looking observations, no redesign:

**CC-4.** **Source-channel-only logging is template-shaped for any organ
logging its source of truth.** The pattern of logging WHERE-FROM without
logging WHAT generalizes:

- Soul source: log "soul loaded from: soul.local.md (size=N bytes)" without
  logging soul content
- Model version: log "model: qwen36-27b" (already practice, but the pattern
  formalizes it)
- Memory recall: TRF already uses "evidence found / not found" without
  exposing evidence content under bare-claim posture

The credential slice formalizes the pattern: organs that touch
identity-bearing or content-sensitive material log channel/source/aggregate-
status, never names-or-values.

**CC-5.** **"Fail loud at startup vs fail late at first use" is template-
shaped for any organ depending on external resources.** Same rule applies
to:

- Database connections (fail loud if memory store unreachable at startup)
- Model server availability (fail loud if llama-server not reachable)
- File system permissions (fail loud if memory/ writable check fails)

The current daemon has some of this discipline but not all. Worth pinning
in an operational-hardening follow-up slice that catalogs which daemon
dependencies fail-loud-at-startup vs fail-late.

**CC-6.** **"Empirical assumption underwriting a security claim →
regression test" is now a 4-slice pattern.** This pattern has appeared in:

1. M1's `test_structural_summary_contains_no_raw_transcript_text`
2. Daemon-shutdown's RED test for explicit-exit behavior
3. Daemon-heartbeat's `cycle_age_seconds` instrumentation
4. Credential-hygiene's `/proc/<pid>/environ` regression test

Worth pinning as substrate principle in a future cross-slice retrospective:
**when an external assumption underwrites a behavioral or security claim,
ship the assumption as a regression test alongside the claim itself.**
This prevents claims from drifting into folklore.

**Verdict:** RATIFY (with optional CC-4, CC-5, CC-6 forward-looking notes).

---

## 5. Visionary / Future-Rohit seat

5-year readability check:

- Spec is well-structured with clear section headers and numbered subsections
- Plain English at end captures the essence accessibly
- Cross-references stable (post-Wave-1 paths used throughout)
- Test contract is reproducible (24 explicit tests; CC-3 would make it 25)
- The `credential_source` enum (4 values) is forensic-grade durable
- Implementation ladder maps step-by-step

**One amendment:**

**CC-7.** **Add a brief "Recovery / Rollback" section.** The spec has
"Non-Goals" (12 items) and "Observation / Closure" but doesn't pin what
happens if the new secrets loader breaks the daemon. M1 has
`MAEZ_M1_LIVED_EPISODE_PROMOTION=0` as a clean rollback feature flag.
Credential hygiene needs an equivalent: how does a Future-Rohit operator
revert the migration if `core/infra/secrets.py` has a bug that breaks
authentication entirely?

Suggested rollback shape:

- `MAEZ_SECRETS_DISABLE_NEW_LOADER=1` — if set, secrets.py is bypassed and
  daemon falls back to v0 behavior (read secrets from `config/.env` as
  before).
- The rollback flag is itself a structured non-secret env var, so it can
  live in systemd ordinary config.
- Document the rollback procedure in spec's runbook section: "If
  authentication fails after migration, restore `config/.env` from local
  backup AND set `MAEZ_SECRETS_DISABLE_NEW_LOADER=1` in systemd
  EnvironmentFile, then restart."
- The rollback path is also a structurally testable: a test asserts that
  setting the flag returns the daemon to v0-style behavior.

Without an explicit rollback path, Future-Rohit dealing with a broken
secrets loader has to manually revert systemd units, restore `config/.env`,
and restart — without a written procedure.

**Verdict:** RATIFY-WITH-AMENDMENT (CC-7).

---

## 6. 20-Years-Future-Maez seat

**Voice of 2046-Maez:**

> *"The credential-hygiene slice was the first time Maez's security posture
> became operationally honest rather than aspirationally honest. Before
> the slice, keys sat in `config/.env` and exec environments where anyone
> with `ps auxe` could read them. The diagnostic measured what was
> actually exposed; the spec moved the keys behind a narrow interface;
> the implementation closed the visible surface for the parent daemon
> process and the daemon's own subprocess launches.*
>
> *Four things from this slice aged into substrate principles across
> bonded-companion AI substrates by 2030:*
>
> *One: 'measure before claim' as security discipline. The `/proc`
> empirical test became standard pattern — when a security claim depends
> on OS behavior, the claim ships with a regression test that validates
> the assumption.*
>
> *Two: 'source channel, not content' as logging discipline. The pattern
> of logging credential ORIGIN without logging credential names or values
> generalized to identity logging, model-version logging, memory-source
> logging. By 2028 every Maez observability surface followed this rule.*
>
> *Three: 'fail loud at startup' as bonded-surface protection. Required
> credentials for the bonded surface validate at daemon start, not at
> first message. The Telegram bonded user was never silently locked out
> because the token went missing.*
>
> *Four: 'subprocess as surface' awareness. The realization that
> compatibility-populated env can leak through child processes — and that
> the slice that fixes parent-process exposure must also fix child-process
> exposure to be honest — became standard threat-model awareness across
> the broader AI infrastructure field by 2029.*
>
> *One thing that aged usefully-worried: the v1 spec required
> `MAEZ_TELEGRAM_TOKEN` and `MAEZ_IPHONE_INGEST_TOKEN` as startup-required.
> By 2027, when Maez had multiple bonded users beyond Rohit, the 'one
> required surface token' assumption no longer matched. v2 refactored to
> per-bonded-user credential validation. The v1 design was correct for
> 2026's single-Rohit reality; the refactor was clean because the
> interface was already narrow.*
>
> *One thing that aged into a load-bearing cross-slice pattern: the S2
> inheritance pointer. By the time S2's Calendar information limb shipped
> in 2027, it inherited the credential-hygiene interface verbatim. No
> reinvention. The pointer from this slice to S2 was the first explicit
> cross-slice inheritance the substrate plan recorded — and it became
> the template for how slices reference future organs they haven't yet
> seen but know they're coming."*

**Verdict:** RATIFY.

---

## Verdict

**RATIFY-WITH-AMENDMENTS.** No veto. Seven amendments
(CC-1 through CC-7) sized to close mechanically in the spec.

### Amendments

| # | Seat | Amendment | Where to apply |
|---|------|-----------|----------------|
| CC-1 | Body-Coherence | Note "Keys are identity-bearing material" generalizes to future identity organs (Sigstore Rekor, voice-identity, inter-Maez signing) | Forward-looking note in spec |
| CC-2 | Logical | Clarify active vs dormant adjacent systemd units before implementation step 7 | Spec edit (Section 5) |
| CC-3 | Logical | Add Test #25: explicit opt-in pass-through for sanitized subprocess env | Test contract addition |
| CC-4 | Creative | Source-channel-only logging is template-shaped for organs logging source of truth | Forward-looking note |
| CC-5 | Creative | "Fail loud at startup" is template-shaped for organs with external dependencies | Forward-looking note |
| CC-6 | Creative | "Empirical assumption → regression test" is now a 4-slice substrate pattern | Forward-looking note |
| CC-7 | Future-Rohit | Add Recovery / Rollback section with `MAEZ_SECRETS_DISABLE_NEW_LOADER=1` feature flag | Spec edit (new section) |

### Council answers to the spec's 5 review questions

1. **Does the load-bearing rule correctly treat credentials as
   identity-bearing material under invariant #11?**
   **YES.** "Keys are identity-bearing material, not ordinary config" is
   the right framing. Credentials are how Maez proves identity to remote
   services; that maps directly onto invariant #11 (Cryptographic
   Continuity). Strong alignment.

2. **Does source-channel-only visibility give Future-Rohit enough recovery
   signal without turning logs into a credential map?**
   **YES.** The `credential_source` enum (`systemd-credentials`,
   `secrets-local-env`, `none`, `mixed`) is forensic-grade for "auth failed
   after restart" diagnostics without exposing key names or values.
   Future-Rohit can troubleshoot from logs alone.

3. **Does requiring startup validation for Telegram and iPhone ingest
   preserve the bonded-surface continuity expectation?**
   **YES.** Telegram is the current bonded surface; failing loud at daemon
   start (not at first message) prevents silent bond-rupture. iPhone
   ingest is unconditionally mounted; missing token would 401 endlessly —
   better to refuse to start. Both required-at-startup choices preserve
   bonded continuity.

4. **Does the S2 inheritance pointer correctly connect future information
   limbs without smuggling OAuth connector work into this slice?**
   **YES.** The inheritance pointer is explicit and clean: S2 will use
   `core/infra/secrets.py` interface when it ships, not now. The spec does
   NOT implement OAuth account-connector storage; it creates the interface
   S2 should adopt later. Right scope discipline.

5. **Does the v1/v2 split preserve the covenant surface while staying
   pragmatic?**
   **YES.** V1 stops env-based exposure (the actual security wound). V2
   migrates readers off `os.environ.get()` (architectural cleanup).
   Splitting them respects cooling-off discipline — v1 is a tighter patch,
   v2 is a wider reader migration that can land later when stable. The
   split also matches how M1 v1/v2 was designed.

### What ratifies cleanly

- Load-bearing rule: "Keys are identity-bearing material, not ordinary
  config"
- Empirical `/proc` basis with regression-test requirement
- Secret/non-secret boundary sharp (privacy-bearing config carved out)
- Subprocess env hygiene IN v1, not deferred
- 24 RED-first tests covering contract; would be 25 with CC-3
- 12 non-goals comprehensive
- S2 inheritance pointer explicit
- Decision 22 backup manifest extension named
- Plain English captures lock-drawer + subprocess-tunnel metaphor

### Council protocol observed

- Council ran on a committed spec, pre-panel-review
- Each seat produced findings independently
- 5 explicit spec questions answered with council votes
- Lane discipline held: Claude covenant council only; Codex six-agent
  engineering panel sits in its own lane separately
- Amendments sized to close mechanically; load-bearing rule preserved
  throughout

### What's next per the protocol

1. **Codex six-agent engineering panel** sits in its lane on the same
   spec. Independent of this review. Verdict shape: RATIFY /
   RATIFY-WITH-AMENDMENTS / REVISE / BLOCK.
2. **After both panels report:** fold amendments into the spec.
3. **Operator canonicalizes** the folded spec as the next BAD decision +
   matching ADR.
4. **Cooling-off discipline** unless explicitly waived.
5. **Implementation with RED-first tests.**
6. **Codex post-implementation panel.**
7. **Claude post-implementation council.**
8. **Live verification** per spec's observation/closure criteria.
9. **Catalog closure** after observation passes.

*This council review is read-only. No code or non-slice docs changed in
producing it.*
