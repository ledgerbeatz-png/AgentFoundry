from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from .hardware import detect_hardware, recommend_runtime
from .settings import detect_runtime_paths


class FirstRunWizard(tk.Toplevel):
    def __init__(self, app: "AgentFoundryApp") -> None:
        super().__init__(app)
        self.app = app
        self.title("AgentFoundry — First Run")
        self.geometry("760x560")
        self.resizable(False, False)
        self.transient(app)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._skip)

        self.step = 0
        self.steps = [
            self._welcome_step,
            self._runtime_step,
            self._hardware_step,
            self._model_step,
            self._finish_step,
        ]

        self.container = ttk.Frame(self, style="Root.TFrame", padding=24)
        self.container.pack(fill="both", expand=True)

        nav = ttk.Frame(self, style="Root.TFrame")
        nav.pack(fill="x", padx=24, pady=(0, 20))
        self.back_button = ttk.Button(nav, text="Back", style="Secondary.TButton", command=self._back)
        self.back_button.pack(side="left")
        self.next_button = ttk.Button(nav, text="Next", style="Gold.TButton", command=self._next)
        self.next_button.pack(side="right")

        self._render()

    def _clear(self) -> None:
        for child in self.container.winfo_children():
            child.destroy()

    def _render(self) -> None:
        self._clear()
        self.back_button.configure(state="disabled" if self.step == 0 else "normal")
        self.next_button.configure(text="Finish" if self.step == len(self.steps) - 1 else "Next")
        self.steps[self.step]()

    def _title(self, title: str, subtitle: str) -> None:
        ttk.Label(self.container, text=title, style="Hero.TLabel").pack(anchor="w")
        ttk.Label(self.container, text=subtitle, style="HeroSub.TLabel", wraplength=680).pack(anchor="w", pady=(6, 18))

    def _welcome_step(self) -> None:
        self._title("Welcome to AgentFoundry", "Forge your local intelligence with a guided setup.")
        box = ttk.LabelFrame(self.container, text="WHAT THIS WILL DO", style="Card.TLabelframe", padding=18)
        box.pack(fill="x")
        ttk.Label(
            box,
            text=(
                "AgentFoundry will detect llama.cpp and Hermes, inspect your hardware, "
                "prepare safe runtime defaults, and help you choose or download a GGUF model."
            ),
            style="Body.TLabel",
            wraplength=650,
        ).pack(anchor="w")

    def _runtime_step(self) -> None:
        self._title("Detect local runtimes", "AgentFoundry checks PATH and common Windows installation locations.")
        detected = detect_runtime_paths()
        if detected.llama_server_path:
            self.app.settings.llama_server_path = detected.llama_server_path
        if detected.hermes_path:
            self.app.settings.hermes_path = detected.hermes_path

        box = ttk.LabelFrame(self.container, text="RUNTIME DETECTION", style="Card.TLabelframe", padding=18)
        box.pack(fill="x")
        ttk.Label(box, text="llama.cpp", style="Muted.TLabel").grid(row=0, column=0, sticky="w", pady=6)
        ttk.Label(box, text=self.app.settings.llama_server_path or "Not found", style="Body.TLabel", wraplength=520).grid(row=0, column=1, sticky="w", padx=(14, 0), pady=6)
        ttk.Label(box, text="Hermes", style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Label(box, text=self.app.settings.hermes_path or "Not found", style="Body.TLabel", wraplength=520).grid(row=1, column=1, sticky="w", padx=(14, 0), pady=6)

    def _hardware_step(self) -> None:
        self._title("Tune for this machine", "Hardware is inspected locally. AgentFoundry applies conservative defaults.")
        info = detect_hardware()
        rec = recommend_runtime(info, self.app.model_path.get())
        self.app.context.set(str(rec.context))
        self.app.gpu_layers.set(str(rec.gpu_layers))
        self.app.kv_k.set(rec.kv_cache_k)
        self.app.kv_v.set(rec.kv_cache_v)

        box = ttk.LabelFrame(self.container, text="DETECTED", style="Card.TLabelframe", padding=18)
        box.pack(fill="x")
        text = (
            f"{info.cpu}\n"
            f"{info.ram_gb:.1f} GB RAM · {info.gpu} · {info.vram_gb:.1f} GB VRAM\n\n"
            f"Recommended: {rec.context:,} context · {rec.gpu_layers} GPU layers · "
            f"{rec.kv_cache_k}/{rec.kv_cache_v} KV cache"
        )
        ttk.Label(box, text=text, style="Body.TLabel", wraplength=650, justify="left").pack(anchor="w")

    def _model_step(self) -> None:
        self._title("Choose a model", "Use an existing GGUF model now, or finish setup and download one from the Catalog.")
        box = ttk.LabelFrame(self.container, text="MODEL", style="Card.TLabelframe", padding=18)
        box.pack(fill="x")
        ttk.Label(box, text="Current model", style="Muted.TLabel").pack(anchor="w")
        ttk.Label(box, textvariable=self.app.model_path, style="Body.TLabel", wraplength=640).pack(anchor="w", pady=(6, 12))
        ttk.Button(box, text="Browse GGUF", style="Secondary.TButton", command=self._browse_model).pack(anchor="w")

    def _finish_step(self) -> None:
        self._title("Ready to forge", "Your detected settings will be saved and can be changed later in Settings.")
        box = ttk.LabelFrame(self.container, text="SUMMARY", style="Card.TLabelframe", padding=18)
        box.pack(fill="x")
        ttk.Label(
            box,
            text=(
                f"Endpoint: http://{self.app.settings.host}:{self.app.settings.port}/v1\n"
                f"Context: {self.app.context.get()}\n"
                f"GPU layers: {self.app.gpu_layers.get()}\n"
                f"Model: {self.app.model_path.get() or 'Choose later from Downloads'}"
            ),
            style="Body.TLabel",
            justify="left",
            wraplength=650,
        ).pack(anchor="w")

    def _browse_model(self) -> None:
        path = filedialog.askopenfilename(
            title="Select GGUF model",
            filetypes=[("GGUF models", "*.gguf"), ("All files", "*.*")],
        )
        if path:
            self.app.model_path.set(path)
            self.app.settings.model_dir = str(Path(path).parent)
            self._render()

    def _next(self) -> None:
        if self.step < len(self.steps) - 1:
            self.step += 1
            self._render()
            return
        self._complete()

    def _back(self) -> None:
        if self.step > 0:
            self.step -= 1
            self._render()

    def _complete(self) -> None:
        self.app.settings.first_run_complete = True
        self.app.save_app_settings()
        try:
            self.app.save_profile()
        except Exception:
            pass
        self.destroy()
        self.app.show_screen("home")

    def _skip(self) -> None:
        self.destroy()
        self.app.show_screen("home")


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .app import AgentFoundryApp
