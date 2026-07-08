#!/usr/bin/env python3
"""Maez ScreenCast capture helper.

This runs on the system Python when it talks to the desktop portal, because
the Maez venv lacks gi/Gst/Gio. Those imports stay lazy so unit tests can
exercise the non-live rails in the venv.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import uuid

TOKEN_PATH = os.path.expanduser("~/.config/maez/screencast_restore_token")
CURTAIN_PATH = os.path.expanduser("~/.config/maez/screen_perception.curtain")
TEMP_PREFIX = "maez-screencast-"
PORTAL_BUS_NAME = "org.freedesktop.portal.Desktop"
PORTAL_OBJECT_PATH = "/org/freedesktop/portal/desktop"
PORTAL_REQUEST_PATH = "/org/freedesktop/portal/desktop/request"
SCREENCAST_IFACE = "org.freedesktop.portal.ScreenCast"
REQUEST_IFACE = "org.freedesktop.portal.Request"
PORTAL_TIMEOUT_MS = 120_000
GST_TIMEOUT_NS = 30 * 1_000_000_000


def _result(
    status: str,
    temp_path: str | None = None,
    bytes_: int = 0,
    duration_ms: int = 0,
    error_class: str = "",
) -> dict:
    """Build the only stdout contract this helper may emit."""
    return {
        "status": status,
        "temp_path": temp_path,
        "bytes": int(bytes_),
        "duration_ms": int(duration_ms),
        "error_class": error_class,
    }


def _emit(result: dict) -> None:
    sys.stdout.write(json.dumps(result) + "\n")
    sys.stdout.flush()


def _curtain_drawn() -> bool:
    return os.path.exists(CURTAIN_PATH)


def _save_token(token: str) -> None:
    os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
    fd = os.open(TOKEN_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(token)
            f.write("\n")
    finally:
        os.chmod(TOKEN_PATH, 0o600)


def _load_token() -> str | None:
    try:
        with open(TOKEN_PATH, encoding="utf-8") as f:
            token = f.read().strip()
    except FileNotFoundError:
        return None
    return token or None


class _StageError(Exception):
    """Content-free stage classification for live capture failures."""

    def __init__(self, stage: str):
        super().__init__(stage)
        self.stage = stage


def _safe_unlink(path: str | None) -> None:
    try:
        if path and os.path.exists(path):
            os.unlink(path)
    except Exception:
        pass


def _debug_enabled() -> bool:
    return os.environ.get("MAEZ_SCREENCAST_DEBUG", "").strip().lower() not in (
        "",
        "0",
        "false",
        "no",
        "off",
    )


def _debug(message: str) -> None:
    if _debug_enabled():
        sys.stderr.write(f"{message}\n")
        sys.stderr.flush()


def revoke() -> dict:
    """Hard revoke: withdraw the eye by deleting the token and drawing curtain."""
    try:
        os.unlink(TOKEN_PATH)
    except FileNotFoundError:
        pass
    os.makedirs(os.path.dirname(CURTAIN_PATH), exist_ok=True)
    with open(CURTAIN_PATH, "a", encoding="utf-8"):
        pass
    return _result(status="curtain_drawn")


def capture() -> dict:
    """Capture one frame, unless the privacy curtain is drawn."""
    if _curtain_drawn():
        return _result(status="curtain_drawn")
    return _capture_live()


def _capture_live() -> dict:
    t0 = time.time()
    tmp = tempfile.mktemp(prefix=TEMP_PREFIX, suffix=".png")
    try:
        restore_token = _load_token()
        # The portal binds the ScreenCast session's lifetime to the D-Bus
        # client that created it. `session` MUST stay referenced until AFTER
        # the frame is grabbed — otherwise GNOME tears the session down and
        # the pipewire node disappears mid-pipeline ("target not found").
        session = _portal_screencast_session(restore_token)
        node_id, fd, new_token = session.node_id, session.fd, session.new_token
        if node_id is None or fd is None:
            _safe_unlink(tmp)
            return _result(
                status="needs_grant",
                duration_ms=int((time.time() - t0) * 1000),
            )
        try:
            _grab_one_frame_pipewire(fd, node_id, tmp)
        except _StageError as exc:
            # COVENANT: a background capture must NEVER re-open an interactive
            # consent dialog. On a token-backed failure we drop the (possibly
            # poisoned) token so a future OWNER-INITIATED grant starts clean,
            # but we do NOT silently re-prompt — the eye degrades and waits
            # for a deliberate re-grant. Perception consent is a ceremony the
            # owner initiates, not a demand Maez makes on an idle timer.
            if exc.stage == "gst" and restore_token:
                _debug("restore-token capture failed; dropping token, NOT re-prompting")
                _safe_unlink(TOKEN_PATH)
            raise
        finally:
            session.close()
        size = os.path.getsize(tmp) if os.path.exists(tmp) else 0
        if size <= 0:
            _safe_unlink(tmp)
            return _result(
                status="capture_failed",
                error_class="gst",
                duration_ms=int((time.time() - t0) * 1000),
            )
        if new_token:
            _save_token(new_token)
        return _result(
            status="ok",
            temp_path=tmp,
            bytes_=size,
            duration_ms=int((time.time() - t0) * 1000),
        )
    except _StageError as exc:
        _safe_unlink(tmp)
        return _result(
            status="capture_failed",
            error_class=exc.stage,
            duration_ms=int((time.time() - t0) * 1000),
        )
    except Exception:
        _safe_unlink(tmp)
        return _result(
            status="capture_failed",
            error_class="portal",
            duration_ms=int((time.time() - t0) * 1000),
        )


def _portal_proxy():
    # Lazy import: system python has gi/Gio; the Maez venv does not.
    import gi  # noqa: F401

    from gi.repository import Gio

    return Gio.DBusProxy.new_for_bus_sync(
        Gio.BusType.SESSION,
        Gio.DBusProxyFlags.NONE,
        None,
        PORTAL_BUS_NAME,
        PORTAL_OBJECT_PATH,
        SCREENCAST_IFACE,
        None,
    )


def _request_token(prefix: str) -> str:
    return f"maez_{prefix}_{uuid.uuid4().hex}"


def _request_path(connection, handle_token: str) -> str:
    unique_name = connection.get_unique_name()
    if not unique_name:
        raise _StageError("portal")
    sender = unique_name[1:] if unique_name.startswith(":") else unique_name
    sender = sender.replace(".", "_")
    return f"{PORTAL_REQUEST_PATH}/{sender}/{handle_token}"


def _unwrap_variant(value):
    if hasattr(value, "unpack"):
        return value.unpack()
    return value


def _call_portal(proxy, method: str, params, *, stage: str = "portal"):
    from gi.repository import Gio

    try:
        return proxy.call_sync(
            method,
            params,
            Gio.DBusCallFlags.NONE,
            PORTAL_TIMEOUT_MS,
            None,
        )
    except Exception as exc:
        name = getattr(exc, "matches", None)
        if callable(name):
            # Keep the emitted error content-free; classify only.
            raise _StageError(stage) from None
        raise _StageError(stage) from None


def _wait_request_response(connection, request_path: str, call):
    from gi.repository import Gio, GLib

    loop = GLib.MainLoop()
    state: dict = {"seen": False, "response": 2, "results": {}, "timeout_fired": False}

    def _on_response(_conn, _sender, _path, _iface, _signal, params, _data):
        response, results = params.unpack()
        state["seen"] = True
        state["response"] = response
        state["results"] = results or {}
        loop.quit()

    sub_id = connection.signal_subscribe(
        PORTAL_BUS_NAME,
        REQUEST_IFACE,
        "Response",
        request_path,
        None,
        Gio.DBusSignalFlags.NONE,
        _on_response,
        None,
    )

    def _on_timeout():
        if not state["seen"]:
            state["timeout_fired"] = True
            loop.quit()
        return False

    timeout_id = GLib.timeout_add(PORTAL_TIMEOUT_MS, _on_timeout)
    try:
        call()
        loop.run()
    finally:
        connection.signal_unsubscribe(sub_id)
        if not state["timeout_fired"]:
            try:
                GLib.source_remove(timeout_id)
            except Exception:
                pass

    if not state["seen"]:
        raise _StageError("timeout")
    if state["response"] == 1:
        raise _StageError("permission_denied")
    if state["response"] != 0:
        raise _StageError("portal")
    return state["results"]


def _portal_request(
    proxy,
    method: str,
    params,
    *,
    handle_token: str,
    stage: str = "portal",
) -> dict:
    connection = proxy.get_connection()
    request_path = _request_path(connection, handle_token)

    def _call():
        out = _call_portal(proxy, method, params, stage=stage)
        returned_handle = out.unpack()[0]
        if returned_handle != request_path:
            raise _StageError("portal")

    return _wait_request_response(connection, request_path, _call)


class _PortalSession:
    """Holds the live portal proxy so the ScreenCast session (and its
    pipewire node) survives until the caller closes it AFTER capture."""

    def __init__(self, proxy, node_id, fd, new_token):
        self._proxy = proxy
        self.node_id = node_id
        self.fd = fd
        self.new_token = new_token

    def close(self) -> None:
        # Releasing the proxy lets GNOME close the portal session; only safe
        # once the frame is grabbed and the pipewire fd is done with.
        self._proxy = None


def _portal_screencast_session(restore_token: str | None) -> "_PortalSession":
    """Open a portal ScreenCast session and return it LIVE (proxy retained).

    The returned _PortalSession keeps the D-Bus proxy referenced; the caller
    MUST call .close() only after the frame grab completes.
    """
    from gi.repository import GLib

    proxy = _portal_proxy()

    create_token = _request_token("create")
    create_options = {
        "handle_token": GLib.Variant("s", create_token),
        "session_handle_token": GLib.Variant("s", _request_token("session")),
    }
    create_results = _portal_request(
        proxy,
        "CreateSession",
        GLib.Variant("(a{sv})", (create_options,)),
        handle_token=create_token,
    )
    session_handle = _unwrap_variant(create_results.get("session_handle"))
    if not session_handle:
        raise _StageError("portal")

    select_token = _request_token("select")
    select_options = {
        "handle_token": GLib.Variant("s", select_token),
        "types": GLib.Variant("u", 1),  # MONITOR
        "multiple": GLib.Variant("b", False),
        "cursor_mode": GLib.Variant("u", 1),  # hidden
        "persist_mode": GLib.Variant("u", 2),  # until explicitly revoked
    }
    if restore_token:
        select_options["restore_token"] = GLib.Variant("s", restore_token)
    _portal_request(
        proxy,
        "SelectSources",
        GLib.Variant("(oa{sv})", (session_handle, select_options)),
        handle_token=select_token,
    )

    start_token = _request_token("start")
    start_options = {"handle_token": GLib.Variant("s", start_token)}
    start_results = _portal_request(
        proxy,
        "Start",
        GLib.Variant("(osa{sv})", (session_handle, "", start_options)),
        handle_token=start_token,
    )
    streams = _unwrap_variant(start_results.get("streams")) or []
    new_token = _unwrap_variant(start_results.get("restore_token"))
    if not streams:
        return _PortalSession(proxy, None, None, new_token)
    first_stream = streams[0]
    node_id = _unwrap_variant(first_stream[0])

    try:
        fd_result, fd_list = proxy.call_with_unix_fd_list_sync(
            "OpenPipeWireRemote",
            GLib.Variant("(oa{sv})", (session_handle, {})),
            0,
            30_000,
            None,
            None,
        )
        fd_handle = fd_result.unpack()[0]
        fd = fd_list.get(fd_handle)
    except Exception:
        raise _StageError("pipewire") from None
    return _PortalSession(proxy, node_id, fd, new_token)


def _grab_one_frame_pipewire(fd: int, node_id: int, tmp: str) -> None:
    import gi

    gi.require_version("Gst", "1.0")
    from gi.repository import Gst

    Gst.init(None)
    pipeline = None
    try:
        pipeline_string = (
            "pipewiresrc fd={fd} path={node} num-buffers=1 "
            "! videoconvert ! pngenc ! filesink location={tmp}"
        ).format(
            fd=int(fd),
            node=int(node_id),
            tmp=tmp,
        )
        _debug(f"pipewire node_id={int(node_id)} fd={int(fd)}")
        _debug(f"gst pipeline={pipeline_string}")
        pipeline = Gst.parse_launch(
            pipeline_string
        )
        bus = pipeline.get_bus()
        pipeline.set_state(Gst.State.PLAYING)
        message = bus.timed_pop_filtered(
            GST_TIMEOUT_NS,
            Gst.MessageType.ERROR | Gst.MessageType.EOS,
        )
        if message is None:
            raise _StageError("timeout")
        if message.type == Gst.MessageType.ERROR:
            if _debug_enabled():
                err, debug = message.parse_error()
                src = message.src.get_name() if message.src else ""
                _debug(f"gst error element={src} message={err.message}")
                if debug:
                    _debug(f"gst debug={debug}")
            raise _StageError("gst")
    except _StageError:
        raise
    except Exception:
        raise _StageError("gst") from None
    finally:
        if pipeline is not None:
            pipeline.set_state(Gst.State.NULL)
        try:
            os.close(fd)
        except Exception:
            pass


def safe_capture() -> dict:
    """Last-resort wrapper: never leak raw exception text or tracebacks."""
    try:
        return capture()
    except Exception:
        return _result(status="capture_failed", error_class="gst")


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if "--revoke" in argv:
        _emit(revoke())
        return
    _emit(safe_capture())


if __name__ == "__main__":
    main()
