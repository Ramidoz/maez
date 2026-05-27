# Claude External-Source Pass 1 — Locke (Egress Authority)

**Verdict:** BLOCKING

## Summary

The brief correctly cites the three existing egress surfaces (`external_fetch.fetch_text`, `skills.web_search`, `action_engine._do_fetch_url`) and correctly defers FRONTIER_CONSULT. But it has two blocking egress-authority problems and one verification gap: (1) the LIVE_REDDIT path under-specifies which `fetch_type` registry entry it uses, leaving the door open to either inheriting `fetch_url`'s `would_block_unknown_url_fetch` decision or, worse, accidentally calling `skills/reddit_skill.py` which already bypasses `external_fetch` with raw `requests.get()`; (2) ARXIV_OR_PAPERCLIP claims "the Paperclip CLI exists as the canonical local paper-search tool" but no `paperclip` binary or Python wrapper exists in this repo (only `.agents/skills/paperclip/SKILL.md`, a Markdown skill spec). These must be tightened before implementation.

## Findings

### Finding 1 — LIVE_REDDIT egress route is ambiguous and risks bypass

**Severity:** BLOCKING
**Where:** brief lines 174-185 (§5 LIVE_REDDIT); cross-checked against `core/egress/external_fetch.py:128-155` (registered `fetch_type` set) and `skills/reddit_skill.py:80-116`

**Observation:** The brief says LIVE_REDDIT "may use the existing external-fetch boundary with a public Reddit JSON URL." Two concrete problems:

1. `external_fetch.build_fetch_registry()` only registers `web_search`, `search_rss`, `fetch_url`, `currency_lookup`, `stock_lookup`. A Reddit JSON URL routed through `fetch_text(fetch_type="fetch_url")` is classified `UNKNOWN_URL_FETCH`, returns `decision="would_block"` with reason code `would_block_unknown_url_fetch`. That's substrate-shadow (ok=True today) but the decision string already says "would_block" — the dispatcher would be consuming text that the egress layer is on record as wanting to block. The brief does not address this. If LIVE_REDDIT is canonical, it should either (a) be a NEW registered `fetch_type` with `threat_model_class=PUBLIC_LOOKUP` and `result_origin_class=tool_result_public`, or (b) explicitly inherit `fetch_url`'s "would_block" posture and acknowledge that in `availability_limitations`.
2. There is an existing `skills/reddit_skill.py` that uses raw `requests.get("https://www.reddit.com/r/<sub>/hot.json", ...)` (lines 87-88) — it does NOT route through `external_fetch`. That surface already exists as a smuggling path. The brief must explicitly forbid `core/dispatcher/external_sources.py` from calling `reddit_skill` (or any other path) and require the route to be `external_fetch.fetch_text(...)` only. Without that explicit prohibition, the next implementor will reach for `RedditSkill._fetch_subreddit` because it "already works" and the boundary is silently undone.

**Recommendation:**
- Decide explicitly: either register a new `fetch_type="live_reddit"` (threat_model_class `PUBLIC_LOOKUP`, result_origin_class `tool_result_public`) in `build_fetch_registry()`, OR reuse `fetch_url` and document in §5 that the decision will be `would_block` (substrate_shadow) with a TODO to promote to a public lookup class. Either is defensible; the silence is not.
- Add a hard-line non-goal in §10: "Do not call `skills.reddit_skill.RedditSkill` or any other path that does not route through `core.egress.external_fetch.fetch_text`." Plus a unit/integration test that asserts the LIVE_REDDIT adapter calls `fetch_text` exactly once per branch and never imports `reddit_skill` or `requests`.

### Finding 2 — Paperclip CLI is claimed to exist but is unverifiable in-repo

**Severity:** BLOCKING
**Where:** brief lines 64 ("The Paperclip CLI exists as the canonical local paper-search tool"), 196-200 (§5 ARXIV_OR_PAPERCLIP)

