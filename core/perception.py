"""
Maez Perception Module — Collects system state into a single context snapshot.
Importable by the daemon, callable every cycle.
"""

import json
import subprocess
import time
from datetime import datetime
from typing import TypedDict

import psutil


class GpuStats(TypedDict, total=False):
    utilization_pct: float
    memory_used_mb: float
    memory_total_mb: float
    temperature_c: float


class PerceptionSnapshot(TypedDict):
    timestamp: str
    day_of_week: str
    hour: int
    time_of_day: str
    cpu: dict
    ram: dict
    gpu: GpuStats | None
    disk: dict
    network: dict
    top_processes_cpu: list[dict]
    top_processes_mem: list[dict]


# Module-level state for network throughput calculation
_last_net = {"time": 0.0, "bytes_sent": 0, "bytes_recv": 0}


def _time_of_day(hour: int) -> str:
    if 5 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    elif 17 <= hour < 21:
        return "evening"
    return "night"


def _collect_cpu() -> dict:
    overall = psutil.cpu_percent(interval=1)
    per_core = psutil.cpu_percent(interval=0, percpu=True)
    freq = psutil.cpu_freq()

    result = {
        "percent": overall,
        "per_core": per_core,
        "core_count": psutil.cpu_count(logical=True),
        "freq_mhz": round(freq.current, 1) if freq else None,
    }

    try:
        temps = psutil.sensors_temperatures()
        if "coretemp" in temps:
            readings = temps["coretemp"]
            result["temperature_c"] = max(r.current for r in readings)
        elif temps:
            first_key = next(iter(temps))
            readings = temps[first_key]
            result["temperature_c"] = max(r.current for r in readings)
    except (AttributeError, StopIteration):
        pass

    return result


def _collect_ram() -> dict:
    mem = psutil.virtual_memory()
    return {
        "total_gb": round(mem.total / (1024 ** 3), 1),
        "used_gb": round(mem.used / (1024 ** 3), 1),
        "available_gb": round(mem.available / (1024 ** 3), 1),
        "percent": mem.percent,
    }


def _collect_gpu() -> GpuStats | None:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return None

        parts = result.stdout.strip().split(", ")
        return {
            "utilization_pct": float(parts[0]),
            "memory_used_mb": float(parts[1]),
            "memory_total_mb": float(parts[2]),
            "temperature_c": float(parts[3]),
        }
    except (FileNotFoundError, subprocess.TimeoutExpired, IndexError, ValueError):
        return None


def _collect_disk() -> dict:
    disks = {}
    for mount in ["/", "/home"]:
        try:
            usage = psutil.disk_usage(mount)
            disks[mount] = {
                "total_gb": round(usage.total / (1024 ** 3), 1),
                "used_gb": round(usage.used / (1024 ** 3), 1),
                "free_gb": round(usage.free / (1024 ** 3), 1),
                "percent": usage.percent,
            }
        except FileNotFoundError:
            pass
    return disks


def _collect_network() -> dict:
    global _last_net

    counters = psutil.net_io_counters()
    now = time.time()
    elapsed = now - _last_net["time"] if _last_net["time"] > 0 else 0

    sent_bytes = counters.bytes_sent
    recv_bytes = counters.bytes_recv

    if elapsed > 0:
        sent_rate = (sent_bytes - _last_net["bytes_sent"]) / elapsed
        recv_rate = (recv_bytes - _last_net["bytes_recv"]) / elapsed
    else:
        sent_rate = 0.0
        recv_rate = 0.0

    _last_net = {"time": now, "bytes_sent": sent_bytes, "bytes_recv": recv_bytes}

    return {
        "bytes_sent_total": sent_bytes,
        "bytes_recv_total": recv_bytes,
        "send_rate_mbps": round(sent_rate * 8 / 1_000_000, 2),
        "recv_rate_mbps": round(recv_rate * 8 / 1_000_000, 2),
    }


def _collect_top_processes(by: str, n: int = 10) -> list[dict]:
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            info = p.info
            if info["cpu_percent"] is not None and info["memory_percent"] is not None:
                procs.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    key = "cpu_percent" if by == "cpu" else "memory_percent"
    procs.sort(key=lambda p: p[key], reverse=True)

    return [
        {
            "pid": p["pid"],
            "name": p["name"],
            "cpu_pct": round(p["cpu_percent"], 1),
            "mem_pct": round(p["memory_percent"], 1),
        }
        for p in procs[:n]
    ]


def snapshot() -> PerceptionSnapshot:
    """Collect a full system state snapshot."""
    now = datetime.now().astimezone()
    hour = now.hour

    return {
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "day_of_week": now.strftime("%A"),
        "hour": hour,
        "time_of_day": _time_of_day(hour),
        "cpu": _collect_cpu(),
        "ram": _collect_ram(),
        "gpu": _collect_gpu(),
        "disk": _collect_disk(),
        "network": _collect_network(),
        "top_processes_cpu": _collect_top_processes("cpu"),
        "top_processes_mem": _collect_top_processes("mem"),
    }


def format_snapshot(snap: PerceptionSnapshot) -> str:
    """Format a snapshot into a human-readable string for prompt injection."""
    lines = [
        f"=== System State: {snap['timestamp']} ({snap['day_of_week']} {snap['time_of_day']}) ===",
        "",
        f"CPU: {snap['cpu']['percent']}% overall across {snap['cpu']['core_count']} cores"
        + (f" @ {snap['cpu']['freq_mhz']} MHz" if snap['cpu'].get('freq_mhz') else "")
        + (f", {snap['cpu']['temperature_c']}°C" if snap['cpu'].get('temperature_c') else ""),
        f"RAM: {snap['ram']['used_gb']}/{snap['ram']['total_gb']} GB ({snap['ram']['percent']}%)",
    ]

    gpu = snap.get("gpu")
    if gpu:
        lines.append(
            f"GPU: {gpu['utilization_pct']}% util, "
            f"{gpu['memory_used_mb']:.0f}/{gpu['memory_total_mb']:.0f} MB VRAM, "
            f"{gpu['temperature_c']}°C"
        )

    lines.append("")
    for mount, info in snap["disk"].items():
        lines.append(f"Disk {mount}: {info['used_gb']}/{info['total_gb']} GB ({info['percent']}%)")

    net = snap["network"]
    lines.append(f"Network: ↑ {net['send_rate_mbps']} Mbps, ↓ {net['recv_rate_mbps']} Mbps")

    lines.append("")
    lines.append("Top processes (CPU):")
    for p in snap["top_processes_cpu"][:5]:
        lines.append(f"  {p['name']:<25} CPU: {p['cpu_pct']:>5.1f}%  MEM: {p['mem_pct']:>5.1f}%")

    lines.append("Top processes (MEM):")
    for p in snap["top_processes_mem"][:5]:
        lines.append(f"  {p['name']:<25} CPU: {p['cpu_pct']:>5.1f}%  MEM: {p['mem_pct']:>5.1f}%")

    return "\n".join(lines)


if __name__ == "__main__":
    snap = snapshot()
    print(format_snapshot(snap))
    print("\n--- Raw JSON ---")
    print(json.dumps(snap, indent=2))
