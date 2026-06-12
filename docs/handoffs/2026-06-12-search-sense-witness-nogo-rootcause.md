# Search-as-a-Sense v0.1 — Live Witness NO-GO, Root Causes (for the fix loop)

**Date:** 2026-06-12 ~23:00 | **State:** flag ON, organ live, sense NOT reaching the world.
**Witness:** owner asked 3 current-world questions over Telegram; zero successful web fetches.

## What PASSED live (keep — do not re-litigate)

- Voice: answers in Maez's own words, no result-cards, no permission ceremony.
- Honest absence: "that data isn't in my current evidence" (turn 2), honest
  failure naming (`FRESH_ATTEMPT_FAILED`, turn 3) — no fabricated freshness.
- Progress notice: fired ONLY on the turn where the fanout actually ran
  (true-by-construction proven by its absence on turns 1–2).
- `/receipts`: mechanically correct (returned the retained draft; no web
  sources because no web evidence was admitted).
- Soul reload: witnessed (live soul.md 0 DDG refs, sense anatomy at :50,
  12352→11598 bytes).

## Defect 1 — Layer0 never selects WEB_SEARCH for ordinary current-world questions

**Evidence:** `dispatcher_layer0_emit ... composition_hint=SUBSTRATE_ONLY
external_source_count=0` for both "Hey what is up with openai nowadays?"
(23:00:03) and "What's the latest llama.cpp release?" (23:01:13). Only the
explicit imperative "Search the internet…" (23:02:04) got `FRESH_ONLY`.

**Mechanism (core/dispatcher/layer0.py:214-256):** WEB_SEARCH is selected
only when `_EXPLICIT_FETCH_RE` matches OR archetype class
`B_EXPLICIT_LIVE_FETCH` wins MiniLM scoring. "latest …?" / "nowadays?" /
"what's new with …?" match neither. The plan's assumption that the wing rode
`needs_web_search` (which catches "latest") was wrong — Layer0 has its own,
narrower selector.

**Consequence beyond the miss:** SUBSTRATE_ONLY turns answer *current-world*
questions from stale substrate with no temporal honesty (witness turn 1:
confident present-tense claims about OpenAI from old chatter).

**Fix prescription (deterministic, faculty-graduation-compatible):** add a
current-world predicate arm to Layer0 — question-shaped utterances carrying
freshness markers (latest/nowadays/current/recent/news/what's new/what's
happening/price/release/today) select `WEB_SEARCH`, composed HYBRID
(parallel with substrate, fresh-validates framing) rather than FRESH_ONLY —
these questions benefit from both. Threshold-tuning `B_EXPLICIT_LIVE_FETCH`
alone is not enough (unwitnessable breadth). Tests: each witness utterance
above MUST select WEB_SEARCH; "how are you today?" must NOT (the "today"
trap — require question-shape + freshness marker, not bare keyword).
NOTE: this is still a keyword gate — by canon it stays deterministic until
the intake faculty graduates `search_request`; the faculty shadow is already
measuring this exact gate, and this fix widens it honestly in the interim.

## Defect 2 — the healed body bypasses the egress witness; the wing correctly refuses

**Evidence:** turn 3: `Web search (searxng sense): …` logged (the SearXNG
path RAN, results returned in ~1.19s), then `dispatcher_external_branch …
outcome=error … error_class=UNCLASSIFIED`.

**Mechanism (core/dispatcher/external_sources.py:479-517):** the adapter
requires an egress diagnostic recorded during the fetch
(`_latest_diagnostic_id_after(caller_prefix="skills.web_search.")`); no
diagnostic ⇒ `ERROR/UNCLASSIFIED`. The old DDG path fetched through
`core/egress/external_fetch.fetch_text(...)` which writes the diagnostic;
the v0.1 SearXNG path calls httpx directly — **no egress receipt, so the
wing refused to admit unwitnessed egress as evidence.** The rail worked; the
body skipped the witness layer.

**Fix prescription (covenant-correct, small):** the SearXNG path in
`skills/web_search.py` (or `SearxngBackend`) must fetch through
`external_fetch.fetch_text(fetch_type="web_search", url=<searxng url with
params>, caller="skills.web_search.search.searxng", timeout_s=8)` — the
query egresses to real engines via SearXNG, so the receipt is RIGHT, not
bureaucratic, and the redaction rails come free. Test: a sense-path search
records exactly one diagnostic with the `skills.web_search.` caller prefix
(assert via the same `_latest_diagnostic_id_after` helper the adapter uses);
the adapter integration test goes green end-to-end with a mocked fetch.

## Defect 3 (small) — the fanout query is the verbatim imperative

**Evidence:** the executed query was literally "Search the internet if you
don't have the latest information" — a meta-instruction, not the question.
**Fix prescription:** when `_EXPLICIT_FETCH_RE` triggered the selection,
derive the query from the imperative's object or, when it has none (as
here), from the most recent substantive owner question in chat_history
("What's the latest llama.cpp release?"). Bounded, deterministic, tested.

## Sequencing

Defect 2 first (without the receipt nothing works even when selected), then
1, then 3. All flag-gated under the existing `MAEZ_SEARCH_AS_SENSE_ENABLED`;
flag-off byte-identity tests extend to the touched seams. Lane: Codex builds
/ Claude reviews. Re-witness after merge+restart: the same three questions —
expect notice + fresh answer + one observation row for turns 1-and-2-class
questions, not just explicit imperatives.
