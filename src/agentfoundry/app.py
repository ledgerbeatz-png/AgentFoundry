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


class AgentFoundryApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("AgentFoundry")
        self.geometry("980x680")
        self.minsize(860, 600)

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
        self.status = tk.StringVar(value="Idle")
        self.endpoint = tk.StringVar(value="http://127.0.0.1:8080/v1")

        self._build_ui()
        self._load_selected_profile()
        self.after(150, self._poll_logs)
        self.after(1000, self._refresh_status)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        header = ttk.Frame(self, padding=14)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        ttk.Label(header, text="AgentFoundry", font=("Segoe UI", 22, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="Forge your local intelligence.", font=("Segoe UI", 10)).grid(row=1, column=0, sticky="w")
        ttk.Label(header, textvariable=self.status, font=("Segoe UI", 11, "bold")).grid(row=0, column=2, rowspan=2, sticky="e")

        body = ttk.Frame(self, padding=(14, 0, 14, 10))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(1, weight=1)

        ttk.Label(body, text="Profile").grid(row=0, column=0, sticky="w", pady=4)
        profile_box = ttk.Combobox(body, textvariable=self.profile_name, values=list(self.profiles), state="readonly")
        profile_box.grid(row=0, column=1, sticky="ew", padx=(10, 6), pady=4)
        profile_box.bind("<<ComboboxSelected>>", lambda _e: self._load_selected_profile())
        ttk.Button(body, text="Save profile", command=self._save_profile).grid(row=0, column=2, padx=4)

        ttk.Label(body, text="GGUF model").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(body, textvariable=self.model_path).grid(row=1, column=1, sticky="ew", padx=(10, 6), pady=4)
        ttk.Button(body, text="Browse...", command=self._browse_model).grid(row=1, column=2, padx=4)

        settings = ttk.LabelFrame(body, text="Runtime settings", padding=10)
        settings.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(10, 4))
        for i in range(8):
            settings.columnconfigure(i, weight=1)

        fields = [
            ("Context", self.context),
            ("GPU layers", self.gpu_layers),
            ("KV K", self.kv_k),
            ("KV V", self.kv_v),
            ("RoPE scale", self.rope_scale),
            ("YaRN original", self.yarn_orig_ctx),
        ]
        for idx, (label, variable) in enumerate(fields):
            row = 0 if idx < 3 else 2
            col = (idx % 3) * 2
            ttk.Label(settings, text=label).grid(row=row, column=col, sticky="w", padx=(0, 6), pady=(0, 2))
            ttk.Entry(settings, textvariable=variable, width=16).grid(row=row + 1, column=col, columnspan=2, sticky="ew", padx=(0, 12), pady=(0, 8))

        controls = ttk.Frame(body)
        controls.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(10, 4))
        ttk.Button(controls, text="Start server", command=self._start_server).pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="Start Hermes", command=self._start_hermes).pack(side="left", padx=6)
        ttk.Button(controls, text="Start all", command=self._start_all).pack(side="left", padx=6)
        ttk.Button(controls, text="Stop server", command=self.runtime.stop_server).pack(side="left", padx=6)
        ttk.Button(controls, text="Open model folder", command=self._open_model_folder).pack(side="right")

        info = ttk.Frame(body)
        info.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        info.columnconfigure(1, weight=1)
        ttk.Label(info, text="Endpoint:").grid(row=0, column=0, sticky="w")
        ttk.Label(info, textvariable=self.endpoint).grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Label(info, text="System:").grid(row=1, column=0, sticky="w")
        ttk.Label(info, text=self._system_summary()).grid(row=1, column=1, sticky="w", padx=(8, 0))

        log_frame = ttk.LabelFrame(self, text="Logs", padding=8)
        log_frame.grid(row=2, column=0, sticky="nsew", padx=14, pady=(0, 14))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = tk.Text(log_frame, wrap="word", height=14, font=("Consolas", 9), state="disabled")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set)

        ttk.Button(log_frame, text="Clear", command=self._clear_logs).grid(row=1, column=0, sticky="e", pady=(6, 0))

    def _system_summary(self) -> str:
        pieces = [platform.system(), platform.release(), platform.machine()]
        llama = shutil.which("llama-server") or shutil.which("llama-server.exe")
        hermes = shutil.which("hermes") or shutil.which("hermes.exe")
        pieces.append("llama.cpp ready" if llama else "llama.cpp missing")
        pieces.append("Hermes ready" if hermes else "Hermes missing")
        return " | ".join(pieces)

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
        if self.runtime.server_running() and self.runtime.hermes_running():
            self.status.set("Server + Hermes running")
        elif self.runtime.server_running():
            self.status.set("Server running")
        elif self.runtime.hermes_running():
            self.status.set("Hermes running")
        else:
            self.status.set("Idle")
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
