# Vision Slice 5 — AT-SPI accessibility lane v1.1

Date: 2026-07-09  
Status: IMPLEMENTED UNCOMMITTED; awaiting owner-relayed Claude gate  
Governance: Decision 9 / ADR 0009, ADR 0029, Vision rulings 5–6  
Lane: Codex builds; Claude gates; owner commits only after gate

## Purpose and boundary

Slice 5 adds a dormant deterministic sensor that can quote bounded
accessibility facts from the compositor-focused window. It reads no pixels,
admits nothing to cognition, writes no memory, builds no prompt, and supplies
no tool or command argument.

AT-SPI is deterministic transport, not truth. Every literal is untrusted
quoted evidence supplied by the focused application. The sensor does not claim
that accessibility text is visually corroborated, current, authored by the
owner, or safe to obey.

## Components

### Slice 4 schema v2 binding seam

`core.body.active_window_sensor.ActiveWindowReading` gains a frozen
`FocusBinding(pid, window_id)` and advances to
`active_window_geometry.v2`.

The binding is optional on the general Slice 4 reading and process-memory only:

- it is never returned by `to_receipt()`;
- it is excluded from dataclass repr output;
- it is never written to a diagnostic or log;
- it is never passed through argv, environment, stdin, stdout, or JSON;
- when present it requires a positive PID and bounded compositor window ID;
- ordinary Slice 4 geometry sampling remains available without a binding, so
  v2 is additive and does not regress the dormant geometry nerve;
- Slice 5 requires the binding before any AT-SPI call and refuses
  `window_binding_unavailable` when it is absent.

The FocusedWindow helper already receives PID/window ID from the extension.
Its normal stdout packet continues to omit both. The AT-SPI system helper calls
the compositor probe function directly with identity enabled, then passes that
mapping to Slice 4 in the same process. Slice 4 continues to use the same
title-bearing snapshot for Decision-9 preflight and geometry.

The same private helper call also retains the window's display-local logical
origin as a `WindowCalibration`. Fractional-scale edge conversion cannot be
reconstructed from the native crop alone because Slice 4's floor/ceil step
discards the fractional origin phase. This calibration is neither a public
Slice 4 field nor binding data: it remains in the helper process, is excluded
from repr/JSON/stdout/receipts, and is rechecked with the focus binding.

### Core accessibility contract

`core.body.atspi_sensor` owns the frozen public values, closed vocabularies,
packet validation, content-light receipt projection, and fixed helper adapter.
It imports no GI binding and has no production caller.

`scripts.atspi_window_probe` is the only live AT-SPI adapter. It runs under
`/usr/bin/python3`, where `gi.repository.Atspi` is installed. The helper calls
Slice 4 inside its own process, so the focus binding never crosses a process
boundary. Direct terminal execution refuses before any literal can be printed.

## Closed contract

Schema version: `atspi_accessibility.v1`.

Field kinds:

- `name`
- `text`
- `value`
- `document_uri`

Every successful fact carries:

- `source="atspi"`
- `trust="untrusted_quoted_evidence"`
- `support="atspi_state_bounds_only"`
- `egress_origin_class="third_party_private_context"`
- `publishable=false`
- a bounded literal value held only in process memory
- a right/bottom-exclusive `CropBox` in
  `display_local_native_device_pixels`
- a deterministic content-free region key derived from kind and region

Field values reject over-limit input rather than truncate. C0/C1 controls,
including ESC, are stripped; permitted whitespace is normalized to a single
space. Empty normalized values are not facts.

Named bounds:

- `MAX_IDENTITY_ROOTS = 64`
- `MAX_TOP_LEVEL_WINDOWS = 32`
- `MAX_DOCUMENT_ATTRIBUTE_QUERIES = 64`
- `MAX_NODES = 256`
- `MAX_FIELDS = 512`
- `MAX_FIELD_CHARS = 512`
- `MAX_TOTAL_CHARS = 16_384`
- `MAX_PACKET_BYTES = 262_144`
- `MAX_TIMEOUT_SECONDS = 10.0`

