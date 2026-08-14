"""
utils/mouse_hook.py

Low-level mouse hook to track physical mouse clicks.
Ignores virtual clicks injected by mouse_event or SendInput.
"""

import ctypes
import ctypes.wintypes
import threading

# Win32 hook constants
WH_MOUSE_LL = 14
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP   = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP   = 0x0205

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

# Define types for Win32 API functions to prevent OverflowError on 64-bit systems
LRESULT = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long

ctypes.windll.user32.CallNextHookEx.argtypes = [
    ctypes.c_void_p,
    ctypes.c_int,
    ctypes.wintypes.WPARAM,
    ctypes.wintypes.LPARAM
]
ctypes.windll.user32.CallNextHookEx.restype = LRESULT

CMPFUNC = ctypes.WINFUNCTYPE(
    LRESULT,
    ctypes.c_int,
    ctypes.wintypes.WPARAM,
    ctypes.wintypes.LPARAM
)

ctypes.windll.user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int,
    CMPFUNC,
    ctypes.wintypes.HINSTANCE,
    ctypes.wintypes.DWORD
]
ctypes.windll.user32.SetWindowsHookExW.restype = ctypes.c_void_p

ctypes.windll.user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
ctypes.windll.user32.UnhookWindowsHookEx.restype = ctypes.wintypes.BOOL


class MouseHook:
    def __init__(self, gui=None):
        self.gui = gui
        self.left_pressed = False
        self.right_pressed = False
        self.xbutton1_pressed = False
        self.xbutton2_pressed = False
        self.hook = None
        self.callback = None
        self.thread = threading.Thread(target=self._run_hook, daemon=True)
        self.thread.start()

    def _run_hook(self):
        def hook_callback(nCode, wParam, lParam):
            if nCode >= 0:
                try:
                    info = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                    # LLMHF_INJECTED (0x01) or LLMHF_LOWER_IL_INJECTED (0x02)
                    # If any of these bits are set, it's a virtual click.
                    is_injected = bool(info.flags & 0x01) or bool(info.flags & 0x02)
                    if not is_injected:
                        if wParam == WM_LBUTTONDOWN:
                            self.left_pressed = True
                        elif wParam == WM_LBUTTONUP:
                            self.left_pressed = False
                        elif wParam == WM_RBUTTONDOWN:
                            self.right_pressed = True
                        elif wParam == WM_RBUTTONUP:
                            self.right_pressed = False
                        elif wParam == 0x020B:  # WM_XBUTTONDOWN
                            xbutton = (info.mouseData >> 16) & 0xFFFF
                            key_name = f"xbutton{xbutton}"
                            if xbutton == 1:
                                self.xbutton1_pressed = True
                            elif xbutton == 2:
                                self.xbutton2_pressed = True
                            
                            # Dispatch to GUI main thread safely
                            if self.gui:
                                popup = getattr(self.gui, "active_hotkey_popup", None)
                                callback = getattr(self.gui, "active_hotkey_popup_callback", None)
                                if popup and callback:
                                    self.gui.root.after(0, lambda k=key_name: callback(k))
                                else:
                                    from utils.hotkeys import on_mouse_hotkey_press
                                    self.gui.root.after(0, lambda k=key_name: on_mouse_hotkey_press(self.gui, k))
                        elif wParam == 0x020C:  # WM_XBUTTONUP
                            xbutton = (info.mouseData >> 16) & 0xFFFF
                            if xbutton == 1:
                                self.xbutton1_pressed = False
                            elif xbutton == 2:
                                self.xbutton2_pressed = False
                except Exception:
                    pass
            return ctypes.windll.user32.CallNextHookEx(self.hook, nCode, wParam, lParam)

        self.callback = CMPFUNC(hook_callback)
        self.hook = ctypes.windll.user32.SetWindowsHookExW(
            WH_MOUSE_LL,
            self.callback,
            None,
            0
        )

        # Win32 Message Loop
        msg = ctypes.wintypes.MSG()
        while ctypes.windll.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
            ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))

    def __del__(self):
        if self.hook:
            ctypes.windll.user32.UnhookWindowsHookEx(self.hook)
