# Personal Data Intake Bus v0 — the Admission Doorway

**Date:** 2026-06-04
**Status:** DRAFT for owner review → Codex implements / Claude reviews ([[feedback_parallel_agents_for_maez]]).
**Builds on:** the lived GitHub v1 limb (`core/information_limb/github_v1.py` + `github_store.py`, the `admit_repo_count_to_body` immune step + the resume-first idempotency hardening, all merged + lived — `project_cognition_live_state`); the owner-account taint rail (`egress_origin_class`, `core/egress/gate.py` `KNOWN_ORIGINS`); the honest-ingestion immune primitives (`memory/memory_manager.py` `ProvenanceSource`/`TrustTier`/`_DEFAULT_TIER_BY_SOURCE`); the parked "Personal Data Limb Runtime" sketch (`docs/superpowers/parked/2026-06-03-self-extending-senses-personal-data-ingestion-parked-sketch.md`).
**Roadmap:** the intake bus is now the next build (reordered ahead of continuity/trust-tier — `project_organ_roadmap` 2026-06-04 amendment) on producer-causality grounds: shape the ingestion doorway first so new facts enter correctly-provenanced from day one.

## 0. Why

GitHub v1 proved the covenant ingestion pattern in **one** channel: a staged, minimized fact crossing into Maez's body wearing a trust tier, an `owner_account_context` egress taint, a traceability `source_ref`, idempotency, and a content-free outcome. That immune logic lives **bespoke inside `github_v1.py`**. Calendar is staging-only; Reddit is identity-only; there is **no shared doorway**.

The Intake Bus v0 **extracts that immune step into one reusable contract every limb passes through** — so the next service inherits correct provenance/tier/taint/promotion posture instead of re-implementing them (and re-deciding them inconsistently). In the owner's words: *the bus is not "how to fetch from accounts"; it is the doorway facts must pass through before they become part of Maez. Keep the hands service-specific; make the doorway shared.*

## 1. Scope — boundary A: admission-only

The GitHub admission chain has four layers:
1. **Acquisition** (`fetch_repo_count`) — service-specific.
2. **S2 envelope + policy** (minimize / validate scope / stamp).
3. **Staging store** (`github_store`, durable `promotion_state`).
4. **Admission to body** — the immune step: trust-tier + taint + promotion gate + content-free witness + idempotency + body-write.

**v0 extracts layer 4 only.** Layers 1–3 stay in the limb. The bus owns the covenant moment: *"this staged, minimized fact may enter Maez's body, with this trust tier, this egress taint, this source_ref, this idempotency behavior, and this promotion posture."* It does not fetch, interpret, or own any limb's staging schema.

