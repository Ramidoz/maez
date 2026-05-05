# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""core.symphony.evals — Maez Eval Harness v1.

Built on the R5 surface_probe pattern: stdlib + pyyaml only,
JSON baselines, curated corpora, no new dependencies. External
eval frameworks (Inspect AI, DeepEval, Promptfoo, Ragas) are
references, not infrastructure. We extend our own pattern.

Six families:
  body_action_truth     — claim-vs-runtime + tool outcomes
  memory_continuity     — retrieval + provenance
  telemetry_coherence   — single-turn truth across stores
  surface_coherence     — diff-vs-baseline (extends R5)
  voice_bond            — owner-rubric only
  adversarial_identity  — hold / refuse / surface

V1 ships the scaffold + 1-2 proof probes per family. The real
corpus is owner-curated work; bad prompts make a harness look
rigorous while testing the wrong thing. The corpus is the eval.
"""
