"""
utils/options.py

Save / load settings with robust error handling and type-safe casting.
Backward compatible with options.json files written by Chione v0.1.8.
"""

import json
import os
import sys

from config.setup import MIN_SIZE_W, MIN_SIZE_H


def get_user_path(json_file: str) -> str:
    filename = os.path.basename(json_file)
    home_directory = os.path.expanduser("~")
    return os.path.join(home_directory, filename)


# ---------------------------------------------------------------------------
# Load logic
# ---------------------------------------------------------------------------

def load_logic(self, path: str) -> None:
    """
    Parse a SaveFile JSON from `path` and restore all widget-value dicts.
    Numeric values are cast with float()/int(); booleans with bool().
    """
    with open(path, 'r', encoding='utf-8') as file:
        modules_data = json.load(file)

    if not isinstance(modules_data, list) or len(modules_data) == 0:
        raise ValueError("SaveFile is not a valid JSON array.")

    # Restore window geometry
    width  = max(int(modules_data[0].get('width',  MIN_SIZE_W)), MIN_SIZE_W)
    height = max(int(modules_data[0].get('height', MIN_SIZE_H)), MIN_SIZE_H)
    self.root.geometry(f"{width}x{height}")

    for module_data in modules_data:
        module_name = module_data.get("name")
        module = self.modules.get(module_name)

        if not module:
            continue  # unknown module — skip silently

        # Restore hotkey
        module["hotkey"] = module_data.get("hotkey", False)
        module["hotkey_scan"] = module_data.get("hotkey_scan", None)

        # Restore sliders (cast to float for safety)
        for x in range(module.get("slider", 0)):
            raw = module_data.get(f"slider_{x}")
            if raw is not None:
                try:
                    self.sliders[f"{module_name}_{x}"] = float(raw)
                except (TypeError, ValueError):
                    pass

        # Restore checkboxes (cast to bool)
        for x in range(module.get("checkbox", 0)):
            raw = module_data.get(f"checkbox_{x}")
            if raw is not None:
                self.checkboxs[f"{module_name}_{x}"] = bool(raw)

        # Restore dropdowns (must be a string)
        for x in range(module.get("dropdown", 0)):
            raw = module_data.get(f"dropdown_{x}")
            if raw is not None and isinstance(raw, str):
                self.dropdowns[f"{module_name}_{x}"] = raw

        # Restore buttons (must be a string)
        for x in range(module.get("button", 0)):
            raw = module_data.get(f"button_{x}")
            if raw is not None and isinstance(raw, str):
                self.buttons[f"{module_name}_{x}"] = raw


def load_settings(self, json_file: str) -> None:
    """
    Load settings from the user's home-directory copy of options.json.
    Falls back to the bundled default if missing or corrupted.
    """
    user_path = get_user_path(json_file)

    try:
        load_logic(self, user_path)
        return
    except FileNotFoundError:
        pass
    except (json.JSONDecodeError, ValueError, KeyError, TypeError) as exc:
        print(
            f"WARNING: Could not load settings from '{user_path}': {exc}. "
            "Resetting to default settings.",
            file=sys.stderr,
        )
        try:
            if os.path.exists(user_path):
                os.remove(user_path)
        except Exception:
            pass

    # Fallback to bundled default
    try:
        load_logic(self, json_file)
    except (FileNotFoundError, json.JSONDecodeError, ValueError,
            KeyError, TypeError) as exc:
        print(
            f"WARNING: Could not load bundled defaults from '{json_file}': {exc}. "
            "Starting with factory defaults.",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# Save logic
# ---------------------------------------------------------------------------

def save_logic(self, path: str) -> None:
    """Serialize all widget-value dicts to a SaveFile JSON at `path`."""
    modules_data = []

    # First element: window geometry
    modules_data.append({
        "width":  self.root.winfo_width(),
        "height": self.root.winfo_height(),
    })

    for module_name, module_info in self.modules.items():
        module_data = {
            "name":        module_name,
            "hotkey":      module_info.get("hotkey", False),
            "hotkey_scan": module_info.get("hotkey_scan", None),
        }

        # Sliders
        for x in range(module_info.get("slider", 0)):
            slider = self.sliders.get(f"{module_name}_{x}")
            if hasattr(slider, 'get'):
                module_data[f"slider_{x}"] = slider.get()
            elif isinstance(slider, (int, float)):
                module_data[f"slider_{x}"] = slider
            else:
                module_data[f"slider_{x}"] = None

        # Checkboxes
        for x in range(module_info.get("checkbox", 0)):
            cb = self.checkboxs.get(f"{module_name}_{x}")
            if hasattr(cb, 'get'):
                module_data[f"checkbox_{x}"] = cb.get()
            elif isinstance(cb, bool):
                module_data[f"checkbox_{x}"] = cb
            else:
                module_data[f"checkbox_{x}"] = None

        # Dropdowns
        for x in range(module_info.get("dropdown", 0)):
            dd = self.dropdowns.get(f"{module_name}_{x}")
            if hasattr(dd, 'selected_option'):
                module_data[f"dropdown_{x}"] = dd.selected_option.get()
            elif isinstance(dd, str):
                module_data[f"dropdown_{x}"] = dd
            else:
                module_data[f"dropdown_{x}"] = None

        # Buttons
        for x in range(module_info.get("button", 0)):
            btn = self.buttons.get(f"{module_name}_{x}")
            if isinstance(btn, str):
                module_data[f"button_{x}"] = btn
            elif btn is not None:
                try:
                    module_data[f"button_{x}"] = btn.cget("text")
                except Exception:
                    module_data[f"button_{x}"] = None
            else:
                module_data[f"button_{x}"] = None

        modules_data.append(module_data)

    with open(path, 'w', encoding='utf-8') as file:
        json.dump(modules_data, file, indent=4)


def save_settings(self, json_file: str) -> None:
    """Save current settings then close the application."""
    user_path = get_user_path(json_file)
    save_logic(self, user_path)
    self.root.destroy()
