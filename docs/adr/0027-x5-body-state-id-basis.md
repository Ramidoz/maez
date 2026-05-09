# ADR 0027: X.5 Body State ID Basis

**Status:** Accepted  
**Date:** 2026-05-09

## Context

Slice X.5 records mechanical body-state diagnostics from existing
runtime introspection. These records must be readable across hardware
succession without exposing host fingerprints, service labels, ports,
logs, command output, or illness-coded narration.

## Decision

Body-state service handles use a content-free typed-handle hash basis:

`BODY_STATE_SERVICE_HASH_PREFIX = "x5.body_state.service.v1|service_name:<name>|kind:<service|hardware|interval>"`

`BODY_STATE_ID_BASIS_VERSION = 1`

`SERVICE_HANDLE_BASIS_VERSION = 1`

The hash basis explicitly excludes host UUIDs, MAC addresses,
hostnames, kernel versions, ports, PIDs, CPU model strings, serials,
argv, logs, command output, and prose summaries.

`MISSED_INTERVAL_CAUSE_BASIS` is locked as:

`("organ_alive_source_silent", "organ_broken", "unknown")`

Changing the hash basis, mechanical-enum vocabulary,
`MISSED_INTERVAL_CAUSE_BASIS`, forbidden-fields list, or read-path lock
requires ADR because these are covenant properties, not implementation
details.

## Consequences

X.5 can longitudinally observe Maez's body without turning telemetry
into health narration, host fingerprinting, or product-style control.
Future narration, if it ever cites body-state records, must cite record
ids and hashed source-command handles rather than importing labels or
log content.