**Observation:** Searched the repo: `which paperclip` returns nothing; the only thing matching `paperclip*` is `/home/rohit/maez/.agents/skills/paperclip/SKILL.md` — a Markdown skill specification, not an executable. `grep -rn "paperclip"` across `core/` and `skills/` returns zero hits. The brief asserts "Use the local `paperclip` CLI" with a 3s budget and CLI-nonzero failure mapping, but there is no evidence such a CLI is installed on the surface the dispatcher will run on.

If this turns out to be a shell command provided by a sibling agent's PATH (likely `.agents/skills/paperclip/`), that route is not bounded by Maez's egress layer at all — it can hit PMC/bioRxiv/medRxiv/arXiv with whatever its own credential discipline is. Routing dispatcher external-source consumption through an unaudited binary undoes the entire point of the central egress boundary.

**Recommendation:**
- Before the slice lands: either (a) point to a concrete, in-repo, observable invocation surface for `paperclip` (path, signature, audited network discipline), or (b) reduce ARXIV_OR_PAPERCLIP v1 to arXiv-via-`fetch_text(fetch_type="fetch_url")` against a known stable arXiv API URL, with paperclip explicitly deferred and marked `RESERVED_UNAVAILABLE` alongside FRONTIER_CONSULT.
- If paperclip is going to be the path, add a non-goal: "paperclip CLI invocation must record diagnostics equivalent to `external_fetch_diagnostics.jsonl` (HMAC digests of query and response) — no out-of-band egress."

### Finding 3 — RED test #7 under-specifies which diagnostic keys must be present

