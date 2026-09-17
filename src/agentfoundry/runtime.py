from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from queue import Queue
from typing import Optional


@dataclass
class RuntimeProfile:
    model_path: str
    context: int = 65536
    gpu_layers: int = 20
    kv_cache_k: str = "q4_0"
    kv_cache_v: str = "q4_0"
    rope_scaling: str = "yarn"
    rope_scale: float = 2.0
    yarn_orig_ctx: int = 40960
    host: str = "127.0.0.1"
    port: int = 8080
    reasoning: str = "off"
    reasoning_budget: int = 0

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}/v1"


class RuntimeController:
    def __init__(self, log_queue: Optional[Queue[str]] = None) -> None:
        self.log_queue = log_queue or Queue()
        self.server_process: Optional[subprocess.Popen[str]] = None
        self.hermes_process: Optional[subprocess.Popen[str]] = None
        self._log_threads: list[threading.Thread] = []

    def log(self, message: str) -> None:
        self.log_queue.put(message)

    @staticmethod
    def find_executable(name: str) -> Optional[str]:
        return shutil.which(name)

    def build_llama_args(self, profile: RuntimeProfile) -> list[str]:
        return [
            "-m", profile.model_path,
            "-c", str(profile.context),
            "-ngl", str(profile.gpu_layers),
            "--no-kv-offload",
            "-ctk", profile.kv_cache_k,
            "-ctv", profile.kv_cache_v,
            "--rope-scaling", profile.rope_scaling,
            "--rope-scale", str(profile.rope_scale),
            "--yarn-orig-ctx", str(profile.yarn_orig_ctx),
            "--reasoning", profile.reasoning,
            "--reasoning-budget", str(profile.reasoning_budget),
            "--host", profile.host,
            "--port", str(profile.port),
        ]

    def _pump_output(self, process: subprocess.Popen[str], prefix: str) -> None:
        assert process.stdout is not None
        for line in process.stdout:
            self.log(f"[{prefix}] {line.rstrip()}")

    def start_server(self, profile: RuntimeProfile) -> None:
        if self.server_process and self.server_process.poll() is None:
            self.log("[AgentFoundry] llama.cpp server is already running.")
            return

        model = Path(profile.model_path)
        if not model.is_file():
            raise FileNotFoundError(f"GGUF model not found: {model}")

        executable = self.find_executable("llama-server") or self.find_executable("llama-server.exe")
        if not executable:
            raise FileNotFoundError("llama-server was not found in PATH.")

        command = [executable, *self.build_llama_args(profile)]
        self.log("[AgentFoundry] Starting llama.cpp server...")
        self.log("[AgentFoundry] " + subprocess.list2cmdline(command))

        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NO_WINDOW

        self.server_process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
        )
        thread = threading.Thread(
            target=self._pump_output,
            args=(self.server_process, "llama"),
            daemon=True,
        )
        thread.start()
        self._log_threads.append(thread)

    def wait_for_server(self, profile: RuntimeProfile, timeout: float = 120.0) -> bool:
        deadline = time.monotonic() + timeout
        url = f"{profile.base_url}/models"
        while time.monotonic() < deadline:
            if self.server_process and self.server_process.poll() is not None:
                return False
            try:
                with urllib.request.urlopen(url, timeout=2) as response:
                    if response.status == 200:
                        self.log(f"[AgentFoundry] Server ready: {profile.base_url}")
                        return True
            except Exception:
                time.sleep(1)
        return False

    def get_models(self, profile: RuntimeProfile) -> list[str]:
        try:
            with urllib.request.urlopen(f"{profile.base_url}/models", timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8"))
            data = payload.get("data", [])
            return [str(item.get("id", "")) for item in data if item.get("id")]
        except Exception:
            return []

    def start_hermes(self) -> None:
        if self.hermes_process and self.hermes_process.poll() is None:
            self.log("[AgentFoundry] Hermes is already running.")
            return

        executable = self.find_executable("hermes") or self.find_executable("hermes.exe")
        if not executable:
            raise FileNotFoundError("Hermes CLI was not found in PATH.")

        self.log("[AgentFoundry] Launching Hermes...")
        if os.name == "nt":
            self.hermes_process = subprocess.Popen(
                ["cmd.exe", "/k", executable],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        else:
            self.hermes_process = subprocess.Popen([executable])

    def stop_server(self) -> None:
        process = self.server_process
        if not process or process.poll() is not None:
            self.log("[AgentFoundry] llama.cpp server is not running.")
            return

        self.log("[AgentFoundry] Stopping llama.cpp server...")
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
        self.log("[AgentFoundry] llama.cpp server stopped.")
        self.server_process = None

    def server_running(self) -> bool:
        return bool(self.server_process and self.server_process.poll() is None)

    def hermes_running(self) -> bool:
        return bool(self.hermes_process and self.hermes_process.poll() is None)
