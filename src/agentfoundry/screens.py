from __future__ import annotations

import platform
import queue
import threading
import time
from dataclasses import asdict
import shutil
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .benchmark import BenchmarkResult
from .autotune import AutoTuneRunner
from .catalog import load_model_manifests
from .commerce import Feature, Plan
from .downloads import DownloadCancelled, DownloadProgress, ResumableDownloader, filename_from_url, human_bytes
from .hardware import detect_hardware, recommend_runtime
from .packs import builtin_registry
from .self_setup import build_self_setup_plan
from .runtime import RuntimeProfile
from .settings import detect_runtime_paths, save_settings
from .theme import COLORS


class BaseScreen(ttk.Frame):
    def __init__(self, master: tk.Misc, app: "AgentFoundryApp", title: str, subtitle: str) -> None:
        super().__init__(master, style="Root.TFrame", padding=(26, 20, 26, 18))
        self.app = app
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, style="Root.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text=title, style="Hero.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header, text=subtitle, style="HeroSub.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 0))


class HomeScreen(BaseScreen):
    def __init__(self, master: tk.Misc, app: "AgentFoundryApp") -> None:
        super().__init__(master, app, "Jupiter Command Center", "Local intelligence, under your control.")

        body = ttk.Frame(self, style="Root.TFrame")
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(3, weight=1)

        metrics = ttk.Frame(body, style="Root.TFrame")
        metrics.grid(row=0, column=0, sticky="ew")
        for i in range(4):
            metrics.columnconfigure(i, weight=1)

        self.metric_model = self._metric_card(metrics, 0, "MINERVA · MODEL", "Ready")
        self.metric_server = self._metric_card(metrics, 1, "VULCAN · RUNTIME", "Stopped")
        self.metric_agent = self._metric_card(metrics, 2, "HERMES · AGENT", "Idle")
        self.metric_context = self._metric_card(metrics, 3, "APOLLO · CONTEXT", "65K")

        actions = ttk.LabelFrame(body, text="QUICK ACTIONS", style="Card.TLabelframe", padding=16)
        actions.grid(row=1, column=0, sticky="ew", pady=(16, 12))
        ttk.Button(actions, text="LAUNCH ALL", style="Gold.TButton", command=app.start_all).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Start server", style="Secondary.TButton", command=app.start_server).pack(side="left", padx=4)
        ttk.Button(actions, text="Open Hermes", style="Secondary.TButton", command=app.start_hermes).pack(side="left", padx=4)
        ttk.Button(actions, text="Stop server", style="Danger.TButton", command=app.stop_server).pack(side="left", padx=4)
        ttk.Button(actions, text="Models", style="Secondary.TButton", command=lambda: app.show_screen("models")).pack(side="right")

        system = ttk.LabelFrame(body, text="SYSTEM · JUPITER", style="Card.TLabelframe", padding=14)
        system.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        system.columnconfigure(1, weight=1)
        ttk.Label(system, text="Endpoint", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(system, textvariable=app.endpoint, style="Body.TLabel").grid(row=0, column=1, sticky="w", padx=(12, 0))
        ttk.Label(system, text="Host", style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Label(system, text=app.system_summary(), style="Body.TLabel").grid(row=1, column=1, sticky="w", padx=(12, 0), pady=(6, 0))

        oracle = ttk.LabelFrame(body, text="ORACLE · RECENT ACTIVITY", style="Card.TLabelframe", padding=10)
        oracle.grid(row=3, column=0, sticky="nsew")
        oracle.columnconfigure(0, weight=1)
        oracle.rowconfigure(0, weight=1)
        self.preview = tk.Text(
            oracle,
            height=10,
            wrap="word",
            state="disabled",
            bg=COLORS["midnight"],
            fg=COLORS["marble"],
            insertbackground=COLORS["marble"],
            font=("Cascadia Mono", 9),
            relief="flat",
            padx=10,
            pady=10,
        )
        self.preview.grid(row=0, column=0, sticky="nsew")
        ttk.Button(oracle, text="Open full logs", style="Secondary.TButton", command=lambda: app.show_screen("logs")).grid(row=1, column=0, sticky="e", pady=(8, 0))

    def _metric_card(self, parent: ttk.Frame, column: int, caption: str, value: str) -> ttk.Label:
        card = ttk.Frame(parent, style="PanelAlt.TFrame", padding=(14, 12))
        card.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 6, 0 if column == 3 else 6))
        ttk.Label(card, text=caption, style="MetricCaption.TLabel").pack(anchor="w")
        label = ttk.Label(card, text=value, style="Metric.TLabel")
        label.pack(anchor="w", pady=(3, 0))
        return label

    def refresh(self) -> None:
        profile = self.app.current_profile()
        self.metric_model.configure(text=Path(profile.model_path).stem[:28] if profile.model_path else "No model")
        self.metric_server.configure(text="Running" if self.app.runtime.server_running() else "Stopped")
        self.metric_agent.configure(text="Running" if self.app.runtime.hermes_running() else "Idle")
        self.metric_context.configure(text=f"{profile.context // 1000}K")

    def append_preview(self, line: str) -> None:
        self.preview.configure(state="normal")
        self.preview.insert("end", line + "\n")
        self.preview.see("end")
        lines = int(self.preview.index("end-1c").split(".")[0])
        if lines > 120:
            self.preview.delete("1.0", "20.0")
        self.preview.configure(state="disabled")


