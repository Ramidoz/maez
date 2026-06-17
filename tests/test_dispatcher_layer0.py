import json
import numpy as np
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def _write_manifest(path: Path) -> None:
    path.write_text(
        """# Test Dispatcher Archetypes

### Class A — `A_EXPLICIT_SUBSTRATE_RECALL`

| Archetype | Tag | Anchor |
|---|---|---|
| what do you remember about qwen | empirical | test |

### Class B — `B_EXPLICIT_LIVE_FETCH`

| Archetype | Tag | Anchor |
|---|---|---|
| search qwen online | empirical | test |

### Class C — `C_HYBRID_CONTENT_ANCHORED`

| Archetype | Tag | Anchor |
|---|---|---|
| how is qwen looking online | proposed | test |
""",
        encoding="utf-8",
    )


class _FakeEncoder:
    model = "fake-minilm"
    dimension = 3

    def __init__(self):
        self.calls = []

    def encode_many(self, texts):
        self.calls.append(list(texts))
        return [self._vec(text) for text in texts]

    def encode(self, text):
        return self._vec(text)

    def _vec(self, text):
        text = text.lower()
        if "remember" in text:
            return [1.0, 0.0, 0.0]
        if "search" in text:
            return [0.0, 1.0, 0.0]
        if "qwen" in text or "online" in text:
            return [0.0, 0.0, 1.0]
        return [0.25, 0.25, 0.25]


class _NumpyScalarEncoder(_FakeEncoder):
    def _vec(self, text):
        return [np.float32(value) for value in super()._vec(text)]


class _RecallBiasedRedditEncoder(_FakeEncoder):
    def _vec(self, text):
        if "reddit" in text.lower():
            return [1.0, 0.0, 0.0]
        return super()._vec(text)


