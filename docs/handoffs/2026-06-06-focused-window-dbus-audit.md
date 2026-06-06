# Focused Window D-Bus Audit — Active-Window Route v0

Date: 2026-06-06
Slice: Active-Window Route v0 (Full Lens — Slice B)
Extension: `flexagoon/focused-window-dbus`
Pinned commit: `5ff336fac73b34deaf83f32772e8478885fa4925`
Audited file: `extension.js`
Audited file SHA-256: `de7ab71d0c22a3c43b8acefda75cab44b55b6db5585fc858ce04025149a02ee7`

## Verdict

Pass for owner review: the pinned source exposes a read-only focused-window nerve. Codex must not install or enable the extension; installation and enablement remain owner-authorized after this audit.

## D-Bus Surface

- Bus name: `org.gnome.Shell`
- Object path: `/org/gnome/shell/extensions/FocusedWindow`
- Interface: `org.gnome.shell.extensions.FocusedWindow`
- Method: `Get`
- Signal: `FocusChanged`

## Audit Notes

- No network or egress surface found: no `fetch`, `XMLHttpRequest`, or `Soup` usage in `extension.js`.
- No write/action D-Bus methods found: the declared D-Bus schema exposes only `Get` and `FocusChanged`.
- No window actuation method names found as callable surfaces: no `Activate` or `activate`.
- The strings `moveable`, `resizeable`, and `canclose` appear only as returned metadata fields from `Get`; they are not methods and Maez's parser discards them.
- The extension uses `Gio.DBusExportedObject.wrapJSObject` to export the declared D-Bus schema on the session bus.

## Boundary

This audit records that the pinned third-party code is suitable to review as a read-only compositor nerve. It is not an install instruction, and it does not authorize enabling the extension. The owner audit/install/enable breath remains separate from Codex implementation.
