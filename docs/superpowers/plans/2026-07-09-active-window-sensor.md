# Slice 4 — Active-Window Sensor Implementation Plan

**Goal:** Land a dormant, deterministic GNOME/Wayland active-window identity
and geometry sensor under gate criteria v1.1, while closing the discovered
privacy-curtain fallback bypass.

**Boundary:** No capture or admission from the new sensor, no daemon/cognition/
memory/prompt wiring, no extension mutation, no service start, and no change to
`MAEZ_SCREEN_PERCEPTION`.

## Task 1 — Close the curtain side door

1. Add a loop-level RED proving a drawn curtain invokes none of the capture
   candidates, including GNOME D-Bus and portal fallbacks.
2. Add a shared pause/curtain privacy gate and route the capture loop through
   it. Retain the ScreenCast helper's internal curtain check as defense in
   depth.
3. Re-run the focused capture and perception suites.

## Task 2 — Share the CropBox contract

1. Add a RED pinning one frozen `CropBox` type for Slice 3 and Slice 4.
2. Move the frozen right/bottom-exclusive value to a neutral geometry module
   and re-export it from the Slice 3 harness.

## Task 3 — Add the dormant active-window sensor

1. Add REDs for single-snapshot exclusion, missing-class exclusion, typed
   compositor refusal, degenerate/off-screen/cross-display refusal, HiDPI
   floor/ceil conversion, schema version, and receipt omission rules.
2. Add a read-only system-Python/Gio compositor probe using the already-audited
   FocusedWindow D-Bus `Get` method once and Mutter DisplayConfig solely for
   display identity, bounds, native dimensions, scale, and serial.
3. Add the frozen sensor contract and validation. Keep title ephemeral and
   exclusion-only. Publish no production caller.

## Task 4 — Structural and containment verification

1. Add structural REDs proving no title-bearing memory/prompt/receipt path, no
   capture/service/env mutation, and no daemon/cognition import of the sensor.
2. Run focused Slice 4, Slice 3, ambient, screen-perception, capture, and flag-0
   suites plus lint.
3. Run independent code/privacy review and address all material findings.
4. Re-witness exact live flag value and `llama-vision.service` inactive/disabled
   without changing either.

