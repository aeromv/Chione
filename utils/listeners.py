"""
utils/listeners.py

Event-driven foreground-window detection using Win32 WinEventHook.
Falls back to a 0.5 s polling loop if the hook fails to register.
"""

import ctypes
import ctypes.wintypes
import sys
import threading
import time

import psutil
import win32gui
import win32process


# ---------------------------------------------------------------------------
# Win32 constants
# ---------------------------------------------------------------------------
EVENT_SYSTEM_FOREGROUND = 0x0003
WINEVENT_OUTOFCONTEXT   = 0x0000
WINEVENT_SKIPOWNPROCESS = 0x0002

WinEventProcType = ctypes.WINFUNCTYPE(
    None,
    ctypes.wintypes.HANDLE,   # hWinEventHook
    ctypes.wintypes.DWORD,    # event
    ctypes.wintypes.HWND,     # hwnd
    ctypes.wintypes.LONG,     # idObject
    ctypes.wintypes.LONG,     # idChild
    ctypes.wintypes.DWORD,    # idEventThread
    ctypes.wintypes.DWORD,    # dwmsEventTime
)


# ---------------------------------------------------------------------------
# Helper: process name from hwnd
# ---------------------------------------------------------------------------
def _get_process_name(hwnd):
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        return psutil.Process(pid).name()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Win32 message pump (runs in a daemon thread)
# ---------------------------------------------------------------------------
def _message_pump():
    """Pump Win32 messages so the WinEvent hook callback fires."""
    msg = ctypes.wintypes.MSG()
    while ctypes.windll.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
        ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))


def install_win_event_hook(gui) -> None:
    _start_polling_fallback(gui)


def _polling_fallback(gui) -> None:
    # Runs in the background to check if minecraft is currently focused
    while True:
        currentWindow = win32gui.GetForegroundWindow()
        class_name = win32gui.GetClassName(currentWindow) if currentWindow else ""
        process_name = None
        if currentWindow:
            try:
                process_name = psutil.Process(
                    win32process.GetWindowThreadProcessId(currentWindow)[-1]
                ).name()
            except Exception:
                process_name = None

        in_foreground = False
        if class_name in ("GLFW30", "LWJGL"):
            in_foreground = True
        elif process_name:
            proc_lower = process_name.lower()
            if any(x in proc_lower for x in ("java", "minecraft", "az-launcher", "az_launcher", "lunar", "badlion", "minecraft.windows")):
                in_foreground = True

        with gui._state_lock:
            gui.focused_process = process_name
            gui.currently_in_foreground = in_foreground

        time.sleep(0.15)


def _start_polling_fallback(gui) -> None:
    t = threading.Thread(target=_polling_fallback, args=(gui,), daemon=True)
    t.start()


def window_listener(gui) -> None:
    _polling_fallback(gui)
