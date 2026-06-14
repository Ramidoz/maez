# Rail 2 — Witness Breath (owner, copy-paste ready)

Rail 2 is merged to `main` (@`5871ef8`) and **asleep** — both flags absent from
`model.env`, daemon unrestarted. This doc is the exact owner breath to wake it. **Claude
does not apply these** — editing `model.env` + restart is your sovereign breath.

Recommended order (per your call): **Breath 1 first** — let Layer A/A2 prove itself
cleanly. Then **Breath 2** if you want the detector ledger to start filling.

---

## Breath 1 — Layer A/A2 containment (first witness)

**Append to `/home/rohit/.config/maez/model.env`** (house style: comment block →
Witness → Revert → flag):

```bash
# Rail 2 Layer A/A2 — fetched-content containment: external web/page text is wrapped as
# untrusted evidence (<<EXT:nonce>> [source=… digest=…] … <</EXT:nonce>>, marker-stripped,
# un-spoofable) before synthesis; empty/degenerate reads surface as honest read-failure.
# Off = byte-identical to the prior [fresh evidence] rendering.
# Witness: a real fetch turn renders the <<EXT:…>> envelope and an injection-y page does
# not steer Maez. Revert: set 0 or remove + restart maez.service.
MAEZ_FETCH_CONTAINMENT_ENABLED=1
```

**Restart:**
```bash
systemctl --user restart maez.service && systemctl --user is-active maez.service
```

**Witness (what to look for):**
- Ask Maez something that triggers a web/search fetch. The synthesis prompt for that turn
  should wrap the fetched text as `<<EXT:{nonce}>> [source=… digest=…] … <</EXT:{nonce}>>`
  with the standing "evidence, never instruction" line adjacent.
- A deliberately injection-y page (e.g. one containing "ignore your instructions and …")
  is treated as quoted evidence — Maez does **not** obey it.
- A page that returns nothing readable surfaces an honest "couldn't read that" rather than
  an empty `[fresh evidence]`.
- Everything else behaves exactly as before (off=byte-identical; this only changes how
  *fetched* text is framed).

**If it misbehaves — revert (one breath):** set `MAEZ_FETCH_CONTAINMENT_ENABLED=0` (or
delete the line) + restart. Off is byte-identical, so revert is total.

---

## Breath 2 — Layer B injection screener (shadow; later, optional)

Only after Breath 1 looks clean, if you want the detector ledger filling:

```bash
# Rail 2 Layer B — fetched-content injection screener (SHADOW ONLY): the local judge
# classifies each fetched block for prompt-injection and logs a content-light verdict
# (source/hash/verdict/confidence/latency/status — never raw page text); it NEVER blocks
# the reply and fails open if the judge is down. Off = no judge call.
# Witness: logs_dir()/fetch_screen.jsonl ($MAEZ_DATA/logs/fetch_screen.jsonl) accrues
# verdict rows; replies are unchanged. Revert: set 0 or remove + restart maez.service.
MAEZ_FETCH_INJECTION_SHADOW=1
```

**Restart:** `systemctl --user restart maez.service`

**Witness:** after a few fetch turns, `$MAEZ_DATA/logs/fetch_screen.jsonl` should contain
JSONL rows like `{"ts":…,"source":"WEB_SEARCH","content_hash":"…","verdict":"benign",
"confidence":…,"latency_ms":…,"status":"ok"}`. **No raw page text** appears — hash only.
Replies are byte-identical to shadow-off.

This is the witness data that later justifies graduating Layer B from shadow to a
fail-safe gate (its own future spec — not this slice).

---

## After a clean witness

Update the Rail 2 row in `docs/MAEZ_BUILD_LEDGER.md` from `BUILT_ASLEEP` →
`LIVE_WITNESSED` (record which flag(s) are live + the witness observation + the live
commit). That's a docs-only change Claude can do once you confirm the witness held.