class ModelsScreen(BaseScreen):
    def __init__(self, master: tk.Misc, app: "AgentFoundryApp") -> None:
        super().__init__(master, app, "Minerva · Models", "Curate, profile and prepare local intelligence.")

        body = ttk.Frame(self, style="Root.TFrame")
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=2)
        body.columnconfigure(1, weight=5)
        body.rowconfigure(0, weight=1)

        left = ttk.LabelFrame(body, text="MODEL PROFILES", style="Card.TLabelframe", padding=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)
        ttk.Label(left, text="Profile", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        self.profile_box = ttk.Combobox(left, textvariable=app.profile_name, values=list(app.profiles), state="readonly")
        self.profile_box.grid(row=1, column=0, sticky="new", pady=(5, 10))
        self.profile_box.bind("<<ComboboxSelected>>", lambda _e: app.load_selected_profile())
        ttk.Button(left, text="Import GGUF", style="Gold.TButton", command=self._browse).grid(row=2, column=0, sticky="ew", pady=4)
        ttk.Button(left, text="Save profile", style="Secondary.TButton", command=app.save_profile).grid(row=3, column=0, sticky="ew", pady=4)
        ttk.Button(left, text="Open model folder", style="Secondary.TButton", command=app.open_model_folder).grid(row=4, column=0, sticky="ew", pady=4)

        details = ttk.LabelFrame(body, text="MODEL IDENTITY", style="Card.TLabelframe", padding=16)
        details.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        details.columnconfigure(1, weight=1)

        fields = [
            ("GGUF path", app.model_path),
            ("Context", app.context),
            ("GPU layers", app.gpu_layers),
            ("KV cache K", app.kv_k),
            ("KV cache V", app.kv_v),
            ("RoPE scale", app.rope_scale),
            ("YaRN original", app.yarn_orig_ctx),
        ]
        for row, (label, variable) in enumerate(fields):
            ttk.Label(details, text=label, style="Muted.TLabel").grid(row=row, column=0, sticky="w", pady=6)
            ttk.Entry(details, textvariable=variable).grid(row=row, column=1, sticky="ew", padx=(14, 0), pady=6)

        actions = ttk.Frame(details, style="Panel.TFrame")
        actions.grid(row=len(fields), column=0, columnspan=2, sticky="ew", pady=(14, 0))
        ttk.Button(actions, text="Save Profile", style="Gold.TButton", command=app.save_profile).pack(side="left")
        ttk.Button(actions, text="Launch with this model", style="Secondary.TButton", command=app.start_all).pack(side="left", padx=8)

    def _browse(self) -> None:
        filename = filedialog.askopenfilename(title="Select GGUF model", filetypes=[("GGUF models", "*.gguf"), ("All files", "*.*")])
        if filename:
            self.app.model_path.set(filename)

    def refresh_profiles(self) -> None:
        self.profile_box.configure(values=list(self.app.profiles))


class RuntimeScreen(BaseScreen):
    def __init__(self, master: tk.Misc, app: "AgentFoundryApp") -> None:
        super().__init__(master, app, "Vulcan · Runtime", "Shape the forge: context, cache, offload and inference.")

        card = ttk.LabelFrame(self, text="LLAMA.CPP ENGINE", style="Card.TLabelframe", padding=16)
        card.grid(row=1, column=0, sticky="nsew")
        card.columnconfigure(1, weight=1)

        rows = [
            ("Context", app.context),
            ("GPU layers", app.gpu_layers),
            ("KV cache K", app.kv_k),
            ("KV cache V", app.kv_v),
            ("RoPE scale", app.rope_scale),
            ("YaRN original", app.yarn_orig_ctx),
        ]
        for row, (label, variable) in enumerate(rows):
            ttk.Label(card, text=label, style="Muted.TLabel").grid(row=row, column=0, sticky="w", pady=6)
            ttk.Entry(card, textvariable=variable).grid(row=row, column=1, sticky="ew", padx=(14, 0), pady=6)

        ttk.Separator(card).grid(row=len(rows), column=0, columnspan=2, sticky="ew", pady=14)
        ttk.Label(card, text="OpenAI-compatible endpoint", style="Muted.TLabel").grid(row=len(rows)+1, column=0, sticky="w")
        ttk.Label(card, textvariable=app.endpoint, style="Body.TLabel").grid(row=len(rows)+1, column=1, sticky="w", padx=(14, 0))

        actions = ttk.Frame(card, style="Panel.TFrame")
        actions.grid(row=len(rows)+2, column=0, columnspan=2, sticky="ew", pady=(18, 0))
        ttk.Button(actions, text="START RUNTIME", style="Gold.TButton", command=app.start_server).pack(side="left")
        ttk.Button(actions, text="Stop", style="Danger.TButton", command=app.stop_server).pack(side="left", padx=8)
        ttk.Button(actions, text="Save profile", style="Secondary.TButton", command=app.save_profile).pack(side="left")


class HermesScreen(BaseScreen):
    def __init__(self, master: tk.Misc, app: "AgentFoundryApp") -> None:
        super().__init__(master, app, "Hermes · Agents", "Connect thought to action through local tools.")

        card = ttk.LabelFrame(self, text="AGENT CONNECTION", style="Card.TLabelframe", padding=16)
        card.grid(row=1, column=0, sticky="nsew")
        card.columnconfigure(1, weight=1)

        ttk.Label(card, text="Endpoint", style="Muted.TLabel").grid(row=0, column=0, sticky="w", pady=6)
        ttk.Label(card, textvariable=app.endpoint, style="Body.TLabel").grid(row=0, column=1, sticky="w", padx=(14, 0), pady=6)
        ttk.Label(card, text="Compatibility", style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Label(card, text="Chat Completions", style="Body.TLabel").grid(row=1, column=1, sticky="w", padx=(14, 0), pady=6)
        ttk.Label(card, text="Context", style="Muted.TLabel").grid(row=2, column=0, sticky="w", pady=6)
        ttk.Label(card, textvariable=app.context, style="Body.TLabel").grid(row=2, column=1, sticky="w", padx=(14, 0), pady=6)

        status_box = ttk.Frame(card, style="PanelAlt.TFrame", padding=14)
        status_box.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(16, 10))
        self.status_label = ttk.Label(status_box, text="Hermes idle", style="Metric.TLabel")
        self.status_label.pack(anchor="w")
        ttk.Label(status_box, text="Tool calling is validated when Hermes can execute terminal actions through the local model.", style="MetricCaption.TLabel", wraplength=700).pack(anchor="w", pady=(4, 0))

        actions = ttk.Frame(card, style="Panel.TFrame")
        actions.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Button(actions, text="OPEN HERMES", style="Gold.TButton", command=app.start_hermes).pack(side="left")
        ttk.Button(actions, text="Launch full stack", style="Secondary.TButton", command=app.start_all).pack(side="left", padx=8)

    def refresh(self) -> None:
        self.status_label.configure(text="Hermes running" if self.app.runtime.hermes_running() else "Hermes idle")


class BenchmarksScreen(BaseScreen):
    def __init__(self, master: tk.Misc, app: "AgentFoundryApp") -> None:
        super().__init__(
            master,
            app,
            "Apollo · Benchmarks",
            "Measure before you optimize.",
        )

        body = ttk.Frame(self, style="Root.TFrame")
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(2, weight=1)

        controls = ttk.LabelFrame(body, text="BENCHMARK PLAN", style="Card.TLabelframe", padding=14)
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="FULL AUTO-TUNE", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        self.layers = tk.StringVar(value="")
        self.advanced = ttk.Frame(controls, style="Panel.TFrame")
        ttk.Label(self.advanced, text="GPU layer candidates (blank = automatic):", style="Muted.TLabel").pack(side="left")
        ttk.Entry(self.advanced, textvariable=self.layers).pack(side="left", padx=8)
        self.quick_button = ttk.Button(controls, text="⚡ QUICK TUNE", style="Gold.TButton",
                                       command=lambda: self._start("quick"))
        self.quick_button.grid(row=0, column=2, padx=8)
        self.deep_button = ttk.Button(controls, text="◎ DEEP BENCHMARK", style="Secondary.TButton",
                                      command=lambda: self._start("deep"))
        self.deep_button.grid(row=0, column=3)

        self.state_label = ttk.Label(
            controls,
            text="Full Auto-Tune · hardware → GPU → verification → AI workers → save",
            style="Muted.TLabel",
        )
        self.state_label.grid(row=1, column=0, columnspan=4, sticky="w", pady=(10, 0))

        self.activity_var = tk.DoubleVar(value=0)
        self.activity = ttk.Progressbar(controls, variable=self.activity_var, maximum=100, mode="determinate")
        self.activity.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        self.activity_detail = ttk.Label(controls, text="Idle · waiting for benchmark.", style="Muted.TLabel")
        self.activity_detail.grid(row=3, column=0, columnspan=4, sticky="w", pady=(5, 0))
        self._activity_step = 0
        self._activity_total = 1

        self.result_card = ttk.LabelFrame(body, text="APOLLO RESULT", style="Card.TLabelframe", padding=12)
        self.result_card.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        for column in range(5):
            self.result_card.columnconfigure(column, weight=1)

        self.result_status = ttk.Label(self.result_card, text="WAITING", style="GoldStatus.TLabel")
        self.result_status.grid(row=0, column=0, sticky="w")
        self.result_layers = ttk.Label(self.result_card, text="—", style="MetricGold.TLabel")
        self.result_layers.grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Label(self.result_card, text="GPU LAYERS", style="MetricCaption.TLabel").grid(row=2, column=0, sticky="w")

        self.result_workers = ttk.Label(self.result_card, text="—", style="Metric.TLabel")
        self.result_workers.grid(row=1, column=1, sticky="w", pady=(4, 0))
        ttk.Label(self.result_card, text="AI WORKERS", style="MetricCaption.TLabel").grid(row=2, column=1, sticky="w")

        self.result_tps = ttk.Label(self.result_card, text="—", style="Metric.TLabel")
        self.result_tps.grid(row=1, column=2, sticky="w", pady=(4, 0))
        ttk.Label(self.result_card, text="TOK/S", style="MetricCaption.TLabel").grid(row=2, column=2, sticky="w")

        self.result_elapsed = ttk.Label(self.result_card, text="—", style="Metric.TLabel")
        self.result_elapsed.grid(row=1, column=3, sticky="w", pady=(4, 0))
        ttk.Label(self.result_card, text="COMPLETED", style="MetricCaption.TLabel").grid(row=2, column=3, sticky="w")

        self.verify_button = ttk.Button(
            self.result_card,
            text="RUN DEEP VERIFICATION",
            style="Secondary.TButton",
            state="disabled",
            command=lambda: self._start("deep"),
        )
        self.verify_button.grid(row=1, column=4, rowspan=2, sticky="e", padx=(12, 0))
        self.refresh_saved_result()

        results = ttk.LabelFrame(body, text="RESULTS", style="Card.TLabelframe", padding=10)
        results.grid(row=2, column=0, sticky="nsew")
        results.columnconfigure(0, weight=1)
        results.rowconfigure(0, weight=1)

        columns = ("layers", "status", "latency", "tokens", "tps")
        self.table = ttk.Treeview(results, columns=columns, show="headings", height=6)
        headings = {
            "layers": "GPU layers",
            "status": "Status",
            "latency": "Latency",
            "tokens": "Tokens",
            "tps": "End-to-end tok/s",
        }
        widths = {"layers": 110, "status": 110, "latency": 130, "tokens": 90, "tps": 130}
        for key in columns:
            self.table.heading(key, text=headings[key])
            self.table.column(key, width=widths[key], anchor="center")
        self.table.grid(row=0, column=0, sticky="nsew")
        ttk.Scrollbar(results, command=self.table.yview).grid(row=0, column=1, sticky="ns")
        self.table.configure(yscrollcommand=lambda first, last: None)

        footer = ttk.Frame(results, style="Panel.TFrame")
        footer.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        footer.columnconfigure(0, weight=1)
        self.recommendation = ttk.Label(
            footer,
            text="No benchmark result yet.",
            style="Body.TLabel",
        )
        self.recommendation.grid(row=0, column=0, sticky="w")

        self.cancel_button = ttk.Button(footer, text="CANCEL", state="disabled", command=self._cancel)
        self.cancel_button.grid(row=0, column=1, sticky="e")
        self.details_button = ttk.Button(footer, text="SHOW DETAILS", command=self._toggle_details)
        self.details_button.grid(row=0, column=2, padx=8)
        self.details = tk.Text(results, height=6, wrap="word", state="disabled")

        concurrency = ttk.LabelFrame(body, text="AI WORKERS · CONCURRENCY", style="Card.TLabelframe", padding=10)
        concurrency.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        concurrency.columnconfigure(0, weight=1)
        self.worker_state = ttk.Label(
            concurrency,
            text="Workers 1 / 2 / 4 are optimized automatically after the GPU tests.",
            style="Body.TLabel",
        )
        self.worker_state.grid(row=0, column=0, sticky="w")
        worker_columns = ("workers", "wall", "throughput", "avg_latency")
        self.worker_table = ttk.Treeview(concurrency, columns=worker_columns, show="headings", height=3)
        worker_headings = {
            "workers": "Workers",
            "wall": "Wall time",
            "throughput": "Requests/s",
            "avg_latency": "Avg latency",
        }
        for key in worker_columns:
            self.worker_table.heading(key, text=worker_headings[key])
            self.worker_table.column(key, width=130, anchor="center")
        self.worker_table.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        self.running = False
        self.events = queue.Queue()
        self.cancelled = threading.Event()

    @staticmethod
    def _format_elapsed(seconds: int | float | None) -> str:
        if seconds is None:
            return "saved"
        seconds = max(0, int(seconds))
        minutes, remaining = divmod(seconds, 60)
        return f"{minutes}m {remaining:02d}s" if minutes else f"{remaining}s"

    def refresh_saved_result(self):
        status = self.app.settings.apollo_status
        layers = self.app.settings.apollo_gpu_layers
        workers = self.app.settings.apollo_workers
        tps = self.app.settings.apollo_tokens_per_second
        if status in {"VERIFIED", "QUICK READY"} and layers is not None:
            self.result_status.configure(
                text=("✓ VERIFIED" if status == "VERIFIED" else "⚡ QUICK READY"),
                style=("Success.TLabel" if status == "VERIFIED" else "GoldStatus.TLabel"),
            )
            self.result_layers.configure(text=str(layers))
            self.result_workers.configure(text=str(workers) if workers is not None else "—")
            self.result_tps.configure(text=f"{tps:.2f}" if tps is not None else "—")
            self.result_elapsed.configure(text="saved")
            if status == "QUICK READY":
                self.verify_button.configure(text="RUN DEEP VERIFICATION", state="normal")
            else:
                self.verify_button.configure(text="✓ VERIFIED", state="disabled")
        else:
            self.result_status.configure(text=status or "WAITING", style="GoldStatus.TLabel")
            self.result_layers.configure(text="—")
            self.result_workers.configure(text="—")
            self.result_tps.configure(text="—")
            self.result_elapsed.configure(text="—")
            self.verify_button.configure(text="RUN DEEP VERIFICATION", state="disabled")

    def _set_result_card(self, result, elapsed):
        status = result.status
        self.result_status.configure(
            text=("✓ VERIFIED" if status == "VERIFIED" else "⚡ QUICK READY" if status == "QUICK READY" else status),
            style=("Success.TLabel" if status == "VERIFIED" else "GoldStatus.TLabel"),
        )
        self.result_layers.configure(text=str(result.profile.get("gpu_layers", "—")))
        workers = result.workers["recommended_concurrency"] if result.workers else None
        self.result_workers.configure(text=str(workers) if workers is not None else "—")
        tps = result.verification["tokens_per_second"] if result.verification else None
        self.result_tps.configure(text=f"{tps:.2f}" if tps is not None else "—")
        self.result_elapsed.configure(text=self._format_elapsed(elapsed))
        if status == "QUICK READY":
            self.verify_button.configure(text="RUN DEEP VERIFICATION", state="normal")
        elif status == "VERIFIED":
            self.verify_button.configure(text="✓ VERIFIED", state="disabled")
        else:
            self.verify_button.configure(text="RETEST REQUIRED", state="disabled")

    def _apply_tuned_profile(self, profile):
        values = (
            (self.app.model_path, profile["model_path"]),
            (self.app.context, profile["context"]),
            (self.app.gpu_layers, profile["gpu_layers"]),
            (self.app.kv_k, profile["kv_cache_k"]),
            (self.app.kv_v, profile["kv_cache_v"]),
            (self.app.rope_scale, profile["rope_scale"]),
            (self.app.yarn_orig_ctx, profile["yarn_orig_ctx"]),
        )
        for variable, value in values:
            variable.set(str(value))
        self.app.save_profile()

    def _toggle_details(self):
        if self.details.winfo_ismapped():
            self.details.grid_remove()
            self.advanced.grid_remove()
            self.details_button.configure(text="SHOW DETAILS")
        else:
            self.details.grid(row=2, column=0, columnspan=2, sticky="ew", pady=8)
            self.advanced.grid(row=4, column=0, columnspan=4, sticky="ew", pady=8)
            self.details_button.configure(text="HIDE DETAILS")

    def _cancel(self):
        self.cancelled.set()
        self.activity_detail.configure(text="Cancelling · waiting for the current request and server cleanup…")

    def _start(self, mode="quick"):
        if self.running:
            return
        if mode not in {"quick", "deep"}:
            messagebox.showerror("Apollo", f"Unknown tune mode: {mode}")
            return
        quick = mode == "quick"
        try:
            profile = self.app.current_profile()
            candidates = [int(raw.strip()) for raw in self.layers.get().split(",") if raw.strip()] or None
            if candidates and any(not 0 <= value <= 200 for value in candidates):
                raise ValueError("GPU layers must be between 0 and 200.")
        except Exception as exc:
            messagebox.showerror("Apollo", str(exc))
            return
        self.running = self.app.tuning_active = True
        self.cancelled.clear()
        self.started = time.monotonic()
        self.source_profile = asdict(profile)
        self.source_executable = self.app.settings.llama_server_path
        self.state_label.configure(text="● RUNNING · " + ("QUICK TUNE" if quick else "DEEP BENCHMARK"))
        self.activity_detail.configure(text=("QUICK MODE" if quick else "DEEP MODE") + " · Hardware preflight…")
        self.activity_var.set(0)
        self._activity_step = 0
        self._activity_total = len(set(candidates)) if candidates else 4
        self.quick_button.configure(state="disabled")
        self.deep_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.recommendation.configure(text="Checking hardware, model and available memory…")
        self.result_status.configure(text="● RUNNING", style="GoldStatus.TLabel")
        self.result_layers.configure(text="—")
        self.result_workers.configure(text="—")
        self.result_tps.configure(text="—")
        self.result_elapsed.configure(text="—")
        self.verify_button.configure(state="disabled")
        self.worker_state.configure(text="Waiting for GPU selection before AI worker optimization.")
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("end", f"APOLLO MODE = {mode.upper()}\n")
        self.details.configure(state="disabled")
        for table in (self.table, self.worker_table):
            for item in table.get_children():
                table.delete(item)
        previous = {"fingerprint": self.app.settings.apollo_fingerprint,
                    "gpu_layers": self.app.settings.apollo_gpu_layers,
                    "tokens_per_second": self.app.settings.apollo_tokens_per_second or 0}

        def log(message):
            self.app.log_queue.put(message)
            self.events.put(("log", message))

        def worker():
            try:
                runner = AutoTuneRunner(self.source_executable, log, self.cancelled)
                result = runner.run(
                    profile,
                    quick=quick,
                    candidates=candidates,
                    previous=previous,
                    progress=lambda item: self.events.put(("gpu", item)),
                )
                self.events.put(("done", result))
            except Exception as exc:
                self.events.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=False).start()
        self.after(100, self._poll_tune)

    def _poll_tune(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "log":
                    self.details.configure(state="normal")
                    self.details.insert("end", value + "\n")
                    self.details.see("end")
                    self.details.configure(state="disabled")
                    if not value.startswith("[Apollo server diagnostics]"):
                        self.activity_detail.configure(text=value)
                    if value.startswith("Verify configuration"):
                        self.activity_var.set(65)
                    elif value.startswith("AI worker"):
                        self.activity_var.set(80)
                elif kind == "gpu":
                    self._activity_step += 1
                    self.activity_var.set(min(60, 60 * self._activity_step / self._activity_total))
                    self.table.insert("", "end", values=(value.gpu_layers, value.status,
                                      f"{value.latency_seconds:.2f}s", value.completion_tokens,
                                      f"{value.tokens_per_second:.2f}"))
                elif kind == "done":
                    self._complete_tune(value)
                elif kind == "error":
                    self._tune_failed(value)
        except queue.Empty:
            pass
        if self.running:
            self.state_label.configure(text=f"● RUNNING · Elapsed {int(time.monotonic() - self.started)}s")
            self.after(200, self._poll_tune)

    def _end_tune(self):
        self.running = self.app.tuning_active = False
        self.quick_button.configure(state="normal")
        self.deep_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")

    def _tune_failed(self, message):
        self._end_tune()
        self.state_label.configure(text="RETEST REQUIRED · Auto-Tune did not complete")
        self.recommendation.configure(text=message, wraplength=720)
        self.activity_detail.configure(text="Current profile preserved. See details for diagnostics.")
        self.result_status.configure(text="RETEST REQUIRED", style="GoldStatus.TLabel")
        self.result_elapsed.configure(text=self._format_elapsed(time.monotonic() - self.started))
        self.verify_button.configure(text="RETEST REQUIRED", state="disabled")
        self.app.settings.apollo_status = "RETEST REQUIRED"
        self.app._apollo_saved_status = "RETEST REQUIRED"
        self.app.settings.apollo_last_attempt = {"status": "RETEST REQUIRED", "reason": message}
        try:
            save_settings(self.app.settings)
        except OSError as exc:
            self.app.log_queue.put(f"[Apollo] Could not save failure status: {exc}")
        self._refresh_forge()

    def _complete_tune(self, result):
        try:
            if self.cancelled.is_set():
                raise RuntimeError("Auto-Tune cancelled. Current profile preserved.")
            if (asdict(self.app.current_profile()) != self.source_profile
                    or self.app.settings.llama_server_path != self.source_executable):
                raise RuntimeError("Runtime settings changed while tuning. Retest required.")
            settings = self.app.settings
            # One atomic settings write contains evidence, workers and the full selected profile.
            from dataclasses import replace
            updated = replace(settings, apollo_last_attempt=asdict(result), apollo_status=result.status)
            if result.status in {"VERIFIED", "QUICK READY"}:
                updated.apollo_profile = result.profile
                updated.apollo_fingerprint = result.fingerprint
                updated.apollo_gpu_layers = result.profile["gpu_layers"]
                updated.apollo_workers = result.workers["recommended_concurrency"]
                updated.apollo_tokens_per_second = result.verification["tokens_per_second"]
            save_settings(updated)
            self.app.settings = updated
            self.app._apollo_saved_status = result.status
            if result.status in {"VERIFIED", "QUICK READY"}:
                self._apply_tuned_profile(result.profile)
                self.app.apollo_gpu_layers = updated.apollo_gpu_layers
                self.app.apollo_workers = updated.apollo_workers
                self.app.apollo_tokens_per_second = updated.apollo_tokens_per_second
                updated.apollo_status = result.status
                self.app._apollo_saved_status = result.status
            if result.workers:
                for item in result.workers["results"]:
                    self.worker_table.insert("", "end", values=(item["concurrency"],
                        f'{item["wall_seconds"]:.2f}s', f'{item["throughput_rps"]:.3f}',
                        f'{item["average_latency_seconds"]:.2f}s'))
                self.worker_state.configure(text=f'Candidate: {result.workers["recommended_concurrency"]} AI worker(s) · {result.status}')
            self._end_tune()
            self.activity_var.set(100)
            self.state_label.configure(text=f"{result.status} · Elapsed {int(time.monotonic() - self.started)}s")
            self.recommendation.configure(text=result.reason, wraplength=720)
            self._set_result_card(result, time.monotonic() - self.started)
            self.activity_detail.configure(text=(
                "✓ VERIFIED · Profile saved and applied."
                if result.status == "VERIFIED"
                else "⚡ QUICK READY · Provisional profile saved and applied · Deep Benchmark optional."
                if result.status == "QUICK READY"
                else "Measurement saved · Current profile preserved · Retest recommended."
            ))
            self._refresh_forge()
        except Exception as exc:
            self._tune_failed(str(exc))

    def _refresh_forge(self):
        forge = self.app.screens.get("self_setup")
        if forge is not None:
            forge.refresh_apollo_result()


class HardwareScreen(BaseScreen):
    def __init__(self, master: tk.Misc, app: "AgentFoundryApp") -> None:
        super().__init__(master, app, "Forge Hardware", "Know the machine behind the model.")

        body = ttk.Frame(self, style="Root.TFrame")
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)

        detected = ttk.LabelFrame(body, text="DETECTED HARDWARE", style="Card.TLabelframe", padding=16)
        detected.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        detected.columnconfigure(1, weight=1)

        self.hardware_labels: dict[str, ttk.Label] = {}
        for row, key in enumerate(("OS", "CPU", "RAM", "GPU", "VRAM")):
            ttk.Label(detected, text=key, style="Muted.TLabel").grid(row=row, column=0, sticky="w", pady=6)
            label = ttk.Label(detected, text="Detecting…", style="Body.TLabel", wraplength=430)
            label.grid(row=row, column=1, sticky="w", padx=(14, 0), pady=6)
            self.hardware_labels[key] = label

        ttk.Button(detected, text="SCAN HARDWARE", style="Secondary.TButton", command=self.refresh).grid(
            row=6, column=0, columnspan=2, sticky="w", pady=(16, 0)
        )

        recommend = ttk.LabelFrame(body, text="VULCAN · SAFE RECOMMENDATION", style="Card.TLabelframe", padding=16)
        recommend.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        recommend.columnconfigure(1, weight=1)

        self.rec_context = ttk.Label(recommend, text="—", style="Metric.TLabel")
        self.rec_layers = ttk.Label(recommend, text="—", style="Metric.TLabel")
        self.rec_kv = ttk.Label(recommend, text="—", style="Metric.TLabel")

        ttk.Label(recommend, text="Context", style="Muted.TLabel").grid(row=0, column=0, sticky="w", pady=6)
        self.rec_context.grid(row=0, column=1, sticky="w", padx=(14, 0), pady=6)
        ttk.Label(recommend, text="GPU layers", style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=6)
        self.rec_layers.grid(row=1, column=1, sticky="w", padx=(14, 0), pady=6)
        ttk.Label(recommend, text="KV cache", style="Muted.TLabel").grid(row=2, column=0, sticky="w", pady=6)
        self.rec_kv.grid(row=2, column=1, sticky="w", padx=(14, 0), pady=6)

        self.reason = ttk.Label(
            recommend,
            text="Run hardware detection to generate a recommendation.",
            style="Body.TLabel",
            wraplength=430,
            justify="left",
        )
        self.reason.grid(row=3, column=0, columnspan=2, sticky="w", pady=(14, 10))

        ttk.Button(
            recommend,
            text="APPLY RECOMMENDATION",
            style="Gold.TButton",
            command=self._apply,
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(10, 0))

        self.info = None
        self.recommendation = None

    def refresh(self) -> None:
        self.info = detect_hardware()
        self.recommendation = recommend_runtime(self.info, self.app.model_path.get())

        self.hardware_labels["OS"].configure(
            text=f"{self.info.os_name} {self.info.os_version} · {self.info.architecture}"
        )
        self.hardware_labels["CPU"].configure(text=self.info.cpu)
        self.hardware_labels["RAM"].configure(text=f"{self.info.ram_gb:.1f} GB")
        self.hardware_labels["GPU"].configure(text=self.info.gpu)
        self.hardware_labels["VRAM"].configure(
            text=f"{self.info.vram_gb:.1f} GB" if self.info.vram_gb else "Unknown"
        )

        self.rec_context.configure(text=f"{self.recommendation.context:,}")
        self.rec_layers.configure(text=str(self.recommendation.gpu_layers))
        self.rec_kv.configure(
            text=f"{self.recommendation.kv_cache_k} / {self.recommendation.kv_cache_v}"
        )
        self.reason.configure(text=self.recommendation.reason)

    def _apply(self) -> None:
        if self.recommendation is None:
            self.refresh()
        if self.recommendation is None:
            return

        if not messagebox.askyesno(
            "AgentFoundry",
            "Apply the detected safe runtime recommendation to the current form?\n\n"
            "Your saved profile will not be overwritten until you explicitly save it.",
        ):
            return

        self.app.context.set(str(self.recommendation.context))
        self.app.gpu_layers.set(str(self.recommendation.gpu_layers))
        self.app.kv_k.set(self.recommendation.kv_cache_k)
        self.app.kv_v.set(self.recommendation.kv_cache_v)
        self.app.log_queue.put(
            "[AgentFoundry] Hardware recommendation applied to current runtime settings."
        )


