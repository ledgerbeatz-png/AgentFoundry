from __future__ import annotations

import tkinter as tk
from tkinter import ttk


COLORS = {
    "obsidian": "#080B0F",
    "midnight": "#0D131A",
    "panel": "#111922",
    "panel_alt": "#151F2A",
    "border": "#273342",
    "gold": "#D6A85F",
    "pale_gold": "#F2D59C",
    "marble": "#ECE9E2",
    "muted": "#98A3AE",
    "green": "#31D17C",
    "blue": "#5EA7FF",
    "violet": "#8D72FF",
    "danger": "#E06969",
}


def apply_theme(root: tk.Tk) -> ttk.Style:
    root.configure(bg=COLORS["obsidian"])

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(".",
                    background=COLORS["obsidian"],
                    foreground=COLORS["marble"],
                    fieldbackground=COLORS["panel"],
                    bordercolor=COLORS["border"],
                    lightcolor=COLORS["border"],
                    darkcolor=COLORS["border"],
                    font=("Segoe UI", 10))

    style.configure("Root.TFrame", background=COLORS["obsidian"])
    style.configure("Panel.TFrame", background=COLORS["panel"])
    style.configure("PanelAlt.TFrame", background=COLORS["panel_alt"])
    style.configure("Sidebar.TFrame", background=COLORS["midnight"])

    style.configure("Brand.TLabel",
                    background=COLORS["midnight"],
                    foreground=COLORS["pale_gold"],
                    font=("Georgia", 18, "bold"))
    style.configure("BrandSub.TLabel",
                    background=COLORS["midnight"],
                    foreground=COLORS["muted"],
                    font=("Segoe UI", 9))
    style.configure("Hero.TLabel",
                    background=COLORS["obsidian"],
                    foreground=COLORS["marble"],
                    font=("Georgia", 22, "bold"))
    style.configure("HeroSub.TLabel",
                    background=COLORS["obsidian"],
                    foreground=COLORS["muted"],
                    font=("Segoe UI", 10))
    style.configure("Section.TLabel",
                    background=COLORS["panel"],
                    foreground=COLORS["pale_gold"],
                    font=("Segoe UI", 10, "bold"))
    style.configure("Body.TLabel",
                    background=COLORS["panel"],
                    foreground=COLORS["marble"])
    style.configure("Muted.TLabel",
                    background=COLORS["panel"],
                    foreground=COLORS["muted"])
    style.configure("Status.TLabel",
                    background=COLORS["obsidian"],
                    foreground=COLORS["green"],
                    font=("Segoe UI", 10, "bold"))
    style.configure("Metric.TLabel",
                    background=COLORS["panel_alt"],
                    foreground=COLORS["marble"],
                    font=("Segoe UI", 13, "bold"))
    style.configure("MetricCaption.TLabel",
                    background=COLORS["panel_alt"],
                    foreground=COLORS["muted"],
                    font=("Segoe UI", 8))

    style.configure("TEntry",
                    fieldbackground=COLORS["midnight"],
                    foreground=COLORS["marble"],
                    insertcolor=COLORS["marble"],
                    bordercolor=COLORS["border"],
                    padding=7)
    style.map("TEntry", bordercolor=[("focus", COLORS["gold"])])

    style.configure("TCombobox",
                    fieldbackground=COLORS["midnight"],
                    background=COLORS["midnight"],
                    foreground=COLORS["marble"],
                    arrowcolor=COLORS["gold"],
                    bordercolor=COLORS["border"],
                    padding=6)
    style.map("TCombobox",
              fieldbackground=[("readonly", COLORS["midnight"])],
              foreground=[("readonly", COLORS["marble"])],
              bordercolor=[("focus", COLORS["gold"])])

    style.configure("Gold.TButton",
                    background=COLORS["gold"],
                    foreground=COLORS["obsidian"],
                    bordercolor=COLORS["gold"],
                    padding=(12, 8),
                    font=("Segoe UI", 10, "bold"))
    style.map("Gold.TButton",
              background=[("active", COLORS["pale_gold"]), ("pressed", COLORS["pale_gold"])])

    style.configure("Secondary.TButton",
                    background=COLORS["panel_alt"],
                    foreground=COLORS["marble"],
                    bordercolor=COLORS["border"],
                    padding=(11, 8))
    style.map("Secondary.TButton",
              background=[("active", COLORS["border"])],
              bordercolor=[("focus", COLORS["gold"])])

    style.configure("Danger.TButton",
                    background=COLORS["panel_alt"],
                    foreground=COLORS["danger"],
                    bordercolor=COLORS["border"],
                    padding=(11, 8))
    style.map("Danger.TButton", background=[("active", "#2A1B1D")])

    style.configure("Nav.TButton",
                    background=COLORS["midnight"],
                    foreground=COLORS["muted"],
                    borderwidth=0,
                    anchor="w",
                    padding=(14, 9))
    style.map("Nav.TButton",
              background=[("active", COLORS["panel_alt"])],
              foreground=[("active", COLORS["pale_gold"])])

    style.configure("Card.TLabelframe",
                    background=COLORS["panel"],
                    bordercolor=COLORS["border"],
                    relief="solid")
    style.configure("Card.TLabelframe.Label",
                    background=COLORS["panel"],
                    foreground=COLORS["pale_gold"],
                    font=("Segoe UI", 10, "bold"))

    return style
