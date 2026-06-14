"""Dependency-free sd_notify(3) datagram emitter for the Maez daemon.

systemd `Type=notify` units stay in `activating` until the service tells the
service manager it is actually up by sending a `READY=1` datagram to the socket
named in ``$NOTIFY_SOCKET``. Until then `systemctl is-active` reports
`activating`, not `active`. This module is the single, importable place that
writes that datagram — it deliberately pulls in nothing from the heavy daemon so
tests (and any other organ) can import and exercise it on its own.

Honesty contract: this only *reports* readiness; the caller decides *when* it is
true (after the backend probe passes AND the health socket binds). The notify is
a no-op when there is no notify socket (running outside systemd, in a sandbox, or
under the flag turned off), and it never raises — a failed datagram must never
take down a daemon that is otherwise serving.

Flag: MAEZ_SYSTEMD_NOTIFY — strict {1,true,yes,on}, DEFAULT-ON when unset
(mirrors core/infra/env_flags.strict_env_flag, but default-on instead of
default-off, so absence of the flag keeps systemd's readiness contract honest).
"""
from __future__ import annotations

import os
import socket
from typing import Callable, Mapping, Optional

# Mirror the one truthy set for the whole house (core/infra/env_flags.TRUTHY).
_TRUTHY = frozenset({"1", "true", "yes", "on"})

_FLAG = "MAEZ_SYSTEMD_NOTIFY"


def systemd_notify_enabled(environ: Optional[Mapping[str, str]] = None) -> bool:
    """Return True unless ``MAEZ_SYSTEMD_NOTIFY`` is explicitly set to an off value.

    DEFAULT-ON: when the flag is unset (or empty), notify is enabled. When set,
    only ``1/true/yes/on`` keep it on; ``0/false/no/off`` (or anything else) turn
    it off. This is the inverse default of the house ``strict_env_flag`` but uses
    the same strict truthy set, so a stray ``"0"`` reliably disables it.
    """
    env = os.environ if environ is None else environ
    raw = env.get(_FLAG, "")
    raw = (raw or "").strip().lower()
    if raw == "":
        return True
    return raw in _TRUTHY


def _resolve_socket_path(raw: str) -> bytes:
    """Translate a ``$NOTIFY_SOCKET`` value into the bytes used by ``sendto``.

    systemd uses a leading ``@`` to mean an abstract namespace socket, which in
    the Linux sockaddr_un encoding is a leading NUL byte. A leading ``/`` is an
    ordinary filesystem path and is passed through unchanged.
    """
    if raw.startswith("@"):
        return b"\0" + raw[1:].encode("utf-8")
    return raw.encode("utf-8")


def sd_notify(
    state: str,
    *,
    environ: Optional[Mapping[str, str]] = None,
    socket_factory: Optional[Callable[[], socket.socket]] = None,
) -> bool:
    """Send one ``state`` datagram to ``$NOTIFY_SOCKET``; return whether it was sent.

    Returns ``False`` and sends nothing when ``NOTIFY_SOCKET`` is unset/empty, or
    when :func:`systemd_notify_enabled` is False. Any :class:`OSError` from the
    socket (missing socket, permission, closed manager) is swallowed and reported
    as ``False`` — emitting readiness must never crash a serving daemon.

    ``socket_factory`` is a seam for tests: a zero-arg callable returning a
    connected/unconnected ``socket.socket``. When omitted a real
    ``AF_UNIX/SOCK_DGRAM`` socket is created.
    """
    env = os.environ if environ is None else environ

    raw = env.get("NOTIFY_SOCKET", "")
    if not raw:
        # No socket -> nothing is waiting on us. Honor the flag's no-op intent:
        # when there is no socket (non-systemd / sandbox) the flag's only job is
        # to keep this a no-op, which it already is. Always returns False here.
        return False

    # A present NOTIFY_SOCKET means systemd is ACTUALLY waiting on READY=1 under
    # Type=notify. FORCE-ON: send the datagram regardless of MAEZ_SYSTEMD_NOTIFY.
    # If the flag could suppress the signal here the daemon would serve fine but
    # systemd would kill it at TimeoutStartSec -> crash loop. The flag still
    # meaningfully disables the (otherwise no-op) emit when there is no socket /
    # we are not running under systemd — handled by the early return above.

    payload = state.encode("utf-8") if isinstance(state, str) else state
    addr = _resolve_socket_path(raw)

    sock: Optional[socket.socket] = None
    try:
        if socket_factory is not None:
            sock = socket_factory()
        else:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM | socket.SOCK_CLOEXEC)
        sock.sendto(payload, addr)
        return True
    except OSError:
        return False
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
