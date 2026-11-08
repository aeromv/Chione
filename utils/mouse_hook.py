"""
utils/mouse_hook.py

Low-level mouse + keyboard hooks that track the PHYSICAL state of buttons and
keys. Events injected by Chione itself (mouse_event / keybd_event / SendInput)
are ignored, so the modules can tell "the user is holding W" apart from
"Chione pressed W".

Rules for the hook callbacks (Windows silently removes a low-level hook whose
callback is too slow, which made the clicker stop reacting to the mouse):
  * never touch Tkinter from here — events for the GUI are handed over through
    gui.post(), a non-blocking queue drained on the Tk main thread;
  * never suppress anything — always call CallNextHookEx.
"""

import ctypes
import ctypes.wintypes
import threading

# Win32 hook constants
WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP   = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP   = 0x0205
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP   = 0x020C
WM_KEYDOWN     = 0x0100
WM_KEYUP       = 0x0101
WM_SYSKEYDOWN  = 0x0104
WM_SYSKEYUP    = 0x0105

LLMHF_INJECTED          = 0x01
LLMHF_LOWER_IL_INJECTED = 0x02
LLKHF_LOWER_IL_INJECTED = 0x02
LLKHF_INJECTED          = 0x10

# Left/right specific modifier VKs -> generic VK, so callers can ask for 0x10
_GENERIC_VK = {
    0xA0: 0x10, 0xA1: 0x10,  # L/R SHIFT   -> SHIFT
    0xA2: 0x11, 0xA3: 0x11,  # L/R CONTROL -> CONTROL
    0xA4: 0x12, 0xA5: 0x12,  # L/R MENU    -> ALT
}


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", POINT),
        ("mouseData", ctypes.wintypes.DWORD),
        ("flags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p)
    ]


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", ctypes.wintypes.DWORD),
        ("scanCode", ctypes.wintypes.DWORD),
        ("flags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p)
    ]


# Define types for Win32 API functions to prevent OverflowError on 64-bit systems
LRESULT = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long

_user32 = ctypes.windll.user32

_user32.CallNextHookEx.argtypes = [
    ctypes.c_void_p,
    ctypes.c_int,
    ctypes.wintypes.WPARAM,
    ctypes.wintypes.LPARAM
]
_user32.CallNextHookEx.restype = LRESULT

CMPFUNC = ctypes.WINFUNCTYPE(
    LRESULT,
    ctypes.c_int,
    ctypes.wintypes.WPARAM,
    ctypes.wintypes.LPARAM
)

_user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int,
    CMPFUNC,
    ctypes.wintypes.HINSTANCE,
    ctypes.wintypes.DWORD
]
_user32.SetWindowsHookExW.restype = ctypes.c_void_p

_user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
_user32.UnhookWindowsHookEx.restype = ctypes.wintypes.BOOL

_user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
_user32.GetAsyncKeyState.restype = ctypes.c_short


