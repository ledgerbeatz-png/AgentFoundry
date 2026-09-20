from __future__ import annotations

import json
import time
import tkinter as tk
from tkinter import ttk

from .screens import BaseScreen
from .settings import APP_DIR
from .theme import COLORS
from .trading.memory import TradeMemory


HORIZON_ORDER = ("5m", "15m", "1h", "6h", "24h")


class SolanaCommandCenterScreen(BaseScreen):
    """Card-first PAPER research dashboard.

    Tkinter cannot provide true frosted-glass compositing, so this screen mimics
    the cinematic glass/HUD feeling with layered dark panels, luminous borders,
    compact status chips and floating detail windows.
    """

    def __init__(self, master: tk.Misc, app: "AgentFoundryApp") -> None:
        super().__init__(
            master,
            app,
            "Solana · Command Center",
            "Live PAPER intelligence · local Qwen · persistent outcomes · AstraFly social slot reserved",
        )
        self.database = APP_DIR / "paper" / "solana-research.sqlite3"
        self._refresh_job = None

        body = ttk.Frame(self, style="Root.TFrame")
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(2, weight=1)

        metrics = ttk.Frame(body, style="Root.TFrame")
        metrics.grid(row=0, column=0, sticky="ew")
        for column in range(4):
            metrics.columnconfigure(column, weight=1)

        self.runtime_value = self._metric_card(metrics, 0, "RUNTIME", "OFFLINE")
        self.open_value = self._metric_card(metrics, 1, "OPEN PAPER", "0")
        self.decisions_value = self._metric_card(metrics, 2, "QWEN DECISIONS", "0")
        self.winrate_value = self._metric_card(metrics, 3, "24H WIN RATE", "—")

        signals = ttk.Frame(body, style="Root.TFrame")
        signals.grid(row=1, column=0, sticky="ew", pady=(14, 14))
        signals.columnconfigure(0, weight=2)
        signals.columnconfigure(1, weight=1)

        qwen = ttk.Frame(signals, style="Glass.TFrame", padding=14)
        qwen.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        ttk.Label(qwen, text="QWEN · LOCAL DECISION ENGINE", style="GlassTitle.TLabel").pack(anchor="w")
        self.qwen_status = ttk.Label(
            qwen,
            text="Waiting for stored decisions…",
            style="GlassBody.TLabel",
            wraplength=650,
            justify="left",
        )
        self.qwen_status.pack(anchor="w", pady=(8, 0))

        social = ttk.Frame(signals, style="GlassAccent.TFrame", padding=14)
        social.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        ttk.Label(social, text="ASTRAFLY · SOCIAL SIGNALS", style="GlassAccentTitle.TLabel").pack(anchor="w")
        self.social_status = ttk.Label(
            social,
            text="RESERVED · Historical + social intelligence will plug into this card next.",
            style="GlassAccentBody.TLabel",
            wraplength=360,
            justify="left",
        )
        self.social_status.pack(anchor="w", pady=(8, 0))

        workspace = ttk.Frame(body, style="Root.TFrame")
        workspace.grid(row=2, column=0, sticky="nsew")
        workspace.columnconfigure(0, weight=3)
        workspace.columnconfigure(1, weight=2)
        workspace.rowconfigure(0, weight=1)

        positions = ttk.Frame(workspace, style="Glass.TFrame", padding=14)
        positions.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        positions.columnconfigure(0, weight=1)
        positions.rowconfigure(1, weight=1)

        header = ttk.Frame(positions, style="Glass.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="OPEN PAPER POSITIONS", style="GlassTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(header, text="REFRESH", style="Secondary.TButton", command=self.refresh).grid(row=0, column=1, sticky="e")

        self.position_canvas = tk.Canvas(
            positions,
            bg=COLORS["panel"],
            highlightthickness=0,
            borderwidth=0,
        )
        self.position_canvas.grid(row=1, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(positions, orient="vertical", command=self.position_canvas.yview)
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.position_canvas.configure(yscrollcommand=scrollbar.set)

        self.position_stack = ttk.Frame(self.position_canvas, style="Glass.TFrame")
        self.position_window = self.position_canvas.create_window((0, 0), window=self.position_stack, anchor="nw")
        self.position_stack.bind("<Configure>", self._sync_scrollregion)
        self.position_canvas.bind("<Configure>", self._sync_canvas_width)

        activity = ttk.Frame(workspace, style="Glass.TFrame", padding=14)
        activity.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        activity.columnconfigure(0, weight=1)
        activity.rowconfigure(1, weight=1)
        ttk.Label(activity, text="RECENT AI DECISIONS", style="GlassTitle.TLabel").grid(row=0, column=0, sticky="w")

        self.activity_text = tk.Text(
            activity,
            wrap="word",
            state="disabled",
            bg=COLORS["midnight"],
            fg=COLORS["marble"],
            insertbackground=COLORS["marble"],
            relief="flat",
            padx=12,
            pady=12,
            font=("Cascadia Mono", 9),
        )
        self.activity_text.grid(row=1, column=0, sticky="nsew", pady=(10, 0))

    def _metric_card(self, parent: ttk.Frame, column: int, caption: str, value: str) -> ttk.Label:
        card = ttk.Frame(parent, style="GlassMetric.TFrame", padding=(14, 12))
        card.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 6, 0 if column == 3 else 6))
        ttk.Label(card, text=caption, style="GlassMetricCaption.TLabel").pack(anchor="w")
        label = ttk.Label(card, text=value, style="GlassMetricValue.TLabel")
        label.pack(anchor="w", pady=(4, 0))
        return label

    def _sync_scrollregion(self, _event=None) -> None:
        self.position_canvas.configure(scrollregion=self.position_canvas.bbox("all"))

    def _sync_canvas_width(self, event) -> None:
        self.position_canvas.itemconfigure(self.position_window, width=event.width)

    @staticmethod
    def _fmt_price(value: float | None) -> str:
        if value is None:
            return "—"
        value = float(value)
        if value == 0:
            return "0"
        if abs(value) < 0.001:
            return f"{value:.8g}"
        return f"{value:,.6f}"

    @staticmethod
    def _fmt_pct(value: float | None) -> str:
        if value is None:
            return "—"
        return f"{float(value):+.2f}%"

    def _clear_positions(self) -> None:
        for child in self.position_stack.winfo_children():
            child.destroy()

    def _position_card(self, memory: TradeMemory, row, index: int) -> None:
        market = json.loads(row["market_json"])
        outcomes = {item["horizon"]: item for item in memory.outcomes_for_trade(row["trade_id"])}
        latest = None
        for horizon in HORIZON_ORDER:
            if horizon in outcomes:
                latest = outcomes[horizon]

        card = ttk.Frame(self.position_stack, style="GlassRaised.TFrame", padding=12)
        card.grid(row=index, column=0, sticky="ew", pady=(0, 9))
        card.columnconfigure(1, weight=1)

        ttk.Label(card, text=str(row["symbol"]), style="GlassSymbol.TLabel").grid(row=0, column=0, rowspan=2, sticky="w")
        ttk.Label(
            card,
            text=f"ENTRY  {self._fmt_price(row['entry_price'])}",
            style="GlassMuted.TLabel",
        ).grid(row=0, column=1, sticky="w", padx=(16, 0))

        confidence = market.get("qwen_confidence")
        confidence_text = f"QWEN {float(confidence):.0%}" if confidence is not None else "QWEN —"
        ttk.Label(card, text=confidence_text, style="GlassChip.TLabel").grid(row=0, column=2, sticky="e")

        latest_text = (
            f"LATEST {latest['horizon']}  {self._fmt_pct(latest['return_from_entry_pct'])}"
            if latest is not None else
            "WAITING FOR 5m"
        )
        ttk.Label(card, text=latest_text, style="GlassBody.TLabel").grid(row=1, column=1, sticky="w", padx=(16, 0), pady=(5, 0))

        ttk.Button(
            card,
            text="EXPAND ↗",
            style="Secondary.TButton",
            command=lambda trade_id=row["trade_id"]: self._open_trade_overlay(trade_id),
        ).grid(row=1, column=2, sticky="e", pady=(5, 0))

        timeline = ttk.Frame(card, style="GlassRaised.TFrame")
        timeline.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        for column, horizon in enumerate(HORIZON_ORDER):
            timeline.columnconfigure(column, weight=1)
            item = outcomes.get(horizon)
            text = f"{horizon}  {self._fmt_pct(item['return_from_entry_pct'])}" if item else f"{horizon}  PENDING"
            style = "GlassPositive.TLabel" if item and float(item["return_from_entry_pct"]) >= 0 else (
                "GlassNegative.TLabel" if item else "GlassMuted.TLabel"
            )
            ttk.Label(timeline, text=text, style=style).grid(row=0, column=column, sticky="w", padx=(0, 8))

    def _open_trade_overlay(self, trade_id: str) -> None:
        memory = TradeMemory(self.database)
        try:
            rows = [row for row in memory.open_trades_with_market() if row["trade_id"] == trade_id]
            if not rows:
                rows = [row for row in memory.closed_trades() if row["trade_id"] == trade_id]
            if not rows:
                return
            row = rows[0]
            market_json = row["market_json"] if "market_json" in row.keys() else None
            market = json.loads(market_json) if market_json else {}
            outcomes = memory.outcomes_for_trade(trade_id)
        finally:
            memory.close()

        overlay = tk.Toplevel(self)
        overlay.title(f"{row['symbol']} · PAPER POSITION")
        overlay.geometry("760x560")
        overlay.configure(bg=COLORS["obsidian"])
        overlay.transient(self.winfo_toplevel())

        shell = tk.Frame(
            overlay,
            bg=COLORS["panel"],
            highlightbackground=COLORS["blue"],
            highlightcolor=COLORS["blue"],
            highlightthickness=1,
            padx=20,
            pady=18,
        )
        shell.pack(fill="both", expand=True, padx=18, pady=18)

        tk.Label(
            shell,
            text=f"{row['symbol']}  ·  PAPER POSITION",
            bg=COLORS["panel"],
            fg=COLORS["pale_gold"],
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor="w")

        tk.Label(
            shell,
            text=f"Entry {self._fmt_price(row['entry_price'])}    Strategy {row['strategy_version']}    Status {row['status'].upper()}",
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(6, 16))

        thesis = market.get("qwen_thesis") or "No stored Qwen thesis."
        confidence = market.get("qwen_confidence")
        qwen_line = f"QWEN CONFIDENCE {float(confidence):.0%}" if confidence is not None else "QWEN CONFIDENCE —"
        tk.Label(shell, text=qwen_line, bg=COLORS["panel"], fg=COLORS["blue"], font=("Segoe UI", 11, "bold")).pack(anchor="w")
        tk.Label(
            shell,
            text=thesis,
            bg=COLORS["panel"],
            fg=COLORS["marble"],
            font=("Segoe UI", 11),
            wraplength=690,
            justify="left",
        ).pack(anchor="w", pady=(5, 18))

        timeline = tk.Frame(shell, bg=COLORS["midnight"], padx=12, pady=12)
        timeline.pack(fill="x")
        tk.Label(timeline, text="OUTCOME TIMELINE", bg=COLORS["midnight"], fg=COLORS["pale_gold"], font=("Segoe UI", 10, "bold")).pack(anchor="w")
        by_horizon = {item["horizon"]: item for item in outcomes}
        for horizon in HORIZON_ORDER:
            item = by_horizon.get(horizon)
            if item:
                value = float(item["return_from_entry_pct"])
                fg = COLORS["green"] if value >= 0 else COLORS["danger"]
                text = f"{horizon:<4}  price {self._fmt_price(item['price']):>12}    PnL {value:+.2f}%"
            else:
                fg = COLORS["muted"]
                text = f"{horizon:<4}  pending"
            tk.Label(timeline, text=text, bg=COLORS["midnight"], fg=fg, font=("Cascadia Mono", 10)).pack(anchor="w", pady=2)

        tk.Button(
            shell,
            text="CLOSE PANEL",
            command=overlay.destroy,
            bg=COLORS["panel_alt"],
            fg=COLORS["marble"],
            activebackground=COLORS["border"],
            activeforeground=COLORS["pale_gold"],
            relief="flat",
            padx=12,
            pady=8,
        ).pack(anchor="e", pady=(18, 0))

    def refresh(self) -> None:
        profile = self.app.current_profile()
        runtime_online = self.app.runtime.endpoint_ready(profile)
        self.runtime_value.configure(text="ONLINE" if runtime_online else "OFFLINE")

        memory = TradeMemory(self.database)
        try:
            open_rows = memory.open_trades_with_market()
            decisions = memory.research_decisions(limit=12)
            closed = memory.closed_trades()
            wins = sum(float(row["realized_pnl_pct"] or 0) > 0 for row in closed)
            win_rate = (wins / len(closed) * 100.0) if closed else None

            self.open_value.configure(text=str(len(open_rows)))
            self.decisions_value.configure(text=str(memory.research_decision_count()))
            self.winrate_value.configure(text=f"{win_rate:.0f}%" if win_rate is not None else "—")

            self._clear_positions()
            if open_rows:
                for index, row in enumerate(open_rows):
                    self._position_card(memory, row, index)
            else:
                ttk.Label(
                    self.position_stack,
                    text="No open PAPER positions · waiting for Qwen PAPER_BUY.",
                    style="GlassMuted.TLabel",
                ).grid(row=0, column=0, sticky="w", pady=12)

            if decisions:
                latest = decisions[0]
                self.qwen_status.configure(
                    text=(
                        f"{latest['symbol']} · {latest['action']} · confidence {float(latest['confidence']):.0%}\n"
                        f"{latest['thesis']}"
                    )
                )
            else:
                self.qwen_status.configure(text="Waiting for stored decisions…")

            lines = []
            for item in decisions[:10]:
                when = time.strftime("%H:%M:%S", time.localtime(float(item["observed_at"])))
                lines.append(
                    f"{when}  {item['symbol']:<10}  {item['action']:<9}  "
                    f"{float(item['confidence']):.0%}\n"
                    f"      {item['thesis']}\n"
                )
            self.activity_text.configure(state="normal")
            self.activity_text.delete("1.0", "end")
            self.activity_text.insert("1.0", "\n".join(lines) if lines else "No Qwen decisions recorded yet.")
            self.activity_text.configure(state="disabled")
        finally:
            memory.close()

        if self._refresh_job is not None:
            self.after_cancel(self._refresh_job)
        self._refresh_job = self.after(5000, self.refresh)


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .app import AgentFoundryApp