class SelfSetupScreen(BaseScreen):
    def __init__(self, master: tk.Misc, app: "AgentFoundryApp") -> None:
        super().__init__(master, app, "Forge · Self Setup", "Analyze this machine and forge a compatible local AI stack.")

        body = ttk.Frame(self, style="Root.TFrame")
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)

        machine = ttk.LabelFrame(body, text="1 · MACHINE", style="Card.TLabelframe", padding=16)
        machine.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.machine_text = ttk.Label(machine, text="Press ANALYZE MY SYSTEM to begin.", style="Body.TLabel", wraplength=430, justify="left")
        self.machine_text.pack(anchor="w")

        plan = ttk.LabelFrame(body, text="2 · FORGE PLAN", style="Card.TLabelframe", padding=16)
        plan.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.plan_text = ttk.Label(plan, text="No plan generated yet.", style="Body.TLabel", wraplength=430, justify="left")
        self.plan_text.pack(anchor="w")

        packs = ttk.LabelFrame(body, text="3 · COMPATIBLE PACKS", style="Card.TLabelframe", padding=16)
        packs.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(16, 0))
        self.pack_text = ttk.Label(packs, text="Pack discovery runs after analysis.", style="Body.TLabel", wraplength=900, justify="left")
        self.pack_text.pack(anchor="w")

        actions = ttk.Frame(body, style="Root.TFrame")
        actions.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(18, 0))
        ttk.Button(actions, text="ANALYZE MY SYSTEM", style="Gold.TButton", command=self._analyze).pack(side="left")
        self.apply_button = ttk.Button(actions, text="APPLY SAFE SETUP", style="Secondary.TButton", command=self._apply, state="disabled")
        self.apply_button.pack(side="left", padx=8)
        ttk.Button(actions, text="RUN APOLLO BENCHMARK", style="Secondary.TButton", command=lambda: app.show_screen("benchmarks")).pack(side="right")

        self.info = None
        self.plan = None

        self.apollo_status = ttk.LabelFrame(body, text="APOLLO · OPTIMIZATION STATUS", style="Card.TLabelframe", padding=14)
        self.apollo_status.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(16, 0))
        self.apollo_result_text = ttk.Label(
            self.apollo_status,
            text="Not benchmarked yet · Run Apollo to verify this machine.",
            style="GoldStatus.TLabel",
            justify="left",
        )
        self.apollo_result_text.pack(anchor="w")
        apollo_actions = ttk.Frame(self.apollo_status, style="Panel.TFrame")
        apollo_actions.pack(fill="x", pady=(12, 0))
        self.start_optimized_button = ttk.Button(
            apollo_actions,
            text="START OPTIMIZED RUNTIME",
            style="Gold.TButton",
            state="disabled",
            command=self._start_optimized_runtime,
        )
        self.start_optimized_button.pack(side="left")
        ttk.Button(
            apollo_actions,
            text="OPEN APOLLO",
            style="Secondary.TButton",
            command=lambda: app.show_screen("benchmarks"),
        ).pack(side="right")
        self.refresh_apollo_result()

    def refresh_apollo_result(self) -> None:
        status = self.app.settings.apollo_status
        layers = self.app.apollo_gpu_layers
        workers = self.app.apollo_workers
        tps = self.app.apollo_tokens_per_second
        parts = []
        if layers is not None:
            parts.append(f"{layers} GPU layers")
        if workers is not None:
            parts.append(f"{workers} AI worker{'s' if workers != 1 else ''}")
        if tps is not None:
            parts.append(f"{tps:.2f} tok/s")
        ready = status in {"VERIFIED", "QUICK READY"} and bool(self.app.settings.apollo_profile)
        if ready and parts:
            prefix = "✓ VERIFIED" if status == "VERIFIED" else "⚡ QUICK READY"
            suffix = "Production profile verified." if status == "VERIFIED" else "Provisional profile ready; Deep verification is optional."
            self.apollo_result_text.configure(
                text=prefix + " · " + " · ".join(parts) + "\n" + suffix + " Ready for local PAPER research packs."
            )
            self.start_optimized_button.configure(state="normal")
        else:
            self.apollo_result_text.configure(
                text=status + " · Run Apollo Auto-Tune before starting an optimized runtime."
            )
            self.start_optimized_button.configure(state="disabled")

    def _start_optimized_runtime(self) -> None:
        if self.app.settings.apollo_status not in {"VERIFIED", "QUICK READY"}:
            messagebox.showwarning("Forge", "Apollo must produce QUICK READY or VERIFIED before optimized launch.")
            return
        self.app.log_queue.put(
            f"[Forge] Starting optimized runtime · {self.app.apollo_gpu_layers} GPU layers · "
            f"{self.app.apollo_workers or 1} AI worker(s)."
        )
        self.start_optimized_button.configure(text="STARTING…", state="disabled")
        self.app.start_server()
        self.after(1200, lambda: self.start_optimized_button.configure(
            text="RUNTIME RUNNING" if self.app.runtime.server_running() else "START OPTIMIZED RUNTIME",
            state="disabled" if self.app.runtime.server_running() else "normal",
        ))

    def _analyze(self) -> None:
        self.info = detect_hardware()
        self.plan = build_self_setup_plan(self.info, self.app.model_path.get())
        self.machine_text.configure(text=(
            f"{self.info.os_name} {self.info.os_version} · {self.info.architecture}\n"
            f"{self.info.cpu}\n"
            f"{self.info.ram_gb:.1f} GB RAM · {self.info.gpu} · {self.info.vram_gb:.1f} GB VRAM"
        ))
        self.plan_text.configure(text=(
            f"Model class: {self.plan.model.parameter_class} · {self.plan.model.quantization}\n"
            f"Runtime: {self.plan.runtime.context:,} context · {self.plan.runtime.gpu_layers} GPU layers\n"
            f"KV cache: {self.plan.runtime.kv_cache_k}/{self.plan.runtime.kv_cache_v}\n"
            f"Concurrency: {self.plan.recommended_concurrency} until Apollo measures this machine"
        ))
        compatible = [
            pack for pack in builtin_registry().all()
            if not pack.requires_local_model or bool(self.app.model_path.get().strip())
        ]
        if compatible:
            lines = []
            for pack in compatible:
                mode = "PAPER ONLY" if pack.paper_only else "ENABLED"
                lines.append(f"{pack.name} · {mode}\n{pack.description}")
            self.pack_text.configure(text="\n\n".join(lines))
        else:
            self.pack_text.configure(text="No compatible packs yet. Select a local model first.")
        self.apply_button.configure(state="normal")
        self.app.log_queue.put("[Forge] Self Setup analysis complete.")

    def _apply(self) -> None:
        if self.plan is None:
            self._analyze()
        if self.plan is None:
            return
        self.app.context.set(str(self.plan.runtime.context))
        self.app.gpu_layers.set(str(self.plan.runtime.gpu_layers))
        self.app.kv_k.set(self.plan.runtime.kv_cache_k)
        self.app.kv_v.set(self.plan.runtime.kv_cache_v)
        self.app.log_queue.put("[Forge] Safe Self Setup applied to the current runtime profile.")
        messagebox.showinfo(
            "AgentFoundry",
            "Safe runtime settings applied.\n\nRun Apollo Auto-Tune next. Deep Benchmark automatically saves and applies a verified GPU and worker profile.",
        )


