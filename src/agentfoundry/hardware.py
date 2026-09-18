from __future__ import annotations

import ctypes
import json
import os
import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class HardwareInfo:
    os_name: str
    os_version: str
    architecture: str
    cpu: str
    ram_gb: float
    gpu: str = "Unknown"
    vram_gb: float = 0.0

    @property
    def summary(self) -> str:
        return (
            f"{self.cpu} · {self.ram_gb:.1f} GB RAM · "
            f"{self.gpu} · {self.vram_gb:.1f} GB VRAM"
        )


@dataclass
class RuntimeRecommendation:
    context: int
    gpu_layers: int
    kv_cache_k: str = "q4_0"
    kv_cache_v: str = "q4_0"
    reason: str = ""


def _windows_ram_gb() -> float:
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MEMORYSTATUSEX()
    status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return 0.0
    return status.ullTotalPhys / (1024 ** 3)


def _unix_ram_gb() -> float:
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        pages = os.sysconf("SC_PHYS_PAGES")
        return (page_size * pages) / (1024 ** 3)
    except (AttributeError, ValueError, OSError):
        return 0.0


def _detect_windows_gpu() -> tuple[str, float]:
    command = [
        "powershell",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        (
            "Get-CimInstance Win32_VideoController | "
            "Select-Object Name,AdapterRAM | ConvertTo-Json -Compress"
        ),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0 or not result.stdout.strip():
            return "Unknown", 0.0

        payload = json.loads(result.stdout)
        adapters = payload if isinstance(payload, list) else [payload]
        best_name = "Unknown"
        best_vram = 0.0

        for adapter in adapters:
            name = str(adapter.get("Name") or "Unknown")
            raw = adapter.get("AdapterRAM") or 0
            try:
                vram = float(raw) / (1024 ** 3)
            except (TypeError, ValueError):
                vram = 0.0
            if vram >= best_vram:
                best_name = name
                best_vram = vram

        return best_name, best_vram
    except Exception:
        return "Unknown", 0.0


def detect_hardware() -> HardwareInfo:
    system = platform.system()
    ram_gb = _windows_ram_gb() if system == "Windows" else _unix_ram_gb()

    cpu = platform.processor().strip()
    if not cpu:
        cpu = os.environ.get("PROCESSOR_IDENTIFIER", "Unknown CPU")

    gpu = "Unknown"
    vram_gb = 0.0
    if system == "Windows":
        gpu, vram_gb = _detect_windows_gpu()

    return HardwareInfo(
        os_name=system,
        os_version=platform.release(),
        architecture=platform.machine(),
        cpu=cpu,
        ram_gb=ram_gb,
        gpu=gpu,
        vram_gb=vram_gb,
    )


def recommend_runtime(info: HardwareInfo, model_path: str = "") -> RuntimeRecommendation:
    # Conservative defaults: AgentFoundry should prefer a stable launch over a
    # maximal offload that can exhaust VRAM.
    if info.ram_gb >= 24:
        context = 65536
    elif info.ram_gb >= 16:
        context = 65536
    elif info.ram_gb >= 12:
        context = 32768
    else:
        context = 16384

    if info.vram_gb >= 16:
        gpu_layers = 48
    elif info.vram_gb >= 12:
        gpu_layers = 40
    elif info.vram_gb >= 8:
        gpu_layers = 28
    elif info.vram_gb >= 5.5:
        gpu_layers = 20
    elif info.vram_gb >= 4:
        gpu_layers = 12
    elif info.vram_gb > 0:
        gpu_layers = 6
    else:
        gpu_layers = 0

    model_note = ""
    path = Path(model_path).expanduser() if model_path else None
    if path and path.is_file():
        size_gb = path.stat().st_size / (1024 ** 3)
        model_note = f" Model file: {size_gb:.1f} GB."

        # Very large models on 16 GB system RAM need extra headroom.
        if info.ram_gb and size_gb > info.ram_gb * 0.65:
            context = min(context, 32768)

    reason = (
        f"Based on {info.ram_gb:.1f} GB RAM and {info.vram_gb:.1f} GB VRAM, "
        f"AgentFoundry recommends a conservative {context:,}-token context and "
        f"{gpu_layers} GPU layers with q4_0 KV cache.{model_note}"
    )

    return RuntimeRecommendation(
        context=context,
        gpu_layers=gpu_layers,
        kv_cache_k="q4_0",
        kv_cache_v="q4_0",
        reason=reason,
    )
