# Private Thoughts Signal Registry

**Introduced:** S1a.1, 2026-05-13

This table defines the 2026 meaning of the closed vocabularies used by
`memory/private_thoughts.db`. It exists so a future reader can interpret
old private-thought records without this chat or an implementation diff.

## Versions

| field | value | meaning |
|---|---|---|
| `envelope_version` | `1.0` | S1a contextual-integrity envelope: source, subject, consent tier, retention, allowed flows, optional extra metadata. |
| `schema_version` | `1.0` | S1a.1 split fields: producer identity, detailed forensic kind, coarse behavior class, sensitivity, and state. |
| `PRAGMA user_version` | `101` | SQLite migration marker for S1a.1 private-thoughts hardening. Older code must not downgrade a higher value. |

## Closed Vocabularies

| enum | value | 2026 meaning |
|---|---|---|
| `AllowedFlow` | `private_reader` | Behavior-safe aggregate reader may count the row if all other fields validate. |
| `AllowedFlow` | `audit_trace` | Operator forensic/audit tools may dereference handles after writing an audit row. |
| `AllowedFlow` | `crisis_channel` | Reserved route for future crisis-channel producer/consumer work. Not active in S1a.1. |
| `AllowedFlow` | `rupture_repair` | Reserved route for future rupture-repair producer/consumer work. Not active in S1a.1. |
| `ConsentTier` | `owner_private` | Owner-bond private material; never public/multi-user. |
| `RetentionRule` | `until_reviewed` | Hold until operator/Maez review logic decides it no longer needs active attention. |
| `RetentionRule` | `until_routed` | Hold until a future routed channel has handled the signal. |
| `RetentionRule` | `until_repaired` | Hold until a future rupture-repair lifecycle resolves it. |
| `RetentionRule` | `until_resolved` | Hold until a future generic resolution lifecycle resolves it. |
| `SurfaceSensitivity` | `forensic_sensitive` | Detailed producer/forensic metadata; not behavior-facing. |
| `SurfaceSensitivity` | `behavior_safe_coarse` | Aggregate behavior output only; no raw text, handles, or detailed kinds. |
| `SignalState` | `active` | Eligible for behavior aggregation if the row validates. |
| `SignalState` | `resolved` | Durable but not behavior-active. |

## Signal Registry

| signal_kind | producer_id | signal_class | allowed producer contract | introduced | deprecated | merge/split note |
|---|---|---|---|---|---|---|
| `audit_held` | `audit_rail` | `audit_awareness` | Audit rail may record a held internal concern. | `1.0` | | Initial S1a class. |
| `reasoning_residue` | `reasoning_residue` | `reasoning_residue` | Reasoning-residue producer may record leftover internal state. | `1.0` | | Initial S1a class. |
| `urge_held` | `urge_monitor` | `urge_pressure` | Urge monitor may record a held impulse that should not become action directly. | `1.0` | | Initial S1a class. |
| `dream_fragment` | `dream_cycle` | `dream_residue` | Dream cycle may record private residue from offline synthesis. | `1.0` | | Initial S1a class. |
| `self_wondering` | `self_wondering` | `self_observation` | Self-wondering producer may record private self-observation. | `1.0` | | Initial S1a class. |
| `rupture_unhealed` | `rupture_detector` | `bond_repair` | Rupture detector may record unresolved repair pressure. | `1.0` | | Reserved for S1b+ behavior wiring. |
| `crisis_signal_held` | `crisis_detector` | `crisis_routing` | Crisis detector may record a held crisis-routing signal. | `1.0` | | Reserved for crisis-channel work. |
| `soul_objection_forming` | `soul_objection_detector` | `soul_boundary` | Soul-objection detector may record a forming boundary objection. | `1.0` | | Reserved for soul-boundary work. |

## Legacy Mapping

S1a rows used `provenance` as both producer identity and signal kind.
S1a.1 preserves `provenance` as `legacy_provenance`.

| legacy source | S1a.1 mapping |
|---|---|
| known legacy `provenance` in `SignalKind` | maps to `signal_kind`; `signal_class` derives from the registry above. |
| legacy `context.source` in `ProducerId` | maps to `producer_id` only during the one-time migration. |
| unknown legacy `provenance` | remains forensic-readable as legacy data; does not surface to behavior. |
| unsupported future `envelope_version` / `schema_version` | skipped, never rewritten by older code. |

Behavior readers receive only `signal_class`, count/state, and
`behavior_safe_coarse` sensitivity. Detailed `signal_kind`,
`producer_id`, raw text, and dereferenceable handles are forensic-only.