**Proof strategy — N=2:** GitHub refactors to ride the bus **byte-identical** (the only real lived limb's behavior must not change), **plus** a synthetic test-only rider with a deliberately un-GitHub fact shape proves the abstraction is not GitHub-shaped. No real second service (Calendar/Reddit) is promoted.

## 2. The contract (`core/intake_bus/contract.py`)

```python
class PromotionPosture(Enum):
    ADMIT_TO_BODY = "admit_to_body"   # the fact may become a body memory (GitHub)
    STAGE_ONLY    = "stage_only"      # the fact stays staged; the doorway refuses body-admission (Calendar-shaped)
    # future (Option C, NOT in v0): QUARANTINE_PROPOSAL — lands as a contestable reflection proposal

@dataclass(frozen=True)
class IntakeFact:
    source_kind: str                    # provenance label, e.g. "github.repo_count"
    source_ref: str                     # idempotency + traceability key, e.g. "github.s2:<ingest_record_id>"
    content: str                        # honest, LIMB-BUILT wording; the bus moves it verbatim, never composes/interprets
    provenance_source: ProvenanceSource # the bus DERIVES trust_tier from this (limb cannot over-claim)
    egress_origin_class: str            # the taint this fact claims; validated against KNOWN_ORIGINS, non-"unclassified"
    promotion_posture: PromotionPosture
    fetch_batch_id: str                 # traceability
    metadata: Mapping[str, str] = field(default_factory=dict)  # extra traceability; NO secret/owner-content VALUES

class StoreAdapter(Protocol):
    # The limb implements these so the bus drives idempotency without owning the staging schema.
    def oldest_pending(self) -> IntakeFact | None: ...
    def mark_admitted(self, source_ref: str, *, body_memory_id: str) -> None: ...

@dataclass(frozen=True)
class IntakeOutcome:                     # content-free BY CONSTRUCTION
    status: str        # "admitted" | "already_admitted" | "staged_not_admitted" | "refused" | "nothing_pending"
    source_ref: str | None
    reason: str | None = None            # content-free CODE, only for "refused" (never fact content)
```

**The doorway does not report `resumed`.** Whether a pending record was just-staged this call or left over from a prior crash is knowledge only the **limb** has (it sees whether `oldest_pending` was `None` before it staged). The bus must not assert knowledge it lacks; `resumed` is a limb-level result field (§5), not a doorway outcome.

**Content-blindness is a covenant property:** the bus moves `fact.content` to the body verbatim and never composes or inspects it. The honest wording stays the limb's responsibility.

## 3. The doorway (`core/intake_bus/admit.py`)

`admit(store_adapter, memory) -> IntakeOutcome`. Ordered, fail-closed. The bus imports `KNOWN_ORIGINS` from `core/egress/gate.py` (the single origin-class registry).

```
fact = store_adapter.oldest_pending()
if fact is None:
    return IntakeOutcome("nothing_pending", None)          # honest no-op, content-free

# Stage A — covenant validation → REFUSE (a verdict; NON-throwing; no substrate touched)
reason = validate(fact)        # see below; a malformed package never reaches the body
if reason is not None:
    return IntakeOutcome("refused", fact.source_ref, reason=reason)   # NO write

# Stage B — promotion posture
if fact.promotion_posture is PromotionPosture.STAGE_ONLY:
    return IntakeOutcome("staged_not_admitted", fact.source_ref)      # NO body write; record stays staged

# Stage C — idempotency (resume-first); body-state uncertainty RAISES, leaving the record pending
existing = memory.body_row_id_by_source_ref(fact.source_ref, egress_origin_class=fact.egress_origin_class)
if existing is not None:
    store_adapter.mark_admitted(fact.source_ref, body_memory_id=str(existing))
    return IntakeOutcome("already_admitted", fact.source_ref)

# Stage D — derive tier (inside store, from provenance_source) + body-write WITH the taint
body_id = memory.store(
    content=fact.content, cycle=0,
    provenance_source=fact.provenance_source,        # bus owns tier-derivation via _DEFAULT_TIER_BY_SOURCE
    egress_origin_class=fact.egress_origin_class,     # the taint, applied at the doorway
    metadata={"source_ref": fact.source_ref, "fetch_batch_id": fact.fetch_batch_id, **fact.metadata},
)
store_adapter.mark_admitted(fact.source_ref, body_memory_id=str(body_id))
return IntakeOutcome("admitted", fact.source_ref)
```

**`validate(fact)` (returns a content-free reason code, else `None`):**
- `source_ref` missing/empty → `"missing_source_ref"`.
- `egress_origin_class` **not in `KNOWN_ORIGINS`** → `"unknown_origin_class"`.
- `egress_origin_class == "unclassified"` → `"unclassified_origin"`. *(Known but NOT admissible through a covenant doorway — named explicitly: admission requires a known, explicit, non-`unclassified` origin.)*
- `content` empty → `"missing_content"`.
- (`provenance_source` and `promotion_posture` are enums → valid by construction.)

**The two kinds of "no" are never conflated (owner-required):**
- **Bad package → `refused`**: a returned verdict, content-free, no write. The machine continues.
- **Uncertain substrate → raise**: any `body_row_id_by_source_ref` / `store` / `mark_admitted` backend error propagates; the staged record stays pending for a clean retry. The machine stops rather than guess. Never launder "I can't tell the body's state" into "absent → admit."

## 4. The generic body-row lookup (`memory/memory_manager.py`)

The current `owner_account_row_id_by_source_ref` is hardcoded to `egress_origin_class == "owner_account_context"`. A shared doorway must not bake "owner_account" into every future fact's idempotency check.

**Add** `body_row_id_by_source_ref(source_ref, *, egress_origin_class) -> id | None`: the strict read-only lookup, filtered by the **passed** origin class. **Fail-closed identical to today's** — raises on backend error, never returns `None` on uncertainty (no absence-laundering). `owner_account_row_id_by_source_ref` becomes a thin wrapper: `return self.body_row_id_by_source_ref(source_ref, egress_origin_class="owner_account_context")` — so GitHub's existing direct callers stay byte-identical. **`MemoryManager.store` is untouched** (same discipline as the hardening). The bus calls the generic form with `egress_origin_class=fact.egress_origin_class`. (Bonus correctness: a `source_ref` is only "the same fact" if it also wears the same origin class.)

## 5. Rider 1 — GitHub rides the bus, byte-identical (`core/information_limb/github_v1.py`)

- **New `GithubStoreAdapter(store)`** implements `StoreAdapter`:
  - `oldest_pending()` reads the existing `github_store` pending row and builds an `IntakeFact`: `source_kind="github.repo_count"`, `source_ref=f"github.s2:{ingest_record_id}"`, `content=`**the limb's existing `_honest_repo_count_content(count, count_field)`** (content-building stays GitHub's), `provenance_source=ProvenanceSource.TOOL_OBSERVATION`, `egress_origin_class="owner_account_context"`, `promotion_posture=PromotionPosture.ADMIT_TO_BODY`, `fetch_batch_id=<staged>`. **`github_store`'s schema is untouched.**
  - `mark_admitted(source_ref, body_memory_id)` maps back to `store.mark_admitted(ingest_record_id, body_memory_id=...)`.
