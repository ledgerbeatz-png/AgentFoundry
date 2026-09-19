from __future__ import annotations

import platform
import queue
import shutil
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from .commerce import Entitlement, Feature, Plan, feature_available, start_trial
from .profiles import load_profiles, save_profiles
from .runtime import RuntimeController, RuntimeProfile
from .settings import AppSettings, load_settings, save_settings
from .screens import (
    BenchmarksScreen,
    DownloadsScreen,
    HardwareScreen,
    SelfSetupScreen,
    HermesScreen,
    HomeScreen,
    LicenseScreen,
    LogsScreen,
    ModelsScreen,
    PlaceholderScreen,
    RuntimeScreen,
    SettingsScreen,
)
from .theme import COLORS, apply_theme
from .wizard import FirstRunWizard


class AgentFoundryApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("AgentFoundry — Forge your local intelligence")
        self.geometry("1220x780")
        self.minsize(1040, 700)
        apply_theme(self)

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.settings = load_settings()
        try:
            entitlement_plan = Plan(self.settings.plan)
        except ValueError:
            entitlement_plan = Plan.FREE
        self.entitlement = Entitlement(
            plan=entitlement_plan,
            trial_started_at=self.settings.trial_started_at,
            license_token=self.settings.license_token,
        )
        self.runtime = RuntimeController(
            self.log_queue,
            llama_server_path=self.settings.llama_server_path,
            hermes_path=self.settings.hermes_path,
        )
        self.profiles = load_profiles()
        self.profile_name = tk.StringVar(value=next(iter(self.profiles)))

        self.model_path = tk.StringVar()
        self.context = tk.StringVar()
        self.gpu_layers = tk.StringVar()
        self.kv_k = tk.StringVar()
        self.kv_v = tk.StringVar()
        self.rope_scale = tk.StringVar()
        self.yarn_orig_ctx = tk.StringVar()
        self.endpoint = tk.StringVar(value=f"http://{self.settings.host}:{self.settings.port}/v1")
        self.status = tk.StringVar(value="IDLE")
        self.apollo_gpu_layers: int | None = self.settings.apollo_gpu_layers
        self.apollo_workers: int | None = self.settings.apollo_workers
        self.apollo_tokens_per_second: float | None = self.settings.apollo_tokens_per_second

        self.nav_buttons: dict[str, ttk.Button] = {}
        self.screens: dict[str, ttk.Frame] = {}

        self._build_shell()
        self._build_screens()
        self.load_selected_profile()
        self.show_screen("home")
        self.after(150, self._poll_logs)
        self.after(1000, self._refresh_status)
        if not self.settings.first_run_complete:
            self.after(350, self.open_setup_wizard)

    def open_setup_wizard(self) -> None:
        FirstRunWizard(self)

    def _build_shell(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        sidebar = ttk.Frame(self, style="Sidebar.TFrame", width=225)
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_propagate(False)
        sidebar.columnconfigure(0, weight=1)
        sidebar.rowconfigure(20, weight=1)

        brand = ttk.Frame(sidebar, style="Sidebar.TFrame", padding=(18, 20, 18, 14))
        brand.grid(row=0, column=0, sticky="ew")
        ttk.Label(brand, text="AGENTFOUNDRY", style="Brand.TLabel").pack(anchor="w")
        ttk.Label(brand, text="FORGE YOUR LOCAL INTELLIGENCE", style="BrandSub.TLabel").pack(anchor="w", pady=(2, 0))
        tk.Frame(sidebar, bg=COLORS["gold"], height=1).grid(row=1, column=0, sticky="ew", padx=18, pady=(2, 12))

        items = [
            ("home", "⌂   Home"),
            ("models", "◇   Minerva · Models"),
            ("runtime", "◈   Vulcan · Runtime"),
            ("hermes", "✦   Hermes · Agents"),
            ("benchmarks", "◎   Apollo · Benchmarks"),
            ("hardware", "⌁   Hardware"),
            ("self_setup", "⚒   Forge · Self Setup"),
            ("downloads", "⇣   Downloads"),
            ("logs", "≡   Logs"),
            ("license", "◆   License"),
            ("settings", "⚙   Settings"),
        ]
        for row, (key, label) in enumerate(items, start=2):
            button = ttk.Button(sidebar, text=label, style="Nav.TButton", command=lambda name=key: self.show_screen(name))
            button.grid(row=row, column=0, sticky="ew", padx=8, pady=1)
            self.nav_buttons[key] = button

        footer = ttk.Frame(sidebar, style="Sidebar.TFrame", padding=18)
        footer.grid(row=21, column=0, sticky="sew")
        ttk.Label(footer, text="LOCAL-FIRST", style="BrandSub.TLabel").pack(anchor="w")
        ttk.Label(footer, text="Modern tools. Ancient wisdom.", style="BrandSub.TLabel").pack(anchor="w", pady=(4, 0))

        self.content = ttk.Frame(self, style="Root.TFrame")
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)

    def _build_screens(self) -> None:
        self.screens = {
            "home": HomeScreen(self.content, self),
            "models": ModelsScreen(self.content, self),
            "runtime": RuntimeScreen(self.content, self),
            "hermes": HermesScreen(self.content, self),
            "benchmarks": BenchmarksScreen(self.content, self),
            "hardware": HardwareScreen(self.content, self),
            "self_setup": SelfSetupScreen(self.content, self),
            "downloads": DownloadsScreen(self.content, self),
            "logs": LogsScreen(self.content, self),
            "license": LicenseScreen(self.content, self),
            "settings": SettingsScreen(self.content, self),
        }
        for screen in self.screens.values():
            screen.grid(row=0, column=0, sticky="nsew")

    def feature_available(self, feature: Feature) -> bool:
        return feature_available(self.entitlement, feature)

    def start_trial(self) -> None:
        before = self.entitlement.trial_started_at
        start_trial(self.entitlement)
        if before == self.entitlement.trial_started_at and before:
            messagebox.showinfo("AgentFoundry", "The trial has already been started for this installation.")
            return
        self._persist_entitlement()
        self.log_queue.put("[AgentFoundry] Pro trial started.")
        license_screen = self.screens.get("license")
        if isinstance(license_screen, LicenseScreen):
            license_screen.refresh()

    def _persist_entitlement(self) -> None:
        self.settings.plan = self.entitlement.plan.value
        self.settings.trial_started_at = self.entitlement.trial_started_at
        self.settings.license_token = self.entitlement.license_token
        self.save_app_settings()

    def show_screen(self, name: str) -> None:
        gated = {
            "downloads": Feature.RESUMABLE_DOWNLOADS,
            "benchmarks": Feature.BENCHMARKS,
            "hermes": Feature.HERMES_AUTOMATION,
        }
        feature = gated.get(name)
        if feature is not None and not self.feature_available(feature):
            name = "license"
        screen = self.screens[name]
        screen.tkraise()
        for key, button in self.nav_buttons.items():
            button.configure(style="NavActive.TButton" if key == name else "Nav.TButton")
        if hasattr(screen, "refresh"):
            screen.refresh()

    def current_profile(self) -> RuntimeProfile:
        return RuntimeProfile(
            model_path=self.model_path.get().strip(),
            context=int(self.context.get()),
            gpu_layers=int(self.gpu_layers.get()),
            kv_cache_k=self.kv_k.get().strip() or "q4_0",
            kv_cache_v=self.kv_v.get().strip() or "q4_0",
            rope_scale=float(self.rope_scale.get()),
            yarn_orig_ctx=int(self.yarn_orig_ctx.get()),
            host=self.settings.host,
            port=self.settings.port,
        )

    def load_selected_profile(self) -> None:
        profile = self.profiles[self.profile_name.get()]
        self.model_path.set(profile.model_path)
        self.context.set(str(profile.context))
        self.gpu_layers.set(str(profile.gpu_layers))
        self.kv_k.set(profile.kv_cache_k)
        self.kv_v.set(profile.kv_cache_v)
        self.rope_scale.set(str(profile.rope_scale))
        self.yarn_orig_ctx.set(str(profile.yarn_orig_ctx))
        self.endpoint.set(profile.base_url)
        models = self.screens.get("models")
        if isinstance(models, ModelsScreen):
            models.refresh_profiles()
        home = self.screens.get("home")
        if isinstance(home, HomeScreen):
            home.refresh()

    def save_app_settings(self) -> None:
        save_settings(self.settings)
        self.runtime.llama_server_path = self.settings.llama_server_path
        self.runtime.hermes_path = self.settings.hermes_path
        self.endpoint.set(f"http://{self.settings.host}:{self.settings.port}/v1")
        self.log_queue.put("[AgentFoundry] Application settings saved.")

    def save_profile(self) -> None:
        try:
            self.profiles[self.profile_name.get()] = self.current_profile()
            save_profiles(self.profiles)
            self.log_queue.put("[AgentFoundry] Profile saved.")
        except Exception as exc:
            messagebox.showerror("AgentFoundry", str(exc))

    def start_server(self) -> None:
        try:
            profile = self.current_profile()
            self.endpoint.set(profile.base_url)
            self.runtime.start_server(profile)
        except Exception as exc:
            messagebox.showerror("AgentFoundry", str(exc))

    def start_hermes(self) -> None:
        if not self.feature_available(Feature.HERMES_AUTOMATION):
            self.show_screen("license")
            return
        try:
            self.runtime.start_hermes()
        except Exception as exc:
            messagebox.showerror("AgentFoundry", str(exc))

    def start_all(self) -> None:
        if not self.feature_available(Feature.HERMES_AUTOMATION):
            self.show_screen("license")
            return
        try:
            profile = self.current_profile()
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

    def stop_server(self) -> None:
        self.runtime.stop_server()

    def open_model_folder(self) -> None:
        path = Path(self.model_path.get()).expanduser()
        folder = path.parent if path.suffix else path
        if not folder.exists():
            messagebox.showwarning("AgentFoundry", f"Folder does not exist:\n{folder}")
            return
        if platform.system() == "Windows":
            subprocess.Popen(["explorer", str(folder)])

    def system_summary(self) -> str:
        pieces = [platform.system(), platform.release(), platform.machine()]
        llama_ready = bool(self.settings.llama_server_path or shutil.which("llama-server") or shutil.which("llama-server.exe"))
        hermes_ready = bool(self.settings.hermes_path or shutil.which("hermes") or shutil.which("hermes.exe"))
        pieces.append("llama.cpp ready" if llama_ready else "llama.cpp missing")
        pieces.append("Hermes ready" if hermes_ready else "Hermes missing")
        return "  ·  ".join(pieces)

    def _poll_logs(self) -> None:
        while True:
            try:
                line = self.log_queue.get_nowait()
            except queue.Empty:
                break
            logs = self.screens.get("logs")
            if isinstance(logs, LogsScreen):
                logs.append(line)
            home = self.screens.get("home")
            if isinstance(home, HomeScreen):
                home.append_preview(line)
        self.after(150, self._poll_logs)

    def _refresh_status(self) -> None:
        if self.runtime.server_running() and self.runtime.hermes_running():
            self.status.set("READY")
        elif self.runtime.server_running():
            self.status.set("RUNTIME")
        else:
            self.status.set("IDLE")
        home = self.screens.get("home")
        if isinstance(home, HomeScreen):
            home.refresh()
        hermes = self.screens.get("hermes")
        if isinstance(hermes, HermesScreen):
            hermes.refresh()
        self.after(1000, self._refresh_status)


def main() -> None:
    AgentFoundryApp().mainloop()


if __name__ == "__main__":
    main()