class DownloadsScreen(BaseScreen):
    def __init__(self, master: tk.Misc, app: "AgentFoundryApp") -> None:
        super().__init__(
            master,
            app,
            "Downloads",
            "Install large GGUF models without fragile manual steps.",
        )

        body = ttk.Frame(self, style="Root.TFrame")
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)

        form = ttk.LabelFrame(body, text="MODEL DOWNLOAD", style="Card.TLabelframe", padding=16)
        form.grid(row=0, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)

        self.url = tk.StringVar()
        default_dir = app.settings.model_dir or (str(Path(app.model_path.get()).parent) if app.model_path.get() else str(Path.home() / "AgentFoundry" / "models"))
        self.destination_dir = tk.StringVar(value=default_dir)
        self.sha256 = tk.StringVar()

        ttk.Label(form, text="URL", style="Muted.TLabel").grid(row=0, column=0, sticky="w", pady=6)
        ttk.Entry(form, textvariable=self.url).grid(row=0, column=1, columnspan=2, sticky="ew", padx=(12, 0), pady=6)

        ttk.Label(form, text="Destination", style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Entry(form, textvariable=self.destination_dir).grid(row=1, column=1, sticky="ew", padx=(12, 8), pady=6)
        ttk.Button(form, text="Browse", style="Secondary.TButton", command=self._browse_destination).grid(row=1, column=2, pady=6)

        ttk.Label(form, text="SHA256 (optional)", style="Muted.TLabel").grid(row=2, column=0, sticky="w", pady=6)
        ttk.Entry(form, textvariable=self.sha256).grid(row=2, column=1, columnspan=2, sticky="ew", padx=(12, 0), pady=6)

        progress_card = ttk.LabelFrame(body, text="TRANSFER", style="Card.TLabelframe", padding=16)
        progress_card.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        progress_card.columnconfigure(0, weight=1)

        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(progress_card, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=0, column=0, sticky="ew")

        self.status_text = tk.StringVar(value="Ready.")
        self.speed_text = tk.StringVar(value="")
        ttk.Label(progress_card, textvariable=self.status_text, style="Body.TLabel").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Label(progress_card, textvariable=self.speed_text, style="Muted.TLabel").grid(row=2, column=0, sticky="w", pady=(4, 0))

        actions = ttk.Frame(progress_card, style="Panel.TFrame")
        actions.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        self.start_button = ttk.Button(actions, text="DOWNLOAD MODEL", style="Gold.TButton", command=self._start)
        self.start_button.pack(side="left")
        self.cancel_button = ttk.Button(actions, text="Cancel", style="Danger.TButton", command=self._cancel, state="disabled")
        self.cancel_button.pack(side="left", padx=8)
        ttk.Button(actions, text="Use current model folder", style="Secondary.TButton", command=self._use_current_folder).pack(side="right")

        self.downloader: ResumableDownloader | None = None
        self.running = False
        self.completed_path: Path | None = None

    def _browse_destination(self) -> None:
        folder = filedialog.askdirectory(title="Select model download folder", initialdir=self.destination_dir.get() or None)
        if folder:
            self.destination_dir.set(folder)

    def _use_current_folder(self) -> None:
        current = Path(self.app.model_path.get()).expanduser()
        folder = current.parent if current.suffix else current
        if str(folder):
            self.destination_dir.set(str(folder))

    def _start(self) -> None:
        if self.running:
            return

        url = self.url.get().strip()
        destination_dir = Path(self.destination_dir.get().strip()).expanduser()
        if not url.startswith(("https://", "http://")):
            messagebox.showerror("AgentFoundry", "Enter a valid HTTP or HTTPS model URL.")
            return
        if not self.destination_dir.get().strip():
            messagebox.showerror("AgentFoundry", "Choose a destination folder.")
            return

        filename = filename_from_url(url)
        if not filename.lower().endswith(".gguf"):
            if not messagebox.askyesno(
                "AgentFoundry",
                f"The URL resolves to '{filename}', not a .gguf filename. Continue anyway?",
            ):
                return

        destination = destination_dir / filename
        self.running = True
        self.completed_path = None
        self.progress_var.set(0.0)
        self.status_text.set(f"Preparing {filename}…")
        self.speed_text.set("")
        self.start_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")

        def log(message: str) -> None:
            self.app.log_queue.put(message)

        def progress(update: DownloadProgress) -> None:
            self.after(0, lambda update=update: self._update_progress(update))

        self.downloader = ResumableDownloader(progress=progress, log=log)

        def worker() -> None:
            try:
                path = self.downloader.download(
                    url,
                    destination,
                    expected_sha256=self.sha256.get(),
                    retries=3,
                )
                self.after(0, lambda path=path: self._complete(path))
            except DownloadCancelled:
                self.after(0, self._cancelled)
            except Exception as exc:
                self.after(0, lambda exc=exc: self._failed(exc))

        import threading
        threading.Thread(target=worker, daemon=True).start()

    def _update_progress(self, update: DownloadProgress) -> None:
        if update.total > 0:
            self.progress_var.set(update.fraction * 100)
            amount = f"{human_bytes(update.downloaded)} / {human_bytes(update.total)}"
        else:
            amount = human_bytes(update.downloaded)

        if update.state == "verifying":
            self.status_text.set("Verifying SHA256…")
            self.speed_text.set(amount)
        elif update.state == "complete":
            self.progress_var.set(100.0)
            self.status_text.set("Download complete.")
            self.speed_text.set(amount)
        else:
            self.status_text.set(f"Downloading… {amount}")
            self.speed_text.set(f"{human_bytes(update.speed_bps)}/s" if update.speed_bps > 0 else "")

    def _complete(self, path: Path) -> None:
        self.running = False
        self.completed_path = path
        self.start_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")
        self.progress_var.set(100.0)
        self.status_text.set(f"Complete: {path.name}")
        self.speed_text.set(str(path))
        self.app.model_path.set(str(path))
        self.app.log_queue.put(f"[Downloads] Active model path set to {path}.")

    def _cancel(self) -> None:
        if self.downloader is not None:
            self.downloader.cancel()
            self.status_text.set("Cancelling after current chunk…")

    def _cancelled(self) -> None:
        self.running = False
        self.start_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")
        self.status_text.set("Cancelled. Partial file kept; starting again resumes it.")
        self.speed_text.set("")

    def _failed(self, exc: Exception) -> None:
        self.running = False
        self.start_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")
        self.status_text.set("Download failed.")
        self.speed_text.set(str(exc))
        self.app.log_queue.put(f"[Downloads] Failed: {exc}")

    def refresh(self) -> None:
        if not self.running and not self.destination_dir.get().strip():
            self._use_current_folder()


class LogsScreen(BaseScreen):
    def __init__(self, master: tk.Misc, app: "AgentFoundryApp") -> None:
        super().__init__(master, app, "Oracle · Logs", "See exactly what the forge is doing.")

        frame = ttk.LabelFrame(self, text="LIVE LOG", style="Card.TLabelframe", padding=10)
        frame.grid(row=1, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.text = tk.Text(
            frame,
            wrap="word",
            state="disabled",
            bg=COLORS["midnight"],
            fg=COLORS["marble"],
            insertbackground=COLORS["marble"],
            font=("Cascadia Mono", 9),
            relief="flat",
            padx=10,
            pady=10,
        )
        self.text.grid(row=0, column=0, sticky="nsew")
        ttk.Scrollbar(frame, command=self.text.yview).grid(row=0, column=1, sticky="ns")
        ttk.Button(frame, text="Clear", style="Secondary.TButton", command=self.clear).grid(row=1, column=0, sticky="e", pady=(8, 0))

    def append(self, line: str) -> None:
        self.text.configure(state="normal")
        self.text.insert("end", line + "\n")
        self.text.see("end")
        self.text.configure(state="disabled")

    def clear(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")


class LicenseScreen(BaseScreen):
    def __init__(self, master: tk.Misc, app: "AgentFoundryApp") -> None:
        super().__init__(
            master,
            app,
            "License",
            "Unlock the full local-AI workflow when you are ready.",
        )

        body = ttk.Frame(self, style="Root.TFrame")
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)

        status = ttk.LabelFrame(body, text="CURRENT PLAN", style="Card.TLabelframe", padding=18)
        status.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        status.columnconfigure(0, weight=1)

        self.plan_label = ttk.Label(status, text="FREE", style="Metric.TLabel")
        self.plan_label.grid(row=0, column=0, sticky="w")
        self.plan_detail = ttk.Label(status, text="", style="Body.TLabel", wraplength=430, justify="left")
        self.plan_detail.grid(row=1, column=0, sticky="w", pady=(8, 14))

        self.trial_button = ttk.Button(
            status,
            text="START 14-DAY PRO TRIAL",
            style="Gold.TButton",
            command=app.start_trial,
        )
        self.trial_button.grid(row=2, column=0, sticky="w")

        ttk.Label(
            status,
            text=(
                "Pro activation will use a signed server-issued entitlement. "
                "No master key or payment secret is stored in the desktop app."
            ),
            style="Muted.TLabel",
            wraplength=430,
            justify="left",
        ).grid(row=3, column=0, sticky="w", pady=(18, 0))

        features = ttk.LabelFrame(body, text="FREE VS PRO", style="Card.TLabelframe", padding=18)
        features.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        rows = [
            ("Hardware compatibility scan", "FREE"),
            ("Basic model profiles", "FREE"),
            ("Basic llama.cpp runtime", "FREE"),
            ("Resumable model downloads", "PRO"),
            ("Automatic tuning workflow", "PRO"),
            ("Apollo benchmarks", "PRO"),
            ("Hermes automation", "PRO"),
            ("Premium update channel", "PRO"),
        ]
        for row, (label, plan) in enumerate(rows):
            ttk.Label(features, text=label, style="Body.TLabel").grid(row=row, column=0, sticky="w", pady=5)
            style = "MetricCaption.TLabel" if plan == "FREE" else "Status.TLabel"
            ttk.Label(features, text=plan, style=style).grid(row=row, column=1, sticky="e", padx=(24, 0), pady=5)

        activation = ttk.LabelFrame(body, text="PRO ACTIVATION", style="Card.TLabelframe", padding=18)
        activation.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        activation.columnconfigure(1, weight=1)

        self.license_key = tk.StringVar()
        ttk.Label(activation, text="License key", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Entry(activation, textvariable=self.license_key, show="•").grid(
            row=0, column=1, sticky="ew", padx=(12, 8)
        )
        ttk.Button(
            activation,
            text="ACTIVATE",
            style="Secondary.TButton",
            command=self._activate_placeholder,
        ).grid(row=0, column=2)
        self.activation_status = ttk.Label(
            activation,
            text="Activation service not connected yet.",
            style="Muted.TLabel",
        )
        self.activation_status.grid(row=1, column=0, columnspan=3, sticky="w", pady=(10, 0))

    def _activate_placeholder(self) -> None:
        self.activation_status.configure(
            text=(
                "License activation backend is not connected in this development build. "
                "The client will only accept signed entitlements once the commerce backend is live."
            )
        )

    def refresh(self) -> None:
        plan = self.app.entitlement.effective_plan()
        if plan == Plan.PRO:
            self.plan_label.configure(text="PRO")
            self.plan_detail.configure(text="AgentFoundry Pro is active.")
            self.trial_button.configure(state="disabled", text="PRO ACTIVE")
        elif plan == Plan.TRIAL:
            days = self.app.entitlement.days_left()
            self.plan_label.configure(text="PRO TRIAL")
            self.plan_detail.configure(text=f"{days} day(s) remaining in the Pro trial.")
            self.trial_button.configure(state="disabled", text="TRIAL ACTIVE")
        else:
            self.plan_label.configure(text="FREE")
            if self.app.entitlement.trial_started_at:
                detail = "Your Pro trial has ended. Free features remain available."
                self.trial_button.configure(state="disabled", text="TRIAL USED")
            else:
                detail = "Free edition. Start the one-time Pro trial to unlock premium workflows."
                self.trial_button.configure(state="normal", text="START 14-DAY PRO TRIAL")
            self.plan_detail.configure(text=detail)


class SettingsScreen(BaseScreen):
    def __init__(self, master: tk.Misc, app: "AgentFoundryApp") -> None:
        super().__init__(
            master,
            app,
            "Settings",
            "Shape AgentFoundry around your local stack.",
        )

        card = ttk.LabelFrame(self, text="LOCAL RUNTIME", style="Card.TLabelframe", padding=16)
        card.grid(row=1, column=0, sticky="new")
        card.columnconfigure(1, weight=1)

        self.llama_path = tk.StringVar(value=app.settings.llama_server_path)
        self.hermes_path = tk.StringVar(value=app.settings.hermes_path)
        self.model_dir = tk.StringVar(value=app.settings.model_dir)
        self.host = tk.StringVar(value=app.settings.host)
        self.port = tk.StringVar(value=str(app.settings.port))
        self.status_text = tk.StringVar(value="")

        ttk.Label(card, text="llama-server", style="Muted.TLabel").grid(row=0, column=0, sticky="w", pady=6)
        ttk.Entry(card, textvariable=self.llama_path).grid(row=0, column=1, sticky="ew", padx=(12, 8), pady=6)
        ttk.Button(card, text="Browse", style="Secondary.TButton", command=self._browse_llama).grid(row=0, column=2, pady=6)

        ttk.Label(card, text="Hermes", style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Entry(card, textvariable=self.hermes_path).grid(row=1, column=1, sticky="ew", padx=(12, 8), pady=6)
        ttk.Button(card, text="Browse", style="Secondary.TButton", command=self._browse_hermes).grid(row=1, column=2, pady=6)

        ttk.Label(card, text="Model folder", style="Muted.TLabel").grid(row=2, column=0, sticky="w", pady=6)
        ttk.Entry(card, textvariable=self.model_dir).grid(row=2, column=1, sticky="ew", padx=(12, 8), pady=6)
        ttk.Button(card, text="Browse", style="Secondary.TButton", command=self._browse_models).grid(row=2, column=2, pady=6)

        ttk.Label(card, text="Host", style="Muted.TLabel").grid(row=3, column=0, sticky="w", pady=6)
        ttk.Entry(card, textvariable=self.host).grid(row=3, column=1, sticky="ew", padx=(12, 8), pady=6)

        ttk.Label(card, text="Port", style="Muted.TLabel").grid(row=4, column=0, sticky="w", pady=6)
        ttk.Entry(card, textvariable=self.port).grid(row=4, column=1, sticky="ew", padx=(12, 8), pady=6)

        actions = ttk.Frame(card, style="Panel.TFrame")
        actions.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(16, 0))
        ttk.Button(actions, text="AUTO DETECT", style="Secondary.TButton", command=self._detect).pack(side="left")
        ttk.Button(actions, text="SAVE SETTINGS", style="Gold.TButton", command=self._save).pack(side="left", padx=8)
        ttk.Button(actions, text="RUN SETUP WIZARD", style="Secondary.TButton", command=app.open_setup_wizard).pack(side="right")

        ttk.Label(card, textvariable=self.status_text, style="Muted.TLabel", wraplength=760).grid(
            row=6, column=0, columnspan=3, sticky="w", pady=(12, 0)
        )

    def _browse_llama(self) -> None:
        path = filedialog.askopenfilename(
            title="Select llama-server executable",
            filetypes=[("Executable", "*.exe"), ("All files", "*.*")],
        )
        if path:
            self.llama_path.set(path)

    def _browse_hermes(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Hermes executable",
            filetypes=[("Executable", "*.exe"), ("All files", "*.*")],
        )
        if path:
            self.hermes_path.set(path)

    def _browse_models(self) -> None:
        folder = filedialog.askdirectory(
            title="Select default model folder",
            initialdir=self.model_dir.get() or None,
        )
        if folder:
            self.model_dir.set(folder)

    def _detect(self) -> None:
        detected = detect_runtime_paths()
        if detected.llama_server_path:
            self.llama_path.set(detected.llama_server_path)
        if detected.hermes_path:
            self.hermes_path.set(detected.hermes_path)
        if not self.model_dir.get().strip():
            self.model_dir.set(detected.model_dir)

        llama_state = self.llama_path.get().strip() or "not found"
        hermes_state = self.hermes_path.get().strip() or "not found"
        self.status_text.set(
            f"llama.cpp: {llama_state}  ·  Hermes: {hermes_state}"
        )

    def _save(self) -> None:
        try:
            port = int(self.port.get())
            if port < 1 or port > 65535:
                raise ValueError("Port must be between 1 and 65535.")
            host = self.host.get().strip()
            if not host:
                raise ValueError("Host cannot be empty.")
        except ValueError as exc:
            messagebox.showerror("AgentFoundry", str(exc))
            return

        self.app.settings.llama_server_path = self.llama_path.get().strip()
        self.app.settings.hermes_path = self.hermes_path.get().strip()
        self.app.settings.model_dir = self.model_dir.get().strip()
        self.app.settings.host = host
        self.app.settings.port = port
        self.app.save_app_settings()
        self.status_text.set("Settings saved.")

    def refresh(self) -> None:
        self.llama_path.set(self.app.settings.llama_server_path)
        self.hermes_path.set(self.app.settings.hermes_path)
        self.model_dir.set(self.app.settings.model_dir)
        self.host.set(self.app.settings.host)
        self.port.set(str(self.app.settings.port))


class PlaceholderScreen(BaseScreen):
    def __init__(self, master: tk.Misc, app: "AgentFoundryApp", title: str, subtitle: str, body: str) -> None:
        super().__init__(master, app, title, subtitle)
        card = ttk.LabelFrame(self, text="COMING NEXT", style="Card.TLabelframe", padding=22)
        card.grid(row=1, column=0, sticky="new")
        ttk.Label(card, text=body, style="Body.TLabel", wraplength=760).pack(anchor="w")


# Avoid importing app.py at runtime; only for type checking.
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .app import AgentFoundryApp