**Severity:** SUGGEST
**Where:** brief lines 304-306 (RED test #7); cross-checked against `external_fetch.py:208-228` (the `_write_diagnostic` row shape)

**Observation:** The test description says "write the existing `external_fetch_diagnostics.jsonl` diagnostic fields with HMAC digests." The actual schema (schema_version `external-fetch-diagnostic-v1`) has load-bearing keys: `request_id`, `caller`, `fetch_type`, `threat_model_class`, `result_origin_class`, `decision`, `reason_codes`, `destination_host_digest`, `url_digest`, `query_digest`, `response_digest`, `status_code`, `preflight_status`, `preflight_refusal_kind`. A test that asserts "fields with HMAC digests" without naming them can pass on a single digest while the others silently disappear under a refactor.

**Recommendation:** Tighten test #7 to assert specific keys exist and that all four `*_digest` keys are `hmac-sha256:`-prefixed, and that `caller` is a non-empty string identifying the dispatcher external-sources module (e.g., `caller="dispatcher.external_sources.web_search"`). The `caller` field is the only handle a future audit has for "who reached for egress" — it must not be the empty string or `"unknown"`.

### Finding 4 — Credentials/cookies/sessions discipline is sharp; one tighten suggested

**Severity:** SUGGEST
**Where:** brief lines 177-178

**Observation:** §5 says "no credentials, no cookies, no browser session" for LIVE_REDDIT. The phrasing is good but is a policy claim on the dispatcher side. The actual enforcement lives in `external_fetch._request_headers()` (lines 356-364), which already strips `authorization`, `cookie`, `proxy-authorization`, `user-agent`, `accept-language`, and `x-forwarded-*`. As long as LIVE_REDDIT goes through `fetch_text`, credentials cannot be smuggled in headers — this is mechanically enforced.

However, the brief does not forbid query-string credentials. A future "small change" that appends `?api_token=...` to a Reddit URL would not be caught by `FORBIDDEN_REQUEST_HEADERS`. Preflight refuses `parsed.username`/`parsed.password` (URL userinfo) but not arbitrary query params.

**Recommendation:** Add to §5 LIVE_REDDIT and §10 non-goals: "no authentication query parameters (e.g., `?api_token=`, `?api_key=`, `?access_token=`); the URL composed by the adapter must be a public path with no credential-bearing query strings." Optionally, add a test that asserts the composed Reddit URL has no `api_token`/`api_key`/`access_token`/`bearer`/`session` substring.

### Finding 5 — §6 "raw exception text at debug level only if it contains no raw owner-private content" is unenforced

**Severity:** SUGGEST
**Where:** brief lines 226-228

**Observation:** The sentence is correct in intent but is a wish, not a mechanism. There is no classifier in `core/` for "raw owner-private content," and any blanket `logger.debug(str(exc))` from a fetch failure can pull in owner-private substrate context if the exception happens to wrap it (e.g., a redacted-URL error message that includes path components). The brief should either (a) name the mechanism that filters owner-private content from exception text, or (b) take the safer cut: never log raw exception text — log only the exception class name and a closed reason code.

**Recommendation:** Replace the sentence with: "Adapter exception handlers MUST log only the exception class name plus the closed taxonomy reason code (e.g., `SOURCE_TIMEOUT`, `FRESH_ATTEMPT_FAILED`). Raw exception text MUST NOT reach any logger." This is mechanically enforceable in code review (grep for `logger.*(str(exc)|repr(exc)|f"{exc}")` in the new module).

### Finding 6 — FETCH_URL "two URLs per reply" cap should be enforced at the module boundary

**Severity:** NIT
**Where:** brief lines 188-194 (§5 FETCH_URL)

**Observation:** The two-URLs-per-reply limit is stated as a policy. Worth making it an assertion in the module contract (§4) — e.g., `FETCH_URL` adapter raises `ValueError` if asked for >2 URLs from a single spec — so a misshapen `CompositionSpec` cannot quietly fan out 50 URL fetches. The cap is part of the egress boundary, not a downstream concern.

**Recommendation:** Add a sentence to §4 module contract or §5 FETCH_URL: "If the spec presents more than 2 URLs for FETCH_URL, the adapter executes the first 2 in spec order and emits `FRESH_ATTEMPT_FAILED` with limitation `EXCESSIVE_URL_REQUEST` for the remainder." Or refuse the whole branch.

## What the brief gets right

- §2 "Code Evidence" is accurate. Verified:
  - `skills/web_search.py:55, 115, 213` calls `external_fetch.fetch_text` with `fetch_type="web_search"` and `"search_rss"`.
  - `core/actions/action_engine.py:1600` calls `external_fetch.fetch_text(fetch_type="fetch_url")`.
  - `external_fetch.py:200-232` writes HMAC-digested diagnostics rows.
- Option A vs B vs C reasoning correctly identifies that Option B re-tangles orchestration and Option C is falsified by the daemon witness.
- FRONTIER_CONSULT is correctly reserved (§5, §10) — no model or subscription proxy call. Test #4 is the right anchor.
- Failure taxonomy in §6 is closed and uses the existing `AvailabilityLimitation` vocabulary; no free-form reasons reach prompt or audit.
- §7 explicitly requires reconstructed `CompositionSpec` to pass normal validation before rendering — that's the right way to keep failure paths honest.
- §8 concurrency note (Layer 1 substrate fan-out and external fan-out run concurrently from the same sealed spec) preserves the seal-by-generation-id discipline.
- §10 non-goals correctly forbid frontier consultation, credentials/browser automation, LLM-invented URLs, and flipping the dispatcher default flag.

## Open questions for synthesis

- Out-of-lens but related: the brief assumes Layer 0 will emit `LIVE_REDDIT` once a narrow selector update lands (§5, line 184). The selector and the consumer are co-dependent — if the selector lands without the consumer ready, `LIVE_REDDIT` specs would fall through to JARVIS again. Sequence of landings matters; defer to Huygens / engineering for ordering.
- Out-of-lens: §7 hybrid-reconstruction path ("reconstruct a valid `CompositionSpec` with `availability_limitations`") — synthesis should check whether reconstructing a spec downstream is consistent with seal discipline elsewhere in ADR 0047, or if it should instead annotate the original sealed spec with a limitations side-channel.
- Out-of-lens: the brief notes JARVIS remains the disabled-flag fallback (§3 decision, §8 last paragraph). Confirm with engineering that there is no surface where dispatcher-enabled + dispatcher-empty-transcript still falls through to JARVIS for `external_sources` — that would be the exact silent bypass this slice is designed to close.
