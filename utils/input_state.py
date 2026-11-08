"""
utils/input_state.py

Safe helpers for reading key state.

`keyboard.is_pressed()` raises ValueError for names it cannot map (a control
bound to a mouse side button, a character missing from the active layout, ...).
Inside a module thread that exception used to kill the thread silently: the
toggle stayed ON but the module did nothing. These helpers never raise.
"""

import keyboard

from utils.sendinput import get_vk


def is_key_logically_down(key_name) -> bool:
    """Key state as Windows sees it (includes keys Chione injected)."""
    if not key_name:
        return False
    try:
        return keyboard.is_pressed(str(key_name).lower())
    except Exception:
        return False


def is_key_physically_down(gui, key_name) -> bool:
    """True only if the USER is holding the key (Chione's own presses ignored)."""
    vk = get_vk(key_name)
    hook = getattr(gui, "mouse_hook", None)
    if vk and hook is not None:
        try:
            return hook.is_key_physically_down(vk)
        except Exception:
            pass
    return is_key_logically_down(key_name)
