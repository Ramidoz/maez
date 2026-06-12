# Page-Read Sense v0 — Design (the reading limb)

**Date:** 2026-06-12
**Status:** Spec for owner review. Cross-lane: Claude designed → owner approved with
three sharpenings (all baked in below as load-bearing, both mechanisms verified
against the tree) → ready for the implementation plan.
**Lane:** Codex builds / Claude reviews (covenant axis: egress + evidence + memory-write).
**Canon:** docs/SENSES_NOT_SERVICES.md staged shape — the DOM/text lane precursor.
Plain HTTP fetch+extract. NO browser, NO JS rendering, NO vision.

## The witnessed need (2026-06-11, verbatim)

Maez searched llama.cpp releases, held the GitHub releases URL, the snippet
truncated the version number, and Maez honestly said *"We might need to check the
full GitHub page directly"* — because Maez cannot read a page. Search returns
snippets; there is no fetch-the-page-and-read-it sense.

## The decisive discovery (verified)

**`ExternalSource.FETCH_URL` already exists, fully railed, and dormant:**
- Adapter built and registered (`external_sources.py:678`, `_DEFAULT_ADAPTERS:715`):
  fetches through the egress-witnessed `external_fetch.fetch_text(fetch_type=
  "fetch_url", caller="core.dispatcher.external_sources.fetch_url", timeout_s=5.0)`.
- Covenant preflights already built (:373-400): owner-URL extraction
  (`_extract_urls`), **`MODEL_INVENTED_URL` refusal** (a model-suggested URL with
  no owner-named URL is PREFLIGHT_BLOCKED — the owner-only trigger philosophy is
  already enforced in code), `_has_sensitive_query` refusal, subject-boundary
  predicate, and `external_fetch`'s standing guards (scheme allowlist http/https,
  private/loopback IP refusal, `max_bytes`, redirect handling).

**What's missing — exactly three things:**
1. **No nerve:** Layer0 never selects FETCH_URL (no arm exists).
2. **No digestion:** `_payload_from_fetch_result` passes RAW `result.text` (HTML)
   capped at `MAX_FRESH_CHARS_PER_SOURCE=2000` — a fetch today injects `<head>`
   boilerplate as "evidence."
3. **No admission path:** `fetch_url` is registered
   `result_origin_class="unclassified"` (`external_fetch.py:151-153`) and the
   intake bus refuses `unclassified` (`admit.py:24`) — a page-read observation
   would be **born refused** without the reclassification rule below.

## Owner decisions (locked)

1. **Own flag:** `MAEZ_PAGE_READ_ENABLED`, default-OFF, byte-identical off.
   Independent witness, independent revert from the search sense.
2. **Same stomach:** page-reads feed the world-observation lane — one bounded
   `external_web`/`untrusted` record per read.

## The three load-bearing sharpenings (owner-required, mechanisms verified)

**S1 — Content-type guard must be real.** `ExternalFetchResult` (:169-181) carries
no `content_type`. v0 **extends `ExternalFetchResult` with `content_type: str = ""`**,
populated from the response `Content-Type` header in the fetch layer. The
FETCH_URL adapter accepts only `text/html` and `text/plain` (parameters like
`; charset=utf-8` stripped before compare); anything else →
`_MappedExternalFailure(EMPTY/NO_RESULTS, FRESH_ATTEMPT_FAILED)` — honest
refusal, never binary garbage into evidence. (Field addition is additive with a
default; existing constructors stay valid.)

**S2 — Page-read admission rule (the reclassification).** The clean rule, exact:
> owner-supplied URL ∧ external_fetch preflight allowed ∧ extracted content-type
> ∈ {text/html, text/plain} ⇒ the OBSERVATION (not the fetch registration) is
> written with `egress_origin_class="tool_result_public"`, `provenance_source=
> ProvenanceSource.EXTERNAL_WEB` → `TrustTier.UNTRUSTED`, `source_ref=
> "page_read:<diagnostic_id>:<url_hash>"`.
Anything model-suggested or otherwise unclassified stays refused (the existing
MODEL_INVENTED_URL preflight + the bus's unclassified refusal both stay
untouched). The fetch registration itself remains `unclassified` — the
reclassification happens at the LANE, justified by the three conditions above,
and the lane records all three as booleans in the observation metadata so the
reclassification is auditable, never silent.

**S3 — Source-specific progress wording.** The progress emit becomes
source-aware: `FETCH_URL` fanout start → "reading the page…"; WEB_SEARCH keeps
"searching the web…". (In v0 the Layer0 precedence rule means a turn selects
ONE of the two, so the one-shot sender policy needs no change — the emit helper
just gains the per-source text.) Never a search-ish message for a page read.

## Components

