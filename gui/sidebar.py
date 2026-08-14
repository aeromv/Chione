"""
gui/sidebar.py

Vertical navigation rail (SidebarNav) replacing the old flat-button sidebar.
Each category gets an icon glyph + text label.  The active item is highlighted
with an accent-colour bar on its left edge.
"""

import tkinter as tk
from config.setup import (
    MENU_COLOR, FONT_COLOR, ACCENT_COLOR, INACTIVE_COLOR,
    FONT, FONT_SM, SIDEBAR_WIDTH, SIDEBAR_ITEM_H, SIDEBAR_ACCENT_W,
)


class _NavItem(tk.Frame):
    """A single navigation item: accent bar + label."""

    def __init__(self, parent, category: str, on_click):
        super().__init__(parent, bg=MENU_COLOR,
                         width=SIDEBAR_WIDTH, height=SIDEBAR_ITEM_H)
        self.pack_propagate(False)
        self.category = category

        # Accent bar on the left edge (hidden when inactive)
        self._accent = tk.Frame(self, bg=ACCENT_COLOR,
                                width=SIDEBAR_ACCENT_W, height=SIDEBAR_ITEM_H)
        self._accent.pack(side=tk.LEFT, fill=tk.Y)
        self._accent.pack_propagate(False)

        # Label
        self._label = tk.Label(
            self,
            text=category,
            bg=MENU_COLOR,
            fg=FONT_COLOR,
            font=(FONT, FONT_SM),
            anchor=tk.W,
            padx=6,
        )
        self._label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Bindings
        self.bind("<Button-1>", lambda _: on_click(category))
        self._label.bind("<Button-1>", lambda _: on_click(category))
        self._accent.bind("<Button-1>", lambda _: on_click(category))

        # Hover effect
        for widget in (self, self._label, self._accent):
            widget.bind("<Enter>", self._on_enter)
            widget.bind("<Leave>", self._on_leave)

        self._active = False

    def set_active(self, active: bool):
        self._active = active
        color = ACCENT_COLOR if active else MENU_COLOR
        self._accent.config(bg=color)
        self._label.config(fg=FONT_COLOR if active else INACTIVE_COLOR)

    def _on_enter(self, _=None):
        if not self._active:
            self._label.config(bg="#2A2A2A")
            self.config(bg="#2A2A2A")

    def _on_leave(self, _=None):
        self._label.config(bg=MENU_COLOR)
        self.config(bg=MENU_COLOR)


class SidebarNav(tk.Frame):
    """
    Vertical navigation rail.

    Parameters
    ----------
    parent      : tk parent widget
    categories  : ordered list of category strings from ModuleCategory
    on_select   : callback called with the selected category string
    """

    def __init__(self, parent, categories, on_select):
        super().__init__(parent, bg=MENU_COLOR, width=SIDEBAR_WIDTH)
        self.pack_propagate(False)

        self._on_select = on_select
        self._items: dict[str, _NavItem] = {}

        # App title at the top
        title_label = tk.Label(
            self,
            text="Chione",
            bg=MENU_COLOR,
            fg=ACCENT_COLOR,
            font=(FONT, 20, "bold"),
        )
        title_label.pack(pady=(12, 8))

        # Thin separator
        sep = tk.Frame(self, bg=ACCENT_COLOR, height=1)
        sep.pack(fill=tk.X, padx=8, pady=(0, 4))

        # Navigation items
        for cat in categories:
            item = _NavItem(self, cat, self._handle_click)
            item.pack(fill=tk.X)
            self._items[cat] = item

    def _handle_click(self, category: str):
        self.set_active(category)
        self._on_select(category)

    def set_active(self, category: str):
        """Highlight the specified item and deselect all others."""
        for cat, item in self._items.items():
            item.set_active(cat == category)
