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
        node_id, fd, new_token = _portal_screencast_session(_load_token())
        if new_token:
            _save_token(new_token)
        if node_id is None or fd is None:
            _safe_unlink(tmp)
            return _result(
                status="needs_grant",
                duration_ms=int((time.time() - t0) * 1000),
            )
        _grab_one_frame_pipewire(fd, node_id, tmp)
        size = os.path.getsize(tmp) if os.path.exists(tmp) else 0
        if size <= 0:
            _safe_unlink(tmp)
            return _result(
                status="capture_failed",
                error_class="gst",
                duration_ms=int((time.time() - t0) * 1000),
            )
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
            error_class="gst",
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


def _wait_request_response(request_path: str) -> dict:
    from gi.repository import Gio, GLib

    connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
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


def _portal_request(proxy, method: str, params, *, stage: str = "portal") -> dict:
    out = _call_portal(proxy, method, params, stage=stage)
    handle = out.unpack()[0]
    return _wait_request_response(handle)


def _portal_screencast_session(restore_token: str | None):
    """Return (node_id, pipewire_fd, refreshed_restore_token)."""
    from gi.repository import GLib

    proxy = _portal_proxy()

    create_options = {
        "handle_token": GLib.Variant("s", _request_token("create")),
        "session_handle_token": GLib.Variant("s", _request_token("session")),
    }
    create_results = _portal_request(
        proxy,
        "CreateSession",
        GLib.Variant("(a{sv})", (create_options,)),
    )
    session_handle = _unwrap_variant(create_results.get("session_handle"))
    if not session_handle:
        raise _StageError("portal")

    select_options = {
        "handle_token": GLib.Variant("s", _request_token("select")),
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
    )

    start_options = {"handle_token": GLib.Variant("s", _request_token("start"))}
    start_results = _portal_request(
        proxy,
        "Start",
        GLib.Variant("(osa{sv})", (session_handle, "", start_options)),
    )
    streams = _unwrap_variant(start_results.get("streams")) or []
    new_token = _unwrap_variant(start_results.get("restore_token"))
    if not streams:
        return None, None, new_token
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
    return node_id, fd, new_token


def _grab_one_frame_pipewire(fd: int, node_id: int, tmp: str) -> None:
    import gi

    gi.require_version("Gst", "1.0")
    from gi.repository import Gst

    Gst.init(None)
    pipeline = None
    try:
        pipeline = Gst.parse_launch(
            "pipewiresrc fd={fd} path={node} num-buffers=1 "
            "! videoconvert ! pngenc ! filesink location={tmp}".format(
                fd=int(fd),
                node=int(node_id),
                tmp=tmp,
            )
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
