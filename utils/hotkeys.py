from tkinter.messagebox import showinfo
from utils.others import get_file_path
from utils.others import set_icon
from utils.others import resource
from utils.executor import *
from config.setup import *
import tkinter as tk
import re
import ctypes

def set_hotkey(self, button, module):
    self.hotkeys_enabled = False
    popup = tk.Toplevel()
    popup.title("Set Hotkey")
    popup.geometry("400x200")
    popup.configure(bg=CONTENT_COLOR)
    set_icon(popup)
    popup.resizable(False, False)
    popup.attributes("-topmost", True)  # Ensure the popup stays on top
    
    self.active_hotkey_popup = popup

    def assign_key(key, scan_code=None):
        if key == "Escape" or key == "esc":
            self.modules[module]["hotkey"] = "None"
            self.modules[module]["hotkey_scan"] = None
            button.config(text="Bind Hotkey")
            popup.destroy()
        else:
            if check_already_in_use(self, key, scan_code):
                showinfo("Error", "This hotkey is already in use.")
                popup.focus_force()
                return
            
            if not key.startswith("xbutton") and (not key.isalnum() or len(key) > 1):
                key = map_sepcial_chars(key.lower())
                if key is None:
                    showinfo("Error", "Special character not supported as a hotkey.")
                    popup.focus_force()
                    return
            
            self.modules[module]["hotkey"] = key
            self.modules[module]["hotkey_scan"] = scan_code
            
            # Format display text: "Mouse 4" or "Mouse 5" for xbutton1/xbutton2, otherwise uppercase
            if key.startswith("xbutton"):
                btn_num = 4 if key == "xbutton1" else 5
                button.config(text=f"Key: [MOUSE {btn_num}]")
            else:
                button.config(text=f"Key: [{key.upper()}]")
            popup.destroy()

        self.hotkeys_enabled = True
        self.active_hotkey_popup = None
        self.active_hotkey_popup_callback = None

    self.active_hotkey_popup_callback = assign_key

    def on_closing():
        self.hotkeys_enabled = True
        self.active_hotkey_popup = None
        self.active_hotkey_popup_callback = None
        popup.destroy()

    # Make sure that hotkeys are enabled when the popup is closed
    popup.protocol("WM_DELETE_WINDOW", on_closing)

    label = tk.Label(popup, text="Press a key or Mouse Side Button", font=(FONT, 12), fg=FONT_COLOR, bg=CONTENT_COLOR)
    label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    popup.focus_force()

def normalize_hotkey(key):
    if not key:
        return ""
    key_str = str(key).lower().replace('_', ' ').replace('-', ' ').strip()
    
    # Direct mappings for Tkinter/keyboard names to standard single characters
    mapping = {
        'grave': '`',
        'dead grave': '`',
        'comma': ',',
        'period': '.',
        'minus': '-',
        'plus': '+',
        'equal': '=',
        'slash': '/',
        'backslash': '\\',
        'semicolon': ';',
        'apostrophe': "'",
        'bracketleft': '[',
        'bracketright': ']',
        'return': 'enter',
        'escape': 'esc',
        'space': 'space',
        'control l': 'ctrl',
        'control r': 'ctrl',
        'control': 'ctrl',
        'shift l': 'shift',
        'shift r': 'shift',
        'shift': 'shift',
        'alt l': 'alt',
        'alt r': 'alt',
        'alt': 'alt',
        'caps': 'capslock',
        'capslock': 'capslock',
    }
    
    if key_str in mapping:
        return mapping[key_str]
        
    if "grave" in key_str:
        return "`"
        
    # Remove bracket wraps if it was saved like "[W]"
    key_str = re.sub(r'^\[|\]$', '', key_str)
    return key_str

def on_key_press(self, event):
    key_name = event.name
    if not key_name:
        return

    popup = getattr(self, "active_hotkey_popup", None)
    callback = getattr(self, "active_hotkey_popup_callback", None)
    if popup and callback:
        self.root.after(0, lambda: callback(key_name, event.scan_code))
        return

    try:
        pressed_normalized = normalize_hotkey(key_name)
        
        for module, data in self.modules.items():
            if data.get("hotkey") != False:
                # Match by hardware scan code first (layout independent)
                saved_scan = data.get("hotkey_scan")
                if saved_scan is not None and saved_scan == event.scan_code:
                    if self.hotkeys_enabled:
                        toggle_and_execute(self, module)
                    continue

                # Fallback to name match
                saved_normalized = normalize_hotkey(data.get("hotkey"))
                if saved_normalized and saved_normalized == pressed_normalized:
                    if self.hotkeys_enabled:
                        toggle_and_execute(self, module)
    except Exception as e:
        print(f"[Chione] Error in hotkey execution: {e}", flush=True)

def on_mouse_hotkey_press(self, key_name):
    try:
        pressed_normalized = normalize_hotkey(key_name)
        print(f"[Chione] Mouse side-button pressed: '{key_name}' (Normalized: '{pressed_normalized}')", flush=True)
        for module, data in self.modules.items():
            if data.get("hotkey") != False:
                saved_normalized = normalize_hotkey(data.get("hotkey"))
                if saved_normalized and saved_normalized == pressed_normalized:
                    if self.hotkeys_enabled:
                        toggle_and_execute(self, module)
    except Exception as e:
        print(f"[Chione] Error in mouse hotkey execution: {e}", flush=True)

def check_already_in_use(self, key, scan_code=None):
    normalized_target = normalize_hotkey(key)
    if normalized_target == "none" or not normalized_target:
        return False
    for module, data in self.modules.items():
        if data.get("hotkey") != False:
            if scan_code is not None and data.get("hotkey_scan") == scan_code:
                return True
            saved_normalized = normalize_hotkey(data.get("hotkey"))
            if saved_normalized and saved_normalized == normalized_target:
                return True
    return False

def get_controls(self, action_key, default):
    key = self.buttons.get(action_key, default)
    if key == "None" or key is None:
        return default
    
    if isinstance(key, str):
        key = re.sub(r'^\[|\]$', '', key)
        return key
    else:
        try:
            if hasattr(key, "winfo_exists") and key.winfo_exists():
                key_text = key.cget("text")
                key_text = re.sub(r'^\[|\]$', '', key_text)
                return key_text
        except Exception:
            pass
        return default
    
def map_sepcial_chars(key):
    special_chars_mapping = {
        'control_l': 'ctrl_l',
        'shift_l': 'shift',
        'win_l': 'cmd',
        'less': '<',
        'app': 'menu',
        'control_r': 'ctrl_r',
        'comma': ',',
        'period': '.',
        'minus': '-',
        'return': 'enter',
        'ssharp': 'ß',
        'plus': '+',
        'numbersign': '#',
        'next': 'page_down',
        'prior': 'page_up',
        'multi_key': None, # Not supported
        'grave': '`',
        'dead_grave': '`',
        'apostrophe': "'",
        'backslash': '\\',
        'slash': '/',
        'equal': '=',
        'bracketleft': '[',
        'bracketright': ']',
        'semicolon': ';',
    }

    return special_chars_mapping.get(key, key)

def check_special_chars(key):
    # Goofy solution, the problem is tkinter and pyautogui use different names for the same key
    if key == "Control": return "ctrl"
    elif key == "Caps": return "capslock"
    else: return key 