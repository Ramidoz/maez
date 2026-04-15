# Presto Hardware Module

This directory makes the Pimoroni Presto a distinct Maez hardware module instead of a loose set of one-off scripts.

## What lives here

- `bridge.py`: host-side serial bridge for talking to the board over MicroPython raw REPL
- `body_state_server.py`: tiny LAN relay that exposes Maez body state to the Presto
- `device_apps/`: board-facing apps that can be pushed onto the Presto
- `device_manifest.json`: a small identity/ownership record so future hardware modules can follow the same pattern

## Compatibility

The existing entry points in `scripts/` and `skills/` still work. They now either import from, or mirror, this module so we do not break the current bridge flow while the rest of Maez is still evolving.

## Why this matters

Maez is growing beyond a single machine. Treating Presto as `hardware/presto` gives it a stable home, makes its role legible, and creates a repeatable pattern for later modules such as cameras, displays, sensors, or other embodied surfaces.
