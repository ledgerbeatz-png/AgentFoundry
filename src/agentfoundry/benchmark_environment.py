"""Read-only benchmark guards. Never terminate a server we did not create."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import socket
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .hardware import detect_hardware
from .runtime import RuntimeProfile


def command_output(args: list[str]) -> str:
    result = subprocess.run(args, capture_output=True, text=True, timeout=10,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "System inspection failed")
    return result.stdout.strip()


def server_pids() -> list[int]:
    if os.name == "nt":
        rows = csv.reader(io.StringIO(command_output(["tasklist", "/FO", "CSV", "/NH"])))
        return [int(row[1]) for row in rows if row and row[0].lower() == "llama-server.exe"]
    rows = command_output(["ps", "-eo", "pid=,comm="]).splitlines()
    return [int(row.split()[0]) for row in rows
            if len(row.split()) >= 2 and Path(row.split()[1]).name == "llama-server"]


@dataclass
class MemorySnapshot:
    available_ram_gb: float | None
    free_vram_mb: float | None
    gpu_identity: str = ""


def memory_snapshot() -> MemorySnapshot:
    ram = None
    try:
        if os.name == "nt":
            raw = command_output(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                                  "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory"])
            ram = float(raw) / 1024 ** 2
        else:
            lines = Path("/proc/meminfo").read_text().splitlines()
            ram = float(next(line.split()[1] for line in lines if line.startswith("MemAvailable:"))) / 1024 ** 2
    except (OSError, ValueError, StopIteration, RuntimeError, subprocess.SubprocessError):
        pass
    vram = None
    identity = ""
    try:
        raw = command_output(["nvidia-smi", "--query-gpu=uuid,name,memory.total,driver_version,memory.free",
                              "--format=csv,noheader,nounits"])
        rows = list(csv.reader(io.StringIO(raw)))
        vram = sum(float(row[-1]) for row in rows)
        identity = json.dumps([row[:-1] for row in rows])
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        pass
    return MemorySnapshot(ram, vram, identity)


def assert_idle(port: int) -> None:
    pids = server_pids()
    if pids:
        raise RuntimeError("Close existing llama-server processes before tuning. PIDs: " + ", ".join(map(str, pids)))
    with socket.socket() as sock:
        if os.name == "nt":
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError as exc:
            raise RuntimeError(f"Benchmark port {port} is already in use.") from exc


def wait_for_memory(baseline: MemorySnapshot, log, timeout: float = 30) -> MemorySnapshot:
    deadline = time.monotonic() + timeout
    consecutive = 0
    while True:
        current = memory_snapshot()
        ram_ok = (baseline.available_ram_gb is None or
                  current.available_ram_gb is not None and
                  current.available_ram_gb >= max(1.0, baseline.available_ram_gb - 1.0))
        gpu_ok = (baseline.free_vram_mb is None or
                  current.free_vram_mb is not None and
                  current.free_vram_mb >= baseline.free_vram_mb - 256)
        consecutive = consecutive + 1 if ram_ok and gpu_ok else 0
        if consecutive >= 2:
            return current
        if time.monotonic() >= deadline:
            raise RuntimeError("RAM/VRAM did not return to the preflight baseline. Retest required.")
        log("Waiting for RAM/VRAM to settle…")
        time.sleep(1)


def fingerprint(profile: RuntimeProfile, executable: str, hardware=None, memory=None) -> str:
    hardware = hardware or detect_hardware()
    memory = memory or memory_snapshot()
    def identity(path: str) -> dict:
        resolved = Path(path).resolve(strict=True)
        stat = resolved.stat()
        return {"path": os.path.normcase(str(resolved)), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    config = asdict(profile)
    for key in ("gpu_layers", "host", "port"):
        config.pop(key)
    runtime = identity(executable)
    # DLL replacement changes the effective llama.cpp runtime even if the EXE stays the same.
    libraries = [identity(str(path)) for path in sorted(Path(executable).resolve().parent.glob("*.dll"))]
    payload = {"protocol": 2, "hardware": asdict(hardware), "gpu_driver": memory.gpu_identity,
               "model": identity(profile.model_path), "runtime": identity(executable), "config": config}
    payload["runtime"] = {"executable": runtime, "libraries": libraries}
    payload["environment"] = {key: value for key, value in os.environ.items()
                              if key.startswith(("LLAMA_", "GGML_", "CUDA_"))}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