- **`run_ingest`** becomes: `was_pending = store.oldest_pending() is not None`; if not pending → `fetch_repo_count` + `ingest_repo_count` (stage — limb code, unchanged); then `outcome = intake_bus.admit(GithubStoreAdapter(store), memory)`; **translate `outcome` → the existing content-free result dict** (`{ok, ingest_record_id, fetch_batch_id, staged, admitted, resumed}`) so the daemon route + `scripts/github_ingest.py` allowlists and their tests are unchanged. **`resumed` is computed by `run_ingest`** (`= was_pending`, the limb's own knowledge — §2), `admitted = outcome.status == "admitted"`.
- `admit_repo_count_to_body`'s body-write + idempotency move into the bus; if a thin GitHub shim is kept it only builds the `IntakeFact` (no immune logic).

**Correctness bar (the zero-change proof):** the existing `tests/test_github_v1_egress_canary.py` and the GitHub idempotency tests pass **unchanged** — same body row (`owner_account_context` taint, `source_ref`, OBSERVED tier, verbatim honest content), same content-free outcome. **If those tests need editing to pass, the extraction changed behavior and is wrong** — that is the strongest evidence and must be preserved.

## 6. Rider 2 — the synthetic rider (test-only, N=2)

`tests/test_intake_bus_admit.py` defines a `FakeLimbStoreAdapter` with a deliberately un-GitHub shape and exercises the doorway:
- **Admit a non-owner fact** — `source_kind="synthetic.note"`, its own `source_ref` scheme, `egress_origin_class="memory"` (a real `KNOWN_ORIGINS` member in `MINIMIZABLE_PRIVATE_CONTEXT` — non-owner, **not** reserved-denied/categorically-blocked, so this proves non-owner admission + the parameterized lookup **without** conflating with the egress refusal gate), `ADMIT_TO_BODY`. → `status="admitted"`; a body row exists with `egress_origin_class="memory"` and content **verbatim** from the adapter (proves content-blindness); the lookup was called with `egress_origin_class="memory"` (proves it is not owner-account-baked).
- **Idempotency** — second `admit` → `already_admitted`, exactly one body row.
- **`STAGE_ONLY`** — a fact with `STAGE_ONLY` → `staged_not_admitted`, **no body row**.
- **`refused`** — a fact with an unknown origin class → `status="refused"`, `reason="unknown_origin_class"`, **no body row**, **no raise**.
- **Substrate-uncertainty raises** — a `memory` stub whose lookup raises → `admit` **raises**, no write, record left pending (distinct from `refused`).
- **Tier authority** — the body row's `trust_tier` is derived from `provenance_source`, independent of any tier the fake limb might assert.

The synthetic rider is never shipped and never touches real personal data.

## 7. Covenant rails

- **Content-blind doorway**: moves `content`, never composes/inspects it (asserted: body content == adapter content, byte-for-byte).
- **Tier authority at the doorway**: tier derived from `provenance_source`; the limb cannot over-claim.
- **Taint validated + applied at the doorway**: known, explicit, non-`unclassified` origin or `refused`.
- **Two kinds of "no" kept distinct**: bad package → `refused` (verdict, returned); uncertain substrate → raise (machine stops, record pending).
- **Content-free** outcome + logs: status / source_ref / reason-code only — never content, count, secret, or owner value.
- **No new external deps; no brain-emitted code**: pure substrate. `MemoryManager.store` untouched.

## 8. Hermetic tests (no proxy, no HTTP)

- `tests/test_intake_bus_admit.py` — the synthetic rider above (admit / idempotency / `STAGE_ONLY` / `refused` / substrate-raise / tier authority / content-blindness / parameterized-lookup).
- `body_row_id_by_source_ref` tests — honors the passed `egress_origin_class`; fail-closed (raises, never `None`-launders); the `owner_account_row_id_by_source_ref` wrapper still resolves owner-account rows.
- **GitHub regression net** — existing `tests/test_github_v1_egress_canary.py` + GitHub idempotency tests pass **unchanged**.
- Run the **full** `.venv/bin/python -B -m unittest discover -s tests -p 'test_*.py' -t .` before done (the schema-pin lesson). Cross-lane review runs branch code in the **asset-rich main checkout** apples-to-apples, not the worktree ([[feedback_worktree_floor_confound]]).

## 9. Acceptance rules

1. `IntakeFact` / `StoreAdapter` / `PromotionPosture` / `IntakeOutcome` exist in `core/intake_bus/contract.py`; `IntakeOutcome` carries no content/count/secret.
2. `admit` validates **known, explicit, non-`unclassified`** origin; typo/missing/`unclassified` → `refused` with a content-free reason code, **no write, no raise**.
3. `admit` raises (does not refuse, does not admit) on any lookup/store backend uncertainty, leaving the record pending.
4. `admit` derives `trust_tier` from `provenance_source` (limb cannot over-claim).
5. `admit` enforces posture: `STAGE_ONLY` → `staged_not_admitted` (no body row); `ADMIT_TO_BODY` → body-write with the declared taint.
6. `admit` is idempotent on `(source_ref, egress_origin_class)`: a pre-existing body row → `already_admitted`, exactly one row.
7. `body_row_id_by_source_ref(source_ref, *, egress_origin_class)` exists, fail-closed; `owner_account_row_id_by_source_ref` is a thin wrapper; `store` untouched.
8. GitHub rides the bus: `run_ingest` stages-then-`admit`; the existing GitHub canary + idempotency tests pass **unchanged**; the daemon route / script content-free result is unchanged.
9. The synthetic rider proves admission of a non-`owner_account` (`memory`) fact, idempotency, `STAGE_ONLY`, `refused`, substrate-raise, tier authority, and content-blindness — without touching real data.
10. Full suite green (zero new failures, apples-to-apples vs main); content-free throughout; no new external deps.

## 10. File structure

**Create:** `core/intake_bus/__init__.py`, `core/intake_bus/contract.py`, `core/intake_bus/admit.py`, `tests/test_intake_bus_admit.py`, `tests/test_memory_body_row_lookup.py` (or extend the existing memory lookup test).
**Modify:** `memory/memory_manager.py` (add generic lookup + wrapper), `core/information_limb/github_v1.py` (add `GithubStoreAdapter`, refactor `run_ingest`, slim `admit_repo_count_to_body`).
**Untouched:** `MemoryManager.store`, `github_store` schema, `core/egress/gate.py` (consumed read-only), Calendar, Reddit.

## 11. Scope

**In:** the admission doorway (contract + `admit`), the generic body-row lookup, the GitHub byte-identical refactor, the synthetic rider, hermetic tests.
**Out (so the bite stays one bite):** acquisition/auth/fetch generalization; generic staging-store or S2-envelope (layers 1–3); promoting any real second service (Calendar/Reddit); the quarantine/reflection-proposal posture (enum leaves room; v0 does not implement it); connector/descriptor registry; privacy-filter / span detection; any daemon route or restart (v0 is library + tests; GitHub's existing route is unchanged and the running daemon is untouched until a future deliberate restart).

## 12. Lane

Codex implements / Claude reviews. Cross-lane verification mandatory ([[feedback_cross_lane_verification_mandatory]]); the GitHub zero-change bar (existing tests unedited) is the primary review anchor.
