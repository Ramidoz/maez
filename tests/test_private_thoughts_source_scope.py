from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from core.cognition.lean_idle_heartbeat import HEARTBEAT_VERSION
from core.infra.private_thoughts import (
    AllowedFlow,
    ConsentTier,
    PrivateThoughts,
    ProducerId,
    RetentionRule,
    SignalKind,
)


class RecentBySourceTest(unittest.TestCase):
    def _store(self) -> PrivateThoughts:
        tmp = Path(tempfile.mkdtemp()) / "private_thoughts.db"
        return PrivateThoughts(db_path=tmp)

    def _add(
        self,
        store: PrivateThoughts,
        *,
        source: str,
        content: str,
        consent: str = ConsentTier.OWNER_PRIVATE,
        flows: tuple[str, ...] = (AllowedFlow.PRIVATE_READER, AllowedFlow.AUDIT_TRACE),
        phase: str = "gestation",
    ) -> int:
        return store.record_signal(
            content=content,
            signal_kind=SignalKind.SELF_WONDERING,
            producer_id=ProducerId.SELF_WONDERING,
            source=source,
            subject="maez_internal_state",
            consent_tier=consent,
            retention=RetentionRule.UNTIL_REVIEWED,
            allowed_flows=flows,
            context_extra={},
            memory_phase=phase,
        )

    def _rewrite_consent(self, store: PrivateThoughts, thought_id: int, consent: str) -> None:
        row = store.get_thought(thought_id)
        self.assertIsNotNone(row)
        context = dict(row["context"])
        context["consent_tier"] = consent
        conn = sqlite3.connect(store.db_path)
        try:
            conn.execute(
                "UPDATE private_thoughts SET context_json = ? WHERE thought_id = ?",
                (json.dumps(context), thought_id),
            )
            conn.commit()
        finally:
            conn.close()

    def test_excludes_newest_foreign_rows(self) -> None:
        store = self._store()
        self._add(store, source=HEARTBEAT_VERSION, content="my own note")
        self._add(store, source="daemon_cycle.reasoning_residue", content="residue newer")
        self._add(store, source="clinical_boundary", content="crisis newest")

        rows = store.recent_by_source(HEARTBEAT_VERSION, limit=5)

        self.assertEqual([row["content"] for row in rows], ["my own note"])

    def test_surfaces_heartbeat_older_than_global_newest_20(self) -> None:
        store = self._store()
        self._add(store, source=HEARTBEAT_VERSION, content="old heartbeat note")
        for i in range(25):
            self._add(store, source="daemon_cycle.reasoning_residue", content=f"residue {i}")

        rows = store.recent_by_source(HEARTBEAT_VERSION, limit=2)

        self.assertEqual([row["content"] for row in rows], ["old heartbeat note"])

    def test_default_spans_phase_and_explicit_phase_still_filters(self) -> None:
        store = self._store()
        self._add(store, source=HEARTBEAT_VERSION, content="gestation note", phase="gestation")
        self._add(store, source=HEARTBEAT_VERSION, content="lived note", phase="lived")
        self._add(
            store,
            source=HEARTBEAT_VERSION,
            content="no private reader",
            flows=(AllowedFlow.AUDIT_TRACE,),
        )

        rows = store.recent_by_source(HEARTBEAT_VERSION, limit=5)
        self.assertEqual([row["content"] for row in rows], ["lived note", "gestation note"])

        rows = store.recent_by_source(HEARTBEAT_VERSION, limit=5, phase="gestation")
        self.assertEqual([row["content"] for row in rows], ["gestation note"])

    def test_rejects_wrong_consent_even_with_right_source(self) -> None:
        store = self._store()
        thought_id = self._add(store, source=HEARTBEAT_VERSION, content="wrong consent")
        self._rewrite_consent(store, thought_id, "not_owner_private")

        self.assertEqual(store.recent_by_source(HEARTBEAT_VERSION, limit=5), [])

    def test_respects_limit_newest_first(self) -> None:
        store = self._store()
        for i in range(4):
            self._add(store, source=HEARTBEAT_VERSION, content=f"note {i}")

        rows = store.recent_by_source(HEARTBEAT_VERSION, limit=2)

        self.assertEqual([row["content"] for row in rows], ["note 3", "note 2"])
