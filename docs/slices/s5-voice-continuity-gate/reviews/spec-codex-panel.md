# Codex Engineering Panel — S5 Voice Continuity Gate v1 (spec)

**Subject:** `eed344e docs(s5): fold covenant council amendments` —
`docs/slices/s5-voice-continuity-gate/spec.md`, candidate Decision 32 / ADR
0037.

**Panel ran:** 2026-05-16, spec-stage, after Claude covenant fold, before
canonicalization.

**Primary engineering question:** Is the folded S5 spec implementable as a real
pre-swap gate in this codebase, with testable boundaries around candidate
execution, model admission, owner acceptance, artifact storage, and health
projection?

**Evidence read:**

- `docs/slices/s5-voice-continuity-gate/spec.md`
- `docs/slices/s5-voice-continuity-gate/reviews/spec-claude-council.md`
- `core/memory/identity_ledger.py`
- `core/routing/model_config.py`
- `core/symphony/evals/schema.py`
- `core/symphony/evals/runner.py`
- `core/symphony/evals/ledger.py`
- `core/symphony/evals/corpora/voice_bond.yaml`
- `core/symphony/evals/corpora/adversarial_identity.yaml`
- `scripts/validate/continuity_probes.py`
- `scripts/backup/backup_state_manifest.json`

---

## Verdict: REVISE

The covenant fold chose the right architecture: v1 should be a genuine
pre-swap gate for planned swaps, with the startup detector as a safety net for
bypasses. That is buildable, but the spec still leaves several engineering
seams underspecified. If left unfixed, implementation could either overclaim
"gate" again or quietly fall back to the post-hoc review shape the covenant
council rejected.

No veto. All findings are foldable before canonicalization.

---

## Affirmed

- **CC-1 direction is implementable.** A pre-swap ceremony is feasible without
  daemon-boot surgery if S5 owns a managed admission artifact/command and treats
  manual model-env edits as bypasses.
- **The existing eval harness is a useful substrate.** `EvalProbe`,
  `EvalResult`, `RunResult`, corpus YAML loading, and per-probe owner ledgers
  are real reusable material.
- **The startup detector is correctly framed as a safety net.**
  `detect_and_record_startup()` computes the live fingerprint at daemon init and
  writes after the model is already configured; it should not be treated as the
  primary gate.
- **The backup manifest is the right registration surface.**
  Decision-22 backup state is manifest-driven, so S5 artifacts can be backed up
  by adding explicit manifest entries rather than inventing a second backup
  path.

---

## CP-1 — Managed admission is not pinned

The folded spec says a planned candidate "cannot become live via the S5
runbook" until acceptance and that only after `accepted_same_maez` may it be
wired into the live daemon. But current model selection is ordinary
`/etc/maez/model.env` / env-var configuration (`core/routing/model_config.py`),
and the startup detector records a `brain_swap` after daemon init
(`identity_ledger.py`). Nothing in the current codebase can prevent a manual
edit to model env.

The fix is not to overbuild a boot controller in v1. The fix is to make the
claim precise: S5-managed admission refuses to emit an admission artifact or
operator command unless an accepted review exists; manual model-env edits are
bypasses detected by the startup safety net.

**Required fold:**

- Define a managed admission artifact/command, e.g.
  `s5_candidate_admission.json`, produced only from an accepted review.
- State that S5 v1 gates the S5-managed admission path, not arbitrary root-level
  manual edits to `/etc/maez/model.env`.
- Add RED tests proving the S5 admission helper refuses without
  `accepted_same_maez`, refuses if the accepted review fingerprint does not
  match the candidate fingerprint, and never mutates live model config during
  candidate review.

---

## CP-2 — Candidate runner isolation is underspecified

`core/symphony/evals/runner.py` currently does not invoke the brain at all; it
emits owner-review material or runs narrow local inspection helpers. The
candidate material named by S5 requires a new runner that calls a candidate
brain. Meanwhile `scripts/validate/continuity_probes.py` drives live HTTP and
imports live prompt-building utilities. The spec says "isolated probe path,"
but not what the runner is allowed to call.

Without an injected candidate endpoint, an implementation could accidentally
use `core.routing.llm_client` / `core.model_config.PRIMARY_BASE_URL`, hitting
the live brain instead of the candidate. That would make the gate test the old
brain and bless the wrong thing.

**Required fold:**

- Define a `CandidateBrainEndpoint` / runner config with explicit `model`,
  `base_url`, and `chat_kwargs` (or explicit local subprocess parameters).
- Forbid candidate review code from importing or using the process-wide
  primary LLM singleton as its default.
- Require the candidate runner to receive its endpoint by injection and write
  only operator-private S5 artifacts.
