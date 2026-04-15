"""
Maez Presto Body Bridge

Minimal host-side bridge for talking to a Pimoroni Presto over the
MicroPython serial REPL. This keeps the first version intentionally
small: detect the board, inspect it, push files, and launch a chosen
script on next boot.
"""

from __future__ import annotations

import ast
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import serial
from serial.tools import list_ports


PRESTO_VID = 0x2E8A
PRESTO_RUNTIME_PID = 0x0005
PRESTO_BOOT_PID = 0x000F
PROMPT = b">>> "
RAW_PROMPT = b">"


class PrestoBridgeError(RuntimeError):
    pass


@dataclass
class PrestoPort:
    device: str
    description: str
    vid: Optional[int]
    pid: Optional[int]
    serial_number: Optional[str]


class PrestoBridge:
    def __init__(self, port: str | None = None, baudrate: int = 115200, timeout: float = 1.0):
        self.port = port or self.detect_runtime_port()
        self.baudrate = baudrate
        self.timeout = timeout

    @staticmethod
    def detect_runtime_port() -> str:
        for port in list_ports.comports():
            if port.vid == PRESTO_VID and port.pid == PRESTO_RUNTIME_PID:
                return port.device
            if "MicroPython" in (port.description or "") and port.device.startswith("/dev/ttyACM"):
                return port.device
        raise PrestoBridgeError("No Presto runtime serial port detected")

    @staticmethod
    def bootloader_present() -> bool:
        for port in list_ports.comports():
            if port.vid == PRESTO_VID and port.pid == PRESTO_BOOT_PID:
                return True
        return False

    @staticmethod
    def runtime_port_info() -> Optional[PrestoPort]:
        for port in list_ports.comports():
            if port.vid == PRESTO_VID and port.pid == PRESTO_RUNTIME_PID:
                return PrestoPort(
                    device=port.device,
                    description=port.description or "",
                    vid=port.vid,
                    pid=port.pid,
                    serial_number=port.serial_number,
                )
        return None

    def _open(self) -> serial.Serial:
        try:
            return serial.Serial(self.port, self.baudrate, timeout=self.timeout, write_timeout=self.timeout)
        except serial.SerialException as exc:
            raise PrestoBridgeError(f"Could not open {self.port}: {exc}") from exc

    def _interrupt_to_prompt(self, ser: serial.Serial) -> None:
        ser.write(b"\r\x03\x03")
        time.sleep(0.25)
        ser.reset_input_buffer()
        ser.reset_output_buffer()

    def _read_until_prompt(self, ser: serial.Serial, timeout: float = 4.0) -> str:
        deadline = time.time() + timeout
        chunks = bytearray()
        while time.time() < deadline:
            data = ser.read(512)
            if data:
                chunks.extend(data)
                if PROMPT in chunks:
                    break
            else:
                time.sleep(0.05)
        return chunks.decode("utf-8", "replace")

    def _read_until(self, ser: serial.Serial, marker: bytes, timeout: float = 4.0) -> bytes:
        deadline = time.time() + timeout
        chunks = bytearray()
        while time.time() < deadline:
            data = ser.read(512)
            if data:
                chunks.extend(data)
                if marker in chunks:
                    return bytes(chunks)
            else:
                time.sleep(0.05)
        raise PrestoBridgeError(f"Timed out waiting for marker {marker!r}")

    def exec_snippet(self, code: str, timeout: float = 6.0) -> str:
        with self._open() as ser:
            time.sleep(0.8)
            self._interrupt_to_prompt(ser)
            ser.write(b"\x01")
            self._read_until(ser, RAW_PROMPT, timeout=2.0)
            ser.write(code.rstrip().encode("utf-8"))
            ser.write(b"\x04")
            packet = self._read_until(ser, b"\x04\x04>", timeout=timeout)
            ser.write(b"\x02")
            if not packet.startswith(b"OK"):
                raise PrestoBridgeError(f"Unexpected raw REPL response: {packet!r}")
            body = packet[2:]
            stdout, remainder = body.split(b"\x04", 1)
            stderr, _prompt = remainder.split(b"\x04", 1)
            if stderr.strip():
                raise PrestoBridgeError(stderr.decode("utf-8", "replace"))
            return stdout.decode("utf-8", "replace")

    def eval_expr(self, expr: str) -> str:
        marker = "__MAEZ_EVAL__"
        out = self.exec_snippet(
            f"print('{marker}')\nprint(repr({expr}))\nprint('{marker}')",
            timeout=4.0,
        )
        parts = out.split(marker)
        if len(parts) < 3:
            raise PrestoBridgeError(f"Could not parse eval output: {out}")
        middle = parts[1].strip().splitlines()
        if not middle:
            return ""
        return middle[-1].strip()

    def list_root(self) -> list[str]:
        raw = self.eval_expr("os.listdir()")
        return ast.literal_eval(raw)

    def device_info(self) -> dict:
        snippet = """
import os, sys
print('__MAEZ_INFO__')
print(repr({
    'version': sys.version,
    'platform': sys.platform,
    'implementation': tuple(getattr(sys, 'implementation', ())),
    'uname': tuple(os.uname()),
    'root': os.listdir(),
}))
print('__MAEZ_INFO__')
"""
        out = self.exec_snippet(snippet, timeout=6.0)
        parts = out.split("__MAEZ_INFO__")
        if len(parts) < 3:
            raise PrestoBridgeError(f"Could not parse device info: {out}")
        payload_lines = [line.strip() for line in parts[1].splitlines() if line.strip()]
        return ast.literal_eval(payload_lines[-1])

    def write_file(self, remote_path: str, content: str) -> str:
        payload = repr(content)
        snippet = f"""
data = {payload}
with open({remote_path!r}, 'w') as f:
    f.write(data)
print('WROTE', {remote_path!r}, len(data))
"""
        return self.exec_snippet(snippet, timeout=10.0)

    def read_file(self, remote_path: str) -> str:
        raw = self.eval_expr(f"open({remote_path!r}).read()")
        return ast.literal_eval(raw)

    def set_launch(self, script_name: str) -> str:
        if not script_name.endswith(".py"):
            raise PrestoBridgeError("launch target must be a .py file")
        snippet = f"""
import os
if 'ramfs' not in os.listdir():
    raise OSError('ramfs missing')
with open('/ramfs/launch.txt', 'w') as f:
    f.write({script_name!r})
print('LAUNCH_SET', {script_name!r})
"""
        return self.exec_snippet(snippet, timeout=6.0)

    def soft_reset(self) -> str:
        with self._open() as ser:
            time.sleep(0.5)
            self._interrupt_to_prompt(ser)
            ser.write(b"\x04")
            time.sleep(0.4)
            return self._read_until_prompt(ser, timeout=6.0)

    def install_repo_app(self, local_path: str | os.PathLike[str], remote_name: str | None = None) -> str:
        source = Path(local_path)
        if not source.exists():
            raise PrestoBridgeError(f"Local file not found: {source}")
        target = remote_name or source.name
        content = source.read_text()
        return self.write_file(target, content)
