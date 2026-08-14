"""
gui/status_bar.py

StatusBar — bottom strip showing active modules as pill badges.
All updates from non-main threads are dispatched via root.after(0, ...).
"""

import tkinter as tk
from config.setup import (
    CONTENT_COLOR, FONT_COLOR, ACCENT_COLOR, FONT, FONT_SM,
    STATUS_BAR_H, STATUS_PILL_PAD_X, STATUS_PILL_PAD_Y,
    FEATURE_COLOR,
)


class StatusBar(tk.Frame):
    """
    Bottom status bar.

    Left side  : version string + author.
    Right side : one pill badge per active module.
    """

    def __init__(self, parent, version: str, dev: str):
        super().__init__(parent, bg=CONTENT_COLOR,
                         height=STATUS_BAR_H)
        self.pack_propagate(False)

        # Accent line at top of bar
        top_line = tk.Frame(self, bg=FEATURE_COLOR, height=1)
        top_line.pack(side=tk.TOP, fill=tk.X)

        # Left: version + author
        left_frame = tk.Frame(self, bg=CONTENT_COLOR)
        left_frame.pack(side=tk.LEFT, fill=tk.Y)

        tk.Label(
            left_frame,
            text=f"v{version}  {dev}",
            bg=CONTENT_COLOR,
            fg=FONT_COLOR,
            font=(FONT, FONT_SM),
        ).pack(side=tk.LEFT, padx=6, pady=2)

        # Right: pills container
        self._pills_frame = tk.Frame(self, bg=CONTENT_COLOR)
        self._pills_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=4)

        # Track pill widgets per module
        self._pills: dict[str, tk.Label] = {}

        # Store root for after() calls
        self._root = parent.winfo_toplevel()

    # ------------------------------------------------------------------
    # Public API (thread-safe via root.after)
    # ------------------------------------------------------------------

    def set_active(self, module: str):
        """Add a pill badge for the given module (safe to call from any thread)."""
        self._root.after(0, self._add_pill, module)

    def set_inactive(self, module: str):
        """Remove the pill badge for the given module (safe to call from any thread)."""
        self._root.after(0, self._remove_pill, module)

    # ------------------------------------------------------------------
    # Internal helpers (must run on main thread)
    # ------------------------------------------------------------------

    def _add_pill(self, module: str):
        if module in self._pills:
            return  # already shown
        pill = tk.Label(
            self._pills_frame,
            text=module,
            bg=ACCENT_COLOR,
            fg="#ffffff",
            font=(FONT, FONT_SM),
            padx=STATUS_PILL_PAD_X,
            pady=STATUS_PILL_PAD_Y,
            relief=tk.FLAT,
        )
        pill.pack(side=tk.LEFT, padx=2, pady=2)
        self._pills[module] = pill

    def _remove_pill(self, module: str):
        pill = self._pills.pop(module, None)
        if pill is not None:
            pill.destroy()
