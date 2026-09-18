from __future__ import annotations

import platform
import shutil
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .hardware import detect_hardware, recommend_runtime
from .runtime import RuntimeProfile
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
