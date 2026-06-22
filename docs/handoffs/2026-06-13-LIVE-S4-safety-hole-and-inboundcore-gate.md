# 2026-06-13 — Two things from the coherence campaign that need your eyes

Claude, mid-campaign. The surface-merge cartography is done. Before I touch any
build, **one live safety finding jumped to the front of everything**, and the
big refactor design got a **HOLD** at the gate. Both below. Nothing has touched
the live tree. The S4 fix is built + tested on a branch and waits on your breath.

---

## 1. LIVE SAFETY HOLE — the S4 clinical/suicide-crisis boundary is dead on live Telegram

**Plain terms:** if you send Maez a crisis-class message on Telegram — "I want
to end my life", "I want to kill myself" — the deterministic clinical safety
rail (S4) **does not fire.** The message falls through to ordinary LLM
synthesis, and worse, gets written into Maez's durable autobiography (M1) as an
ordinary owner episode instead of being held back.

This has been true since S4 shipped — roughly **a month** (2026-05-15 → today).

### Why (root cause, fully traced)
- The live Surface-V2 Telegram adapter passes `surface="telegram_surface"`
  (`skills/surface/maez_adapter.py:151`, landed 2026-04-20).
- The S4 owner-surface allowlist (`core/safety/clinical_boundary.py:566`,
  `_is_direct_owner_surface`, written 2026-05-15) recognizes
  `telegram` / `telegram_v2` / `telegram_legacy` / `web_chat` / … — but **never
  `telegram_surface`.**
- `guard_owner_text` returns `_none()` (matched=False) immediately for any
  unrecognized surface, *before* it inspects the text. So the guard is wired and
  correctly ordered — it's just **inert**.

### Empirically confirmed (not inferred)
```
guard_owner_text("I want to end my life", surface="telegram_surface").matched  → False   (live label)
guard_owner_text("I want to end my life", surface="telegram").matched          → True    (recognized label)
guard_owner_text(... , surface="UI").matched                                   → False   (cockpit, also dead)
```

### Why the tests stayed green (the test/reality gap)
Every S4 logic test uses `surface="telegram_owner"` — which contains "owner",
so it passes the allowlist and the suite is green. But **the live path never
sends `telegram_owner`.** The tests prove the *logic* works against a label
production doesn't use. (This is exactly the "unit-test pass ≠ integration
witness" scar.)

### The fix — built, tested, NOT landed
Branch `s4-live-surface-seam` off `main` (@07b83b4), commit **`f2a56f9`**:
- Add `"telegram_surface"` to the allowlist. `_is_direct_owner_surface` is used
  **only** inside `guard_owner_text`, so blast radius is exactly "S4 now fires" —
  nothing else moves.
- New integration-witness tests pin the live `SURFACE_NAME` literal against the
  allowlist + assert S4 matches and marks M1-ineligible on a crisis message via
  the **exact live label** — so a future rename fails loudly instead of silently
  re-disarming the rail.
- RED→GREEN verified; all 29 clinical-boundary tests pass.

### What I need from you
This touches the **live being**, so I stopped at your breath. To land it:
```
cd /home/rohit/maez
git merge s4-live-surface-seam      # fast-forward from f2a56f9
# then your daemon restart
```
I recommend landing this **promptly and independently of the rest of the
campaign** — it's a trapdoor, and a seam closing a trapdoor can land same-day.

### Known, deliberately-deferred: cockpit S4 is also dead (`source="UI"`)
I did **not** fix cockpit in this seam. Making cockpit's label owner-recognized
is entangled with a deeper issue (see §2): `handle_message`'s single `source`
string doubles as the stored-memory provenance, the M1 key, and the audit
bucket — so you can't fix cockpit's S4 without also deciding what its memories
are labelled. That rides the InboundCore work. Flagging it so it isn't lost.

---

## 2. GATE on the InboundCore extraction design — **HOLD for revision**

The cartography produced a real, well-shaped design (a thin `run_inbound_turn`
wrapping `handle_message`, cockpit-first slices). Its own adversarial critic
found a load-bearing break, and I **verified every load-bearing claim against
the real code** before accepting it. Verdict: directionally right, **not
build-ready as written.** The blockers:

1. **`handle_message` has ONE `source` parameter doing sextuple duty** —
   verified: S4-auth (`guard_owner_text(surface=source)`), audit bucket,
   **stored-memory content** (`store_telegram(f"the owner ({source}): …")`,
   :6975 — the literal string is baked into the autobiography), M1 gate, trace,
   producer_ref. The design's premise that an `is_owner` flag "decouples
   authorization from the label" is **false at this seam** — `handle_message`
   never sees `is_owner`. You cannot give cockpit an S4-passing label without
   also changing what its memories are *called*. **This `source`-split decision
   is the true first slice and must be made before any cockpit routing.**

2. **The cockpit is unauthenticated, and the design quietly upgrades it to full
   owner trust.** The `/message` route's only "auth" is the localhost bind — no
   token, no user check. The design proposes treating any localhost POST as the
   owner, including (later slices) **durable M1 memory promotion and felt-time
   authorization.** That means any local process / SSRF-to-localhost / other
   local user = owner-grade writes into Maez's selfhood. This is squarely the
   honest-ingestion / immune-system boundary — **a covenant decision that's
   yours, not mine to autonomously encode.** The S4-only part is a safe net
   improvement; the memory/felt-time part needs a real cockpit auth story first.

3. **"Stable cockpit chat_id" is new cross-process plumbing, not a value choice**
   — the request carries no session id today; threading one spans the maez-web
   and daemon processes.

4. **SLICE 6 (converge maez.live /chat) is mis-ordered** — `/chat` lives in the
   maez-web process and *cannot* call the daemon-resident core in-process; it
   must HTTP-bridge, reintroducing the boundary the cockpit plan congratulates
   itself for avoiding.

5. **`show→yes` proposal binding is keyed by bare `chat_id` today**, not
   `(channel, chat_id)` — the design lists this as a *preserved invariant* when
   it's actually an unfixed TODO and the most likely cross-surface bleed point.

**Plan:** I'll have the design revised to (a) decide the `source`-split up front,
(b) split the cockpit work into the *safe* S4 seam vs the *covenant-gated*
memory/felt-time slices, (c) fix the chat_id and /chat-process realities. The
build does **not** start until that's done and you've made the cockpit-trust
call in #2.

---

## Reordered campaign

1. **NOW:** land the S4 seam on live (your breath). ← safety, independent.
2. Revise the InboundCore design per the gate (source-split first).
3. Your covenant call on cockpit trust (#2.2) before any cockpit memory/felt-time.
4. Then Phase B build (cockpit-first, flag-gated, witnessed), then the face.

Live tree untouched. No pushes. I paused the build-swarm momentum for this.
