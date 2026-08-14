"""
utils/sendinput.py

Keyboard simulation using Win32 keybd_event with hardware scan codes and virtual key codes.
Uses keybd_event instead of SendInput to avoid 64-bit struct alignment issues.
Does NOT install any keyboard hooks — will never interfere with volume/Fn keys.
"""

import ctypes

# Flags for keybd_event
KEYEVENTF_SCANCODE    = 0x0008
KEYEVENTF_KEYUP       = 0x0002
KEYEVENTF_EXTENDEDKEY = 0x0001

# Map key name to (vk_code, scan_code, is_extended)
_KEY_MAPPING = {
    # Letters
    'a': (0x41, 0x1E, False), 'b': (0x42, 0x30, False), 'c': (0x43, 0x2E, False),
    'd': (0x44, 0x20, False), 'e': (0x45, 0x12, False), 'f': (0x46, 0x21, False),
    'g': (0x47, 0x22, False), 'h': (0x48, 0x23, False), 'i': (0x49, 0x17, False),
    'j': (0x4A, 0x24, False), 'k': (0x4B, 0x25, False), 'l': (0x4C, 0x26, False),
    'm': (0x4D, 0x32, False), 'n': (0x4E, 0x31, False), 'o': (0x4F, 0x18, False),
    'p': (0x50, 0x19, False), 'q': (0x51, 0x10, False), 'r': (0x52, 0x13, False),
    's': (0x53, 0x1F, False), 't': (0x54, 0x14, False), 'u': (0x55, 0x16, False),
    'v': (0x56, 0x2F, False), 'w': (0x57, 0x11, False), 'x': (0x58, 0x2D, False),
    'y': (0x59, 0x15, False), 'z': (0x5A, 0x2C, False),
    # Numbers
    '1': (0x31, 0x02, False), '2': (0x32, 0x03, False), '3': (0x33, 0x04, False),
    '4': (0x34, 0x05, False), '5': (0x35, 0x06, False), '6': (0x36, 0x07, False),
    '7': (0x37, 0x08, False), '8': (0x38, 0x09, False), '9': (0x39, 0x0A, False),
    '0': (0x30, 0x0B, False),
    # Modifiers
    'shift': (0x10, 0x2A, False), 'left shift': (0x10, 0x2A, False), 'right shift': (0x10, 0x36, False),
    'ctrl': (0x11, 0x1D, False), 'left ctrl': (0x11, 0x1D, False), 'right ctrl': (0x11, 0x1D, True),
    'control': (0x11, 0x1D, False),
    'alt': (0x12, 0x38, False), 'left alt': (0x12, 0x38, False), 'right alt': (0x12, 0x38, True),
    # Special keys
    'space': (0x20, 0x39, False),
    'enter': (0x0D, 0x1C, False),
    'escape': (0x1B, 0x01, False), 'esc': (0x1B, 0x01, False),
    'tab': (0x09, 0x0F, False),
    'backspace': (0x08, 0x0E, False),
    'capslock': (0x14, 0x3A, False),
    # Function keys
    'f1': (0x70, 0x3B, False), 'f2': (0x71, 0x3C, False), 'f3': (0x72, 0x3D, False),
    'f4': (0x73, 0x3E, False), 'f5': (0x74, 0x3F, False), 'f6': (0x75, 0x40, False),
    'f7': (0x76, 0x41, False), 'f8': (0x77, 0x42, False), 'f9': (0x78, 0x43, False),
    'f10': (0x79, 0x44, False), 'f11': (0x7A, 0x57, False), 'f12': (0x7B, 0x58, False),
    # Punctuation
    '`': (0xC0, 0x29, False), '-': (0xBD, 0x0C, False), '=': (0xBB, 0x0D, False),
    '[': (0xDB, 0x1A, False), ']': (0xDD, 0x1B, False), '\\': (0xDC, 0x2B, False),
    ';': (0xBA, 0x27, False), "'": (0xDE, 0x28, False), ',': (0xBC, 0x33, False),
    '.': (0xBE, 0x34, False), '/': (0xBF, 0x35, False),
    # Arrow keys (extended)
    'up': (0x26, 0x48, True), 'down': (0x28, 0x50, True),
    'left': (0x25, 0x4B, True), 'right': (0x27, 0x4D, True),
    # Numpad keys
    'numpad 0': (0x60, 0x52, False), 'numpad 1': (0x61, 0x4F, False),
    'numpad 2': (0x62, 0x50, False), 'numpad 3': (0x63, 0x51, False),
    'numpad 4': (0x64, 0x4B, False), 'numpad 5': (0x65, 0x4C, False),
    'numpad 6': (0x66, 0x4D, False), 'numpad 7': (0x67, 0x47, False),
    'numpad 8': (0x68, 0x48, False), 'numpad 9': (0x69, 0x49, False),
}

# Configure types for keybd_event API
ctypes.windll.user32.keybd_event.argtypes = [
    ctypes.c_ubyte,
    ctypes.c_ubyte,
    ctypes.c_ulong,
    ctypes.c_void_p
]
ctypes.windll.user32.keybd_event.restype = None


def _get_key_details(key_name: str):
    """Return (vk, scan_code, is_extended) for a key name, or None."""
    key_lower = key_name.lower().strip()
    result = _KEY_MAPPING.get(key_lower)
    if result:
        return result
    # Fallback for single characters: use VkKeyScanW and MapVirtualKeyW
    if len(key_lower) == 1:
        try:
            vk = ctypes.windll.user32.VkKeyScanW(ctypes.c_wchar(key_lower)) & 0xFF
            if vk != 0xFF:
                scan = ctypes.windll.user32.MapVirtualKeyW(vk, 0)
                if scan:
                    return (vk, scan, False)
        except Exception:
            pass
    return None


def press_key(key_name: str):
    """Simulate pressing (holding down) a key by name using keybd_event."""
    result = _get_key_details(key_name)
    if result:
        vk, scan, extended = result
        flags = KEYEVENTF_SCANCODE
        if extended:
            flags |= KEYEVENTF_EXTENDEDKEY
        ctypes.windll.user32.keybd_event(vk, scan, flags, None)


def release_key(key_name: str):
    """Simulate releasing a key by name using keybd_event."""
    result = _get_key_details(key_name)
    if result:
        vk, scan, extended = result
        flags = KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP
        if extended:
            flags |= KEYEVENTF_EXTENDEDKEY
        ctypes.windll.user32.keybd_event(vk, scan, flags, None)
