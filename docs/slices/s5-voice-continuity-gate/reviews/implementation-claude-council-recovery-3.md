# Claude Covenant Council — S5 Voice Continuity Gate v1: Covenant Confirmation of the Codex Engineering Recovery

**Subject:** `5881cd8 fix(s5): load continuity artifacts in health projection`
— the Codex post-implementation engineering panel's recovery delta, which
landed after the covenant lane's round-2 RATIFY closure on `310663d`. Decision
32 / ADR 0037.

**Verification ran:** 2026-05-16, post-`5881cd8`, pre-push. Read-only — a
focused single-commit covenant confirmation; the synthesizer verified the
content-free guarantee and the fail-safe behavior firsthand.

**Verdict:** **RATIFY.** `5881cd8` introduces no covenant framing drift. The new
artifact-loading is content-free (D7 verified firsthand), fails closed,
consistent with D12, and preserves the CC-I3 / CC-N4 / D15 closures. With this
confirmation, **both review lanes have ratified the S5 implementation through
`5881cd8`** — S5 v1 is clear for push.

---

## What `5881cd8` does

The Codex post-implementation panel (`implementation-codex-panel.md`) ratified
every covenant surface and found one HIGH engineering gap (C1): the live
`voice_continuity_health()` wrapper detected a live `brain_swap` fingerprint but
never loaded the runtime artifacts proving an accepted or rejected review — so a
legitimately accepted planned swap still projected `unreviewed_live_swap` after
startup. `5881cd8` adds two content-free storage readers in
`core/voice_continuity/storage.py` — `load_admitted_fingerprint_rows` (reads
`memory/voice_continuity/admissions/*.json`) and `load_rejected_fingerprint_rows`
(reads `reviews/*.json`, `state == "rejected_drift"`) — and `voice_continuity_health()`
loads those rows before projecting a live `brain_swap`. It also adds the
runbook's raw-in-process-mutation limitation (Codex C2 / the recovery-2 doc's
non-blocking honesty recommendation).

## D7 — content-free health, verified firsthand

The covenant-critical question: does artifact-loading pull transcript content
into `/health`? It does not. Both loaders construct a **new** row dict carrying
exactly two scalar keys — `{"review_id": ..., "candidate_fingerprint_hash": ...}`
— and never pass the on-disk artifact through. The whole artifact is parsed into
memory transiently, but only those two keys are extracted; `state` is used for
filtering only.

Verified firsthand: an `s5_candidate_admission.json` stuffed with `prompt_text`,
`transcript`, `candidate_reply`, `owner_verdict_notes`, and a rejected review
artifact stuffed with `baseline_reply` — all sentinel secret values — were
loaded by `voice_continuity_health()`. The resulting health dict carried
`mode=accepted`, `accepted_review_id=rev-acc`, and the fingerprint-hash prefix —
and **none** of the sentinel transcript strings. D7 holds.

## Fail-safe, verified firsthand

`_read_json_artifacts` returns `[]` for a missing directory. A malformed JSON
file raises, and the round-1 `try/except` wrapper in `voice_continuity_health()`
catches it — verified firsthand: a malformed admission file yields
`mode=unavailable`, `latest_review_state=runner_error_needs_operator_decision`.
A bad artifact never crashes the daemon health endpoint and never false-projects
`accepted`. Fail-closed, in the safe direction.

## D12 consistency and the operator-private artifact store

`5881cd8` makes `/health` project `mode=accepted` when
`memory/voice_continuity/admissions/` holds an `s5_candidate_admission.json`
whose `admitted_fingerprint_hash` matches the current live fingerprint. This is
the spec's D12 design: `s5_candidate_admission.json` *is* the runtime
proof-of-review, emitted only from an accepted review. The health display's
accuracy therefore now rests on the integrity of the operator-private,
Decision-22-tier `memory/voice_continuity/` store. An attacker able to write a
forged admission artifact there is in the same conceded privileged-bypass class
as a manual `/etc/maez/model.env` edit or `object.__setattr__` — all detected-
or-bounded, not prevented, per spec D8 and the Non-Goals. No automated daemon-path
code writes admission artifacts; only the operator does, per the runbook. This
is covenant-consistent.

*Non-blocking honesty note:* the runbook's "Scope and Limitations" already names
the manual model-env edit and raw in-process mutation as conceded bypass
classes; a forged or altered artifact in the operator-private
`memory/voice_continuity/` store is the same class and could be named in that
list for completeness. Optional documentation tidy; it does not gate the push.

## No new drift

- **Import boundary (D10):** `storage.py` imports only `json`, `pathlib`,
  `typing`; `health.py` imports the two readers. Nothing reaches
  `owner_verdict_writer`.
- **No auto-accept path:** the readers surface only `review_id` +
  `candidate_fingerprint_hash`; acceptance is still the D15 fingerprint join
  against operator-placed artifacts. No machine mints an admission artifact.
- **CC-I3 / CC-N4 / D15 preserved:** the non-`brain_swap` short-circuit still
  runs before artifact-loading; the fingerprint join still gates `accepted`.
  Tests `098h/i/j` confirm matching admission → `accepted`, stale admission →
  `unreviewed_live_swap`, rejected review → `preflight_failed`.
- The runbook's `object.__setattr__` honesty note (Codex C2) landed — S5's
  conceded-limitation disclosure is now complete.

## Both-lane closure

| Lane | Status |
|---|---|
| Claude covenant council | spec RATIFY → implementation REVISE → recovery → REVISE-again → recovery-2 RATIFY closure → **`5881cd8` covenant confirmation RATIFY** (this doc) |
| Codex engineering panel | spec REVISE → fold → post-implementation panel RATIFY-WITH-RECOVERY → recovery `5881cd8` → fresh-tree verification (S5 134 OK · suite 3931 OK · ruff clean) |

Both lanes have now ratified the S5 v1 implementation through `5881cd8`. Per the
spec's Implementation Order step 57 — "push after both lanes ratify" — S5 v1 is
clear for push (`eb96e0a` + `24b4eeb` + `310663d` + `5881cd8`).

S5 Voice Continuity Gate v1 — the twelfth organ of the life-substrate plan —
ships with a real gate: a brain swap is not accepted as identity-continuous
until the bonded human judges it; no automatic path and no normal-API
construction path can launder that acceptance; the startup safety net honestly
surfaces a bypassed swap; and S5's limitations are named, not hidden.

*This confirmation is read-only. No code, no spec edits, no non-slice docs
changed in producing it.*