class DispatcherLayer0Tests(unittest.TestCase):
    def _emit_spec_for(self, utterance: str, *, env: dict[str, str] | None = None):
        from core.dispatcher.inventory import InventorySummary
        from core.dispatcher.layer0 import Layer0Dispatcher, load_archetype_index
        from core.dispatcher.spec import (
            ExternalSource,
            InventoryWitness,
            SourceAvailability,
            SubstrateSource,
        )

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        manifest = Path(tmp.name) / "archetypes.md"
        _write_manifest(manifest)
        encoder = _FakeEncoder()
        index = load_archetype_index(
            manifest_path=manifest,
            cache_path=Path(tmp.name) / "cache.json",
            encoder=encoder,
        )
        inventory = InventorySummary(
            inventory_witness=InventoryWitness.PRESENT,
            source_availability={
                SubstrateSource.TELEGRAM_SEMANTIC: SourceAvailability.EXECUTABLE_PRESENT,
                SubstrateSource.ENTITY_INDEX: SourceAvailability.EXECUTABLE_PRESENT,
                SubstrateSource.LIVED_EPISODES: SourceAvailability.EXECUTABLE_PRESENT,
                ExternalSource.WEB_SEARCH: SourceAvailability.EXECUTABLE_PRESENT,
                ExternalSource.LIVE_REDDIT: SourceAvailability.EXECUTABLE_PRESENT,
                ExternalSource.FETCH_URL: SourceAvailability.EXECUTABLE_PRESENT,
            },
            availability_limitations=[],
            generated_at=1.0,
        )
        with mock.patch.dict("os.environ", env or {}, clear=False):
            return Layer0Dispatcher(index=index, encoder=encoder).emit_spec(
                utterance,
                surface="telegram",
                inventory=inventory,
            )

    def test_archetype_manifest_parser_stops_at_non_archetype_tables(self):
        from core.dispatcher.layer0 import _parse_manifest

        raw = """# Test Dispatcher Archetypes

### Class K — `CONTRADICTION`

| Archetype | Tag | Anchor |
|---|---|---|
| You're wrong | empirical | test |

## Empirical-anchor coverage

| Class | Total | Empirical | Proposed | Coverage rationale |
|---|---|---|---|---|
| K — CONTRADICTION | 1 | 1 | 0 | summary row |
| **Total** | **1** | **1** | **0** | summary row |
"""

        archetypes = _parse_manifest(raw)

        self.assertEqual([item.text for item in archetypes], ["You're wrong"])

    def test_archetype_cache_reencodes_when_manifest_or_encoder_identity_changes(self):
        from core.dispatcher.layer0 import load_archetype_index

        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "archetypes.md"
            cache = Path(tmp) / "archetypes-cache.json"
            _write_manifest(manifest)

            encoder = _FakeEncoder()
            first = load_archetype_index(manifest_path=manifest, cache_path=cache, encoder=encoder)
            second = load_archetype_index(manifest_path=manifest, cache_path=cache, encoder=encoder)

            self.assertEqual(first.manifest_hash, second.manifest_hash)
            self.assertEqual(len(encoder.calls), 1)

            manifest.write_text(manifest.read_text(encoding="utf-8") + "\nextra witness\n", encoding="utf-8")
            third = load_archetype_index(manifest_path=manifest, cache_path=cache, encoder=encoder)
            self.assertNotEqual(first.manifest_hash, third.manifest_hash)
            self.assertEqual(len(encoder.calls), 2)

            payload = json.loads(cache.read_text(encoding="utf-8"))
            payload["encoder_model"] = "different"
            cache.write_text(json.dumps(payload), encoding="utf-8")
            load_archetype_index(manifest_path=manifest, cache_path=cache, encoder=encoder)
            self.assertEqual(len(encoder.calls), 3)

    def test_archetype_cache_serializes_numpy_scalar_embeddings(self):
        from core.dispatcher.layer0 import load_archetype_index

        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "archetypes.md"
            cache = Path(tmp) / "archetypes-cache.json"
            _write_manifest(manifest)

            index = load_archetype_index(
                manifest_path=manifest,
                cache_path=cache,
                encoder=_NumpyScalarEncoder(),
            )
            self.assertTrue(cache.exists())

        self.assertEqual(index.encoder_dimension, 3)

    def test_content_anchored_query_emits_hybrid_spec_with_inventory_witness(self):
        from core.dispatcher.inventory import InventorySummary
        from core.dispatcher.layer0 import Layer0Dispatcher, load_archetype_index
        from core.dispatcher.spec import (
            CompositionHint,
            ExternalSource,
            InventoryWitness,
            ProvenanceFraming,
            SourceAvailability,
            SubstrateSource,
        )

        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "archetypes.md"
            _write_manifest(manifest)
            encoder = _FakeEncoder()
            index = load_archetype_index(
                manifest_path=manifest,
                cache_path=Path(tmp) / "cache.json",
                encoder=encoder,
            )
            inventory = InventorySummary(
                inventory_witness=InventoryWitness.UNKNOWN,
                source_availability={
                    SubstrateSource.TELEGRAM_SEMANTIC: SourceAvailability.EXECUTABLE_UNKNOWN,
                    SubstrateSource.ENTITY_INDEX: SourceAvailability.EXECUTABLE_UNKNOWN,
                    SubstrateSource.LIVED_EPISODES: SourceAvailability.EXECUTABLE_UNKNOWN,
                    ExternalSource.WEB_SEARCH: SourceAvailability.EXECUTABLE_PRESENT,
                },
                availability_limitations=[],
                generated_at=1.0,
            )

            spec = Layer0Dispatcher(index=index, encoder=encoder).emit_spec(
                "how is qwen looking online",
                surface="telegram",
                inventory=inventory,
            )

        self.assertEqual(spec.composition_hint, CompositionHint.SUBSTRATE_THEN_FETCH_IF_STALE)
        self.assertEqual(
            spec.provenance_framing,
            ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES,
        )
        self.assertEqual(spec.inventory_witness, InventoryWitness.UNKNOWN)
        self.assertIn(SubstrateSource.TELEGRAM_SEMANTIC, spec.substrate_sources)
        self.assertEqual(spec.external_sources, [ExternalSource.WEB_SEARCH])
        self.assertEqual(
            spec.source_availability[SubstrateSource.TELEGRAM_SEMANTIC],
            SourceAvailability.EXECUTABLE_UNKNOWN,
        )

    def test_current_world_question_selects_web_search_hybrid(self):
        from core.dispatcher.inventory import InventorySummary
        from core.dispatcher.layer0 import Layer0Dispatcher, load_archetype_index
        from core.dispatcher.spec import (
            CompositionHint,
            ExternalSource,
            InventoryWitness,
            ProvenanceFraming,
            SourceAvailability,
            SubstrateSource,
        )

        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "archetypes.md"
            _write_manifest(manifest)
            encoder = _FakeEncoder()
            index = load_archetype_index(
                manifest_path=manifest,
                cache_path=Path(tmp) / "cache.json",
                encoder=encoder,
            )
            inventory = InventorySummary(
                inventory_witness=InventoryWitness.PRESENT,
                source_availability={
                    SubstrateSource.TELEGRAM_SEMANTIC: SourceAvailability.EXECUTABLE_PRESENT,
                    SubstrateSource.ENTITY_INDEX: SourceAvailability.EXECUTABLE_PRESENT,
                    SubstrateSource.LIVED_EPISODES: SourceAvailability.EXECUTABLE_PRESENT,
                    ExternalSource.WEB_SEARCH: SourceAvailability.EXECUTABLE_PRESENT,
                },
                availability_limitations=[],
                generated_at=1.0,
            )

            with mock.patch.dict("os.environ", {"MAEZ_SEARCH_AS_SENSE_ENABLED": "1"}):
                spec = Layer0Dispatcher(index=index, encoder=encoder).emit_spec(
                    "What's the latest with Anthropic?",
                    surface="telegram",
                    inventory=inventory,
                )

        self.assertEqual(spec.external_sources, [ExternalSource.WEB_SEARCH])
        self.assertIn(SubstrateSource.TELEGRAM_SEMANTIC, spec.substrate_sources)
        self.assertEqual(spec.composition_hint, CompositionHint.PARALLEL)
        self.assertEqual(
            spec.provenance_framing,
            ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES,
        )

    def test_self_capability_status_question_does_not_egress_to_web(self):
        from core.dispatcher.inventory import InventorySummary
        from core.dispatcher.layer0 import Layer0Dispatcher, load_archetype_index
        from core.dispatcher.spec import (
            CompositionHint,
            ExternalSource,
            InventoryWitness,
            ProvenanceFraming,
            SourceAvailability,
            SubstrateSource,
        )

        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "archetypes.md"
            _write_manifest(manifest)
            encoder = _FakeEncoder()
            index = load_archetype_index(
                manifest_path=manifest,
                cache_path=Path(tmp) / "cache.json",
                encoder=encoder,
            )
            inventory = InventorySummary(
                inventory_witness=InventoryWitness.PRESENT,
                source_availability={
                    SubstrateSource.TELEGRAM_SEMANTIC: SourceAvailability.EXECUTABLE_PRESENT,
                    SubstrateSource.ENTITY_INDEX: SourceAvailability.EXECUTABLE_PRESENT,
                    SubstrateSource.LIVED_EPISODES: SourceAvailability.EXECUTABLE_PRESENT,
                    ExternalSource.WEB_SEARCH: SourceAvailability.EXECUTABLE_PRESENT,
                },
                availability_limitations=[],
                generated_at=1.0,
            )

            with mock.patch.dict(
                "os.environ",
                {
                    "MAEZ_EVIDENCE_PRECEDENCE_ENABLED": "1",
                    "MAEZ_SEARCH_AS_SENSE_ENABLED": "1",
                },
            ):
                spec = Layer0Dispatcher(index=index, encoder=encoder).emit_spec(
                    "What's the state of your web search tools?",
                    surface="telegram",
                    inventory=inventory,
                )

        self.assertEqual(spec.external_sources, [])
        self.assertNotIn(ExternalSource.WEB_SEARCH, spec.external_sources)
        self.assertEqual(spec.composition_hint, CompositionHint.SUBSTRATE_ONLY)
        self.assertEqual(
            spec.provenance_framing,
            ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION,
        )

    def test_self_capability_status_question_flag_off_preserves_prior_search_shape(self):
        from core.cognition.capability_card import evidence_precedence_enabled
        from core.dispatcher.inventory import InventorySummary
        from core.dispatcher.layer0 import Layer0Dispatcher, load_archetype_index
        from core.dispatcher.spec import (
            ExternalSource,
            InventoryWitness,
            SourceAvailability,
            SubstrateSource,
        )

        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "archetypes.md"
            _write_manifest(manifest)
            encoder = _FakeEncoder()
            index = load_archetype_index(
                manifest_path=manifest,
                cache_path=Path(tmp) / "cache.json",
                encoder=encoder,
            )
            inventory = InventorySummary(
                inventory_witness=InventoryWitness.PRESENT,
                source_availability={
                    SubstrateSource.TELEGRAM_SEMANTIC: SourceAvailability.EXECUTABLE_PRESENT,
                    ExternalSource.WEB_SEARCH: SourceAvailability.EXECUTABLE_PRESENT,
                },
                availability_limitations=[],
                generated_at=1.0,
            )

            with mock.patch.dict(
                "os.environ",
                {
                    "MAEZ_SEARCH_AS_SENSE_ENABLED": "1",
                    "MAEZ_EVIDENCE_PRECEDENCE_ENABLED": "0",
                },
            ):
                self.assertFalse(evidence_precedence_enabled())
                spec = Layer0Dispatcher(index=index, encoder=encoder).emit_spec(
                    "What's the state of your web search tools?",
                    surface="telegram",
                    inventory=inventory,
                )

        self.assertEqual(spec.external_sources, [ExternalSource.WEB_SEARCH])

    def test_self_capability_complaint_about_search_does_not_egress(self):
        from core.dispatcher.spec import (
            CompositionHint,
            ExternalSource,
            ProvenanceFraming,
        )

        spec = self._emit_spec_for(
            "you seem unable to search the web",
            env={
                "MAEZ_EVIDENCE_PRECEDENCE_ENABLED": "1",
                "MAEZ_SEARCH_AS_SENSE_ENABLED": "1",
            },
        )

        self.assertEqual(spec.external_sources, [])
        self.assertNotIn(ExternalSource.WEB_SEARCH, spec.external_sources)
        self.assertEqual(spec.composition_hint, CompositionHint.SUBSTRATE_ONLY)
        self.assertEqual(
            spec.provenance_framing,
            ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION,
        )

    def test_self_capability_complaint_about_fetch_does_not_egress(self):
        from core.dispatcher.spec import ExternalSource

        spec = self._emit_spec_for(
            "why can't you fetch pages",
            env={
                "MAEZ_EVIDENCE_PRECEDENCE_ENABLED": "1",
                "MAEZ_SEARCH_AS_SENSE_ENABLED": "1",
            },
        )

        self.assertEqual(spec.external_sources, [])
        self.assertNotIn(ExternalSource.WEB_SEARCH, spec.external_sources)

    def test_self_capability_complaint_about_subreddit_does_not_egress(self):
        from core.dispatcher.spec import ExternalSource

        spec = self._emit_spec_for(
            "you keep failing at r/LocalLLaMA",
            env={
                "MAEZ_EVIDENCE_PRECEDENCE_ENABLED": "1",
                "MAEZ_SEARCH_AS_SENSE_ENABLED": "1",
            },
        )

        self.assertEqual(spec.external_sources, [])
        self.assertNotIn(ExternalSource.LIVE_REDDIT, spec.external_sources)

    def test_self_capability_complaint_flag_off_preserves_prior_external_shape(self):
        from core.dispatcher.spec import ExternalSource

        spec = self._emit_spec_for(
            "you seem unable to search the web",
            env={
                "MAEZ_EVIDENCE_PRECEDENCE_ENABLED": "0",
                "MAEZ_SEARCH_AS_SENSE_ENABLED": "1",
            },
        )

        self.assertEqual(spec.external_sources, [ExternalSource.WEB_SEARCH])

    def test_explicit_search_still_wins_over_complaint_guard(self):
        from core.dispatcher.spec import ExternalSource

        spec = self._emit_spec_for(
            "search for Anthropic news",
            env={
                "MAEZ_EVIDENCE_PRECEDENCE_ENABLED": "1",
                "MAEZ_SEARCH_AS_SENSE_ENABLED": "1",
            },
        )

        self.assertEqual(spec.external_sources, [ExternalSource.WEB_SEARCH])

    def test_explicit_search_about_broken_owner_object_still_egresses(self):
        from core.dispatcher.spec import ExternalSource

        spec = self._emit_spec_for(
            "can you search for why my script is broken",
            env={
                "MAEZ_EVIDENCE_PRECEDENCE_ENABLED": "1",
                "MAEZ_SEARCH_AS_SENSE_ENABLED": "1",
            },
        )

        self.assertEqual(spec.external_sources, [ExternalSource.WEB_SEARCH])

    def test_explicit_fetch_about_not_working_owner_object_still_egresses(self):
        from core.dispatcher.spec import ExternalSource

        spec = self._emit_spec_for(
            "can you fetch pages about why my app is not working",
            env={
                "MAEZ_EVIDENCE_PRECEDENCE_ENABLED": "1",
                "MAEZ_SEARCH_AS_SENSE_ENABLED": "1",
            },
        )

        self.assertEqual(spec.external_sources, [ExternalSource.WEB_SEARCH])

    def test_owner_url_still_wins_over_complaint_guard(self):
        from core.dispatcher.spec import ExternalSource

        spec = self._emit_spec_for(
            "why can't you fetch https://example.com/release-notes",
            env={
                "MAEZ_EVIDENCE_PRECEDENCE_ENABLED": "1",
                "MAEZ_PAGE_READ_ENABLED": "1",
                "MAEZ_SEARCH_AS_SENSE_ENABLED": "1",
            },
        )

        self.assertEqual(spec.external_sources, [ExternalSource.FETCH_URL])

    def test_current_world_question_flag_off_preserves_prior_substrate_only_shape(self):
        from core.dispatcher.inventory import InventorySummary
        from core.dispatcher.layer0 import Layer0Dispatcher, load_archetype_index
        from core.dispatcher.spec import (
            CompositionHint,
            ExternalSource,
            InventoryWitness,
            ProvenanceFraming,
            SourceAvailability,
            SubstrateSource,
        )

        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "archetypes.md"
            _write_manifest(manifest)
            encoder = _FakeEncoder()
            index = load_archetype_index(
                manifest_path=manifest,
                cache_path=Path(tmp) / "cache.json",
                encoder=encoder,
            )
            inventory = InventorySummary(
                inventory_witness=InventoryWitness.PRESENT,
                source_availability={
                    SubstrateSource.TELEGRAM_SEMANTIC: SourceAvailability.EXECUTABLE_PRESENT,
                    SubstrateSource.ENTITY_INDEX: SourceAvailability.EXECUTABLE_PRESENT,
                    SubstrateSource.LIVED_EPISODES: SourceAvailability.EXECUTABLE_PRESENT,
                    ExternalSource.WEB_SEARCH: SourceAvailability.EXECUTABLE_PRESENT,
                },
                availability_limitations=[],
                generated_at=1.0,
            )

            with mock.patch.dict("os.environ", {}, clear=True):
                spec = Layer0Dispatcher(index=index, encoder=encoder).emit_spec(
                    "What's the latest llama.cpp release?",
                    surface="telegram",
                    inventory=inventory,
                )

        self.assertEqual(spec.external_sources, [])
        self.assertIn(SubstrateSource.TELEGRAM_SEMANTIC, spec.substrate_sources)
        self.assertEqual(spec.composition_hint, CompositionHint.SUBSTRATE_ONLY)
        self.assertEqual(
            spec.provenance_framing,
            ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION,
        )

    def test_owner_url_selects_fetch_url_fresh_only_under_flag(self):
        from core.dispatcher.inventory import InventorySummary
        from core.dispatcher.layer0 import Layer0Dispatcher, load_archetype_index
        from core.dispatcher.spec import (
            CompositionHint,
            ExternalSource,
            InventoryWitness,
            ProvenanceFraming,
            SourceAvailability,
            SubstrateSource,
        )

        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "archetypes.md"
            _write_manifest(manifest)
            encoder = _FakeEncoder()
            index = load_archetype_index(
                manifest_path=manifest,
                cache_path=Path(tmp) / "cache.json",
                encoder=encoder,
            )
            inventory = InventorySummary(
                inventory_witness=InventoryWitness.PRESENT,
                source_availability={
                    SubstrateSource.TELEGRAM_SEMANTIC: SourceAvailability.EXECUTABLE_PRESENT,
                    SubstrateSource.ENTITY_INDEX: SourceAvailability.EXECUTABLE_PRESENT,
                    SubstrateSource.LIVED_EPISODES: SourceAvailability.EXECUTABLE_PRESENT,
                    ExternalSource.WEB_SEARCH: SourceAvailability.EXECUTABLE_PRESENT,
                    ExternalSource.FETCH_URL: SourceAvailability.EXECUTABLE_PRESENT,
                },
                availability_limitations=[],
                generated_at=1.0,
            )

            with mock.patch.dict("os.environ", {"MAEZ_PAGE_READ_ENABLED": "1"}):
                spec = Layer0Dispatcher(index=index, encoder=encoder).emit_spec(
                    "check https://github.com/ggml-org/llama.cpp/releases - what's the latest release?",
                    surface="telegram_surface",
                    inventory=inventory,
                )

        self.assertEqual(spec.external_sources, [ExternalSource.FETCH_URL])
        self.assertEqual(spec.substrate_sources, [])
        self.assertEqual(spec.composition_hint, CompositionHint.FRESH_ONLY)
        self.assertEqual(spec.provenance_framing, ProvenanceFraming.FRESH_ONLY)

    def test_owner_url_flag_off_prior_composition(self):
        from core.dispatcher.inventory import InventorySummary
        from core.dispatcher.layer0 import Layer0Dispatcher, load_archetype_index
        from core.dispatcher.spec import (
            ExternalSource,
            InventoryWitness,
            SourceAvailability,
            SubstrateSource,
        )

        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "archetypes.md"
            _write_manifest(manifest)
            encoder = _FakeEncoder()
            index = load_archetype_index(
                manifest_path=manifest,
                cache_path=Path(tmp) / "cache.json",
                encoder=encoder,
            )
            inventory = InventorySummary(
                inventory_witness=InventoryWitness.PRESENT,
                source_availability={
                    SubstrateSource.TELEGRAM_SEMANTIC: SourceAvailability.EXECUTABLE_PRESENT,
                    SubstrateSource.ENTITY_INDEX: SourceAvailability.EXECUTABLE_PRESENT,
                    SubstrateSource.LIVED_EPISODES: SourceAvailability.EXECUTABLE_PRESENT,
                    ExternalSource.WEB_SEARCH: SourceAvailability.EXECUTABLE_PRESENT,
                    ExternalSource.FETCH_URL: SourceAvailability.EXECUTABLE_PRESENT,
                },
                availability_limitations=[],
                generated_at=1.0,
            )

            with mock.patch.dict("os.environ", {}, clear=True):
                spec = Layer0Dispatcher(index=index, encoder=encoder).emit_spec(
                    "check https://github.com/x/releases please",
                    surface="telegram_surface",
                    inventory=inventory,
                )

        self.assertNotIn(ExternalSource.FETCH_URL, spec.external_sources)

    def test_no_url_arm_inert_even_with_flag(self):
        from core.dispatcher.inventory import InventorySummary
        from core.dispatcher.layer0 import Layer0Dispatcher, load_archetype_index
        from core.dispatcher.spec import (
            ExternalSource,
            InventoryWitness,
            SourceAvailability,
            SubstrateSource,
        )

        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "archetypes.md"
            _write_manifest(manifest)
            encoder = _FakeEncoder()
            index = load_archetype_index(
                manifest_path=manifest,
                cache_path=Path(tmp) / "cache.json",
                encoder=encoder,
            )
            inventory = InventorySummary(
                inventory_witness=InventoryWitness.PRESENT,
                source_availability={
                    SubstrateSource.TELEGRAM_SEMANTIC: SourceAvailability.EXECUTABLE_PRESENT,
                    SubstrateSource.ENTITY_INDEX: SourceAvailability.EXECUTABLE_PRESENT,
                    SubstrateSource.LIVED_EPISODES: SourceAvailability.EXECUTABLE_PRESENT,
                    ExternalSource.WEB_SEARCH: SourceAvailability.EXECUTABLE_PRESENT,
                    ExternalSource.FETCH_URL: SourceAvailability.EXECUTABLE_PRESENT,
                },
                availability_limitations=[],
                generated_at=1.0,
            )

            with mock.patch.dict("os.environ", {"MAEZ_PAGE_READ_ENABLED": "1"}):
                spec = Layer0Dispatcher(index=index, encoder=encoder).emit_spec(
                    "check that page we talked about",
                    surface="telegram_surface",
                    inventory=inventory,
                )

        self.assertNotIn(ExternalSource.FETCH_URL, spec.external_sources)

    def test_current_world_question_does_not_treat_greeting_today_as_search(self):
        from core.dispatcher.inventory import InventorySummary
        from core.dispatcher.layer0 import Layer0Dispatcher, load_archetype_index
        from core.dispatcher.spec import (
            ExternalSource,
            InventoryWitness,
            SourceAvailability,
            SubstrateSource,
        )

        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "archetypes.md"
            _write_manifest(manifest)
            encoder = _FakeEncoder()
            index = load_archetype_index(
                manifest_path=manifest,
                cache_path=Path(tmp) / "cache.json",
                encoder=encoder,
            )
            inventory = InventorySummary(
                inventory_witness=InventoryWitness.PRESENT,
                source_availability={
                    SubstrateSource.TELEGRAM_SEMANTIC: SourceAvailability.EXECUTABLE_PRESENT,
                    SubstrateSource.ENTITY_INDEX: SourceAvailability.EXECUTABLE_PRESENT,
                    SubstrateSource.LIVED_EPISODES: SourceAvailability.EXECUTABLE_PRESENT,
                    ExternalSource.WEB_SEARCH: SourceAvailability.EXECUTABLE_PRESENT,
                },
                availability_limitations=[],
                generated_at=1.0,
            )

            spec = Layer0Dispatcher(index=index, encoder=encoder).emit_spec(
                "How are you today?",
                surface="telegram",
                inventory=inventory,
            )

        self.assertNotIn(ExternalSource.WEB_SEARCH, spec.external_sources)

    def test_mid_band_no_match_is_deterministic_and_marks_low_confidence(self):
        from core.dispatcher.inventory import InventorySummary
        from core.dispatcher.layer0 import (
            Layer0Dispatcher,
            ScoringThresholds,
            load_archetype_index,
        )
        from core.dispatcher.spec import (
            AvailabilityLimitation,
            ExternalSource,
            InventoryWitness,
            SourceAvailability,
            SubstrateSource,
        )

        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "archetypes.md"
            _write_manifest(manifest)
            encoder = _FakeEncoder()
            index = load_archetype_index(
                manifest_path=manifest,
                cache_path=Path(tmp) / "cache.json",
                encoder=encoder,
            )
            inventory = InventorySummary(
                inventory_witness=InventoryWitness.PRESENT,
                source_availability={
                    SubstrateSource.TELEGRAM_SEMANTIC: SourceAvailability.EXECUTABLE_PRESENT,
                    SubstrateSource.ENTITY_INDEX: SourceAvailability.EXECUTABLE_PRESENT,
                    SubstrateSource.LIVED_EPISODES: SourceAvailability.EXECUTABLE_PRESENT,
                    ExternalSource.WEB_SEARCH: SourceAvailability.EXECUTABLE_PRESENT,
                },
                availability_limitations=[],
                generated_at=1.0,
            )
            dispatcher = Layer0Dispatcher(
                index=index,
                encoder=encoder,
                thresholds=ScoringThresholds(
                    min_accept=0.99,
                    dominance_margin=0.08,
                    multi_match_delta=0.04,
                    no_match_below=0.1,
                ),
            )

            first = dispatcher.emit_spec("tell me about status", surface="telegram", inventory=inventory)
            second = dispatcher.emit_spec("tell me about status", surface="telegram", inventory=inventory)

        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertIn(AvailabilityLimitation.SCORING_LOW_CONFIDENCE, first.availability_limitations)
        self.assertEqual(
            first.substrate_sources,
            [
                SubstrateSource.TELEGRAM_SEMANTIC,
                SubstrateSource.ENTITY_INDEX,
                SubstrateSource.LIVED_EPISODES,
            ],
        )
        self.assertEqual(first.external_sources, [ExternalSource.WEB_SEARCH])

    def test_reddit_source_anchor_selects_reddit_substrate(self):
        from core.dispatcher.inventory import InventorySummary
        from core.dispatcher.layer0 import Layer0Dispatcher, load_archetype_index
        from core.dispatcher.spec import (
            ExternalSource,
            InventoryWitness,
            SourceAvailability,
            SubstrateSource,
        )

        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "archetypes.md"
            _write_manifest(manifest)
            encoder = _FakeEncoder()
            index = load_archetype_index(
                manifest_path=manifest,
                cache_path=Path(tmp) / "cache.json",
                encoder=encoder,
            )
            inventory = InventorySummary(
                inventory_witness=InventoryWitness.PRESENT,
                source_availability={
                    SubstrateSource.REDDIT_SOURCE: SourceAvailability.EXECUTABLE_PRESENT,
                    SubstrateSource.TELEGRAM_SEMANTIC: SourceAvailability.EXECUTABLE_PRESENT,
                    ExternalSource.WEB_SEARCH: SourceAvailability.EXECUTABLE_PRESENT,
                },
                availability_limitations=[],
                generated_at=1.0,
            )

            spec = Layer0Dispatcher(index=index, encoder=encoder).emit_spec(
                "Check Reddit then",
                surface="telegram",
                inventory=inventory,
            )

        self.assertEqual(spec.substrate_sources, [SubstrateSource.REDDIT_SOURCE])
        self.assertIn(SubstrateSource.REDDIT_SOURCE, spec.source_availability)

    def test_reddit_source_anchor_survives_explicit_substrate_class_win(self):
        from core.dispatcher.inventory import InventorySummary
        from core.dispatcher.layer0 import Layer0Dispatcher, load_archetype_index
        from core.dispatcher.spec import (
            InventoryWitness,
            SourceAvailability,
            SubstrateSource,
        )

        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "archetypes.md"
            _write_manifest(manifest)
            encoder = _RecallBiasedRedditEncoder()
            index = load_archetype_index(
                manifest_path=manifest,
                cache_path=Path(tmp) / "cache.json",
                encoder=encoder,
            )
            inventory = InventorySummary(
                inventory_witness=InventoryWitness.PRESENT,
                source_availability={
                    SubstrateSource.REDDIT_SOURCE: SourceAvailability.EXECUTABLE_PRESENT,
                    SubstrateSource.TELEGRAM_SEMANTIC: SourceAvailability.EXECUTABLE_PRESENT,
                },
                availability_limitations=[],
                generated_at=1.0,
            )

            spec = Layer0Dispatcher(index=index, encoder=encoder).emit_spec(
                "Check Reddit then",
                surface="telegram",
                inventory=inventory,
            )

        self.assertEqual(spec.substrate_sources, [SubstrateSource.REDDIT_SOURCE])

    def test_live_reddit_subreddit_anchor_selects_substrate_and_live_reddit(self):
        from core.dispatcher.inventory import InventorySummary
        from core.dispatcher.layer0 import Layer0Dispatcher, load_archetype_index
        from core.dispatcher.spec import (
            CompositionHint,
            ExternalSource,
            InventoryWitness,
            ProvenanceFraming,
            SourceAvailability,
            SubstrateSource,
        )

        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "archetypes.md"
            _write_manifest(manifest)
            encoder = _FakeEncoder()
            index = load_archetype_index(
                manifest_path=manifest,
                cache_path=Path(tmp) / "cache.json",
                encoder=encoder,
            )
            inventory = InventorySummary(
                inventory_witness=InventoryWitness.PRESENT,
                source_availability={
                    SubstrateSource.REDDIT_SOURCE: SourceAvailability.EXECUTABLE_PRESENT,
                    ExternalSource.LIVE_REDDIT: SourceAvailability.EXECUTABLE_PRESENT,
                    ExternalSource.WEB_SEARCH: SourceAvailability.EXECUTABLE_PRESENT,
                },
                availability_limitations=[],
                generated_at=1.0,
            )

            spec = Layer0Dispatcher(index=index, encoder=encoder).emit_spec(
                "Search r/LocalLLaMA right now",
                surface="telegram",
                inventory=inventory,
            )

        self.assertEqual(spec.substrate_sources, [SubstrateSource.REDDIT_SOURCE])
        self.assertEqual(spec.external_sources, [ExternalSource.LIVE_REDDIT])
        self.assertEqual(spec.composition_hint, CompositionHint.PARALLEL)
        self.assertEqual(
            spec.provenance_framing,
            ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES,
        )

    def test_subreddit_anchor_without_search_verb_selects_live_reddit_hybrid(self):
        from core.dispatcher.inventory import InventorySummary
        from core.dispatcher.layer0 import Layer0Dispatcher, load_archetype_index
        from core.dispatcher.spec import (
            ExternalSource,
            InventoryWitness,
            SourceAvailability,
            SubstrateSource,
        )

        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "archetypes.md"
            _write_manifest(manifest)
            encoder = _FakeEncoder()
            index = load_archetype_index(
                manifest_path=manifest,
                cache_path=Path(tmp) / "cache.json",
                encoder=encoder,
            )
            inventory = InventorySummary(
                inventory_witness=InventoryWitness.PRESENT,
                source_availability={
                    SubstrateSource.REDDIT_SOURCE: SourceAvailability.EXECUTABLE_PRESENT,
                    ExternalSource.LIVE_REDDIT: SourceAvailability.EXECUTABLE_PRESENT,
                    ExternalSource.WEB_SEARCH: SourceAvailability.EXECUTABLE_PRESENT,
                },
                availability_limitations=[],
                generated_at=1.0,
            )

            spec = Layer0Dispatcher(index=index, encoder=encoder).emit_spec(
                "What's on r/LocalLLaMA?",
                surface="telegram",
                inventory=inventory,
            )

        self.assertEqual(spec.substrate_sources, [SubstrateSource.REDDIT_SOURCE])
        self.assertEqual(spec.external_sources, [ExternalSource.LIVE_REDDIT])

    def test_non_subreddit_reddit_anchor_stays_substrate_only(self):
        from core.dispatcher.inventory import InventorySummary
        from core.dispatcher.layer0 import Layer0Dispatcher, load_archetype_index
        from core.dispatcher.spec import (
            ExternalSource,
            InventoryWitness,
            SourceAvailability,
            SubstrateSource,
        )

        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "archetypes.md"
            _write_manifest(manifest)
            encoder = _FakeEncoder()
            index = load_archetype_index(
                manifest_path=manifest,
                cache_path=Path(tmp) / "cache.json",
                encoder=encoder,
            )
            inventory = InventorySummary(
                inventory_witness=InventoryWitness.PRESENT,
                source_availability={
                    SubstrateSource.REDDIT_SOURCE: SourceAvailability.EXECUTABLE_PRESENT,
                    ExternalSource.LIVE_REDDIT: SourceAvailability.EXECUTABLE_PRESENT,
                    ExternalSource.WEB_SEARCH: SourceAvailability.EXECUTABLE_PRESENT,
                },
                availability_limitations=[],
                generated_at=1.0,
            )

            spec = Layer0Dispatcher(index=index, encoder=encoder).emit_spec(
                "What's going on on Reddit?",
                surface="telegram",
                inventory=inventory,
            )

        self.assertEqual(spec.substrate_sources, [SubstrateSource.REDDIT_SOURCE])
        self.assertEqual(spec.external_sources, [])

    def test_generic_fresh_search_selects_web_search_not_live_reddit(self):
        from core.dispatcher.inventory import InventorySummary
        from core.dispatcher.layer0 import Layer0Dispatcher, load_archetype_index
        from core.dispatcher.spec import (
            ExternalSource,
            InventoryWitness,
            SourceAvailability,
        )

        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "archetypes.md"
            _write_manifest(manifest)
            encoder = _FakeEncoder()
            index = load_archetype_index(
                manifest_path=manifest,
                cache_path=Path(tmp) / "cache.json",
                encoder=encoder,
            )
            inventory = InventorySummary(
                inventory_witness=InventoryWitness.PRESENT,
                source_availability={
                    ExternalSource.LIVE_REDDIT: SourceAvailability.EXECUTABLE_PRESENT,
                    ExternalSource.WEB_SEARCH: SourceAvailability.EXECUTABLE_PRESENT,
                },
                availability_limitations=[],
                generated_at=1.0,
            )

            spec = Layer0Dispatcher(index=index, encoder=encoder).emit_spec(
                "Search Qwen online",
                surface="telegram",
                inventory=inventory,
            )

        self.assertEqual(spec.external_sources, [ExternalSource.WEB_SEARCH])


