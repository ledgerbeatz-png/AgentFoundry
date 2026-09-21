from __future__ import annotations

import tkinter as tk
from tkinter import ttk


COLORS = {
    "obsidian": "#0A0D12",
    "midnight": "#0F1724",
    "panel": "#171C25",
    "panel_alt": "#1D2530",
    "border": "#273342",
    "gold": "#C9A15A",
    "pale_gold": "#E0C48A",
    "marble": "#D7D9DD",
    "muted": "#8B919A",
    "green": "#34D17A",
    "blue": "#69B7FF",
    "violet": "#8D72FF",
    "amber": "#F2B544",
    "warning": "#C9833B",
    "danger": "#C94A4A",
}


def apply_theme(root: tk.Tk) -> ttk.Style:
    root.configure(bg=COLORS["obsidian"])

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(
        ".",
        background=COLORS["obsidian"],
        foreground=COLORS["marble"],
        fieldbackground=COLORS["panel"],
        bordercolor=COLORS["border"],
        lightcolor=COLORS["border"],
        darkcolor=COLORS["border"],
        font=("Segoe UI", 10),
    )

    style.configure("Root.TFrame", background=COLORS["obsidian"])
    style.configure("Panel.TFrame", background=COLORS["panel"])
    style.configure("PanelAlt.TFrame", background=COLORS["panel_alt"])
    style.configure("Sidebar.TFrame", background=COLORS["midnight"])

    style.configure("Brand.TLabel", background=COLORS["midnight"], foreground=COLORS["pale_gold"], font=("Georgia", 18, "bold"))
    style.configure("BrandSub.TLabel", background=COLORS["midnight"], foreground=COLORS["muted"], font=("Segoe UI", 9))
    style.configure("Hero.TLabel", background=COLORS["obsidian"], foreground=COLORS["marble"], font=("Georgia", 22, "bold"))
    style.configure("HeroSub.TLabel", background=COLORS["obsidian"], foreground=COLORS["muted"], font=("Segoe UI", 10))
    style.configure("Section.TLabel", background=COLORS["panel"], foreground=COLORS["pale_gold"], font=("Segoe UI", 10, "bold"))
    style.configure("Body.TLabel", background=COLORS["panel"], foreground=COLORS["marble"])
    style.configure("Muted.TLabel", background=COLORS["panel"], foreground=COLORS["muted"])
    style.configure("Status.TLabel", background=COLORS["obsidian"], foreground=COLORS["green"], font=("Segoe UI", 10, "bold"))
    style.configure("Metric.TLabel", background=COLORS["panel_alt"], foreground=COLORS["marble"], font=("Segoe UI", 13, "bold"))
    style.configure("MetricCaption.TLabel", background=COLORS["panel_alt"], foreground=COLORS["muted"], font=("Segoe UI", 8))
    style.configure("MetricGold.TLabel", background=COLORS["panel_alt"], foreground=COLORS["pale_gold"], font=("Segoe UI", 20, "bold"))
    style.configure("Success.TLabel", background=COLORS["panel"], foreground=COLORS["green"], font=("Segoe UI", 10, "bold"))
    style.configure("GoldStatus.TLabel", background=COLORS["panel"], foreground=COLORS["pale_gold"], font=("Segoe UI", 10, "bold"))
    style.configure("Badge.TLabel", background=COLORS["panel_alt"], foreground=COLORS["green"], font=("Segoe UI", 8, "bold"), padding=(7, 3))
    style.configure("PaperBadge.TLabel", background=COLORS["panel_alt"], foreground=COLORS["amber"], font=("Segoe UI", 8, "bold"), padding=(7, 3))
    style.configure("Horizontal.TProgressbar", troughcolor=COLORS["midnight"], background=COLORS["gold"], bordercolor=COLORS["border"], lightcolor=COLORS["gold"], darkcolor=COLORS["gold"])

    style.configure("TEntry", fieldbackground=COLORS["midnight"], foreground=COLORS["marble"], insertcolor=COLORS["marble"], bordercolor=COLORS["border"], padding=7)
    style.map("TEntry", bordercolor=[("focus", COLORS["gold"])])

    style.configure("TCombobox", fieldbackground=COLORS["midnight"], background=COLORS["midnight"], foreground=COLORS["marble"], arrowcolor=COLORS["gold"], bordercolor=COLORS["border"], padding=6)
    style.map("TCombobox", fieldbackground=[("readonly", COLORS["midnight"])], foreground=[("readonly", COLORS["marble"])], bordercolor=[("focus", COLORS["gold"])])

    style.configure("Gold.TButton", background=COLORS["gold"], foreground=COLORS["obsidian"], bordercolor=COLORS["gold"], padding=(12, 8), font=("Segoe UI", 10, "bold"))
    style.map("Gold.TButton", background=[("active", COLORS["pale_gold"]), ("pressed", COLORS["pale_gold"])])

    style.configure("Secondary.TButton", background=COLORS["panel_alt"], foreground=COLORS["marble"], bordercolor=COLORS["border"], padding=(11, 8))
    style.map("Secondary.TButton", background=[("active", COLORS["border"])], bordercolor=[("focus", COLORS["gold"])])

    style.configure("Danger.TButton", background=COLORS["panel_alt"], foreground=COLORS["danger"], bordercolor=COLORS["border"], padding=(11, 8))
    style.map("Danger.TButton", background=[("active", "#2A1B1D")])

    style.configure("Nav.TButton", background=COLORS["midnight"], foreground=COLORS["muted"], borderwidth=0, anchor="w", padding=(14, 9))
    style.map("Nav.TButton", background=[("active", COLORS["panel_alt"])], foreground=[("active", COLORS["pale_gold"])])

    style.configure("NavActive.TButton", background=COLORS["panel_alt"], foreground=COLORS["pale_gold"], bordercolor=COLORS["gold"], borderwidth=1, anchor="w", padding=(14, 9), font=("Segoe UI", 10, "bold"))
    style.map("NavActive.TButton", background=[("active", COLORS["panel_alt"])], foreground=[("active", COLORS["pale_gold"])])

    style.configure("Glass.TFrame", background=COLORS["panel"], bordercolor=COLORS["border"], relief="solid")
    style.configure("GlassAccent.TFrame", background=COLORS["panel_alt"], bordercolor=COLORS["violet"], relief="solid")
    style.configure("GlassMetric.TFrame", background=COLORS["panel_alt"], bordercolor=COLORS["blue"], relief="solid")
    style.configure("GlassRaised.TFrame", background=COLORS["midnight"], bordercolor=COLORS["border"], relief="solid")
    style.configure("GlassTitle.TLabel", background=COLORS["panel"], foreground=COLORS["pale_gold"], font=("Segoe UI", 10, "bold"))
    style.configure("GlassBody.TLabel", background=COLORS["panel"], foreground=COLORS["marble"], font=("Segoe UI", 10))
    style.configure("GlassMuted.TLabel", background=COLORS["midnight"], foreground=COLORS["muted"], font=("Segoe UI", 9))
    style.configure("GlassAccentTitle.TLabel", background=COLORS["panel_alt"], foreground=COLORS["violet"], font=("Segoe UI", 10, "bold"))
    style.configure("GlassAccentBody.TLabel", background=COLORS["panel_alt"], foreground=COLORS["marble"], font=("Segoe UI", 9))
    style.configure("GlassMetricCaption.TLabel", background=COLORS["panel_alt"], foreground=COLORS["muted"], font=("Segoe UI", 8, "bold"))
    style.configure("GlassMetricValue.TLabel", background=COLORS["panel_alt"], foreground=COLORS["blue"], font=("Segoe UI", 18, "bold"))
    style.configure("GlassSymbol.TLabel", background=COLORS["midnight"], foreground=COLORS["pale_gold"], font=("Segoe UI", 16, "bold"))
    style.configure("GlassChip.TLabel", background=COLORS["panel_alt"], foreground=COLORS["blue"], font=("Segoe UI", 8, "bold"), padding=(7, 3))
    style.configure("GlassPositive.TLabel", background=COLORS["midnight"], foreground=COLORS["green"], font=("Cascadia Mono", 9, "bold"))
    style.configure("GlassNegative.TLabel", background=COLORS["midnight"], foreground=COLORS["danger"], font=("Cascadia Mono", 9, "bold"))
    style.configure("Card.TLabelframe", background=COLORS["panel"], bordercolor=COLORS["border"], relief="solid")
    style.configure("Card.TLabelframe.Label", background=COLORS["panel"], foreground=COLORS["pale_gold"], font=("Segoe UI", 10, "bold"))
    style.configure("Treeview", background=COLORS["midnight"], fieldbackground=COLORS["midnight"], foreground=COLORS["marble"], rowheight=30, bordercolor=COLORS["border"])
    style.configure("Treeview.Heading", background=COLORS["panel_alt"], foreground=COLORS["pale_gold"], font=("Segoe UI", 9, "bold"), padding=(8, 7))
    style.map("Treeview", background=[("selected", COLORS["panel_alt"])], foreground=[("selected", COLORS["pale_gold"])])
    style.map("Treeview.Heading", background=[("active", COLORS["border"])])

    return style