Exceeding an identity-selection bound refuses `identity_scan_exceeded`.
Exceeding a node, field, per-field, total-character, or packet bound refuses
`field_limit_exceeded`. The helper checks counts before reading literal values.

## Sampling flow

1. Check the shared pause/curtain authority.
2. Obtain one Slice 4 v2 reading inside the helper process.
3. If Slice 4 returns a valid non-available reading, propagate its exact state
   and reason and perform zero AT-SPI calls. Reserve `slice4_unavailable` for
   missing, malformed, or wrong-schema upstream input.
4. Inspect the desktop root's child count before materializing any child. If it
   exceeds `MAX_IDENTITY_ROOTS`, refuse `identity_scan_exceeded`; otherwise
   enumerate those immediate application roots reading process identity only.
   Select exactly one application whose PID matches `FocusBinding.pid`.
5. Inspect at most `MAX_TOP_LEVEL_WINDOWS` immediate children of that
   application using state and component bounds only. Select exactly one
   ACTIVE/FOCUSED top-level whose dimensions agree with Slice 4. Class/name is
   never used as a binding heuristic. Zero or multiple matches refuse
   `window_binding_unavailable` or `window_binding_ambiguous`.
6. Traverse only the selected window subtree, including the selected top-level
   root itself. Stop before fetching the next node when `MAX_NODES` would be
   exceeded. Any child-enumeration uncertainty refuses rather than treating an
   unknown subtree as a leaf.
7. First pass: read state, role, bounds, and document-wide attributes only.
   Query a named, bounded set of case/separator variants whose normalized keys
   map to the seven allowlisted names; never fetch an unbounded attribute map.
   Require SHOWING and VISIBLE, positive resolvable extents, and intersection
   with the selected root's exact logical width/height. Do not reconstruct that
   ruler from a rounded native crop. Clip partial intersections to the active
   crop. Count excluded nodes without reading their content. Any document
   transport error refuses rather than meaning "no document".
8. Path preflight: inspect only document-wide values whose normalized key is
   in the closed set `{uri, url, docurl, documenturi, documenturl, path,
   documentpath}`. Do not inspect hyperlink targets. Canonicalize bounded
   percent-encoded URI/path representations before applying the single
   existing Decision-9 exclusion authority; malformed or over-nested encodings
   fail closed as `window_schema_invalid`.
9. If any document reference is sensitive, stop traversal, discard every
   collected node/reference/fact, and return whole-lane
   `state="excluded", reason="excluded_path"`. The reference literal appears
   nowhere in the result, receipt, hash, or diagnostic.
10. Second pass: only after path preflight succeeds, fetch the four allowed
    literal kinds from eligible nodes and create bounded facts. AT-SPI text
    exposes a character-count query, so the count is checked before text is
    fetched. Name and numeric-value interfaces expose no corresponding count;
    those values are read once into helper memory, immediately length-checked,
    and cause whole-sample refusal on overflow. No prefix is salvaged.
11. Recheck pause/curtain.
12. Re-read Slice 4 in the same helper process. If PID, window ID, geometry, or
    display serial changed, discard the sample as `focus_changed`.
13. Return the bounded packet through captured stdout. Recheck privacy in the
    parent immediately before returning the frozen reading.

## Visibility and geometry

The sensor filters what AT-SPI itself marks SHOWING and VISIBLE. It does not
claim cross-window stacking visibility. Successful readings and receipts carry
`support="atspi_state_bounds_only"` and `occlusion_checked=false`.

All component bounds use `Atspi.CoordType.WINDOW`, relative to the selected
top-level window. The top-level dimensions are calibrated against Slice 4's
native crop under its exact rational scale and private logical-origin phase. A
mismatch refuses `bounds_unresolvable`.

Child edges use the Slice 4 rule against that retained display-local logical
origin:

