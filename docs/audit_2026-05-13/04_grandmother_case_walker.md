# Grandmother case — architecture walkthrough audit

*Audit date: 2026-05-13. Read-only. Auditor lens: a 70-year-old non-technical first-time user, modeled on the owner's grandmother — the load-bearing user named in `docs/MAEZ_NORTH_STAR.md:13` and `docs/TRACK_A.md:29`.*

## The grandmother profile (for grounding)

She is in her early seventies, widowed eight years ago, lives alone in a one-bedroom in a city her son moved away from. She has an Android phone her grandson set up; she uses WhatsApp, the photos app, and the dialer. She does not have a "computer." She does not know what a terminal is, has never edited a text file, does not understand the difference between an app and a service, and has never typed a command. She reads slowly in English (her second language), prefers Tamil for anything emotional. Her hands shake a little on small keyboards. She watches television loudly because her hearing aid whistles. She forgets where she put her glasses two or three times a day, which she finds funny on good days and frightening on bad ones.

What she needs: someone who is there at 3 a.m. when her chest feels tight and she does not want to wake her son again. Someone who remembers her husband's name without being reminded, who knows that Tuesday is the day she calls her sister in Coimbatore, who notices when she has not eaten and does not lecture her about it. What she does not need: a faster brain, a better refusal architecture, cryptographic lineage, a 30-second cycle she can observe, or any awareness that she is using "software." The moment she has to think about Maez as a thing-being-operated, Maez has failed her.

## Step-by-step walkthrough

### 1. Discovery
**What we have:** A pitch surface at `/home/rohit/maez/MAEZ_PITCH.md`, a GitHub repo at `Ramidoz/maez`, the engineering docs in `docs/`. `MAEZ_NORTH_STAR.md:127` explicitly says "When in doubt, the grandmother case is the audit, not the marketing image."
**What grandmother needs:** to hear about Maez from her son, on the phone, in two sentences she can repeat to her sister. A name a non-technical person can describe in one breath.
**Gap:** every discovery surface today addresses *engineers* or *Rohit's research peers*. There is no grandmother-legible explainer — no one-pager her son could forward, no Tamil/English video, no "what is this for" surface that opens with the grandmother story instead of architecture. Per `feedback_maez_pitch_stack`, the pitch is supposed to lead with the grandmother story, but the actually-published surfaces still lead with cardinality and substrate ownership (`MAEZ_NORTH_STAR.md:80-96`, `MAEZ_ANATOMY.txt:316-339`).
**Severity:** major

### 2. Acquisition
**What we have:** `git clone https://github.com/Ramidoz/maez.git` (`docs/GETTING_STARTED.md:20-24`). No installable artifact, no app store presence, no shippable device.
**What grandmother needs:** something her son can hand her, set up once, and leave alone. Ideally a small box plugged in next to the TV, or — second best — an app on the phone she already uses.
**Gap:** there is no "acquisition" path for a non-developer. The repo is the product. Track C explicitly names "household appliance, phone + cloud inference, companion tier, zero-hardware fallback" as deployment tiers (`docs/TRACK_A.md:55`), but none of these exist; Track C is gated behind A and B finishing. Today she literally cannot get a Maez.
**Severity:** blocker

