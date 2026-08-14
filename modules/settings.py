from utils.hotkeys import check_special_chars
from utils.options import get_user_path
from utils.others import get_file_path
from utils.others import set_icon
from utils.others import resource
import win32gui
import os
from config.setup import *
import tkinter as tk


# ---------------------------------------------------------------------------
# Settings module — filter logic replaced with simple boolean flag setters.
# Race conditions from the old threading globals are eliminated.
# ---------------------------------------------------------------------------

def thread_window(self, _, var):
    """
    Set the focus-filter flag.
    No new thread is needed — just update the boolean flag on the GUI instance.
    """
    self.focus_filter_enabled = bool(var)


def thread_menu(self, _, var):
    """
    Set the menu-filter flag.
    No new thread is needed — just update the boolean flag on the GUI instance.
    """
    self.menu_filter_enabled = bool(var)


def hide_taskbar(self, _, var):
    self.root.overrideredirect(var)


def dis_tooltips(self, _, var):
    self.tooltips_enabled = not var


def on_top(self, _, var):
    self.root.attributes("-topmost", var)


def reset_settings(self, _, button_name=None, text_value=None):
    try:
        os.remove(get_user_path(self.json_file))
        self.root.destroy()
    except FileNotFoundError:
        pass


def set_controls(self, _, button_name, text_value):
    popup = tk.Toplevel()
    popup.title("Set new Key")
    popup.geometry("400x200")
    popup.configure(bg=CONTENT_COLOR)
    set_icon(popup)
    popup.resizable(False, False)
    popup.attributes("-topmost", True)

    self.active_hotkey_popup = popup

    def assign_key(key, scan_code=None):
        if key == "Escape" or key == "esc":
            self.buttons[button_name].config(text="None")
            popup.destroy()
        else:
            key = key.split('_')[0]
            key = check_special_chars(key)
            self.buttons[button_name].config(text=f"[{key.upper()}]")
            popup.destroy()
        self.active_hotkey_popup = None
        self.active_hotkey_popup_callback = None

    self.active_hotkey_popup_callback = assign_key

    def on_closing():
        self.active_hotkey_popup = None
        self.active_hotkey_popup_callback = None
        popup.destroy()

    popup.protocol("WM_DELETE_WINDOW", on_closing)

    label = tk.Label(
        popup, text="Press a key",
        font=(FONT, 12), fg=FONT_COLOR, bg=CONTENT_COLOR
    )
    label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    popup.focus_force()