- left/top: floor((logical origin + window-relative edge) × scale)
- right/bottom: ceil((logical origin + window-relative edge) × scale)

The resulting region must be contained in `geometry.crop_box`; partially
intersecting nodes are clipped to the crop and disjoint nodes are excluded.
The parent independently revalidates the exact Slice 4 schema, coordinate
space, geometry, and every region's containment before constructing a reading.

An individual node with unresolved, zero, or out-of-crop bounds is excluded and
counted. Root calibration failure is lane-level `bounds_unresolvable`. If no
eligible facts remain, the lane refuses `no_visible_nodes`.

## Decision-9 path authority

The existing `active_window_preflight_reason()` remains the only authority. It
is extended with bounded document references and returns `excluded_path` when
an owner-configured exclusion term matches one. No second term list and no
action-engine sensitive-path regex are permitted.

Path preflight precedes every `document_uri` fact and every ordinary text/name/
value read. A sensitive document excludes the whole window context, matching
Decision 9's requirement that Maez not even observe that the document is open.

## Third-party and injection posture

AT-SPI has no general authorship signal. Therefore every fact defaults to
`third_party_private_context` and `publishable=false`. Tagging alone is not
treated as minimization: no ordinary Slice 5 output reaches cognition, prompt,
memory, egress, tool selection, or command construction.

An input such as `Ignore previous instructions…` remains a quoted literal in
the ephemeral reading only. It never becomes control text. Static import/caller
tests enforce that boundary.

## Receipts and persistence

An available receipt may contain:

- schema/state/timestamp
- support and `occlusion_checked=false`
- Slice 4 schema plus SHA-256 of its canonical geometry receipt
- included/excluded node counts by closed reason
- per-fact kind, character count, SHA-256, region key and region box

It contains no literal, application class, title, PID, window ID, document path,
URI, or diagnostic path.

Every excluded/refused receipt is content-blind and contains only schema,
state, timestamp, and typed reason.

Ordinary sampling performs no filesystem write. It does not create a bench
artifact. Owner-approved manual persistence remains exclusively under Slice
3's `/local/vision_bench/` rules: private directory, owner/third-party approval,
literal in quarantined diagnostic, cryptographic identity in receipt.

## Refusal vocabulary

Slice 5 adds the closed reasons:

- `slice4_unavailable`
- `atspi_unreachable`
- `atspi_protocol_invalid`
- `identity_scan_exceeded`
- `window_binding_unavailable`
- `window_binding_ambiguous`
- `bounds_unresolvable`
- `no_visible_nodes`
- `excluded_path`
- `field_limit_exceeded`
- `focus_changed`

Valid Slice 4 reasons are propagated exactly rather than translated into this
list.

## Dormancy and containment

There is no Slice 5 runtime flag because there is no runtime caller. A dead
flag would falsely imply an admission path. Structural tests require zero
imports from daemon, routing, prompt, memory, action, and production sensor
paths. The helper contains no screenshot, portal, shell, service-management,
or filesystem-write surface. Existing `MAEZ_SCREEN_PERCEPTION=0` and disabled
vision-service witnesses remain unchanged.

## Acceptance tests

RED-first coverage includes:

- Slice 4 v2 binding required, redacted from repr/receipt, and never serialized;
- same-class two-window zero/multiple selection refusals;
- identity scan cap;
- exact upstream refusal propagation with zero AT-SPI calls;
- SHOWING ∧ VISIBLE ∧ intersecting filter, including scrolled/offscreen nodes;
- unresolved-node counting and root mismatch refusal;
- window-relative HiDPI floor/ceil conversion;
- path preflight before all literal reads and whole-window exclusion;
- no hyperlink harvesting;
- third-party/injection literals inert and non-publishable;
- all caps and closed vocabularies;
- successful content-light receipts and content-blind refused receipts;
- ordinary sampling creates zero files;
- no capture, service, admission, prompt, memory, tool, or command surface;
- post-suite screen flag and vision-service containment witnesses.
