import json
import numpy as np
import tempfile
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
