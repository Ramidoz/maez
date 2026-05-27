import unittest


class DispatcherInventoryTests(unittest.TestCase):
    def test_inventory_summary_uses_cached_source_registry(self):
        from core.dispatcher.inventory import InventoryEntry, InventoryRegistry
        from core.dispatcher.spec import (
            InventoryWitness,
            SourceAvailability,
            SubstrateSource,
        )

        calls = {"count": 0, "cursor": 0}

        def cursor_query():
            calls["cursor"] += 1
            return "cursor-1"

        def count_query():
            calls["count"] += 1
            return 3

        registry = InventoryRegistry(
            [
                InventoryEntry(
                    source=SubstrateSource.REDDIT_SOURCE,
                    backing_store="memory/db/raw/chroma.sqlite3",
                    cache_key="reddit-source",
                    invalidation_signal="rowid:reddit-source",
                    max_staleness_s=60,
                    count_query=count_query,
                    cursor_query=cursor_query,
                )
            ],
            clock=lambda: 1000.0,
        )

        first = registry.summarize([SubstrateSource.REDDIT_SOURCE])
        second = registry.summarize([SubstrateSource.REDDIT_SOURCE])

        self.assertEqual(first.inventory_witness, InventoryWitness.PRESENT)
        self.assertEqual(second.inventory_witness, InventoryWitness.PRESENT)
        self.assertEqual(
            second.source_availability[SubstrateSource.REDDIT_SOURCE],
            SourceAvailability.EXECUTABLE_PRESENT,
        )
        self.assertEqual(second.availability_limitations, [])
        self.assertEqual(calls["cursor"], 2)
        self.assertEqual(calls["count"], 1)

    def test_inventory_unknown_fallback_when_cursor_or_count_fails(self):
        from core.dispatcher.inventory import InventoryEntry, InventoryRegistry
        from core.dispatcher.spec import (
            AvailabilityLimitation,
            InventoryWitness,
            SourceAvailability,
            SubstrateSource,
        )

        registry = InventoryRegistry(
            [
                InventoryEntry(
                    source=SubstrateSource.TELEGRAM_SEMANTIC,
                    backing_store="memory/db/raw/chroma.sqlite3",
                    cache_key="telegram-semantic",
                    invalidation_signal="collection-version:telegram",
                    max_staleness_s=60,
                    count_query=lambda: 1,
                    cursor_query=lambda: (_ for _ in ()).throw(RuntimeError("db locked")),
                )
            ]
        )

        summary = registry.summarize([SubstrateSource.TELEGRAM_SEMANTIC])

        self.assertEqual(summary.inventory_witness, InventoryWitness.UNKNOWN)
        self.assertEqual(
            summary.source_availability[SubstrateSource.TELEGRAM_SEMANTIC],
            SourceAvailability.EXECUTABLE_UNKNOWN,
        )
        self.assertEqual(summary.availability_limitations, [AvailabilityLimitation.INVENTORY_UNKNOWN])

    def test_reserved_and_privacy_gated_sources_never_execute_inventory_count(self):
        from core.dispatcher.inventory import InventoryEntry, InventoryRegistry
        from core.dispatcher.spec import (
            AvailabilityLimitation,
            InventoryWitness,
            SourceAvailability,
            SubstrateSource,
        )

        calls = {"private_count": 0}

        def private_count():
            calls["private_count"] += 1
            return 2

        registry = InventoryRegistry(
            [
                InventoryEntry(
                    source=SubstrateSource.PRIVATE_THOUGHTS,
                    backing_store="memory/private_thoughts.db",
                    cache_key="private-thoughts",
                    invalidation_signal="bounded-reader",
                    max_staleness_s=60,
                    count_query=private_count,
                    cursor_query=lambda: "private-cursor",
                    privacy_gate=lambda: False,
                ),
                InventoryEntry.reserved(
                    SubstrateSource.LIVED_GRAPH,
                    backing_store="memory/lived_graph.db",
                    cache_key="lived-graph",
                    invalidation_signal="G11-not-landed",
                ),
            ]
        )

        summary = registry.summarize(
            [SubstrateSource.PRIVATE_THOUGHTS, SubstrateSource.LIVED_GRAPH]
        )

        self.assertEqual(summary.inventory_witness, InventoryWitness.MIXED)
        self.assertEqual(
            summary.source_availability[SubstrateSource.PRIVATE_THOUGHTS],
            SourceAvailability.PRIVACY_GATED,
        )
        self.assertEqual(
            summary.source_availability[SubstrateSource.LIVED_GRAPH],
            SourceAvailability.RESERVED_UNAVAILABLE,
        )
        self.assertEqual(
            summary.availability_limitations,
            [
                AvailabilityLimitation.PRIVACY_GATED,
                AvailabilityLimitation.RESERVED_SOURCE_UNAVAILABLE,
            ],
        )
        self.assertEqual(calls["private_count"], 0)

    def test_unimplemented_default_fallback_sources_are_reserved(self):
        from core.dispatcher.inventory import InventoryRegistry
        from core.dispatcher.spec import (
            AvailabilityLimitation,
            SourceAvailability,
            SubstrateSource,
        )

        summary = InventoryRegistry().summarize(
            [
                SubstrateSource.TELEGRAM_SEMANTIC,
                SubstrateSource.ENTITY_INDEX,
                SubstrateSource.LIVED_EPISODES,
            ]
        )

        self.assertEqual(
            summary.source_availability[SubstrateSource.TELEGRAM_SEMANTIC],
            SourceAvailability.EXECUTABLE_UNKNOWN,
        )
        self.assertEqual(
            summary.source_availability[SubstrateSource.ENTITY_INDEX],
            SourceAvailability.RESERVED_UNAVAILABLE,
        )
        self.assertEqual(
            summary.source_availability[SubstrateSource.LIVED_EPISODES],
            SourceAvailability.RESERVED_UNAVAILABLE,
        )
        self.assertIn(
            AvailabilityLimitation.RESERVED_SOURCE_UNAVAILABLE,
            summary.availability_limitations,
        )


if __name__ == "__main__":
    unittest.main()
