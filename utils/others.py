import webbrowser, sys, os
import tkinter as tk


def open_web(url):
    webbrowser.open_new(url)


def resource(relative_path):
    if getattr(sys, 'frozen', False):
        # Inside PyInstaller bundle: files are extracted to _MEIPASS
        base_path = sys._MEIPASS
    else:
        # Running as a script: base is the project root (parent of utils/)
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def get_file_path(filename):
    # Always return a path relative to the assets folder.
    # resource() will prepend _MEIPASS (frozen) or the project root (dev).
    return os.path.join("assets", filename)


def set_icon(window):
    """Set window icon safely — uses iconphoto when frozen (PyInstaller) to avoid
    the _MEIPASS path issue with iconbitmap, falls back to iconbitmap in dev."""
    ico_path = resource(get_file_path("icon.ico"))
    if getattr(sys, 'frozen', False):
        try:
            from PIL import Image, ImageTk
            img = Image.open(ico_path)
            photo = ImageTk.PhotoImage(img)
            window.iconphoto(True, photo)
            if not hasattr(window, '_icon_ref'):
                window._icon_ref = photo
        except Exception:
            pass
    else:
        window.iconbitmap(ico_path)


def set_settings(self):
    """Re-apply saved General checkbox states to their command handlers."""
    general_checkboxes = {
        key: value for key, value in self.checkboxs.items()
        if key.startswith('General')
    }
    for key, value in general_checkboxes.items():
        module = key.split('_')[0]
        number = int(key.split('_')[-1])
        module_name = self.modules.get(module)
        cb_command = module_name.get(f"checkbox_command{number + 1}")
        if cb_command is None:
            continue
        if isinstance(value, bool):
            cb_command(self, module, value)
        else:
            cb_command(self, module, value.get())


def is_cursor_visible() -> bool:
    try:
        import win32gui
        flags, _, _ = win32gui.GetCursorInfo()
        return flags == 1
    except Exception:
        return False


def modules_should_run(gui) -> bool:
    """
    Arbitration function that gates module execution on the two filter flags.

    Returns False (module should NOT run) if:
      - focus_filter_enabled is True and the game window is not in the foreground, or
      - menu_filter_enabled  is True and a game menu is currently open (unless shifting).
    Returns True otherwise.
    """
    if getattr(gui, 'focus_filter_enabled', False) and not gui.currently_in_foreground:
        return False
    if getattr(gui, 'menu_filter_enabled', False) and gui.currently_in_foreground and (gui.currently_in_menu or is_cursor_visible()):
        # Allow clicking in menus (inventories) while shifting (fast looting)
        from utils.hotkeys import get_controls
        import keyboard
        crouch_key = get_controls(gui, "Controls_1", "SHIFT")
        if keyboard.is_pressed(crouch_key):
            return True
        return False
    return True
