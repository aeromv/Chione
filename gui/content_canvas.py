"""
gui/content_canvas.py

ScrollableContentCanvas — a tk.Canvas + vertical tk.Scrollbar wrapper that
hosts module cards.  The scrollbar is shown only when content overflows.
"""

import tkinter as tk
from config.setup import CONTENT_COLOR


class ScrollableContentCanvas(tk.Frame):
    """
    A scrollable content area.

    Use get_inner_frame() to obtain the Frame where module cards should be packed.
    Call clear() before rebuilding and scroll_to_top() after navigation.
    """

    def __init__(self, parent):
        super().__init__(parent, bg=CONTENT_COLOR)

        # Canvas + scrollbar
        self._canvas = tk.Canvas(self, bg=CONTENT_COLOR,
                                 highlightthickness=0, bd=0)
        self._scrollbar = tk.Scrollbar(self, orient=tk.VERTICAL,
                                       command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._on_yscroll)

        self._scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Inner frame (where module cards live)
        self._inner = tk.Frame(self._canvas, bg=CONTENT_COLOR)
        self._inner_id = self._canvas.create_window(
            (0, 0), window=self._inner, anchor=tk.NW
        )

        # Bindings
        self._inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._canvas.bind("<MouseWheel>", self._on_mousewheel)
        self._inner.bind("<MouseWheel>", self._on_mousewheel)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_inner_frame(self) -> tk.Frame:
        """Return the inner frame where module cards should be packed."""
        return self._inner

    def clear(self):
        """Destroy all child widgets in the inner frame and reset grid configurations."""
        for widget in self._inner.winfo_children():
            widget.destroy()
        
        # Reset grid configurations to prevent layout bleed across tab navigation
        cols, rows = self._inner.grid_size()
        for i in range(cols):
            self._inner.columnconfigure(i, weight=0, uniform="")
        for i in range(rows):
            self._inner.rowconfigure(i, weight=0, uniform="")

    def scroll_to_top(self):
        """Reset scroll position to the top."""
        self._canvas.yview_moveto(0.0)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _on_yscroll(self, first, last):
        """Show scrollbar only when content overflows viewport."""
        first, last = float(first), float(last)
        if first <= 0.0 and last >= 1.0:
            # Content fits — hide scrollbar
            self._scrollbar.pack_forget()
        else:
            if not self._scrollbar.winfo_ismapped():
                self._scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            self._scrollbar.set(first, last)

    def _on_inner_configure(self, _=None):
        """Update canvas scroll region when inner frame changes size."""
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        """Keep inner frame width and minimum height equal to canvas dimensions."""
        self._canvas.itemconfig(self._inner_id, width=event.width)
        # Stretch inner frame to fill canvas height when content is shorter
        inner_h = self._inner.winfo_reqheight()
        if inner_h < event.height:
            self._canvas.itemconfig(self._inner_id, height=event.height)
        else:
            # Let content dictate height (for scrolling)
            self._canvas.itemconfig(self._inner_id, height=inner_h)

    def _on_mousewheel(self, event):
        """Scroll on Windows mouse-wheel events."""
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
