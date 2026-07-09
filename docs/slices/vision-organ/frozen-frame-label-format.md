# Frozen-frame bench label format

Slice 3 is a private evaluation rig. It judges one manually started loopback
vision candidate against owner-authored truth; it does not admit, rank, or
configure a production sensor. It never captures a screen or starts/stops a
service. All frames, labels, transcripts, diagnostics, and receipts remain
under the gitignored `local/vision_bench/` directory.

## Private directory layout

Create the directory with owner-only permissions (`0700`) and place files at:

```text
local/vision_bench/
  manifest.json
  frames/<frame-id>.png
  labels/<frame-id>.json
  runs/                         # generated, private UNTRUSTED artifacts
  receipts/                     # generated, content-light local receipts
```

The harness reads only frame IDs explicitly listed in `manifest.json`; it does
not discover files by glob. Every source PNG is read once, hash-checked, fully
decoded, and retained in memory. `full_640`, `full_1280`, and `active_native`
are then derived deterministically from those same bytes.

## Manifest

```json
{
  "schema_version": "vision_frozen_manifest.v1",
  "frames": ["frame-001"]
}
```

## Owner label file

`labels/frame-001.json` has this shape:

```json
{
  "schema_version": "vision_frozen_labels.v1",
  "frame_id": "frame-001",
  "source_sha256": "<sha256 of exact frames/frame-001.png bytes>",
  "truth_source": "owner_human",
  "owner_approved": true,
  "third_party_content_reviewed": true,
  "active_window_crop": {
    "left": 120,
    "top": 80,
    "right": 1400,
    "bottom": 860
  },
  "labels": [
    {
      "label_id": "title-1",
      "region_id": "titlebar",
      "region_aliases": ["titlebar", "window title"],
      "kind": "window_title",
      "text": "Settings",
      "visible_in": ["full_640", "full_1280", "active_native"]
    }
  ]
}
```

Only the owner supplies truth. `truth_source` must be exactly `owner_human`,
and `owner_approved` must be JSON `true`. The owner also decides whether the
frame is appropriate for this corpus; `third_party_content_reviewed` must be
JSON `true`. Exclude third-party content whenever owner discretion says it
does not belong in the bench.

`active_window_crop` is owner-authored native-pixel geometry, with right and
bottom exclusive. `region_aliases` are the only permitted mappings from model
region labels to a canonical `region_id`; the harness never auto-aligns them.
`visible_in` declares which derived transforms actually contain that labeled
region. Every evaluated transform must have at least one applicable human
label or the run refuses before contacting a candidate.

Allowed `kind` values are `window_title`, `filename`, `command`,
`application_name`, `error_message`, and `key_string`.

## Evaluation semantics

Candidate requests use the Slice 2 transcribe/abstain request at temperature
zero, and replies use the Slice 2 parser without prompt or parser variants.

Correct-text coverage and abstention coverage are reported separately. A
label counts toward correct-text coverage only when the candidate transcribes
its exact text in the owner-mapped region. A partial or explicit unreadable
field counts toward abstention coverage; the two measures are never averaged
into one score.

Evidence monotonicity permits a lower-resolution abstention or partial field
to become a transcription at higher evidence. Replacing a non-abstained value
or losing it at higher evidence is recorded as a hard contradiction or
regression. Exact output agreement across transforms is not required.

Any high-specificity string absent from applicable owner labels is a hard
failure. The literal appears only in the private quarantined diagnostic. Its
receipt entry contains the string kind, character count, SHA-256,
diagnostic-relative path, and `diagnostic_sha256`. To inspect it, first verify
the diagnostic file's exact hash against `diagnostic_sha256`, then match the
kind/count/string hash inside the diagnostic. This closes receipt → diagnostic
→ literal without placing the literal in the receipt.

## Manual candidate precondition and VRAM

Start at most one candidate server manually, bound to an explicit loopback
port and model alias. The harness accepts only an already-running
`http://127.0.0.1:<port>` or `http://localhost:<port>` endpoint. It does not
start, stop, enable, disable, or otherwise manage that process.

Each run records a finite post-load VRAM peak after exact alias readiness and
a separate peak spanning the complete image-inference batch. Missing either
number makes the candidate unscored. The receipt is a local bake-off witness
only: Slice 3 judges; it does not admit a model or modify any sensor path.
