from __future__ import annotations

import platform
import queue
import shutil
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .profiles import load_profiles, save_profiles
from .runtime import RuntimeController, RuntimeProfile
from .theme import COLORS, apply_theme


class AgentFoundryApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("AgentFoundry — Forge your local intelligence")
        self.geometry("1180x760")
        self.minsize(1000, 680)

        apply_theme(self)

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.runtime = RuntimeController(self.log_queue)
        self.profiles = load_profiles()
        self.profile_name = tk.StringVar(value=next(iter(self.profiles)))

        self.model_path = tk.StringVar()
        self.context = tk.StringVar()
        self.gpu_layers = tk.StringVar()
        self.kv_k = tk.StringVar()
        self.kv_v = tk.StringVar()
        self.rope_scale = tk.StringVar()
        self.yarn_orig_ctx = tk.StringVar()
        self.status = tk.StringVar(value="IDLE")
        self.endpoint = tk.StringVar(value="http://127.0.0.1:8080/v1")

        self._build_ui()
        self._load_selected_profile()
        self.after(150, self._poll_logs)
        self.after(1000, self._refresh_status)

    def _build_ui(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        sidebar = ttk.Frame(self, style="Sidebar.TFrame", width=210)
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_propagate(False)
        sidebar.columnconfigure(0, weight=1)

        brand = ttk.Frame(sidebar, style="Sidebar.TFrame", padding=(18, 20, 18, 14))
        brand.grid(row=0, column=0, sticky="ew")
        ttk.Label(brand, text="AGENTFOUNDRY", style="Brand.TLabel").pack(anchor="w")
        ttk.Label(brand, text="FORGE YOUR LOCAL INTELLIGENCE", style="BrandSub.TLabel").pack(anchor="w", pady=(2, 0))

        divider = tk.Frame(sidebar, bg=COLORS["gold"], height=1)
        divider.grid(row=1, column=0, sticky="ew", padx=18, pady=(2, 12))

        for row, item in enumerate((
            "⌂   Home",
            "◇   Models",
            "◈   Servers",
            "✦   Agents",
            "⇣   Downloads",
            "⌁   Hardware",
            "◎   Benchmarks",
            "⚙   Settings",
            "≡   Logs",
        ), start=2):
            ttk.Button(sidebar, text=item, style="Nav.TButton", command=lambda: None).grid(
                row=row, column=0, sticky="ew", padx=8, pady=1
            )

        footer = ttk.Frame(sidebar, style="Sidebar.TFrame", padding=18)
        footer.grid(row=20, column=0, sticky="sew")
        sidebar.rowconfigure(19, weight=1)
        ttk.Label(footer, text="LOCAL-FIRST", style="BrandSub.TLabel").pack(anchor="w")
        ttk.Label(footer, text="Modern tools. Ancient wisdom.", style="BrandSub.TLabel").pack(anchor="w", pady=(4, 0))

        main = ttk.Frame(self, style="Root.TFrame", padding=(26, 20, 26, 18))
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(5, weight=1)

        hero = ttk.Frame(main, style="Root.TFrame")
        hero.grid(row=0, column=0, sticky="ew")
        hero.columnconfigure(0, weight=1)
        ttk.Label(hero, text="Local intelligence, under your control.", style="Hero.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            hero,
            text="Manage models, tune hardware and launch autonomous agents from one forge.",
            style="HeroSub.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        status_wrap = ttk.Frame(hero, style="Root.TFrame")
        status_wrap.grid(row=0, column=1, rowspan=2, sticky="e")
        tk.Label(
            status_wrap,
            text="●",
            bg=COLORS["obsidian"],
            fg=COLORS["green"],
            font=("Segoe UI", 12, "bold"),
        ).pack(side="left", padx=(0, 6))
        ttk.Label(status_wrap, textvariable=self.status, style="Status.TLabel").pack(side="left")

        metrics = ttk.Frame(main, style="Root.TFrame")
        metrics.grid(row=1, column=0, sticky="ew", pady=(18, 14))
        for i in range(4):
            metrics.columnconfigure(i, weight=1)

        self.metric_model = self._metric_card(metrics, 0, "MODEL", "Ready")
        self.metric_server = self._metric_card(metrics, 1, "SERVER", "Stopped")
        self.metric_agent = self._metric_card(metrics, 2, "AGENT", "Idle")
        self.metric_context = self._metric_card(metrics, 3, "CONTEXT", "65K")

        top_cards = ttk.Frame(main, style="Root.TFrame")
        top_cards.grid(row=2, column=0, sticky="ew")
        top_cards.columnconfigure(0, weight=3)
        top_cards.columnconfigure(1, weight=2)

        model_card = ttk.LabelFrame(top_cards, text="ACTIVE MODEL · MINERVA", style="Card.TLabelframe", padding=14)
        model_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        model_card.columnconfigure(1, weight=1)

        ttk.Label(model_card, text="Profile", style="Body.TLabel").grid(row=0, column=0, sticky="w", pady=4)
        profile_box = ttk.Combobox(model_card, textvariable=self.profile_name, values=list(self.profiles), state="readonly")
        profile_box.grid(row=0, column=1, sticky="ew", padx=(12, 8), pady=4)
        profile_box.bind("<<ComboboxSelected>>", lambda _e: self._load_selected_profile())
        ttk.Button(model_card, text="Save", style="Secondary.TButton", command=self._save_profile).grid(row=0, column=2, padx=(0, 2))

        ttk.Label(model_card, text="GGUF model", style="Body.TLabel").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(model_card, textvariable=self.model_path).grid(row=1, column=1, sticky="ew", padx=(12, 8), pady=4)
        ttk.Button(model_card, text="Browse", style="Secondary.TButton", command=self._browse_model).grid(row=1, column=2, padx=(0, 2))

        runtime_card = ttk.LabelFrame(top_cards, text="RUNTIME · VULCAN", style="Card.TLabelframe", padding=14)
        runtime_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        runtime_card.columnconfigure(0, weight=1)
        runtime_card.columnconfigure(1, weight=1)

        runtime_fields = [
            ("Context", self.context),
            ("GPU layers", self.gpu_layers),
            ("KV cache K", self.kv_k),
            ("KV cache V", self.kv_v),
            ("RoPE scale", self.rope_scale),
            ("YaRN original", self.yarn_orig_ctx),
        ]
        for idx, (label, variable) in enumerate(runtime_fields):
            row = (idx // 2) * 2
            col = idx % 2
            ttk.Label(runtime_card, text=label, style="Muted.TLabel").grid(row=row, column=col, sticky="w", padx=(0, 8), pady=(0, 3))
            ttk.Entry(runtime_card, textvariable=variable, width=14).grid(row=row + 1, column=col, sticky="ew", padx=(0, 8), pady=(0, 9))

        actions = ttk.Frame(main, style="Root.TFrame")
        actions.grid(row=3, column=0, sticky="ew", pady=(14, 12))
        ttk.Button(actions, text="LAUNCH ALL", style="Gold.TButton", command=self._start_all).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Start server", style="Secondary.TButton", command=self._start_server).pack(side="left", padx=4)
        ttk.Button(actions, text="Open Hermes", style="Secondary.TButton", command=self._start_hermes).pack(side="left", padx=4)
        ttk.Button(actions, text="Stop server", style="Danger.TButton", command=self.runtime.stop_server).pack(side="left", padx=4)
        ttk.Button(actions, text="Open model folder", style="Secondary.TButton", command=self._open_model_folder).pack(side="right")

        system = ttk.LabelFrame(main, text="SYSTEM · JUPITER", style="Card.TLabelframe", padding=12)
        system.grid(row=4, column=0, sticky="ew", pady=(0, 12))
        system.columnconfigure(1, weight=1)
        ttk.Label(system, text="Endpoint", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(system, textvariable=self.endpoint, style="Body.TLabel").grid(row=0, column=1, sticky="w", padx=(12, 0))
        ttk.Label(system, text="Host", style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(5, 0))
        ttk.Label(system, text=self._system_summary(), style="Body.TLabel").grid(row=1, column=1, sticky="w", padx=(12, 0), pady=(5, 0))

        log_frame = ttk.LabelFrame(main, text="ORACLE LOG", style="Card.TLabelframe", padding=10)
        log_frame.grid(row=5, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = tk.Text(
            log_frame,
            wrap="word",
            height=12,
            font=("Cascadia Mono", 9),
            state="disabled",
            bg=COLORS["midnight"],
            fg=COLORS["marble"],
            insertbackground=COLORS["marble"],
            selectbackground=COLORS["border"],
            relief="flat",
            padx=10,
            pady=10,
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set)
        ttk.Button(log_frame, text="Clear log", style="Secondary.TButton", command=self._clear_logs).grid(row=1, column=0, sticky="e", pady=(8, 0))

    def _metric_card(self, parent: ttk.Frame, column: int, caption: str, value: str) -> ttk.Label:
        card = ttk.Frame(parent, style="PanelAlt.TFrame", padding=(14, 11))
        card.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 6, 0 if column == 3 else 6))
        ttk.Label(card, text=caption, style="MetricCaption.TLabel").pack(anchor="w")
        label = ttk.Label(card, text=value, style="Metric.TLabel")
        label.pack(anchor="w", pady=(3, 0))
        return label

    def _system_summary(self) -> str:
        pieces = [platform.system(), platform.release(), platform.machine()]
        llama = shutil.which("llama-server") or shutil.which("llama-server.exe")
        hermes = shutil.which("hermes") or shutil.which("hermes.exe")
        pieces.append("llama.cpp ready" if llama else "llama.cpp missing")
        pieces.append("Hermes ready" if hermes else "Hermes missing")
        return "  ·  ".join(pieces)

    def _load_selected_profile(self) -> None:
        profile = self.profiles[self.profile_name.get()]
        self.model_path.set(profile.model_path)
        self.context.set(str(profile.context))
        self.gpu_layers.set(str(profile.gpu_layers))
        self.kv_k.set(profile.kv_cache_k)
        self.kv_v.set(profile.kv_cache_v)
        self.rope_scale.set(str(profile.rope_scale))
        self.yarn_orig_ctx.set(str(profile.yarn_orig_ctx))
        self.endpoint.set(profile.base_url)
        if hasattr(self, "metric_context"):
            self.metric_context.configure(text=f"{int(profile.context) // 1000}K")
        if hasattr(self, "metric_model"):
            model_name = Path(profile.model_path).stem if profile.model_path else "Ready"
            self.metric_model.configure(text=model_name[:24])

    def _profile_from_form(self) -> RuntimeProfile:
        return RuntimeProfile(
            model_path=self.model_path.get().strip(),
            context=int(self.context.get()),
            gpu_layers=int(self.gpu_layers.get()),
            kv_cache_k=self.kv_k.get().strip() or "q4_0",
            kv_cache_v=self.kv_v.get().strip() or "q4_0",
            rope_scale=float(self.rope_scale.get()),
            yarn_orig_ctx=int(self.yarn_orig_ctx.get()),
        )

    def _save_profile(self) -> None:
        try:
            self.profiles[self.profile_name.get()] = self._profile_from_form()
            save_profiles(self.profiles)
            self._append_log("[AgentFoundry] Profile saved.")
        except Exception as exc:
            messagebox.showerror("AgentFoundry", str(exc))

    def _browse_model(self) -> None:
        filename = filedialog.askopenfilename(
            title="Select GGUF model",
            filetypes=[("GGUF models", "*.gguf"), ("All files", "*.*")],
        )
        if filename:
            self.model_path.set(filename)
            if hasattr(self, "metric_model"):
                self.metric_model.configure(text=Path(filename).stem[:24])

    def _open_model_folder(self) -> None:
        path = Path(self.model_path.get()).expanduser()
        folder = path.parent if path.suffix else path
        if not folder.exists():
            messagebox.showwarning("AgentFoundry", f"Folder does not exist:\n{folder}")
            return
        if platform.system() == "Windows":
            subprocess.Popen(["explorer", str(folder)])

    def _start_server(self) -> None:
        try:
            profile = self._profile_from_form()
            self.endpoint.set(profile.base_url)
            self.runtime.start_server(profile)
        except Exception as exc:
            messagebox.showerror("AgentFoundry", str(exc))

    def _start_hermes(self) -> None:
        try:
            self.runtime.start_hermes()
        except Exception as exc:
            messagebox.showerror("AgentFoundry", str(exc))

    def _start_all(self) -> None:
        try:
            profile = self._profile_from_form()
            self.endpoint.set(profile.base_url)
            self.runtime.start_server(profile)
        except Exception as exc:
            messagebox.showerror("AgentFoundry", str(exc))
            return

        def worker() -> None:
            if self.runtime.wait_for_server(profile):
                try:
                    self.runtime.start_hermes()
                except Exception as exc:
                    self.log_queue.put(f"[AgentFoundry] Hermes start failed: {exc}")
            else:
                self.log_queue.put("[AgentFoundry] Server did not become ready in time.")

        threading.Thread(target=worker, daemon=True).start()

    def _append_log(self, line: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _poll_logs(self) -> None:
        try:
            while True:
                self._append_log(self.log_queue.get_nowait())
        except queue.Empty:
            pass
        self.after(150, self._poll_logs)

    def _refresh_status(self) -> None:
        server = self.runtime.server_running()
        hermes = self.runtime.hermes_running()

        if server and hermes:
            self.status.set("ONLINE")
            self.metric_server.configure(text="Running")
            self.metric_agent.configure(text="Connected")
        elif server:
            self.status.set("SERVER ONLINE")
            self.metric_server.configure(text="Running")
            self.metric_agent.configure(text="Idle")
        elif hermes:
            self.status.set("AGENT ONLINE")
            self.metric_server.configure(text="Stopped")
            self.metric_agent.configure(text="Connected")
        else:
            self.status.set("IDLE")
            self.metric_server.configure(text="Stopped")
            self.metric_agent.configure(text="Idle")

        self.after(1000, self._refresh_status)

    def _clear_logs(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")


def main() -> None:
    app = AgentFoundryApp()
    app.mainloop()


if __name__ == "__main__":
    main()
