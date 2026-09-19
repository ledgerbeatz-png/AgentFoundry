from __future__ import annotations

import platform
import shutil
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .benchmark import BenchmarkRunner, BenchmarkResult, ConcurrencyBenchmarkRunner, select_best_result
from .catalog import load_model_manifests
from .commerce import Feature, Plan
from .downloads import DownloadCancelled, DownloadProgress, ResumableDownloader, filename_from_url, human_bytes
from .hardware import detect_hardware, recommend_runtime
from .packs import builtin_registry
from .self_setup import build_self_setup_plan
from .runtime import RuntimeProfile
from .settings import detect_runtime_paths
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
        body.rowconfigure(1, weight=1)

        controls = ttk.LabelFrame(body, text="BENCHMARK PLAN", style="Card.TLabelframe", padding=14)
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="GPU layers", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        self.layers = tk.StringVar(value="12,16,20,24")
        ttk.Entry(controls, textvariable=self.layers).grid(row=0, column=1, sticky="ew", padx=(12, 8))
        ttk.Button(
            controls,
            text="RUN BENCHMARK",
            style="Gold.TButton",
            command=self._start,
        ).grid(row=0, column=2)

        self.state_label = ttk.Label(
            controls,
            text="Ready. Each value is tested in an isolated llama.cpp process.",
            style="Muted.TLabel",
        )
        self.state_label.grid(row=1, column=0, columnspan=3, sticky="w", pady=(10, 0))

        results = ttk.LabelFrame(body, text="RESULTS", style="Card.TLabelframe", padding=10)
        results.grid(row=1, column=0, sticky="nsew")
        results.columnconfigure(0, weight=1)
        results.rowconfigure(0, weight=1)

        columns = ("layers", "status", "latency", "tokens", "tps")
        self.table = ttk.Treeview(results, columns=columns, show="headings", height=10)
        headings = {
            "layers": "GPU layers",
            "status": "Status",
            "latency": "Latency",
            "tokens": "Tokens",
            "tps": "Approx tok/s",
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

        self.apply_button = ttk.Button(
            footer,
            text="APPLY BEST",
            style="Secondary.TButton",
            state="disabled",
            command=self._apply_best,
        )
        self.apply_button.grid(row=0, column=1, sticky="e")

        concurrency = ttk.LabelFrame(body, text="AI WORKERS · CONCURRENCY", style="Card.TLabelframe", padding=10)
        concurrency.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        concurrency.columnconfigure(0, weight=1)
        self.worker_state = ttk.Label(
            concurrency,
            text="Start the main runtime, then measure 1 / 2 / 4 parallel local AI requests.",
            style="Body.TLabel",
        )
        self.worker_state.grid(row=0, column=0, sticky="w")
        ttk.Button(
            concurrency,
            text="AUTO OPTIMIZE AI WORKERS",
            style="Gold.TButton",
            command=self._start_concurrency,
        ).grid(row=0, column=1, sticky="e", padx=(12, 0))

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

        self.best_result: BenchmarkResult | None = None
        self.recommended_workers = 1
        self.running = False


    def _start_concurrency(self) -> None:
        if self.running:
            return
        if not self.app.runtime.server_running():
            messagebox.showwarning(
                "AgentFoundry",
                "Start the main llama.cpp runtime first. Worker optimization measures the live local endpoint.",
            )
            return
        self.running = True
        for item in self.worker_table.get_children():
            self.worker_table.delete(item)
        self.worker_state.configure(text="Apollo is measuring 1 / 2 / 4 workers…")
        profile = self.app.current_profile()
        runner = ConcurrencyBenchmarkRunner(log=self.app.log_queue.put)

        def worker() -> None:
            try:
                summary = runner.run(profile)
                self.after(0, lambda: self._finish_concurrency(summary))
            except Exception as exc:
                self.after(0, lambda exc=exc: self._fail_concurrency(exc))

        import threading
        threading.Thread(target=worker, daemon=True).start()

    def _finish_concurrency(self, summary) -> None:
        self.running = False
        self.recommended_workers = summary.recommended_concurrency
        for result in summary.results:
            self.worker_table.insert(
                "",
                "end",
                values=(
                    result.concurrency,
                    f"{result.wall_seconds:.2f}s",
                    f"{result.throughput_rps:.3f}",
                    f"{result.average_latency_seconds:.2f}s",
                ),
            )
        self.worker_state.configure(
            text=f"Apollo recommendation: {summary.recommended_concurrency} parallel AI worker(s)."
        )
        self.app.log_queue.put(
            f"[Apollo] Recommended AI concurrency: {summary.recommended_concurrency} worker(s)."
        )

    def _fail_concurrency(self, exc: Exception) -> None:
        self.running = False
        self.worker_state.configure(text=f"Worker optimization failed: {exc}")
        self.app.log_queue.put(f"[Apollo] Concurrency benchmark failed: {exc}")

    def _parse_layers(self) -> list[int]:
        values: list[int] = []
        for raw in self.layers.get().split(","):
            raw = raw.strip()
            if not raw:
                continue
            value = int(raw)
            if value < 0 or value > 200:
                raise ValueError("GPU layer values must be between 0 and 200.")
            if value not in values:
                values.append(value)
        if not values:
            raise ValueError("Enter at least one GPU layer value.")
        return values

    def _start(self) -> None:
        if self.running:
            return
        if self.app.runtime.server_running():
            messagebox.showwarning(
                "AgentFoundry",
                "Stop the main llama.cpp runtime before benchmarking so VRAM measurements are not distorted.",
            )
            return

        try:
            values = self._parse_layers()
            profile = self.app.current_profile()
        except Exception as exc:
            messagebox.showerror("AgentFoundry", str(exc))
            return

        self.running = True
        self.best_result = None
        self.apply_button.configure(state="disabled")
        for item in self.table.get_children():
            self.table.delete(item)
        self.state_label.configure(text="Apollo is benchmarking…")
        self.recommendation.configure(text="Testing stable configurations…")

        def log(message: str) -> None:
            self.app.log_queue.put(message)

        runner = BenchmarkRunner(log=log, llama_server_path=self.app.settings.llama_server_path)

        def on_result(result: BenchmarkResult) -> None:
            self.after(0, lambda result=result: self._append_result(result))

        def worker() -> None:
            try:
                results = runner.run_many(profile, values, progress=on_result)
                best = select_best_result(results)
                self.after(0, lambda: self._finish(best))
            except Exception as exc:
                self.after(0, lambda exc=exc: self._fail(exc))

        import threading
        threading.Thread(target=worker, daemon=True).start()

    def _append_result(self, result: BenchmarkResult) -> None:
        self.table.insert(
            "",
            "end",
            values=(
                result.gpu_layers,
                result.status,
                f"{result.latency_seconds:.2f}s" if result.stable else "—",
                result.completion_tokens if result.stable else "—",
                f"{result.tokens_per_second:.2f}" if result.stable else "—",
            ),
        )

    def _finish(self, best: BenchmarkResult | None) -> None:
        self.running = False
        self.best_result = best
        if best is None:
            self.state_label.configure(text="Benchmark finished: no stable configuration found.")
            self.recommendation.configure(text="No stable result. Keep the current profile and inspect the logs.")
            self.apply_button.configure(state="disabled")
            return

        self.state_label.configure(text="Benchmark complete.")
        self.recommendation.configure(
            text=(
                f"Fastest stable result: {best.gpu_layers} GPU layers · "
                f"{best.latency_seconds:.2f}s · {best.tokens_per_second:.2f} approximate tok/s"
            )
        )
        self.apply_button.configure(state="normal")

    def _fail(self, exc: Exception) -> None:
        self.running = False
        self.state_label.configure(text="Benchmark failed.")
        self.recommendation.configure(text=str(exc))
        self.apply_button.configure(state="disabled")
        self.app.log_queue.put(f"[Apollo] Benchmark failed: {exc}")

    def _apply_best(self) -> None:
        if self.best_result is None:
            return
        layers = self.best_result.gpu_layers
        self.app.gpu_layers.set(str(layers))
        self.app.log_queue.put(
            f"[Apollo] Applied benchmark recommendation: {layers} GPU layers."
        )
        self.recommendation.configure(
            text=f"✓ Applied: {layers} GPU layers. Save/apply the profile before the next runtime start."
        )
        self.apply_button.configure(text="✓ APPLIED", state="disabled")
        messagebox.showinfo(
            "Apollo · Recommendation applied",
            f"Applied {layers} GPU layers to the current AgentFoundry profile.\n\n"
            "The new value will be used for the next runtime start.",
        )


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
            "Safe runtime settings applied.\n\nRun Apollo Benchmarks next to measure GPU layers and concurrency before saving the final profile.",
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