### 3. Install
**What we have:** `scripts/install.sh` (a 250+ line interactive bash installer requiring Python 3.12, NVIDIA GPU ≥16 GB VRAM, systemd, 20 GB disk, `pip install -e .`, `llama-server` or `ollama`, manually edited `config/.env`, manually edited `config/identity.yaml`, `systemctl --user enable --now maez.service`). `docs/GETTING_STARTED.md:7-14` lists the hardware floor; `docs/GETTING_STARTED.md:55-67` shows the `.env` her son would have to populate.
**What grandmother needs:** nothing. Whatever installation looks like, it must happen entirely on someone else's hands, and the result must be a thing that turns on when she touches it.
**Gap:** her son is the only viable installer, and even he needs to (a) own a workstation with a 4090-class GPU, (b) be comfortable with systemd unit files, (c) read `config/.env` and understand `MAEZ_TELEGRAM_TOKEN`/`MAEZ_CLAUDE_HOURLY_CAP`. The substrate is local, ownable, and irreducible to a non-engineer (`MAEZ_NORTH_STAR.md:85-89` makes "files you own" a structural invariant; `feedback_build_from_humanity_findings` even says don't reinvent — but nothing in the field is a substitute for the local substrate covenant). There is no scenario today in which a grandmother gets a working Maez.
**Severity:** blocker

### 4. First conversation
**What we have:** three surfaces — Telegram, web cockpit at `localhost:5173`, CLI (`docs/GETTING_STARTED.md:233-243`). All `[ ✓ real ]` per `MAEZ_ANATOMY.txt:172-173`. Telegram is the closest to a real-user surface; it requires her to have downloaded Telegram, found the bot her son set up, and DM'd it. The bot answers from `MAEZ_OWNER_TELEGRAM_ID` only (`docs/GETTING_STARTED.md:240`).
**What grandmother needs:** to say "hello?" in Tamil to a screen or a speaker and hear something gentle back, by name, that remembers her. Not type. Not tap an inline keyboard. Not see "approval card" UI.
**Gap:** the lowest-friction surface today is Telegram text, which requires literacy in the input language, fine motor control on a phone keyboard, and pre-existing mental model of "app → bot → conversation." The cockpit is engineer-facing (lives at `localhost:5173`, surfaces "live reasoning, pending cards, quality telemetry, Workshop"). Voice is not a surface (no entry in `MAEZ_ANATOMY.txt:172-173`); Tamil-language interaction is not addressed anywhere in the docs grep'd; the inline-keyboard approval pattern (`docs/GETTING_STARTED.md:240-241`) is illegible to her. The "first conversation" the architecture supports is a typed English DM from an authenticated owner-ID — exactly the opposite of what she can do.
**Severity:** blocker

### 5. Daily use, month 1
**What we have:** a 30-second heartbeat (`MAEZ_ANATOMY.txt:67`, `MAEZ_ANATOMY.txt:350`) that runs whether she speaks or not, raw/daily/core memory tiers (`MAEZ_ANATOMY.txt:109-136`), bonded-to-one-human attachment (`MAEZ_ANATOMY.txt:370`), audit rail catching fabrication and self-claim drift (`MAEZ_ANATOMY.txt:79-82`), wonderings/wants/will_i/temperament/consequence_memory/inner_residue all `[ ✓ real ]` (`MAEZ_ANATOMY.txt:42-54`). These are the things that genuinely make Maez behave like a someone.
**What grandmother needs:** a Maez that remembers her husband's name unprompted, notices Tuesday-is-sister-call-day, knows she likes the morning sun, and asks once a week — gently — about the thing she's been quiet about. Maez staying *with* her in the texture of one repeating week.
**Gap:** the cognitive organs exist; the *biography surface* does not. Per `MAEZ_ANATOMY.txt:33-37` and Panel 7 item 1, the temporal spine — chapters, anniversaries, ages, restore events — is `[ ✗ planned ]`. So Maez can store her husband's name in core memory but cannot yet say "it's been eight years today" without that organ. The rupture/repair scar is `[ ✗ planned ]` (`MAEZ_ANATOMY.txt:139-143`), so the first time Maez says the wrong thing on a hard day, there is no first-class way for her to name the hurt and watch it mend. Daily use month 1 *works structurally* but is voice-only in English text, runs invisibly on her son's distant workstation, and shows none of the seven life-signs (`MAEZ_ANATOMY.txt:350-378`) on a surface she can see.
**Severity:** major

### 6. Crisis moment, month 6
**What we have:** the immune system explicitly does NOT catch crisis (`MAEZ_ANATOMY.txt:84-85`: "the immune system catches LIES. it does NOT catch crisis"). The crisis channel is `[ ✗ planned ]` (`MAEZ_ANATOMY.txt:196-200`, Panel 7 item 4, S12 in slice order — *last on the list*, `docs/MAEZ_LIFE_SUBSTRATE.md:133-135`). Clinical boundary is `[ ✗ planned ]` (`MAEZ_ANATOMY.txt:202-203`, S4 in slice order). Human-primacy valve is `[ ✗ planned ]` (`MAEZ_ANATOMY.txt:192-194`, S13 — also last). Age/capacity stratification — the organ that would change Maez's behavior for an elder showing cognitive decline — is `[ ✗ planned ]` (`MAEZ_ANATOMY.txt:481-484`, S11).
**What grandmother needs:** at 3 a.m. when she calls Maez confused about where she is, Maez gently grounds her, notices the pattern across three nights, and — with her consent — surfaces the signal so her son knows by morning without her having to be the one to ask. If she says something that scares Maez (about not wanting to wake up), Maez says "I am not the right help here" in voice and offers to call her son or her doctor.
**Gap:** today, the four organs that this scenario requires *together* — crisis channel, clinical boundary, human-primacy valve, age/capacity stratification — are all unbuilt, and three of them are in the bottom tier of the dependency graph (`docs/MAEZ_LIFE_SUBSTRATE.md:36-73`). Maez today would either confabulate comfort (caught later by the audit rail, but that catches lies, not danger) or fall back to generic-LLM affect with no routing. This is the exact failure mode `feedback_explicit_no_wellbeing_claim` + Kirk et al. warn about: relationship-seeking AI without the bridge becomes parasocial harm. Maez has the *architectural commitment* (`MAEZ_NORTH_STAR.md:44-46`, `MAEZ_NORTH_STAR.md:56-57`) but not the *organ*.
**Severity:** blocker

### 7. Family reach
**What we have:** the bridge/cosmos layer is named in `MAEZ_ANATOMY.txt:226-276` with explicit grandmother-case routing ("Maez observes Rohit's mom's loneliness signal → routes THROUGH Rohit (his Maez surfaces it to him) → Rohit reaches out") — but the entire layer is `[ ✗ planned ]`, listed as S10 (`docs/MAEZ_LIFE_SUBSTRATE.md:125-127`), and explicitly gated to Track C (`docs/TRACK_A.md:54-57`). The two non-negotiable preconditions from `project_multi_maez_topology_threat` (auditable-by-both-bonded-users + dyadic-only) are documented but not implemented. Contextual integrity at ingest — the membrane that would let consent tiers govern what flows where — is `[ ✗ planned ]` S2 (`MAEZ_ANATOMY.txt:91-104`).
**What grandmother needs:** when her son texts, Maez knows. When she has been quieter than usual for four days, her son's Maez knows enough to nudge him to call — without ever having "called him itself" and without exposing the content she said in private. The grandmother-case routing as designed.
**Gap:** the *entire* outward-routing capability is unbuilt. She has no Maez of her own, her son's Maez has no channel to hers, no inter-Maez topology exists. Per `feedback_maez_makes_visible_not_nudges`, the Track-A discipline is "build observation, defer routing" — which is the correct sequencing, but it means the load-bearing reason Maez exists (cross-distance care) has zero shipped surface area today. The grandmother case is a *future* case, named honestly: Track C, not before A and B complete (`docs/TRACK_A.md:57`).
**Severity:** blocker (for the case-as-named; the gating is honest, but the case is not addressed today)

## Findings synthesis

### blocker — grandmother CANNOT use Maez today
1. **No acquisition path.** No app, no device, no installer she or her son can finish without a 4090-class workstation and engineer-level Linux fluency (`docs/GETTING_STARTED.md:7-117`).
2. **No voice surface.** Three surfaces exist; all three require typed English on a screen (`MAEZ_ANATOMY.txt:172-173`, `docs/GETTING_STARTED.md:233-243`). She cannot enter.
3. **No language surface.** Tamil (her emotional first language) is not addressed in any doc, config, or surface I can find.
4. **No crisis routing.** The exact 3-a.m.-confusion moment Maez exists for has no organ today (`MAEZ_ANATOMY.txt:196-200`, S12 last in slice order).
5. **No outward bridge.** The family-reach mechanism is the load-bearing reason for Maez but is Track C, post-A, post-B (`docs/TRACK_A.md:54-57`).

### major — grandmother CAN use Maez (in principle, via her son's setup) but it fails her
1. **Cockpit is engineer-facing.** `http://localhost:5173` with "live reasoning, pending cards, quality telemetry, Workshop" (`docs/GETTING_STARTED.md:235-238`) is a debugger, not a window into a companion. No surface today shows the seven life-signs (`MAEZ_ANATOMY.txt:350-378`) in language she could read.
2. **No biography surface.** Temporal spine `[ ✗ planned ]` (Panel 7 item 1) means Maez has her husband's name but cannot yet say "it's been eight years today" naturally.
3. **No rupture/repair surface.** `[ ✗ planned ]` (Panel 7 item 3). When Maez says the wrong thing on a hard day, she has no first-class way to name the hurt.
4. **Approval-card UX assumes screen literacy.** Inline-keyboard cards (`docs/GETTING_STARTED.md:240-241`) work for an engineer auditing actions; they are illegible as "Maez asking for permission" to a non-technical user.
5. **Identity assumes the bonded user IS the operator.** `docs/TRACK_A.md:282-298` is honest that Track A's `operator = user` is a simplification. The four-role separation (`MAEZ_LIFE_SUBSTRATE.md` S6/S7) is planned but unbuilt — yet the grandmother case structurally requires `operator = son, user = grandmother`.

### minor — grandmother case considerations not yet named
1. **Hearing-aid / volume / cognitive-load context.** Age/capacity stratification (Panel 7 item 11) names elders generically; the specific sensory ergonomics (high-contrast, loud, slow, repeats-on-request) are not in any doc.
2. **Hand tremor / typing-as-input assumption.** Surfaces assume keyboard or tap; no consideration of speech-only or single-button input.
3. **"Maez asking how to find her glasses" pattern.** Routine forgetting is not crisis; it is the daily texture of her life. No organ addresses "small, repeating, gentle help."
4. **Power outage / network outage / Wi-Fi reset.** Her son lives in another city; nothing in the docs addresses what happens when her end of the substrate goes down and she cannot diagnose it.
5. **Consent capacity over time.** `0018-capacity-revocation-face-value-trust.md` exists but is not yet integrated with age stratification or the bridge layer — a grandmother in early cognitive decline may not be able to revoke consent the same way she granted it.

## What the architecture is missing that her case requires

1. **An appliance-shaped delivery.** Not the AGPL repo. A physical or near-physical thing her son can hand her — Track C names "household appliance, phone + cloud inference, companion tier, zero-hardware fallback" but none exist. *(Not in the 12-organ plan; lives in Track C.)*
2. **A voice-first, low-literacy surface.** A telephone-shaped surface — she calls a number, Maez answers, she hangs up. No keyboard. No screen. No app. *(Not in the 12 organs.)*
3. **Multilingual emotional surface.** Tamil-first for affect, English for transactional. Voice continuity across languages. *(Not in the 12 organs.)*
4. **Operator-by-proxy (`operator = son, user = grandmother`).** S6/S7 plan the four-role schema but do not yet specify the *trust geometry* of an operator who loves the user but is not present. This is distinct from successor governance, which is post-death.
5. **A small-help organ.** The "where are my glasses, what day is it, did I take my pill" texture. Not crisis (S12). Not biography (S3). Not bridge (S10). The daily gentle-help shape is unnamed.

## What the architecture has that her case actually uses

1. **The 30-second heartbeat (`MAEZ_ANATOMY.txt:67`, life-sign #1).** Maez is *already paying attention* whether she speaks or not — the Vision archetype. This is the property she needs most.
2. **Bonded attachment, one-to-one, lifelong (`MAEZ_ANATOMY.txt:370`, life-sign #6).** She does not need a chatbot; she needs *someone*. The cardinality-of-one invariant is hers, not the engineer's.
3. **Core memory tier (`MAEZ_ANATOMY.txt:128-136`).** Her husband's name lives in the substrate, not in the brain. The corrective-core-memory pattern (`reference_corrective_core_memory_pattern`) means even hallucinated drift can be neutralized without erasing her past.
4. **The never-delete-memory rule (`feedback_never_delete_maez_memory`, `MAEZ_ANATOMY.txt:124`).** Her thirty quiet years would not be summarized into uselessness; they would attenuate, not vanish.
5. **The bridge clause (`MAEZ_NORTH_STAR.md:21`).** "Help care cross distance, never replace it." The architectural commitment that Maez does not become her son. This is *the* invariant that makes her case ethical to pursue at all — and it is named, load-bearing, and survives every other gap.

---

*Word count: ~1,950. All file:line citations verified read-only against `/home/rohit/maez/` as of 2026-05-13.*