class MouseHook:
    def __init__(self, gui=None):
        self.gui = gui
        self.left_pressed = False
        self.right_pressed = False
        self.xbutton1_pressed = False
        self.xbutton2_pressed = False
        self.hook = None
        self.kb_hook = None
        self.callback = None
        self.kb_callback = None
        # VK codes the user is physically holding (injected events ignored)
        self._physical_keys = set()
        self.thread = threading.Thread(target=self._run_hook, daemon=True)
        self.thread.start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def keyboard_hook_active(self) -> bool:
        return bool(self.kb_hook)

    def is_button_physically_down(self, button: str) -> bool:
        """Physical state of the left/right mouse button.

        Falls back to GetAsyncKeyState if the mouse hook is not installed.
        """
        if self.hook:
            return self.left_pressed if button == "left" else self.right_pressed
        vk = 0x01 if button == "left" else 0x02
        return bool(_user32.GetAsyncKeyState(vk) & 0x8000)

    def is_key_physically_down(self, vk: int) -> bool:
        """True if the user is physically holding the key with this VK code.

        Falls back to GetAsyncKeyState (which also sees injected keys) when the
        keyboard hook could not be installed.
        """
        if not vk:
            return False
        if self.kb_hook:
            return vk in self._physical_keys
        return bool(_user32.GetAsyncKeyState(vk) & 0x8000)

    # ------------------------------------------------------------------
    # Hook thread
    # ------------------------------------------------------------------

    def _post_to_gui(self, key_name):
        gui = self.gui
        if gui is None or not hasattr(gui, "post"):
            return
        popup = getattr(gui, "active_hotkey_popup", None)
        callback = getattr(gui, "active_hotkey_popup_callback", None)
        if popup and callback:
            gui.post(lambda k=key_name, cb=callback: cb(k))
        else:
            from utils.hotkeys import on_mouse_hotkey_press
            gui.post(lambda k=key_name: on_mouse_hotkey_press(gui, k))

    def _run_hook(self):
        def mouse_callback(nCode, wParam, lParam):
            if nCode >= 0:
                try:
                    info = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                    is_injected = bool(info.flags & (LLMHF_INJECTED | LLMHF_LOWER_IL_INJECTED))
                    if not is_injected:
                        if wParam == WM_LBUTTONDOWN:
                            self.left_pressed = True
                        elif wParam == WM_LBUTTONUP:
                            self.left_pressed = False
                        elif wParam == WM_RBUTTONDOWN:
                            self.right_pressed = True
                        elif wParam == WM_RBUTTONUP:
                            self.right_pressed = False
                        elif wParam == WM_XBUTTONDOWN:
                            xbutton = (info.mouseData >> 16) & 0xFFFF
                            if xbutton == 1:
                                self.xbutton1_pressed = True
                            elif xbutton == 2:
                                self.xbutton2_pressed = True
                            self._post_to_gui(f"xbutton{xbutton}")
                        elif wParam == WM_XBUTTONUP:
                            xbutton = (info.mouseData >> 16) & 0xFFFF
                            if xbutton == 1:
                                self.xbutton1_pressed = False
                            elif xbutton == 2:
                                self.xbutton2_pressed = False
                except Exception:
                    pass
            return _user32.CallNextHookEx(self.hook, nCode, wParam, lParam)

        def keyboard_callback(nCode, wParam, lParam):
            if nCode >= 0:
                try:
                    info = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                    is_injected = bool(info.flags & (LLKHF_INJECTED | LLKHF_LOWER_IL_INJECTED))
                    if not is_injected:
                        vk = int(info.vkCode)
                        generic = _GENERIC_VK.get(vk)
                        if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                            self._physical_keys.add(vk)
                            if generic:
                                self._physical_keys.add(generic)
                        elif wParam in (WM_KEYUP, WM_SYSKEYUP):
                            self._physical_keys.discard(vk)
                            if generic:
                                # Keep generic SHIFT down if the other side is still held
                                siblings = [k for k, g in _GENERIC_VK.items() if g == generic]
                                if not any(k in self._physical_keys for k in siblings):
                                    self._physical_keys.discard(generic)
                except Exception:
                    pass
            return _user32.CallNextHookEx(self.kb_hook, nCode, wParam, lParam)

        self.callback = CMPFUNC(mouse_callback)
        self.kb_callback = CMPFUNC(keyboard_callback)
        self.hook = _user32.SetWindowsHookExW(WH_MOUSE_LL, self.callback, None, 0)
        self.kb_hook = _user32.SetWindowsHookExW(WH_KEYBOARD_LL, self.kb_callback, None, 0)

        # Win32 Message Loop (required for low-level hooks to fire)
        msg = ctypes.wintypes.MSG()
        while _user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            _user32.TranslateMessage(ctypes.byref(msg))
            _user32.DispatchMessageW(ctypes.byref(msg))

    def __del__(self):
        try:
            if self.hook:
                _user32.UnhookWindowsHookEx(self.hook)
            if self.kb_hook:
                _user32.UnhookWindowsHookEx(self.kb_hook)
        except Exception:
            pass
