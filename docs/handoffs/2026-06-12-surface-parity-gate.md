# Surface Parity Restoration v0 - STOP-at-gate handoff

Status: built, verified, default-off, stopped before merge/restart/witness.

Branch: `surface-parity-restoration-v0`
Implementation tip before this handoff: `ccadc39`

## What changed

The three confirmed Surface V2 orphans from
`docs/SURFACE_PARITY_MAP_2026-06-12.md` are now wired into the live inbound
handler behind one strict flag, `MAEZ_SURFACE_PARITY_ENABLED`.

- O1 Proposal approvals: `skills/surface/maez_adapter.py` now handles bounded
  owner approval/show/reject phrases after open cards and before search
  commitment, using `core.dispatcher.proposal_resolver` for shared parsing and
  the existing evolution/dream engines for actions.
- O2 Felt-time: Surface V2 now passes the same
  `SubjectiveDurationOwnerAuth(surface="telegram_owner",
  proof="telegram_authorized_user")` shape that legacy Telegram used into
  `daemon.handle_message`.
- O2b Capability card: the felt-time entry is no longer an unconditional static
  tuple. Flag off returns the exact old `built, not yet attached` string; flag
  on reports `attached`; probe failure reports `unknown (probe error)`.
- O3 D20 gap detection: Surface V2 schedules
  `maybe_fire_capability_proposal` after S4/auth and before every interceptor,
  passing the live `pipe.card_store`. No manual card send exists.
- R4 Loudness guard: `skills/telegram_voice.py` now carries an OUTBOUND-ONLY
  banner and a one-shot warning if `_handle_message` is invoked.
- Build Ledger: `docs/MAEZ_BUILD_LEDGER.md` created and updated; O1/O2/O3 moved
  from `BUILT_ORPHANED` to `BUILT_ASLEEP`.

## Task 0 proofs

### 0a Live handler seam

Verified in `skills/surface/maez_adapter.py`:

- S4/owner guard at `guard_owner_text(...)` before any restoration.
- Open-card block uses `pipe.card_store.get_open_for_channel(...)` and remains
  the first early-return approval surface.
- Search commitment call remains later than proposal approvals.
- `daemon.handle_message(...)` is the synthesis call that receives
  `subjective_duration_owner_auth`.

Placement now:

1. S4/auth and setup.
2. D20 gap detection enqueue.
3. Intake shadow.
4. Open-card handler.
5. Proposal approvals.
6. Search commitment.
7. Brain/synthesis path.

### 0b Resolver decision

Chosen path: shared parser/binder, adapter-side engine reuse.

New module: `core/dispatcher/proposal_resolver.py`

- `detect_proposal_intent(text) -> (action, explicit_id)`
- `resolve_proposal_target(...) -> target_id | None`

`telegram_voice._detect_proposal_intent` delegates to the shared detector, so
the phrase parser is no longer forked. The target-resolution machinery is used
by Surface V2, where the live adapter can check both evolution and dream stores
before acting.

Justification: extracting the entire legacy async reply/action body would have
dragged `telegram.Update`, `_reply_text`, and legacy instance state into the new
surface. The safe anti-drift seam is the parser and target binding; action
execution remains per-surface while calling the same engines. Surface V2 also
repairs a legacy ordering trap: explicit dream proposal ids are checked against
the dream store before falling through, instead of being masked by the
evolution queue.

### 0c Felt-time auth

Verified legacy constructor:

```python
SubjectiveDurationOwnerAuth(
    surface="telegram_owner",
    proof="telegram_authorized_user",
)
```

Surface V2 now constructs that exact shape when the strict parity flag is on.

### 0d D20 contract

Verified `core/infra/capability_gap_detector.py:maybe_fire_capability_proposal`:

- accepts `pending_card_store`, `chat_id`, `user_id`;
- catches its own exceptions and returns a summary dict;
- creates cards through the supplied pending-card store/orchestrator path.

Surface V2 passes `pipe.card_store` and does not send any card message itself.

## Review anchors

- Off means off: `MAEZ_SURFACE_PARITY_ENABLED` is strict parsed. Unset, `0`,
  `false`, `no`, and `off` are all off.
- Flag-off byte identity:
  - no D20 call;
  - no proposal interception;
  - no subjective-duration auth;
  - capability card preserves exact `felt time: built, not yet attached`.
- R3 placement: D20 source-order is after auth and before `get_open_for_channel`.
- R3 visibility: no `_send_intermediate`, no manual card send; only
  `pending_card_store`.
- R1 precedence: open cards beat proposal phrases; proposal approvals beat
  search commitment.
- R1 safety: bare `yes` with no explicit target or recent last-shown proposal
  falls through to chat.
- R1 engine reuse: evolution actions call `skills.evolution_engine`;
  dream actions call `daemon.dream`; no duplicate stores.
- Ledger rows updated: O1/O2/O3 and related hazard rows updated in
  `docs/MAEZ_BUILD_LEDGER.md`.

## Verification

Focused tests:

```text
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_parity_flag tests.test_telegram_voice_loudness \
  tests.test_surface_parity_d20 tests.test_surface_parity_felttime \
  tests.test_capability_card tests.test_proposal_resolver \
  tests.test_surface_parity_proposals tests.test_surface_adapter \
  tests.test_evidence_state -v
```

Result: `Ran 67 tests ... OK`

Lint:

```text
/home/rohit/maez/.venv/bin/python -m ruff check \
  core/cognition/parity_flag.py core/cognition/capability_card.py \
  core/dispatcher/proposal_resolver.py skills/surface/maez_adapter.py \
  skills/telegram_voice.py tests/test_parity_flag.py \
  tests/test_telegram_voice_loudness.py tests/test_surface_parity_d20.py \
  tests/test_surface_parity_felttime.py tests/test_proposal_resolver.py \
  tests/test_surface_parity_proposals.py tests/test_capability_card.py
```

Result: `All checks passed!`

Note: the fake daemon tests log grounding-judge timeout/circuit messages when
the local judge endpoint is unavailable. The tests still pass; this is existing
test-environment noise, not a parity failure.

## Owner witness after review

Do not merge/restart/flip in this branch. Owner breaths:

1. Merge locally to main, no push.
2. Restart `maez.service`.
3. Set `MAEZ_SURFACE_PARITY_ENABLED=1` and restart.
4. O1 witness: have one pending evolution or dream proposal, then approve it
   by voice on Telegram (`yes` after `show #N`, or `approve #N`). Expected:
   Surface V2 applies/rejects/shows through the real engine instead of general
   chat. Open approval cards still win over proposal phrases.
5. O2 witness: ask "Are you able to feel time?" Expected: the live prompt card
   says felt time is attached, and the daemon records owner contact through
   `SubjectiveDuration`.
6. O3 witness: send one crafted capability-gap turn. Expected: the call-site
   fires through the pending-card path if the detector threshold/cooldown
   allows it; if no proposal fires, report the detector result honestly, do not
   force a card.
7. Flag-off spot check: with flag unset or `0`, proposal phrases fall through,
   no D20 call runs, no subjective-duration auth is passed, and the capability
   card renders the exact old felt-time string.