1. **The nerve — Layer0 arm (flag-gated):** when `page_read_enabled()` AND the
   utterance contains an explicit URL (reuse the fanout's `_extract_urls`
   notion — http/https only), select `[ExternalSource.FETCH_URL]`, composed
   HYBRID with substrate (PARALLEL when substrate available, FRESH_ONLY
   otherwise) — same composition shape as the current-world arm. Precedence:
   the explicit-URL arm sits above the current-world arm (a URL-bearing turn
   reads the page rather than searching about it). Flag off ⇒ Layer0 never
   selects FETCH_URL (today's behavior exactly).
2. **The digestion — stdlib extractor:** new module `core/search/page_extract.py`
   (`html.parser.HTMLParser` based): drop `script/style/noscript/nav/header/
   footer/svg` subtrees, capture `<title>`, collapse whitespace, bound output
   (~6000 chars pre-cap; the fanout's 2000-char prompt cap still applies
   downstream). text/plain passes through bounded. Garbage/empty extraction →
   honest EMPTY failure. Quality bar: honest bounded text, not beauty. NO new
   dependencies (verified: trafilatura/readability/bs4/lxml/html2text absent).
   Applied inside `_fetch_url_adapter` between fetch and payload; the payload
   text becomes `"<title>\n<extracted text>"`.
3. **The stomach — lane extension:** the pipeline stash carries FETCH_URL
   branches too: `evaluate_write_condition` becomes source-aware (WEB_SEARCH or
   FETCH_URL in effective_spec + summaries + outcome OK); the observation
   content for page reads = URL + title + bounded excerpt; `source_ref=
   "page_read:<diagnostic_id>:<url_hash>"`; same chat_id-keyed stash, same
   daemon drain, same idempotency. `/receipts` sources include the read URL.
4. **Voice:** unchanged — evidence flows into synthesis, `[E#]` rendered to
   natural attribution post-audit; the attribution suffix already generalizes
   ("I looked at the live web for this").

## Error honesty

- Preflight refusals (model-invented URL, sensitive query, private IP, scheme)
  → the wing's existing typed failures → honest limitation in the reply.
- Non-text content-type → EMPTY/NO_RESULTS → honest "couldn't read that page."
- Extraction yields nothing → EMPTY → honest absence. Never fake page content.
- Lane/bus failure → log + drop, never block the reply (existing law).

## Testing

- Layer0: URL+flag ⇒ FETCH_URL hybrid; URL+flag-off ⇒ byte-identical prior
  composition; no-URL ⇒ unchanged; URL+current-world-markers ⇒ FETCH_URL wins
  precedence.
- Extractor: boilerplate stripped, title captured, bounds enforced, plain text
  passthrough, garbage fails safe.
- Adapter: extraction applied; content-type guard (html ok, plain ok,
  application/pdf refused EMPTY); receipts intact (diagnostic id present);
  `MODEL_INVENTED_URL` + sensitive-query preflights still green UNTOUCHED.
- `ExternalFetchResult.content_type`: populated from header; default ""
  keeps every existing constructor/test green.
- Lane: page-read observation written under the S2 rule with the three
  audit booleans; idempotent on diagnostic id; WEB_SEARCH lane behavior
  unchanged; unclassified-origin attempts still refused by the bus (test the
  REAL `_validate`).
- Progress: FETCH_URL start ⇒ "reading the page…"; WEB_SEARCH wording
  unchanged; flag-off ⇒ no FETCH_URL emits.

## Witness plan (owner breaths, after merge)

1. `MAEZ_PAGE_READ_ENABLED=1` + restart.
2. Paste tonight's exact unfinished question: *"check
   https://github.com/ggml-org/llama.cpp/releases — what's the latest
   release?"* → expect "reading the page…" → the version number, finally,
   in Maez's voice.
3. `/receipts` → the page URL as source.
4. Memory: one `page_read:*` observation with the three audit booleans;
   repeat the paste → no duplicate.
5. A model-invented-URL probe (ask Maez to check a page WITHOUT naming a
   URL) → no fetch, honest reply (the rail holding).
6. A non-text URL (e.g. a direct PDF link) → honest "couldn't read that."

## Deferred (named)

Search-followthrough auto-reads (snippet-insufficient judgment); multi-page /
link-following; JS rendering / browser body; vision lane; autonomous
curiosity page-reads (the standing third-party + public-topic rails apply
when that arc opens); richer extraction libraries.

## Constraints

Default-OFF own flag; witnessed before live; Codex builds / Claude reviews;
test runner `/home/rohit/maez/.venv/bin/python -B -m unittest`, no
full-discover in the live tree; main local-only, no push; `## Predicted
effect` on behavior commits; merge/flag/restart = owner breaths.