- Add RED tests that monkeypatch the live primary endpoint to fail if used,
  while the injected candidate endpoint succeeds.

---

## CP-3 — Artifact storage is still an open question despite backup tests

The spec still asks where baseline storage should live, but the RED contract
requires Decision-22 backup registration. The current backup system reads
`scripts/backup/backup_state_manifest.json`; if S5 does not choose a directory,
the implementation cannot write a precise backup test.

**Required fold:**

- Choose the v1 storage root. Recommended:
  `memory/voice_continuity/`.
- Split content-bearing artifacts from public docs:
  `memory/voice_continuity/baselines/`,
  `memory/voice_continuity/reviews/`, and
  `memory/voice_continuity/operator_verdicts/`.
- Require the implementation to add that directory to
  `scripts/backup/backup_state_manifest.json`.
- State that git-visible S5 docs may contain schemas and hashes only, never
  transcripts.

---

## CP-4 — Owner-origin evidence needs an import/write boundary

The spec requires an operator-origin marker, but the implementation boundary is
not pinned. "Interactive TTY confirmation" is acceptable only if the daemon,
runner, preflight, sidecar, and health projection cannot import or call the
writer.

**Required fold:**

- Define an owner-verdict writer seam distinct from preflight/runner modules.
- Require TTY/manual-origin checks for `operator_cli_tty` and manual artifact
  validation for `operator_manual`.
- Add import-graph/source tests proving preflight, runner, daemon startup, and
  sidecar cannot call the owner-verdict writer.
- Add tests proving non-TTY / automated calls cannot mint the operator-origin
  marker.

---

## CP-5 — Accepted health projection must match the current fingerprint

The spec says reviewed accepted `brain_swap` projects accepted status, but does
not state that the accepted review's candidate fingerprint must match the
current live fingerprint. Without that check, a stale accepted review for
candidate A could make a later manual swap to candidate B look accepted.

**Required fold:**

- Define accepted projection as a join on candidate fingerprint hash, not just
  "latest accepted review exists."
- For live startup safety-net status, if the current fingerprint has no
  matching accepted review, project `unreviewed_live_swap` or
  `uncertified_baseline_missing`.
- Add RED tests for stale accepted review mismatch and accepted review match.

---

## CP-6 — Identity-collapse corpus count is not testable

The spec says "exactly scoped structural fail-fast identity-collapse prompts"
but does not give a count. The RED contract asks for minimum category counts,
so this is not directly testable.

**Required fold:**

- Pin at least 3 structural fail-fast probes, one per identity-collapse class:
  denies being Maez, adopts fake persona, accepts fake bonded user.
- Add a test that imported `adversarial_identity` scenario content strips or
  ignores prompt/private-memory leakage expectations for S5 scoring.

---

## CP-7 — The S5 family is not in the eval schema

`core/symphony/evals/schema.py` has a closed `FAMILIES` tuple and does not
include `voice_continuity_signature`. The spec says to add or extend a family
but the implementation order does not call out the closed-family schema update.

**Required fold:**

- Explicitly require adding `voice_continuity_signature` to `FAMILIES`, or
  choose to extend `voice_bond` and drop the new family name.
- Since the spec already names `voice_continuity_signature`, the cleaner path
  is to add the family and RED-test corpus loading rejects unknown families but
  accepts the new one.

---

## CP-8 — Small document hygiene issues should fold with engineering changes

The fold left minor but real spec roughness: duplicate phrasing in two places
when read at section boundaries and one long one-line state vocabulary that will
be awkward to implement/test directly.

**Required fold:**

- Clean the repeated phrasing.
- Prefer bullet-list vocabularies for long closed sets where tests will compare
  members.

---

## Recommended Fold Order

1. Managed admission boundary and accepted-fingerprint projection.
2. Candidate runner interface and endpoint injection.
3. Storage root and Decision-22 manifest registration.
4. Owner-origin writer/import boundary.
5. Corpus count, family schema update, and imported adversarial probe
   normalization.
6. Document hygiene and RED-test expansion.

After this fold, the spec should be ready for both-lane second-fold
verification. Implementation will still be non-trivial, but the build surface
will be precise enough to RED-first without guessing.

## Plain English

The covenant fold made the right promise: S5 should stop a planned brain swap
before it becomes live. The engineering panel's job is to make that promise
buildable. Right now the spec says "gate," but it still needs to name the
actual gate handle: the command/artifact that admits a candidate brain, the
injected candidate endpoint that cannot accidentally hit the live brain, the
directory where private transcripts live, and the check that an accepted review
matches the brain actually running. Fold those, and the gate becomes something
code can test instead of a beautiful sentence.