class CurrentWorldRequestTest(unittest.TestCase):
    """Bare current-world fragments must trigger fresh search.

    The predicate used to require question shape, so 'news about Anthropic' and
    'latest Elon news' fell through to SUBSTRATE_ONLY and the brain answered (and
    confabulated current specifics) from memory. Now any utterance carrying a
    current-world marker counts — question-shaped or a bare fragment — while the
    conversational 'how are you today' greeting stays excluded and explicit-memory
    forms are still blocked at the emit_spec branch.
    """

    def _emit(self, utterance):
        import tempfile
        from pathlib import Path
        from unittest import mock

        from core.dispatcher.inventory import InventorySummary
        from core.dispatcher.layer0 import Layer0Dispatcher, load_archetype_index
        from core.dispatcher.spec import (
            ExternalSource,
            InventoryWitness,
            SourceAvailability,
            SubstrateSource,
        )

        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "archetypes.md"
            _write_manifest(manifest)
            encoder = _FakeEncoder()
            index = load_archetype_index(
                manifest_path=manifest,
                cache_path=Path(tmp) / "cache.json",
                encoder=encoder,
            )
            inventory = InventorySummary(
                inventory_witness=InventoryWitness.PRESENT,
                source_availability={
                    SubstrateSource.TELEGRAM_SEMANTIC: SourceAvailability.EXECUTABLE_PRESENT,
                    SubstrateSource.ENTITY_INDEX: SourceAvailability.EXECUTABLE_PRESENT,
                    SubstrateSource.LIVED_EPISODES: SourceAvailability.EXECUTABLE_PRESENT,
                    ExternalSource.WEB_SEARCH: SourceAvailability.EXECUTABLE_PRESENT,
                },
                availability_limitations=[],
                generated_at=1.0,
            )
            with mock.patch.dict("os.environ", {"MAEZ_SEARCH_AS_SENSE_ENABLED": "1"}):
                return Layer0Dispatcher(index=index, encoder=encoder).emit_spec(
                    utterance, surface="telegram", inventory=inventory
                )

    # --- predicate-level (fast, direct) ---

    def test_predicate_bare_subject_news_fragment_is_current_world(self):
        from core.dispatcher.layer0 import _is_current_world_request

        self.assertTrue(_is_current_world_request("news about Anthropic"))

    def test_predicate_bare_latest_person_news_fragment_is_current_world(self):
        from core.dispatcher.layer0 import _is_current_world_request

        self.assertTrue(_is_current_world_request("latest Elon news"))

    def test_predicate_question_form_still_current_world(self):
        from core.dispatcher.layer0 import _is_current_world_request

        self.assertTrue(_is_current_world_request("what's today's news?"))

    def test_predicate_conversational_today_excluded(self):
        from core.dispatcher.layer0 import _is_current_world_request

        self.assertFalse(_is_current_world_request("how are you today?"))

    def test_predicate_requires_a_current_world_marker(self):
        from core.dispatcher.layer0 import _is_current_world_request

        # No news/latest/today/etc. marker -> not a current-world request.
        self.assertFalse(_is_current_world_request("tell me about your day"))

    # --- emit_spec-level (the spec the dispatcher actually emits) ---

    def test_bare_subject_news_selects_web_search(self):
        from core.dispatcher.spec import ExternalSource

        spec = self._emit("news about Anthropic")
        self.assertIn(ExternalSource.WEB_SEARCH, spec.external_sources)

    def test_bare_latest_person_news_selects_web_search(self):
        from core.dispatcher.spec import ExternalSource

        spec = self._emit("latest Elon news")
        self.assertIn(ExternalSource.WEB_SEARCH, spec.external_sources)

    def test_generic_news_question_still_selects_web_search(self):
        from core.dispatcher.spec import ExternalSource

        spec = self._emit("what's today's news?")
        self.assertIn(ExternalSource.WEB_SEARCH, spec.external_sources)

    def test_greeting_today_still_no_web_search(self):
        from core.dispatcher.spec import ExternalSource

        spec = self._emit("How are you today?")
        self.assertNotIn(ExternalSource.WEB_SEARCH, spec.external_sources)

    def test_explicit_memory_news_stays_substrate_only(self):
        from core.dispatcher.spec import CompositionHint, ExternalSource

        # 'what do you remember' is explicit memory; even with a current-world marker
        # the emit_spec branch (and not explicit_memory) keeps it substrate-only.
        spec = self._emit("what do you remember about the latest news?")
        self.assertNotIn(ExternalSource.WEB_SEARCH, spec.external_sources)
        self.assertEqual(spec.composition_hint, CompositionHint.SUBSTRATE_ONLY)


if __name__ == "__main__":
    unittest.main()
